#!/usr/bin/env python3
"""Put firmware on a PicoFox over USB.

    ./run tools/flash.py                    # this firmware: build/foxsinad_fw.ino.uf2
    ./run tools/flash.py path/to/file.uf2   # any UF2 file
    ./run tools/flash.py --stock            # AI6YM's stock PicoFox firmware
    ./run tools/flash.py --stock --download-only   # fetch it, don't flash

--stock checks AI6YM's repository (github.com/ai6ym/PicoFox, releases/)
for firmware images, compares them with copies saved earlier in stock/,
and asks which one to flash: a new or updated image from GitHub, or the
copy you already have. Press Enter for the suggested one. Downloads are
checked against GitHub's file hash. If GitHub can't be reached, only the
saved copies are offered.

Flashing:
  1. If the RP2040's bootloader drive (RPI-RP2) is already mounted, use
     it. Otherwise open the PicoFox's serial port at 1200 baud and close
     it; that tells firmware built with Arduino-Pico (this firmware and
     the stock firmware) to reboot into the bootloader.
  2. Wait for the RPI-RP2 drive and copy the UF2 onto it. The board
     flashes itself and reboots.
  3. Check the result: this firmware must answer HELLO; the stock
     firmware must show its USB drive with settings.txt.

If step 1 doesn't work, enter the bootloader by hand: hold BOOTSEL (SW2),
tap RUN (SW1), release BOOTSEL. Then run this again.

Works on macOS, Linux and Windows. Requires pyserial.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import string
import sys
import time
import urllib.request
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foxctl import PicoFox, PicoFoxError, find_port  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DEFAULT_UF2 = REPO / "build" / "foxsinad_fw.ino.uf2"
STOCK_DIR = REPO / "stock"
STOCK_API = "https://api.github.com/repos/ai6ym/PicoFox"
STOCK_PAGE = "https://github.com/ai6ym/PicoFox/tree/main/releases"


# ---------------------------------------------------------------- flashing
def _candidate_mounts():
    if sys.platform == "win32":
        return [f"{d}:\\" for d in string.ascii_uppercase]
    user = os.environ.get("USER", "")
    pats = ["/Volumes/*", f"/media/{user}/*", f"/run/media/{user}/*", "/media/*", "/mnt/*"]
    return [m for pat in pats for m in glob.glob(pat)]


def find_bootloader_drive():
    """Mount point of an RP2040 UF2 bootloader drive, or None."""
    for m in _candidate_mounts():
        info = os.path.join(m, "INFO_UF2.TXT")
        try:
            with open(info, errors="replace") as f:
                if "RPI-RP2" in f.read():
                    return m
        except OSError:
            continue
    return None


def find_stock_drive():
    """Mount point of the stock PicoFox firmware's USB drive, or None."""
    for m in _candidate_mounts():
        if os.path.isfile(os.path.join(m, "settings.txt")):
            return m
    return None


def wait_for(fn, timeout_s, what):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            result = fn()
        except PicoFoxError:
            result = None
        if result:
            return result
        time.sleep(0.5)
    raise TimeoutError(what)


def flash(uf2, port=None, stock=False):
    drive = find_bootloader_drive()
    if drive:
        print(f"bootloader drive already mounted at {drive}")
    else:
        try:
            port = port or find_port()
        except PicoFoxError as e:
            sys.exit(f"error: {e}\n(or enter the bootloader by hand: "
                     "hold BOOTSEL (SW2), tap RUN (SW1), release BOOTSEL)")
        print(f"asking {port} to reboot into the bootloader")
        s = serial.Serial(port, 1200)
        s.close()
        try:
            drive = wait_for(find_bootloader_drive, 15, "no RPI-RP2 drive appeared")
        except TimeoutError:
            sys.exit("error: the board didn't enter the bootloader.\n"
                     "Hold BOOTSEL (SW2), tap RUN (SW1), release SW2, then run this again.")
        print(f"bootloader drive at {drive}")

    print(f"copying {uf2.name} ({uf2.stat().st_size} bytes)")
    try:
        shutil.copyfile(uf2, os.path.join(drive, uf2.name))
    except OSError as e:
        # The drive vanishes as soon as the bootloader has the image; some
        # systems report that as an error after the data is written.
        print(f"(copy reported {e.__class__.__name__}: {e} - checking whether the board rebooted)")

    print("waiting for the board to reboot")
    if stock:
        try:
            where = wait_for(find_stock_drive, 30, "no PicoFox drive appeared")
        except TimeoutError:
            sys.exit("error: flashed, but the PicoFox drive (with settings.txt) didn't\n"
                     "appear. Check that SW3 is on, or unplug and replug the USB cable.")
        print(f"stock firmware running: its drive is at {where}")
        return
    try:
        port = wait_for(find_port, 20, "serial port did not come back")
        time.sleep(1.0)
        with PicoFox(port, check=False) as fox:
            hello = fox.hello()
    except (TimeoutError, PicoFoxError) as e:
        sys.exit(f"error: flashed, but couldn't confirm the new firmware: {e}")
    if not hello.startswith("FOXSINAD"):
        sys.exit(f"error: the board answers {hello!r}, not foxsinad_fw")
    print(f"{port}: {hello}")


# ----------------------------------------------------- stock firmware fetch
def git_blob_sha(data):
    """The hash GitHub reports for a file: SHA-1 of 'blob <size>\\0<data>'."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "foxsinad-flash",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def list_stock_releases():
    """UF2 images in AI6YM's releases/ folder: name, size, sha, url, date."""
    files = []
    for f in _get_json(f"{STOCK_API}/contents/releases"):
        if f.get("type") != "file" or not f["name"].lower().endswith(".uf2"):
            continue
        try:
            commits = _get_json(f"{STOCK_API}/commits?path=releases/{f['name']}&per_page=1")
            date = commits[0]["commit"]["committer"]["date"][:10]
        except Exception:
            date = "?"
        files.append({"name": f["name"], "size": f["size"], "sha": f["sha"],
                      "url": f["download_url"], "date": date})
    return files


def local_stock():
    """Copies saved earlier in stock/: name -> (path, sha)."""
    out = {}
    for path in sorted(STOCK_DIR.glob("*.uf2")):
        out[path.name] = (path, git_blob_sha(path.read_bytes()))
    return out


def stock_choices(remote, local, online=True):
    """What to offer: GitHub images (new, changed, or the same as a saved
    copy) and saved copies. Returns (choices, index of the suggestion)."""
    choices = []
    for f in sorted(remote, key=lambda f: (f["date"], "forceformat" not in f["name"]),
                    reverse=True):
        mine = local.get(f["name"])
        if mine and mine[1] == f["sha"]:
            choices.append({**f, "path": mine[0], "status": "same as your saved copy"})
        else:
            choices.append({**f, "path": None,
                            "status": "changed since your saved copy" if mine
                            else "new: not downloaded yet"})
    remote_by_name = {f["name"]: f for f in remote}
    for name, (path, sha) in local.items():
        r = remote_by_name.get(name)
        if r and r["sha"] == sha:
            continue  # already offered above
        choices.append({"name": name, "path": path, "sha": sha, "date": "", "url": None,
                        "status": "your saved copy"
                                  + ("" if r or not online else " (no longer on GitHub)")})
    suggest = next((i for i, c in enumerate(choices) if "forceformat" not in c["name"]), 0)
    return choices, suggest


def choose(choices, suggest):
    print(f"\nStock PicoFox firmware ({STOCK_PAGE}):")
    for i, c in enumerate(choices, 1):
        print(f"  {i}) {c['name']:28s} {c['date']:10s}  {c['status']}")
    if any("forceformat" in c["name"] for c in choices):
        print("\nNote: AI6YM's README doesn't describe the 'forceformat' image. From its\n"
              "name it probably erases the PicoFox's stored settings and audio, so use\n"
              "it only if that's what you want.")
    while True:
        answer = input(f"\nWhich one? [{suggest + 1}]: ").strip()
        if not answer:
            return choices[suggest]
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        print(f"Type a number from 1 to {len(choices)}, or press Enter.")


def fetch(choice):
    """Path to the chosen image, downloading and hash-checking it if needed."""
    if choice["path"]:
        return Path(choice["path"])
    STOCK_DIR.mkdir(exist_ok=True)
    print(f"downloading {choice['name']} ...")
    req = urllib.request.Request(choice["url"], headers={"User-Agent": "foxsinad-flash"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if git_blob_sha(data) != choice["sha"]:
        sys.exit(f"error: {choice['name']} didn't match GitHub's hash; not saved")
    dest = STOCK_DIR / choice["name"]
    dest.write_bytes(data)
    print(f"saved {dest.relative_to(REPO)} ({len(data)} bytes, hash checked)")
    return dest


def pick_stock_image():
    try:
        remote, online = list_stock_releases(), True
    except Exception as e:
        print(f"Couldn't reach GitHub ({e}). Offering your saved copies only.")
        remote, online = [], False
    local = local_stock()
    if not remote and not local:
        sys.exit(f"error: no stock firmware available. Download a .uf2 from\n{STOCK_PAGE}\n"
                 f"into {STOCK_DIR.relative_to(REPO)}/ and run this again.")
    choices, suggest = stock_choices(remote, local, online)
    return fetch(choose(choices, suggest))


def main():
    p = argparse.ArgumentParser(description="Put firmware on a PicoFox over USB.")
    p.add_argument("uf2", nargs="?",
                   help=f"UF2 image (default: {DEFAULT_UF2.relative_to(REPO)})")
    p.add_argument("--stock", action="store_true",
                   help="flash AI6YM's stock PicoFox firmware (checks GitHub for updates)")
    p.add_argument("--download-only", action="store_true",
                   help="with --stock: choose and download, but don't flash")
    p.add_argument("--port", help="serial port for the 1200-baud reset (default: auto)")
    args = p.parse_args()

    if args.stock:
        uf2 = pick_stock_image()
        if args.download_only:
            return
        flash(uf2, args.port, stock=True)
        return
    uf2 = Path(args.uf2) if args.uf2 else DEFAULT_UF2
    if not uf2.is_file():
        sys.exit(f"error: {uf2} not found - build it first with ./build.sh")
    flash(uf2, args.port)


if __name__ == "__main__":
    main()
