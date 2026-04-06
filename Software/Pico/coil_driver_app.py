# coil_driver_app.py — Helmholtz coil driver (MOSFET 3ch or Model Y + INA3221 + RC + Pico W)
# See COIL_DRIVER.md. Deploy as main.py on device or copy main.py + this package to Pico.

import sys
import time
import micropython
import machine
from machine import I2C, Pin, PWM, Timer

import config

# Firmware version (single source of truth). Bump MAJOR for large / incompatible changes;
# bump MINOR for bug fixes and small additions.
VERSION_MAJOR = 3
VERSION_MINOR = 21
VERSION = "%d.%d" % (VERSION_MAJOR, VERSION_MINOR)


def host_print(*args):
    """Host UI log line (prefix TXT::). Use instead of print() for user-visible text."""
    print("TXT:: " + " ".join(str(a) for a in args))


def _scheduled_tm_line(arg):
    """Print TM:: in main context. Timer ISR must not print — USB CDC interleaves with TXT:: from main."""
    global _host_txt_burst_active
    if _host_txt_burst_active:
        return
    try:
        print(arg)
    except Exception:
        pass


def _scheduled_tm_err(arg):
    global _host_txt_burst_active
    if _host_txt_burst_active:
        return
    try:
        host_print("STATUS TM_ERR", arg)
    except Exception:
        pass


# --- Hardware handles ---
i2c = None
mon = None
pwms = []
# RP2040 PWM slice (0..7) and channel (0=A, 1=B) per axis for INA off-window sync; set in _init_hardware from IN1 GPIO.
_pwm_slice_for_axis = (-1, -1, -1)
_pwm_cc_chan_per_axis = (0, 0, 0)
# DRV8871: IN2 GPIO per axis (IN1 uses hardware PWM in pwms); unused for other COIL_DRIVER_HW.
_drv8871_in2_pins = [None, None, None]
lcd = None
# PCF8574 address actually opened (for host boot log); None if LCD missing.
lcd_i2c_addr_used = None
# One I2C object per hardware block — creating I2C(1,…) twice (init + hw_report) breaks the LCD driver.
_lcd_bus_instance = None

# True while _report_hardware_to_host runs: scheduled TM:: must not print (still interleaves with TXT:: on USB).
_host_txt_burst_active = False

def _axis_order():
    return tuple(getattr(config, "INA3221_AXIS_ORDER", (0, 1, 2)))


def _axis_index_for_ina_ch(ina_ch: int) -> int:
    """Coil axis index 0..2 (X..Z) that drives the PWM aligned with INA channel ina_ch."""
    order = _axis_order()
    for ax in range(3):
        if int(order[ax]) == int(ina_ch):
            return ax
    return 0


def _init_hardware():
    global i2c, mon, pwms, _drv8871_in2_pins, _pwm_slice_for_axis, _pwm_cc_chan_per_axis
    i2c = None
    mon = None
    pwms = []
    _drv8871_in2_pins = [None, None, None]
    _pwm_slice_for_axis = (-1, -1, -1)
    _pwm_cc_chan_per_axis = (0, 0, 0)
    try:
        i2c = I2C(
            int(getattr(config, "I2C_ID", 0)),
            sda=Pin(int(getattr(config, "I2C_SDA", 4))),
            scl=Pin(int(getattr(config, "I2C_SCL", 5))),
            freq=int(getattr(config, "I2C_FREQ_HZ", 100_000)),
        )
        addr = int(getattr(config, "INA3221_ADDRESS", 0x40))
        if addr in i2c.scan():
            try:
                from ina3221 import INA3221
            except ImportError:
                host_print("STATUS ina3221.py missing; INA3221 disabled")
            else:
                try:
                    rsh = float(getattr(config, "INA3221_SHUNT_OHMS", 0.1))
                    mon = INA3221(i2c, addr, rsh)
                except Exception as e:
                    host_print("STATUS INA3221 init ERR:", e)
    except Exception:
        i2c = None
        mon = None

    hw = str(getattr(config, "COIL_DRIVER_HW", "model_y"))
    if hw == "model_y":
        # Model Y: fixed "forward" direction per OSOYOO tables
        for pair in (
            getattr(config, "DIR_PINS_X", (6, 7)),
            getattr(config, "DIR_PINS_Y", (8, 9)),
            getattr(config, "DIR_PINS_Z", (11, 13)),
        ):
            try:
                Pin(pair[0], Pin.OUT).value(1)
                Pin(pair[1], Pin.OUT).value(0)
            except Exception:
                pass

    pwm_hz = int(getattr(config, "PWM_FREQ_HZ", 20_000))
    if hw == "drv8871_3ch":
        in1 = getattr(config, "DRV8871_IN1_PWM_PINS", (10, 12, 14))
        in2 = getattr(config, "DRV8871_IN2_PINS", (11, 13, 15))
        for i in range(3):
            try:
                g2 = int(in2[i])
                p2 = Pin(g2, Pin.OUT)
                p2.value(0)
                _drv8871_in2_pins[i] = p2
            except Exception:
                pass
        for pin_num in in1:
            try:
                p = PWM(Pin(int(pin_num)))
                p.freq(pwm_hz)
                p.duty_u16(0)
                pwms.append(p)
            except Exception:
                pwms.append(None)
    else:
        for pin_num in getattr(config, "PWM_EN_PINS", (10, 12, 14)):
            try:
                p = PWM(Pin(pin_num))
                p.freq(pwm_hz)
                p.duty_u16(0)
                pwms.append(p)
            except Exception:
                pwms.append(None)
    while len(pwms) < 3:
        pwms.append(None)

    # RP2040: slice = (GPIO >> 1) & 7, channel A/B = GPIO & 1 (0=A, 1=B). Matches MicroPython PWM routing.
    if hw == "drv8871_3ch":
        pin_list = list(getattr(config, "DRV8871_IN1_PWM_PINS", (10, 12, 14)))
    else:
        pin_list = list(getattr(config, "PWM_EN_PINS", (10, 12, 14)))
    sl = [-1, -1, -1]
    cc = [0, 0, 0]
    for i in range(3):
        try:
            g = int(pin_list[i])
            sl[i] = (g >> 1) & 7
            cc[i] = g & 1
        except Exception:
            pass
    _pwm_slice_for_axis = (sl[0], sl[1], sl[2])
    _pwm_cc_chan_per_axis = (cc[0], cc[1], cc[2])


def _pwm_ctr_ring_dist(ctr, target, period):
    """Circular distance between counter and target on 0..period-1."""
    d = ctr - target
    if d < 0:
        d = -d
    half = period >> 1
    if d > half:
        d = period - d
    return d


def _pwm_sync_wait_period_mid_slice(sn, timeout_us, sh):
    """Fallback when slice CSR.PH_CORRECT=1: align to middle of full period (off is split on up/down ramp)."""
    if sn < 0 or sn > 7:
        return
    base = 0x40050000 + sn * 0x14
    t0 = time.ticks_us()
    sh = max(1, min(8, sh))
    while time.ticks_diff(time.ticks_us(), t0) < timeout_us:
        try:
            top = machine.mem32[base + 0x10] & 0xFFFF
            ctr = machine.mem32[base + 8] & 0xFFFF
        except Exception:
            return
        if top < 8:
            top = 65535
        period = top + 1
        mid = top >> 1
        w = max(1, period >> sh)
        if _pwm_ctr_ring_dist(ctr, mid, period) <= w:
            return


def _wait_ina3221_pwm_off_center(axis_idx: int) -> None:
    """Align INA sample near the middle of PWM **off** time (DRV8871 IN1 low, quiet RC).

    RP2040 non–phase-correct: MicroPython sets CC so output is high while counter < CC (before CSR invert).
    Off interval is the complementary part of 0..TOP. ~100% duty (no off) → return immediately.
    Phase-correct slices fall back to mid-period (single stable window).
    """
    if sys.platform != "rp2":
        return
    if not int(getattr(config, "INA3221_BUS_V_SYNC_PWM", 1)):
        return
    if mon is None or axis_idx < 0 or axis_idx > 2:
        return
    sn = _pwm_slice_for_axis[axis_idx]
    if sn < 0 or sn > 7:
        return
    if axis_idx >= len(pwms) or pwms[axis_idx] is None:
        return

    timeout_us = int(getattr(config, "INA3221_BUS_V_SYNC_TIMEOUT_US", 3000))
    sh = int(getattr(config, "INA3221_BUS_V_SYNC_OFF_CENTER_SHIFT", 4))
    sh = max(1, min(8, sh))
    base = 0x40050000 + sn * 0x14

    try:
        csr = machine.mem32[base + 0x00]
    except Exception:
        return

    if csr & (1 << 3):
        _pwm_sync_wait_period_mid_slice(sn, timeout_us, sh)
        return

    try:
        ch = int(_pwm_cc_chan_per_axis[axis_idx]) & 1
        cc_word = machine.mem32[base + 0x0C]
        cc = cc_word & 0xFFFF if ch == 0 else (cc_word >> 16) & 0xFFFF
        top = machine.mem32[base + 0x10] & 0xFFFF
    except Exception:
        return

    if top < 8:
        top = 65535
    period = top + 1
    if period < 2:
        return

    inv = bool((csr >> (4 + ch)) & 1)

    if not inv:
        if cc >= period:
            return
        if cc == 0:
            off_len = period
            target = off_len >> 1
        else:
            off_len = period - cc
            target = cc + (off_len >> 1)
    else:
        if cc == 0:
            return
        if cc >= period:
            off_len = period
            target = off_len >> 1
        else:
            off_len = cc
            target = (cc - 1) >> 1

    w = max(1, off_len >> sh)
    t0 = time.ticks_us()
    while time.ticks_diff(time.ticks_us(), t0) < timeout_us:
        try:
            ctr = machine.mem32[base + 8] & 0xFFFF
        except Exception:
            return
        if _pwm_ctr_ring_dist(ctr, target, period) <= w:
            return


def _lcd_i2c_bus():
    """LCD bus from config.LCD_I2C_* (e.g. I2C1, SDA=GP2, SCL=GP3); else shared `i2c` if same pins as INA3221."""
    global _lcd_bus_instance
    lid = int(getattr(config, "LCD_I2C_ID", 0))
    sid = int(getattr(config, "I2C_ID", 0))
    lsda = int(getattr(config, "LCD_I2C_SDA", 4))
    lscl = int(getattr(config, "LCD_I2C_SCL", 5))
    ssda = int(getattr(config, "I2C_SDA", 4))
    sscl = int(getattr(config, "I2C_SCL", 5))
    freq_lcd = int(getattr(config, "LCD_I2C_FREQ_HZ", 100_000))
    if lid == sid and lsda == ssda and lscl == sscl:
        if i2c is not None:
            return i2c
        # INA3221 I2C failed but LCD shares same pins — still create a bus for the display.
        if _lcd_bus_instance is not None:
            return _lcd_bus_instance
        try:
            _lcd_bus_instance = I2C(lid, sda=Pin(lsda), scl=Pin(lscl), freq=freq_lcd)
            return _lcd_bus_instance
        except Exception:
            return None
    if _lcd_bus_instance is not None:
        return _lcd_bus_instance
    try:
        _lcd_bus_instance = I2C(lid, sda=Pin(lsda), scl=Pin(lscl), freq=freq_lcd)
        return _lcd_bus_instance
    except Exception:
        return None


def _init_lcd():
    """Freenove 2×16 I2C (config.LCD_I2C_*). Full top row of blocks = powered but no I2C init (wrong pins/addr)."""
    global lcd, lcd_i2c_addr_used
    lcd = None
    lcd_i2c_addr_used = None
    try:
        from I2C_LCD import I2CLcd

        retries = int(getattr(config, "LCD_INIT_RETRIES", 4))
        want = int(getattr(config, "LCD_I2C_ADDR", 0x27))

        for attempt in range(max(1, retries)):
            bus = _lcd_i2c_bus()
            if bus is None:
                host_print("STATUS LCD no I2C bus (fix LCD_* pins or INA I2C)")
                return
            time.sleep_ms(50)
            found = bus.scan()
            host_print("STATUS LCD scan", [hex(x) for x in found], "try", attempt + 1)
            # PCF8574 LCD backpack is 0x27 or 0x3F — never treat INA3221 (0x40) as the display.
            lcd_addrs = [a for a in found if a in (0x27, 0x3F)]
            if want in lcd_addrs:
                addr = want
            elif lcd_addrs:
                addr = lcd_addrs[0]
            else:
                time.sleep_ms(150)
                continue
            try:
                lcd = I2CLcd(bus, addr, 2, 16)
                lcd_i2c_addr_used = addr
                return
            except Exception as e:
                lcd = None
                host_print("STATUS LCD I2CLcd try ERR:", e)
                time.sleep_ms(150)
        host_print("STATUS LCD failed: no PCF8574 at 0x27/0x3F after retries (SDA/SCL, address jumpers)")
    except Exception as e:
        lcd = None
        host_print("STATUS LCD init ERR:", e)


# --- Control state ---
LOOP_HZ = int(getattr(config, "LOOP_HZ", 50))
dt = 1.0 / max(1, LOOP_HZ)
P_GAIN = float(getattr(config, "P_GAIN", 0.02))
I_GAIN = float(getattr(config, "I_GAIN", 0.05))
CONTROL_FEEDFORWARD = int(getattr(config, "CONTROL_FEEDFORWARD", 0))
MAX_MA_DEFAULT = float(getattr(config, "MAX_CURRENT_PER_COIL_MA", 500.0))

set_X_ma = 0.0
set_Y_ma = 0.0
set_Z_ma = 0.0

manual_pwm_duty = [None, None, None]
# Last commanded duty 0..1 per axis (overcurrent soft-gate, telemetry).
_last_u_cmd = [0.0, 0.0, 0.0]
_duty_integral = [0.0, 0.0, 0.0]
# Soft-start ramp (0→target): per-axis, after setpoint 0→>0.
_ramp_active = [False, False, False]
_ramp_t0_ms = [0, 0, 0]
_ramp_stable_count = [0, 0, 0]
_prev_target_ma = [0.0, 0.0, 0.0]
# After duty ramp: hold u fixed until INA current is step-to-step stable, then PI (see RAMP_SETTLE_DC_*).
_settle_active = [False, False, False]
_settle_t0_ms = [0, 0, 0]
_u_hold = [0.0, 0.0, 0.0]
_prev_I_ma = [0.0, 0.0, 0.0]
_dc_settle_count = [0, 0, 0]
# Consecutive over-limit samples per axis (see OVERCURRENT_CONFIRM_SAMPLES).
_oc_confirm = [0, 0, 0]
_alarm_latched = False
_last_telem_ms = 0
TELEM_PERIOD_MS = max(
    50,
    int(1000 / max(1, min(50, float(getattr(config, "TELEM_HZ", 10.0))))),
)

PWM_RESOLUTION = 4095

_last_lcd_ms = 0
_last_host_rx_ms = None
_host_set_ma_ack = False
_lcd_was_slave_mode = False
_safe_state = False
_estop_pin = None
_estop_button_held = False
_estop_last_press_ms = None
_estop_last_release_ms = None

_init_hardware()

# Overcurrent boot window — set in main() after _init_lcd() (LCD init must not run at import time).
_BOOT_TICKS_MS = None
_lcd_write_err_logged = False
_lcd_refresh_err_logged = False


def _lcd_center_16(text):
    """Pad to 16 columns, centered (HD44780 16×2)."""
    s = (text or "")[:16]
    L = len(s)
    if L >= 16:
        return s
    pad = 16 - L
    left = pad // 2
    return (" " * left) + s + (" " * (pad - left))


def _lcd_put_row(row, text):
    """16 columns, fixed width."""
    global _lcd_write_err_logged, lcd
    if lcd is None:
        return
    s = (text + "                ")[:16]
    try:
        lcd.move_to(0, row)
        lcd.putstr(s)
    except Exception as e:
        if not _lcd_write_err_logged:
            _lcd_write_err_logged = True
            host_print("STATUS LCD write ERR:", e)


def _lcd_seg_ma(actual_ma, limit_ma, target_ma, measured_ok):
    """One field: mA:NN, mA:!! (over-range), mA:-- (not measured)."""
    if not measured_ok:
        return "mA:--"
    if target_ma > 1e-6 and actual_ma > limit_ma + 1e-3:
        return "mA:!!"
    v = int(min(99, abs(round(actual_ma))))
    return "mA:%02d" % v


def _lcd_slave_mode():
    """Host GUI link active → SLAVED + mA; else READY FOR / DEPLOYMENT (centered)."""
    now = time.ticks_ms()
    tmo = int(getattr(config, "HOST_LINK_TIMEOUT_MS", 5000))
    return _last_host_rx_ms is not None and time.ticks_diff(now, _last_host_rx_ms) < tmo


def _lcd_clear():
    global lcd
    if lcd is None:
        return
    try:
        lcd.clear()
    except Exception:
        pass


def _lcd_line2_ma():
    """X Y Z measured mA fields, 5 chars each, 15 total."""
    measured_ok = mon is not None
    x_m, y_m, z_m = 0.0, 0.0, 0.0
    if measured_ok:
        try:
            x_m, y_m, z_m = read_currents_ma_ordered_xyz()
        except Exception:
            measured_ok = False
    tgt = (max(0.0, set_X_ma), max(0.0, set_Y_ma), max(0.0, set_Z_ma))
    a = (x_m, y_m, z_m)
    parts = []
    for i in range(3):
        parts.append(_lcd_seg_ma(a[i], MAX_MA_DEFAULT, tgt[i], measured_ok))
    return "".join(parts)[:16]


def _lcd_refresh_period_ms():
    """Minimum interval between LCD paints. Cap at 10 Hz: faster is pointless for HD44780 and adds I2C / main-loop load."""
    return max(100, int(getattr(config, "LCD_REFRESH_MS", 100)))


def lcd_refresh(force=False):
    """Idle: READY FOR + DEPLOYMENT centered. Slave: SLAVED (centered) + mA (HOST_LINK_TIMEOUT_MS)."""
    global _last_lcd_ms, _lcd_was_slave_mode, lcd, _lcd_refresh_err_logged
    if lcd is None:
        return
    period = _lcd_refresh_period_ms()
    now = time.ticks_ms()
    if (
        not _estop_button_held
        and not force
        and time.ticks_diff(now, _last_lcd_ms) < period
    ):
        return
    _last_lcd_ms = now
    slave = _lcd_slave_mode()
    try:
        try:
            lcd.display_on()
        except Exception:
            pass
        if _estop_button_held:
            _lcd_put_row(0, _lcd_center_16("SAFE"))
            _lcd_put_row(1, _lcd_center_16("REBOOTING"))
            _lcd_was_slave_mode = slave
            return
        if slave:
            if _safe_state:
                _lcd_put_row(0, "SAFE STATE")
            else:
                _lcd_put_row(0, _lcd_center_16("SLAVED"))
            _lcd_put_row(1, _lcd_line2_ma())
        else:
            if _lcd_was_slave_mode:
                _lcd_clear()
            _lcd_put_row(0, _lcd_center_16("READY FOR"))
            _lcd_put_row(1, _lcd_center_16("DEPLOYMENT"))
        _lcd_was_slave_mode = slave
    except Exception as e:
        if not _lcd_refresh_err_logged:
            _lcd_refresh_err_logged = True
            host_print("STATUS LCD refresh ERR:", e)


def _show_boot_lcd_splash():
    """Clear LCD; centered product line + firmware version; hold then continue boot."""
    if lcd is None:
        return
    splash_s = float(getattr(config, "BOOT_LCD_SPLASH_S", 5.0))
    if splash_s <= 0:
        return
    try:
        try:
            lcd.display_on()
        except Exception:
            pass
        _lcd_clear()
        _lcd_put_row(0, _lcd_center_16("3DHC-Calibrator"))
        _lcd_put_row(1, _lcd_center_16("VER %s" % VERSION))
        time.sleep(splash_s)
    except Exception:
        pass


def _pwm_all_off():
    for i, p in enumerate(pwms):
        if p is not None:
            try:
                p.duty_u16(0)
            except Exception:
                pass
        if i < len(_last_u_cmd):
            _last_u_cmd[i] = 0.0


def _reset_ramp_state():
    global _ramp_active, _prev_target_ma, _ramp_stable_count, _oc_confirm
    global _settle_active, _settle_t0_ms, _u_hold, _prev_I_ma, _dc_settle_count
    _ramp_active = [False, False, False]
    _prev_target_ma = [0.0, 0.0, 0.0]
    _ramp_stable_count = [0, 0, 0]
    _oc_confirm = [0, 0, 0]
    _settle_active = [False, False, False]
    _settle_t0_ms = [0, 0, 0]
    _u_hold = [0.0, 0.0, 0.0]
    _prev_I_ma = [0.0, 0.0, 0.0]
    _dc_settle_count = [0, 0, 0]


def _coils_hw_all_off_immediate():
    global _duty_integral
    _pwm_all_off()
    _duty_integral = [0.0, 0.0, 0.0]
    _reset_ramp_state()
    for i in range(3):
        manual_pwm_duty[i] = None


def _apply_deploy_ready_coils_off(status_tag=None, refresh_lcd=True):
    """Same as serial host_disconnect / abort: PWM off, clear SAFE latch, zero setpoints, DEPLOY_READY."""
    global set_X_ma, set_Y_ma, set_Z_ma, _host_set_ma_ack, _safe_state, _alarm_latched, _last_host_rx_ms
    set_X_ma = 0.0
    set_Y_ma = 0.0
    set_Z_ma = 0.0
    _host_set_ma_ack = False
    _safe_state = False
    _alarm_latched = False
    _last_host_rx_ms = None
    _coils_hw_all_off_immediate()
    msg = "STATUS DEPLOY_READY coils_off pwm_safe"
    if status_tag:
        msg += " " + str(status_tag)
    host_print(msg)
    if refresh_lcd:
        _lcd_clear()
        lcd_refresh(force=True)


def _estop_edge_scheduled(_):
    """Main context: press → deploy-ready + clear LCD + SAFE/REBOOTING; release → normal LCD."""
    global _estop_button_held, _estop_last_press_ms, _estop_last_release_ms
    pin = _estop_pin
    if pin is None:
        return
    now = time.ticks_ms()
    deb = max(40, int(getattr(config, "HARDWARE_ESTOP_DEBOUNCE_MS", 80)))
    pressed = pin.value() == 0

    if pressed:
        if _estop_button_held:
            return
        if (
            _estop_last_press_ms is not None
            and time.ticks_diff(now, _estop_last_press_ms) < deb
        ):
            return
        _estop_last_press_ms = now
        _estop_button_held = True
        _apply_deploy_ready_coils_off("hw_estop", refresh_lcd=False)
        if lcd is not None:
            try:
                lcd.display_on()
            except Exception:
                pass
            _lcd_clear()
            _lcd_put_row(0, _lcd_center_16("SAFE"))
            _lcd_put_row(1, _lcd_center_16("REBOOTING"))
    else:
        if (
            _estop_last_release_ms is not None
            and time.ticks_diff(now, _estop_last_release_ms) < deb
        ):
            return
        _estop_last_release_ms = now
        if not _estop_button_held:
            return
        _estop_button_held = False
        try:
            lcd_refresh(force=True)
        except Exception:
            pass


def _estop_pin_irq(_pin):
    try:
        micropython.schedule(_estop_edge_scheduled, None)
    except Exception:
        pass


def _init_hardware_estop():
    """NO button to GND on HARDWARE_ESTOP_GP: pull-up; press → deploy + SAFE/REBOOTING until release."""
    global _estop_pin
    _estop_pin = None
    gp = int(getattr(config, "HARDWARE_ESTOP_GP", 0))
    if gp <= 0:
        return
    try:
        _estop_pin = Pin(int(gp), Pin.IN, Pin.PULL_UP)
        _estop_pin.irq(
            handler=_estop_pin_irq,
            trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
        )
        host_print(
            "STATUS HARDWARE_ESTOP GP%d pull-up IRQ_FALLING|RISING -> deploy + SAFE while held"
            % int(gp)
        )
    except Exception as e:
        _estop_pin = None
        host_print("STATUS HARDWARE_ESTOP init ERR:", e)


def _enter_safe(reason):
    """Latched SAFE: PWM off, setpoints zero, refuse set_*_ma until safe_reset or abort."""
    global _safe_state, _alarm_latched, set_X_ma, set_Y_ma, set_Z_ma, _host_set_ma_ack
    if _safe_state:
        return
    _safe_state = True
    _alarm_latched = True
    set_X_ma = 0.0
    set_Y_ma = 0.0
    set_Z_ma = 0.0
    _host_set_ma_ack = False
    _coils_hw_all_off_immediate()
    host_print("ERROR: Safe State -", reason)
    host_print(
        "ERROR: Safe State - PWM off; mA commands refused until safe_reset or abort"
    )


def _maybe_coils_hw_all_off_after_setpoints():
    if (
        max(0.0, set_X_ma) < 1e-6
        and max(0.0, set_Y_ma) < 1e-6
        and max(0.0, set_Z_ma) < 1e-6
    ):
        _coils_hw_all_off_immediate()


def _read_currents_raw_ch012():
    """INA3221 ch0..ch2 mA (raw sign from shunt wiring). Fix polarity at the shunt, not in SW.

    With INA3221_BUS_V_SYNC_PWM, each channel is sampled after aligning to that axis's PWM **off**
    window (middle of IN1 low time) so INA sees the quietest RC node.
    """
    if mon is None:
        return 0.0, 0.0, 0.0
    try:
        if not int(getattr(config, "INA3221_BUS_V_SYNC_PWM", 1)):
            return (
                mon.current_ma(0),
                mon.current_ma(1),
                mon.current_ma(2),
            )
        out = [0.0, 0.0, 0.0]
        for ic in range(3):
            _wait_ina3221_pwm_off_center(_axis_index_for_ina_ch(ic))
            out[ic], _ = mon.current_ma_and_bus_voltage_v(ic)
        return (out[0], out[1], out[2])
    except OSError:
        return 0.0, 0.0, 0.0


def read_currents_ma_ordered_xyz():
    r0, r1, r2 = _read_currents_raw_ch012()
    raw = [r0, r1, r2]
    order = _axis_order()
    return (
        raw[order[0]],
        raw[order[1]],
        raw[order[2]],
    )


def _duty_u16_clamped(duty):
    """0..65535 for MicroPython PWM; if duty>0 but float rounds to 0 counts, use 1 LSB (ramp ease-in)."""
    duty = max(0.0, min(1.0, float(duty)))
    u = int(duty * 65535)
    if duty > 0.0 and u == 0:
        u = 1
    return u


def set_pwm(axis, duty):
    if axis < 0 or axis >= len(pwms) or pwms[axis] is None:
        return
    duty = max(0.0, min(1.0, duty))
    if 0 <= axis < len(_last_u_cmd):
        _last_u_cmd[axis] = duty
    if str(getattr(config, "COIL_DRIVER_HW", "")) == "drv8871_3ch":
        if axis < len(_drv8871_in2_pins) and _drv8871_in2_pins[axis] is not None:
            try:
                _drv8871_in2_pins[axis].value(0)
            except Exception:
                pass
    pwms[axis].duty_u16(_duty_u16_clamped(duty))


def _set_pwm_hz_axis(axis, hz):
    """Runtime PWM frequency for one coil channel (EN pin)."""
    hz = int(max(100, min(100_000, hz)))
    if 0 <= axis < len(pwms) and pwms[axis] is not None:
        try:
            p = pwms[axis]
            p.freq(hz)
            # RP2040 MicroPython often resets duty_u16 when freq() changes; restore last command.
            u = float(_last_u_cmd[axis]) if 0 <= axis < len(_last_u_cmd) else 0.0
            u = max(0.0, min(1.0, u))
            p.duty_u16(int(u * 65535))
            return True
        except Exception:
            return False
    return False


def control_step(_=None):
    global _last_telem_ms, _alarm_latched, _ramp_active, _ramp_t0_ms, _ramp_stable_count, _prev_target_ma, _duty_integral, _oc_confirm

    t_now = time.ticks_ms()
    c0, c1, c2 = _read_currents_raw_ch012()
    currents_ch = [c0, c1, c2]
    order = _axis_order()
    lim_one = max(1e-6, MAX_MA_DEFAULT)
    limits = (lim_one, lim_one, lim_one)
    axes = ("X", "Y", "Z")

    # Overcurrent — trip SAFE before any PWM update this cycle (not in first OVERCURRENT_ARM_MS after boot).
    arm_ms = int(getattr(config, "OVERCURRENT_ARM_MS", 800))
    oc_ready = (
        _BOOT_TICKS_MS is not None
        and time.ticks_diff(time.ticks_ms(), _BOOT_TICKS_MS) >= arm_ms
    )
    oc_need = max(1, int(getattr(config, "OVERCURRENT_CONFIRM_SAMPLES", 3)))
    oc_trip = int(getattr(config, "OVERCURRENT_TRIP_ENABLE", 1))
    if oc_trip and not _safe_state and oc_ready:
        for j in range(3):
            ch_idx = order[j]
            # Magnitude — a mistaken SW sign flip could make I negative and skip a plain > limit check.
            if abs(currents_ch[ch_idx]) > limits[j] + 1e-3:
                oc_soft = int(getattr(config, "OC_LOW_DUTY_IGNORE", 1))
                if oc_soft:
                    u_th = float(getattr(config, "OC_LOW_DUTY_U_THRESH", 0.35))
                    relax = float(getattr(config, "OC_LOW_DUTY_LIMIT_RELAX", 1.0))
                    if _last_u_cmd[j] < u_th:
                        ceiling = limits[j] * (1.0 + relax)
                        if abs(currents_ch[ch_idx]) <= ceiling + 1e-3:
                            _oc_confirm[j] = 0
                            continue
                _oc_confirm[j] += 1
                if _oc_confirm[j] >= oc_need:
                    _enter_safe(
                        "OVERCURRENT %s %.3f mA (limit %.3f)"
                        % (axes[j], currents_ch[ch_idx], limits[j])
                    )
                    break
            else:
                _oc_confirm[j] = 0

    duties = {}
    if _safe_state:
        _pwm_all_off()
        duties = {"X": 0, "Y": 0, "Z": 0}
    else:
        targets = (max(0.0, set_X_ma), max(0.0, set_Y_ma), max(0.0, set_Z_ma))
        for i, axis in enumerate(axes):
            if manual_pwm_duty[i] is not None:
                set_pwm(i, manual_pwm_duty[i])
                duties[axis] = int(manual_pwm_duty[i] * PWM_RESOLUTION)
                continue
            target = targets[i]
            ch_idx = order[i]
            actual = currents_ch[ch_idx]
            lim = max(1e-6, limits[i])
            prev = _prev_target_ma[i]

            if target < 1e-6:
                _duty_integral[i] = 0.0
                _ramp_active[i] = False
                _settle_active[i] = False
                _ramp_stable_count[i] = 0
                set_pwm(i, 0.0)
                duties[axis] = 0
                _prev_target_ma[i] = target
                continue

            # Soft-start: 0% duty → PWM_RAMP_TO_TARGET_FRAC × (target/limit) over PWM_RAMP_MS (ease-in optional).
            if prev < 1e-6 and target >= 1e-6:
                _ramp_active[i] = True
                _settle_active[i] = False
                _ramp_t0_ms[i] = t_now
                _ramp_stable_count[i] = 0
                _duty_integral[i] = 0.0

            pwm_ramp_ms = max(1, int(getattr(config, "PWM_RAMP_MS", 3000)))
            ramp_ease = int(getattr(config, "PWM_RAMP_EASE_IN", 1))
            ramp_abs = float(getattr(config, "RAMP_EXIT_MA_ABS", 1.0))
            ramp_frac = float(getattr(config, "RAMP_EXIT_FRAC", 0.15))
            n_stable = int(getattr(config, "RAMP_STABLE_SAMPLES", 0))
            settle_enable = int(getattr(config, "RAMP_SETTLE_DC_ENABLE", 1))

            if _ramp_active[i]:
                ff_cap = min(1.0, target / lim)
                ramp_to_tgt = float(getattr(config, "PWM_RAMP_TO_TARGET_FRAC", 0.3))
                ramp_to_tgt = max(0.0, min(1.0, ramp_to_tgt))
                u_ramp_end = ff_cap * ramp_to_tgt
                elapsed = max(0, time.ticks_diff(t_now, _ramp_t0_ms[i]))
                prog = min(1.0, elapsed / float(pwm_ramp_ms))
                if ramp_ease:
                    prog = prog * prog
                u_ramp = ff_cap * ramp_to_tgt * prog
                ramp_done = False
                if elapsed >= pwm_ramp_ms:
                    ramp_done = True
                elif mon is not None and n_stable > 0:
                    tol = max(ramp_abs, ramp_frac * target)
                    if abs(actual - target) <= tol:
                        _ramp_stable_count[i] += 1
                        if _ramp_stable_count[i] >= n_stable:
                            ramp_done = True
                            u_ramp_end = u_ramp
                    else:
                        _ramp_stable_count[i] = 0
                if ramp_done:
                    _ramp_active[i] = False
                    if settle_enable and mon is not None:
                        _settle_active[i] = True
                        _settle_t0_ms[i] = t_now
                        _u_hold[i] = u_ramp_end
                        _dc_settle_count[i] = 0
                        _prev_I_ma[i] = actual
                        set_pwm(i, _u_hold[i])
                        duties[axis] = int(_u_hold[i] * PWM_RESOLUTION)
                        _prev_target_ma[i] = target
                        continue
                else:
                    set_pwm(i, u_ramp)
                    duties[axis] = int(u_ramp * PWM_RESOLUTION)
                    _prev_target_ma[i] = target
                    continue

            if _settle_active[i]:
                settle_min = int(getattr(config, "SETTLE_MIN_MS", 200))
                settle_max = int(getattr(config, "SETTLE_MAX_MS", 12000))
                d_m = float(getattr(config, "DC_STABLE_DELTA_MA", 3.0))
                n_dc = max(1, int(getattr(config, "DC_STABLE_SAMPLES", 12)))
                if not settle_enable or mon is None:
                    _settle_active[i] = False
                else:
                    u_fixed = _u_hold[i]
                    set_pwm(i, u_fixed)
                    duties[axis] = int(u_fixed * PWM_RESOLUTION)
                    _prev_target_ma[i] = target
                    el = max(0, time.ticks_diff(t_now, _settle_t0_ms[i]))
                    di = abs(actual - _prev_I_ma[i])
                    _prev_I_ma[i] = actual
                    if el >= settle_max:
                        _settle_active[i] = False
                    elif el >= settle_min and di <= d_m:
                        _dc_settle_count[i] += 1
                        if _dc_settle_count[i] >= n_dc:
                            _settle_active[i] = False
                    else:
                        _dc_settle_count[i] = 0
                    if _settle_active[i]:
                        continue

            err = target - actual
            ff = (min(1.0, target / lim) if CONTROL_FEEDFORWARD else 0.0)
            p_term = P_GAIN * (err / lim)
            # Integrate with anti-windup: do not accumulate integral when output would saturate.
            trial_i = _duty_integral[i] + err * dt
            trial_i = max(-1.0, min(1.0, trial_i))
            u_trial = ff + p_term + I_GAIN * trial_i
            if u_trial > 1.0 and err > 0:
                trial_i = _duty_integral[i]
            elif u_trial < 0.0 and err < 0:
                trial_i = _duty_integral[i]
            _duty_integral[i] = trial_i
            u = ff + p_term + I_GAIN * _duty_integral[i]
            u = max(0.0, min(1.0, u))
            # Hard cap vs setpoint: without this, PI can still command ~100% duty for small targets (e.g. 10 mA / 100 mA limit).
            head = float(getattr(config, "PI_DUTY_HEADROOM", 0.35))
            if head >= 0.0 and target > 1e-6:
                u_cap = min(1.0, (target / lim) * (1.0 + head))
                u = min(u, u_cap)
            set_pwm(i, u)
            duties[axis] = int(u * PWM_RESOLUTION)
            _prev_target_ma[i] = target

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_telem_ms) >= TELEM_PERIOD_MS:
        _last_telem_ms = now
        try:
            if mon and int(getattr(config, "INA3221_BUS_V_SYNC_PWM", 1)):
                r012 = [0.0, 0.0, 0.0]
                vb = [float("nan"), float("nan"), float("nan")]
                for ic in range(3):
                    _wait_ina3221_pwm_off_center(_axis_index_for_ina_ch(ic))
                    r012[ic], vb[ic] = mon.current_ma_and_bus_voltage_v(ic)
                c0, c1, c2 = r012[0], r012[1], r012[2]
                x_i = r012[order[0]]
                y_i = r012[order[1]]
                z_i = r012[order[2]]
                coil_v_x = vb[order[0]]
                coil_v_y = vb[order[1]]
                coil_v_z = vb[order[2]]
            else:
                c0, c1, c2 = _read_currents_raw_ch012()
                raw = [c0, c1, c2]
                x_i, y_i, z_i = raw[order[0]], raw[order[1]], raw[order[2]]
                if mon:
                    coil_v_x = mon.bus_voltage_v(order[0])
                    coil_v_y = mon.bus_voltage_v(order[1])
                    coil_v_z = mon.bus_voltage_v(order[2])
                else:
                    coil_v_x = coil_v_y = coil_v_z = float("nan")
            tmo = int(getattr(config, "HOST_LINK_TIMEOUT_MS", 5000))
            cfg = 0
            if (
                _host_set_ma_ack
                and _last_host_rx_ms is not None
                and time.ticks_diff(now, _last_host_rx_ms) < tmo
            ):
                cfg = 1
            closed_loop = 0
            if (
                not _safe_state
                and mon is not None
                and all(manual_pwm_duty[i] is None for i in range(3))
                and not any(_ramp_active)
                and not any(_settle_active)
            ):
                closed_loop = 1
            parts = [
                "meas_ok=%d" % (1 if mon is not None else 0),
                "X_ma=%.2f" % x_i,
                "Y_ma=%.2f" % y_i,
                "Z_ma=%.2f" % z_i,
                "set_X_ma=%.2f" % max(0.0, set_X_ma),
                "set_Y_ma=%.2f" % max(0.0, set_Y_ma),
                "set_Z_ma=%.2f" % max(0.0, set_Z_ma),
                "closed_loop=%d" % closed_loop,
                "ramp=%d" % (1 if any(_ramp_active) else 0),
                "settle=%d" % (1 if any(_settle_active) else 0),
                "cfg=%d" % cfg,
                "safe=%d" % (1 if _safe_state else 0),
                "diag_Ch1_ma=%.2f" % c0,
                "diag_Ch2_ma=%.2f" % c1,
                "diag_Ch3_ma=%.2f" % c2,
                "coil_V_X=%s" % _fmt_telem_float(coil_v_x),
                "coil_V_Y=%s" % _fmt_telem_float(coil_v_y),
                "coil_V_Z=%s" % _fmt_telem_float(coil_v_z),
                "diag_X_duty=%d" % duties.get("X", 0),
                "diag_Y_duty=%d" % duties.get("Y", 0),
                "diag_Z_duty=%d" % duties.get("Z", 0),
                "alarm=%d" % (1 if (_alarm_latched or _safe_state) else 0),
            ]
            try:
                micropython.schedule(_scheduled_tm_line, "TM:: " + " ".join(parts))
            except Exception:
                pass
        except Exception as e:
            try:
                micropython.schedule(_scheduled_tm_err, str(e))
            except Exception:
                pass

    # Do NOT call lcd_refresh() here: this runs from the Timer ISR. I2C/LCD needs heap + main context
    # (see MicroPython ISR rules); doing I2C from the callback can blank the panel or corrupt writes.


def _fmt_telem_float(x, fmt="%.3f"):
    try:
        if x != x:
            return "nan"
        return fmt % x
    except Exception:
        return "nan"


def _parse_float(s, default=None):
    try:
        return float(s.strip().split()[0])
    except Exception:
        return default


def handle_line(line):
    global set_X_ma, set_Y_ma, set_Z_ma
    global _last_host_rx_ms, _host_set_ma_ack
    global _safe_state, _alarm_latched

    s = (line or "").strip()
    if not s or s.startswith("TM::") or s.startswith("STATUS") or s.startswith("TXT::"):
        return ""

    parts = s.split(None, 1)
    cmd = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""
    u = cmd.upper()
    key = cmd.lower()

    # host_disconnect = Calibrator host leaving; legacy names kept for old tools.
    if key in ("host_disconnect", "abort", "shutdown", "calibration_stop"):
        _apply_deploy_ready_coils_off()
        if key == "host_disconnect":
            return "OK host_disconnect"
        return "OK %s" % key

    # Any other host line counts as "slave mode" activity (refreshes LCD host link timer).
    _last_host_rx_ms = time.ticks_ms()

    if key == "noop":
        return ""

    # Host keepalive (1 Hz): confirms firmware is running; also refreshes slave LCD link like noop.
    if key == "alive":
        return "OK ALIVE"

    # Re-print I2C / INA / LCD / H-bridge summary (boot TXT:: is often missed before host opens COM).
    if key in ("hw_report", "hw_info", "boot_report"):
        _report_hardware_to_host(boot_footer=False)
        return "OK hw_report"

    if key == "safe":
        _enter_safe("Host SAFE button")
        lcd_refresh(force=True)
        return "OK SAFE"

    if key in ("safe_reset", "reset_safe"):
        _safe_state = False
        _alarm_latched = False
        host_print("STATUS safe_reset OK")
        return "OK safe_reset"

    if _safe_state:
        if key in (
            "set_x_ma",
            "set_y_ma",
            "set_z_ma",
            "set_x_pwm_hz",
            "set_y_pwm_hz",
            "set_z_pwm_hz",
        ):
            host_print("ERROR: Safe State - command ignored")
            return "ERR SAFE_STATE"

    if u == "PING":
        return "PONG"

    # gui_status = Calibrator host status request: returns version and refreshes slave-mode timer.
    if key in ("version", "fw_version", "gui_status"):
        return "OK VERSION %s" % VERSION

    if key in ("set_x_ma",) or u == "SET_X_MA":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        set_X_ma = v
        _host_set_ma_ack = True
        _maybe_coils_hw_all_off_after_setpoints()
        return "OK set_X_ma %.2f" % v
    if key in ("set_y_ma",) or u == "SET_Y_MA":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        set_Y_ma = v
        _host_set_ma_ack = True
        _maybe_coils_hw_all_off_after_setpoints()
        return "OK set_Y_ma %.2f" % v
    if key in ("set_z_ma",) or u == "SET_Z_MA":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        set_Z_ma = v
        _host_set_ma_ack = True
        _maybe_coils_hw_all_off_after_setpoints()
        return "OK set_Z_ma %.2f" % v

    if key == "set_x_pwm_hz":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        hz = int(max(100, min(100_000, v)))
        return ("OK set_x_pwm_hz %d" % hz) if _set_pwm_hz_axis(0, hz) else "ERR set_x_pwm_hz"
    if key == "set_y_pwm_hz":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        hz = int(max(100, min(100_000, v)))
        return ("OK set_y_pwm_hz %d" % hz) if _set_pwm_hz_axis(1, hz) else "ERR set_y_pwm_hz"
    if key == "set_z_pwm_hz":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        hz = int(max(100, min(100_000, v)))
        return ("OK set_z_pwm_hz %d" % hz) if _set_pwm_hz_axis(2, hz) else "ERR set_z_pwm_hz"

    return "ERR unknown"


# null_field_* for TM compatibility if extended later
null_field_X_ma = 0.0
null_field_Y_ma = 0.0
null_field_Z_ma = 0.0


def _hex_list(addrs):
    if not addrs:
        return "[]"
    return "[" + ", ".join("0x%02x" % int(a) for a in sorted(addrs)) + "]"


def _report_hardware_to_host(boot_footer=True):
    """Hardware / I2C / INA / H-bridge summary for Calibrator (TXT:: lines).

    Called once at boot (boot_footer=True). Host can request again with hw_report
    after connect — boot lines are already gone from the serial buffer.
    """
    global _host_txt_burst_active
    # Do not deinit the control Timer during hw_report: on some MP builds re-init fails silently
    # and control_step never runs again (no PWM). Suppressing scheduled TM:: is enough for clean TXT::.
    _host_txt_burst_active = True
    try:
        _report_hardware_to_host_body(boot_footer)
    finally:
        _host_txt_burst_active = False


def _report_hardware_to_host_body(boot_footer=True):
    host_print("Initializing CoilDriver …")
    host_print("Firmware version", VERSION)
    thz = 1000.0 / max(1, TELEM_PERIOD_MS)
    host_print(
        "Control: loop %d Hz; telemetry every %d ms (~%.1f Hz)"
        % (LOOP_HZ, TELEM_PERIOD_MS, thz)
    )
    if int(getattr(config, "OVERCURRENT_TRIP_ENABLE", 1)):
        host_print(
            "Overcurrent→SAFE armed after %d ms from boot (config OVERCURRENT_ARM_MS)"
            % int(getattr(config, "OVERCURRENT_ARM_MS", 800))
        )
        host_print(
            "Overcurrent→SAFE needs %d consecutive samples over limit (OVERCURRENT_CONFIRM_SAMPLES)"
            % max(1, int(getattr(config, "OVERCURRENT_CONFIRM_SAMPLES", 3)))
        )
        if int(getattr(config, "OC_LOW_DUTY_IGNORE", 1)):
            host_print(
                "Overcurrent: low EN duty soft band — u<%.2f → trip only if I>limit×(1+%.2f) (OC_LOW_DUTY_*)"
                % (
                    float(getattr(config, "OC_LOW_DUTY_U_THRESH", 0.35)),
                    float(getattr(config, "OC_LOW_DUTY_LIMIT_RELAX", 1.0)),
                )
            )
    else:
        host_print(
            "Overcurrent→SAFE: disabled (config OVERCURRENT_TRIP_ENABLE=0; shunt I does not latch SAFE)"
        )
    if int(getattr(config, "RAMP_SETTLE_DC_ENABLE", 1)):
        host_print(
            "After PWM ramp: DC settle — hold duty until |ΔI|≤%.2f mA for %d samples (SETTLE_MIN/MAX_MS)"
            % (
                float(getattr(config, "DC_STABLE_DELTA_MA", 3.0)),
                int(getattr(config, "DC_STABLE_SAMPLES", 12)),
            )
        )

    egp = int(getattr(config, "HARDWARE_ESTOP_GP", 0))
    edb = int(getattr(config, "HARDWARE_ESTOP_DEBOUNCE_MS", 80))
    if egp > 0:
        host_print(
            "Hardware estop: GP%d (NO to GND), pull-up; press -> DEPLOY + SAFE/REBOOTING LCD until release; debounce %d ms"
            % (egp, edb)
        )
    else:
        host_print("Hardware estop: off (HARDWARE_ESTOP_GP=0)")

    i2c_id = int(getattr(config, "I2C_ID", 0))
    sda = int(getattr(config, "I2C_SDA", 4))
    scl = int(getattr(config, "I2C_SCL", 5))
    freq = int(getattr(config, "I2C_FREQ_HZ", 100_000))
    ina_addr = int(getattr(config, "INA3221_ADDRESS", 0x40))
    rsh = float(getattr(config, "INA3221_SHUNT_OHMS", 0.1))
    order = _axis_order()
    host_print("--- INA3221 (I2C current monitor) ---")
    host_print("  Bus I2C%d SDA=GP%d SCL=GP%d %d Hz" % (i2c_id, sda, scl, freq))
    addrs_ina = []
    if i2c is not None:
        try:
            addrs_ina = list(i2c.scan())
        except Exception as e:
            host_print("  I2C scan failed:", e)
    host_print("  Devices on bus:", _hex_list(addrs_ina))
    host_print("  Config: I2C address 0x%02x; R_shunt = %.4f Ohm" % (ina_addr, rsh))
    fs_ma = 163.0 / max(rsh, 1e-9)
    host_print(
        "  Full-scale shunt current ~%.0f mA (±163 mV sense FS / R_shunt, TI INA3221)"
        % fs_ma
    )
    host_print(
        "  Logical axes: INA3221 ch%u,%u,%u -> X,Y,Z"
        % (order[0], order[1], order[2])
    )
    if mon is not None:
        host_print(
            "  Driver: OK — readings use R_shunt above; chip setup per ina3221.py (default regs if unset)"
        )
        try:
            r0 = mon.shunt_raw(0)
            r1 = mon.shunt_raw(1)
            r2 = mon.shunt_raw(2)
            host_print("  Shunt regs (raw counts, ch0..2):", r0, r1, r2)
        except Exception as e:
            host_print("  Shunt reg read failed:", e)
    elif not addrs_ina or ina_addr not in addrs_ina:
        host_print(
            "  Driver: not active — no device at 0x%02x (check A0 strap / wiring)"
            % ina_addr
        )
    else:
        host_print("  Driver: not active — ina3221.py missing or init raised")

    host_print("--- LCD (PCF8574 + HD44780) ---")
    lid = int(getattr(config, "LCD_I2C_ID", 0))
    lsda = int(getattr(config, "LCD_I2C_SDA", 4))
    lscl = int(getattr(config, "LCD_I2C_SCL", 5))
    lfreq = int(getattr(config, "LCD_I2C_FREQ_HZ", 100_000))
    want_lcd = int(getattr(config, "LCD_I2C_ADDR", 0x27))
    host_print(
        "  Bus I2C%d SDA=GP%d SCL=GP%d %d Hz; target 0x%02x or 0x3F"
        % (lid, lsda, lscl, lfreq, want_lcd)
    )
    lbus = None
    try:
        lbus = _lcd_i2c_bus()
    except Exception as e:
        host_print("  LCD bus failed:", e)
    lcd_addrs = []
    if lbus is not None:
        try:
            lcd_addrs = list(lbus.scan())
        except Exception as e:
            host_print("  I2C scan failed:", e)
    host_print("  Devices on bus:", _hex_list(lcd_addrs))
    if lcd is not None and lcd_i2c_addr_used is not None:
        host_print("  LCD: OK at 0x%02x, 2 rows x 16 cols" % lcd_i2c_addr_used)
    else:
        host_print("  LCD: not opened — check retries / wiring (see STATUS LCD … during init)")

    hb = str(getattr(config, "H_BRIDGE_MODEL", "H-bridge"))
    n_pt = int(getattr(config, "PT5126_COUNT", 0))
    pwm_hz = int(getattr(config, "PWM_FREQ_HZ", 20_000))
    p_en = getattr(config, "PWM_EN_PINS", (10, 12, 14))
    dx = getattr(config, "DIR_PINS_X", (6, 7))
    dy = getattr(config, "DIR_PINS_Y", (8, 9))
    dz = getattr(config, "DIR_PINS_Z", (11, 13))
    hw = str(getattr(config, "COIL_DRIVER_HW", "model_y"))
    if hw == "drv8871_3ch":
        in1 = getattr(config, "DRV8871_IN1_PWM_PINS", (10, 12, 14))
        in2 = getattr(config, "DRV8871_IN2_PINS", (11, 13, 15))
        host_print("--- Coil drivers (%s) ---" % hb)
        host_print(
            "  3× TI DRV8871 — IN1 = PWM from Pico; IN2 held low (TI unidirectional PWM / coast decay)."
        )
        host_print(
            "  VM 6.5–45 V per datasheet; OUT1/OUT2 to coil. Use f_PWM so off-time < ~1 ms (sleep if both IN low)."
        )
        host_print(
            "  IN1 PWM %d Hz — X=GP%u Y=GP%u Z=GP%u"
            % (pwm_hz, in1[0], in1[1], in1[2])
        )
        host_print(
            "  IN2 low (GPIO) — X=GP%u Y=GP%u Z=GP%u"
            % (in2[0], in2[1], in2[2])
        )
        host_print(
            "  INA PWM off-sync: X slice %u ch %s | Y slice %u ch %s | Z slice %u ch %s"
            % (
                _pwm_slice_for_axis[0],
                "A" if _pwm_cc_chan_per_axis[0] == 0 else "B",
                _pwm_slice_for_axis[1],
                "A" if _pwm_cc_chan_per_axis[1] == 0 else "B",
                _pwm_slice_for_axis[2],
                "A" if _pwm_cc_chan_per_axis[2] == 0 else "B",
            )
        )
        for i, ax in enumerate(("X", "Y", "Z")):
            g = int(in1[i])
            ok = i < len(pwms) and pwms[i] is not None
            host_print(
                "  Axis %s IN1 GP%u: hardware PWM %s"
                % (ax, g, "OK" if ok else "FAIL (no output — bad GPIO or wiring damage)")
            )
    elif hw == "mosfet_3ch":
        host_print("--- Coil drivers (%s) ---" % hb)
        host_print(
            "  3× MOSFET modules — one PWM per axis to module input; no bridge DIR pins."
        )
        host_print(
            "  Power wiring: VIN+ VIN− VOUT+ VOUT− (see module silk); coils on VOUT side."
        )
        host_print(
            "  PWM %d Hz — X=GP%u Y=GP%u Z=GP%u"
            % (pwm_hz, p_en[0], p_en[1], p_en[2])
        )
    else:
        host_print("--- H-bridge (%s, %d x PT5126) ---" % (hb, n_pt))
        host_print(
            "  PT5126: no I2C — Pico only sets PWM duty on EN pins and fixed DIR per axis."
        )
        host_print(
            "  Channel use: X = bank A ENA, Y = bank A ENB, Z = bank B ENA (spare = bank B ENB)"
        )
        host_print(
            "  PWM %d Hz — X=GP%u Y=GP%u Z=GP%u"
            % (pwm_hz, p_en[0], p_en[1], p_en[2])
        )
        host_print(
            "  DIR — X: GP%u,GP%u | Y: GP%u,GP%u | Z: GP%u,GP%u (forward pattern in firmware)"
            % (dx[0], dx[1], dy[0], dy[1], dz[0], dz[1])
        )
    pwm_ok = []
    for i in range(3):
        pwm_ok.append("OK" if i < len(pwms) and pwms[i] is not None else "FAIL")
    host_print(
        "  PWM init summary: X=%s Y=%s Z=%s (0%% duty until setpoint > 0 — driver EN LED may be off)"
        % (pwm_ok[0], pwm_ok[1], pwm_ok[2])
    )
    host_print(
        "  SAFE latched: %s — if yes, PWM stays off until safe_reset / host Reset"
        % ("YES" if _safe_state else "no")
    )

    if boot_footer:
        host_print("PWM all channels 0%%; entering main loop.")
        host_print("READY")
        host_print("STATUS CONNECTED")
    else:
        host_print("— end hw_report —")


def _lcd_scheduled(_):
    """Runs in main interpreter context (not Timer ISR); safe for I2C."""
    try:
        lcd_refresh()
    except Exception:
        pass


def _lcd_timer_tick(_):
    """Timer ISR: only schedule; never I2C here (MicroPython ISR rules)."""
    try:
        micropython.schedule(_lcd_scheduled, None)
    except Exception:
        pass


def main():
    global _BOOT_TICKS_MS
    _init_lcd()
    _show_boot_lcd_splash()
    _init_hardware_estop()
    _BOOT_TICKS_MS = time.ticks_ms()
    _pwm_all_off()
    _report_hardware_to_host()
    # After splash: normal idle (READY FOR / DEPLOYMENT) or slave layout.
    lcd_refresh(force=True)

    def on_timer(_):
        control_step()

    tim = Timer()
    tim.init(mode=Timer.PERIODIC, period=int(dt * 1000), callback=on_timer)
    # LCD on its own timer + schedule: USB select/poll is unreliable on RP2040; readline() blocks.
    tim_lcd = None
    for _tid in (-1, 1):
        try:
            tim_lcd = Timer(_tid)
            tim_lcd.init(
                mode=Timer.PERIODIC,
                period=_lcd_refresh_period_ms(),
                callback=_lcd_timer_tick,
            )
            break
        except Exception:
            tim_lcd = None
    if tim_lcd is None:
        host_print("STATUS LCD no period timer; updates on boot + serial only")
    try:
        while True:
            line = sys.stdin.readline()
            if line:
                resp = handle_line(line)
                if resp:
                    host_print(resp)
                lcd_refresh(force=True)
    finally:
        if tim_lcd is not None:
            try:
                tim_lcd.deinit()
            except Exception:
                pass
        tim.deinit()
        for i in range(len(pwms)):
            if pwms[i]:
                try:
                    pwms[i].duty_u16(0)
                except Exception:
                    pass


if __name__ == "__main__":
    main()
