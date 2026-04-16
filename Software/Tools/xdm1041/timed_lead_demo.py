#!/usr/bin/env python3
"""Timed lead exercise: OPEN → SHORT → AAA (DCV). Run: python timed_lead_demo.py COM4"""

from __future__ import annotations

import argparse
import sys
import time

from client import XDM1041


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("port", default="COM4", nargs="?")
    p.add_argument("--wait", type=int, default=12, help="Seconds between prompts")
    args = p.parse_args()
    w = max(3, args.wait)

    dmm = XDM1041(args.port)
    dmm.open()
    try:
        dmm.set_auto_range()
        dmm.configure_mode("dc_volts")
        dmm.set_sample_rate("fast")

        print("\n>>> 1/3  LEADS OPEN - not touching the AAA. Measuring in 2 s...")
        time.sleep(2)
        print("OPEN:", dmm.read_primary_raw())

        print(f"\n>>> 2/3  Within {w} s: SHORT the probe tips together. Hold until next line prints.")
        time.sleep(w)
        print("SHORT:", dmm.read_primary_raw())

        print(f"\n>>> 3/3  Within {w} s: Touch AAA - RED to (+), BLACK to (-). Hold steady.")
        time.sleep(w)
        print("AAA :", dmm.read_primary_raw())

        print("\n>>> Done. Remove AAA / open leads. (Script finished.)\n")
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 1
    finally:
        dmm.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
