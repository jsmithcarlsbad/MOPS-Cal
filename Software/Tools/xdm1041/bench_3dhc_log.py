#!/usr/bin/env python3
"""
Interactive CSV logger for 3D Helmholtz bench tests (lab supply + fixture, no Pico driver).

Uses OWON XDM1041 over USB (same SCPI stack as ``client.py``). You change DMM front-panel
leads when switching between ``dc_volts`` and ``dc_current`` — the script only reminds you.

Default CSV path: ``Hardware/bench_logs/bench_3dhc_YYYYMMDD_HHMMSS.csv`` under repo root.

  cd Software\\Tools\\xdm1041
  ..\\..\\..\\.venv\\Scripts\\python.exe bench_3dhc_log.py --port COM4
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from client import MEASUREMENT_MODE_IDS, XDM1041, parse_measurement_float

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _default_csv_path() -> Path:
    out_dir = _REPO_ROOT / "Hardware" / "bench_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return out_dir / f"bench_3dhc_{stamp}.csv"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    p = argparse.ArgumentParser(description="Log XDM1041 readings for 3D Helmholtz bench tests.")
    p.add_argument("--port", default="COM4", help="Serial port for XDM1041")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="CSV output path (default: Hardware/bench_logs/bench_3dhc_<UTC time>.csv)",
    )
    p.add_argument("--debug", action="store_true", help="Print SCPI traffic")
    args = p.parse_args()

    out_path = Path(args.out) if args.out else _default_csv_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 60)
    print("  BENCH 3DHC — XDM1041 session logger")
    print("=" * 60)
    print(f"  Port:     {args.port}")
    print(f"  CSV out:  {out_path}")
    print(f"  Modes:    {', '.join(MEASUREMENT_MODE_IDS)}")
    print()
    print("  TOPOLOGY: lab supply -> breakout -> 25 ft cable -> 3D fixture")
    print("  Pico / DRV8871 chassis: NOT CONNECTED to this path.")
    print()
    print("  When you switch dc_volts <-> dc_current, MOVE PROBES on the meter")
    print("  (V Ohm jack vs A jacks) before pressing Enter to sample.")
    print("=" * 60)
    print()

    fieldnames = [
        "utc_iso",
        "note",
        "mode_id",
        "n_samples",
        "interval_s",
        "mean",
        "stdev",
        "raw_samples",
    ]
    new_file = not out_path.exists()
    last_mode: str | None = None

    try:
        with XDM1041(args.port, debug_serial=args.debug) as dmm:
            idn = dmm.query("*IDN?")
            print("Connected:", idn)
            dmm.set_auto_range()

            with out_path.open("a", newline="", encoding="utf-8") as fp:
                writer = csv.DictWriter(fp, fieldnames=fieldnames)
                if new_file:
                    writer.writeheader()

                while True:
                    note = input("Note for this row (axis, V_lab, wiring, etc.) [q=quit]: ").strip()
                    if not note:
                        print("  (skipped empty note — type q to quit)")
                        continue
                    if note.lower() in ("q", "quit", "exit"):
                        break

                    mode = input(f"DMM mode [{', '.join(('dc_volts', 'dc_current'))}] [dc_current]: ").strip()
                    if not mode:
                        mode = "dc_current"
                    if mode not in MEASUREMENT_MODE_IDS:
                        print("  Unknown mode; pick one of:", MEASUREMENT_MODE_IDS)
                        continue

                    if last_mode is not None and mode != last_mode:
                        print()
                        print("  *** CHANGE DMM LEADS for", mode, "then press Enter ***")
                        input("  Ready? ")
                    last_mode = mode

                    ns = input("Number of samples (1-30) [5]: ").strip() or "5"
                    try:
                        n_samples = max(1, min(30, int(ns)))
                    except ValueError:
                        print("  Bad number, using 5")
                        n_samples = 5

                    interval = input("Interval between samples (s) [0.5]: ").strip() or "0.5"
                    try:
                        interval_s = max(0.05, float(interval))
                    except ValueError:
                        interval_s = 0.5

                    input("  Adjust lab supply / wiring, then press Enter to sample... ")

                    dmm.set_auto_range()
                    dmm.configure_mode(mode)
                    dmm.set_sample_rate("fast")

                    raws: list[str] = []
                    floats: list[float] = []
                    for i in range(n_samples):
                        raw = dmm.read_primary_raw()
                        raws.append(raw)
                        fv = parse_measurement_float(raw)
                        if fv is not None:
                            floats.append(fv)
                        if i + 1 < n_samples:
                            time.sleep(interval_s)

                    if len(floats) >= 2:
                        mean_v = statistics.fmean(floats)
                        stdev_v = statistics.pstdev(floats)
                    elif len(floats) == 1:
                        mean_v = floats[0]
                        stdev_v = 0.0
                    else:
                        mean_v = ""
                        stdev_v = ""

                    row = {
                        "utc_iso": _utc_iso(),
                        "note": note,
                        "mode_id": mode,
                        "n_samples": n_samples,
                        "interval_s": interval_s,
                        "mean": mean_v,
                        "stdev": stdev_v,
                        "raw_samples": " | ".join(raws),
                    }
                    writer.writerow(row)
                    fp.flush()
                    print(
                        f"  Logged: mean={mean_v!s} stdev={stdev_v!s} (n={n_samples}) mode={mode}"
                    )
                    print()

        print("Done. CSV:", out_path)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
