# Changelog

## 0.2.0 — unreleased

First public version.

**Firmware**
- 2 m FM test transmitter for the PicoFox r3, based on AI6YM's stock
  PicoFox firmware. Carrier or FM tone on 144.02–147.98 MHz, with the
  output level adjustable in 0.25 dB steps while transmitting.
- Text commands over USB. Each gets one reply, and `OK` means the change
  has been made.
- Safe at power-on: RF off, maximum attenuation, nothing remembered. RF
  can't be turned on until a callsign is set.
- Morse ID every 9 minutes while transmitting, and when RF is turned off
  if anything was sent since the last ID.
- All radio hardware is handled by one processor core. Changing the
  attenuator during a transmission turns RF off briefly.
- Builds with the standard Arduino-Pico core and the Pico SDK's USB
  support.
- The Si5351 output is kept off whenever RF is off.

**Tools**
- `tools/flash.py`: puts firmware on the PicoFox over USB, and checks that
  it answers. Works on macOS, Linux and Windows.
- `tools/flash.py --stock`: restores AI6YM's stock firmware. It checks his
  repository for new or changed images, offers them alongside your saved
  copies, and verifies each download's hash.
- `tools/foxctl.py`: controls the PicoFox from the command line or from
  Python. Finds the board automatically, and checks values before
  sending them.
- `run`, `run.cmd` and `bootstrap`: start the tools with a Python that
  really is 3.10 or newer and has pyserial.

**Documentation**
- Serial API reference, an explanation of how it works, and measurements
  of one PicoFox r3.

**Known issues**
- The tone frequency runs about 1% high.
- The true deviation hasn't been confirmed independently.
- The firmware reads text that isn't a number as 0. `tools/foxctl.py`
  checks values first.
- A line longer than 63 characters gets an error, and the rest of the
  line is then read as a new command.
