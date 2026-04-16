# CoilDriver — resume handoff

*Written for: pick up after reboot / new Cursor session. Summarizes this thread’s context and repo state.*

---

## Project

- **Pico** (MicroPython): coil driver + INA3221 + I2C LCD + **3× TI DRV8871** H-bridge channels (X/Y/Z).
- **Host**: `Software/HostApp/CalibratorUI.py` (PySide6), loads `CalibratorUI.ini`.
- **Deploy bundle**: copy everything under **`DEPLOY/`** to the Pico (`deploy.py` + `mpremote`).

---

## Firmware version (today)

- **`OK VERSION 3.4`** — `VERSION_MAJOR = 3`, `VERSION_MINOR = 4` in `Software/Pico/coil_driver_app.py` and `DEPLOY/coil_driver_app.py`.

---

## Hardware mode (`config.py`)

- **`COIL_DRIVER_HW = "drv8871_3ch"`**
- **`H_BRIDGE_MODEL = "3× TI DRV8871"`**
- **DRV8871 logic (Pico → module)**  
  - **IN1** = hardware **PWM**  
  - **IN2** = **GPIO low** (unidirectional PWM + coast between pulses; keep PWM frequency so both inputs are not low for ~1 ms → sleep, per TI SLVSCY9B)

### Pico GP → DRV8871 (default `config.py`)

| Axis | IN1 (PWM) | IN2 (low) |
|------|-----------|-----------|
| X | **GP10** | **GP11** |
| Y | **GP12** | **GP13** |
| Z | **GP14** | **GP15** |

- Config keys: `DRV8871_IN1_PWM_PINS`, `DRV8871_IN2_PINS`
- **When IN1 = high, IN2 = low:** TI Table 1 → **OUT1 = H**, **OUT2 = L** (“forward”, current OUT1 → OUT2).
- **VM / PGND / OUT1 / OUT2 / ILIM / GND** per module + [DRV8871 datasheet](https://www.ti.com/lit/ds/symlink/drv8871.pdf).

### Other `COIL_DRIVER_HW` values (legacy)

- **`mosfet_3ch`** — one PWM per axis (`PWM_EN_PINS`), no DIR.
- **`model_y`** — OSOYOO Model Y + DIR pairs (`DIR_PINS_*`).

---

## Control / safety (firmware)

- **No per-axis host alarm limits** — removed `x_alarm_limit` / telemetry `lim_*`; ceiling for OC + PI scaling is **`MAX_CURRENT_PER_COIL_MA`** in `config.py` only.
- **`OVERCURRENT_TRIP_ENABLE = 0`** in `config` (bring-up when INA showed bogus ~−1300 mA on X). Set to **`1`** when shunt path is trusted for real OC→SAFE.
- **SAFE** latches PWM off; host **`safe_reset`** clears it. **GUI Set** sends **`safe_reset`** before **`set_*_ma`** / **`set_*_pwm_hz`** so Set works after SAFE.

---

## Git (recent commits)

1. **`fbc8ff6`** — *1st V3 test successful! switched driver to DRV8871 (H-Bridge)* — body notes **firmware 3.4** (at commit time MINOR was bumped 3→4). Touches Pico/DEPLOY `coil_driver_app.py`, `config.py`, `CalibratorUI.py`.
2. **`611d3b6`** — *Add hardware reference PDFs* — `Hardware/AOD4184A.pdf`, `Hardware/l9110_2_channel_motor_driver.pdf`.

Earlier history includes **`90d8e01`** (*Last working version before going to version 3.0*) with GUI fix for SAFE/Set.

**Note:** A full `git checkout` to the single old base commit was done once in the past and **wiped uncommitted 2.x work** — prefer **commits/branches** for milestones.

---

## Deploy / test checklist

1. Edit pins in **`DEPLOY/config.py`** if wiring differs; mirror **`Software/Pico/config.py`** if you maintain both.
2. From repo root: `python deploy.py --port COMx` (adjust port).
3. Connect GUI → **`version`** → **3.4**; **`hw_report`** → DRV8871 IN1/IN2 GP lines.
4. Flow: connect → **safe_reset** if needed → enable axis → **Set** mA.

---

## Calibrator GUI

- **`Software/HostApp/CalibratorUI.py`** — Set sends `safe_reset` + `set_<axis>_ma` + `set_<axis>_pwm_hz` (no `*_alarm_limit`).
- **Settings → Max current** — used for **measured mA display coloring** only (not sent as Pico alarm limit).

---

## Open / next (from chat)

- **Flyback / diode** across coil or in OUT path — user planned to add; polarity depends on schematic (Schottky/TVS rated for **VM** and coil current).
- Re-enable **`OVERCURRENT_TRIP_ENABLE = 1`** after INA/shunt wiring verified.
- Optional: `.cursor/` still **untracked**; add to `.gitignore` if desired.

---

## User preferences (for the assistant)

- **Only change what is explicitly requested** — no drive-by refactors, experiments, or broad `git checkout` without clear instruction.
- **`CalibratorUI.ui`**: user-only edits per project rules (agent should not edit `.ui` unless asked).

---

## Quick paths

| Item | Path |
|------|------|
| Pico app | `Software/Pico/coil_driver_app.py`, `config.py` |
| Deploy copy | `DEPLOY/coil_driver_app.py`, `DEPLOY/config.py`, … |
| Host GUI | `Software/HostApp/CalibratorUI.py` |
| Deploy script | `deploy.py` (repo root) |
| Datasheets | `Hardware/*.pdf` |

---

*End of RESUME — tomorrow: open this file + repo; redeploy if you changed `DEPLOY/`.*
