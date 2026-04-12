#!/usr/bin/env python3
"""Plot TM log from CalibratorUI DEBUG>=3 (test_1.csv): set V, mA, coil V, Gauss vs time."""

from __future__ import annotations

import argparse
import configparser
import csv
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DEFAULT_CSV = _HERE / "test_1.csv"
_INI_PATH = _HERE / "CalibratorUI.ini"

_MU0_SI = 4.0 * math.pi * 1e-7
_HELMHOLTZ_PAIR_AXIS_CENTER_FACTOR = 8.0 / (5.0 ** 1.5)


def _f(row: dict[str, str], key: str) -> float:
    v = (row.get(key) or "").strip()
    if not v:
        return float("nan")
    try:
        return float(v)
    except ValueError:
        return float("nan")


def _helm_geom_from_ini(ini: Path) -> dict[str, tuple[float, float] | None]:
    """Match CalibratorUI._reload_helmholtz_geometry: radius_m, N per axis."""
    out: dict[str, tuple[float, float] | None] = {"X": None, "Y": None, "Z": None}
    if not ini.is_file():
        return out
    cp = configparser.ConfigParser()
    cp.read(ini, encoding="utf-8")
    if not cp.has_section("helmholtz"):
        return out
    for ax in ("X", "Y", "Z"):
        al = ax.lower()
        try:
            d_mm = float(cp.get("helmholtz", f"{al}_diameter_mm", fallback="0").strip())
            n_turn = float(cp.get("helmholtz", f"{al}_turns", fallback="0").strip())
        except ValueError:
            continue
        if d_mm <= 0.0 or n_turn <= 0.0:
            continue
        r_m = (d_mm / 1000.0) * 0.5
        if r_m <= 0.0:
            continue
        out[ax] = (r_m, n_turn)
    return out


def _helm_r_ohm_from_ini(ini: Path) -> dict[str, float | None]:
    """DC coil R (Ω) per axis for I≈|V|/R — same keys as CalibratorUI [helmholtz] *_r_ohm."""
    out: dict[str, float | None] = {"X": None, "Y": None, "Z": None}
    if not ini.is_file():
        return out
    cp = configparser.ConfigParser()
    cp.read(ini, encoding="utf-8")
    if not cp.has_section("helmholtz"):
        return out
    for ax in ("X", "Y", "Z"):
        al = ax.lower()
        try:
            ro = float(cp.get("helmholtz", f"{al}_r_ohm", fallback="0").strip())
        except ValueError:
            continue
        if ro > 0.0:
            out[ax] = ro
    return out


def _current_a_for_gauss_row(
    row: dict[str, str], ax: str, r_ohm: dict[str, float | None]
) -> float:
    ro = r_ohm.get(ax)
    if ro is not None and ro > 0.0:
        v = _f(row, "coil_V_%s" % ax)
        if math.isnan(v):
            v = _f(row, "set_%s_v" % ax)
        if not math.isnan(v) and math.isfinite(v):
            return abs(v) / ro
    ma = _f(row, "%s_ma" % ax)
    if math.isnan(ma):
        return float("nan")
    return abs(ma) / 1000.0


def _helmholtz_pair_axis_center_gauss(i_a: float, radius_m: float, n_turns: float) -> float:
    if radius_m <= 0.0 or n_turns <= 0.0:
        return float("nan")
    b_t = (
        _HELMHOLTZ_PAIR_AXIS_CENTER_FACTOR
        * _MU0_SI
        * float(n_turns)
        * abs(float(i_a))
        / float(radius_m)
    )
    return b_t * 1e4


def _gauss_series_for_axis(
    rows: list[dict[str, str]],
    ax: str,
    geom: dict[str, tuple[float, float] | None],
    r_ohm: dict[str, float | None],
    has_csv_gauss: bool,
) -> list[float]:
    key_g = "Gauss_%s" % ax
    out: list[float] = []
    for row in rows:
        if has_csv_gauss and (row.get(key_g) or "").strip():
            out.append(_f(row, key_g))
            continue
        g0 = geom.get(ax)
        if g0 is None:
            out.append(float("nan"))
            continue
        r_m, n_turn = g0
        i_a = _current_a_for_gauss_row(row, ax, r_ohm)
        if math.isnan(i_a):
            out.append(float("nan"))
        else:
            out.append(_helmholtz_pair_axis_center_gauss(i_a, r_m, n_turn))
    return out


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        print("File not found:", path.resolve(), file=sys.stderr)
        sys.exit(1)
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        if not r.fieldnames:
            print("CSV has no header:", path, file=sys.stderr)
            sys.exit(1)
        return list(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="Plot test_1.csv (TM telemetry from CalibratorUI).")
    ap.add_argument(
        "csv",
        nargs="?",
        type=Path,
        default=_DEFAULT_CSV,
        help="CSV path (default: HostApp/test_1.csv next to this script)",
    )
    ap.add_argument(
        "--ini",
        type=Path,
        default=_INI_PATH,
        help="CalibratorUI.ini for Helmholtz Gauss if CSV lacks Gauss_* columns",
    )
    ap.add_argument(
        "--save",
        metavar="PNG",
        type=Path,
        default=None,
        help="Write figure to this PNG path instead of opening an interactive window",
    )
    args = ap.parse_args()
    path: Path = args.csv
    ini_path: Path = args.ini

    if args.save is not None:
        import matplotlib

        matplotlib.use("Agg", force=True)

    rows = load_rows(path)
    if not rows:
        print("No data rows in", path.resolve(), file=sys.stderr)
        sys.exit(1)

    fieldnames = list(rows[0].keys()) if rows else []
    has_csv_gauss = "Gauss_X" in fieldnames
    geom = _helm_geom_from_ini(ini_path)
    r_ohm = _helm_r_ohm_from_ini(ini_path)

    ts = [_f(row, "unix_s") for row in rows]
    if all(math.isnan(x) for x in ts):
        print("Column unix_s missing or empty.", file=sys.stderr)
        sys.exit(1)
    t0 = min(x for x in ts if not math.isnan(x))
    t_rel = [x - t0 if not math.isnan(x) else float("nan") for x in ts]

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            "matplotlib is required. Install: pip install matplotlib",
            file=sys.stderr,
        )
        return 1

    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(11, 10), constrained_layout=True)
    fig.suptitle("TM log: %s (%d rows)" % (path.name, len(rows)))

    ax0, ax1, ax2, ax3 = axes
    for ax, keys, title, unit in (
        (
            ax0,
            ("set_X_v", "set_Y_v", "set_Z_v"),
            "Set voltage",
            "V",
        ),
        (ax1, ("X_ma", "Y_ma", "Z_ma"), "Measured current", "mA"),
        (ax2, ("coil_V_X", "coil_V_Y", "coil_V_Z"), "Coil voltage (TM)", "V"),
    ):
        for k in keys:
            y = [_f(row, k) for row in rows]
            if any(not math.isnan(yi) for yi in y):
                ax.plot(t_rel, y, label=k, linewidth=1.0)
        ax.set_ylabel(unit)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)

    for axname, color in zip(("X", "Y", "Z"), ("C0", "C1", "C2")):
        gy = _gauss_series_for_axis(rows, axname, geom, r_ohm, has_csv_gauss)
        if any(not math.isnan(yi) for yi in gy):
            ax3.plot(
                t_rel, gy, label="Gauss_%s" % axname, linewidth=1.0, color=color
            )
    ax3.set_ylabel("G (Gauss)")
    ax3.set_title(
        "Helmholtz |B| (midpoint): CSV Gauss_* or V/R + [helmholtz] in %s" % ini_path.name
    )
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="upper right", fontsize=8)

    def _meas_ok_int(row: dict[str, str]) -> int | None:
        v = (row.get("meas_ok") or "").strip()
        if not v:
            return None
        try:
            return int(float(v))
        except ValueError:
            return None

    mk_series = [_meas_ok_int(row) for row in rows]
    if any(v is not None for v in mk_series):
        mk_y = [0 if v is None else v for v in mk_series]
        ax2_t = ax2.twinx()
        ax2_t.step(t_rel, mk_y, where="post", color="tab:gray", alpha=0.5, linewidth=1, label="meas_ok")
        ax2_t.set_ylabel("meas_ok (0/1)")
        ax2_t.set_ylim(-0.1, 1.1)
        ax2_t.legend(loc="upper left", fontsize=8)

    ax3.set_xlabel("Time since start (s)")
    if args.save is not None:
        out = args.save.expanduser()
        if out.parent != Path() and not out.parent.is_dir():
            out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150)
        print(out.resolve())
    else:
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
