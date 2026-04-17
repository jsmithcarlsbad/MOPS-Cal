# DROK architecture — **FROZEN** checkpoint (3 identical axis units)

**Frozen date:** 2026-04-16  
**Purpose:** Single source of truth for the **three-enclosure** DROK build: **one Pico + one XY6020L + one relay module per axis**, **three USB links** to the host. Supersedes earlier single-Pico / SC16IS752 / third-UART planning.

---

## 1. Executive summary

| Old stack (single chassis) | New stack (**frozen**) |
|----------------------------|-------------------------|
| 1× Pico driving 3× DRV8871 + INA3221 + PWM/RC | **3× identical enclosures** — each **1× Pico 2 W**, **1× XY6020L**, **1× 2‑ch relay module** for that axis only |
| One USB to one Pico | **Three USB CDC links** — host **CalibratorUI** opens **three COM ports** and **coordinates** X / Y / Z |
| Polarity via H-bridge IN1/IN2 | **Relay-only polarity** (NC default, energized = swapped) — **one relay module per enclosure** |
| Coil telemetry from INA | **Measured V/I** from DROK **Modbus** registers (`VOUT` / `IOUT`, etc. per [XY6020L Modbus PDF](https://github.com/tinkering4fun/XY6020L-Modbus/blob/main/doc/XY6020L-Modbus-Interface.pdf)) |
| Closed-loop ideas on Pico | **Closed-loop Gauss on host** (~**5 Hz** effective outer loop); each Pico is **Modbus bridge + local SAFE + relays** for **one** axis |

**Develop / manufacture:** design, firmware, and harness for **one channel**; **assemble three copies** (X, Y, Z). Per-unit **axis identity** and **LCD I2C address** come from a **small file on each Pico’s filesystem** (see §4).

**Operate vs SAFE (frozen):**

- Rear **2‑pos SPST** (see §4.3): two positions **Operate** and **SAFE** (use those labels on the panel).
- **SAFE** (switch **open** → **GP16 HIGH** via internal pull‑up): Pico **always** commands **DROK output OFF** via Modbus and drives **relays de‑energized** (default / NC path). Host **coil / DROK setpoints** are **not** trusted. **SAFE shall still allow a deploy action** (e.g. **back‑button** workflow on **GP17** — same semantics as prior “deployment” behavior; details when coding).
- **Operate** (switch **closed** → **GP16 LOW**, pin shorted to **GND**): normal operation — host may command that axis via USB.
- **Relay switching under load:** prefer **DROK off** and **coil energy collapsed** before changing relay state (contact life + supply stress) — operating procedure + firmware sequencing.

---

## 2. Power & operating procedure (**frozen**)

- **12 V:** One **bench supply** feeds **all three** enclosures; **common ground** across X / Y / Z and the supply return. A single **bench “output enable”** applies **12 V to all three units at once** (not three independent 12 V switches).
- **USB first:** **All three Picos** must be **powered from USB** (enumerated / running) **before** **12 V output** is enabled. That preserves **RP2350** intent: **IOVDD (3.3 V) up** before DROK **TTL** can present **~5 V** on **RX** (see §4.1).
- **Host GUI (recommended):** before **Connect**, a **popup** lets the operator confirm **three powered Picos** (reduces risk of **12 V on** with a dark Pico).
- **Power-down (recommended practice):** mirror for safety where practical — **DROK outputs off**, then drop **12 V**, then disconnect **USB** — so **Pico RX** is not exposed to live DROK TTL during **3.3 V** collapse.

---

## 3. Parts & docs (still authoritative)

- **XY6020L Modbus:** [XY6020L-Modbus-Interface.pdf](https://github.com/tinkering4fun/XY6020L-Modbus/blob/main/doc/XY6020L-Modbus-Interface.pdf) — **115200 8N1**, holding registers for **V‑SET**, **I‑SET**, **VOUT**, **IOUT**, **ONOFF**, etc. README warns of **CC→CV** oddities on **battery-like** loads; Helmholtz coils are mostly resistive — keep **I‑limits** and host checks.
- **Relay boards:** **5 V** opto input, **active LOW** (e.g. Hosyond-style 2‑ch modules): **GPIO HIGH = relay off**, **LOW = energized**. Match **VCC/GND/IN1/IN2** to your harness.
- **LCD:** Per enclosure, **2×16 I2C** (COB HD44780‑class); **different brand OK** if **software-compatible**. **7‑bit I2C address** (often **0x27** or **0x3F**) stored in **per‑Pico boot config** (§4).
- **SC16IS752:** **Not used** in this frozen architecture (no I²C‑UART). Local datasheet `SC16IS752_SC16IS762.pdf` remains in repo for reference only.
- **IR thermometer:** optional bench tool for **Kapton‑covered** windings.

---

## 4. Per-enclosure hardware (one axis)

### 4.1 Logical blocks

| Block | Count per enclosure | Notes |
|-------|---------------------|--------|
| Pico 2 W | 1 | **USB only** for host link in normal use |
| XY6020L | 1 | **One `machine.UART`** ↔ **TTL Modbus** (TX/RX/GND; **+5 V** pin per DROK doc — usually **sourced by module** when DROK input is powered) |
| 2‑ch relay module | 1 | **Polarity only** for that axis’s coil pair |
| 2×16 I2C LCD | 1 | Boot display of **axis** + **firmware version** |
| Rear **Operate / SAFE** | 1× SPST | **Operate** = switch closed, **GP16 LOW**; **SAFE** = switch open, **GP16 HIGH** (DROK off + relays default) |

### 4.2 Per‑Pico boot configuration file (**on flash**)

Read **at boot** (implementation detail TBD — e.g. `axis_config.ini` or merged into existing config pattern):

| Key / content | Purpose |
|---------------|---------|
| **Axis** | **`X`**, **`Y`**, or **`Z`** — drives first LCD line text, e.g. **`X AXIS`** |
| **LCD I2C address** | **0x27** / **0x3F** / etc. so **one firmware image** works across LCD vendors |
| (optional) UART id / pins | If not hard-coded |

**LCD lines (frozen intent):**

- **Line 1:** axis label (e.g. **`X AXIS`**) — pad/truncate to **16 chars**.
- **Line 2:** **`Ver: xx.xx`** (firmware version string).

### 4.3 GPIO template (provisional — one enclosure; verify vs PCB)

**Default intent:** match existing `Software/Pico/config.py` conventions where possible so one channel firmware maps cleanly.

| Function | Assignment | Notes |
|----------|------------|--------|
| **DROK Modbus UART** | **UART0:** **GP0** = TX → DROK RX, **GP1** = RX ← DROK TX | **115200 8N1**; **GND** common with DROK |
| **Relay IN1 / IN2** | e.g. **GP10**, **GP11** | **Active LOW**; only **two** pins per enclosure |
| **LCD I2C** | **I2C1:** **GP2** SDA, **GP3** SCL | Same electrical role as current `LCD_I2C_*`; address from **boot ini** |
| **Operate / SAFE** | **Recommended:** **GP16** (digital **input**, **internal pull‑up enabled**) | **SPST:** one terminal to **GP16**, the other to **GND**. **Closed** (GP16 → GND) → **LOW** → **Operate** (normal host control). **Open** → pull‑up → **HIGH** → **SAFE** (DROK off, relays default, host setpoints ignored for drive). **Panel labels:** **Operate** / **SAFE**. |
| **Back / deploy** | **GP17** | **Deploy** remains available in **SAFE** (see §1). Use **hold‑to‑deploy** (or equivalent) consistent with existing product behavior when implemented. |

**Not present per enclosure:** INA3221, DRV8871, second/third UART, PIO UART for DROK.

### 4.4 DROK serial — **5 V‑class TTL** (unchanged requirement)

- **RX** from DROK may sit **high near 5 V** when the module is powered.
- **RP2350:** treat **5 V tolerance** per **datasheet** — **IOVDD up** before relying on it; follow **§2 USB‑before‑12 V** for all three units.
- **Pico TX** is **3.3 V** high — XY6020L doc reports **3.3 V and 5 V** host levels worked in testing; **confirm** on your boards.
- **Optional:** bidirectional **level shifters** if you want to avoid FT/sequencing discussion entirely.

---

## 5. Host software (**frozen intent**)

- **CalibratorUI** (or host layer) is the **Gauss outer loop** (~**5 Hz** or as tuned) using **MT‑102** + **WIT901** streams already on the PC.
- **Three serial ports** in **`CalibratorUI.ini`** (or equivalent): one **COM** per **Pico**. Axis binding is **on the Pico** (LCD + config file); the host **routes commands** to the correct COM by **message design** (e.g. prefix or channel field — **implementation TBD** when you approve `CalibratorUI.py` edits).
- **Connect flow:** optional **“three Picos ready”** confirmation dialog before opening links / enabling bench coordination.

---

## 6. Software repo snapshot (expect changes when implementing)

- **Pico firmware:** still expected to live under **`drok_coil_driver_app.py`** + `main.py` import pattern; today that file may still be a **legacy copy** until rewritten for **one DROK + one relay + Modbus + Operate/SAFE (GP16) + deploy in SAFE + per‑unit ini**.
- **`config.py`:** will shrink to **single‑axis** constants per build (or one image + ini overrides).
- **Deploy:** `deploy.py` / `Software/HostApp/deploy.py` / `DEPLOY/` — still list **`drok_coil_driver_app.py`** until packaging is split or clarified for **triplicate** deploy.
- **`CalibratorUI.py`:** **protected** — multi‑COM coordination requires **your explicit approval** before edits.

---

## 7. Resume checklist (3‑enclosure)

1. **Build one enclosure** end‑to‑end: USB → Modbus **read MODEL/VERSION** → **output off** → relay toggle dry test → **LCD** shows axis + version from **ini**.
2. **Copy ×3**; set **axis** + **LCD address** in each Pico’s **ini**; label **USB cables** / enclosures **X / Y / Z** for humans.
3. **Bench procedure:** document **USB first → operator check → 12 V enable**; mirror for shutdown.
4. **Host:** define **tri‑port** protocol + **Connect** gating; implement after you approve host file changes.
5. **Closed loop:** tune **host** loop + **DROK command rate** once real **Modbus latency** and **Gauss** jitter are measured.

---

## 8. Open items (implementation phase)

- **Exact** Modbus register use (beyond **VOUT/IOUT** reads and **V‑SET / I‑SET / ONOFF** writes) — from **XY6020L PDF** only.
- **Host message format** for three Picos ( framing, errors, SAFE propagation ).
- **Operate / SAFE:** wiring **GP16 ↔ GND** + **pull‑up** is locked (§4.3); confirm **panel label** matches **LOW = Operate**, **HIGH = SAFE** in firmware.

---

## 9. Related repo files

- `Software/Pico/config.py` — pins (will align to §4.3 when coding).
- `Software/Pico/drok_coil_driver_app.py` — per‑axis DROK firmware.
- `Software/HostApp/CalibratorUI.ini` — will grow **three COM** entries when host is updated.
- `deploy.py`, `Software/HostApp/deploy.py` — deploy bundle.
- `COIL_AND_DRIVE_SPEC.md`, `GAUSS_CALCULATIONS.md` — coil physics reference.

---

*Frozen architecture — update only when you explicitly revise the product split or host protocol.*
