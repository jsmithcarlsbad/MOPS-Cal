# Resume — conversation 2026-04-14 (AM)

## User report

After **Connect All**: Pico text output window appeared **blank**; **Test NULL** checked → **no PWM**, **no measured voltages or currents** on the UI.

## Diagnosis (CalibratorUI / Pico serial)

1. **Pico log pane vs telemetry**  
   `textEdit_CalibratorTestOutput` shows **`TXT::`** payloads only (boot, `hw_report`, command echoes). **`TM::`** lines update the **coil/current LCDs** and are **not** echoed into that text control. A “blank” log can be normal if the firmware only streams `TM::`.

2. **Meters stay `---`**  
   That means **`TM::` is not being received** (wrong COM, wrong baud, Pico not running the coil driver, stuck in MicroPython REPL, etc.). Not a Test NULL–specific display bug.

3. **`CalibratorUI.ini` context**  
   Example config had **`soft_reset_on_connect = 0`**. Without soft reset, early boot `TXT::` can be missed; a stuck REPL or bad link may show **no TM** until **`soft_reset_on_connect = 1`**, power-cycle, or COM/baud is corrected.

4. **PWM after connect**  
   **Master coil enable** is intentionally **unchecked** at startup. Connect pushes `set_*_v` / `enable_*` from the GUI; with master off, enables stay off → **no PWM** until the user enables master and sets voltages as intended.

5. **Test NULL end state**  
   Test NULL finishes with **`safe`** (coils off). The UI could still show **master coils ON** while hardware was safe → confusing “nothing drives” behavior.

## Code changes made (this thread)

**File:** `Software/HostApp/CalibratorUI.py`  
**UI version:** bumped to **1.49**.

- **`_sync_master_coils_ui_off_after_testcal_safe()`**  
  After Test NULL successfully sends **`safe`**, **uncheck master coil enable** and call **`_on_master_coils_enable_changed(0)`** so the UI matches coils-off.

- **On successful serial connect**  
  Append one **`[CalibratorUI]`** line to the Pico log explaining: TXT-only log vs TM on LCDs; master + Test V for PWM; if LCDs stay `---`, try **`soft_reset_on_connect=1`** / power-cycle / verify COM.

## Suggested next steps on the bench

1. Reconnect; confirm the new hint line appears in the Pico log.  
2. If meters remain `---` → set **`soft_reset_on_connect = 1`** under `[serial]` in `CalibratorUI.ini` (or power-cycle Pico), then **Connect All** again.  
3. For normal coil drive: **master coil ON**, non-zero **Test V** / override as you use in workflow.  
4. If Test NULL aborts immediately, read the **status bar** (MT-102 / F-cal / openpyxl, etc.).

## Rules reminder (project)

- Do not edit `Software/HostApp/CalibratorUI.ui` in the agent; UI layout stays user-only in Designer.  
- Protected / scoped edits: follow `.cursor/rules/edit-scope-and-approval.mdc` for firmware and host files.
