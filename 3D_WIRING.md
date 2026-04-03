# 3D Helmholtz fixture — calibrator harness

This project uses a **single 6-pin** connector between the **calibrator electronics** and the **3D Helmholtz coil fixture**. Pin numbering follows the **connector housing** (pin **1** as marked on the part you use—e.g. triangle / keying).

## 6-pin pinout (fixed for this build)

Colors are chosen to stay distinct in a typical jumper kit (**no orange** — **YIN+** is **white**).

| Pin | Signal | Wire color |
|-----|--------|------------|
| 1 | XIN+ | Red |
| 2 | XIN− | Black |
| 3 | YIN+ | White |
| 4 | YIN− | Yellow |
| 5 | ZIN+ | Green |
| 6 | ZIN− | Blue |

**+ / −** are the two drive nodes for that axis (bridge / RC / sense path to the coil pair). If field polarity is wrong on one axis, swap **only** that axis’s **+** and **−** at one end of the harness.

Use the **same** connector series, **same** pin-1 orientation, and **same** colors on **both** ends of the cable assembly.

See also **`COIL_DRIVER.md`** for the full drive and sense topology.
