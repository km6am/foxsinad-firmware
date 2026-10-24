# How it works

This explains how foxsinad_fw makes a PicoFox r3 into a programmable FM
test source, and what that means if you use it for measurements.

Each statement says how it's known:
- **from the code**: what the firmware source does. Statements about
  firmware behavior are from the code unless marked otherwise.
- **from the schematic**: read from the published PicoFox schematic.
- **measured**: seen on real hardware, with how.
- **computed**: calculated from the firmware's exact arithmetic.
- **inferred**: reasoned, but not checked independently.

## 1. The signal path

*From the schematic.* The published PicoFox schematic (the sheet is
marked REV2 but already shows the r3 attenuator) has these stages, in
order:

1. **Signal generation.** An Si5351A clock generator, locked to a 25 MHz
   TCXO. Its CLK0 output feeds the RF path; CLK1 and CLK2 go to the
   expansion header.
2. A **3 dB attenuator pad**.
3. A **low-pass filter**.
4. The **amplifier stage**, built around the BVA1761. It includes the
   step attenuator, set through a serial interface (pins `LE`, `CLK` and
   `DATA`). The firmware switches the amplifier on and off with GPIO 2
   (`AMP_EN`; low = on). The amplifier runs from the battery supply after
   the power switch, and the schematic notes that its maximum output
   rises with supply voltage.
5. A second **low-pass filter**.
6. Two **jumpers**, JP1 and JP2, for an optional external amplifier. Both
   must be closed for normal use.
7. The **SMA output**.

The RP2040 talks to the Si5351 over I2C on GPIO 0 (SDA) and GPIO 1 (SCL).
**The attenuator's serial interface uses the same two pins**, plus a latch
pin on GPIO 4. GPIO 22–25 tell the firmware the board revision. The board's
buttons and switch are listed in the [README](../README.md#hardware).

## 2. Setting the frequency

The Si5351 makes its output by dividing down the frequency of an
internal oscillator (its PLL). The firmware fixes that divider at **6** and
sets the frequency by tuning the PLL to 6 × the wanted output. This is
the stock PicoFox firmware's scheme. Moving only the PLL keeps each update
small: a few registers.

The Si5351's PLL runs from 600 to 900 MHz, so dividing by 6 can reach 100
to 150 MHz. The firmware allows only **144.02–147.98 MHz**: the widest
2 m band (ITU Region 2), less a 20 kHz margin for the largest deviation.
In other regions the band is narrower; see the
[README](../README.md#before-you-transmit).

## 3. Making FM

The firmware makes FM by **retuning the PLL 5000 times a second**. On
each step, the RF core:

1. Advances a 32-bit phase counter by `tone × 2³² / 5000`.
2. Uses the top 8 bits of that counter to pick an entry from a
   **256-entry sine table**.
3. Scales the entry to the commanded deviation.
4. Writes the new PLL frequency, 6 × (carrier + deviation), over I2C at
   1 MHz. The stock PicoFox firmware notes that the bus must run at
   800 kHz or more to fit an update into each step.
5. Waits for the next step.

**The tone runs about 1% high.** *Measured* on an HP 8935: demodulated
tones read 1.0101 × the requested frequency (300 → 303.0 Hz, 500 →
505.0 Hz, 1500 → 1518.4 Hz, 2000 → 2020.2 Hz). So the firmware is making
about 5050 steps per second instead of 5000.
- *From the code and computed:* each step should last 200 µs. Each step
  starts a timer, writes to the Si5351, and waits until 197 µs have
  passed, using a correction constant (`SAMPLE_WRITE_CORR_US = −3`)
  carried over from the stock PicoFox firmware. The measured rate means
  each step actually lasts about 198 µs. So the code that runs between
  the end of one wait and the start of the next step takes about 1 µs.
- *From the code:* in the stock firmware, reading each sample from flash
  memory happens in that same gap, outside the timed wait, so the −3 µs
  correction makes up for it. This firmware computes samples instead, so
  its gap is shorter and the same correction makes each step too short.
- A constant of −1 should fix the rate. That hasn't been tested.
- The Morse ID tone runs 1% high too.
- SINAD meters that lock onto the tone, which is normal, aren't affected.
  A meter with a fixed 1000 Hz notch would need checking.

**The sine table is accurate enough.** *Computed* from the firmware's exact
arithmetic: the table alone gives 43–45 dB SINAD for tones from 300 to
2400 Hz. That's well above any SINAD measured so far (§7), so the table
doesn't limit it.

## 4. What the steps do to the signal

The deviation changes in steps and holds still in between, like a
staircase. That has three consequences.

**(a) The tone comes out smaller than commanded**: by 6% at 1 kHz, but
by 34% at 2400 Hz. *Computed:*
stepping reduces the tone by the factor sin(πf/5000)/(πf/5000), where f
is the tone frequency:

| Tone | Delivered ÷ commanded | Unwanted copy at | Copy's level vs tone |
|---|---|---|---|
| 300 Hz | 0.994 (−0.05 dB) | 4700 Hz | −23.9 dB |
| 1000 Hz | 0.936 (−0.58 dB) | 4000 Hz | −12.0 dB |
| 2400 Hz | 0.662 (−3.58 dB) | 2600 Hz | −0.7 dB |

To get a delivered deviation D, command D divided by that factor. (The
frequencies in the table assume exactly 5000 steps per second. At the
real rate they're about 1% higher.)

**(b) Stepping adds an unwanted copy of the tone near 5000 − f Hz.** Its
level relative to the tone is f / (5000 − f), as in the table. For a
1 kHz tone it's at 4 kHz and 12 dB down. **So when measuring SINAD, use
a low-pass filter that cuts off below 5000 − f Hz.** The tone's own
harmonics must stay in, because SINAD counts them as distortion. For a
1 kHz tone, a 3 kHz low-pass filter does this; the SINAD figures in §7 were
measured that way. Higher tones bring the copy into any normal audio
filter.

**(c) Deviation meters that read the peak see the steps, not just the
tone.** *Computed:* for a 1 kHz tone there are 5 steps per cycle, and
the highest step is 0.950–1.000 × the commanded deviation, depending on
where the steps fall on the sine wave. *Measured* on an HP 8935, the peak
reading depends heavily on the meter's audio filter:
- With a 15 kHz low-pass filter it read 1.2–1.4 × commanded (1 kHz tone,
  depending on the deviation).
- With a 3 kHz low-pass filter, after correcting the commanded value as
  in (a), it read 1.04 × at 800 Hz, rising to 1.86 × at 2400 Hz. That's
  *consistent with* the unwanted copy getting through the filter, but
  doesn't prove it.
- At 300 Hz it read 0.75 ×. That's *consistent with* the meter's own
  300 Hz high-pass filter cutting the tone.

**So the true deviation hasn't been confirmed by an independent method
yet.** A carrier-null (Bessel zero) measurement doesn't depend on any
audio filter, and is planned. Until then, treat the commanded deviation
as nominal.

## 5. The attenuator, and why ATT turns RF off briefly

The BVA1761 takes a 16-bit word: 8 bits of attenuation, lowest bit first,
then 8 zero bits, then a pulse on `LE` to apply it. The firmware sends it
by switching the I2C pins directly:
1. It stops the I2C hardware.
2. It holds SCL low before changing SDA, so the Si5351 never sees the
   start of an I2C message.
3. It clocks the bits out and pulses `LE`.
4. It restarts I2C.

This is the stock PicoFox firmware's method.

The stock firmware sets the attenuator between fox transmissions, while RF
is off, which is all a fox needs. This firmware changes level during a
transmission. On the hardware designer's advice, it doesn't program the
attenuator while the Si5351 is transmitting. So `ATT` with RF on:

1. turns off the Si5351 output and the amplifier,
2. sets the attenuator,
3. retunes the Si5351 completely, to be sure its registers are correct,
4. turns RF back on.

*Measured:* in a sweep that changed the attenuator 16 times while a tone
was transmitting, SINAD was back to 23.6–23.7 dB after every change
(§7). Nobody has listened to the brief gap itself.

## 6. The two cores

The RP2040 has two processor cores.
- **The RF core (core 1)** owns all the radio hardware once the firmware
  has started. That covers the tone loop, every Si5351 write, and the
  attenuator. The attenuator borrows the I2C pins, so only one core may
  touch the hardware.
- **The serial core (core 0)** reads commands. It answers `HELLO`, `CALL`
  and `STATUS` itself.
- For anything that changes the radio, the serial core puts the command
  in a **one-command mailbox** and waits. The RF core checks the mailbox
  at every step, about every 0.2 ms, applies the command, and signals
  back. Only then does the serial core reply `OK`.
- The RF core sends the Morse ID inside the same loop, so a command that
  arrives during an ID waits until it ends.
- At startup, the serial core sets up the pins, the attenuator (at 127)
  and the Si5351. It then lets the RF core start.

## 7. Measured performance, in brief

These figures come from one PicoFox r3, connected by cable to an HP 8935.
Details, plots and limits are in [PERFORMANCE.md](PERFORMANCE.md).

- **Best SINAD: at least 23.6 dB.** The 8935's FM demodulator read
  23.6–23.7 dB at every attenuator setting (1 kHz tone, 3 kHz commanded
  deviation, 300 Hz–3 kHz filters). Through a real receiver the same
  signal read about 32 dB, so the 8935 figure is a lower bound; why it
  reads lower is not yet settled.
- **Attenuator:** 31.77 dB total, against 31.75 dB nominal. Each measured
  setting (every 4th, at 145.55 MHz) is within 0.83 dB of the ideal
  value.
- **Output at `ATT 0`:** about +12 dBm at 145.55 MHz, measured at the end
  of a short cable.

## 8. Building with the standard Arduino-Pico core

The stock PicoFox firmware is built with AI6YM's own "AI6YM PicoFox" board
definition, in his version of the Arduino-Pico core. It sets every pin
correctly for this board. This firmware uses the standard Arduino-Pico
core with its generic `rpipico` board instead, which has different pin
defaults. Two pins must therefore be set in the firmware:

- **I2C:** the generic board puts I2C on GPIO 4 and 5. GPIO 4 is the
  attenuator's latch pin on the PicoFox, so the Si5351 never gets a
  command. Everything replies `OK` but nothing is transmitted (*measured*).
  The firmware moves I2C back to GPIO 0 and 1.
- **LED:** the generic board's LED pin is GPIO 25, which on the PicoFox is
  a board-revision pin. The firmware uses GPIO 3 instead.

The firmware has no USB storage drive, so it uses the Pico SDK's standard
USB support rather than Adafruit TinyUSB.

## 9. Known issues

- **Tones run about 1% high** (§3).
- **Text that isn't a number counts as 0**, so `ATT x` means full power.
  Check values before sending ([API.md](API.md#check-numbers-before-you-send-them)).
- **A line over 63 characters** gets an error, and its remainder is read
  as a new line.
- **The true deviation hasn't been confirmed independently** (§4).
- **Unwanted copies of the tone** sit near 5000 − f Hz, so measure SINAD
  with filters that stop below them (§4).
- **Output level vs frequency isn't fully understood.** At full power it
  was 0.7 dB lower at 146.5 MHz, repeatably, and at 147.9 MHz readings
  changed by up to 0.8 dB between runs. See
  [PERFORMANCE.md](PERFORMANCE.md#2-output-level-across-the-band).
- **How long `ATT` turns RF off** hasn't been measured.
