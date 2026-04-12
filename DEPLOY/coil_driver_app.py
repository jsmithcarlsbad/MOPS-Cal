# coil_driver_app.py — Host slave: enables + set_x/y/z_v (V); DRV8871 IN1 = hardware PWM only (drv8871_3ch).
# No PI / no ramp. Duty applied immediately: min(1, set_*_v / COIL_VOLTAGE_REF_VM_V) when axis enabled (open-loop V).
# One virtual Timer(-1): fast INA3221 snapshots + EMA filter; TM:: to host ≤30 Hz (filtered readings, config).
# LCD: splash / deploy / estop / explicit refresh after selected serial lines — not on every readline.
import sys
import time
import micropython
from machine import I2C, Pin, PWM, Timer

import config

VERSION_MAJOR = 5
VERSION_MINOR = 15
VERSION = "%d.%d" % (VERSION_MAJOR, VERSION_MINOR)

# TM:: rate to host (Hz): hard max 30 Hz (USB bandwidth); default from config often 10 Hz.
SLAVE_TM_HZ = float(getattr(config, "SLAVE_TM_HZ", 10.0))
SLAVE_TM_HZ = max(0.5, min(30.0, SLAVE_TM_HZ))
SLAVE_TM_PERIOD_MS = int(max(1, round(1000.0 / SLAVE_TM_HZ)))
# INA3221: fast full 3-ch reads; EMA in _poll_ina_and_filter → smooth values on TM::.
_smi = int(getattr(config, "INA3221_SAMPLE_MIN_MS", 20))
INA3221_SAMPLE_MIN_MS = max(5, min(250, _smi))
_FILTER_A = float(getattr(config, "INA3221_FILTER_ALPHA", 0.18))
INA3221_FILTER_ALPHA = 1.0 if _FILTER_A <= 0.0 else max(0.01, min(1.0, _FILTER_A))
# Virtual timer: back-button + INA poll; also ≤ TM period so TM:: can actually run at SLAVE_TM_HZ.
_POLL = int(getattr(config, "SLAVE_POLL_MS", 50))
_tp = max(10, min(100, _POLL))
SLAVE_TIMER_PERIOD_MS = max(10, min(_tp, SLAVE_TM_PERIOD_MS))

_last_tm_emit_ms = None
_last_ina_sample_ms = None
_filt_i012 = [None, None, None]
_filt_v012 = [None, None, None]

PWM_RESOLUTION = 4095

# --- Print helpers ---
_host_txt_burst_active = False


def host_print(*args):
    print("TXT:: " + " ".join(str(a) for a in args))


def _scheduled_tm_line(arg):
    global _host_txt_burst_active
    if _host_txt_burst_active:
        return
    try:
        print(arg)
    except Exception:
        pass


def _axis_order():
    return tuple(getattr(config, "INA3221_AXIS_ORDER", (0, 1, 2)))


# --- Hardware ---
i2c = None
mon = None
pwms = []
_drv8871_in2_pins = [None, None, None]
lcd = None
lcd_i2c_addr_used = None
_lcd_bus_instance = None

# --- Host state (bridge duty from set_*_v + enable only) ---
set_X_v = 0.0
set_Y_v = 0.0
set_Z_v = 0.0
_host_enable = [False, False, False]
_last_u_cmd = [0.0, 0.0, 0.0]

_last_host_rx_ms = None
_deploy_standalone_lcd = False

_last_slave_i012 = [0.0, 0.0, 0.0]
_last_slave_v012 = [float("nan"), float("nan"), float("nan")]

# LCD / estop / back
_last_lcd_ms = 0
_lcd_prev_layout = None
_lcd_write_err_logged = False
_lcd_refresh_err_logged = False
_estop_pin = None
_estop_button_held = False
_estop_last_press_ms = None
_estop_last_release_ms = None
_back_pin = None
_back_press_t0_ms = None
_back_deploy_fired = False
_back_last_edge_ms = None


def _init_hardware():
    global i2c, mon, pwms, _drv8871_in2_pins
    i2c = None
    mon = None
    pwms = []
    _drv8871_in2_pins = [None, None, None]
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
        # IN1/IN2 pairs are adjacent GPIOs on the same PWM slice (e.g. GP10/11 →
        # slice 5). Claim IN1 as PWM *before* configuring IN2 as plain GPIO so
        # the slice is registered for PWM first (avoids silent / stuck PWM on
        # some RP2040/RP2350 + MicroPython combinations).
        for i in range(3):
            try:
                g1 = int(in1[i])
                g2 = int(in2[i])
                # Same pattern as MicroPython docs: PWM(Pin(n)), freq(Hz), duty_u16(0..65535).
                p = PWM(Pin(g1))
                p.freq(pwm_hz)
                p.duty_u16(0)
                pwms.append(p)
            except Exception:
                pwms.append(None)
                _drv8871_in2_pins[i] = None
                continue
            try:
                p2 = Pin(g2, Pin.OUT)
                p2.value(0)
                _drv8871_in2_pins[i] = p2
            except Exception:
                _drv8871_in2_pins[i] = None
    else:
        for pin_num in getattr(config, "PWM_EN_PINS", (10, 12, 14)):
            try:
                p = PWM(Pin(int(pin_num)))
                p.freq(pwm_hz)
                p.duty_u16(0)
                pwms.append(p)
            except Exception:
                pwms.append(None)
    while len(pwms) < 3:
        pwms.append(None)


_init_hardware()


def _lcd_i2c_bus():
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
        host_print("STATUS LCD failed: no PCF8574 at 0x27/0x3F after retries")
    except Exception as e:
        lcd = None
        host_print("STATUS LCD init ERR:", e)


def _lcd_center_16(text):
    s = (text or "")[:16]
    L = len(s)
    if L >= 16:
        return s
    pad = 16 - L
    left = pad // 2
    return (" " * left) + s + (" " * (pad - left))


def _lcd_put_row(row, text):
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


def _lcd_clear():
    global lcd
    if lcd is None:
        return
    try:
        lcd.clear()
    except Exception:
        pass


def _lcd_refresh_period_ms():
    return max(100, int(getattr(config, "LCD_REFRESH_MS", 100)))


def lcd_refresh(force=False):
    global _last_lcd_ms, _lcd_prev_layout, lcd, _lcd_refresh_err_logged
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
    try:
        try:
            lcd.display_on()
        except Exception:
            pass
        if _estop_button_held:
            _lcd_put_row(0, _lcd_center_16("SAFE"))
            _lcd_put_row(1, _lcd_center_16("REBOOTING"))
            _lcd_prev_layout = "e"
            return
        layout = "d" if _deploy_standalone_lcd else "s"
        if (
            _lcd_prev_layout is not None
            and _lcd_prev_layout != layout
            and (_lcd_prev_layout == "e" or _lcd_prev_layout in ("d", "s"))
        ):
            _lcd_clear()
        if layout == "d":
            _lcd_put_row(0, _lcd_center_16("READY FOR"))
            _lcd_put_row(1, _lcd_center_16("DEPLOYMENT"))
        else:
            _lcd_put_row(0, _lcd_center_16("SLAVED"))
            _lcd_put_row(1, _lcd_center_16("REMOTE"))
        _lcd_prev_layout = layout
    except Exception as e:
        if not _lcd_refresh_err_logged:
            _lcd_refresh_err_logged = True
            host_print("STATUS LCD refresh ERR:", e)


def _show_boot_lcd_splash():
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


def _coils_hw_all_off_immediate():
    global set_X_v, set_Y_v, set_Z_v
    _pwm_all_off()
    set_X_v = 0.0
    set_Y_v = 0.0
    set_Z_v = 0.0


def _apply_deploy_ready_coils_off(status_tag=None, refresh_lcd=True):
    global _last_host_rx_ms
    global _deploy_standalone_lcd, _host_enable
    _host_enable = [False, False, False]
    _last_host_rx_ms = None
    _deploy_standalone_lcd = True
    _coils_hw_all_off_immediate()
    msg = "STATUS DEPLOY_READY coils_off pwm_safe"
    if status_tag:
        msg += " " + str(status_tag)
    host_print(msg)
    if refresh_lcd:
        _lcd_clear()
        lcd_refresh(force=True)


def _estop_edge_scheduled(_):
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
        _coils_stop_pwm_safe("Hardware estop (NO to GND)")
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
            "STATUS HARDWARE_ESTOP GP%d pull-up -> coils_off pwm_safe (NO to GND); not latched"
            % int(gp)
        )
    except Exception as e:
        _estop_pin = None
        host_print("STATUS HARDWARE_ESTOP init ERR:", e)


def _back_edge_scheduled(_):
    global _back_press_t0_ms, _back_deploy_fired, _back_last_edge_ms
    pin = _back_pin
    if pin is None:
        return
    now = time.ticks_ms()
    deb = max(40, int(getattr(config, "BACK_BUTTON_DEBOUNCE_MS", 80)))
    if (
        _back_last_edge_ms is not None
        and time.ticks_diff(now, _back_last_edge_ms) < deb
    ):
        return
    _back_last_edge_ms = now
    pressed = pin.value() == 0
    if pressed:
        _back_press_t0_ms = now
        _back_deploy_fired = False
    else:
        _back_press_t0_ms = None
        _back_deploy_fired = False


def _back_pin_irq(_pin):
    try:
        micropython.schedule(_back_edge_scheduled, None)
    except Exception:
        pass


def _init_hardware_back_button():
    global _back_pin
    _back_pin = None
    gp = int(getattr(config, "BACK_BUTTON_GP", 0))
    if gp <= 0:
        return False
    egp = int(getattr(config, "HARDWARE_ESTOP_GP", 0))
    if gp == egp:
        host_print("STATUS BACK_BUTTON ignored (same GP as HARDWARE_ESTOP)")
        return False
    try:
        _back_pin = Pin(int(gp), Pin.IN, Pin.PULL_UP)
        deb = max(40, int(getattr(config, "BACK_BUTTON_DEBOUNCE_MS", 80)))
        time.sleep_ms(deb)
        boot_down = _back_pin.value() == 0
        _back_pin.irq(
            handler=_back_pin_irq,
            trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
        )
        host_print(
            "STATUS BACK_BUTTON GP%d debounce %d ms -> deploy if down at boot or held >= %d ms (runtime)"
            % (int(gp), deb, deb)
        )
        return boot_down
    except Exception as e:
        _back_pin = None
        host_print("STATUS BACK_BUTTON init ERR:", e)
        return False


def _back_hold_poll():
    global _back_deploy_fired
    pin = _back_pin
    if pin is None or _back_press_t0_ms is None or _back_deploy_fired:
        return
    if pin.value() != 0:
        return
    deb = max(40, int(getattr(config, "BACK_BUTTON_DEBOUNCE_MS", 80)))
    now = time.ticks_ms()
    if time.ticks_diff(now, _back_press_t0_ms) < deb:
        return
    _back_deploy_fired = True
    _apply_deploy_ready_coils_off(status_tag="back_button_hold")


def _coils_stop_pwm_safe(reason):
    global set_X_v, set_Y_v, set_Z_v
    global _host_enable
    set_X_v = 0.0
    set_Y_v = 0.0
    set_Z_v = 0.0
    _host_enable = [False, False, False]
    _coils_hw_all_off_immediate()
    host_print("STATUS coils_off pwm_safe —", reason)


def _duty_u16_clamped(duty):
    duty = max(0.0, min(1.0, float(duty)))
    return int(duty * 65535 + 0.5)


def _bridge_duty_frac(axis, duty_frac, report=False):
    duty_frac = max(0.0, min(1.0, float(duty_frac)))
    ax = ("X", "Y", "Z")[axis] if 0 <= axis < 3 else "?"
    pct = int(round(duty_frac * 100.0))
    if pct < 0:
        pct = 0
    elif pct > 100:
        pct = 100
    line = "PWM %s duty=%d%%" % (ax, pct)
    if axis < 0 or axis >= len(pwms) or pwms[axis] is None:
        if report:
            s = line + " NO_PWM_OUT"
            print(s)
            host_print(s)
        return
    u16 = _duty_u16_clamped(duty_frac)
    if report:
        print(line)
        host_print(line)
    try:
        pwms[axis].duty_u16(u16)
    except Exception as e:
        if report:
            s = line + " duty_u16_ERR " + str(e)
            print(s)
            host_print(s)
        return
    if 0 <= axis < len(_last_u_cmd):
        _last_u_cmd[axis] = duty_frac


def _vm_ref_v():
    vm = float(getattr(config, "COIL_VOLTAGE_REF_VM_V", 12.0))
    if vm <= 0.0 or vm != vm:
        vm = 12.0
    return vm


def _v_cmd_max():
    m = float(getattr(config, "COIL_VOLTAGE_COMMAND_MAX_V", 45.0))
    if m <= 0.0 or m != m:
        m = 45.0
    return m


def _apply_voltage_commands():
    vm = _vm_ref_v()
    vmax = _v_cmd_max()
    targets = (set_X_v, set_Y_v, set_Z_v)
    for i in range(3):
        if not _host_enable[i]:
            _bridge_duty_frac(i, 0.0, False)
            continue
        v = max(0.0, min(vmax, float(targets[i])))
        if v <= 0.0:
            _bridge_duty_frac(i, 0.0, False)
            continue
        _bridge_duty_frac(i, min(1.0, v / vm), True)


def _read_ina_slave_snapshot():
    if mon is None:
        return None
    scale = float(getattr(config, "INA3221_CURRENT_SCALE", 1.0))
    if scale <= 0.0 or scale != scale:
        scale = 1.0
    ci = [0.0, 0.0, 0.0]
    cv = [float("nan"), float("nan"), float("nan")]
    for ic in range(3):
        try:
            i_ma, v_v = mon.current_ma_and_bus_voltage_v(ic)
            ci[ic] = i_ma * scale
            cv[ic] = v_v
        except OSError:
            pass
    return (ci[0], ci[1], ci[2], cv[0], cv[1], cv[2])


def _ema_step(prev, x, alpha):
    """One-step exponential moving average; NaN sample leaves prev unchanged."""
    try:
        if x != x:
            return prev
        xf = float(x)
        if prev is None or prev != prev:
            return xf
        return float(prev) + alpha * (xf - float(prev))
    except Exception:
        return prev


def _poll_ina_and_filter():
    """Fast INA3221 3-ch read (rate-limited); EMA → _last_slave_* for TM:: (≤30 Hz)."""
    global _last_slave_i012, _last_slave_v012, _last_ina_sample_ms
    global _filt_i012, _filt_v012
    if mon is None:
        return
    now = time.ticks_ms()
    if _last_ina_sample_ms is not None:
        if time.ticks_diff(now, _last_ina_sample_ms) < INA3221_SAMPLE_MIN_MS:
            return
    _last_ina_sample_ms = now
    r = _read_ina_slave_snapshot()
    if r is None:
        return
    c0, c1, c2, v0, v1, v2 = r
    a = INA3221_FILTER_ALPHA
    _filt_i012[0] = _ema_step(_filt_i012[0], c0, a)
    _filt_i012[1] = _ema_step(_filt_i012[1], c1, a)
    _filt_i012[2] = _ema_step(_filt_i012[2], c2, a)
    _filt_v012[0] = _ema_step(_filt_v012[0], v0, a)
    _filt_v012[1] = _ema_step(_filt_v012[1], v1, a)
    _filt_v012[2] = _ema_step(_filt_v012[2], v2, a)
    for i in range(3):
        fi = _filt_i012[i]
        _last_slave_i012[i] = 0.0 if fi is None or fi != fi else float(fi)
    for i in range(3):
        fv = _filt_v012[i]
        if fv is None or fv != fv:
            _last_slave_v012[i] = float("nan")
        else:
            _last_slave_v012[i] = float(fv)


def _fmt_telem_float(x, fmt="%.3f"):
    try:
        if x != x:
            return "nan"
        return fmt % x
    except Exception:
        return "nan"


def _emit_tm_scheduled(_):
    global _last_slave_i012, _last_slave_v012, _host_txt_burst_active, _last_tm_emit_ms
    if _host_txt_burst_active:
        return
    try:
        order = _axis_order()
        now = time.ticks_ms()
        if _last_tm_emit_ms is not None:
            if time.ticks_diff(now, _last_tm_emit_ms) < SLAVE_TM_PERIOD_MS:
                return
        _last_tm_emit_ms = now
        tmo = int(getattr(config, "HOST_LINK_TIMEOUT_MS", 5000))
        cfg = (
            1
            if (
                _last_host_rx_ms is not None
                and time.ticks_diff(now, _last_host_rx_ms) < tmo
            )
            else 0
        )
        if mon is None:
            line = (
                "TM:: meas_ok=0 closed_loop=0 cfg=%d safe=0 alarm=0"
                % cfg
            )
            micropython.schedule(_scheduled_tm_line, line)
            return
        c0, c1, c2 = _last_slave_i012[0], _last_slave_i012[1], _last_slave_i012[2]
        v0, v1, v2 = _last_slave_v012[0], _last_slave_v012[1], _last_slave_v012[2]
        raw_i = [c0, c1, c2]
        raw_v = [v0, v1, v2]
        xi = raw_i[order[0]]
        yi = raw_i[order[1]]
        zi = raw_i[order[2]]
        cvx = raw_v[order[0]]
        cvy = raw_v[order[1]]
        cvz = raw_v[order[2]]
        duties = {}
        for ai, ax in enumerate(("X", "Y", "Z")):
            duties[ax] = int(max(0.0, min(1.0, _last_u_cmd[ai])) * PWM_RESOLUTION)
        parts = [
            "meas_ok=1",
            "X_ma=%s" % _fmt_telem_float(xi, "%.2f"),
            "Y_ma=%s" % _fmt_telem_float(yi, "%.2f"),
            "Z_ma=%s" % _fmt_telem_float(zi, "%.2f"),
            "set_X_v=%.3f" % max(0.0, set_X_v),
            "set_Y_v=%.3f" % max(0.0, set_Y_v),
            "set_Z_v=%.3f" % max(0.0, set_Z_v),
            "closed_loop=0",
            "cfg=%d" % cfg,
            "safe=0",
            "ina_X_ch=%u" % int(order[0]),
            "ina_Y_ch=%u" % int(order[1]),
            "ina_Z_ch=%u" % int(order[2]),
            "diag_Ch1_ma=%.2f" % c0,
            "diag_Ch2_ma=%.2f" % c1,
            "diag_Ch3_ma=%.2f" % c2,
            "coil_V_X=%s" % _fmt_telem_float(cvx),
            "coil_V_Y=%s" % _fmt_telem_float(cvy),
            "coil_V_Z=%s" % _fmt_telem_float(cvz),
            "diag_X_duty=%d" % duties["X"],
            "diag_Y_duty=%d" % duties["Y"],
            "diag_Z_duty=%d" % duties["Z"],
            "alarm=0",
        ]
        micropython.schedule(_scheduled_tm_line, "TM:: " + " ".join(parts))
    except Exception as e:
        try:
            host_print("STATUS TM_ERR", str(e))
        except Exception:
            pass


def _slave_periodic(_):
    try:
        _back_hold_poll()
    except Exception:
        pass
    try:
        _poll_ina_and_filter()
    except Exception:
        pass
    _emit_tm_scheduled(None)


def _slave_timer_tick(_):
    try:
        micropython.schedule(_slave_periodic, None)
    except Exception:
        pass


def _parse_float(s, default=None):
    try:
        return float(s.strip().split()[0])
    except Exception:
        return default


def handle_line(line):
    global set_X_v, set_Y_v, set_Z_v
    global _last_host_rx_ms
    global _deploy_standalone_lcd
    global _host_enable

    s = (line or "").strip()
    if not s or s.startswith("TM::") or s.startswith("STATUS") or s.startswith("TXT::"):
        return ""

    parts = s.split(None, 1)
    cmd = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""
    u = cmd.upper()
    key = cmd.lower()

    if key in ("host_disconnect", "abort", "shutdown", "calibration_stop"):
        _apply_deploy_ready_coils_off()
        if key == "host_disconnect":
            return "OK host_disconnect"
        return "OK %s" % key

    if key == "alive":
        _last_host_rx_ms = time.ticks_ms()
        was_deploy = _deploy_standalone_lcd
        _deploy_standalone_lcd = False
        if was_deploy:
            lcd_refresh(force=True)
        return "OK ALIVE"

    _last_host_rx_ms = time.ticks_ms()
    was_deploy = _deploy_standalone_lcd
    _deploy_standalone_lcd = False
    if was_deploy:
        lcd_refresh(force=True)

    if key == "noop":
        return ""

    if key in ("hw_report", "hw_info", "boot_report"):
        _report_hardware_to_host(boot_footer=False)
        return "OK hw_report"

    if key == "safe":
        _coils_stop_pwm_safe("Host SAFE button")
        lcd_refresh(force=True)
        return "OK SAFE"

    if key in ("safe_reset", "reset_safe"):
        # Same coil / bridge shutdown as `safe`: all IN1 PWM duty 0, enables cleared, set_*_v zeroed.
        _coils_stop_pwm_safe("Host safe_reset")
        lcd_refresh(force=True)
        return "OK safe_reset"

    if u == "PING":
        return "PONG"

    if key in ("version", "fw_version", "gui_status"):
        return "OK VERSION %s" % VERSION

    if key == "set_x_v":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        set_X_v = max(0.0, min(_v_cmd_max(), float(v)))
        _apply_voltage_commands()
        return "OK set_x_v %.3f" % set_X_v
    if key == "set_y_v":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        set_Y_v = max(0.0, min(_v_cmd_max(), float(v)))
        _apply_voltage_commands()
        return "OK set_y_v %.3f" % set_Y_v
    if key == "set_z_v":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        set_Z_v = max(0.0, min(_v_cmd_max(), float(v)))
        _apply_voltage_commands()
        return "OK set_z_v %.3f" % set_Z_v

    if key == "enable_x":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        on = int(v) != 0
        _host_enable[0] = on
        if not on:
            set_X_v = 0.0
        _apply_voltage_commands()
        return "OK enable_x %d" % (1 if on else 0)
    if key == "enable_y":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        on = int(v) != 0
        _host_enable[1] = on
        if not on:
            set_Y_v = 0.0
        _apply_voltage_commands()
        return "OK enable_y %d" % (1 if on else 0)
    if key == "enable_z":
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        on = int(v) != 0
        _host_enable[2] = on
        if not on:
            set_Z_v = 0.0
        _apply_voltage_commands()
        return "OK enable_z %d" % (1 if on else 0)

    return "ERR unknown"


def _hex_list(addrs):
    if not addrs:
        return "[]"
    return "[" + ", ".join("0x%02x" % int(a) for a in sorted(addrs)) + "]"


def _report_hardware_to_host(boot_footer=True):
    global _host_txt_burst_active
    _host_txt_burst_active = True
    try:
        _report_hardware_to_host_body(boot_footer)
    finally:
        _host_txt_burst_active = False


def _report_hardware_to_host_body(boot_footer=True):
    host_print("OK VERSION %s" % VERSION)
    host_print(
        "CoilDriver 5.x slave — set_x_v set_y_v set_z_v + enables; TM:: ≤30 Hz (now %.1f Hz) filtered INA (no PI)"
        % SLAVE_TM_HZ
    )
    host_print(
        "  Voltage mode: hardware PWM duty = set_*_v / COIL_VOLTAGE_REF_VM_V when enabled; freq = PWM_FREQ_HZ."
    )
    host_print("Stop: host safe / estop / host_disconnect / back -> deploy-ready; not latched.")

    egp = int(getattr(config, "HARDWARE_ESTOP_GP", 0))
    edb = int(getattr(config, "HARDWARE_ESTOP_DEBOUNCE_MS", 80))
    if egp > 0:
        host_print(
            "Hardware estop: GP%d (NO to GND), pull-up; press -> coils_off; debounce %d ms"
            % (egp, edb)
        )
    else:
        host_print("Hardware estop: off (HARDWARE_ESTOP_GP=0)")

    bgp = int(getattr(config, "BACK_BUTTON_GP", 0))
    bdeb = max(40, int(getattr(config, "BACK_BUTTON_DEBOUNCE_MS", 80)))
    if bgp > 0 and bgp != egp:
        host_print(
            "Back button: GP%d -> deploy-ready if down at boot or held >= %d ms"
            % (bgp, bdeb)
        )
    else:
        host_print("Back button: off (BACK_BUTTON_GP=0 or same as estop)")

    i2c_id = int(getattr(config, "I2C_ID", 0))
    sda = int(getattr(config, "I2C_SDA", 4))
    scl = int(getattr(config, "I2C_SCL", 5))
    freq = int(getattr(config, "I2C_FREQ_HZ", 100_000))
    ina_addr = int(getattr(config, "INA3221_ADDRESS", 0x40))
    rsh = float(getattr(config, "INA3221_SHUNT_OHMS", 0.1))
    order = _axis_order()
    host_print("--- INA3221 ---")
    host_print("  Bus I2C%d SDA=GP%d SCL=GP%d %d Hz" % (i2c_id, sda, scl, freq))
    host_print("  Address 0x%02x; R_shunt = %.4f Ohm" % (ina_addr, rsh))
    host_print(
        "  Logical axes: INA3221 ch%u,%u,%u -> X,Y,Z"
        % (order[0], order[1], order[2])
    )
    if mon is not None:
        host_print("  Driver: OK")
        host_print(
            "  Last TM mA EMA (ch0,ch1,ch2): %.3f %.3f %.3f"
            % (_last_slave_i012[0], _last_slave_i012[1], _last_slave_i012[2])
        )
    else:
        host_print("  Driver: not active (expect 0x%02x)" % ina_addr)

    host_print("--- LCD ---")
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
        host_print("  LCD: OK at 0x%02x" % lcd_i2c_addr_used)
    else:
        host_print("  LCD: not opened")

    hb = str(getattr(config, "H_BRIDGE_MODEL", "H-bridge"))
    pwm_hz = int(getattr(config, "PWM_FREQ_HZ", 20_000))
    hw = str(getattr(config, "COIL_DRIVER_HW", "model_y"))
    if hw == "drv8871_3ch":
        in1 = getattr(config, "DRV8871_IN1_PWM_PINS", (10, 12, 14))
        in2 = getattr(config, "DRV8871_IN2_PINS", (11, 13, 15))
        host_print("--- Coil drivers (%s) ---" % hb)
        host_print(
            "  DRV8871 IN1 hardware PWM %d Hz — X=GP%u Y=GP%u Z=GP%u"
            % (pwm_hz, in1[0], in1[1], in1[2])
        )
        host_print(
            "  IN2 low — X=GP%u Y=GP%u Z=GP%u"
            % (in2[0], in2[1], in2[2])
        )
    else:
        p_en = getattr(config, "PWM_EN_PINS", (10, 12, 14))
        host_print("--- Coil drivers (%s) ---" % hb)
        host_print(
            "  PWM %d Hz — X=GP%u Y=GP%u Z=GP%u"
            % (pwm_hz, p_en[0], p_en[1], p_en[2])
        )
    pwm_ok = []
    for i in range(3):
        pwm_ok.append("OK" if i < len(pwms) and pwms[i] is not None else "FAIL")
    host_print("  PWM init: X=%s Y=%s Z=%s" % (pwm_ok[0], pwm_ok[1], pwm_ok[2]))
    host_print(
        "  COIL_VOLTAGE_REF_VM_V=%.3f COIL_VOLTAGE_COMMAND_MAX_V=%.3f"
        % (_vm_ref_v(), _v_cmd_max())
    )

    if boot_footer:
        host_print("Bridge outputs off (0 V command); entering main loop.")
        host_print("READY")
        host_print("STATUS CONNECTED")
    else:
        host_print("— end hw_report —")


def main():
    global _back_deploy_fired
    _init_lcd()
    _init_hardware_estop()
    boot_back = _init_hardware_back_button()
    if boot_back:
        _apply_deploy_ready_coils_off(status_tag="boot_back_button")
        _back_deploy_fired = True
        host_print("STATUS boot: back button down -> DEPLOY_READY (skipped splash)")
    else:
        _show_boot_lcd_splash()
    _pwm_all_off()
    _report_hardware_to_host()
    lcd_refresh(force=True)

    tim_slave = Timer(-1)
    tim_slave.init(
        mode=Timer.PERIODIC,
        period=SLAVE_TIMER_PERIOD_MS,
        callback=_slave_timer_tick,
    )
    host_print(
        "STATUS slave timer(-1) %d ms tick; INA sample ≥%d ms EMA α=%.2f; TM %.1f Hz (cap 30)"
        % (
            SLAVE_TIMER_PERIOD_MS,
            INA3221_SAMPLE_MIN_MS,
            INA3221_FILTER_ALPHA,
            SLAVE_TM_HZ,
        )
    )

    try:
        while True:
            line = sys.stdin.readline()
            if line:
                resp = handle_line(line)
                if resp:
                    host_print(resp)
    finally:
        try:
            tim_slave.deinit()
        except Exception:
            pass
        for i in range(len(pwms)):
            if pwms[i]:
                try:
                    pwms[i].duty_u16(0)
                except Exception:
                    pass


if __name__ == "__main__":
    main()
