# 3D Helmholtz fixture — calibrator harness

This project uses a **single 6-pin** connector between the **calibrator electronics** (including the **latest hardware driver chassis**) and the **3D Helmholtz coil fixture**. Pin numbering follows the **connector housing** (pin **1** as marked on the part you use—e.g. triangle / keying).

## 6-pin pinout (driver chassis wiring)

| Pin | Wire color | Signal |
|-----|------------|--------|
| 1 | Red | X Coil+ |
| 2 | Black | X Coil− |
| 3 | White | Y Coil+ |
| 4 | Yellow | Y Coil− |
| 5 | Green | Z Coil+ |
| 6 | Blue | Z Coil− |

**+ / −** are the two drive nodes for that axis (bridge / RC / sense path to the coil pair). If field polarity is wrong on one axis, swap **only** that axis’s **+** and **−** at one end of the harness.

Wire colors are fixed for this build so the harness matches the driver chassis (distinct colors; **no orange** in the set).

Use the **same** connector series, **same** pin-1 orientation, and **same** colors on **both** ends of the cable assembly.

See also **`COIL_DRIVER.md`** for the full drive and sense topology.
