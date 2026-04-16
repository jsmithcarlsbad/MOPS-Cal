#!/usr/bin/env python3
"""Minimal CLI: *IDN?, optional mode + one MEAS1? reading.

Run from this directory (uses same-folder import)::

    cd Software/Tools/xdm1041
    python dmm_cli.py COM5
    python dmm_cli.py COM5 --mode dc_current --rate fast
"""

from __future__ import annotations

import argparse
import sys

from client import MEASUREMENT_MODE_IDS, XDM1041


def main() -> int:
    p = argparse.ArgumentParser(description="OWON XDM1041 headless SCPI smoke (CoilDriver Tools).")
    p.add_argument("port", help="Serial port (e.g. COM5)")
    p.add_argument(
        "--mode",
        default="dc_volts",
        choices=MEASUREMENT_MODE_IDS,
        help="Measurement function (default dc_volts)",
    )
    p.add_argument("--rate", default="fast", choices=("fast", "medium", "slow"))
    p.add_argument("--debug", action="store_true", help="Print SCPI TX/RX lines")
    args = p.parse_args()

    try:
        with XDM1041(args.port, debug_serial=args.debug) as dmm:
            print("IDN:", dmm.query("*IDN?"))
            dmm.set_auto_range()
            dmm.configure_mode(args.mode)
            dmm.set_sample_rate(args.rate)
            raw = dmm.read_primary_raw()
            print("MEAS1?:", raw)
            print("float:", dmm.read_primary_float())
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
