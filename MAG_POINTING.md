# MAG pointing (MOPS) — summary, analysis, and plan

## 1. External reference

**URL (original share):** [https://share.google/aimode/BzmwcZJH9XtK1kVKY](https://share.google/aimode/BzmwcZJH9XtK1kVKY)

Automated fetch of that link **timed out** in tooling; the substantive content below is **verbatim summary** of what **you pasted** from that page (tutorial-style explanation, not a peer-reviewed citation).

---

## 1a. Summary of pasted content (3D Helmholtz + digital compass heading)

**Goal:** With three orthogonal coil pairs (X, Y, Z / triax Helmholtz), choose coil currents so the **net** field at the sensor

\[ \mathbf{B}_{\mathrm{net}} = \mathbf{B}_{\mathrm{earth}} + \mathbf{B}_{\mathrm{coil}} \]

matches a **desired horizontal direction** for a digital compass (heading from horizontal \(B_x, B_y\) via \(\atan2\)-style logic).

**Steps (as in the paste):**

1. **Target horizontal vector**  
   For a desired heading \(\psi\) in the horizontal plane (after fixing which axis is “reference” and sign conventions), the **horizontal** part of \(\mathbf{B}_{\mathrm{target}}\) should have components consistent with \(\psi\)—typically proportional to \((\cos\psi,\,\sin\psi)\) in the horizontal plane once a **0° reference** (e.g. magnetic or true North) is defined.

2. **Subtract Earth (vector calculus)**  
   Required coil field is

   \[ \mathbf{B}_{\mathrm{coil}} = \mathbf{B}_{\mathrm{target}} - \mathbf{B}_{\mathrm{earth}} \]

   so the compass sees \(\mathbf{B}_{\mathrm{net}} = \mathbf{B}_{\mathrm{target}}\).  
   **Full override / “null sphere” idea:** first generate \(\mathbf{B}_{\mathrm{coil}} \approx -\mathbf{B}_{\mathrm{earth}}\) to null ambient, then add the field for the desired heading (same vector formalism, two-stage or one combined vector).

3. **Helmholtz pair → current (per axis)**  
   Once each axis’s required **on-axis** flux density \(B_i\) at the working volume is known (in **tesla**), convert to current using the **ideal Helmholtz pair** center-field relation (one pair along that axis):

   \[
   B = \left(\frac{4}{5}\right)^{3/2} \frac{\mu_0 N I}{R}
   = \frac{8}{5^{3/2}}\,\frac{\mu_0 N I}{R}
   \]

   where \(R\) is coil radius (m), \(N\) turns per coil (each of the two coils in the pair), \(I\) current (A), \(\mu_0 = 4\pi\times 10^{-7}\,\mathrm{H/m}\).  
   Solve:

   \[
   I = \frac{B\,R}{\mu_0 N}\,\left(\frac{5}{4}\right)^{3/2}.
   \]

   Apply **separately per axis** only if each pair’s field is dominated by its own axis component at the sensor (ideal triax Helmholtz / small cross-talk assumption; otherwise use a **3×3 cross-coupling matrix** \(\mathbf{M}\) from **section 1b**).

4. **Horizontal heading decomposition (trigonometry)**  
   For a purely **horizontal** target direction \(\psi\): drive horizontal coil components so the **horizontal part** of \(\mathbf{B}_{\mathrm{coil}}\) (after Earth cancellation) yields \(\psi\). The pasted material states that **Z** is often used to **cancel Earth’s vertical (dip) component** so the horizontal compass math stays valid when the sensor is level—i.e. make the **net** vertical \(B\) at the sensor what the tilt-compensated algorithm expects (often ~0 in the horizontal projection step).

**Conclusion from paste:** Implementation is **vector subtraction** (Earth correction / nulling) plus **trig decomposition** of heading into horizontal \(B\) components, then **Helmholtz geometry** to turn each axis’s \(B\) into **current** (or voltage via \(I \approx |V|/R_{\mathrm{coil}}\) where appropriate).

**“Do we have radius and turns?”**  
In this repo, **`CalibratorUI.ini`** section **`[helmholtz]`** already carries per-axis geometry used by the host Gauss estimate: `x_diameter_mm`, `x_turns`, (and Y, Z), plus optional `x_r_ohm` for \(I \approx |V|/R\). Those are the right **inputs** for open-loop current-from-\(B\) once diameters are converted to **radius in meters** and \(B\) is in **tesla** (1 G = \(10^{-4}\) T). Values must match **physical** coils, not placeholder ini.

---

## 1b. Cross-coupling matrix \(\mathbf{M}\) (from your diagram)

Real 3-axis Helmholtz systems have **crosstalk**: current in one pair produces field not only on its “own” axis but also on the other two (misalignment, finite geometry, mutual effects). The linear model at the working point is:

\[
\mathbf{B} = \mathbf{M}\,\mathbf{I}
\]

with \(\mathbf{B} = [B_x,\,B_y,\,B_z]^T\), \(\mathbf{I} = [I_x,\,I_y,\,I_z]^T\), and \(\mathbf{M}\) a **3×3** matrix of coefficients \(k_{ij}\) in **tesla per ampere (T/A)**:

\[
\begin{bmatrix} B_x \\ B_y \\ B_z \end{bmatrix}
=
\begin{bmatrix}
k_{xx} & k_{xy} & k_{xz} \\
k_{yx} & k_{yy} & k_{yz} \\
k_{zx} & k_{zy} & k_{zz}
\end{bmatrix}
\begin{bmatrix} I_x \\ I_y \\ I_z \end{bmatrix}.
\]

- **Diagonal** \(k_{xx}, k_{yy}, k_{zz}\): primary “coil constant” for that axis (T/A).  
- **Off-diagonal** \(k_{xy}, k_{yx}, \ldots\): **cross-coupling**. In an ideal aligned system they are **zero** and \(\mathbf{M}\) is diagonal.

### Empirical calibration (column by column)

Use a **3-axis vector magnetometer** at the **same location** as the MT102 (or the MT102 itself once noise and timing are acceptable):

1. **X column:** Set **only** \(I_x \neq 0\), with \(I_y = 0\), \(I_z = 0\). Measure the resulting field components \(B_{x(x)}, B_{y(x)}, B_{z(x)}\) (notation: field from X drive only).  
   \[
   k_{xx} = B_{x(x)} / I_x,\quad
   k_{yx} = B_{y(x)} / I_x,\quad
   k_{zx} = B_{z(x)} / I_x.
   \]
2. **Y column:** Apply **only** \(I_y\); measure \(B_{x(y)}, B_{y(y)}, B_{z(y)}\).  
   \[
   k_{xy} = B_{x(y)} / I_y,\quad
   k_{yy} = B_{y(y)} / I_y,\quad
   k_{zy} = B_{z(y)} / I_y.
   \]
3. **Z column:** Apply **only** \(I_z\); measure \(B_{x(z)}, B_{y(z)}, B_{z(z)}\).  
   \[
   k_{xz} = B_{x(z)} / I_z,\quad
   k_{yz} = B_{y(z)} / I_z,\quad
   k_{zz} = B_{z(z)} / I_z.
   \]

**Using \(\mathbf{M}\) for control:** Given a required coil field \(\mathbf{B}_{\mathrm{coil}}\) (after Earth / target subtraction), solve

\[
\mathbf{I} = \mathbf{M}^{-1}\,\mathbf{B}_{\mathrm{coil}}
\]

(if \(\mathbf{M}\) is invertible). For production, store \(\mathbf{M}\) (or \(\mathbf{M}^{-1}\)) in **`CalibratorUI.ini`** or a dedicated calibration file, with units and frame documented.

**Practical notes**

- Perform calibration with **Earth compensated** or **subtracted** so each column reflects **coil-only** field (or measure \(\Delta\mathbf{B}\) from a zero-current baseline each time).  
- Use **several** current levels per axis and **fit** slope \(dB/dI\) to reduce noise (still yields one effective \(\mathbf{M}\) near the operating point).  
- A copy of the source diagram is saved under the Cursor workspace assets path from your upload; the **normative text** for implementation is this section.

---

## 2. What “MOPS” means in *this* project (from your UI spec)

Authoritative widget-level intent is in **`Software/HostApp/calibrator_DROK_UI_RequiredChanges.txt`**. Relevant excerpts:

| UI element | Role |
|------------|------|
| `lcdNumber_MOPS_Pitch`, `lcdNumber_MOPS_Roll`, `lcdNumber_MOPS_Hdg` | Show **Pitch**, **Roll**, and **Heading (0–359°, ±1° goal)** derived from **MT102** measurements after agreed math. |
| `radioButton_MOPS_Set_North_Plus_45` | Coil field + geometry such that MT102 reads **level** (horizontal) and **heading ≈ 045° (NE)** in the horizon frame. |
| `radioButton_MOPS_Set_72_Deg` | Same “level + NE” style target, plus **dip angle ≈ 72° ±1°** (dip = rotation of MT102 about its **Y** axis, nose down vs horizon, **as reported by MT102**). |
| `radioButton_MOPS_Set_80_Deg` | **Level** + **dip ≈ 80° ±1°**; spec text also says **“No Coil driver heading applied”** (interpret as: achieve dip/level via **local field / attitude** without imposing an extra coil-based heading bias—**needs your confirmation**). |
| `radioButton_MOPS_Set_NullSphere` | Presented field such that MT102 reads **level**, **heading ≈ 0° (N)**, **independent of Earth field** → practically a **zero-net or controlled ambient** “null sphere” regime so the sensor is dominated by the **coil field**, not local geomagnetism. |
| `checkBox_MOPS_TestMode` | When checked, apply **cal factors** to measured Gauss before display (`measured × CalFactor`). |

**Spec ambiguities to resolve with you (not blockers for architecture, blockers for exact numbers):**

- The **72°** and **80°** bullet text in the requirements file **repeats “45° NE”** in places where **80°** might intend a different heading or “dip only” scenario; align final truth table (target heading, target dip, whether Earth is nulled) per preset.
- **“Dip”** must be pinned to a **single convention**: MT102 body Y, “nose down,” relative to **local gravity horizontal**—and which **MT102 raw channels / factory cal** feed that angle.

---

## 3. Problem statement (engineering)

We must drive **three (or more) coil axes** so that the **total magnetic field vector** at the MT102, expressed in a **horizontal “level” frame**, matches prescribed **heading** and (where required) **dip** behavior, within **±1° heading** (and dip tolerance where stated).

The MT102 is a **vector magnetometer** (after F-cal): it measures **B** in its sensor frame. **Heading** and **level** are not raw registers; they come from **tilt-compensated compass** style math (accelerometer/tilt + mag) or from your defined mapping if MT102 already outputs attitude—**that choice is an implementation decision** tied to what the MT102 stream actually provides (see section 5).

---

## 4. Coordinate frames (must be fixed once)

1. **World / lab frame** `W`: fixed axes on the bench (e.g. X east, Y north, Z up)—or your existing convention in firmware/host.
2. **Horizontal frame** `H`: Z along **gravity up**; X,Y span the horizontal plane for **heading**.
3. **MT102 body / sensor frame** `S`: how RAW X,Y,Z map to `W` after **PCB rework / `mt102_swapped_xy`** (already a host policy in `CalibratorUI.py`).
4. **Magnetic declination** (if we express heading as **true vs magnetic**): already a concept in host ini (`mag_declination_deg`); MOPS targets should state which one the operator expects on `lcdNumber_MOPS_Hdg`.

---

## 5. Measurement path → Pitch / Roll / Heading

**Plan A (recommended if MT102 provides gravity / tilt):**

- Use **tilt-compensated heading**: from accelerometer (or attitude) get rotation `R_{S→H}`; rotate **B** into horizontal plane;  
  `heading = atan2(B_h_y, B_h_x)` (with quadrant fix and declination policy).

**Plan B (if stream is mag-only):**

- Restrict MOPS to **physically level** fixture, or derive tilt from another sensor (not in current DROK list—would be a **new** requirement).

**Pitch / roll on MOPS LCDs:**

- Either pass through **MT102-reported** pitch/roll if the protocol exposes them, or compute from the same tilt solution used for heading. The spec says “after required math”—we document the exact formulas in code comments + here once stream fields are fixed.

**Link to existing code:** `CalibratorUI.py` already maps a **field vector** to **roll, pitch, yaw** for the 3D viewer (`_field_vector_to_rotation`). MOPS can **reuse or refactor** that logic **after** we unify frame conventions (viewer vs compass heading).

---

## 6. Control path → coil drivers

**Plant:** At the sensor, `B_total = B_earth + B_coil(I_x, I_y, I_z)` (plus soft iron; F-cal partly handles linear part). The pasted reference formalizes exactly what we already sketched: **`B_coil = B_target − B_earth`** in vector form, then **per-axis Helmholtz** (or calibrated matrix) to currents.

**Open-loop feedforward (from section 1a):**

1. Estimate or measure **`B_earth`** at the sensor (three-vector), in the same frame as coil axes.
2. Form **`B_target`** for the MOPS preset (horizontal magnitude + heading; handle vertical / null-sphere presets explicitly).
3. **`B_coil = B_target − B_earth`** (component-wise).
4. For each axis \(i \in \{X,Y,Z\}\): \(I_i = f_{\mathrm{Helm}}(B_{coil,i},\,N_i,\,R_i)\) using the formula in section 1a; convert to **DROK** `set_ma` / voltage commands per firmware policy.

**Cross-axis coupling:** If real coils deviate from ideal Helmholtz, replace the per-axis Helmholtz inversion with **\(\mathbf{I} = \mathbf{M}^{-1} \mathbf{B}_{\mathrm{coil}}\)** using \(\mathbf{M}\) from **section 1b** (empirical T/A matrix), or combine: physics-based diagonal plus small \(\mathbf{M}\) off-diagonals from calibration.

**Preset modes (conceptual):**

| Preset | Idea |
|--------|------|
| **North + 45** | `B_coil` dominates horizontal component so horizontal heading ≈ 45° when MT102 is level. |
| **72° / 80°** | Add requirement on **dip**: physically the board is tilted about body Y, **or** we interpret dip as a **target orientation** checked against MT102-reported tilt—your spec mixes both; we need the **intended** interpretation. |
| **NullSphere** | **Cancel or swamp `B_earth`** so horizontal direction is defined by coils alone → typically **closed-loop** on **B_h** until earth is suppressed and heading locks to 0°. |

**Actuators:**

- Today: legacy `set_x_v / set_y_v / set_z_v` / `enable_*` on one serial link (transitioning to **per-axis DROK** per `calibrator_DROK_UI_RequiredChanges.txt`).
- Tomorrow: **three COM ports**, each DROK (or triax firmware) — MOPS controller outputs **three independent** commands.

**Control law (staged):**

1. **Open-loop (fast to implement):** Use Helmholtz / coil geometry + calibration (`[helmholtz]`, Gauss cal factors) to map **desired B** → **I or V**. Good for coarse pointing; sensitive to position and earth field.
2. **Closed-loop (meets ±1°):** Read MT102 mag (and tilt), compute **heading error** (and dip error if applicable), **PID** (or constrained least-squares) on **I_x, I_y, I_z** with limits from `max_ma_mA` / supply limits. Update at **TM rate** or slower outer loop.

**Safety:** Presets must respect **SAFE**, **OCP/OVP** dialogs, and never command beyond hardware limits ([DROK_COIL_DRIVER_PROTOCOL.md](DROK_COIL_DRIVER_PROTOCOL.md) and Pico `drok_coil_driver_app.py`).

---

## 7. Implementation plan (software)

### Phase 0 — Clarify & freeze

- Resolve **preset truth table** (heading, dip, earth cancellation) and **dip definition**.
- Confirm **MT102 fields** available each poll (RAW only vs attitude).
- Lock **frame + declination** policy for `lcdNumber_MOPS_Hdg`.

### Phase 1 — Readouts only

- Bind `lcdNumber_MOPS_Pitch`, `lcdNumber_MOPS_Roll`, `lcdNumber_MOPS_Hdg` in `CalibratorUI.py` (you own `.ui` objectNames).
- Implement **one** agreed math path from MT102 → pitch/roll/heading; show **dashes** when MT102 not connected.

### Phase 2 — Preset selection (no coils)

- Exclusive `QButtonGroup` for the four `radioButton_MOPS_*` (or enforce exclusivity in code).
- Persist last selection in `CalibratorUI.ini` if you want session continuity (**you** decide).

### Phase 3 — Open-loop coil feedforward

- Given selected preset, compute **target B** in `H` (or `W`).
- Map to **axis currents/voltages** using **section 1a** (ideal Helmholtz) and/or **section 1b** (\(\mathbf{M}^{-1}\)); persist \(\mathbf{M}\) from bench calibration. Send commands to whichever coil stack is connected (single Pico vs per-axis).

### Phase 4 — Closed-loop pointing

- Outer loop: compare **measured** heading/dip to **target**; update commands until **|Δheading| ≤ 1°** (and dip if required).
- Rate limits + integrator anti-windup; pause on ALARM / SAFE.

### Phase 5 — `checkBox_MOPS_TestMode`

- Pipe displayed Gauss / derived vectors through **cal factors** exactly as spec states (display path vs control path—define both).

---

## 8. Dependencies outside this markdown

- **`calibrator_DROK_UI_RequiredChanges.txt`** — widget names and operator intent.
- **`DROK_COIL_DRIVER_PROTOCOL.md`** — serial verbs, SAFE, TM tokens.
- **`DROK_MODS.md`** — hardware reality (relays, polarity, ESTOP).
- **`mt102_interface`** — actual getters for mag (and attitude if any).

---

## 9. Status

| Item | Result |
|------|--------|
| **Google AI Mode link** | Tooling could not fetch; **you supplied the text** — summarized in **section 1a**. |
| **`MAG_POINTING.md`** | Living plan at repo root; **section 1a** aligns pasted math with MOPS / Helmholtz / ini. |
| **Next unblocker** | Confirm **MOPS preset truth table** (72° vs 80° vs NE copy in UI spec) and whether **\(B_{\mathrm{earth}}\)** is measured once, tabulated, or closed-loop identified before each run. |

---

*Document version: includes section 1b cross-coupling matrix (from user diagram); finalize preset table and Earth-field policy with hardware owner.*
