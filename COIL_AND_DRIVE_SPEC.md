# Helmholtz Calibrator – Coil Wire & Drive Specification

## 1. Fixture Geometry (Scaled 3DHC1)

| Axis | Coil Radius R | Groove Size (W×H) | Coils per Axis |
|------|---------------|------------------|----------------|
| **Z** (outer) | 156 mm | 10.9 × 12.9 mm | 2 |
| **Y** (middle) | 132 mm | 9.4 × 12.9 mm | 2 |
| **X** (inner) | 100 mm | 15.5 × 22.7 mm | 2 |

Test volume: 100×100×100 mm³ centered at fixture origin.

---

## 2. Wire Specification

| Parameter | Value | Notes |
|-----------|-------|------|
| **Gauge** | AWG 22 | 0.644 mm bare, ~0.7 mm with enamel |
| **Alternative** | AWG 24 | 0.511 mm bare – more turns, lower current |
| **Type** | Enameled copper (magnet wire) | For wire-wrap grooves |
| **Resistance** | ~53 mΩ/m (AWG 22) | At 20°C |

**Groove fit:** AWG 22 allows ~14–16 turns per layer in the Y/Z grooves and ~24 in the X groove. AWG 24 allows more turns for higher field at lower current.

---

## 3. Turns per Coil & Wire Length

Recommended turns (based on groove capacity and field requirement):

| Axis | Turns per Coil | Coils | Circumference | Wire per Coil | Total per Axis |
|------|----------------|-------|---------------|---------------|----------------|
| **Z** | 80 | 2 | 2π × 156 mm = 980 mm | 78.4 m | 156.8 m |
| **Y** | 80 | 2 | 2π × 132 mm = 829 mm | 66.3 m | 132.6 m |
| **X** | 100 | 2 | 2π × 100 mm = 628 mm | 62.8 m | 125.6 m |

**Total wire:** ~415 m (add ~10% for leads and connections → **~460 m**)

---

## 4. Magnetic Field Formula

For a Helmholtz pair (separation = radius R):

**B = (8/5^(3/2)) × μ₀ × N × I / R**

With μ₀ = 4π×10⁻⁷ T·m/A:

**B ≈ 8.99×10⁻⁷ × N × I / R** (Tesla)

| Axis | N | R (m) | I (A) | B (µT) |
|------|---|-------|-------|--------|
| Z | 80 | 0.156 | 0.5 | 230 |
| Y | 80 | 0.132 | 0.5 | 272 |
| X | 100 | 0.100 | 0.5 | 450 |

All axes exceed ~65 µT, so Earth’s field can be nulled on each axis.

---

## 5. Driving the Coils – Nulling Earth’s Field

### 5.1 Earth’s Field

- Typical magnitude: **25–65 µT** (location-dependent)
- Direction: horizontal component + inclination (dip angle)
- To cancel Earth’s field at the test point: **B_coil = −B_earth**

### 5.2 Three-Axis Control

Each axis pair (Hx, Hy, Hz) is driven independently. The total field at the center is:

**B_total = Bx·x̂ + By·ŷ + Bz·ẑ**

To null Earth’s field:

- **Bx = −B_earth,x**
- **By = −B_earth,y**
- **Bz = −B_earth,z**

### 5.3 Required Currents

From B = 8.99×10⁻⁷ × N × I / R:

**I = B × R / (8.99×10⁻⁷ × N)**

For |B| = 50 µT (typical nulling):

| Axis | I (mA) |
|------|--------|
| Z | 86 |
| Y | 73 |
| X | 56 |

Use **0.5 A** per axis as a safe design current.

---

## 6. Arbitrary Magnetometer Orientation (Independent of Earth)

### 6.1 Principle

With three orthogonal coil pairs, any field vector **B** in the test volume can be produced by choosing currents Ix, Iy, Iz:

- **Bx** from X coils
- **By** from Y coils  
- **Bz** from Z coils

So the magnetometer can be placed in any orientation and will see a controlled field, independent of Earth’s field.

### 6.2 Modes of Operation

| Mode | Purpose | Drive |
|------|---------|-------|
| **Null** | Zero field at center | Ix, Iy, Iz set so B_total = −B_earth |
| **Calibration** | Known field for scaling/offset | Apply known B, measure magnetometer output |
| **Orientation test** | Check response vs. direction | Apply B along chosen axis, rotate magnetometer |

### 6.3 Drive Electronics

- **3 independent current sources** (one per axis)
- **Bipolar** (reversible current) for full 3D control
- **Range:** 0–0.5 A per axis
- **Resolution:** ~1 mA for fine nulling

Example: three H-bridge or linear current sources with DAC/ADC control.

### 6.4 Nulling Procedure

1. Place magnetometer at center of test volume.
2. Measure B_earth (or use local declination/inclination).
3. Set initial currents (e.g. 50 mA per axis).
4. Iteratively adjust Ix, Iy, Iz until magnetometer reads (0, 0, 0).
5. Record null currents for later use.

---

## 7. Benchtop Power Supply – Driving & Calibration

### 7.1 Supply Requirements

| Parameter | Minimum | Recommended |
|-----------|---------|--------------|
| **Voltage** | 5 V | 0–30 V (adjustable) |
| **Current** | 0.5 A | 0–1 A (current limit) |
| **Outputs** | 1 | 1–3 (one per axis) |

**Per-axis voltage at 0.5 A:** V = I × R ≈ 0.5 × 7 Ω ≈ **3.5 V**

A single 0–30 V / 0–1 A supply is sufficient. For simultaneous three-axis drive, use a triple-output supply or three separate supplies.

### 7.2 Coil Wiring (Per Axis)

Each axis has **2 coils in series**. Wire them so the magnetic fields add at the center:

- **Same winding direction** on both coils
- **Series connection:** end of coil 1 → start of coil 2
- **Polarity:** reversing the supply leads reverses the field direction (needed for nulling)

Bring out two leads per axis to a terminal block or banana jacks.

### 7.3 Single-Supply Setup (One Axis at a Time)

With one benchtop supply:

1. **Set current limit** to 0.5 A before connecting.
2. **Set voltage** to 5–10 V (headroom for IR drop).
3. Use a **3-way switch** or **alligator clips** to connect the supply to X, Y, or Z coils.
4. **Reverse polarity:** swap + and − at the coil terminals to reverse field direction.

### 7.4 Multi-Supply Setup (All Axes Simultaneous)

With 2–3 supplies (or one triple-output supply):

1. Connect each supply to one axis (X, Y, Z).
2. Set current limit to 0.5 A on each.
3. Set voltage to 5–10 V on each.
4. Drive all three axes at once for nulling and full 3D calibration.

### 7.5 Calibration Procedure (Benchtop Supply)

#### Step 1: Single-Axis Field Constant

For each axis (X, Y, Z):

1. Place magnetometer at fixture center, aligned so one sensor axis matches the coil axis.
2. Set supply to 0 A, then increase to 100 mA.
3. Record magnetometer reading (e.g. Bx in µT).
4. Compute **field constant:** k = B_measured / I (µT/A).
5. Compare to theory: B = 8.99×10⁻⁷ × N × I / R.

| Axis | Expected k (µT/A) @ design turns |
|------|----------------------------------|
| Z | 461 |
| Y | 545 |
| X | 900 |

If measured k differs, check turn count and coil radius.

#### Step 2: Scale Factor Calibration

1. Drive one axis at known currents: 50, 100, 150, 200 mA.
2. Plot magnetometer output vs. current.
3. Fit slope = scale factor (counts/µT or LSB/µT).
4. Repeat for all three magnetometer axes (rotate fixture or magnetometer between runs).

#### Step 3: Nulling (Zero-Field Calibration)

1. Place magnetometer at center.
2. With **one supply:** drive X first, adjust until magnetometer X reads ~0; disconnect, connect Y, adjust; repeat for Z. Iterate 2–3 times.
3. With **three supplies:** adjust Ix, Iy, Iz together until (Bx, By, Bz) ≈ (0, 0, 0).
4. **Reverse polarity:** if an axis needs negative current, swap that coil’s leads and use positive current.
5. Record null currents (Ix_null, Iy_null, Iz_null) for repeatability.

#### Step 4: Full 3D Calibration (Optional)

1. With null established, apply known fields along each axis.
2. Rotate magnetometer to 6+ orientations (e.g. ±X, ±Y, ±Z).
3. Use data to solve for hard-iron offset, soft-iron matrix, and scale factors.

### 7.6 Practical Tips

- **Current limit:** Always set to 0.5 A before connecting to avoid overheating.
- **Coil heating:** At 0.5 A, coils warm up in a few minutes. Allow to cool between long runs.
- **Earth’s field:** Calibrate away from steel benches, tools, and power cables.
- **Leads:** Keep supply leads short and twisted to reduce stray field.
- **Polarity marking:** Label coil pairs (+/− or A/B) to track field direction.

---

## 8. Power & Thermal

| Axis | Resistance (est.) | Power @ 0.5 A |
|------|-------------------|---------------|
| Z | 156.8 m × 0.053 Ω/m ≈ 8.3 Ω | 2.1 W |
| Y | 132.6 m × 0.053 Ω/m ≈ 7.0 Ω | 1.8 W |
| X | 125.6 m × 0.053 Ω/m ≈ 6.7 Ω | 1.7 W |
| **Total** | ~22 Ω | **~5.6 W** |

PLA fixture can handle this with natural convection. For long runs, monitor temperature.

---

## 9. Summary

| Item | Specification |
|------|---------------|
| **Wire** | AWG 22 enameled copper, ~460 m total |
| **Turns** | Z: 80/coil, Y: 80/coil, X: 100/coil |
| **Current** | 0–0.5 A per axis (bipolar) |
| **Field** | 65+ µT per axis (enough to null Earth) |
| **Drive** | Benchtop supply 0–30 V / 0–1 A (see §7) |
| **Power** | ~6 W at full current |

---

## 10. References

- 3D-Helmholtz-Coil-Simulator: https://github.com/tarciszera/3D-Helmholtz-Coil-Simulator
- Helmholtz coil field formula: B = (4/5)^(3/2) × μ₀ × N × I / R
- Earth’s magnetic field: ~25–65 µT
