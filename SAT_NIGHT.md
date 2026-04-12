# Saturday night — Calibrator / 3DHC driver notes

Conversation snapshot (host app, TM logging, field levels, git milestone).

## CalibratorUI crash — Unicode in `CalibratorUI.ini`

- **Error:** `UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2 in position 225`
- **Cause:** Comments used UTF-8 punctuation (`→`, `—`) while `load_ini()` used `encoding="ascii"`.
- **Fix:** Replaced those characters with ASCII in the ini; switched ini read/write in `CalibratorUI.py` to **UTF-8**; updated the module note that settings are UTF-8, not ASCII-only.

## TM CSV plotting

- **`plot_tm_csv.py`:** Plots `test_1.csv` (DEBUG ≥ 3): set V, mA, coil V, Helmholtz-modeled Gauss vs time; optional `--save PNG`.
- **Dependency:** `matplotlib` was missing from the venv; installed with pip.
- **Bugfix:** `ConfigParser.read()` does not accept `errors=`; removed invalid `errors="replace"` from ini reads in `plot_tm_csv.py`.
- **Venv path:** Use `D:\Calibrator\CoilDriver\.venv\Scripts\python.exe` from `Software\HostApp` (not `Software\.venv`).

## Earth field vs coil field

- **Earth (typical):** ~25–65 µT total magnitude, often quoted ~**0.25–0.65 G**; horizontal component commonly ~**0.2–0.4 G** depending on location.
- **“Overcome” Earth:** Either **swamp** (coil |B| ≫ ~0.5 G) or **cancel** (opposing field ~same magnitude as local Earth vector).
- **This project’s ini geometry** (`CalibratorUI.ini` `[helmholtz]`): at **~100 mA**, on-axis modeled |B| is **~same order as Earth** to **~1 G** depending on axis (X tighter → stronger for same I). At **low tens of mA**, Earth is **not negligible** for absolute field unless measured or nulled.

## What the sample `test_1.csv` plot implied

- **Magnitude:** Steady modeled Gauss on the order of **~1–2 G** during the pulse — **several times** a typical **~0.3–0.5 G** Earth field, so **not current-starved** for “dominate Earth” in that run.
- **Interpretation:** Plot Gauss traces are **model** (geometry + |V|/R from `coil_V_*` / `set_*_v` / mA), not NIST truth until compared on the bench.
- **Telemetry vs intent:** Log showed **Z setpoint** clearly; **set_X_v / set_Y_v** often empty (serial framing); **`coil_V_X,Y,Z`** all ~**2.85 V** with **high Y and Z mA**, **X mA = 0**. Modeled **Gauss_X** is large because **`coil_V_X / x_r_ohm`** is used for X — need **INA / shunt channel map** and **probe** validation so axes and model match hardware.

## Follow-ups mentioned elsewhere

- **Monday:** NIST Gauss meter at fixture; optional offset/scale in ini later.
- **Pico:** Deploy current firmware if device lags `Software/Pico` / `DEPLOY`.

## Git

- Commit message: **`1st working 3DHC driver`**
