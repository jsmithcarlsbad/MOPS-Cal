# Driver electronics — naming & hardware

**3D Helmholtz coil driver (agreed hardware + control):** see **`COIL_DRIVER.md`** — **OSOYOO Model Y** + **Pico 2 W** + **RC** + **INA3221** + **50 Ω** return; **not** the Waveshare Pico-Motor-Driver.

For the remainder of this project:

- **pico** — means **Raspberry Pi Pico 2 W** (RP2350 + wireless). **Not** the original **Pico W** (RP2040) unless a note explicitly says legacy.

- **Motor driver (3D build)** — [**OSOYOO Model Y**](https://osoyoo.com/2022/02/25/osoyoo-model-y-4-channel-motor-driver/) (see **`COIL_DRIVER.md`**). The [**Waveshare Pico-Motor-Driver**](https://www.waveshare.com/wiki/Pico-Motor-Driver) is **not** used (no PCA9685 stack-on).

Firmware and harness docs live in this repo: **`DEPLOY/`**, **`3D_WIRING.md`**, **`ELECTRONICS.md`**. **I2C:** **INA3221** single address for three channels (see **`COIL_DRIVER.md`**).

---

## Coil drive concept (per axis) — PWM → RC → coil → sense → constant current → field

**Power:** **12 V** (nominal) into the **Model Y** (or equivalent bridge) **VIN**; use **one H-bridge channel** per axis as a **PWM** switch into an **RC** network: **20 Ω 2 W** in series with **100 µF 35 V low-ESR** to **GND** (low-pass). The **averaged** voltage at the **RC / coil node** (where the filter meets the coil) acts as a **controllable DC drive** for the winding.

**Return:** Coil **low** side through a **50 Ω 3 W** resistor to **GND** (completes the path; also defines a **known** series element for current/voltage reasoning).

**Sensing:** **INA3221** (three-channel) **shunt** current per axis, or node voltage as needed — see **`COIL_DRIVER.md`**. With **R_coil** measured after winding, the series path **R_coil + R_return** lets firmware solve **I** from the measured node voltage (or sense current directly) and **adjust PWM duty** in **real time** to hold a **set** **mA** (**constant-current** behavior in the control loop, subject to **12 V** headroom and resistor power limits).

**Field:** With **I**, **N**, **mean diameter / Helmholtz geometry**, compute **B** (nT) in firmware or on the PC — same physics as the OpenSCAD **Helmholtz** stats.

**End goal:** Print and wind **both** coils, assemble the **full Helmholtz pair**, then use the fixture to **calibrate a magnetometer** against **known B** from **known I** and geometry.

**Practical checks:** Size **20 Ω / 50 Ω** power ratings for **max** **I²R**; choose **PWM frequency** and **RC** so ripple at the coil is acceptable; **Model Y** wiring per OSOYOO docs (direction + PWM on enable); verify **GND** reference for **INA3221** and Pico.

---

## Driver documentation and variants

- **Documented 3D driver:** **`COIL_DRIVER.md`** — **Model Y** (3 of 4 channels), **INA3221**, **RC**, **50 Ω** return, **Pico 2 W** closed loop.

- **Optional future:** **Three discrete MOSFET** legs instead of Model Y — same **RC + INA3221 + 50 Ω** **topology** per axis if you later want a custom power stage.
