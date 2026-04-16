# Monday AM resume — CoilDriver / Pico PWM

Handoff from the Sunday night session. Use this to pick up at the office.

## What you asked for (keep in mind next session)

- **No unrequested code edits.** Ask explicitly before changing firmware/host app.
- **You own the architecture** (ramp, settle, PI, limits). Do not re-explain your own spec as if it were a “maybe you didn’t notice” bug.
- **Hardware:** You verified pins (scope/DVM). Swapping X/Y **driver JSTs** only permuted which board was driven vs software labels — not a reason to assume GPIO damage.
- **Freenove breakout:** Per-pin buffered LEDs follow GPIO state; see `Hardware/Freenove_Breakout_Board_for_Raspberry_Pi_Pico-master/Freenove Brekout Board Design Explanation.pdf` (buffers isolate LEDs from pull-up/down issues on I2C/ADC/floating).

## GPIO ↔ axis (DRV8871 default, firmware order X, Y, Z)

| Axis | IN1 (PWM) | IN2 (held low) |
|------|-----------|----------------|
| X    | GP10      | GP11           |
| Y    | GP12      | GP13           |
| Z    | GP14      | GP15           |

**RP2040:** slice = `(GP >> 1) & 7`, channel A/B = `GP & 1` (even GP → ch A). So GP10/12/14 → slices **5 / 6 / 7**, channel **A** each (not the old wrong static slice table).

## Technical work that landed in-repo (recent)

- **INA3221 bus read timing:** PWM-off-window sync; slice/channel **derived from IN1 pin list**, not stale `PWM_SLICE_PER_AXIS` / `PWM_CC_CHANNEL_PER_AXIS` (those tuples were removed from `config.py`; comments document pin-derived sync).
- **`hw_report`:** DRV8871 section prints per-axis **IN1 GP + PWM OK/FAIL**, **INA off-sync slices**, **SAFE latched**, renamed “PWM init summary” (was misleadingly labeled “PWM slices”).
- **Serial / telemetry:** Prior work on `micropython.schedule` for `TM::` vs `TXT::`, `_host_txt_burst_active` during `hw_report` (avoid deinit control timer during report).
- **Firmware version** in tree at checkpoint: minor bumped (e.g. toward **3.20** — confirm on device with `version` / boot text).

## The failure you care about

- **One run:** PWM activity observed on **GP10** (your words; scope waveform not fully characterized).
- **After power off:** Traced wiring — **X and Y driver connectors swapped** (wrong board vs channel).
- **Next run:** **No PWM on GP10** (buffer LED + scope + far end of cable). You correlate that with **code changes made in chat without you asking**, not with the JST swap.

## Git checkpoint (Sunday night)

- **Commit:** `cc02eff`
- **Message (short):** `checkpoint: WIP — PWM not verified; Cursor session changes`
- **Files in that commit (7):**  
  `DEPLOY/coil_driver_app.py`, `DEPLOY/config.py`, `DEPLOY/ina3221.py`,  
  `Software/Pico/coil_driver_app.py`, `Software/Pico/config.py`, `Software/Pico/ina3221.py`,  
  `Software/HostApp/CalibratorUI.ini`
- **Not in commit:** untracked items (e.g. `CURRENT_CAL.md`, `RESUME.md`, `.cursor/`, FreeCAD/STL, etc.) — add separately if you want them versioned.

**Office options:** `git show cc02eff`, compare to older commit you trust, or `git revert cc02eff` / checkout known-good tree before deploying to Pico.

## Suggested Monday sequence (minimal)

1. Flash/deploy **exactly** the tree you trust (possibly **pre-`cc02eff`** if tonight’s build is suspect).
2. `version` + `hw_report` over serial: confirm **COIL_DRIVER_HW**, **Axis X IN1 GP10: … OK/FAIL**, **SAFE latched**.
3. Connect CalibratorUI; **Set** X 20 mA with X enabled; watch **`TM::`** for `safe=`, `diag_X_duty=`, `set_X_ma=`.
4. If **PWM FAIL** in report → `PWM(Pin(10))` never stuck; if **OK** but pin quiet → trace `set_pwm` / control loop / SAFE / estop (**GP16** estop default in config).

## CalibratorUI.ini (your machine)

- Path: `Software/HostApp/CalibratorUI.ini` (e.g. COM port, `soft_reset_on_connect`).

## Golden reference (your words from earlier context)

- Working baseline to compare against: **`coil_driver_app.py` ~3.4** + DRV8871 + RC + INA3221 + CalibratorUI (see also `Hardware/.../CURRENT_CAL.md` for cal notes and GPIO table).

---

*This file is a session summary for continuity, not a verbatim export of the chat.*
