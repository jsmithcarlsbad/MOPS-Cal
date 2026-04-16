#!/usr/bin/env python3
"""
Log OWON XDM1041 readings for 3D Helmholtz coil bench sessions (lab supply only).

Topology: lab supply -> breakout -> 25 ft cable -> fixture. Drive chassis disconnected.

Run from repo (or anywhere) with Tools on path — script adds sibling ``xdm1041/`` for imports.

Examples::

    cd Software\\Tools
    ..\\.venv\\Scripts\\python.exe bench_3dhc_log.py --port COM4 --once --axis X --supply-v 6.0 --mode dc_current --note "A jacks, series in X+"

Interactive session (CSV grows each entry)::

    ..\\.venv\\Scripts\\python.exe bench_3dhc_log.py --port COM4 --interactive --csv Hardware\\bench_3dhc_log.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS / "xdm1041"))

from client import MEASUREMENT_MODE_IDS, XDM1041  # noqa: E402


CSV_FIELDS = [
    "timestamp_utc",
    "axis",
    "supply_v_lab_display",
    "dmm_mode",
    "meas_raw",
    "meas_float",
    "n_samples",
    "operator_note",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _append_csv(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow(row)


def _avg_read(dmm: XDM1041, mode: str, n: int) -> tuple[str, float | None]:
    dmm.set_auto_range()
    dmm.configure_mode(mode)
    dmm.set_sample_rate("medium")
    raws: list[str] = []
    floats: list[float] = []
    for _ in range(max(1, n)):
        raw = dmm.read_primary_raw()
        raws.append(raw)
        v = dmm.read_primary_float()
        if v is not None:
            floats.append(v)
        time.sleep(0.15)
    joined = " | ".join(raws)
    if not floats:
        return joined, None
    return joined, sum(floats) / len(floats)


def run_once(
    port: str,
    csv_path: Path,
    axis: str,
    supply_v: float,
    mode: str,
    n: int,
    note: str,
    debug: bool,
) -> int:
    dmm = XDM1041(port, debug_serial=debug)
    dmm.open()
    try:
        raw, avg = _avg_read(dmm, mode, n)
        row = {
            "timestamp_utc": _utc_now_iso(),
            "axis": axis.upper(),
            "supply_v_lab_display": supply_v,
            "dmm_mode": mode,
            "meas_raw": raw,
            "meas_float": "" if avg is None else avg,
            "n_samples": n,
            "operator_note": note,
        }
        _append_csv(csv_path, row)
        print("Logged:", csv_path)
        print(dict(row))
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 1
    finally:
        dmm.close()
    return 0


def run_interactive(port: str, csv_path: Path, n: int, debug: bool) -> int:
    print("Bench 3DHC logger — OWON XDM1041")
    print("Topology: lab supply -> breakout -> cable -> fixture. Drive unit DISCONNECTED.")
    print(f"CSV: {csv_path.resolve()}")
    print("Modes:", MEASUREMENT_MODE_IDS)
    print("For dc_current: probes in **A/mA** jacks. For dc_volts: probes in **V** jacks.")
    print("Type q at axis prompt to quit.\n")

    dmm = XDM1041(port, debug_serial=debug)
    dmm.open()
    try:
        print("IDN:", dmm.query("*IDN?"))
        while True:
            axis = input("Axis [X/Y/Z or q]: ").strip().upper()
            if axis in ("Q", "QUIT", ""):
                break
            if axis not in ("X", "Y", "Z"):
                print("Use X, Y, or Z.")
                continue
            sv = input("Lab supply voltage (display reading, V): ").strip()
            try:
                supply_v = float(sv)
            except ValueError:
                print("Invalid number.")
                continue
            mode = input(f"DMM mode id [{', '.join(MEASUREMENT_MODE_IDS[:4])}...]: ").strip()
            if mode not in MEASUREMENT_MODE_IDS:
                print("Unknown mode.")
                continue
            if mode == "dc_current":
                input("Confirm RED lead in **A** (or mA) jack, black in COM. Press Enter...")
            elif mode == "dc_volts":
                input("Confirm probes on **V** jacks. Press Enter...")
            note = input("Short note (e.g. series in X+, 10A range): ").strip()
            raw, avg = _avg_read(dmm, mode, n)
            row = {
                "timestamp_utc": _utc_now_iso(),
                "axis": axis,
                "supply_v_lab_display": supply_v,
                "dmm_mode": mode,
                "meas_raw": raw,
                "meas_float": "" if avg is None else avg,
                "n_samples": n,
                "operator_note": note,
            }
            _append_csv(csv_path, row)
            print("Logged:", row)
            print()
    except (EOFError, KeyboardInterrupt):
        print("\nStopped.")
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 1
    finally:
        dmm.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Log XDM1041 for 3D Helmholtz bench (lab supply only).")
    p.add_argument("--port", default="COM4", help="DMM serial port")
    p.add_argument(
        "--csv",
        type=Path,
        default=Path("Hardware") / "bench_3dhc_log.csv",
        help="CSV output path (relative to cwd unless absolute)",
    )
    p.add_argument("--interactive", action="store_true", help="Prompt for each row")
    p.add_argument("--once", action="store_true", help="Single log row from CLI args")
    p.add_argument("--axis", choices=("X", "Y", "Z"), help="With --once")
    p.add_argument("--supply-v", type=float, help="Lab supply displayed V (with --once)")
    p.add_argument(
        "--mode",
        choices=MEASUREMENT_MODE_IDS,
        default="dc_current",
        help="DMM mode (with --once)",
    )
    p.add_argument("--n", type=int, default=5, help="Samples averaged per log row")
    p.add_argument("--note", default="", help="Operator note (with --once)")
    p.add_argument("--debug", action="store_true", help="SCPI trace")
    args = p.parse_args()

    if args.interactive and args.once:
        print("Use only one of --interactive or --once", file=sys.stderr)
        return 1
    if not args.interactive and not args.once:
        args.interactive = True

    if args.once:
        if args.axis is None or args.supply_v is None:
            print("--once requires --axis and --supply-v", file=sys.stderr)
            return 1
        return run_once(
            args.port,
            args.csv,
            args.axis,
            args.supply_v,
            args.mode,
            args.n,
            args.note,
            args.debug,
        )
    return run_interactive(args.port, args.csv, args.n, args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
