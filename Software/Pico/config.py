# Coil driver — Raspberry Pi Pico W (MicroPython)
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
# Map INA3221 channel index 0,1,2 → logical X,Y,Z (reorder if wiring differs)
INA3221_AXIS_ORDER = (0, 1, 2)

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
# --- OSOYOO Model Y — GPIO (Pico) wiring; edit to match your harness ---
# Two PT5126 bridge ICs on the board — no I2C to Pico; firmware only sets PWM + DIR below.
H_BRIDGE_MODEL = "OSOYOO Model Y"
PT5126_COUNT = 2
# Per axis: one PWM on EN (speed) + two direction pins (forward fixed per COIL_DRIVER.md).
# Example mapping (OSOYOO “forward”): IN1=1 IN2=0, IN3=1 IN4=0, etc.
# High-side / unipolar drive: one bridge output per axis → one wire to RC/coil (return to GND).
# Board silkscreen shows two posts per output (e.g. AK1 and AK2) tied to the SAME net — use ONE terminal per axis.
# X = A ENA → AK1 or AK2 (either). Y = A ENB → AK3 or AK4. Z = B ENA → BK1 or BK2.
PWM_EN_PINS = (10, 12, 14)  # A_ENA, A_ENB, B_ENA
# Direction pins: (IN1, IN2), (IN3, IN4), (B_IN1, B_IN2) — two pins per axis
DIR_PINS_X = (6, 7)   # A IN1, A IN2
DIR_PINS_Y = (8, 9)   # A IN3, A IN4
DIR_PINS_Z = (11, 13)  # B IN1, B IN2

# Engineer RC target: **~83 Hz** cutoff (e.g. 20 Ω + 100 µF → fc ≈ 80 Hz). Use **5 kHz** PWM so ripple is
# well above fc → quasi-DC average at the coil for INA3221 / control (not audio-frequency PWM).
PWM_FREQ_HZ = 5000

# --- Control ---
LOOP_HZ = 50
P_GAIN = 0.02
I_GAIN = 0.05
MAX_CURRENT_PER_COIL_MA = 500.0
# 1 = base duty ≈ target/limit (recommended); 0 = PI-only (easy to over-command duty at low targets).
CONTROL_FEEDFORWARD = 1
# After PI, cap duty to at most (target/limit)*(1+PI_DUTY_HEADROOM) to prevent runaway toward 100% PWM.
# Set -1 to disable the cap (not recommended).
PI_DUTY_HEADROOM = 0.35
# Ignore overcurrent→SAFE until this many ms after boot (INA/converters settle; avoids false SAFE).
OVERCURRENT_ARM_MS = 800
# Require this many consecutive control cycles (50 Hz → 20 ms each) over limit before SAFE.
# 3 ≈ 60 ms sustained overcurrent; reduces trips from single-sample INA spikes.
OVERCURRENT_CONFIRM_SAMPLES = 3
# If last cycle's PWM duty < OC_LOW_DUTY_U_THRESH, do not trip on I just above alarm_limit
# (INA can read high vs low EN duty on some bridges). Trip only if I > limit*(1+OC_LOW_DUTY_LIMIT_RELAX).
# Set OC_LOW_DUTY_IGNORE=0 for strict limit-only behavior.
OC_LOW_DUTY_IGNORE = 1
OC_LOW_DUTY_U_THRESH = 0.35
OC_LOW_DUTY_LIMIT_RELAX = 1.0
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

TELEM_HZ = 10.0
SERIAL_BAUD = 115200  # USB CDC; baud ignored on native USB, kept for docs

# LCD: line 1 status + line 2 mA. Minimum ms between paints (slower is fine). Values < 100 are clamped to 100 (10 Hz max).
LCD_REFRESH_MS = 100
# C=1 if host sent a serial line within this window (ms)
HOST_LINK_TIMEOUT_MS = 5000
