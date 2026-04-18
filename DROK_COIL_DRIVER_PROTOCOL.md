# DROK coil driver — USB serial protocol (Pico ↔ host)

**Firmware:** `Software/Pico/drok_coil_driver_app.py` (mirrored to `DEPLOY/` on deploy).  
**Architecture:** `DROK_MODS.md`.  
**Host app:** CalibratorUI changes are optional until this document is frozen and implemented on the PC.

Lines are UTF‑8 text, newline‑terminated. The Pico may print **`TXT::`** status lines, **`TM::`** telemetry, and **`ALARM`** fault lines (see below). Responses to host commands are usually returned as **`TXT:: OK …`** via `host_print`.

---

## 1. Numeric precision (XY6020L over Modbus)

The module exposes **16‑bit holding registers**. Unless noted, **CV / measured V / OVP** use an **LSB of 0.01 V** (10 mV steps, 0–6000+ centi‑volts depending on range). **CC / measured I / I‑limit / OCP** use an **LSB of 0.01 A** (10 mA steps).

| Quantity            | Native LSB | Typical string format | Notes |
|---------------------|------------|------------------------|-------|
| Voltage (set/meas)  | **0.01 V** | `%.3f` V (e.g. `12.050`) | Third decimal aligns with 10 mV steps; finer resolution is **not** physical. |
| Current limit (A) | **0.01 A** | `%.3f` A (e.g. `6.200`)   | Same as centi‑amps on the wire. |
| Current (mA)      | **0.01 A** | `%.1f` mA preferred on TM | `measured_ma` may use one decimal to avoid implying µA resolution. |
| Power (module)    | **0.1 W**  | `%.2f` W                 | Holding reg 4 (see firmware). |

**OVP / OCP** are read/written in **preset memory** (Modbus start `0x50 + DROK_PRESET_SLOT * 0x10`, 14 words; see Jens3382 `xy6020l.h` `tMemory` / `sOVP` / `sOCP`). Stored values use the same **0.01 V / 0.01 A** scaling as CV/CC.

---

## 2. `ALARM` lines (Pico → host, not `TXT::`)

Format (single line, spaces as shown):

```text
ALARM 0xCCCC short_description
```

- **`0xCCCC`** — 16‑bit **Pico protocol** code (see §3). This is **not** guaranteed to equal the raw XY6020L internal code; supply‑specific raw values may appear inside `short_description`.
- **`short_description`** — ASCII, **no spaces** (firmware replaces spaces with `_`) so a simple split‑on‑space parser can read `ALARM`, then hex token, then the rest as one token or joined tail.

The host should **not** require `TXT::` in front of `ALARM`. Multiple `ALARM` lines may occur over time; the GUI may dedupe by `(code, time)` policy.

---

## 3. Pico `ALARM` code table (initial)

| Code     | Meaning (short_description pattern) |
|----------|-------------------------------------|
| `0x8001` | `modbus_no_response` — repeated Modbus read failure (no valid holding snapshot). |
| `0x8200` | `drok_protect_reg=0xNNNN` — holding register **0x10** (*protect* / status word from supply) is **non‑zero**; `0xNNNN` is the **raw** 16‑bit value read from the module. Decode per XY6020L / tinkering4fun documentation on the host when available. |

**Reserved (documentation only until used by firmware):**

| Code     | Planned use |
|----------|-------------|
| `0x8002` | SAFE / Operate switch blocked an output‑on request. |
| `0x8100` | Supply reported fault bitfield (future: map bits to strings). |

When new codes are added in firmware, **extend this table in the same commit**.

---

## 4. Command summary (subset)

Discovery: **`?`** → `OK AXIS <label> VERSION M.m`.

DROK‑native (no X/Y/Z suffix; one DROK per Pico):

- **`set_vdc`**, **`set_ma`**, **`set_power`** `ON|OFF|…`
- **`get_vdc`**, **`get_ma`**, **`get_power`**, **`get_vin`**, **`get_watts`**, **`get_temp`**, **`get_supply_model`**, **`get_supply_version`**
- **`set_ovp`**, **`set_ocp`**, **`get_ovp`**, **`get_ocp`**, **`get_protect`**

**LCD (host → operator at the enclosure):**

- **`ESTOP`** — Same **safe** action as **`safe`** / physical SAFE: DROK output off, relays de‑energized, host drive latched off. Optional custom **two lines** (up to 16 printable ASCII characters each, **centered** on the 16×2 panel after sanitizing):  
  `ESTOP line1|line2`  
  If omitted, defaults to `HOST ESTOP` and `OUTPUT OFF`. Pipe **`|`** separates line 1 and line 2 (no pipe → second line uses default).
- **`INFO`** `line1|line2` — Does **not** change power state; shows operator instructions (step number, “move MT‑102”, etc.). **Requires** non‑empty payload; use `|` for two lines (second line may be blank after `|`). Each line is **centered** on the 16‑character row (same sanitizing as **`ESTOP`**).
- **`lcd_clear`** (aliases: **`info_clear`**, **`clear_lcd`**) — Clears host LCD override (`INFO` / `ESTOP` custom text); normal axis / version or deploy / SAFE screens resume.
- **`host_operate`** (aliases: **`clear_estop`**, **`estop_clear`**) — Clears **host** latched SAFE / ESTOP so the Pico may accept drive again **only if** the physical **Operate / SAFE** switch is **Operate** (contact closed). If the switch is still **SAFE** (open), returns **`ERR physical_SAFE_open`**.
- **`relay_1` / `relay_2`** (aliases **`rly1` / `rly2`**) **`ON` \| `OFF`** — Drives polarity relay optos (**active‑low** modules: **ON** = GPIO **LOW** = energized). **Refused in SAFE** (`ERR safe`). Before a state change, firmware turns **DROK output off** and waits **`DROK_RELAY_PRE_TOGGLE_MS`** (see `config.py`).
- **`set_pol`** (aliases **`set_polarity`**, **`polarity`**) **`POS` \| `NEG`** — Sets **both** relays to the pattern configured for that polarity (default in `config.py`: **POS** = both de‑energized — NC default path per `DROK_MODS.md`; **NEG** = **relay_1** energized, **relay_2** de‑energized). Accepts synonyms **`POSITIVE`** / **`NEGATIVE`** and **`+`** / **`-`**. Same SAFE rules and DROK‑off sequencing as **`relay_*`**. Response: `OK set_pol POS` or `OK set_pol NEG`.
- **`get_pol`** (alias **`get_polarity`**) — `OK get_pol POS` \| `NEG` \| `MIXED` \| `MISSING` — **`MIXED`** means the two relays do not match either configured pattern (e.g. after manual **`relay_1` / `relay_2`** commands); **`MISSING`** if a relay GPIO failed to init.
- **`get_relays`** (alias **`relays`**) — `OK get_relays relay_1=ON|OFF relay_2=ON|OFF`.
- **`get_status`** (alias **`status`**) — One line: axis, firmware version, physical/host SAFE flags, Modbus freshness, DROK output, relays, **`coil_pol=`** (same tokens as **`get_pol`**), active LCD override tag, deploy flag, and optional `mb_exc=` (last Modbus exception code from the supply, if any).
- **`help`** / **`commands`** — Short list of supported verbs (for serial terminals).

Legacy CalibratorUI compatibility (axis filtered by `axis_config.ini`):

- **`set_x_v` / `set_y_v` / `set_z_v`**, **`enable_x` / `enable_y` / `enable_z`**

Errors: **`ERR args`**, **`ERR safe`**, **`ERR wrong_axis`**, **`ERR modbus`**, **`ERR physical_SAFE_open`**, **`ERR relay_missing`**, **`ERR relay …`**, **`ERR unknown`**.

Exact `OK …` / `TM:: …` strings are defined by the firmware version in the repo; update this file when strings change.

---

## 5. OVP / OCP implementation note

`set_ovp` / `set_ocp` perform **read‑modify‑write** on the **14‑word preset** block for **`DROK_PRESET_SLOT`**. The firmware turns **DROK output off** briefly before the FC16 write, then restores output if it was on and conditions allow. If your GUI uses a different preset slot on the front panel, set **`DROK_PRESET_SLOT`** in `config.py` / per‑unit policy accordingly.

---

*Document version follows firmware `VERSION_MAJOR.MINOR` in `drok_coil_driver_app.py` (currently **6.2**).*

**`TM::` extensions:** `relay_1` / `relay_2` are **`0`** = de‑energized (GPIO high), **`1`** = energized (GPIO low), matching the relay command `ON`/`OFF` sense. **`coil_pol=`** repeats **`POS`** / **`NEG`** / **`MIXED`** / **`MISSING`** from **`get_pol`**.

**CC status (CalibratorUI `radioButton_[XYZ]_LED_Coil_CC`):** `drok_cc_mode=0|1`, `drok_cc_ma=…`, and **`drok_cc_led=0|1|2`** — **`0`** = red (CC mode off, output off, or no target current); **`1`** = lime (CC mode on and supply appears to be current‑regulating vs `set_*_v` ceiling); **`2`** = yellow (CC mode on but not maintaining CC — e.g. voltage‑limited or current mismatch). Interpret with **`drok_axis=`** (`X`/`Y`/`Z`) so the host lights the matching axis LED.

**Polarity vs harness:** If **`POS`** / **`NEG`** do not match coil markings on the bench, either swap host usage (**`POS`** ↔ **`NEG`**) or change **`DROK_SET_POL_*_*`** in `Software/Pico/config.py` (and redeploy) so the patterns match your wiring.

---

## 6. Design notes (optional)

- **Delimiter:** **`|`** is chosen so typical sentences without pipes stay as a single `INFO` line; the GUI can escape or avoid `|` inside a line if needed.
- **Priority:** Deploy / back‑button “READY FOR DEPLOYMENT” overrides **`INFO`** on refresh; **`ESTOP`** / hardware SAFE overrides normal axis splash.
- **Physical vs host SAFE:** With **`HARDWARE_ESTOP_GP`** wired, host **`host_operate`** cannot release latched SAFE while the switch is still SAFE — the operator must close the switch first.
- **Hardware SAFE edge** runs the same **`_apply_safe_hardware`** path as **`safe`** / **`ESTOP`**, which **clears an active `INFO` override** so the panel shows the fault state; use **`INFO`** again after returning to Operate if instructions should reappear.
