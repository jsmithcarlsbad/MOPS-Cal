# Helmholtz coil — magnetic field at center (Gauss)

This document is the reference for converting **coil current** (and geometry) to **magnetic flux density** at the center of a **Helmholtz pair** (two identical circular coils, separation = radius \(R\)). Use it for Calibrator / closed-loop field targets (e.g. Gauss, dip angle) and for **triaxial** setups where **each axis has its own \(N\), \(R\) (or \(D\)), and current**.

**Fixture numbers (radii, turns per axis, wire gauge, resistance, example µT/A):** see **`COIL_AND_DRIVE_SPEC.md`** — that file is the **winding & drive spec** for this 3D Helmholtz (scaled 3DHC1: Z outer / Y middle / X inner).

### Calibration fixture frame (magnetic north)

**Convention:** The **3D Helmholtz cal fixture** is **aligned to magnetic north** once the **MT-102 magnetometer** is mounted in the fixture. That alignment is the **repeatable reference** for all field targets and test steps.

**Implications:**

- **Heading** reported by the MT-102 (and related ADAHRS/CAN logging) is measured in a frame that matches this **north-aligned** coil assembly — no extra **declination** rotation is assumed unless you add it explicitly in software.
- **Dip angle** and **horizontal / vertical** decomposition of a target vector \(|B|\) (e.g. 0.57 G at 72° or 80° dip) are taken in the **magnetic meridian**: **horizontal** lies in the local horizontal plane along **north** (and east); **vertical** is up/down. Map those components to **coil X / Y / Z** using the mechanical definition of which pair is **north–south**, which is **east–west**, and which is **vertical** (document per harness drawing).
- Ambient Earth field is **not** canceled unless you add a separate bias; closed-loop targets are usually **incremental** fields on top of ambient, or **total** simulated field — state which in the test procedure.

---

## 1. Standard formula (SI — result in Tesla)

For one Helmholtz pair, field on axis at the midpoint between coils:

\[
B = \left(\frac{4}{5}\right)^{3/2} \frac{\mu_0 N I}{R}
\]

| Symbol | Meaning |
|--------|--------|
| \(B\) | Magnetic flux density at the center (T) |
| \(\mu_0\) | Permeability of free space: \(4\pi \times 10^{-7}\ \mathrm{T\cdot m/A}\) |
| \(N\) | Number of turns **in each** of the two coils (same \(N\) for both) |
| \(I\) | Current in **amperes** (same in both coils, same sense) |
| \(R\) | **Radius** of each coil (meters). Spacing between coil planes = \(R\) (Helmholtz condition). |

**Geometric factor:** \(\left(\frac{4}{5}\right)^{3/2} \approx 0.71554\).

**Gauss:** \(B_{\mathrm{G}} = B_{\mathrm{T}} \times 10\,000\).

---

## 2. Equivalent numeric form (Tesla, \(R\) in meters, \(I\) in amperes)

Combine constants:

\[
B_{\mathrm{T}} \approx 8.992\times 10^{-7}\,\frac{N\,I}{R}
\]

(using \(\mu_0\) and \(\left(4/5\right)^{3/2}\); value rounded). Then multiply by \(10\,000\) for Gauss.

A compact form sometimes written as:

\[
B_{\mathrm{T}} \approx 0.8992\times 10^{-6}\,\frac{N\,I}{R}
\]

(same content as \(8.992\times 10^{-7}\)).

---

## 3. Practical form (Gauss, \(I\) in mA, diameter in cm)

Let **\(D\)** be the **diameter** of each coil, \(D = 2R\). With \(R_{\mathrm{m}} = D_{\mathrm{cm}}/(100\times 2)\):

\[
B_{\mathrm{G}} \approx 0.001798\,\frac{N\,I_{\mathrm{mA}}}{D_{\mathrm{cm}}}
\]

where:

- \(I_{\mathrm{mA}}\) = current in **milliamperes**
- \(D_{\mathrm{cm}}\) = coil **diameter** in **centimeters** (not separation; Helmholtz spacing is still \(R = D/2\) in consistent units)

**Check:** \(N=100\), \(I=100\ \mathrm{mA}\), \(D=20\ \mathrm{cm}\) → \(B_{\mathrm{G}} \approx 0.001798 \times 100 \times 100 / 20 \approx 0.90\ \mathrm{G}\).

> **Note:** A formula that looks like `1.798 × N × I_mA / D_cm` without the **\(10^{-3}\)** scale is **not** consistent with the SI Helmholtz result for typical mA/cm — the correct leading factor for **Gauss** with those units is **~0.001798** (i.e. **1.798×10⁻³**).

---

## 4. Triaxial (3D) Helmholtz coil

- Treat **X**, **Y**, and **Z** as **three independent** Helmholtz pairs (each pair has its own \(N_X, R_X, I_X\), etc.).
- Nested coils usually have **different diameters** / radii — use the **correct \(N\) and \(R\) (or \(D\)) per axis** in the formulas above.
- The **total** field at the center is the **vector sum** of the three axis contributions (plus any ambient field); magnitude and “dip” depend on how you combine \(B_X, B_Y, B_Z\).

---

## 5. Implementation checklist (firmware / host)

1. For each axis \(a \in \{X,Y,Z\}\): store **\(N_a\)**, **\(R_a\)** (or **\(D_a\)**) from the mechanical/electrical design.
2. From desired **\(B_a\)** (or from a vector target decomposed into axes), invert the appropriate formula to get **target current** \(I_a\) (then feed mA to the coil driver / closed loop).
3. Shunt / INA readings give **current**; use the same geometry constants to convert **measured \(I\)** ↔ **expected \(B\)** for that axis.

---

## 6. References

- Helmholtz coil geometry: two identical coils, separation = radius, same current direction.
- TI / textbooks: \(B = (4/5)^{3/2}\,\mu_0 N I / R\) at center.
