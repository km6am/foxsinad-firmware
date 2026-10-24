# Serial API

Reference for foxsinad_fw version **0.2.0**. It describes what
`foxsinad_fw/foxsinad_fw.ino` does. For why it works this way, see
[THEORY.md](THEORY.md).

The firmware runs on two processor cores. This document calls them the
**serial core** (core 0, which reads commands) and the **RF core**
(core 1, which drives the radio hardware).

## Connecting

- The PicoFox appears as a **USB serial port**:
  - macOS: `/dev/cu.usbmodem*`
  - Linux: `/dev/ttyACM*`
  - Windows: a `COM` port
- Its USB vendor ID is `0x2E8A` (Raspberry Pi).
- The baud rate doesn't matter, because it's USB. Use 115200.
- **To reboot into the bootloader** (for flashing), open the port at
  **1200 baud** and close it again. `tools/flash.py` does this for you.
  If that doesn't work, use the buttons: hold BOOTSEL (SW2), tap RUN
  (SW1), release BOOTSEL.

## Sending commands

- Send **one command per line**, ending with CR, LF or CRLF. Empty lines
  are ignored.
- Commands are **not case-sensitive**. Separate arguments with spaces.
- Every command gets **exactly one reply line**, which starts with `OK`
  or `ERR`.
- Lines starting with `*` are **events**, not replies. An event can
  arrive at any time, including just before a reply.
- **Keep lines to 63 characters or fewer.** On a longer line the firmware
  replies `ERR line too long`, drops the 64th character, and reads the
  rest as a new line, which usually causes a second `ERR`.

### Check numbers before you send them

The firmware converts numbers with the C functions `atol()` and `atof()`,
and they don't report bad input:
- Text that isn't a number becomes **0**. `ATT foo` is accepted as
  `ATT 0`, which is **full power**.
- Extra characters after a number are ignored. `ATT 12dB` is accepted as
  `ATT 12`.

So check every value before sending it. `tools/foxctl.py` does this for
you.

## Commands

| Command | Reply | Needs a callsign |
|---|---|---|
| `HELLO` or `VER` | `OK FOXSINAD <version> REV<board>` | no |
| `CALL <callsign>` | `OK CALL <CALLSIGN>` | — |
| `FREQ <MHz>` | `OK FREQ <MHz>` | no |
| `ATT <0-127>` | `OK ATT <n>` | no |
| `TONE <Hz> <deviation Hz>` | `OK TONE <Hz> <deviation>` | **yes** |
| `CARRIER ON` | `OK CARRIER` | **yes** |
| `OFF`, `TONE OFF` or `CARRIER OFF` | `OK OFF` | no |
| `ABORT` | `OK ABORT` | no |
| `ID` | `OK ID` | RF must be on |
| `STATUS` | `OK STATUS <key=value …>` | no |

For any command that changes the radio (`FREQ`, `ATT`, `TONE`,
`CARRIER`, the off commands, `ABORT` and `ID`), **`OK` means the change
has been made**, not just queued. See [Timing](#timing).

### HELLO

```
→ HELLO
← OK FOXSINAD 0.2.0 REV3
```

`REV` is the board revision, read from configuration pins on the board:
`2`, `3`, or `0` if the pattern is unrecognized. Only `REV3` has the
attenuator. Send `HELLO` first, to confirm you're talking to this
firmware.

### CALL <callsign>

Sets the callsign sent in the Morse ID. **RF can't be turned on until a
callsign is set.**
- 1–11 characters: letters, digits and `/`. Stored in capitals.
- Can be changed at any time. The next ID uses the new callsign.
- It isn't saved: it's lost when the PicoFox is reset or switched off.
- Errors:
  - `ERR CALL <callsign> (1-11 chars)`: missing, or too long
  - `ERR callsign: letters, digits, / only`

### FREQ <MHz>

Sets the carrier frequency.
- Allowed range: **144.0200 to 147.9800 MHz**. That's 144–148 MHz, less a
  20 kHz margin for the largest deviation.
- **144–148 MHz is the 2 m band only in ITU Region 2 (the Americas). In
  Region 1 (Europe, Africa, the Middle East) it's 144–146 MHz, and in
  Region 3 it varies by country.** The firmware doesn't know where you
  are, so staying inside your band is up to you.
- Error: `ERR FREQ 144.0200-147.9800 MHz`.
- The reply shows the frequency with 6 decimal places.
- While transmitting, the carrier moves at once. RF stays on, but the
  retune resets the Si5351's PLL, so expect a brief disturbance.
- At startup: 146.565 MHz.

### ATT <0-127>

Sets the attenuator, in **steps of 0.25 dB**. `ATT 0` gives maximum
output; `ATT 127` gives maximum attenuation (31.75 dB below).
- PicoFox r3 only. On other boards: `ERR no attenuator on this board revision`.
- Error: `ERR ATT 0-127 (0.25 dB steps)`.
- **While transmitting**, the firmware turns RF off for a moment, sets the
  attenuator, and turns RF back on. The mode doesn't change and no ID is
  sent. How long RF is off hasn't been measured; the code involves only a
  few register writes, so it's probably around a millisecond (inferred).
- At startup: 127 (maximum attenuation).
- Measured output for each setting: [PERFORMANCE.md](PERFORMANCE.md).

### TONE <Hz> <deviation Hz>

Transmits FM with a sine-wave tone.
- Tone: **100–2400 Hz**. Error: `ERR TONE <100-2400 Hz> <dev Hz>`.
- Deviation: **100–10000 Hz** peak. Error: `ERR deviation 100-10000 Hz`.
- Needs a callsign, or you get `ERR set CALL first`.
- The usual 2 m SINAD test signal is `TONE 1000 3000`.
- Sending `TONE` while already transmitting switches to the new tone. RF
  stays on and the ID timer continues. The switch resets the PLL, so
  expect a brief disturbance.

**The deviation you set is the "commanded" deviation. The delivered tone
is smaller.** The firmware builds the tone from 5000 steps per second,
which multiplies the tone by sin(πf/5000)/(πf/5000): 0.94 for a 1 kHz
tone, but 0.66 for a 2400 Hz tone. The stepping also adds unwanted copies of the tone near
5000 − f Hz. And tones currently run about 1% high. Read
[THEORY.md §3–4](THEORY.md#3-making-fm) before treating the deviation as
calibrated.

### CARRIER ON

Transmits an unmodulated carrier, for measuring level or as an
interfering signal.
- Needs a callsign.
- Error: `ERR CARRIER ON|OFF` (any other argument).

### OFF, TONE OFF, CARRIER OFF

All three turn RF off.
- If anything was transmitted since the last ID, **the Morse ID is sent
  first**. The reply then comes after `*ID START` and `*ID DONE`.
- If RF is already off, the reply is immediate.

### ABORT

Turns RF off **without** the final Morse ID. It's meant for the bench;
on the air, use `OFF`. If an ID is already being sent, `ABORT` waits for
it to finish, like every other command.

### ID

Sends the Morse ID now. The reply `OK ID` comes after the ID finishes,
following `*ID START` and `*ID DONE`. If RF is off, the reply is
`ERR RF is off`.

### STATUS

Returns the current state on one line:

```
OK STATUS mode=TONE freq=145.550000 att=40 tone=1000 dev=3000 call=N0CALL rev=3 since_id=20 up=336
```

| Key | Meaning |
|---|---|
| `mode` | `OFF`, `CARRIER` or `TONE` |
| `freq` | carrier frequency, MHz |
| `att` | attenuator setting, 0–127 |
| `tone`, `dev` | values from the last mode command. `CARRIER` and `OFF` set both to 0. At startup they read 1000 and 3000, but RF is off. |
| `call` | callsign, or `-` if none is set |
| `rev` | board revision, as in `HELLO` |
| `since_id` | seconds since the last ID, or since RF was last turned on from off. At startup it counts from power-on. |
| `up` | seconds since the PicoFox started |

`STATUS` is answered by the serial core alone, so it replies at once,
even during an ID.

### Errors

Any unknown command gets `ERR unknown command <COMMAND>`.

## Events

| Event | Meaning |
|---|---|
| `*BOOT FOXSINAD <version> REV<board>` | Sent once at startup. You'll usually miss it, because the port can't be opened that early. Send `HELLO` instead. |
| `*ID START` | A Morse ID is starting. It may be the automatic ID, the ID before RF-off, or an `ID` command. |
| `*ID DONE` | The ID has finished. Transmission continues as before, or, for an ID before RF-off, RF now turns off. |

**Anything you measure between `*ID START` and `*ID DONE` is not the test
signal.** During the ID the PicoFox sends a 600 Hz Morse tone at 20 words
per minute, at the current `TONE` deviation (or 3 kHz if no tone is
set), so discard those readings.

## Automatic ID

While RF is on, the firmware sends the Morse ID once **more than 9
minutes** have passed since the last ID, or since RF was turned on. It
also sends the ID when RF is turned off, if anything was transmitted
since the last ID. This follows US Part 97 §97.119; check the rules in
your own country.

An ID takes about **4–10 s** for typical callsigns. That's computed from
the firmware's timing: a 5-character callsign takes 4.5 s, which matches
a measurement. The longest possible callsign (11 characters) takes up to
**16 s**.

## Startup state

Nothing is saved between power-ups. Every start looks the same:

| | At startup |
|---|---|
| RF | off |
| `ATT` | 127 (maximum attenuation) |
| `FREQ` | 146.565 MHz |
| callsign | none, so RF can't be turned on |

So after connecting, always send the full setup, in this order: `HELLO`,
`CALL`, `FREQ`, `ATT`, then `TONE` or `CARRIER`.

To find out whether the PicoFox reset unexpectedly, send `STATUS`: `up=`
starts again from 0, and `call=-` means the callsign is gone.

## Timing

- The RF core checks for a new command about every 0.2 ms, whether or not
  RF is on, and applies it then.
- **During a Morse ID, commands wait until the ID ends**, which can take
  up to 16 s. **Use a reply timeout of at least 20 seconds.**
- `HELLO`, `CALL` and `STATUS` don't wait for the RF core. But a command
  sent while an earlier one is still waiting is only read once that one
  is done.
- After `ATT` or `FREQ`, give the receiver you're testing time to settle
  before measuring. The firmware can't know how long that is.

## Checklist for writing your own driver

1. Find the port (vendor ID `0x2E8A`), open it, send `HELLO`, and check
   that the reply contains `FOXSINAD`.
2. After each command, read lines until one starts with `OK` or `ERR`.
   Keep any `*` lines as events.
3. Treat `ERR` as a failure. Never assume a setting worked.
4. Check numbers before sending them (see above).
5. Ignore measurements taken between `*ID START` and `*ID DONE`.
6. Finish with `OFF`, or `ABORT` on the bench, so RF is left off.

## Example session

```
→ HELLO
← OK FOXSINAD 0.2.0 REV3
→ CALL N0CALL
← OK CALL N0CALL
→ FREQ 145.55
← OK FREQ 145.550000
→ ATT 64
← OK ATT 64
→ TONE 1000 3000
← OK TONE 1000 3000
     (measure)
→ ATT 80
← OK ATT 80
     (measure)
→ OFF
← *ID START
← *ID DONE
← OK OFF
```
