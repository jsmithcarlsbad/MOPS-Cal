#!/usr/bin/env python3
"""
Copy MicroPython firmware from ./DEPLOY to a device (e.g. Raspberry Pi Pico W).

**Every deploy** (default): copies `Software/Pico` -> `DEPLOY` for the required
`.py` set, then uploads from `DEPLOY`. That way the folder you deploy is always
the latest Pico sources from the repo — use `--no-sync-from-pico` only if you
intentionally hand-edit `DEPLOY/` and want to upload as-is.

Uses mpremote (raw REPL file transfer). Before copying, deploy can send Ctrl+C
on the serial port so main.py releases the port. Requires pyserial for that step.

**Required modules** (see PICO_FIRMWARE_REQUIRED below) must exist under
`Software/Pico` (and after sync, under `DEPLOY`) before upload.

Requires: pip install mpremote
Run from repo root or Software/HostApp:
  python deploy.py --port COM25              # sync Pico -> DEPLOY, then upload
  python deploy.py --sync-only               # refresh DEPLOY from Software/Pico only
  python deploy.py --port COM25 --no-sync-from-pico   # upload DEPLOY without syncing
  python deploy.py --list
  python deploy.py --version                 # print deploy.py tool version

This script's version (not Pico firmware): DEPLOY_SCRIPT_VERSION below.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# deploy.py tool version (this host script only; bump MINOR for behavior or messaging changes).
DEPLOY_SCRIPT_VERSION_MAJOR = 1
DEPLOY_SCRIPT_VERSION_MINOR = 0
DEPLOY_SCRIPT_VERSION = "%d.%d" % (DEPLOY_SCRIPT_VERSION_MAJOR, DEPLOY_SCRIPT_VERSION_MINOR)

# MicroPython default over USB CDC; host baud is often ignored but pyserial needs a value.
_DEFAULT_BAUD = 115200

# Complete import closure for coil_driver (main -> coil_driver_app -> config, ina3221, I2C_LCD -> LCD_API).
PICO_FIRMWARE_REQUIRED: tuple[str, ...] = (
    "main.py",
    "coil_driver_app.py",
    "config.py",
    "ina3221.py",
    "I2C_LCD.py",
    "LCD_API.py",
)


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


def _pico_source_dir() -> Path:
    return _repo_root() / "Software" / "Pico"


def _missing_required_firmware(deploy: Path) -> list[str]:
    return [name for name in PICO_FIRMWARE_REQUIRED if not (deploy / name).is_file()]


def _read_coil_driver_version(coil_driver_py: Path) -> str | None:
    """Parse VERSION_MAJOR / VERSION_MINOR from coil_driver_app.py."""
    try:
        text = coil_driver_py.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m_maj = re.search(r"^VERSION_MAJOR\s*=\s*(\d+)", text, re.MULTILINE)
    m_min = re.search(r"^VERSION_MINOR\s*=\s*(\d+)", text, re.MULTILINE)
    if m_maj and m_min:
        return f"{m_maj.group(1)}.{m_min.group(1)}"
    return None


def _print_deploy_version_banner(deploy: Path, *, after_upload: bool) -> None:
    ver = _read_coil_driver_version(deploy / "coil_driver_app.py")
    line = "=" * 70
    print(line)
    print(f"  deploy.py {DEPLOY_SCRIPT_VERSION}")
    if ver:
        print(f"  Coil driver firmware in DEPLOY: {ver}")
    else:
        print("  Coil driver firmware in DEPLOY: (could not read VERSION from coil_driver_app.py)")
    print("  Source of truth: Software/Pico/  ->  copied to  DEPLOY/  on each deploy")
    if after_upload:
        print()
        print("  >>> Reset or power-cycle the Pico, then open CalibratorUI (or serial).")
        print(f"  >>> Confirm you see OK VERSION {ver or '?'} matching the number above.")
    else:
        print()
        print("  >>> Run:  python deploy.py --port COMxx")
        print("  >>> Then reset the Pico and confirm OK VERSION in the host app.")
    print(line)


def _iter_deploy_py_files(deploy: Path) -> list[Path]:
    """All non-hidden .py files in DEPLOY (required set must be a subset)."""
    if not deploy.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(deploy.iterdir()):
        if (
            p.is_file()
            and p.suffix.lower() == ".py"
            and not p.name.startswith(".")
        ):
            out.append(p)
    return out


def cmd_sync_pico_to_deploy(*, show_banner: bool = True) -> int:
    """Copy PICO_FIRMWARE_REQUIRED from Software/Pico into DEPLOY."""
    src = _pico_source_dir()
    dst = _deploy_dir()
    if not src.is_dir():
        print("Source folder not found:", src, file=sys.stderr)
        return 1
    if not dst.is_dir():
        print("DEPLOY folder not found:", dst, file=sys.stderr)
        return 1
    missing = [n for n in PICO_FIRMWARE_REQUIRED if not (src / n).is_file()]
    if missing:
        print(
            "Software/Pico is missing required file(s):",
            ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    for name in PICO_FIRMWARE_REQUIRED:
        shutil.copy2(src / name, dst / name)
        print("Synced", name, "->", dst)
    if show_banner:
        _print_deploy_version_banner(dst, after_upload=False)
    return 0


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
    missing = _missing_required_firmware(deploy)
    if missing:
        print(
            "DEPLOY is missing required firmware file(s):",
            ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "Required set:",
            ", ".join(PICO_FIRMWARE_REQUIRED),
            file=sys.stderr,
        )
        print(
            "Fix: copy from Software/Pico or run: python deploy.py --sync-only",
            file=sys.stderr,
        )
        return 1

    files = _iter_deploy_py_files(deploy)
    if not files:
        print("DEPLOY has no .py files:", deploy, file=sys.stderr)
        return 1

    deployed_names = {p.name for p in files}
    extra = sorted(deployed_names - set(PICO_FIRMWARE_REQUIRED))
    cmd = _mpremote_base() + ["connect", port, "cp"] + [str(f.resolve()) for f in files] + [":"]
    print("Deploy", len(files), ".py file(s) to", port, "(required set OK)")
    for f in files:
        mark = "" if f.name in PICO_FIRMWARE_REQUIRED else " (extra)"
        print(" ", f.name + mark)
    if extra:
        print("Also deploying extra .py:", ", ".join(extra))
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
    _print_deploy_version_banner(deploy, after_upload=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + DEPLOY_SCRIPT_VERSION,
    )
    ap.add_argument(
        "--port",
        "-p",
        metavar="PORT",
        help="Serial port (Windows: COM3, COM25, …). Required for upload unless --list or --sync-only.",
    )
    ap.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List serial devices (same as: python -m mpremote devs).",
    )
    ap.add_argument(
        "--sync-from-pico",
        action="store_true",
        help="Legacy no-op: syncing Software/Pico -> DEPLOY before upload is now the default.",
    )
    ap.add_argument(
        "--no-sync-from-pico",
        action="store_true",
        help="Upload existing DEPLOY/*.py without copying from Software/Pico first.",
    )
    ap.add_argument(
        "--sync-only",
        action="store_true",
        help="Only copy Software/Pico -> DEPLOY; do not connect to a device.",
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

    if args.sync_only:
        return cmd_sync_pico_to_deploy()

    if args.list:
        return cmd_list_ports()

    if not args.port:
        ap.error(
            "--port is required unless using --list, --sync-only. "
            "Example: python deploy.py -p COM25"
        )

    if not args.no_sync_from_pico:
        r = cmd_sync_pico_to_deploy(show_banner=False)
        if r != 0:
            return r
        ver = _read_coil_driver_version(_deploy_dir() / "coil_driver_app.py")
        if ver:
            print(f"(Software/Pico -> DEPLOY done; coil_driver_app version {ver})")

    return cmd_deploy(
        args.port.strip(),
        args.dry_run,
        interrupt=not args.no_interrupt,
        baud=args.baud,
    )


if __name__ == "__main__":
    raise SystemExit(main())
