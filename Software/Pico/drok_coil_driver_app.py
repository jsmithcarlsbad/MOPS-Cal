# drok_coil_driver_app.py — One XY6020L (Modbus) + 2-ch relays + SAFE/Operate per Pico (DROK_MODS.md).
# Identical firmware on X/Y/Z enclosures; per-unit axis label and LCD I2C address from axis_config.ini on flash.
# TM:: includes measured_ma / measured_vdc (DROK output), drok_cc_led=0|1|2 for host CC LEDs. "?" returns controlled axis name + VERSION.
# DROK_CC_MODE (config.py): set_x_v/set_y_v/set_z_v value is **coil current mA**; firmware sets I_SET from mA and
# V_SET = DROK_CC_V_HEADROOM * (mA/1000) * DROK_COIL_R_OHMS so the module can run in CC. Otherwise set_*_v is volts (CV-style).
# DROK-native lines: set_vdc / set_ma / set_power ON|OFF + get_* (see hw_report). set_vdc is ERR when DROK_CC_MODE is on.
# LCD: ESTOP / INFO / lcd_clear / host_operate. Relays: relay_1|relay_2 ON|OFF, set_pol POS|NEG, get_pol (DROK off first), get_relays, get_status.
import sys
import time
import micropython
from machine import I2C, Pin, UART, Timer

import config

VERSION_MAJOR = 6
VERSION_MINOR = 2
VERSION = "%d.%d" % (VERSION_MAJOR, VERSION_MINOR)

# XY6020L holding register indices (0-based), 0.01 V / 0.01 A LSB where applicable — see tinkering4fun / Jens3382 xy6020l.h.
HREG_V_SET = 0
HREG_I_SET = 1
HREG_V_OUT = 2
HREG_I_OUT = 3
HREG_ACT_P = 4
HREG_V_IN = 5
HREG_TEMP = 0x0D
HREG_PROTECT = 0x10
HREG_OUTPUT_ON = 0x12
HREG_MODEL = 0x16
HREG_VERSION = 0x17
# Preset memory CD0..CD9: base 0x50 + slot*0x10, 14 words (Jens3382 xy6020l.h). OVP/OCP are centi‑V / centi‑A.
HREG_PRESET_BASE = 0x50
HREG_PRESET_STRIDE = 0x10
PRESET_NREGS = 14
PRESET_MEM_OVP = 3
PRESET_MEM_OCP = 4

SLAVE_TM_HZ = float(getattr(config, "SLAVE_TM_HZ", 10.0))
SLAVE_TM_HZ = max(0.5, min(30.0, SLAVE_TM_HZ))
SLAVE_TM_PERIOD_MS = int(max(1, round(1000.0 / SLAVE_TM_HZ)))
_POLL = int(getattr(config, "SLAVE_POLL_MS", 50))
_tp = max(10, min(100, _POLL))
SLAVE_TIMER_PERIOD_MS = max(10, min(_tp, SLAVE_TM_PERIOD_MS))

_host_txt_burst_active = False


def host_print(*args):
    print("TXT:: " + " ".join(str(a) for a in args))


def _scheduled_line(arg):
    global _host_txt_burst_active
    if _host_txt_burst_active:
        return
    try:
        print(arg)
    except Exception:
        pass


def _crc16_modbus(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


class XY6020Modbus:
    def __init__(self, uart, slave, inter_ms, rx_timeout_ms):
        self.uart = uart
        self.slave = int(slave) & 0xFF
        self.inter_ms = max(20, int(inter_ms))
        self.rx_timeout_ms = max(30, int(rx_timeout_ms))
        self._last_tx_ms = 0
        self.last_exception_code = None

    def _wait_inter(self):
        now = time.ticks_ms()
        if self._last_tx_ms is not None:
            dt = time.ticks_diff(now, self._last_tx_ms)
            if dt < self.inter_ms:
                time.sleep_ms(self.inter_ms - dt)

    def _drain_rx(self):
        try:
            while self.uart.any():
                self.uart.read()
        except Exception:
            pass

    def _write_frame(self, pdu_tail):
        self._wait_inter()
        self._drain_rx()
        body = bytearray([self.slave]) + pdu_tail
        c = _crc16_modbus(body)
        body.append(c & 0xFF)
        body.append((c >> 8) & 0xFF)
        self.uart.write(body)
        self._last_tx_ms = time.ticks_ms()

    def _read_response(self, expect_fc):
        t0 = time.ticks_ms()
        buf = bytearray()
        while time.ticks_diff(time.ticks_ms(), t0) < self.rx_timeout_ms:
            if self.uart.any():
                buf += self.uart.read()
                if len(buf) >= 5:
                    if buf[0] != self.slave:
                        return None
                    if buf[1] & 0x80:
                        try:
                            self.last_exception_code = (
                                int(buf[2]) if len(buf) > 2 else None
                            )
                        except Exception:
                            self.last_exception_code = None
                        return None
                    if buf[1] != expect_fc:
                        return None
                    if expect_fc == 0x03:
                        bc = buf[2]
                        need = 5 + bc
                        if len(buf) >= need:
                            frame = buf[:need]
                            c_rx = frame[-2] | (frame[-1] << 8)
                            c_ok = _crc16_modbus(frame[:-2])
                            if c_rx == c_ok:
                                return frame
                            return None
                    elif expect_fc == 0x06:
                        need = 8
                        if len(buf) >= need:
                            frame = buf[:need]
                            c_rx = frame[-2] | (frame[-1] << 8)
                            c_ok = _crc16_modbus(frame[:-2])
                            if c_rx == c_ok:
                                return frame
                            return None
                    elif expect_fc == 0x10:
                        need = 8
                        if len(buf) >= need:
                            frame = buf[:need]
                            c_rx = frame[-2] | (frame[-1] << 8)
                            c_ok = _crc16_modbus(frame[:-2])
                            if c_rx == c_ok:
                                return frame
                            return None
            time.sleep_ms(1)
        return None

    def read_holding(self, start_reg, count):
        self.last_exception_code = None
        if count < 1 or count > 40:
            return None
        hi = (start_reg >> 8) & 0xFF
        lo = start_reg & 0xFF
        nhi = (count >> 8) & 0xFF
        nlo = count & 0xFF
        self._write_frame(bytearray([0x03, hi, lo, nhi, nlo]))
        resp = self._read_response(0x03)
        if resp is None:
            return None
        bc = resp[2]
        data = resp[3 : 3 + bc]
        if len(data) != bc or bc != count * 2:
            return None
        out = []
        for i in range(0, len(data), 2):
            out.append(data[i] << 8 | data[i + 1])
        return out

    def write_single(self, reg, value):
        self.last_exception_code = None
        hi = (reg >> 8) & 0xFF
        lo = reg & 0xFF
        v = int(value) & 0xFFFF
        vhi = (v >> 8) & 0xFF
        vlo = v & 0xFF
        self._write_frame(bytearray([0x06, hi, lo, vhi, vlo]))
        resp = self._read_response(0x06)
        if resp is None:
            return False
        return list(resp[2:6]) == [hi, lo, vhi, vlo]

    def write_multiple(self, start_reg, values):
        self.last_exception_code = None
        n = len(values)
        if n < 1 or n > 40:
            return False
        hi = (start_reg >> 8) & 0xFF
        lo = start_reg & 0xFF
        nhi = (n >> 8) & 0xFF
        nlo = n & 0xFF
        bcount = n * 2
        pdu = bytearray([0x10, hi, lo, nhi, nlo, bcount])
        for v in values:
            vi = int(v) & 0xFFFF
            pdu.append((vi >> 8) & 0xFF)
            pdu.append(vi & 0xFF)
        self._write_frame(pdu)
        resp = self._read_response(0x10)
        if resp is None or len(resp) < 8:
            return False
        return list(resp[2:6]) == [hi, lo, nhi, nlo]


# --- axis_config.ini ---
_controlled_axis = str(getattr(config, "DROK_CONTROLLED_AXIS_DEFAULT", "X COIL")).strip()
_lcd_addr_override = None


def _parse_axis_ini_line(line):
    global _controlled_axis, _lcd_addr_override
    s = (line or "").strip()
    if not s or s.startswith("#") or "=" not in s:
        return
    k, v = s.split("=", 1)
    k = k.strip().lower().replace(" ", "_")
    v = v.strip()
    if k in ("controlled_axis", "axis", "controlledaxis"):
        _controlled_axis = v
    elif k in ("lcd_i2c_addr", "lcd_addr", "lcd_address"):
        vs = v.lower().strip()
        try:
            if vs.startswith("0x"):
                _lcd_addr_override = int(vs, 16)
            else:
                _lcd_addr_override = int(vs, 10)
        except ValueError:
            pass


def load_axis_config():
    global _controlled_axis, _lcd_addr_override
    _controlled_axis = str(getattr(config, "DROK_CONTROLLED_AXIS_DEFAULT", "X COIL")).strip()
    _lcd_addr_override = None
    fn = str(getattr(config, "DROK_AXIS_CONFIG_FILENAME", "axis_config.ini"))
    try:
        with open(fn, "r") as f:
            for line in f:
                _parse_axis_ini_line(line)
    except OSError:
        pass


def _axis_letter():
    s = (_controlled_axis or "").strip().upper()
    if not s:
        return "X"
    c = s[0]
    if c in ("X", "Y", "Z"):
        return c
    return "X"


# --- runtime ---
mb = None
uart_drok = None
relay1 = None
relay2 = None
_safe_pin = None
_back_pin = None

_last_mb_regs = None
_last_mb_ok_ms = None
_last_host_rx_ms = None
_deploy_standalone_lcd = False
_back_press_t0_ms = None
_back_deploy_fired = False
_back_last_edge_ms = None

set_v = 0.0
# When config.DROK_CC_MODE: last commanded coil current target (mA) for CC setpoint; set_*_v host lines carry mA.
_cc_target_ma = 0.0
_host_enable = False
_drok_output_on = False

_last_tm_emit_ms = None
_lcd = None
_lcd_i2c_addr_used = None
_lcd_bus_instance = None
_last_lcd_ms = 0
_lcd_prev_layout = None
_lcd_write_err_logged = False
_lcd_refresh_err_logged = False
_safe_asserted = False

# ("estop", l1, l2) with host ESTOP+SAFE; ("info", l1, l2) for operator messages (see ESTOP / INFO / LCD_CLEAR).
_lcd_override = None

_mb_fail_streak = 0
_last_comm_alarm_ms = None
_last_protect_alarm_raw = None


def _emit_alarm(code, text_ascii):
    """Host-visible fault line (not TXT::). GUI should parse ALARM + hex + short text."""
    t = (text_ascii or "unknown").replace(" ", "_")
    try:
        print("ALARM 0x%04X %s" % (int(code) & 0xFFFF, t))
    except Exception:
        pass


def _preset_start():
    slot = int(getattr(config, "DROK_PRESET_SLOT", 0))
    slot = max(0, min(9, slot))
    return HREG_PRESET_BASE + slot * HREG_PRESET_STRIDE


def _read_preset14():
    if mb is None:
        return None
    return mb.read_holding(_preset_start(), PRESET_NREGS)


def _write_preset14(words):
    if mb is None or len(words) != PRESET_NREGS:
        return False
    return mb.write_multiple(_preset_start(), words)


def _apply_preset14_words(words):
    """Write full preset block; briefly drop DROK output (relay sequencing per DROK_MODS)."""
    if len(words) != PRESET_NREGS:
        return False
    was_on = _drok_output_on
    _drok_force_output_off()
    time.sleep_ms(int(getattr(config, "DROK_PRESET_WRITE_SETTLE_MS", 40)))
    ok = _write_preset14(words)
    if was_on and (not _is_safe()) and (not _safe_asserted) and _host_enable:
        try:
            _apply_voltage_to_drok()
        except Exception:
            pass
    return ok


def _check_alarms():
    global _last_comm_alarm_ms, _last_protect_alarm_raw
    now = time.ticks_ms()
    if _mb_fail_streak >= 3:
        if _last_comm_alarm_ms is None or time.ticks_diff(now, _last_comm_alarm_ms) > 10000:
            _emit_alarm(0x8001, "modbus_no_response")
            _last_comm_alarm_ms = now
    if (
        _mb_fail_streak == 0
        and _last_mb_regs is not None
        and len(_last_mb_regs) > HREG_PROTECT
    ):
        try:
            pr = int(_last_mb_regs[HREG_PROTECT])
        except Exception:
            pr = 0
        if pr != 0:
            if _last_protect_alarm_raw != pr:
                _emit_alarm(0x8200, "drok_protect_reg=0x%04X" % pr)
                _last_protect_alarm_raw = pr
        else:
            _last_protect_alarm_raw = None


def _relay_pins_off():
    global relay1, relay2
    for p in (relay1, relay2):
        if p is not None:
            try:
                p.value(1)
            except Exception:
                pass


def _init_uart_modbus():
    global mb, uart_drok
    mb = None
    uart_drok = None
    uid = int(getattr(config, "DROK_UART_ID", 0))
    tx = int(getattr(config, "DROK_UART_TX_PIN", 0))
    rx = int(getattr(config, "DROK_UART_RX_PIN", 1))
    baud = int(getattr(config, "DROK_UART_BAUD", 115200))
    slave = int(getattr(config, "DROK_MODBUS_SLAVE", 1))
    inter = int(getattr(config, "DROK_MODBUS_INTER_FRAME_MS", 55))
    rxt = int(getattr(config, "DROK_MODBUS_RX_TIMEOUT_MS", 220))
    try:
        uart_drok = UART(uid, baudrate=baud, tx=Pin(tx), rx=Pin(rx), bits=8, parity=None, stop=1)
        mb = XY6020Modbus(uart_drok, slave, inter, rxt)
        host_print("STATUS DROK UART id=%u tx=GP%u rx=GP%u %u baud slave=%u" % (uid, tx, rx, baud, slave))
    except Exception as e:
        uart_drok = None
        mb = None
        host_print("STATUS DROK UART init ERR:", e)


def _init_relays():
    global relay1, relay2
    relay1 = None
    relay2 = None
    g1 = int(getattr(config, "DROK_RELAY_IN1_PIN", 10))
    g2 = int(getattr(config, "DROK_RELAY_IN2_PIN", 11))
    try:
        relay1 = Pin(g1, Pin.OUT)
        relay1.value(1)
    except Exception as e:
        host_print("STATUS relay1 GP%u ERR:" % g1, e)
    try:
        relay2 = Pin(g2, Pin.OUT)
        relay2.value(1)
    except Exception as e:
        host_print("STATUS relay2 GP%u ERR:" % g2, e)


def _drok_output_on_from_regs_or_flag():
    if _last_mb_regs is not None and len(_last_mb_regs) > HREG_OUTPUT_ON:
        try:
            return int(_last_mb_regs[HREG_OUTPUT_ON]) != 0
        except Exception:
            pass
    return bool(_drok_output_on)


def _relay_pre_toggle_drok_off():
    """Prefer DROK output off before relay transitions (DROK_MODS §1)."""
    if not _drok_output_on_from_regs_or_flag():
        return
    _drok_force_output_off()
    time.sleep_ms(int(getattr(config, "DROK_RELAY_PRE_TOGGLE_MS", 50)))


def _relay_pin_energized(pin):
    if pin is None:
        return False
    try:
        return pin.value() == 0
    except Exception:
        return False


def _relay_set_channel(which, energized):
    """which 1 or 2 → IN1/IN2; energized True = GPIO LOW (active-low relay inputs)."""
    if _is_safe() or _safe_asserted:
        return "ERR safe"
    pin = relay1 if int(which) == 1 else relay2
    if pin is None:
        return "ERR relay_missing"
    _relay_pre_toggle_drok_off()
    try:
        pin.value(0 if energized else 1)
    except Exception as e:
        return "ERR relay " + str(e)
    return "OK"


def _pol_pattern(which):
    """which 'pos' or 'neg' → (energized_r1, energized_r2) from config."""
    if which == "pos":
        e1 = int(getattr(config, "DROK_SET_POL_POS_R1", 0)) != 0
        e2 = int(getattr(config, "DROK_SET_POL_POS_R2", 0)) != 0
    else:
        e1 = int(getattr(config, "DROK_SET_POL_NEG_R1", 1)) != 0
        e2 = int(getattr(config, "DROK_SET_POL_NEG_R2", 0)) != 0
    return (e1, e2)


def _relay_set_pattern(e1, e2):
    """Set both relay optos in one step (single DROK-off pause if anything changes)."""
    if _is_safe() or _safe_asserted:
        return "ERR safe"
    if relay1 is None or relay2 is None:
        return "ERR relay_missing"
    c1 = _relay_pin_energized(relay1)
    c2 = _relay_pin_energized(relay2)
    if c1 == e1 and c2 == e2:
        return "OK"
    _relay_pre_toggle_drok_off()
    try:
        relay1.value(0 if e1 else 1)
        relay2.value(0 if e2 else 1)
    except Exception as e:
        return "ERR relay " + str(e)
    return "OK"


def _current_pol_label():
    if relay1 is None or relay2 is None:
        return "MISSING"
    cur = (_relay_pin_energized(relay1), _relay_pin_energized(relay2))
    if cur == _pol_pattern("pos"):
        return "POS"
    if cur == _pol_pattern("neg"):
        return "NEG"
    return "MIXED"


def _mb_snapshot_fresh():
    if _last_mb_ok_ms is None:
        return 0
    if time.ticks_diff(time.ticks_ms(), _last_mb_ok_ms) < 2000:
        return 1
    return 0


def _lcd_i2c_bus():
    global _lcd_bus_instance
    lid = int(getattr(config, "LCD_I2C_ID", 1))
    lsda = int(getattr(config, "LCD_I2C_SDA", 2))
    lscl = int(getattr(config, "LCD_I2C_SCL", 3))
    freq_lcd = int(getattr(config, "LCD_I2C_FREQ_HZ", 100_000))
    if _lcd_bus_instance is not None:
        return _lcd_bus_instance
    try:
        _lcd_bus_instance = I2C(lid, sda=Pin(lsda), scl=Pin(lscl), freq=freq_lcd)
        return _lcd_bus_instance
    except Exception:
        return None


def _init_lcd():
    global _lcd, _lcd_i2c_addr_used
    _lcd = None
    _lcd_i2c_addr_used = None
    want = int(_lcd_addr_override) if _lcd_addr_override is not None else int(
        getattr(config, "LCD_I2C_ADDR", 0x27)
    )
    try:
        from I2C_LCD import I2CLcd

        retries = int(getattr(config, "LCD_INIT_RETRIES", 4))
        for attempt in range(max(1, retries)):
            bus = _lcd_i2c_bus()
            if bus is None:
                host_print("STATUS LCD no I2C bus")
                return
            time.sleep_ms(50)
            found = bus.scan()
            host_print("STATUS LCD scan", [hex(x) for x in found], "try", attempt + 1)
            cands = [a for a in found if a in (0x27, 0x3F)]
            if want in cands:
                addr = want
            elif cands:
                addr = cands[0]
            else:
                time.sleep_ms(150)
                continue
            try:
                _lcd = I2CLcd(bus, addr, 2, 16)
                _lcd_i2c_addr_used = addr
                return
            except Exception as e:
                _lcd = None
                host_print("STATUS LCD I2CLcd ERR:", e)
                time.sleep_ms(150)
        host_print("STATUS LCD failed after retries")
    except Exception as e:
        host_print("STATUS LCD init ERR:", e)


def _lcd_sanitize_ascii(s):
    out = []
    for ch in (s or ""):
        c = ord(ch)
        if 32 <= c <= 126:
            out.append(ch)
        else:
            out.append(" ")
        if len(out) >= 16:
            break
    return "".join(out)


def _lcd_center_16(text):
    s = _lcd_sanitize_ascii(text or "")
    L = len(s)
    if L >= 16:
        return s
    pad = 16 - L
    left = pad // 2
    return (" " * left) + s + (" " * (pad - left))


def _lcd_line1():
    return _lcd_sanitize_ascii(_controlled_axis or "? AXIS")


def _split_two_host_lines(rest, default_line1, default_line2):
    """Parse `line1|line2` (pipe). Rest is text after the command word. Each line is 16 chars, centered."""
    s = (rest or "").strip()
    if not s:
        return _lcd_center_16(default_line1), _lcd_center_16(default_line2)
    if s.startswith("|"):
        s = s[1:]
    parts = s.split("|", 1)
    if len(parts) == 2:
        return _lcd_center_16(parts[0]), _lcd_center_16(parts[1])
    return _lcd_center_16(s), _lcd_center_16(default_line2)


def _lcd_put_row(row, text):
    global _lcd_write_err_logged, _lcd
    if _lcd is None:
        return
    s = _lcd_center_16(text)
    try:
        _lcd.move_to(0, row)
        _lcd.putstr(s)
    except Exception as e:
        if not _lcd_write_err_logged:
            _lcd_write_err_logged = True
            host_print("STATUS LCD write ERR:", e)


def _lcd_clear():
    if _lcd is None:
        return
    try:
        _lcd.clear()
    except Exception:
        pass


def _lcd_refresh_period_ms():
    return max(100, int(getattr(config, "LCD_REFRESH_MS", 100)))


def lcd_refresh(force=False):
    global _last_lcd_ms, _lcd_prev_layout, _lcd, _lcd_refresh_err_logged, _safe_asserted
    if _lcd is None:
        return
    period = _lcd_refresh_period_ms()
    now = time.ticks_ms()
    if not force and time.ticks_diff(now, _last_lcd_ms) < period:
        return
    _last_lcd_ms = now
    try:
        try:
            _lcd.display_on()
        except Exception:
            pass
        if _deploy_standalone_lcd:
            if _lcd_prev_layout is not None and _lcd_prev_layout != "d":
                _lcd_clear()
            _lcd_put_row(0, "READY FOR")
            _lcd_put_row(1, "DEPLOYMENT")
            _lcd_prev_layout = "d"
            return
        if _safe_asserted:
            if _lcd_override and _lcd_override[0] == "estop":
                _lcd_put_row(0, _lcd_override[1])
                _lcd_put_row(1, _lcd_override[2])
            else:
                _lcd_put_row(0, "SAFE")
                _lcd_put_row(1, "OUTPUT OFF")
            _lcd_prev_layout = "s"
            return
        if _lcd_override and _lcd_override[0] == "info":
            if _lcd_prev_layout is not None and _lcd_prev_layout != "i":
                _lcd_clear()
            _lcd_put_row(0, _lcd_override[1])
            _lcd_put_row(1, _lcd_override[2])
            _lcd_prev_layout = "i"
            return
        layout = "n"
        if _lcd_prev_layout is not None and _lcd_prev_layout != layout:
            _lcd_clear()
        _lcd_put_row(0, _lcd_line1())
        _lcd_put_row(1, "Ver.%s" % VERSION)
        _lcd_prev_layout = layout
    except Exception as e:
        if not _lcd_refresh_err_logged:
            _lcd_refresh_err_logged = True
            host_print("STATUS LCD refresh ERR:", e)


def _show_boot_lcd_splash():
    if _lcd is None:
        return
    splash_s = float(getattr(config, "BOOT_LCD_SPLASH_S", 5.0))
    if splash_s <= 0:
        return
    try:
        try:
            _lcd.display_on()
        except Exception:
            pass
        _lcd_clear()
        _lcd_put_row(0, _lcd_line1())
        _lcd_put_row(1, "Ver.%s" % VERSION)
        time.sleep(splash_s)
    except Exception:
        pass


def _drok_force_output_off():
    global _drok_output_on
    if mb is None:
        _drok_output_on = False
        return
    try:
        mb.write_single(HREG_OUTPUT_ON, 0)
    except Exception:
        pass
    _drok_output_on = False


def _apply_safe_hardware(reason):
    global _host_enable, set_v, _safe_asserted, _lcd_override, _cc_target_ma
    if _lcd_override and _lcd_override[0] == "info":
        _lcd_override = None
    _safe_asserted = True
    _host_enable = False
    set_v = 0.0
    _cc_target_ma = 0.0
    _drok_force_output_off()
    _relay_pins_off()
    host_print("STATUS SAFE —", reason)


def _clear_safe_if_operate():
    global _safe_asserted, _lcd_override
    if _safe_pin is None:
        return
    try:
        if _safe_pin.value() == 0:
            if _lcd_override and _lcd_override[0] == "estop":
                _lcd_override = None
            _safe_asserted = False
    except Exception:
        pass


def _is_safe():
    if _safe_pin is None:
        return False
    try:
        return _safe_pin.value() != 0
    except Exception:
        return False


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


def _i_set_centi_max():
    lim_a = float(getattr(config, "DROK_I_SET_LIMIT_A", 8.0))
    if lim_a <= 0 or lim_a != lim_a:
        lim_a = 8.0
    return int(min(2000, max(1, round(lim_a * 100.0))))


def _write_i_set_centi(centi_a):
    if mb is None:
        return False
    mx = _i_set_centi_max()
    c = int(max(0, min(int(centi_a), mx)))
    if c < 1:
        c = 1
    try:
        return bool(mb.write_single(HREG_I_SET, c))
    except Exception:
        return False


def _write_i_set_limit():
    _write_i_set_centi(_i_set_centi_max())


def _drok_cc_mode():
    return bool(getattr(config, "DROK_CC_MODE", False))


def _coil_r_ohm():
    r = float(getattr(config, "DROK_COIL_R_OHMS", 0.0))
    if r != r or r < 0.0:
        return 0.0
    return r


def _cc_v_headroom():
    h = float(getattr(config, "DROK_CC_V_HEADROOM", 1.2))
    if h != h or h < 1.0:
        return 1.2
    return h


def _i_centi_from_ma(ma_abs):
    """XY6020L I_SET LSB 0.01 A; host/set_ma use mA. Returns centi-units for register (>=1 when ma>0)."""
    ma_abs = float(ma_abs)
    if ma_abs <= 0.0:
        return 0
    return int(max(1, min(round(ma_abs / 10.0), _i_set_centi_max())))


def _drok_cc_apply_setpoints_ma(ma):
    """Write I_SET and V_SET for CC operation. ma = target coil current (mA). Updates global set_v to V ceiling (V)."""
    global set_v, _cc_target_ma
    _cc_target_ma = max(0.0, float(ma))
    if mb is None:
        return False
    if _cc_target_ma <= 0.0 or _cc_target_ma != _cc_target_ma:
        set_v = 0.0
        if not _write_i_set_centi(1):
            return False
        return _write_v_set_centi(0)
    r = _coil_r_ohm()
    if r <= 0.0:
        host_print("TXT:: ERR DROK_CC_MODE needs config.DROK_COIL_R_OHMS > 0")
        return False
    i_a = _cc_target_ma / 1000.0
    v = _cc_v_headroom() * i_a * r
    vmax = _v_cmd_max()
    if v > vmax:
        v = vmax
    set_v = v
    centi_v = int(min(6000, max(0, round(v * 100.0))))
    ci = _i_centi_from_ma(_cc_target_ma)
    if not _write_i_set_centi(ci):
        return False
    return _write_v_set_centi(centi_v)


def _drok_cc_sync_output():
    """After I_SET/V_SET written: turn DROK output on if host enabled and CC target > 0."""
    global _drok_output_on
    if mb is None or _is_safe():
        _drok_force_output_off()
        return
    if not _host_enable:
        _drok_force_output_off()
        return
    if _cc_target_ma <= 0.0:
        _drok_force_output_off()
        return
    try:
        if not mb.write_single(HREG_OUTPUT_ON, 1):
            _drok_output_on = False
        else:
            _drok_output_on = True
    except Exception:
        _drok_output_on = False


def _write_v_set_centi(centi_v):
    if mb is None:
        return False
    c = int(max(0, min(int(centi_v), 6000)))
    try:
        return bool(mb.write_single(HREG_V_SET, c))
    except Exception:
        return False


def _parse_power_on(rest):
    t = (rest or "").strip().upper()
    if t in ("ON", "1", "TRUE", "YES"):
        return True
    if t in ("OFF", "0", "FALSE", "NO", ""):
        return False
    return None


def _modbus_snapshot_or_err():
    if mb is None:
        return "ERR modbus"
    _poll_modbus_snapshot()
    if _last_mb_regs is None or len(_last_mb_regs) < 24:
        return "ERR modbus"
    return None


def _apply_voltage_to_drok():
    global _drok_output_on
    if mb is None or _is_safe():
        _drok_force_output_off()
        return
    if not _host_enable:
        _drok_force_output_off()
        return
    try:
        if _drok_cc_mode():
            if not _drok_cc_apply_setpoints_ma(_cc_target_ma):
                _drok_output_on = False
                return
            _drok_cc_sync_output()
            return
        vmax = _v_cmd_max()
        v = max(0.0, min(vmax, float(set_v)))
        centi_v = int(min(6000, max(0, round(v * 100.0))))
        if not _write_v_set_centi(centi_v):
            _drok_output_on = False
            return
        if not mb.write_single(HREG_OUTPUT_ON, 1):
            _drok_output_on = False
            return
        _drok_output_on = True
    except Exception:
        _drok_output_on = False


def _poll_modbus_snapshot():
    global _last_mb_regs, _last_mb_ok_ms, _mb_fail_streak
    if mb is None:
        return
    regs = mb.read_holding(0, 31)
    if regs is None or len(regs) < 31:
        regs = mb.read_holding(0, 24)
        if regs is None or len(regs) < 24:
            _mb_fail_streak += 1
            return
        regs = list(regs)
        while len(regs) < 31:
            regs.append(0)
    _mb_fail_streak = 0
    _last_mb_regs = regs
    _last_mb_ok_ms = time.ticks_ms()


def _regs_vout_iout():
    if _last_mb_regs is None or len(_last_mb_regs) < 4:
        return (float("nan"), float("nan"))
    try:
        vc = _last_mb_regs[HREG_V_OUT]
        ic = _last_mb_regs[HREG_I_OUT]
        return (vc * 0.01, ic * 0.01)
    except Exception:
        return (float("nan"), float("nan"))


def _measured_ma_vdc():
    va, ia = _regs_vout_iout()
    ma = (ia * 1000.0) if ia == ia else float("nan")
    return ma, va


def _apply_deploy_ready(status_tag=None, refresh_lcd=True):
    global _last_host_rx_ms, _deploy_standalone_lcd, _host_enable, set_v, _lcd_override, _cc_target_ma
    _lcd_override = None
    _host_enable = False
    set_v = 0.0
    _cc_target_ma = 0.0
    _last_host_rx_ms = None
    _deploy_standalone_lcd = True
    _drok_force_output_off()
    _relay_pins_off()
    msg = "STATUS DEPLOY_READY drok_off relays_open"
    if status_tag:
        msg += " " + str(status_tag)
    host_print(msg)
    if refresh_lcd:
        _lcd_clear()
        lcd_refresh(force=True)


def _safe_edge_scheduled(_):
    global _safe_asserted
    if _safe_pin is None:
        return
    if _is_safe():
        if not _safe_asserted:
            _apply_safe_hardware("Operate/SAFE -> SAFE")
            try:
                lcd_refresh(force=True)
            except Exception:
                pass
    else:
        was = _safe_asserted
        _safe_asserted = False
        if was:
            host_print("STATUS OPERATE (GP16 LOW) — host may command when enabled")
            try:
                lcd_refresh(force=True)
            except Exception:
                pass


def _safe_pin_irq(_pin):
    try:
        micropython.schedule(_safe_edge_scheduled, None)
    except Exception:
        pass


def _init_safe_switch():
    global _safe_pin
    _safe_pin = None
    gp = int(getattr(config, "HARDWARE_ESTOP_GP", 16))
    if gp <= 0:
        return
    try:
        _safe_pin = Pin(int(gp), Pin.IN, Pin.PULL_UP)
        _safe_pin.irq(handler=_safe_pin_irq, trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING)
        host_print(
            "STATUS Operate/SAFE GP%u pull-up — open=SAFE (DROK off) closed=Operate"
            % int(gp)
        )
    except Exception as e:
        _safe_pin = None
        host_print("STATUS SAFE switch init ERR:", e)


def _back_edge_scheduled(_):
    global _back_press_t0_ms, _back_deploy_fired, _back_last_edge_ms
    pin = _back_pin
    if pin is None:
        return
    now = time.ticks_ms()
    deb = max(40, int(getattr(config, "BACK_BUTTON_DEBOUNCE_MS", 80)))
    if _back_last_edge_ms is not None and time.ticks_diff(now, _back_last_edge_ms) < deb:
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


def _init_back_button():
    global _back_pin
    _back_pin = None
    gp = int(getattr(config, "BACK_BUTTON_GP", 0))
    if gp <= 0:
        return False
    sgp = int(getattr(config, "HARDWARE_ESTOP_GP", 0))
    if gp == sgp:
        host_print("STATUS BACK_BUTTON ignored (same GP as SAFE)")
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
        host_print("STATUS BACK_BUTTON GP%u hold -> deploy_ready" % int(gp))
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
    _apply_deploy_ready(status_tag="back_button_hold")


def _fmt_float(x, fmt="%.3f"):
    try:
        if x != x:
            return "nan"
        return fmt % x
    except Exception:
        return "nan"


def _drok_cc_led_tm_value(mb_ok, ma, vdc):
    """TM token drok_cc_led: 0=red (CC off / output off), 1=lime (regulating in CC), 2=yellow (CC not maintained)."""
    if not _drok_cc_mode():
        return 0
    if not mb_ok or (not _drok_output_on) or _cc_target_ma <= 0.0:
        return 0
    if ma != ma or vdc != vdc:
        return 2
    vset = float(set_v)
    i_tgt = float(_cc_target_ma)
    if vset < 0.03:
        return 0
    tol_ma = max(25.0, 0.10 * max(i_tgt, 1.0))
    v_fold = vset - vdc
    if v_fold > 0.06 and abs(ma - i_tgt) < tol_ma:
        return 1
    if vdc >= vset - 0.06:
        return 2
    if abs(ma - i_tgt) >= tol_ma:
        return 2
    return 2


def _emit_tm_scheduled(_):
    global _last_tm_emit_ms, _host_txt_burst_active
    if _host_txt_burst_active:
        return
    try:
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
        mb_ok = _mb_snapshot_fresh()
        ma, vdc = _measured_ma_vdc()
        ilim_ma = float("nan")
        if mb_ok and _last_mb_regs and len(_last_mb_regs) > HREG_I_SET:
            try:
                ilim_ma = float(_last_mb_regs[HREG_I_SET]) * 10.0
            except Exception:
                pass
        ax = _axis_letter()
        x_ma = ma if ax == "X" else 0.0
        y_ma = ma if ax == "Y" else 0.0
        z_ma = ma if ax == "Z" else 0.0
        cvx = vdc if ax == "X" else float("nan")
        cvy = vdc if ax == "Y" else float("nan")
        cvz = vdc if ax == "Z" else float("nan")
        safe_tok = 1 if (_is_safe() or _safe_asserted) else 0
        cc_led = _drok_cc_led_tm_value(mb_ok, ma, vdc)
        parts = [
            "meas_ok=%d" % mb_ok,
            "measured_ma=%s" % _fmt_float(ma, "%.1f"),
            "measured_vdc=%s" % _fmt_float(vdc, "%.3f"),
            "X_ma=%s" % _fmt_float(x_ma, "%.2f"),
            "Y_ma=%s" % _fmt_float(y_ma, "%.2f"),
            "Z_ma=%s" % _fmt_float(z_ma, "%.2f"),
            "set_X_v=%.3f" % (set_v if ax == "X" else 0.0),
            "set_Y_v=%.3f" % (set_v if ax == "Y" else 0.0),
            "set_Z_v=%.3f" % (set_v if ax == "Z" else 0.0),
            "closed_loop=0",
            "cfg=%d" % cfg,
            "safe=%d" % safe_tok,
            "ina_X_ch=0",
            "ina_Y_ch=1",
            "ina_Z_ch=2",
            "diag_Ch1_ma=%.2f" % x_ma,
            "diag_Ch2_ma=%.2f" % y_ma,
            "diag_Ch3_ma=%.2f" % z_ma,
            "coil_V_X=%s" % _fmt_float(cvx),
            "coil_V_Y=%s" % _fmt_float(cvy),
            "coil_V_Z=%s" % _fmt_float(cvz),
            "diag_X_duty=0",
            "diag_Y_duty=0",
            "diag_Z_duty=0",
            "alarm=0",
            "drok_axis=%s" % ax,
            "drok_cc_mode=%d" % (1 if _drok_cc_mode() else 0),
            "drok_cc_ma=%s" % _fmt_float(_cc_target_ma, "%.2f"),
            "drok_cc_led=%d" % int(cc_led),
            "drok_out=%d" % (1 if _drok_output_on else 0),
            "drok_i_limit_ma=%s" % _fmt_float(ilim_ma, "%.1f"),
            "relay_1=%d" % (1 if _relay_pin_energized(relay1) else 0),
            "relay_2=%d" % (1 if _relay_pin_energized(relay2) else 0),
            "coil_pol=%s" % _current_pol_label(),
        ]
        micropython.schedule(_scheduled_line, "TM:: " + " ".join(parts))
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
        _clear_safe_if_operate()
    except Exception:
        pass
    if _is_safe():
        if not _safe_asserted:
            _apply_safe_hardware("poll SAFE")
    try:
        _poll_modbus_snapshot()
    except Exception:
        pass
    try:
        _check_alarms()
    except Exception:
        pass
    if not _is_safe() and not _safe_asserted and _host_enable:
        try:
            _apply_voltage_to_drok()
        except Exception:
            pass
    elif not _is_safe() and not _safe_asserted and not _host_enable:
        try:
            _drok_force_output_off()
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


def _cmd_applies_to_us(key):
    ax = _axis_letter()
    if key in ("set_x_v", "enable_x"):
        return ax == "X"
    if key in ("set_y_v", "enable_y"):
        return ax == "Y"
    if key in ("set_z_v", "enable_z"):
        return ax == "Z"
    return False


def handle_line(line):
    global set_v, _last_host_rx_ms, _deploy_standalone_lcd, _host_enable, _cc_target_ma
    global _lcd_override, _safe_asserted

    s = (line or "").strip()
    if not s or s.startswith("TM::") or s.startswith("STATUS") or s.startswith("TXT::"):
        return ""

    if s == "?":
        return "OK AXIS %s VERSION %s" % (_controlled_axis, VERSION)

    parts = s.split(None, 1)
    cmd = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""
    key = cmd.lower()

    if key in ("host_disconnect", "abort", "shutdown", "calibration_stop"):
        _apply_deploy_ready()
        if key == "host_disconnect":
            return "OK host_disconnect"
        return "OK %s" % key

    if key == "alive":
        _last_host_rx_ms = time.ticks_ms()
        was = _deploy_standalone_lcd
        _deploy_standalone_lcd = False
        if was:
            lcd_refresh(force=True)
        return "OK ALIVE"

    _last_host_rx_ms = time.ticks_ms()
    was = _deploy_standalone_lcd
    _deploy_standalone_lcd = False
    if was:
        lcd_refresh(force=True)

    if key == "noop":
        return ""

    if key in ("help", "commands"):
        return (
            "OK help relay_1 relay_2 set_pol get_pol get_relays ESTOP INFO set_vdc set_ma set_power "
            "get_* set_ovp set_ocp get_status ? host_operate lcd_clear safe alive"
        )

    if key in ("hw_report", "hw_info", "boot_report"):
        _report_hardware_to_host(boot_footer=False)
        return "OK hw_report"

    if key in ("safe", "safe_reset", "reset_safe"):
        if _lcd_override and _lcd_override[0] == "estop":
            _lcd_override = None
        _apply_safe_hardware("Host SAFE")
        lcd_refresh(force=True)
        return "OK %s" % key

    if key == "estop":
        a, b = _split_two_host_lines(rest, "HOST ESTOP", "OUTPUT OFF")
        _lcd_override = ("estop", a, b)
        _apply_safe_hardware("Host ESTOP")
        lcd_refresh(force=True)
        return "OK ESTOP"

    if key == "info":
        t = (rest or "").strip()
        if not t:
            return "ERR args"
        a, b = _split_two_host_lines(t, "", "")
        if "|" not in t and not _lcd_sanitize_ascii(t):
            return "ERR args"
        _lcd_override = ("info", a, b)
        lcd_refresh(force=True)
        return "OK INFO"

    if key in ("lcd_clear", "info_clear", "clear_lcd"):
        _lcd_override = None
        lcd_refresh(force=True)
        return "OK lcd_clear"

    if key in ("host_operate", "clear_estop", "estop_clear"):
        if _is_safe():
            return "ERR physical_SAFE_open"
        _safe_asserted = False
        if _lcd_override and _lcd_override[0] == "estop":
            _lcd_override = None
        lcd_refresh(force=True)
        return "OK host_operate"

    if cmd.upper() == "PING":
        return "PONG"

    if key in ("version", "fw_version", "gui_status"):
        return "OK VERSION %s" % VERSION

    if key in ("set_x_v", "set_y_v", "set_z_v"):
        if not _cmd_applies_to_us(key):
            return "ERR wrong_axis"
        if _is_safe() or _safe_asserted:
            return "ERR safe"
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        if _drok_cc_mode():
            ma = max(0.0, float(v))
            if not _drok_cc_apply_setpoints_ma(ma):
                return "ERR modbus"
            _drok_cc_sync_output()
            return "OK %s %.3f" % (key, set_v)
        set_v = max(0.0, min(_v_cmd_max(), float(v)))
        centi = int(min(6000, max(0, round(set_v * 100.0))))
        if not _write_v_set_centi(centi):
            return "ERR modbus"
        if _host_enable:
            _apply_voltage_to_drok()
        return "OK %s %.3f" % (key, set_v)

    if key in ("enable_x", "enable_y", "enable_z"):
        if not _cmd_applies_to_us(key):
            return "ERR wrong_axis"
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        on = int(v) != 0
        if (_is_safe() or _safe_asserted) and on:
            return "ERR safe"
        _host_enable = on
        if not on:
            set_v = 0.0
            if _drok_cc_mode():
                _cc_target_ma = 0.0
            _drok_force_output_off()
        else:
            _apply_voltage_to_drok()
        return "OK %s %d" % (key, 1 if on else 0)

    if key == "set_vdc":
        if _drok_cc_mode():
            return "ERR cc_mode use set_x_v mA (DROK_CC_MODE)"
        if _is_safe() or _safe_asserted:
            return "ERR safe"
        v = _parse_float(rest, None)
        if v is None:
            return "ERR args"
        set_v = max(0.0, min(_v_cmd_max(), float(v)))
        centi = int(min(6000, max(0, round(set_v * 100.0))))
        if not _write_v_set_centi(centi):
            return "ERR modbus"
        if _host_enable:
            _apply_voltage_to_drok()
        return "OK set_vdc %.3f" % set_v

    if key == "set_ma":
        if _is_safe() or _safe_asserted:
            return "ERR safe"
        ma = _parse_float(rest, None)
        if ma is None:
            return "ERR args"
        if _drok_cc_mode():
            if not _drok_cc_apply_setpoints_ma(float(ma)):
                return "ERR modbus"
            _drok_cc_sync_output()
            return "OK set_ma %.2f" % max(0.0, float(ma))
        centi_a = int(max(1, min(round(float(ma) / 10.0), _i_set_centi_max())))
        if not _write_i_set_centi(centi_a):
            return "ERR modbus"
        return "OK set_ma %.2f" % (centi_a * 10.0)

    if key == "set_power":
        st = _parse_power_on(rest)
        if st is None:
            return "ERR args"
        if st and (_is_safe() or _safe_asserted):
            return "ERR safe"
        _host_enable = bool(st)
        if not st:
            set_v = 0.0
            if _drok_cc_mode():
                _cc_target_ma = 0.0
            _drok_force_output_off()
        else:
            _apply_voltage_to_drok()
        return "OK set_power %s" % ("ON" if st else "OFF")

    if key in ("relay_1", "rly1"):
        st = _parse_power_on(rest)
        if st is None:
            return "ERR args"
        er = _relay_set_channel(1, st)
        if er != "OK":
            return er
        return "OK relay_1 %s" % ("ON" if st else "OFF")

    if key in ("relay_2", "rly2"):
        st = _parse_power_on(rest)
        if st is None:
            return "ERR args"
        er = _relay_set_channel(2, st)
        if er != "OK":
            return er
        return "OK relay_2 %s" % ("ON" if st else "OFF")

    if key in ("set_pol", "set_polarity", "polarity"):
        tok = (rest or "").strip().upper()
        if tok in ("POS", "POSITIVE", "+"):
            which = "pos"
        elif tok in ("NEG", "NEGATIVE", "-"):
            which = "neg"
        else:
            return "ERR args"
        e1, e2 = _pol_pattern(which)
        er = _relay_set_pattern(e1, e2)
        if er != "OK":
            return er
        return "OK set_pol %s" % ("POS" if which == "pos" else "NEG")

    if key in ("get_pol", "get_polarity"):
        return "OK get_pol %s" % _current_pol_label()

    if key in ("get_relays", "relays"):
        a = _relay_pin_energized(relay1)
        b = _relay_pin_energized(relay2)
        return "OK get_relays relay_1=%s relay_2=%s" % (
            "ON" if a else "OFF",
            "ON" if b else "OFF",
        )

    if key in ("get_status", "status"):
        lcdov = "-"
        if _lcd_override:
            lcdov = _lcd_override[0]
        extra = ""
        if mb is not None and mb.last_exception_code is not None:
            extra = " mb_exc=%u" % int(mb.last_exception_code)
        return (
            "OK get_status axis=%s fw=%s phy_safe=%d host_safe=%d mb_ok=%d drok_out=%d "
            "relay_1=%s relay_2=%s coil_pol=%s lcd=%s deploy=%d%s"
            % (
                _axis_letter(),
                VERSION,
                1 if _is_safe() else 0,
                1 if _safe_asserted else 0,
                _mb_snapshot_fresh(),
                1 if _drok_output_on else 0,
                "ON" if _relay_pin_energized(relay1) else "OFF",
                "ON" if _relay_pin_energized(relay2) else "OFF",
                _current_pol_label(),
                lcdov,
                1 if _deploy_standalone_lcd else 0,
                extra,
            )
        )

    if key == "get_vdc":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        r = _last_mb_regs
        sv = r[HREG_V_SET] * 0.01
        ov = r[HREG_V_OUT] * 0.01
        return "OK get_vdc set_vdc=%.3f out_vdc=%.3f" % (sv, ov)

    if key == "get_ma":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        r = _last_mb_regs
        lim_ma = float(r[HREG_I_SET]) * 10.0
        out_ma = float(r[HREG_I_OUT]) * 10.0
        return "OK get_ma out_ma=%.1f limit_ma=%.1f" % (out_ma, lim_ma)

    if key == "get_power":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        on = int(_last_mb_regs[HREG_OUTPUT_ON]) != 0
        return "OK get_power %s" % ("ON" if on else "OFF")

    if key == "get_vin":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        vin = float(_last_mb_regs[HREG_V_IN]) * 0.01
        return "OK get_vin %.3f" % vin

    if key == "get_watts":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        w = float(_last_mb_regs[HREG_ACT_P]) * 0.1
        return "OK get_watts %.2f" % w

    if key == "get_temp":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        tc = float(_last_mb_regs[HREG_TEMP]) * 0.1
        return "OK get_temp %.1f" % tc

    if key == "get_supply_model":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        return "OK get_supply_model 0x%04X" % int(_last_mb_regs[HREG_MODEL])

    if key == "get_supply_version":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        return "OK get_supply_version 0x%04X" % int(_last_mb_regs[HREG_VERSION])

    if key == "set_ovp":
        if _is_safe() or _safe_asserted:
            return "ERR safe"
        fv = _parse_float(rest, None)
        if fv is None:
            return "ERR args"
        words = _read_preset14()
        if words is None or len(words) != PRESET_NREGS:
            return "ERR modbus"
        words = list(words)
        words[PRESET_MEM_OVP] = (
            int(max(0, min(6500, round(float(fv) * 100.0)))) & 0xFFFF
        )
        if not _apply_preset14_words(words):
            return "ERR modbus"
        return "OK set_ovp %.3f" % (words[PRESET_MEM_OVP] * 0.01)

    if key == "set_ocp":
        if _is_safe() or _safe_asserted:
            return "ERR safe"
        fa = _parse_float(rest, None)
        if fa is None:
            return "ERR args"
        words = _read_preset14()
        if words is None or len(words) != PRESET_NREGS:
            return "ERR modbus"
        words = list(words)
        centi = int(max(1, min(round(float(fa) * 100.0), _i_set_centi_max())))
        words[PRESET_MEM_OCP] = centi & 0xFFFF
        if not _apply_preset14_words(words):
            return "ERR modbus"
        return "OK set_ocp %.3f" % (words[PRESET_MEM_OCP] * 0.01)

    if key == "get_ovp":
        w = _read_preset14()
        if w is None or len(w) <= PRESET_MEM_OVP:
            return "ERR modbus"
        return "OK get_ovp %.3f" % (w[PRESET_MEM_OVP] * 0.01)

    if key == "get_ocp":
        w = _read_preset14()
        if w is None or len(w) <= PRESET_MEM_OCP:
            return "ERR modbus"
        return "OK get_ocp %.3f" % (w[PRESET_MEM_OCP] * 0.01)

    if key == "get_protect":
        er = _modbus_snapshot_or_err()
        if er:
            return er
        if len(_last_mb_regs) <= HREG_PROTECT:
            return "ERR modbus"
        return "OK get_protect 0x%04X" % int(_last_mb_regs[HREG_PROTECT])

    return "ERR unknown"


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
        "DROK: set_vdc set_ma set_power get_* set_ovp set_ocp get_ovp get_ocp get_protect "
        "(set_vdc disabled when DROK_CC_MODE)"
    )
    host_print(
        "LCD: ESTOP [line1|line2] INFO line1|line2 lcd_clear host_operate (physical SAFE closed)"
    )
    host_print(
        "Relay: relay_1 ON|OFF relay_2 ON|OFF set_pol POS|NEG get_pol get_relays "
        "(DROK output off before GPIO change)"
    )
    host_print("DROK single-axis — Modbus V/I; TM:: measured_ma measured_vdc; ? -> AXIS + VERSION")
    host_print("  controlled_axis=%r (ini or default)" % _controlled_axis)
    host_print("  axis_letter=%s TM maps mA/V to that axis only" % _axis_letter())
    if _drok_cc_mode():
        host_print(
            "  DROK_CC_MODE on: set_*_v / set_ma arg = coil mA; V_SET=%.3f*(mA/1000)*R Ω; R=%.4f Ω"
            % (_cc_v_headroom(), _coil_r_ohm())
        )
    else:
        host_print("  DROK_CC_MODE off: set_*_v = output volts (CV); set_ma = I_SET limit (mA)")
    if _lcd_i2c_addr_used is not None:
        host_print("  LCD OK 0x%02x" % int(_lcd_i2c_addr_used))
    else:
        host_print("  LCD not opened")
    if mb is not None:
        regs = mb.read_holding(0, 24)
        if regs and len(regs) > HREG_VERSION:
            host_print(
                "  DROK model=0x%04X version=0x%04X"
                % (int(regs[0x16]), int(regs[0x17]))
            )
        else:
            host_print("  DROK Modbus read failed (check UART / 12 V sequencing)")
    else:
        host_print("  DROK Modbus not initialized")
    host_print(
        "  Relay IN1=GP%u IN2=GP%u (HIGH=off LOW=energized)" % (
            int(getattr(config, "DROK_RELAY_IN1_PIN", 10)),
            int(getattr(config, "DROK_RELAY_IN2_PIN", 11)),
        )
    )
    if boot_footer:
        host_print("READY")
        host_print("STATUS CONNECTED")
    else:
        host_print("— end hw_report —")


def main():
    global _back_deploy_fired, _safe_asserted
    load_axis_config()
    _init_uart_modbus()
    _init_relays()
    _init_lcd()
    _init_safe_switch()
    _write_i_set_limit()
    if _is_safe():
        _apply_safe_hardware("boot SAFE")
    boot_back = _init_back_button()
    if boot_back:
        _apply_deploy_ready(status_tag="boot_back_button")
        _back_deploy_fired = True
        host_print("STATUS boot: back down -> DEPLOY_READY (splash skipped)")
    else:
        _show_boot_lcd_splash()
    _drok_force_output_off()
    _relay_pins_off()
    _report_hardware_to_host()
    lcd_refresh(force=True)

    tim = Timer(-1)
    tim.init(
        mode=Timer.PERIODIC,
        period=SLAVE_TIMER_PERIOD_MS,
        callback=_slave_timer_tick,
    )
    host_print(
        "STATUS drok timer %d ms; TM %.1f Hz; axis_config %s"
        % (
            SLAVE_TIMER_PERIOD_MS,
            SLAVE_TM_HZ,
            str(getattr(config, "DROK_AXIS_CONFIG_FILENAME", "axis_config.ini")),
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
            tim.deinit()
        except Exception:
            pass
        _drok_force_output_off()
        _relay_pins_off()


if __name__ == "__main__":
    main()
