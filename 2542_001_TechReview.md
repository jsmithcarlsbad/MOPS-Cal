# MT102 calibration report — OCR extraction for technical review

**Purpose:** Machine-readable extraction from a **scanned PDF** (`2542_001.pdf`). 
Use this to correct transcription errors and, if possible, provide a **searchable PDF** or **CSV/JSON** export from the original calibration system.

**Baseline expectation:** Because the source is a scan, **treat every numeric cell as suspect until confirmed** against the signed certificate, even if not individually flagged.

### Priority items for human verification (summary)

These are the highest-impact items the OCR pipeline is most likely to get wrong on this scan; please confirm each against the original certificate.

1. **Pass/Fail / status column:** Several vertical tick marks were read as placeholder text (for example `xxxix-xxxxxx`, `xxxxxxx`). **Please transcribe the actual Pass/Fail (or equivalent) column** from the scan for every applicable row.
2. **All numeric table cells:** Offsets, scale factors (desired/actual), tolerances, retries, and results on **both pages** — confirm digit-by-digit (decimal point and minus signs are easy to corrupt).
3. **Axis / step description strings:** Parentheses, commas, and subscripts in axis formulas are garbled in places; **confirm the exact axis string** for each step where it matters for traceability.
4. **Metadata block:** Serial number, **date and time** (`03/03/16 10:43:38` per OCR), calibration SW version, Mag SW version, and **CalData file version** (OCR shows `0.0` — confirm whether the field was blank, zero, or misread).
5. **Anything not captured as text:** Signatures, stamps, logos, marginal notes, environmental limits, standard references, and **traceability / accreditation** blocks are **not reliably extracted** from a scan; confirm presence and content on the paper/PDF original.

---

## 1. Provenance

| Item | Value |
|------|-------|
| Source file | `2542_001.pdf` |
| Generated (UTC) | 2026-04-14 17:59:38Z |
| OCR | RapidOCR (ONNXRuntime); pages rasterized with PyMuPDF |
| Rasterization | 3.0× PDF point size |
| Pages | 2 |
| Embedded PDF metadata | {"format": "PDF 1.4", "creationDate": "D:20260414044344-07'00'"} |

---

## 2. Verification legend (how flags were assigned)

| Tag | Meaning |
|-----|---------|
| **VERIFY: data** | Contains digits **or** matches common certificate labels (Serial, Date, Ver, Step, Offset, Scale, Pass/Fail, etc.). **Please confirm against the original.** |
| **VERIFY: low OCR confidence** | OCR score below 0.72 on this scan (max observed ~0.93). **Confirm visually.** |
| **VERIFY: OCR artifact** | Character classes typical of mis-read table rules / noise. **Retype from scan.** |
| **VERIFY: medium OCR confidence on numeric text** | Digits present and score between 0.72 and 0.80 — easy place for single-digit errors. |
| **Spot-check: banner / table header** | Mostly words; lower immediate risk but headers anchor column alignment. |

---

## 3. Page geometry

- **Page 1:** 612.00 × 792.00 pt (width × height). OCR timing (engine-reported, s): [0.9889333248138428, 0.5967857837677002, 6.595263242721558]
- **Page 2:** 612.00 × 792.00 pt (width × height). OCR timing (engine-reported, s): [0.44586944580078125, 0.5540711879730225, 4.722567796707153]

---

## 4. All OCR elements (page, sequence, confidence, bbox, text, flags)

`bbox` is approximate, in **PDF points**, top-left origin.

### Page 1 — 163 elements

| Seq | conf | bbox (x0,y0–x1,y1) | text | Verification notes |
|----:|-----:|---|---|---|
| 1 | 0.920 | (127.7,30.0–494.3,43.3) | Sandel MT102 Magnetic Transducer Accessory Calibration Report | VERIFY: data (number or labeled field) |
| 2 | 0.808 | (31.7,64.3–80.7,73.3) | Serial Num: | VERIFY: data (number or labeled field) |
| 3 | 0.799 | (134.0,63.3–156.7,74.3) | 1475 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 4 | 0.832 | (133.7,75.0–163.7,85.3) | 2.0.0.0 | VERIFY: data (number or labeled field) |
| 5 | 0.887 | (31.7,76.0–115.0,84.7) | Calibration SW Ver: | VERIFY: data (number or labeled field) |
| 6 | 0.902 | (31.3,87.3–100.7,96.3) | CalData File ver: | VERIFY: data (number or labeled field) |
| 7 | 0.750 | (133.3,86.7–148.7,97.0) | 0.0 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 8 | 0.764 | (30.3,98.0–88.7,109.0) | Mag Sw Ver: | VERIFY: data (number or labeled field) |
| 9 | 0.735 | (135.0,97.3–156.3,109.3) | 1.00 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 10 | 0.833 | (29.7,109.0–55.3,120.7) | Date: | VERIFY: data (number or labeled field) |
| 11 | 0.853 | (134.3,110.3–209.0,119.0) | 03/03/16 10:43:38 | VERIFY: data (number or labeled field) |
| 12 | 0.787 | (31.7,131.3–55.3,143.0) | Step | VERIFY: data (number or labeled field) |
| 13 | 0.853 | (56.0,132.0–109.3,143.3) | Description | VERIFY: data (number or labeled field) |
| 14 | 0.799 | (194.7,132.3–217.7,143.0) | Axis | VERIFY: data (number or labeled field) |
| 15 | 0.838 | (222.3,133.0–251.7,142.3) | Offset | VERIFY: data (number or labeled field) |
| 16 | 0.900 | (264.3,133.3–357.7,142.0) | ScaleFactor Desired | VERIFY: data (number or labeled field) |
| 17 | 0.817 | (366.7,132.3–398.0,142.7) | Actual | VERIFY: data (number or labeled field) |
| 18 | 0.888 | (412.7,132.3–495.7,142.3) | Tolerance Retries | VERIFY: data (number or labeled field) |
| 19 | 0.724 | (506.3,132.7–528.7,142.3) | Pass | VERIFY: data (number or labeled field) |
| 20 | 0.717 | (531.7,132.3–551.7,142.3) | Fail | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 21 | 0.824 | (505.3,142.3–516.3,259.3) | xxxix-xxxxxx | Spot-check: banner / table header text |
| 22 | 0.881 | (264.0,155.3–307.0,165.3) | -9120.000 | VERIFY: data (number or labeled field) |
| 23 | 0.775 | (322.0,155.3–362.0,165.7) | 4217.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 24 | 0.846 | (412.0,155.0–458.3,165.0) | -14596.00( | VERIFY: data (number or labeled field) |
| 25 | 0.785 | (58.7,156.0–182.3,166.0) | Xm,XrYm, Yr.(Zm, | Spot-check: banner / table header text |
| 26 | 0.817 | (58.0,177.0–182.3,188.7) | Xm, Yr),Ym,-Xr,Zm | Spot-check: banner / table header text |
| 27 | 0.799 | (263.7,178.0–303.3,188.3) | 2792.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 28 | 0.751 | (322.0,178.3–361.3,188.7) | 8970.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 29 | 0.888 | (412.7,177.7–458.3,187.7) | -14735.00( | VERIFY: data (number or labeled field) |
| 30 | 0.751 | (58.3,200.3–184.0,212.0) | (Xm,Xr),Ym,-Yr,(Zm, | Spot-check: banner / table header text |
| 31 | 0.888 | (263.3,200.7–303.0,210.7) | 8688.000 | VERIFY: data (number or labeled field) |
| 32 | 0.795 | (322.0,201.3–364.3,211.3) | -3796.00( | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 33 | 0.844 | (412.0,200.3–458.7,211.3) | -14324.00( | VERIFY: data (number or labeled field) |
| 34 | 0.837 | (58.0,223.0–183.0,235.3) | (Xm,Yr,Ym, XrZm, | Spot-check: banner / table header text |
| 35 | 0.890 | (263.7,223.7–306.3,234.0) | -3171.000 | VERIFY: data (number or labeled field) |
| 36 | 0.748 | (321.7,222.7–365.0,235.0) | -8531.00( | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 37 | 0.840 | (412.0,223.7–458.7,233.7) | -14167.00( | VERIFY: data (number or labeled field) |
| 38 | 0.666 | (31.3,246.3–45.3,257.7) | 10 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 39 | 0.815 | (57.3,245.7–164.3,258.7) | Xm, Xr,Ym,Yr, | Spot-check: banner / table header text |
| 40 | 0.851 | (263.0,246.0–305.7,257.3) | -8984.000 | VERIFY: data (number or labeled field) |
| 41 | 0.820 | (321.0,245.7–362.7,258.0) | -3094.000 | VERIFY: data (number or labeled field) |
| 42 | 0.816 | (412.0,246.7–457.3,257.0) | 13247.000 | VERIFY: data (number or labeled field) |
| 43 | 0.608 | (31.3,258.3–44.7,269.3) | 11 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 44 | 0.535 | (30.7,269.0–45.3,281.0) | 12 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 45 | 0.763 | (57.7,269.3–163.7,281.0) | (Xm, Yr,(Ym, Xr, | Spot-check: banner / table header text |
| 46 | 0.886 | (262.7,268.7–303.0,281.0) | 3476.000 | VERIFY: data (number or labeled field) |
| 47 | 0.728 | (322.7,269.7–362.7,280.0) | -9202.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 48 | 0.832 | (412.0,269.3–456.7,279.3) | 13621.000 | VERIFY: data (number or labeled field) |
| 49 | 0.664 | (30.7,280.0–45.0,292.7) | 13 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 50 | 0.552 | (31.3,292.3–45.0,303.3) | 14 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 51 | 0.807 | (58.3,293.3–164.0,303.3) | (Xm-Xr, (Ym,Yr,f | Spot-check: banner / table header text |
| 52 | 0.830 | (262.7,292.3–302.7,303.3) | 8199.000 | VERIFY: data (number or labeled field) |
| 53 | 0.825 | (321.7,293.0–362.3,303.0) | 2952.000 | VERIFY: data (number or labeled field) |
| 54 | 0.880 | (413.0,292.3–457.3,302.3) | 13177.000 | VERIFY: data (number or labeled field) |
| 55 | 0.663 | (31.3,303.3–44.7,315.0) | 15 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 56 | 0.602 | (31.3,315.3–45.0,326.7) | 16 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 57 | 0.729 | (57.7,315.7–164.3,327.3) | (Xm,-Yr), (Ym,-Xr 1, ( | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 58 | 0.789 | (263.7,315.7–305.7,325.7) | -4261.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 59 | 0.753 | (321.3,315.7–361.7,325.7) | 9034.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 60 | 0.848 | (412.7,315.0–457.0,325.0) | 12865.000 | VERIFY: data (number or labeled field) |
| 61 | 0.713 | (504.7,311.0–515.7,396.0) | xxxxxxx | VERIFY: low OCR confidence — confirm visually |
| 62 | 0.664 | (31.3,327.3–44.7,338.3) | 17 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 63 | 0.555 | (31.3,338.7–44.7,349.7) | 18 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 64 | 0.799 | (57.3,338.0–162.3,350.3) | (Xm,XrYm,Zr | Spot-check: banner / table header text |
| 65 | 0.860 | (263.7,338.7–305.7,349.0) | -8358.000 | VERIFY: data (number or labeled field) |
| 66 | 0.886 | (321.3,338.3–362.7,349.0) | -13478.0 | VERIFY: data (number or labeled field) |
| 67 | 0.848 | (411.7,338.0–454.7,348.3) | -3683.000 | VERIFY: data (number or labeled field) |
| 68 | 0.656 | (31.3,350.0–44.3,361.0) | 19 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 69 | 0.666 | (31.3,362.0–44.3,372.7) | 20 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 70 | 0.778 | (58.3,362.7–179.3,372.7) | (Xm, Yr , f Ym, Zr), ( Zm | Spot-check: banner / table header text |
| 71 | 0.838 | (262.7,360.7–302.7,372.0) | 3924.000 | VERIFY: data (number or labeled field) |
| 72 | 0.798 | (321.3,361.7–362.3,371.7) | -14281.0( | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 73 | 0.870 | (412.0,361.0–455.0,371.0) | -8738.000 | VERIFY: data (number or labeled field) |
| 74 | 0.502 | (31.3,373.0–43.7,384.3) | 21 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 75 | 0.599 | (31.7,384.7–44.0,395.7) | 22 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 76 | 0.822 | (58.3,385.7–180.7,395.3) | (Xm,-Xr ), f Ym, Zr 3, ( Zm, | VERIFY: data (number or labeled field) |
| 77 | 0.719 | (262.7,384.3–302.7,394.7) | 9068.000 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 78 | 0.718 | (321.3,384.3–362.7,394.3) | -14598.0( | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 79 | 0.880 | (412.0,383.7–451.7,393.7) | 3468.000 | VERIFY: data (number or labeled field) |
| 80 | 0.512 | (504.3,389.7–516.0,441.3) | xxxx | VERIFY: low OCR confidence — confirm visually |
| 81 | 0.529 | (31.3,396.3–44.0,407.3) | 23 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 82 | 0.841 | (57.7,408.3–162.7,418.3) | (Xm,-Yr,  Ym, Zr , ( | Spot-check: banner / table header text |
| 83 | 0.882 | (263.0,407.3–305.7,417.3) | -3144.000 | VERIFY: data (number or labeled field) |
| 84 | 0.819 | (321.0,406.7–362.7,417.0) | -13840.00 | VERIFY: data (number or labeled field) |
| 85 | 0.804 | (411.3,405.3–452.0,416.7) | 8698.000 | VERIFY: data (number or labeled field) |
| 86 | 0.666 | (31.0,419.0–44.0,430.0) | 25 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 87 | 0.633 | (31.0,430.3–44.0,441.3) | 26 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 88 | 0.797 | (57.7,431.3–179.7,441.3) | ( Xm, Xr), (Ym,-Zr , ( Zm, | Spot-check: banner / table header text |
| 89 | 0.827 | (263.0,430.0–305.7,440.0) | -9760.000 | VERIFY: data (number or labeled field) |
| 90 | 0.791 | (320.7,429.3–363.3,440.3) | 14551.00 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 91 | 0.791 | (411.3,428.7–451.7,439.0) | 2393.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 92 | 0.612 | (31.3,441.7–43.7,453.3) | 27 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 93 | 0.884 | (411.0,451.3–451.3,462.7) | 7673.000 | VERIFY: data (number or labeled field) |
| 94 | 0.815 | (57.7,453.3–163.0,465.0) | (Xm, Yr), (Ym,-Zr, ( | Spot-check: banner / table header text |
| 95 | 0.749 | (262.3,452.3–302.7,463.7) | 2388.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 96 | 0.880 | (320.7,453.0–363.0,463.0) | 13930.001 | VERIFY: data (number or labeled field) |
| 97 | 0.666 | (31.7,464.7–43.7,476.3) | 29 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 98 | 0.865 | (262.7,475.0–302.7,486.3) | 7692.000 | VERIFY: data (number or labeled field) |
| 99 | 0.742 | (321.3,475.7–363.0,485.7) | 13725.001 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 100 | 0.857 | (412.0,475.0–454.7,485.0) | -4439.000 | VERIFY: data (number or labeled field) |
| 101 | 0.641 | (505.3,471.7–515.7,521.3) | xxxx | VERIFY: low OCR confidence — confirm visually |
| 102 | 0.666 | (31.7,476.0–43.7,487.7) | 30 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 103 | 0.741 | (57.7,477.3–163.3,487.3) | Xm-XrYm,-Zr, | Spot-check: banner / table header text |
| 104 | 0.561 | (31.7,488.3–43.0,498.7) | 31 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 105 | 0.591 | (31.7,499.3–43.7,509.3) | 32 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 106 | 0.789 | (57.3,499.7–181.3,509.7) | (Xm-Yr,Ym,-Zr,(Zm, | Spot-check: banner / table header text |
| 107 | 0.880 | (263.3,498.7–305.7,508.7) | -4390.000 | VERIFY: data (number or labeled field) |
| 108 | 0.826 | (320.7,498.0–363.0,509.0) | 14343.00t | VERIFY: data (number or labeled field) |
| 109 | 0.809 | (411.7,497.7–455.0,507.7) | -9876.000 | VERIFY: data (number or labeled field) |
| 110 | 0.602 | (31.3,510.3–43.7,521.3) | 33 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 111 | 0.880 | (504.0,515.3–516.0,724.3) | 区区区区区区区区区区区区区区区区区区 | VERIFY: OCR artifact / garbling — retype from scan |
| 112 | 0.665 | (30.7,522.0–44.0,532.7) | 34 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 113 | 0.804 | (57.3,522.0–162.3,533.0) | Xm,Zr,Ym,Yr, | Spot-check: banner / table header text |
| 114 | 0.892 | (263.3,521.3–310.3,531.3) | -14329.000 | VERIFY: data (number or labeled field) |
| 115 | 0.802 | (321.3,521.3–361.0,531.3) | 4200.000 | VERIFY: data (number or labeled field) |
| 116 | 0.778 | (411.3,520.0–451.7,531.7) | 7794.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 117 | 0.508 | (30.7,533.0–43.7,544.7) | 35 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 118 | 0.589 | (31.3,545.3–44.0,556.3) | 36 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 119 | 0.781 | (57.3,545.3–163.3,556.3) | (Xm,Zr,Ym,-Xr | Spot-check: banner / table header text |
| 120 | 0.847 | (262.3,544.0–311.0,555.0) | -14464.000 | VERIFY: data (number or labeled field) |
| 121 | 0.821 | (320.7,543.7–361.3,555.0) | 9744.000 | VERIFY: data (number or labeled field) |
| 122 | 0.880 | (412.0,543.0–455.0,554.3) | -4506.000 | VERIFY: data (number or labeled field) |
| 123 | 0.516 | (31.0,557.0–44.0,568.0) | 37 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 124 | 0.667 | (31.0,568.3–44.0,579.0) | 38 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 125 | 0.758 | (57.3,569.0–180.0,578.7) | I Xm, Zr 1, I Ym,-Yr I, f Zm | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 126 | 0.814 | (262.7,567.7–310.7,577.7) | -13839.000 | VERIFY: data (number or labeled field) |
| 127 | 0.820 | (320.7,567.3–363.0,577.3) | -2599.00( | VERIFY: data (number or labeled field) |
| 128 | 0.859 | (412.0,566.3–455.0,576.7) | -9378.000 | VERIFY: data (number or labeled field) |
| 129 | 0.667 | (31.0,579.7–44.0,590.3) | 39 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 130 | 0.523 | (31.0,590.7–44.0,601.3) | 40 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 131 | 0.799 | (57.7,591.3–179.7,601.0) | Xm,Zr,Ym,Xr,Zm, | Spot-check: banner / table header text |
| 132 | 0.894 | (263.0,590.3–310.7,600.3) | -13644.000 | VERIFY: data (number or labeled field) |
| 133 | 0.804 | (321.0,589.3–362.7,600.0) | -8126.000 | VERIFY: data (number or labeled field) |
| 134 | 0.777 | (411.3,589.3–451.7,599.3) | 2964.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 135 | 0.808 | (411.7,611.3–455.0,622.0) | -9338.000 | VERIFY: data (number or labeled field) |
| 136 | 0.519 | (31.0,613.0–44.0,624.0) | 42 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 137 | 0.861 | (57.3,614.0–180.7,623.7) | Xm,-Zr,(Ym,Yri,Zm, | Spot-check: banner / table header text |
| 138 | 0.783 | (263.0,612.7–307.3,622.7) | 13357.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 139 | 0.866 | (321.0,612.7–361.0,622.7) | 2980.000 | VERIFY: data (number or labeled field) |
| 140 | 0.627 | (31.3,635.7–43.7,647.0) | 44 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 141 | 0.813 | (262.7,634.7–307.7,646.0) | 13045.000 | VERIFY: data (number or labeled field) |
| 142 | 0.877 | (321.0,635.0–361.3,645.3) | 8254.000 | VERIFY: data (number or labeled field) |
| 143 | 0.823 | (411.3,634.3–451.7,645.0) | 2701.000 | VERIFY: data (number or labeled field) |
| 144 | 0.793 | (57.0,636.0–181.3,646.7) | Xm,-Zr , ( Ym,-Xr1, ( Zm, | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 145 | 0.524 | (31.0,646.7–43.7,658.0) | 45 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 146 | 0.658 | (31.3,658.0–43.7,669.3) | 46 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 147 | 0.741 | (56.7,659.3–162.7,669.3) | ( Xm,-Zr l, ( Ym,-Yr I, t | Spot-check: banner / table header text |
| 148 | 0.814 | (262.7,658.3–307.3,668.3) | 13780.000 | VERIFY: data (number or labeled field) |
| 149 | 0.853 | (321.3,657.7–362.3,668.0) | -4306.000 | VERIFY: data (number or labeled field) |
| 150 | 0.841 | (411.0,656.3–451.7,667.7) | 8313.000 | VERIFY: data (number or labeled field) |
| 151 | 0.665 | (30.7,670.0–43.7,681.0) | 47 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 152 | 0.667 | (30.7,681.3–44.0,692.0) | 48 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 153 | 0.799 | (57.0,681.0–162.3,691.7) | Xm-ZrYm,Xr | Spot-check: banner / table header text |
| 154 | 0.897 | (263.0,681.0–307.3,691.0) | 14021.000 | VERIFY: data (number or labeled field) |
| 155 | 0.816 | (321.0,680.0–362.3,691.0) | -9516.00( | VERIFY: data (number or labeled field) |
| 156 | 0.857 | (411.0,679.3–455.0,690.3) | -3759.000 | VERIFY: data (number or labeled field) |
| 157 | 0.667 | (30.7,692.7–43.7,703.3) | 49 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 158 | 0.928 | (56.7,693.7–171.3,702.3) | Calculate and set offsets and | VERIFY: data (number or labeled field) |
| 159 | 0.666 | (30.7,703.3–44.0,714.7) | 50 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 160 | 0.884 | (56.7,704.7–141.3,713.7) | Calculating Offsets... | Spot-check: banner / table header text |
| 161 | 0.660 | (30.3,714.7–43.7,726.0) | 51 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 162 | 0.918 | (55.3,714.7–130.3,725.3) | and Scale Factors. | VERIFY: data (number or labeled field) |
| 163 | 0.661 | (294.3,731.0–323.7,743.3) | Page I1 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |

### Page 2 — 178 elements

| Seq | conf | bbox (x0,y0–x1,y1) | text | Verification notes |
|----:|-----:|---|---|---|
| 1 | 0.908 | (128.3,29.3–493.3,43.0) | Sandel MT102 Magnetic Transducer Accessory Calibration Report | VERIFY: data (number or labeled field) |
| 2 | 0.768 | (34.7,64.3–56.7,74.7) | Step | VERIFY: data (number or labeled field) |
| 3 | 0.870 | (58.7,64.3–111.3,75.0) | Description | VERIFY: data (number or labeled field) |
| 4 | 0.799 | (196.3,65.0–218.0,74.7) | Axis | VERIFY: data (number or labeled field) |
| 5 | 0.820 | (222.7,64.3–253.3,74.7) | Offset | VERIFY: data (number or labeled field) |
| 6 | 0.908 | (264.7,64.7–318.3,73.7) | ScaleFactor | Spot-check: banner / table header text |
| 7 | 0.800 | (321.7,63.7–357.7,74.0) | Desired | VERIFY: data (number or labeled field) |
| 8 | 0.856 | (367.0,63.7–398.3,74.0) | Actual | VERIFY: data (number or labeled field) |
| 9 | 0.898 | (412.0,63.7–458.7,73.7) | Tolerance | VERIFY: data (number or labeled field) |
| 10 | 0.867 | (462.0,64.0–495.0,73.3) | Retries | VERIFY: data (number or labeled field) |
| 11 | 0.795 | (506.3,63.7–528.0,73.3) | Pass | VERIFY: data (number or labeled field) |
| 12 | 0.797 | (531.7,63.0–551.7,74.0) | Fail | VERIFY: data (number or labeled field) |
| 13 | 0.665 | (35.0,75.3–47.3,86.7) | 52 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 14 | 0.674 | (222.7,75.0–240.3,86.3) | 293 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 15 | 0.799 | (367.0,75.0–389.0,84.7) | 2207 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 16 | 0.681 | (411.7,74.3–434.7,85.0) | 2500 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 17 | 0.843 | (59.7,76.3–106.0,85.3) | Test Offset | VERIFY: data (number or labeled field) |
| 18 | 0.661 | (34.7,86.7–47.3,98.0) | 53 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 19 | 0.831 | (60.0,87.7–105.7,96.7) | Test Offset | VERIFY: data (number or labeled field) |
| 20 | 0.744 | (223.0,87.0–238.7,97.3) | -63 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 21 | 0.799 | (366.3,85.0–389.3,97.0) | 2437 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 22 | 0.744 | (411.7,85.7–434.3,96.7) | 2500 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 23 | 0.573 | (34.7,98.0–47.3,109.0) | 54 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 24 | 0.831 | (60.0,99.0–106.7,108.0) | Test Offset | VERIFY: data (number or labeled field) |
| 25 | 0.610 | (223.0,98.0–240.3,108.3) | 609 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 26 | 0.741 | (367.3,97.0–389.0,108.0) | 1891 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 27 | 0.776 | (412.0,97.3–434.7,108.0) | 2500 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 28 | 0.605 | (505.0,94.0–516.7,213.0) | xxxxxxxxxx | VERIFY: low OCR confidence — confirm visually |
| 29 | 0.664 | (34.3,109.3–47.3,120.3) | 55 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 30 | 0.524 | (58.3,110.0–76.0,120.7) | sxx | VERIFY: low OCR confidence — confirm visually |
| 31 | 0.584 | (196.3,108.7–212.0,120.7) | xx | VERIFY: low OCR confidence — confirm visually |
| 32 | 0.829 | (264.0,108.7–289.7,120.0) | 0.000 | VERIFY: data (number or labeled field) |
| 33 | 0.829 | (322.0,108.7–347.3,119.3) | 0.000 | VERIFY: data (number or labeled field) |
| 34 | 0.819 | (368.0,109.3–396.7,118.7) | 10.000 | VERIFY: data (number or labeled field) |
| 35 | 0.700 | (412.3,108.3–441.3,118.7) | 10.000 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 36 | 0.581 | (35.0,121.3–47.0,131.3) | 56 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 37 | 0.620 | (58.3,121.3–76.7,133.7) | sxy | VERIFY: low OCR confidence — confirm visually |
| 38 | 0.633 | (197.0,120.0–211.3,133.3) | XY | VERIFY: low OCR confidence — confirm visually |
| 39 | 0.856 | (264.7,120.0–292.0,130.7) | -4.973 | VERIFY: data (number or labeled field) |
| 40 | 0.755 | (322.3,120.7–347.0,130.3) | 0.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 41 | 0.715 | (367.3,120.3–391.7,130.0) | 5.027 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 42 | 0.856 | (412.7,119.7–441.7,131.0) | 10.000 | VERIFY: data (number or labeled field) |
| 43 | 0.593 | (34.7,132.0–47.3,143.7) | 57 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 44 | 0.848 | (265.0,131.7–292.7,142.3) | -0.636 | VERIFY: data (number or labeled field) |
| 45 | 0.750 | (322.0,131.7–347.3,142.3) | 0.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 46 | 0.756 | (366.7,131.3–392.3,142.0) | 9.364 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 47 | 0.857 | (413.0,131.7–441.7,142.0) | 10.000 | VERIFY: data (number or labeled field) |
| 48 | 0.555 | (59.0,134.3–75.0,143.0) | $xz | VERIFY: low OCR confidence — confirm visually |
| 49 | 0.622 | (34.7,143.7–47.0,155.0) | 58 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 50 | 0.669 | (58.7,145.3–75.3,155.7) | syx | VERIFY: low OCR confidence — confirm visually |
| 51 | 0.805 | (264.3,143.3–292.3,154.0) | -5.262 | VERIFY: data (number or labeled field) |
| 52 | 0.833 | (321.7,142.7–347.3,154.3) | 0.000 | VERIFY: data (number or labeled field) |
| 53 | 0.825 | (366.7,143.0–392.0,154.0) | 4.738 | VERIFY: data (number or labeled field) |
| 54 | 0.816 | (412.3,142.7–441.7,154.0) | 10.000 | VERIFY: data (number or labeled field) |
| 55 | 0.664 | (34.7,155.0–47.3,166.7) | 59 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 56 | 0.775 | (264.3,155.7–288.7,165.3) | 2.043 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 57 | 0.764 | (322.0,154.7–347.3,165.3) | 0.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 58 | 0.833 | (366.7,154.3–392.0,165.0) | 7.957 | VERIFY: data (number or labeled field) |
| 59 | 0.794 | (413.3,154.7–442.0,165.0) | 10.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 60 | 0.602 | (58.7,157.0–75.0,167.3) | syy | VERIFY: low OCR confidence — confirm visually |
| 61 | 0.579 | (34.7,167.3–46.3,177.3) | 60 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 62 | 0.668 | (58.7,168.3–75.0,178.3) | syz | VERIFY: low OCR confidence — confirm visually |
| 63 | 0.856 | (263.7,166.7–292.0,177.0) | -0.943 | VERIFY: data (number or labeled field) |
| 64 | 0.831 | (321.7,165.0–347.3,177.0) | 0.000 | VERIFY: data (number or labeled field) |
| 65 | 0.762 | (366.7,166.3–391.7,176.0) | 9.057 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 66 | 0.857 | (413.0,166.0–442.0,176.3) | 10.000 | VERIFY: data (number or labeled field) |
| 67 | 0.665 | (34.0,178.3–46.3,189.3) | 61 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 68 | 0.672 | (58.7,180.0–74.3,188.7) | szx | VERIFY: low OCR confidence — confirm visually |
| 69 | 0.832 | (264.0,178.3–288.7,187.7) | 0.894 | VERIFY: data (number or labeled field) |
| 70 | 0.833 | (322.0,177.3–347.3,188.0) | 0.000 | VERIFY: data (number or labeled field) |
| 71 | 0.682 | (366.7,177.0–392.3,188.3) | 9.106 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 72 | 0.850 | (412.7,177.3–442.0,187.7) | 10.000 | VERIFY: data (number or labeled field) |
| 73 | 0.510 | (34.3,190.0–46.3,200.0) | 62 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 74 | 0.627 | (58.7,190.7–74.3,201.0) | szy | VERIFY: low OCR confidence — confirm visually |
| 75 | 0.520 | (196.0,189.0–210.3,199.7) | zy | VERIFY: low OCR confidence — confirm visually |
| 76 | 0.803 | (263.7,189.3–292.0,199.7) | -3.434 | VERIFY: data (number or labeled field) |
| 77 | 0.760 | (322.0,189.3–347.0,199.0) | 0.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 78 | 0.833 | (366.3,189.0–392.3,199.3) | 6.566 | VERIFY: data (number or labeled field) |
| 79 | 0.810 | (412.7,188.7–441.7,198.7) | 10.000 | VERIFY: data (number or labeled field) |
| 80 | 0.667 | (34.3,201.0–46.3,211.0) | 63 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 81 | 0.765 | (263.7,200.3–289.0,211.0) | 0.189 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 82 | 0.833 | (321.7,200.3–347.7,210.7) | 0.000 | VERIFY: data (number or labeled field) |
| 83 | 0.747 | (367.0,200.3–391.3,210.0) | 9.811 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 84 | 0.853 | (412.7,200.0–442.0,210.3) | 10.000 | VERIFY: data (number or labeled field) |
| 85 | 0.667 | (34.3,212.3–46.3,222.3) | 64 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 86 | 0.889 | (59.3,212.3–187.0,222.0) | Calculating cardinal orientation | Spot-check: banner / table header text |
| 87 | 0.662 | (34.3,223.0–46.7,234.3) | 65 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 88 | 0.741 | (58.3,223.3–75.0,234.7) | psx | Spot-check: banner / table header text |
| 89 | 0.857 | (265.0,223.0–294.0,233.7) | 19.949 | VERIFY: data (number or labeled field) |
| 90 | 0.831 | (321.7,222.7–347.3,233.3) | 0.000 | VERIFY: data (number or labeled field) |
| 91 | 0.874 | (368.0,222.7–401.7,233.0) | 180.051 | VERIFY: data (number or labeled field) |
| 92 | 0.858 | (412.7,223.3–446.7,232.7) | 200.000 | VERIFY: data (number or labeled field) |
| 93 | 0.666 | (34.0,234.7–46.7,245.7) | 66 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 94 | 0.728 | (57.3,233.7–75.7,246.7) | ysd | Spot-check: banner / table header text |
| 95 | 0.726 | (264.0,234.3–293.7,244.7) | 27.394 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 96 | 0.830 | (321.7,233.7–347.3,245.3) | 0.000 | VERIFY: data (number or labeled field) |
| 97 | 0.802 | (368.3,234.7–401.7,244.0) | 172.606 | VERIFY: data (number or labeled field) |
| 98 | 0.860 | (412.7,234.7–446.7,244.0) | 200.000 | VERIFY: data (number or labeled field) |
| 99 | 0.643 | (505.7,231.3–515.7,269.0) | XXX | VERIFY: low OCR confidence — confirm visually |
| 100 | 0.664 | (34.0,246.3–46.7,257.7) | 67 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 101 | 0.721 | (58.7,246.7–74.3,257.3) | psz | Spot-check: banner / table header text |
| 102 | 0.829 | (264.3,246.3–293.7,257.0) | 18.202 | VERIFY: data (number or labeled field) |
| 103 | 0.832 | (322.3,246.3–347.0,256.3) | 0.000 | VERIFY: data (number or labeled field) |
| 104 | 0.819 | (368.3,246.3–401.7,256.0) | 181.798 | VERIFY: data (number or labeled field) |
| 105 | 0.849 | (412.7,246.3–446.7,256.0) | 200.000 | VERIFY: data (number or labeled field) |
| 106 | 0.667 | (34.3,259.0–46.3,268.3) | 68 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 107 | 0.750 | (58.3,259.3–75.7,269.0) | exx | Spot-check: banner / table header text |
| 108 | 0.601 | (264.3,258.0–293.0,268.3) | 50.221 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 109 | 0.832 | (322.0,257.7–347.3,268.3) | 0.000 | VERIFY: data (number or labeled field) |
| 110 | 0.824 | (367.7,257.7–401.7,268.0) | 149.779 | VERIFY: data (number or labeled field) |
| 111 | 0.811 | (412.0,258.0–446.3,267.3) | 200.000 | VERIFY: data (number or labeled field) |
| 112 | 0.526 | (34.3,270.0–46.3,280.0) | 69 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 113 | 0.750 | (58.0,270.0–75.7,280.7) | exy | Spot-check: banner / table header text |
| 114 | 0.829 | (264.7,269.3–293.3,279.7) | 31.421 | VERIFY: data (number or labeled field) |
| 115 | 0.833 | (322.0,269.7–347.0,279.3) | 0.000 | VERIFY: data (number or labeled field) |
| 116 | 0.848 | (368.3,269.7–401.7,279.0) | 168.579 | VERIFY: data (number or labeled field) |
| 117 | 0.780 | (412.7,269.7–446.7,278.7) | 200.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 118 | 0.665 | (34.3,281.0–46.3,291.0) | 70 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 119 | 0.749 | (58.3,281.7–75.3,291.3) | exz | Spot-check: banner / table header text |
| 120 | 0.831 | (264.7,280.7–293.7,291.0) | 74.768 | VERIFY: data (number or labeled field) |
| 121 | 0.833 | (321.7,280.3–347.3,291.0) | 0.000 | VERIFY: data (number or labeled field) |
| 122 | 0.734 | (367.3,279.7–402.0,290.7) | 125.232 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 123 | 0.788 | (412.7,281.0–446.7,290.0) | 200.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 124 | 0.584 | (34.0,291.7–46.3,302.7) | 71 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 125 | 0.711 | (264.3,291.7–293.7,302.0) | 40.435 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 126 | 0.833 | (321.3,291.0–347.3,302.3) | 0.000 | VERIFY: data (number or labeled field) |
| 127 | 0.749 | (58.7,294.0–75.0,302.7) | eyx | Spot-check: banner / table header text |
| 128 | 0.857 | (368.3,292.3–401.7,301.7) | 159.565 | VERIFY: data (number or labeled field) |
| 129 | 0.801 | (412.7,292.3–446.7,301.3) | 200.000 | VERIFY: data (number or labeled field) |
| 130 | 0.659 | (34.0,303.0–46.7,314.0) | 72 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 131 | 0.743 | (58.0,304.3–75.3,315.7) | eyy | Spot-check: banner / table header text |
| 132 | 0.856 | (263.7,303.3–293.7,313.7) | 36.774 | VERIFY: data (number or labeled field) |
| 133 | 0.832 | (322.0,303.3–347.0,313.0) | 0.000 | VERIFY: data (number or labeled field) |
| 134 | 0.838 | (367.3,302.7–402.3,313.3) | 163.226 | VERIFY: data (number or labeled field) |
| 135 | 0.797 | (412.7,303.7–446.7,313.0) | 200.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 136 | 0.597 | (505.3,300.3–516.3,384.0) | xxixixixxx | VERIFY: low OCR confidence — confirm visually |
| 137 | 0.556 | (34.3,314.3–46.3,325.7) | 73 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 138 | 0.855 | (264.3,315.0–293.3,324.3) | 92.954 | VERIFY: data (number or labeled field) |
| 139 | 0.796 | (322.3,314.7–347.0,324.3) | 0.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 140 | 0.764 | (368.3,315.0–402.0,324.3) | 107.046 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 141 | 0.810 | (412.7,315.0–446.7,324.0) | 200.000 | VERIFY: data (number or labeled field) |
| 142 | 0.718 | (58.3,316.0–75.3,326.0) | eyz | VERIFY: low OCR confidence — confirm visually |
| 143 | 0.569 | (34.7,326.0–46.0,336.3) | 74 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 144 | 0.599 | (58.0,327.0–75.0,336.7) | ezx | VERIFY: low OCR confidence — confirm visually |
| 145 | 0.795 | (263.7,326.0–293.7,336.3) | 72.276 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 146 | 0.832 | (321.7,324.7–347.3,336.7) | 0.000 | VERIFY: data (number or labeled field) |
| 147 | 0.824 | (367.7,325.7–402.0,336.0) | 127.724 | VERIFY: data (number or labeled field) |
| 148 | 0.823 | (412.0,326.3–446.3,335.3) | 200.000 | VERIFY: data (number or labeled field) |
| 149 | 0.545 | (34.0,336.7–46.0,348.7) | 75 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 150 | 0.749 | (57.7,338.3–75.0,349.0) | ezy | Spot-check: banner / table header text |
| 151 | 0.711 | (264.0,337.3–293.7,348.0) | 82.064 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 152 | 0.833 | (322.0,337.7–347.0,347.7) | 0.000 | VERIFY: data (number or labeled field) |
| 153 | 0.823 | (367.0,337.0–402.0,348.3) | 117.936 | VERIFY: data (number or labeled field) |
| 154 | 0.751 | (412.3,337.7–446.7,347.3) | 200.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 155 | 0.666 | (34.0,349.3–46.0,359.3) | 76 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 156 | 0.625 | (57.7,349.3–74.7,360.0) | ezz | VERIFY: low OCR confidence — confirm visually |
| 157 | 0.735 | (264.0,349.0–293.7,359.3) | 48.554 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 158 | 0.833 | (321.7,349.0–347.3,359.7) | 0.000 | VERIFY: data (number or labeled field) |
| 159 | 0.608 | (367.0,348.3–402.3,359.7) | 151.446 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 160 | 0.759 | (412.7,349.7–446.7,359.0) | 200.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 161 | 0.776 | (58.0,359.7–95.3,372.3) | chisqr x | Spot-check: banner / table header text |
| 162 | 0.773 | (264.0,361.0–288.3,370.7) | 2.613 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 163 | 0.832 | (321.3,360.7–347.3,371.0) | 0.000 | VERIFY: data (number or labeled field) |
| 164 | 0.677 | (367.3,361.0–391.7,370.7) | 1.387 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 165 | 0.753 | (412.0,360.7–436.7,370.3) | 4.000 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |
| 166 | 0.654 | (33.7,371.3–46.3,382.3) | 78 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 167 | 0.848 | (58.0,371.0–95.3,384.0) | chisqry | Spot-check: banner / table header text |
| 168 | 0.833 | (262.7,371.0–288.3,382.7) | 2.071 | VERIFY: data (number or labeled field) |
| 169 | 0.832 | (321.3,372.0–347.3,382.3) | 0.000 | VERIFY: data (number or labeled field) |
| 170 | 0.715 | (367.0,371.7–392.0,382.3) | 1.929 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 171 | 0.805 | (412.3,372.3–436.7,382.0) | 4.000 | VERIFY: data (number or labeled field) |
| 172 | 0.611 | (33.0,382.3–46.3,393.7) | 79 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 173 | 0.818 | (57.3,382.7–94.7,395.0) | chisqr_ z | Spot-check: banner / table header text |
| 174 | 0.831 | (263.3,383.0–289.0,393.7) | 3.716 | VERIFY: data (number or labeled field) |
| 175 | 0.833 | (321.3,383.0–347.0,393.7) | 0.000 | VERIFY: data (number or labeled field) |
| 176 | 0.664 | (366.7,383.7–391.7,393.3) | 0.284 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 177 | 0.693 | (411.7,383.7–436.7,393.3) | 4.000 | VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually |
| 178 | 0.793 | (294.3,730.7–323.3,741.3) | Page 2 | VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text |

---

## 5. Flat reading-order text (for quick diff)

### Page 1

- **0.920** — Sandel MT102 Magnetic Transducer Accessory Calibration Report — *VERIFY: data (number or labeled field)*
- **0.808** — Serial Num: — *VERIFY: data (number or labeled field)*
- **0.799** — 1475 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.832** — 2.0.0.0 — *VERIFY: data (number or labeled field)*
- **0.887** — Calibration SW Ver: — *VERIFY: data (number or labeled field)*
- **0.902** — CalData File ver: — *VERIFY: data (number or labeled field)*
- **0.750** — 0.0 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.764** — Mag Sw Ver: — *VERIFY: data (number or labeled field)*
- **0.735** — 1.00 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.833** — Date: — *VERIFY: data (number or labeled field)*
- **0.853** — 03/03/16 10:43:38 — *VERIFY: data (number or labeled field)*
- **0.787** — Step — *VERIFY: data (number or labeled field)*
- **0.853** — Description — *VERIFY: data (number or labeled field)*
- **0.799** — Axis — *VERIFY: data (number or labeled field)*
- **0.838** — Offset — *VERIFY: data (number or labeled field)*
- **0.900** — ScaleFactor Desired — *VERIFY: data (number or labeled field)*
- **0.817** — Actual — *VERIFY: data (number or labeled field)*
- **0.888** — Tolerance Retries — *VERIFY: data (number or labeled field)*
- **0.724** — Pass — *VERIFY: data (number or labeled field)*
- **0.717** — Fail — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.824** — xxxix-xxxxxx — *Spot-check: banner / table header text*
- **0.881** — -9120.000 — *VERIFY: data (number or labeled field)*
- **0.775** — 4217.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.846** — -14596.00( — *VERIFY: data (number or labeled field)*
- **0.785** — Xm,XrYm, Yr.(Zm, — *Spot-check: banner / table header text*
- **0.817** — Xm, Yr),Ym,-Xr,Zm — *Spot-check: banner / table header text*
- **0.799** — 2792.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.751** — 8970.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.888** — -14735.00( — *VERIFY: data (number or labeled field)*
- **0.751** — (Xm,Xr),Ym,-Yr,(Zm, — *Spot-check: banner / table header text*
- **0.888** — 8688.000 — *VERIFY: data (number or labeled field)*
- **0.795** — -3796.00( — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.844** — -14324.00( — *VERIFY: data (number or labeled field)*
- **0.837** — (Xm,Yr,Ym, XrZm, — *Spot-check: banner / table header text*
- **0.890** — -3171.000 — *VERIFY: data (number or labeled field)*
- **0.748** — -8531.00( — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.840** — -14167.00( — *VERIFY: data (number or labeled field)*
- **0.666** — 10 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.815** — Xm, Xr,Ym,Yr, — *Spot-check: banner / table header text*
- **0.851** — -8984.000 — *VERIFY: data (number or labeled field)*
- **0.820** — -3094.000 — *VERIFY: data (number or labeled field)*
- **0.816** — 13247.000 — *VERIFY: data (number or labeled field)*
- **0.608** — 11 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.535** — 12 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.763** — (Xm, Yr,(Ym, Xr, — *Spot-check: banner / table header text*
- **0.886** — 3476.000 — *VERIFY: data (number or labeled field)*
- **0.728** — -9202.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.832** — 13621.000 — *VERIFY: data (number or labeled field)*
- **0.664** — 13 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.552** — 14 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.807** — (Xm-Xr, (Ym,Yr,f — *Spot-check: banner / table header text*
- **0.830** — 8199.000 — *VERIFY: data (number or labeled field)*
- **0.825** — 2952.000 — *VERIFY: data (number or labeled field)*
- **0.880** — 13177.000 — *VERIFY: data (number or labeled field)*
- **0.663** — 15 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.602** — 16 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.729** — (Xm,-Yr), (Ym,-Xr 1, ( — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.789** — -4261.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.753** — 9034.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.848** — 12865.000 — *VERIFY: data (number or labeled field)*
- **0.713** — xxxxxxx — *VERIFY: low OCR confidence — confirm visually*
- **0.664** — 17 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.555** — 18 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.799** — (Xm,XrYm,Zr — *Spot-check: banner / table header text*
- **0.860** — -8358.000 — *VERIFY: data (number or labeled field)*
- **0.886** — -13478.0 — *VERIFY: data (number or labeled field)*
- **0.848** — -3683.000 — *VERIFY: data (number or labeled field)*
- **0.656** — 19 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.666** — 20 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.778** — (Xm, Yr , f Ym, Zr), ( Zm — *Spot-check: banner / table header text*
- **0.838** — 3924.000 — *VERIFY: data (number or labeled field)*
- **0.798** — -14281.0( — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.870** — -8738.000 — *VERIFY: data (number or labeled field)*
- **0.502** — 21 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.599** — 22 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.822** — (Xm,-Xr ), f Ym, Zr 3, ( Zm, — *VERIFY: data (number or labeled field)*
- **0.719** — 9068.000 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.718** — -14598.0( — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.880** — 3468.000 — *VERIFY: data (number or labeled field)*
- **0.512** — xxxx — *VERIFY: low OCR confidence — confirm visually*
- **0.529** — 23 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.841** — (Xm,-Yr,  Ym, Zr , ( — *Spot-check: banner / table header text*
- **0.882** — -3144.000 — *VERIFY: data (number or labeled field)*
- **0.819** — -13840.00 — *VERIFY: data (number or labeled field)*
- **0.804** — 8698.000 — *VERIFY: data (number or labeled field)*
- **0.666** — 25 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.633** — 26 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.797** — ( Xm, Xr), (Ym,-Zr , ( Zm, — *Spot-check: banner / table header text*
- **0.827** — -9760.000 — *VERIFY: data (number or labeled field)*
- **0.791** — 14551.00 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.791** — 2393.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.612** — 27 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.884** — 7673.000 — *VERIFY: data (number or labeled field)*
- **0.815** — (Xm, Yr), (Ym,-Zr, ( — *Spot-check: banner / table header text*
- **0.749** — 2388.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.880** — 13930.001 — *VERIFY: data (number or labeled field)*
- **0.666** — 29 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.865** — 7692.000 — *VERIFY: data (number or labeled field)*
- **0.742** — 13725.001 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.857** — -4439.000 — *VERIFY: data (number or labeled field)*
- **0.641** — xxxx — *VERIFY: low OCR confidence — confirm visually*
- **0.666** — 30 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.741** — Xm-XrYm,-Zr, — *Spot-check: banner / table header text*
- **0.561** — 31 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.591** — 32 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.789** — (Xm-Yr,Ym,-Zr,(Zm, — *Spot-check: banner / table header text*
- **0.880** — -4390.000 — *VERIFY: data (number or labeled field)*
- **0.826** — 14343.00t — *VERIFY: data (number or labeled field)*
- **0.809** — -9876.000 — *VERIFY: data (number or labeled field)*
- **0.602** — 33 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.880** — 区区区区区区区区区区区区区区区区区区 — *VERIFY: OCR artifact / garbling — retype from scan*
- **0.665** — 34 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.804** — Xm,Zr,Ym,Yr, — *Spot-check: banner / table header text*
- **0.892** — -14329.000 — *VERIFY: data (number or labeled field)*
- **0.802** — 4200.000 — *VERIFY: data (number or labeled field)*
- **0.778** — 7794.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.508** — 35 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.589** — 36 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.781** — (Xm,Zr,Ym,-Xr — *Spot-check: banner / table header text*
- **0.847** — -14464.000 — *VERIFY: data (number or labeled field)*
- **0.821** — 9744.000 — *VERIFY: data (number or labeled field)*
- **0.880** — -4506.000 — *VERIFY: data (number or labeled field)*
- **0.516** — 37 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.667** — 38 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.758** — I Xm, Zr 1, I Ym,-Yr I, f Zm — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.814** — -13839.000 — *VERIFY: data (number or labeled field)*
- **0.820** — -2599.00( — *VERIFY: data (number or labeled field)*
- **0.859** — -9378.000 — *VERIFY: data (number or labeled field)*
- **0.667** — 39 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.523** — 40 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.799** — Xm,Zr,Ym,Xr,Zm, — *Spot-check: banner / table header text*
- **0.894** — -13644.000 — *VERIFY: data (number or labeled field)*
- **0.804** — -8126.000 — *VERIFY: data (number or labeled field)*
- **0.777** — 2964.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.808** — -9338.000 — *VERIFY: data (number or labeled field)*
- **0.519** — 42 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.861** — Xm,-Zr,(Ym,Yri,Zm, — *Spot-check: banner / table header text*
- **0.783** — 13357.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.866** — 2980.000 — *VERIFY: data (number or labeled field)*
- **0.627** — 44 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.813** — 13045.000 — *VERIFY: data (number or labeled field)*
- **0.877** — 8254.000 — *VERIFY: data (number or labeled field)*
- **0.823** — 2701.000 — *VERIFY: data (number or labeled field)*
- **0.793** — Xm,-Zr , ( Ym,-Xr1, ( Zm, — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.524** — 45 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.658** — 46 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.741** — ( Xm,-Zr l, ( Ym,-Yr I, t — *Spot-check: banner / table header text*
- **0.814** — 13780.000 — *VERIFY: data (number or labeled field)*
- **0.853** — -4306.000 — *VERIFY: data (number or labeled field)*
- **0.841** — 8313.000 — *VERIFY: data (number or labeled field)*
- **0.665** — 47 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.667** — 48 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.799** — Xm-ZrYm,Xr — *Spot-check: banner / table header text*
- **0.897** — 14021.000 — *VERIFY: data (number or labeled field)*
- **0.816** — -9516.00( — *VERIFY: data (number or labeled field)*
- **0.857** — -3759.000 — *VERIFY: data (number or labeled field)*
- **0.667** — 49 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.928** — Calculate and set offsets and — *VERIFY: data (number or labeled field)*
- **0.666** — 50 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.884** — Calculating Offsets... — *Spot-check: banner / table header text*
- **0.660** — 51 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.918** — and Scale Factors. — *VERIFY: data (number or labeled field)*
- **0.661** — Page I1 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*

### Page 2

- **0.908** — Sandel MT102 Magnetic Transducer Accessory Calibration Report — *VERIFY: data (number or labeled field)*
- **0.768** — Step — *VERIFY: data (number or labeled field)*
- **0.870** — Description — *VERIFY: data (number or labeled field)*
- **0.799** — Axis — *VERIFY: data (number or labeled field)*
- **0.820** — Offset — *VERIFY: data (number or labeled field)*
- **0.908** — ScaleFactor — *Spot-check: banner / table header text*
- **0.800** — Desired — *VERIFY: data (number or labeled field)*
- **0.856** — Actual — *VERIFY: data (number or labeled field)*
- **0.898** — Tolerance — *VERIFY: data (number or labeled field)*
- **0.867** — Retries — *VERIFY: data (number or labeled field)*
- **0.795** — Pass — *VERIFY: data (number or labeled field)*
- **0.797** — Fail — *VERIFY: data (number or labeled field)*
- **0.665** — 52 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.674** — 293 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.799** — 2207 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.681** — 2500 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.843** — Test Offset — *VERIFY: data (number or labeled field)*
- **0.661** — 53 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.831** — Test Offset — *VERIFY: data (number or labeled field)*
- **0.744** — -63 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.799** — 2437 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.744** — 2500 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.573** — 54 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.831** — Test Offset — *VERIFY: data (number or labeled field)*
- **0.610** — 609 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.741** — 1891 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.776** — 2500 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.605** — xxxxxxxxxx — *VERIFY: low OCR confidence — confirm visually*
- **0.664** — 55 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.524** — sxx — *VERIFY: low OCR confidence — confirm visually*
- **0.584** — xx — *VERIFY: low OCR confidence — confirm visually*
- **0.829** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.829** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.819** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.700** — 10.000 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.581** — 56 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.620** — sxy — *VERIFY: low OCR confidence — confirm visually*
- **0.633** — XY — *VERIFY: low OCR confidence — confirm visually*
- **0.856** — -4.973 — *VERIFY: data (number or labeled field)*
- **0.755** — 0.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.715** — 5.027 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.856** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.593** — 57 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.848** — -0.636 — *VERIFY: data (number or labeled field)*
- **0.750** — 0.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.756** — 9.364 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.857** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.555** — $xz — *VERIFY: low OCR confidence — confirm visually*
- **0.622** — 58 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.669** — syx — *VERIFY: low OCR confidence — confirm visually*
- **0.805** — -5.262 — *VERIFY: data (number or labeled field)*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.825** — 4.738 — *VERIFY: data (number or labeled field)*
- **0.816** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.664** — 59 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.775** — 2.043 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.764** — 0.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.833** — 7.957 — *VERIFY: data (number or labeled field)*
- **0.794** — 10.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.602** — syy — *VERIFY: low OCR confidence — confirm visually*
- **0.579** — 60 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.668** — syz — *VERIFY: low OCR confidence — confirm visually*
- **0.856** — -0.943 — *VERIFY: data (number or labeled field)*
- **0.831** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.762** — 9.057 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.857** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.665** — 61 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.672** — szx — *VERIFY: low OCR confidence — confirm visually*
- **0.832** — 0.894 — *VERIFY: data (number or labeled field)*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.682** — 9.106 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.850** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.510** — 62 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.627** — szy — *VERIFY: low OCR confidence — confirm visually*
- **0.520** — zy — *VERIFY: low OCR confidence — confirm visually*
- **0.803** — -3.434 — *VERIFY: data (number or labeled field)*
- **0.760** — 0.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.833** — 6.566 — *VERIFY: data (number or labeled field)*
- **0.810** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.667** — 63 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.765** — 0.189 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.747** — 9.811 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.853** — 10.000 — *VERIFY: data (number or labeled field)*
- **0.667** — 64 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.889** — Calculating cardinal orientation — *Spot-check: banner / table header text*
- **0.662** — 65 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.741** — psx — *Spot-check: banner / table header text*
- **0.857** — 19.949 — *VERIFY: data (number or labeled field)*
- **0.831** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.874** — 180.051 — *VERIFY: data (number or labeled field)*
- **0.858** — 200.000 — *VERIFY: data (number or labeled field)*
- **0.666** — 66 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.728** — ysd — *Spot-check: banner / table header text*
- **0.726** — 27.394 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.830** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.802** — 172.606 — *VERIFY: data (number or labeled field)*
- **0.860** — 200.000 — *VERIFY: data (number or labeled field)*
- **0.643** — XXX — *VERIFY: low OCR confidence — confirm visually*
- **0.664** — 67 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.721** — psz — *Spot-check: banner / table header text*
- **0.829** — 18.202 — *VERIFY: data (number or labeled field)*
- **0.832** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.819** — 181.798 — *VERIFY: data (number or labeled field)*
- **0.849** — 200.000 — *VERIFY: data (number or labeled field)*
- **0.667** — 68 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.750** — exx — *Spot-check: banner / table header text*
- **0.601** — 50.221 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.832** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.824** — 149.779 — *VERIFY: data (number or labeled field)*
- **0.811** — 200.000 — *VERIFY: data (number or labeled field)*
- **0.526** — 69 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.750** — exy — *Spot-check: banner / table header text*
- **0.829** — 31.421 — *VERIFY: data (number or labeled field)*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.848** — 168.579 — *VERIFY: data (number or labeled field)*
- **0.780** — 200.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.665** — 70 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.749** — exz — *Spot-check: banner / table header text*
- **0.831** — 74.768 — *VERIFY: data (number or labeled field)*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.734** — 125.232 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.788** — 200.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.584** — 71 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.711** — 40.435 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.749** — eyx — *Spot-check: banner / table header text*
- **0.857** — 159.565 — *VERIFY: data (number or labeled field)*
- **0.801** — 200.000 — *VERIFY: data (number or labeled field)*
- **0.659** — 72 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.743** — eyy — *Spot-check: banner / table header text*
- **0.856** — 36.774 — *VERIFY: data (number or labeled field)*
- **0.832** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.838** — 163.226 — *VERIFY: data (number or labeled field)*
- **0.797** — 200.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.597** — xxixixixxx — *VERIFY: low OCR confidence — confirm visually*
- **0.556** — 73 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.855** — 92.954 — *VERIFY: data (number or labeled field)*
- **0.796** — 0.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.764** — 107.046 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.810** — 200.000 — *VERIFY: data (number or labeled field)*
- **0.718** — eyz — *VERIFY: low OCR confidence — confirm visually*
- **0.569** — 74 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.599** — ezx — *VERIFY: low OCR confidence — confirm visually*
- **0.795** — 72.276 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.832** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.824** — 127.724 — *VERIFY: data (number or labeled field)*
- **0.823** — 200.000 — *VERIFY: data (number or labeled field)*
- **0.545** — 75 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.749** — ezy — *Spot-check: banner / table header text*
- **0.711** — 82.064 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.823** — 117.936 — *VERIFY: data (number or labeled field)*
- **0.751** — 200.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.666** — 76 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.625** — ezz — *VERIFY: low OCR confidence — confirm visually*
- **0.735** — 48.554 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.608** — 151.446 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.759** — 200.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.776** — chisqr x — *Spot-check: banner / table header text*
- **0.773** — 2.613 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.832** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.677** — 1.387 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.753** — 4.000 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*
- **0.654** — 78 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.848** — chisqry — *Spot-check: banner / table header text*
- **0.833** — 2.071 — *VERIFY: data (number or labeled field)*
- **0.832** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.715** — 1.929 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.805** — 4.000 — *VERIFY: data (number or labeled field)*
- **0.611** — 79 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.818** — chisqr_ z — *Spot-check: banner / table header text*
- **0.831** — 3.716 — *VERIFY: data (number or labeled field)*
- **0.833** — 0.000 — *VERIFY: data (number or labeled field)*
- **0.664** — 0.284 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.693** — 4.000 — *VERIFY: data (number or labeled field); VERIFY: low OCR confidence — confirm visually*
- **0.793** — Page 2 — *VERIFY: data (number or labeled field); VERIFY: medium OCR confidence on numeric text*

---

## 6. Technician checklist (reply template)

Please return **one** of: (a) marked-up scan/PDF, (b) a corrected searchable PDF from the cal system, or (c) a short table of corrections using keys **P{page}-S{seq}** from Section 4 above (example: `P1-S14`).

1. Confirm **instrument identity** (model, serial, any internal asset IDs).
2. Confirm **software / data file versions** and **date/time** of calibration (watch for merged date+time in OCR).
3. For **each table**: confirm column headers match the instrument printout; then confirm **every numeric value** and **Pass/Fail** outcomes.
4. Confirm any **signatures, approvals, standards, traceability**, and **environmental** notes present on the original but missing here.
5. If anything on the certificate was **handwritten**, flag it explicitly (OCR will be unreliable).

---

## 7. Flag counts (elements may have multiple tags)

| Tag type (substring match) | Approx. element hits |
|---|---:|
| data | 284 |
| low | 103 |
| art | 1 |
| mednum | 52 |
| spot | 36 |

*Note:* counts sum with multiplicity when one line has multiple tags.
