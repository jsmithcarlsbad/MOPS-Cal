# 3D Helmholtz coil driver — hardware design

This document is the **reference** for the **3-axis** Helmholtz coil driver: **power**, **switching**, **filtering**, **sensing**, and **return**. It replaces earlier ideas that used the **Waveshare Pico-Motor-Driver** (PCA9685 + TB6612 stack-on board); **that board is not used** in this design.

**MCU:** **Raspberry Pi Pico W** (RP2040 + Wi‑Fi) — referred to as **Pico W** below.

---

## Architecture overview

- **One** **12 V** (nominal) **power brick** feeds the **motor driver board** and shares **GND** with the **Pico W**, **INA3221** logic supply, and the **50 Ω** return network.
- **Three** independent **PWM + direction** channels drive **three** identical **RC low-pass** networks — one per axis (**X / Y / Z**).
- Each axis: **filtered quasi-DC** → **high-side shunt** (current sense) → **Helmholtz coil pair for that axis** (series wiring as built) → **50 Ω** → **GND**.
- **Current and bus voltage** for all three axes are read by **one** [**TI INA3221**](https://www.ti.com/lit/ds/symlink/ina3221.pdf) (**three-channel** high-side monitor) over **I2C**, instead of three separate **INA219** modules.

**Why PWM → RC:** The control loop regulates **average** current through a **smooth** drive, not **chopped** bridge current. That matches **shunt-based** sensing without fighting **PWM ripple** at the sense resistor.

**Signal flow (repeat for X, Y, Z):**

- **12 V brick** → **Model Y** **VIN**; **brick −**, driver, **Pico W**, **INA3221** logic, and **50 Ω** bottom share **GND**.
- **Model Y** bridge output (that axis) → **RC low-pass** → **shunt** (**INA3221** **IN+** / **IN−**) → **coil** → **50 Ω** → **GND**.
- **Pico W:** **PWM + direction** GPIO to **Model Y**; **I2C** to **INA3221** for shunt/bus reads.

---

## Power stage — OSOYOO Model Y (2.0)

**Board:** [**OSOYOO Model Y** 4-channel H-bridge](https://osoyoo.com/2022/02/25/osoyoo-model-y-4-channel-motor-driver/) (**Model Y 2.0** form factor: ~43 × 62 × 12 mm). **Two** **PT5126** bridge ICs, **7–24 V** input, **3.3 V / 5 V** logic.

**Use of channels:** **Three** of **four** independent channels (**ENA / ENB** per half-bridge bank, with **IN1–IN4** direction) drive **X**, **Y**, and **Z**. Fix **direction** pins for **one polarity** per axis; regulate **average** drive with **PWM** on the **enable** lines (same pattern as OSOYOO’s Arduino examples).

**Notes:**

- **VOUT** on the board is **tied to VIN** (not regulated) — do not use it as a logic supply.
- **Two posts per output (e.g. AK1 and AK2):** same **electrical node** — the board gives duplicate screw terminals for one half-bridge output. For **high-side / unipolar** drive you run **one wire per axis** from **either** post to your RC → coil → return; you do **not** need two separate connections for X (same for Y, Z).
- **Fourth** channel is spare (redundancy or future use).

**Not in this design:** [**Waveshare Pico-Motor-Driver**](https://www.waveshare.com/wiki/Pico-Motor-Driver) (stack-on **PCA9685** + **TB6612**) — avoids **I2C PWM** complexity and **address** clashes with the current monitor; **GPIO PWM** on the Pico drives the Model Y directly.

---

## Per-axis analog path

| Element | Typical starting values | Notes |
|--------|-------------------------|--------|
| **RC filter** | e.g. **20 Ω 2 W** + **100 µF 35 V low-ESR** to **GND** | Design target **fc ≈ 83 Hz** (example **20 Ω·100 µF** gives **fc ≈ 1/(2πRC) ≈ 80 Hz**). **PWM = 5 kHz** on the bridge enables so **ripple ≫ fc** → settled **quasi-DC** at the coil for sense/loop. |
| **Shunt** | **0.1 Ω** (**2512** **R100**) preferred | See **§ Shunt selection**. |
| **Coil** | Axis pair per **Helmholtz\*.scad** / `calibrator.ini` | **Flyback diode** across the **coil** (or coil + sensible node per your netlist), **≥ ~1 A**, **≥ 30 V**. |
| **Return** | **50 Ω** (power rating for max **I²R**) | Defines return path and stabilizes the loop; size for worst-case **mA**. |

**High-side sense wiring (INA3221):** For each channel **n**, current flows **through** the shunt: **IN+n** (supply side of shunt) → **shunt** → **IN−n** (load side) → **coil** → **50 Ω** → **GND**. **VIN+** and **VIN−** are **not** two separate rails; they **straddle** the sense resistor. **Bus voltage** for that channel is **IN−n** to **GND** (see [INA3221 datasheet](https://www.ti.com/lit/ds/symlink/ina3221.pdf)).

---

## Shunt selection

The INA3221 resolves shunt voltage with **~40 µV** LSB (order of magnitude); full-scale shunt voltage is **about ±163 mV**.

- **Default recommendation:** **R100 (0.1 Ω)** — at **~150 mA**, **~15 mV** shunt voltage, good **ADC** headroom and **simple** scaling.
- **R050 (0.05 Ω):** Use if you need **higher** sustained current while staying **well below** shunt full-scale, or to match an existing board footprint.
- Use **the same** shunt value on **all three channels** unless you have a strong reason not to (simpler firmware; INA3221 **sum/alert** features assume **equal** shunts when used).

Replace module **default** shunts with your **2512** parts only if the stock value does not match this plan; **re-calibrate** **`R_shunt`** in software after any change.

---

## Current monitor — INA3221

**Single** **INA3221** breakout (**three** channels) replaces **three** **INA219** boards.

- **Interface:** **I2C** (SMBus-compatible); **four** selectable addresses via **A0** (see datasheet).
- **Pico** connects **SDA / SCL** and **3.3 V** logic **GND** common with the monitor **VS** (2.7–5.5 V).
- **Firmware** uses the **INA3221** register map — **not** INA219 registers.

---

## Closed loop control

**Goal:** Hold **target current (mA)** per axis by adjusting **PWM duty** on the corresponding Model Y **enable** line, using **measured** shunt current from the **INA3221**.

### Operating principle

1. Read **shunt voltage** (hence **I**) for **X / Y / Z** from the INA3221 (after conversion time / averaging as configured).
2. Compare to **setpoint** **I_set** (per axis).
3. Update **duty cycle** (and optionally **ramp rate**) for that axis’s **PWM** output.
4. Respect **limits:** max **duty**, **max current**, **thermal** / **brick** capability; **clamp** or **fault** on out-of-range **bus** or **shunt** alerts if implemented.

**Why this works with RC filtering:** The **plant** seen by the loop is dominated by **RC**, **coil L/R**, and **return** — much closer to **DC** behavior than raw **PWM** across the shunt alone.

### Software

- **Drivers:** **I2C** driver for **INA3221** (init **Configuration**, **shunt/bus** read registers, **channel** indexing **1–3** mapped to **X–Z**). Optional use of **programmable conversion time** and **averaging** (datasheet) to match **loop rate** and **noise**.
- **Actuation:** **RP2040 PWM** (**~5 kHz** per `config.py`, with **~83 Hz** RC) on **GPIO** tied to Model Y **ENA/ENB** for the three chosen channels; **GPIO** outputs for **INx** **direction** bits, held **fixed** for **unipolar** drive during normal operation.
- **Control law:** **PI** or **PID** per axis is sufficient to start; **anti-windup** if **duty** saturates; **independent** loops for **X**, **Y**, **Z** (minimal **cross-coupling** if **GND** and **12 V** are solid).
- **Calibration:** **Scale** shunt readings with measured **`R_shunt`** (including **0.1 Ω** tolerance). Optionally store **offset** per channel (board **offset** + **ADC** zero).
- **Setpoint source:** **Phase 1:** constants or **pot** / debug. **Phase 2:** **USB serial** (or Wi‑Fi) **target mA** per axis from the **PC** app — align with **`DriverAndControlApp/`** deployment docs when implemented.
- **Scheduling:** **Fixed** loop interval or **async** I2C with **rate limiting**; ensure **PWM** updates do not **starve** **I2C** (or vice versa) on RP2040.

---

## Alternatives (not the default build)

- **Smaller / modular bridges:** **RZ7899** dual-module boards (**one** motor per IC) — need **multiple** PCBs for **three** axes; electrically similar **H-bridge → RC** idea.
- **Fully discrete 3× MOSFET** low-side or high-side legs — same **topology**, more **layout** work; optional **future** if you outgrow the Model Y **footprint** or want **custom** **Rds(on)**.

---

## Related files

- **`Software/Pico/`** — MicroPython firmware: **`main.py`** (runs on boot), **`coil_driver_app.py`**, **`ina3221.py`**, **`config.py`**. **I2C0** **GP4/GP5** = **INA3221** only; **I2C1** **GP2/GP3** = **Freenove 2×16 LCD** (see **`Hardware/Freenove_LCD_Module/`**, **`config.LCD_I2C_*`**).
- **`ELECTRONICS.md`** — naming (**Pico W**), legacy pointers, **Helmholtz** field goal.
- **`3D_WIRING.md`** — calibrator ↔ 3D fixture **6-pin** harness (pin numbers + wire colors).
- **`DEPLOY/`** — MicroPython files to copy to the Pico.
- **`HelmholtzX/Y/Z.scad`** — coil geometry and **resistance** stats.
