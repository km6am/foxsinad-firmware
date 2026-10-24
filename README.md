# foxsinad_fw

Firmware that turns an AI6YM **PicoFox r3** into a 2 m FM test
transmitter you control over USB. It sends a carrier or an FM tone, and
its output level can be stepped in 0.25 dB steps.

It was built for testing receivers:
- **Sensitivity:** finding a radio's 12 dB SINAD point. Step the level
  down while a SINAD meter listens to the radio's audio.
- **Desense:** how much sensitivity a receiver loses when a strong signal
  is nearby.

**The PicoFox is AI6YM's design: both the hardware and the original
firmware ([github.com/ai6ym/PicoFox](https://github.com/ai6ym/PicoFox)).**
Assembled units are available from
[AI6YM.radio](https://ai6ym.radio/picofox). This project only replaces the
firmware, for bench measurement instead of fox hunting.

```
$ ./run tools/foxctl.py --call N0CALL --freq 145.55 --att 64 --tone 1000 3000
CALL N0CALL
FREQ 145.550000
ATT 64
TONE 1000 3000
```

## What it does

- **Carrier or FM tone**, 144.02–147.98 MHz. Tone 100–2400 Hz; peak
  deviation 100 Hz–10 kHz as commanded (the delivered deviation is
  lower; see [THEORY.md §4](docs/THEORY.md#4-what-the-steps-do-to-the-signal)).
- **Output level in 0.25 dB steps**, 128 steps (31.75 dB), using the
  PicoFox r3's built-in attenuator. You can change it while transmitting.
- **Simple text commands over USB.** Each command gets one reply, and
  `OK` means the change has been made. See [docs/API.md](docs/API.md).
- **Safe at power-on.** RF is off, attenuation is at maximum, and nothing
  is remembered from before.
- **Station identification built in.** RF can't be turned on until you set
  a callsign. The PicoFox then sends a Morse ID every 9 minutes while
  transmitting, and again when RF is turned off.

## Before you transmit

- **You need an amateur radio license for 2 m.**
- **Stay within your country's 2 m band.** It's 144–148 MHz in ITU
  Region 2 (the Americas), but **144–146 MHz in Region 1** (Europe,
  Africa, the Middle East), and it varies by country in Region 3. The
  firmware allows up to 147.98 MHz and doesn't know where you are.
- **Station identification** follows US rules (Part 97 §97.119). Check
  the rules where you are.
- **Never connect the output straight to a receiver.** Full output is
  about +12 dBm (16 mW), enough to risk damaging a receiver's input when
  connected by cable.
  - For sensitivity tests, put fixed attenuators between the PicoFox and
    the receiver. Typical 2 m receivers reach 12 dB SINAD around
    −120 dBm. The PicoFox's lowest output is about −20 dBm, so you need
    roughly **100 dB of fixed attenuation**, plus good shielding. (That's
    an estimate from typical receiver figures, not a measurement.)
- **Harmonics and other unwanted outputs haven't been measured.** Don't
  connect an antenna without checking them yourself.

## Measured performance (one unit)

One PicoFox r3, connected by cable to an HP 8935 test set. Methods, plots
and limits: [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

| | Result |
|---|---|
| Best SINAD | **at least 23.6 dB**: that's the 8935's reading, at every attenuator setting. Through a radio it read about 32 dB. |
| Output at `ATT 0`, 145.55 MHz | about **+12 dBm** (cable loss not removed) |
| Attenuator range | **31.77 dB** (nominal 31.75 dB). Level falls with every step. |
| Level, 144.1–146.5 MHz | within 0.35 dB at `ATT 64` and `ATT 127`. At full power, 0.68 dB lower at 146.5 MHz. |

**Limitations to know.** All are explained in
[docs/THEORY.md](docs/THEORY.md#9-known-issues).
- Version 0.2.0's fix to the end-of-transmission Morse ID hasn't been
  run on a board yet. The rest of the firmware has.
- The tone frequency runs about 1% high.
- The true deviation hasn't been confirmed by an independent method.
- The tone is built in steps, which creates an unwanted copy of it near
  5000 Hz minus the tone frequency. When measuring SINAD, use a low-pass
  filter that cuts off below that copy: a 3 kHz low-pass for a 1 kHz tone.

## Hardware

- **Tested on a PicoFox r3.** The firmware also supports the r2, which has
  no attenuator, so `ATT` is refused there. But it hasn't been tried on
  an r2.
- Buttons and switch (from the schematic):
  - **SW1:** RUN (reset)
  - **SW2:** BOOTSEL
  - **SW3:** power
- **SW3 must be on to use the PicoFox over USB.** On the tested r3, SW3
  also switches USB power.

## Getting started

You need [arduino-cli](https://arduino.github.io/arduino-cli/) and
Python 3.10 or newer.

On macOS or Linux:

```bash
./bootstrap          # once: makes a Python environment (.venv) with pyserial
./build.sh setup     # once: installs the Arduino-Pico core and the Si5351 library
./build.sh           # builds build/foxsinad_fw.ino.uf2
./run tools/flash.py # puts it on the PicoFox
```

`./run` starts a tool with a Python that is 3.10 or newer and has
pyserial, trying the project's `.venv` first.

**On Windows,** use `run.cmd` in place of `./run`. `build.sh` and
`bootstrap` are shell scripts. Run them from Git Bash or WSL, or do the
same by hand:
- run the `arduino-cli` commands shown in `build.sh`
- create the Python environment with:
  ```
  py -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
  ```

**Flashing.** `tools/flash.py` asks the board to restart into its
bootloader, by opening the serial port at 1200 baud. It then copies the
firmware across and checks that the new firmware answers.

If it says the board didn't enter the bootloader (for example, because
the board still runs other firmware), do it by hand:
1. Hold **SW2**.
2. Tap **SW1**.
3. Release **SW2**.
4. Run `./run tools/flash.py` again.

### Going back to the stock PicoFox firmware

```bash
./run tools/flash.py --stock
```

This checks [AI6YM's repository](https://github.com/ai6ym/PicoFox/tree/main/releases)
for firmware images and compares them with any copies you saved before.
Each image is listed as new, changed since your copy, or the same as your
copy, and the tool asks which one to flash. Press Enter for the suggested
one.

- Downloads are checked against GitHub's file hash and saved in `stock/`,
  so next time no download is needed. If GitHub can't be reached, your
  saved copies are offered.
- After flashing, the tool checks that the PicoFox's USB drive (with
  `settings.txt`) appears.
- To fetch an image without flashing it, add `--download-only`.
- To get back to this firmware afterwards, run `./run tools/flash.py`.
  If the stock firmware doesn't respond to the automatic reset, use the
  buttons as described above.

### Using it

```bash
./run tools/foxctl.py --call N0CALL --freq 145.55 --att 64 --tone 1000 3000
./run tools/foxctl.py --att 80        # change the level while transmitting
./run tools/foxctl.py --status
./run tools/foxctl.py --off           # sends the Morse ID, then turns RF off
```

**RF stays on after a command finishes.** Use `--off` when you're done.

`tools/foxctl.py` also works as a Python library: `from foxctl import
PicoFox`. It checks every value before sending it, because the firmware
reads text that isn't a number as 0 (see
[docs/API.md](docs/API.md#check-numbers-before-you-send-them)).

You can also type commands in any serial terminal. For example, on macOS:

```bash
.venv/bin/python -m serial.tools.miniterm -e /dev/cu.usbmodem* 115200
```

`-e` shows what you type. On Linux the port is `/dev/ttyACM0` or
similar; on Windows it's a `COM` port.

## Documentation

- [docs/API.md](docs/API.md): every command, reply, error and event, and
  the timing rules. Start here to control the PicoFox from your own
  software.
- [docs/THEORY.md](docs/THEORY.md): how it works.
- [docs/PERFORMANCE.md](docs/PERFORMANCE.md): the measurements, with
  plots and limits.

## What's in this repository

```
foxsinad_fw/foxsinad_fw.ino   the firmware
build.sh                      builds the firmware with arduino-cli
tools/flash.py                puts firmware on the PicoFox over USB
tools/foxctl.py               controls the PicoFox (command line or Python)
run, run.cmd, bootstrap       start the tools with a suitable Python
tests/                        tests for the tools and docs
docs/                         API reference, how it works, measurements
CHANGELOG.md                  what changed in each version
```

### Tests

```bash
./bootstrap --dev                # adds pytest to .venv
.venv/bin/python -m pytest
```

- The tests run the tools against a simulated serial port.
- They also compare the docs with the firmware source: every command and
  error message must appear in `docs/API.md`, and the version numbers
  must agree.
- They don't test the firmware on hardware. That's what the measurements
  in `docs/PERFORMANCE.md` are for.

## Credits and changes

This firmware is based on the stock PicoFox firmware
([github.com/ai6ym/PicoFox](https://github.com/ai6ym/PicoFox)), Copyright
2025 Giorgi Enterprises LLC dba AI6YM.radio. The PicoFox hardware is
AI6YM's design too. Thanks to AI6YM for publishing both openly, and for
advice on changing the attenuator during a transmission.

**Kept from the stock firmware:**
- the pin assignments and board-revision detection
- the way the Si5351 is used: fixed divide-by-6 output, with the
  frequency set and modulated through its PLL
- the timing loop
- the attenuator driver

**Removed:**
- the USB storage drive and `settings.txt`
- audio file playback
- the fox transmit cycle

**Added:**
- the USB command interface
- the callsign requirement and Morse ID schedule
- tone generation with adjustable tone and deviation
- changing the attenuator during a transmission, with RF briefly off
  while it changes
- all radio hardware handled by one processor core

**Build changes:**
- uses the standard Arduino-Pico core, with two pins set in the firmware
  instead of by a custom board definition
- uses the Pico SDK's USB support instead of Adafruit TinyUSB

## License

- **Firmware** (`foxsinad_fw/`): [CC BY-NC-SA 4.0](LICENSE), as the stock
  PicoFox firmware's license requires.
  - Non-commercial use only. For commercial use, ask Giorgi Enterprises
    LLC dba AI6YM.radio.
  - Changed versions must use the same license.
- **Documentation** (`docs/`, `README.md`, `CHANGELOG.md`):
  [CC BY-NC-SA 4.0](LICENSE) too, to match the firmware.
- **Everything else** (tools, tests, build and launcher scripts):
  [MIT](LICENSE-MIT), Copyright 2026 Badgie Miller, KM6AM.
