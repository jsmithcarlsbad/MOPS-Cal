#!/usr/bin/env python3
"""
Equivalent path (per your sketch): 12 V, R1=20 Ω, ideal switch closed (first-enable),
node B: C1||C2 to GND, then shunt R_s, coil L, R_coil to GND.

ODEs when S1 is ON (single rising edge, held on for this demo):
  V1 - R1 * (C * dV/dt + i) = V
  V = R_s * i + L * di/dt + R_coil * i   =>  di/dt = (V - (R_s + R_coil)*i) / L  [lumping L with series R for state i = coil+shunt branch current]

From first equation:
  dV/dt = (V1 - R1*i - V) / (R1 * C)

Units: V, A, s. Pure stdlib — no numpy.

This illustrates why the INA shunt can see a large *transient* when the 100 µF charges,
even when steady-state "variable DC" at the coil is small — firmware ramp reduces the
*rate* of charge (lower duty envelope), it does not change the RC physics.
"""

import math

# --- Schematic values (edit to match your build) ---
V1 = 12.0
R1 = 20.0
C = 100e-6 + 100e-9  # 100 uF || 100 nF
R_s = 0.1  # shunt (INA sense)
R_coil = 51.0
L = 5e-3  # H — placeholder if unknown; try 1–20 mH for air-core Helmholtz-scale

# fc of RC alone (node to GND through R1 from Thevenin — not exact for full net):
fc_rc = 1.0 / (2 * math.pi * R1 * C)
print("Design check: RC pole (R1*C order) fc ~ %.1f Hz (83 Hz class is expected)" % fc_rc)

T_END = 0.010  # 10 ms
DT = 1e-7
# Initial: V=0 on cap, i=0 in inductor
V = 0.0
i = 0.0
imax = 0.0
tmax = 0.0
steps = int(T_END / DT)

for n in range(steps):
    dV = (V1 - R1 * i - V) / (R1 * C)
    di = (V - (R_s + R_coil) * i) / L
    V += dV * DT
    i += di * DT
    a = abs(i)
    if a > imax:
        imax = a
        tmax = n * DT

print("First-enable (switch held ON, ideal): |I_shunt| max ~ %.2f mA at t ~ %.3f ms" % (imax * 1000, tmax * 1000))
print("  (Transient can exceed steady-state mA from quasi-DC average until cap charges.)")
