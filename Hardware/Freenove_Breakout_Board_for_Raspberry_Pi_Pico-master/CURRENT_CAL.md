every 5 %)
 Current Calibration (measurements )

**GPIO ↔ axis (DRV8871, default wiring)**

| GPIO | Axis |
|------|------|
| **GP10** (IN1 PWM) | **X** |
| **GP11** (IN2 low) | **X** |
| **GP12** (IN1 PWM) | **Y** |
| **GP13** (IN2 low) | **Y** |
| **GP14** (IN1 PWM) | **Z** |
| **GP15** (IN2 low) | **Z** |

Per axis: **X** = GP10+GP11 · **Y** = GP12+GP13 · **Z** = GP14+GP15

Setup:

a. using pico based coil_driver_app.py Version 3.4
b. Version 3 Driver HW (DRV8871) + RC circuit and INA3221 Sensor 
c. custom wound 2D helmholtz coil *37 turns of 23 gauge solid copper wire
d. FLUKE 15B+ DMM in series with the  + lead to coil (in mA scale)
e. Source supply 12V 5 Amp "Brick"

Proceedure used:

1. Using the CalibratorUI GUI connection to pico established over usb serial. 
2. for each "Target" mA the value was entered into the X Coil "spinner" Enable was checked and the Set button clicked.
3. observed actual current on DMM (let settle for 10 seconds) and recorded as Measured_ma
4.Rrecorded the reported (in GUI) Voltage

    Set_ma  Measured_ma     Reported_voltage
1.  1       1.67            0.1
2.  2       3.27            0.18
3.  3       4.78            0.27
4.  4       6.33            0.36
5.  5       7.42            0.42
6.  6       8.43            0.48
7.  7       9.36            0.53
8.  8       8.09            0.46
9.  9       9.00            0.51
10. 10      9.98            0.57
11. 11      10.92           0.62
12. 12      11.86           0.67
13. 13      12.81           0.72
14. 14      13.73           0.78
15. 15      14.65           0.82
16. 16      15.57           0.88
17. 17      16.46           0.93
18. 18      17.35           0.98
19. 19      18.26           1.03
20. 20      19.15           1.08
21. 21      20.07           1.14                     
22. 22      20.93           1.18
23. 23      21.81           1.23
24. 24      22.68           1.28
25. 25      23.55           1.33
26. 26      24.41           1.38
27. 27      25.24           1.42
28. 28      26.08           1.47
29. 29      4.59            0.26
30. 30      5.56            0.31
31. 31      6.55            0.37
32. 32      7.51            0.42
33. 33      8.49            0.48
34. 34      9.41            0.53
35. 35      10.39           0.58
36. 36      11.32           0.64
37. 37      12.23           0.69
38. 38      13.20           0.74
39. 39      14.13           0.80
40. 40      15.02           0.85
41. 41      15.96           0.90
42. 42      16.86           0.96
43. 43      17.73           1.00
44. 44      18.63           1.05
45. 45      19.54           1.10
46. 46      20.44           1.15
47. 47      21.28           1.20
48. 48      22.15           1.25
49. 49      23.01           1.30
50. 50      23.88           1.34
51. 51      24.73           1.39
52. 52      25.58           1.44
53. 53      26.41           1.49
54. 54      27.43           1.54
55. 55      28.06           1.58
56. 56      28.88           1.62
57. 57      28.87           1.62
58. 58      30.49           1.72
59. 59      31.29           1.76
60. 60      32.10           1.81
61. 61      32.89           1.85
62. 62      33.68           1.90
63. 63      34.46           1.94
64. 64      35.23           1.98
65. 65      36.01           2.02
66. 66      36.78           2.07
67. 67      37.55           2.11
68. 68      38.29           2.15
69. 69      39.04           2.20
70. 70      39.80           2.24



