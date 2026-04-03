#!/usr/bin/env python3
"""
Copy everything in ./DEPLOY to a MicroPython device (e.g. Raspberry Pi Pico W).

Uses mpremote, which talks to the board over USB serial using MicroPython's
*raw REPL* (file transfer / exec protocol), not the interactive >>> REPL.

Before copying, deploy sends Ctrl+C on the serial port (like interrupting a
running main.py) so the port is free for mpremote. Requires pyserial (installed
with mpremote).

Requires: pip install mpremote
Run from the CoilDriver project root, or from Software/HostApp (same script):
  python deploy.py --port COM25
  python deploy.py --list
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# MicroPython default over USB CDC; host baud is often ignored but pyserial needs a value.
_DEFAULT_BAUD = 115200


def _repo_root() -> Path:
    """Directory containing ./DEPLOY.

    Works when this script lives in the repo root or in Software/HostApp.
    """
    here = Path(__file__).resolve().parent
    for d in (here, here.parent, here.parent.parent):
        if (d / "DEPLOY").is_dir():
            return d
    return here


def _deploy_dir() -> Path:
    return _repo_root() / "DEPLOY"


def _iter_files(deploy: Path) -> list[Path]:
    if not deploy.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(deploy.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            out.append(p)
    return out


def _mpremote_base() -> list[str]:
    return [sys.executable, "-m", "mpremote"]


def _interrupt_serial(port: str, baud: int) -> None:
    """Send Ctrl+C on the COM port so a running MicroPython script stops (KeyboardInterrupt)."""
    try:
        import serial
    except ImportError:
        print(
            "Warning: pyserial not installed; cannot send Ctrl+C. pip install pyserial",
            file=sys.stderr,
        )
        return
    try:
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = baud
        ser.timeout = 0.3
        ser.write_timeout = 0.3
        ser.open()
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            # Ctrl+C (0x03); twice is common to break busy loops / REPL
            ser.write(b"\x03\x03")
            ser.flush()
        finally:
            ser.close()
        time.sleep(0.2)
    except OSError as e:
        print("Warning: Ctrl+C pre-step skipped (port busy or no device):", e, file=sys.stderr)


def cmd_list_ports() -> int:
    r = subprocess.run(_mpremote_base() + ["devs"])
    return r.returncode


def cmd_deploy(port: str, dry_run: bool, interrupt: bool, baud: int) -> int:
    deploy = _deploy_dir()
    files = _iter_files(deploy)
    if not files:
        print("DEPLOY is missing or empty:", deploy, file=sys.stderr)
        print("Add the .py files to deploy under that folder.", file=sys.stderr)
        return 1

    cmd = _mpremote_base() + ["connect", port, "cp"] + [str(f.resolve()) for f in files] + [":"]
    print("Deploy", len(files), "file(s) to", port)
    for f in files:
        print(" ", f.name)
    if dry_run:
        if interrupt:
            print("Dry-run: would send Ctrl+C on", port, "then:")
        print("Dry-run:", subprocess.list2cmdline(cmd))
        return 0

    if interrupt:
        print("Sending Ctrl+C on", port, "(interrupt running app if needed)…")
        _interrupt_serial(port, baud)

    r = subprocess.run(cmd)
    if r.returncode != 0:
        return r.returncode
    print("Done.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--port",
        "-p",
        metavar="PORT",
        help="Serial port (Windows: COM3, COM25, …). Required unless --list.",
    )
    ap.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List serial devices (same as: python -m mpremote devs).",
    )
    ap.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Print the mpremote command without connecting.",
    )
    ap.add_argument(
        "--no-interrupt",
        action="store_true",
        help="Do not send Ctrl+C on the serial port before copying.",
    )
    ap.add_argument(
        "--baud",
        type=int,
        default=_DEFAULT_BAUD,
        metavar="N",
        help="Serial baud for the Ctrl+C step (default: %(default)s).",
    )
    args = ap.parse_args()

    if args.list:
        return cmd_list_ports()

    if not args.port:
        ap.error("--port is required (or use --list). Example: python deploy.py -p COM25")

    return cmd_deploy(
        args.port.strip(),
        args.dry_run,
        interrupt=not args.no_interrupt,
        baud=args.baud,
    )


if __name__ == "__main__":
    raise SystemExit(main())
