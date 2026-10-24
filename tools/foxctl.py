#!/usr/bin/env python3
"""Host driver and command-line control for foxsinad_fw (docs/API.md).

As a library:
    from foxctl import PicoFox
    with PicoFox() as fox:              # auto-detects the port
        fox.set_call("N0CALL")
        fox.set_freq(145.55)
        fox.set_att(64)
        fox.tone(1000, 3000)
        ...
        fox.off()                       # sends the Morse ID first

From the command line (./run picks a suitable Python; see README):
    ./run tools/foxctl.py --call N0CALL --freq 145.55 --att 64 --tone 1000 3000
    ./run tools/foxctl.py --off
    ./run tools/foxctl.py --status

RF stays on after the command exits. Turn it off with --off.
Requires pyserial.
"""

import argparse
import sys
import time

import serial
from serial.tools import list_ports

RPI_VID = 0x2E8A  # Raspberry Pi; the Arduino-Pico rpipico board's USB vendor ID

FREQ_MIN_MHZ, FREQ_MAX_MHZ = 144.02, 147.98
TONE_MIN_HZ, TONE_MAX_HZ = 100, 2400
DEV_MIN_HZ, DEV_MAX_HZ = 100, 10000


class PicoFoxError(RuntimeError):
    """ERR reply, timeout, or an argument rejected before sending."""


def find_port():
    """The first serial port with the Raspberry Pi USB vendor ID."""
    for p in sorted(list_ports.comports(), key=lambda p: p.device):
        if p.vid == RPI_VID:
            return p.device
    raise PicoFoxError(
        "no Raspberry Pi USB serial device found - is the PicoFox plugged in "
        "and its power switch (SW3) on?")


class PicoFox:
    """Synchronous driver. Each method returns once the firmware has applied
    the change (its OK reply). Asynchronous '*' event lines are collected in
    .events rather than returned."""

    def __init__(self, port=None, timeout_s=20.0, check=True):
        self.port = port or find_port()
        self.timeout_s = timeout_s
        self.events = []
        self._ser = serial.Serial(self.port, 115200, timeout=0.5)
        time.sleep(0.3)
        self._ser.reset_input_buffer()
        if check:
            hello = self.hello()
            if not hello.startswith("FOXSINAD"):
                self.close()
                raise PicoFoxError(f"{self.port} answered {hello!r}, not foxsinad_fw")

    def close(self):
        self._ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def cmd(self, line):
        """Send one raw command; return the reply text after 'OK'."""
        self._ser.write((line + "\r\n").encode())
        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            raw = self._ser.readline().decode(errors="replace").strip()
            if not raw:
                continue
            if raw.startswith("*"):
                self.events.append(raw)
                continue
            if raw.startswith("OK"):
                return raw[2:].strip()
            if raw.startswith("ERR"):
                raise PicoFoxError(f"{line!r}: {raw[3:].strip()}")
        raise PicoFoxError(f"{line!r}: no reply within {self.timeout_s} s")

    # The firmware parses numbers with atol/atof, where junk reads as 0
    # (so a garbled ATT means full power). Validate here, before sending.
    @staticmethod
    def _check(name, value, lo, hi):
        if not lo <= value <= hi:
            raise PicoFoxError(f"{name} {value} outside {lo}-{hi}")

    def hello(self):
        return self.cmd("HELLO")

    def set_call(self, callsign):
        return self.cmd(f"CALL {callsign}")

    def set_freq(self, mhz):
        self._check("FREQ (MHz)", float(mhz), FREQ_MIN_MHZ, FREQ_MAX_MHZ)
        return self.cmd(f"FREQ {float(mhz):.6f}")

    def set_att(self, att):
        """0-127 in 0.25 dB steps; 0 is maximum output."""
        if int(att) != att:
            raise PicoFoxError(f"ATT must be an integer, got {att}")
        self._check("ATT", int(att), 0, 127)
        return self.cmd(f"ATT {int(att)}")

    def tone(self, tone_hz, dev_hz):
        """FM tone; dev_hz is the commanded peak deviation (docs/THEORY.md §4)."""
        self._check("tone (Hz)", int(tone_hz), TONE_MIN_HZ, TONE_MAX_HZ)
        self._check("deviation (Hz)", int(dev_hz), DEV_MIN_HZ, DEV_MAX_HZ)
        return self.cmd(f"TONE {int(tone_hz)} {int(dev_hz)}")

    def carrier(self):
        return self.cmd("CARRIER ON")

    def off(self):
        """RF off. Sends the Morse ID first if due, so may take several seconds."""
        return self.cmd("OFF")

    def abort(self):
        """RF off immediately, with no ID. Bench use."""
        return self.cmd("ABORT")

    def send_id(self):
        return self.cmd("ID")

    def status(self):
        """STATUS as a dict of strings."""
        reply = self.cmd("STATUS")  # "STATUS mode=... freq=... ..."
        return dict(kv.split("=", 1) for kv in reply.split()[1:])


def main():
    p = argparse.ArgumentParser(description="Control a PicoFox running foxsinad_fw.")
    p.add_argument("--port", help="serial port (default: auto-detect)")
    p.add_argument("--call", help="callsign (required before RF can turn on)")
    p.add_argument("--freq", type=float, help=f"carrier, MHz ({FREQ_MIN_MHZ}-{FREQ_MAX_MHZ})")
    p.add_argument("--att", type=int, help="attenuator 0-127 (0.25 dB steps; 0 = max output)")
    p.add_argument("--tone", nargs=2, type=int, metavar=("HZ", "DEV_HZ"),
                   help="FM tone: audio frequency and peak deviation, Hz")
    p.add_argument("--carrier", action="store_true", help="unmodulated carrier on")
    p.add_argument("--off", action="store_true", help="RF off (sends the ID first)")
    p.add_argument("--abort", action="store_true", help="RF off now, no ID (bench use)")
    p.add_argument("--status", action="store_true", help="print STATUS")
    args = p.parse_args()

    acted = False
    try:
        with PicoFox(args.port) as fox:
            if args.call:
                print(fox.set_call(args.call)); acted = True
            if args.freq is not None:
                print(fox.set_freq(args.freq)); acted = True
            if args.att is not None:
                print(fox.set_att(args.att)); acted = True
            if args.tone:
                print(fox.tone(*args.tone)); acted = True
            if args.carrier:
                print(fox.carrier()); acted = True
            if args.off:
                print(fox.off()); acted = True
            if args.abort:
                print(fox.abort()); acted = True
            if args.status or not acted:
                for k, v in fox.status().items():
                    print(f"{k}={v}")
            for ev in fox.events:
                print(ev)
    except PicoFoxError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
