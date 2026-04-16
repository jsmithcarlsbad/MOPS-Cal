# MT-102 F-block capture

Parsed from the last valid `F` line after `QUE` (factory flash cal). See `mt102_interface.FlashCalData` / `MagnetometerParser.cpp` case `'M'`.

- **Captured (host local time):** 2026-04-14T16:20:54
- **F packets parsed (this session):** 1
- **Serial (from F block):** 1475

## Offsets (added to raw M counts as Int16 before soft-iron subtraction)

| Axis | Value |
|------|-------|
| X | 293 |
| Y | -63 |
| Z | 609 |

## Soft-iron matrix (stored /1000 in flash; used as below with `MAG_SF_UC = 0.01`)

Corrected Int16 counts: each axis subtracts `0.01 * (row · [x,y,z])` using **offset** x,y,z.

| | col (× x) | col (× y) | col (× z) |
|---|-------------|-------------|-------------|
| **X row** | 0 | -4.973 | -0.636 |
| **Y row** | -5.262 | 2.043 | -0.943 |
| **Z row** | 0.894 | -3.434 | 0.189 |

### Hint for “Y looks wrong” vs X/Z

- **|YX| + |YZ|** (cross terms into the Y correction) **= 6.205**; **|YY|** **= 2.043**.
- If cross terms are large vs `YY`, factory soft-iron is **mixing X/Z into Y**; with legacy axis routing that can show up as odd **Y Gauss** sign/magnitude vs the other channels.

## Raw F payload (384 ASCII hex chars = 192 bytes mag-cal prefix)

```text
000000000000><93><93><93?=84?=84?=84>;72>;72>;7207?;07?;07?;?<51
?<51?<51037>037>037>?296?296?29600;=00;=00;=012501250125??<1??<1
??<102610261026105<305<305<3000000000000000000000000000000000000
000000000000000000000000000000000000000000000000????????????????
1=<01<=11?>21>9;1?8:1<;9082309320:010=>10<?00?<310<;11=:12>9>?0<
>>1=>=2>>?:6>>;7>=84100011111222100011111222100:111;1228????????
```
