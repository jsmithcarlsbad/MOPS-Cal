# Coil driver — Raspberry Pi Pico 2 W only (MicroPython)
# Hardware: COIL_DRIVER.md (OSOYOO Model Y + INA3221 + RC + 50 Ω return)

# --- I2C0 — INA3221 only (GP4/GP5) — separate from LCD ---
I2C_ID = 0
I2C_SDA = 4
I2C_SCL = 5
I2C_FREQ_HZ = 100_000
# INA3221 A0 pin: GND=0x40, VS=0x41, SDA=0x42, SCL=0x43 (TI Table 7-1)
INA3221_ADDRESS = 0x40
# Triple-channel board: **0.1 Ω** shunts (verify with DMM / BOM). If you change parts, update this.
# INA3221 shunt FS ≈ ±163 mV → linear I ≈ **163 mV / R_shunt** → ~**1.63 A** at 0.1 Ω (before other limits).
INA3221_SHUNT_OHMS = 0.1
# Multiply shunt-derived mA (all channels) after the I = V_shunt / R formula. Use when TM mA disagrees
# with a clamp/DMM (e.g. true 150 mA but TM ~2000 → scale = 150/2000 = 0.075). Default 1.0 = no change.
# Note: firmware 4.x reads INA without PWM phase sync; ripple can inflate shunt readings vs SPICE DC.
INA3221_CURRENT_SCALE = 1.0
# Map INA3221 channel index 0,1,2 → logical X,Y,Z (reorder if wiring differs)
INA3221_AXIS_ORDER = (0, 1, 2)
# --- GPIO ↔ axis (drv8871_3ch) — order is always X, Y, Z ---
#   Axis | IN1 (hardware PWM) | IN2 (GPIO held low)
#   X    | GP10               | GP11
#   Y    | GP12               | GP13
#   Z    | GP14               | GP15
# RP2040 PWM: slice = (GP >> 1) & 7, channel A/B = GP & 1 (even GP → ch A). Firmware derives slice/ch from IN1 pins for INA sync.
# 1 = align INA3221 shunt+bus reads to middle of PWM **off** time (quietest RC node); 0 = read immediately.
INA3221_BUS_V_SYNC_PWM = 1
# Busy-wait budget (µs) per axis before sampling anyway (~15 periods at 5 kHz ≈ 3 ms).
INA3221_BUS_V_SYNC_TIMEOUT_US = 3000
# Sample window half-width: max(1, off_ticks >> INA3221_BUS_V_SYNC_OFF_CENTER_SHIFT). Larger = looser timing.
INA3221_BUS_V_SYNC_OFF_CENTER_SHIFT = 4
# If slice runs phase-correct (CSR PH_CORRECT), off-window math is skipped; fall back to mid-period alignment.

# --- Freenove 2×16 I2C LCD (PCF8574) — I2C1 only; not shared with INA3221 ---
# Freenove’s Pico *demo* uses I2C0 on GP4/GP5; this project uses I2C1 on GP2/GP3 instead.
# MicroPython: I2C(1, sda=Pin(2), scl=Pin(3), …)  →  SDA = GP2,  SCL = GP3
LCD_I2C_ID = 1
LCD_I2C_SDA = 2
LCD_I2C_SCL = 3
# Same as Freenove Pico demo IIC_LCD1602.py: I2C(..., freq=400000)
LCD_I2C_FREQ_HZ = 400_000
# PCF8574 backpack: often 0x27 or 0x3F — run i2c.scan() on LCD_I2C_* if unsure
LCD_I2C_ADDR = 0x27
# Power-up / I2C retries if the panel shows a full row of blocks (uninitialized HD44780).
LCD_INIT_RETRIES = 4
# --- Coil power drivers (Pico GPIO) ---
# "drv8871_3ch" = three TI DRV8871 H-bridge modules (IN1/IN2 logic; VM 6.5–45 V). See TI SLVSCY9B.
# "mosfet_3ch" = three low-side MOSFET modules; one PWM each; no DIR.
# "model_y" = legacy OSOYOO Model Y (2× PT5126): PWM on EN + DIR pin pairs below.
COIL_DRIVER_HW = "drv8871_3ch"

# Host log / hw_report title (set appropriately for COIL_DRIVER_HW).
H_BRIDGE_MODEL = "3× TI DRV8871"
PT5126_COUNT = 0  # unused for drv8871_3ch / mosfet_3ch; legacy Model Y used 2

# drv8871_3ch: IN1 = **RP2040 hardware PWM** only; IN2 held low (unidirectional coil + coast between pulses).
# Match your breakout labels to TI IN1/IN2. PWM period should keep both inputs low < ~1 ms (sleep).
DRV8871_IN1_PWM_PINS = (10, 12, 14)  # X, Y, Z → module IN1
DRV8871_IN2_PINS = (11, 13, 15)  # X, Y, Z → module IN2 (held 0)

# mosfet_3ch / model_y PWM pins (ignored when COIL_DRIVER_HW == "drv8871_3ch"):
PWM_EN_PINS = (10, 12, 14)

# Legacy Model Y only — ignored when COIL_DRIVER_HW == "mosfet_3ch" (pins not driven).
DIR_PINS_X = (6, 7)
DIR_PINS_Y = (8, 9)
DIR_PINS_Z = (11, 13)

# Engineer RC target: **~83 Hz** cutoff (e.g. 20 Ω + 100 µF → fc ≈ 80 Hz). Use **5 kHz** PWM so ripple is
# well above fc → quasi-DC average at the coil for INA3221 / control (not audio-frequency PWM).
PWM_FREQ_HZ = 5000

# Host serial set_x_v / set_y_v / set_z_v (V): open-loop average coil command. Firmware duty ≈ set_v / ref (clamped).
COIL_VOLTAGE_REF_VM_V = 12.0
# Hard clamp on commanded set_v (0 … this). Keep ≤ your DRV8871 VM.
COIL_VOLTAGE_COMMAND_MAX_V = 45.0

# Idle supply check: when not SAFE and all setpoints 0, at SUPPLY_SENSE_RATE_HZ (default 10 Hz) drive each axis
# IN1 at 100 % (steady DC on), read that INA3221 channel (bus V + shunt I) with no PWM off-window wait, then drive off.
# X, Y, Z sequenced once per cycle for clean brick voltage on TM:: coil_V_* / GUI.
SUPPLY_SENSE_ENABLE = 1
SUPPLY_SENSE_RATE_HZ = 10.0
SUPPLY_SENSE_INTERVAL_MS = 100  # used only when SUPPLY_SENSE_RATE_HZ <= 0
SUPPLY_SENSE_SETTLE_US = 50  # optional delay after DC-on before I2C sample (RC node); 0 = sample immediately after on

# --- Host slave (firmware 5.x voltage command) ---
# TM:: to PC: set desired rate here (firmware clamps 0.5–30 Hz). Each line is IIR-smoothed INA3221 mA / bus V.
SLAVE_TM_HZ = 10.0
# Virtual timer tick (ms): back-button hold poll + fast INA3221 snapshot cadence (see below).
SLAVE_POLL_MS = 50
# Minimum ms between full 3-channel INA3221 I2C reads (fast sampling → software filter → smooth TM::).
INA3221_SAMPLE_MIN_MS = 20
# Exponential moving average α per snapshot (0..1). Lower = smoother / slower step response; 1 = no filter.
INA3221_FILTER_ALPHA = 0.18

# --- Control (legacy 3.x; unused when running 4.x slave firmware) ---
# INA3221: only the control timer at this rate performs I2C shunt/bus reads; TM:: and PI consume that stream
# (sum/count mean per ch per TELEM window). No other task reads the INA3221 on the wire.
LOOP_HZ = 50
P_GAIN = 0.02
I_GAIN = 0.05
MAX_CURRENT_PER_COIL_MA = 500.0
# 1 = base duty ≈ target/limit (recommended); 0 = PI-only (easy to over-command duty at low targets).
CONTROL_FEEDFORWARD = 1
# After PI, cap duty to at most (target/limit)*(1+PI_DUTY_HEADROOM) to prevent runaway toward 100% PWM.
# Set -1 to disable the cap (not recommended).
PI_DUTY_HEADROOM = 0.35
# Soft-start: after setpoint goes 0→>0, ramp over PWM_RAMP_MS (ms). End of ramp reaches only this
# fraction of nominal duty (target/limit); PI brings current the rest of the way (slow, low inrush).
PWM_RAMP_MS = 3000
PWM_RAMP_TO_TARGET_FRAC = 0.3
# 1 = ease-in (duty ∝ t²): slower at the start of the ramp; 0 = linear in time.
PWM_RAMP_EASE_IN = 1
# Exit ramp early when |I - target| <= max(RAMP_EXIT_MA_ABS, RAMP_EXIT_FRAC * target) for RAMP_STABLE_SAMPLES cycles.
# 0 = never exit early (always run full PWM_RAMP_MS) — safest before PI takes over.
RAMP_EXIT_MA_ABS = 1.0
RAMP_EXIT_FRAC = 0.15
RAMP_STABLE_SAMPLES = 0
# After duty ramp: hold PWM fixed and wait until INA current is "DC-like" (small step-to-step change),
# then enable PI. Skipped if INA missing or RAMP_SETTLE_DC_ENABLE=0.
RAMP_SETTLE_DC_ENABLE = 1
SETTLE_MIN_MS = 200
SETTLE_MAX_MS = 12000
DC_STABLE_DELTA_MA = 3.0
DC_STABLE_SAMPLES = 12

# INA3221 rolling window: sum/count reset every TELEM_HZ^-1 ms (e.g. 10 Hz -> 100 ms). Closed-loop PI and TM:: to
# the host both use this same window mean (_ina_avg_sum_* / _ina_avg_n); TM is every LOOP_HZ tick, values not raw INA.
TELEM_HZ = 10.0
SERIAL_BAUD = 115200  # USB CDC; baud ignored on native USB, kept for docs

# LCD refresh cadence when idle/slave (HD44780); unrelated to TM:: rate.
LCD_REFRESH_MS = 100
# At boot: clear LCD, show 3DHC-Calibrator + VER line (centered), then hold this many seconds before normal screens.
BOOT_LCD_SPLASH_S = 5.0
# C=1 if host sent a serial line within this window (ms)
HOST_LINK_TIMEOUT_MS = 5000

# Back button: NO to GND, pull-up. Down at boot (after debounce) or held >= BACK_BUTTON_DEBOUNCE_MS → deploy-ready
# (READY FOR / DEPLOYMENT), same as host_disconnect. 0 = disabled. Avoid GP used by estop / PWM / I2C.
BACK_BUTTON_GP = 17
# Legacy name only (not used for timing); deploy timing uses BACK_BUTTON_DEBOUNCE_MS.
BACK_BUTTON_LONG_PRESS_MS = 3000
BACK_BUTTON_DEBOUNCE_MS = 80

# NO switch to GND = latched SAFE (same as host `safe`): internal pull-up, IRQ → PWM off until safe_reset.
# 0 = disabled. Default GP16 avoids DRV8871 (10–15) and I2C (2–3, 4–5).
HARDWARE_ESTOP_GP = 16
HARDWARE_ESTOP_DEBOUNCE_MS = 80
