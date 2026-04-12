#!/usr/bin/env python3
"""
CalibratorUI — PySide6 host for the CoilDriver Pico (serial).

Loads CalibratorUI.ui from this directory. Settings in CalibratorUI.ini (UTF-8).

Serial line protocol (newline-terminated):
  TXT:: <text> — shown in textEdit_CalibratorTestOutput (boot, I2C scan, command replies).
  TM:: key=value ... — telemetry: LEDs (alarm, cfg, closed_loop, meas_ok); measured mA and coil V
    (Host: TM lines that lost the leading prefix may be repaired if they start with '=float set_Y_v=' — restores set_X_v.)
    LCDs (lcdNumber_[XYZ]_mA from X_ma/Y_ma/Z_ma, with diag_Ch*_ma + ina_*_ch fallback if *_ma is nan;
    lcdNumber_[XYZ]_Volts from coil_V_X/Y/Z). Unprefixed TM-shaped rows use the same parser and are not copied
    to the text log.
  On connect: by default the host does not reset the Pico — it clears DTR/RTS after opening the COM port (Windows often toggles them and resets RP2040), then waits briefly for boot / CDC.
    If soft reset on connect is off, boot TXT:: was usually already sent before the port opened; the host then sends hw_report so the text log fills with the Pico hardware summary (same as firmware boot report).
    Firmware prints TXT:: OK VERSION … and a hardware report at boot, then streams TM:: every control loop (~LOOP_Hz) with X/Y/Z always present; no host keepalive.
    Optional Settings → "Soft reset on connect" (CalibratorUI.ini [serial] soft_reset_on_connect=1): Ctrl+C then Ctrl+D (MicroPython soft reset),
    then a short boot wait — use only when stuck in >>> REPL.
  Link “fresh” on any TXT:: or TM:: line. Stale: no traffic for ~8 s before the first line after connect, or >3 s after traffic stops (yellow LED + status; STALE dbg at DEBUG≥1 once per episode).
  On Disconnect / app quit: host sends host_disconnect (coils off, deploy-ready; legacy abort still on Pico).
  Status bar Reset sends `safe_reset`: Pico turns off all bridge PWM (IN1 duty 0, inactive) like `safe`. SAFE sends `safe` (same coil-off path; not latched). Soft reset on connect (Ctrl+C Ctrl+D) restarts firmware; boot forces PWM outputs off until host commands again.
  Settings (menu, saved in CalibratorUI.ini [settings]): PWM 3/5 kHz (host display / legacy; Pico 5.x fixes Hz in firmware).
    Each axis Set sends: set_<axis>_v from doubleSpinBox_Test_<axis>_V (volts); coils must be enabled (see below).
  Optional lcdNumber_X_Gauss / Y / Z: estimated |B| (Gauss) at Helmholtz midpoint from [helmholtz]
  x_diameter_mm, x_turns (pair formula). Drive current for that model: prefer I = |V|/R from TM coil_V_* (or
  set_*_v) and ini [helmholtz] x_r_ohm / y_r_ohm / z_r_ohm when R>0; else TM measured mA. Updated every TM::.
  Optional frame_NullIndicator + label_NullIndicatorText: host-defined “null-like” banner when
  |mA| is above a floor on all axes and the three Gauss estimates are within 1% spread (not B⃗=0).
  Optional pushButton_Set_Coil_Voltages (with voltage override widgets): applies all three Test V spinboxes via set_*_v.
  Coil command voltage to the Pico is only the Test V doubleSpinBox values, coil enable(s),
  Set coil voltages / per-axis Set, and the connect-time sync — nothing else sends set_*_v.
  Coil enable: **checkBox_TestVoltageSetting** is the master checkbox (drives enable_x/y/z together) and,
  when the full Test V widget set is present, gates voltage override toward the Test V spinboxes; its state
  is **not** saved or restored from CalibratorUI.ini (always starts off at launch). Legacy: three
  **checkBox_{X,Y,Z}_Enabled** still use ini **enable_X/Y/Z** if the master checkbox is absent. mA target spin
  + Set-mA buttons per axis are optional; if absent, lcdNumber_[XYZ]_mA still update from TM:: (banding uses
  Settings → max mA when no per-axis target; legacy objectName lcdNumber_*_Measured is still accepted). Override needs doubleSpinBox_Test_[XYZ]_V +
  lcdNumber_[XYZ]_Test_Volts: when checked, host adjusts set_<axis>_v per enabled axis toward the Test V
  spinbox using TM:: coil_V_*; test LCDs use green within ±0.25 V, amber below that band, red above.

  Debug (terminal stdout): CalibratorUI.ini [debug] DEBUG = integer 0–9 (default 0).
    One line always goes to stderr with ini path and effective level (even when DEBUG=0).
    0 = off. 1 = basic (connect/disconnect, serial backlog cap, log trim, Pico version).
    2 = + TXT:: / unprefixed serial lines (truncated); once per serial link, one TM dbg line: if set_X_v/set_x_v
    is absent but X_ma or coil_V_X is present, log that raw TM (truncated); else log the first TM line after connect.
    3 = + TM:: rows to HostApp/test_1.csv (set_*_v, *_ma, coil_V_*, meas_ok, Gauss_X/Y/Z from [helmholtz] + mA) and
    a compact DBG3 TM_CSV line per TM
    (also non-TM RX repr as before).

  Run:
    pip install -r requirements.txt
    python CalibratorUI.py

  Host app version: CALIBRATOR_UI_VERSION in this file (bump with user-verified releases; pair with
  Software/Pico coil_driver_app.py VERSION in git commits).
  Help → About Calibrator: logo from Software/Host/3DHC_Logo.png (or HostApp fallback), UI and Pico
  versions, Python libraries, attribution.
"""

from __future__ import annotations

import configparser
import csv
import datetime
import html
import math
import re
import sys
import time
from pathlib import Path

import serial
import serial.tools.list_ports
from PySide6.QtCore import QFile, QIODevice, Qt, QTimer
from PySide6.QtGui import QAction, QPixmap, QTextCursor
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLCDNumber,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QMainWindow,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

# --- Paths ---
_HERE = Path(__file__).resolve().parent
_UI_PATH = _HERE / "CalibratorUI.ui"
_INI_PATH = _HERE / "CalibratorUI.ini"
# DEBUG≥3: append TM snapshot rows here (CSV for Excel/plot tools; not .xls binary).
_TM_CSV_PATH = _HERE / "test_1.csv"
# Project logo for Help → About (user asset); also accepts HostApp/3DHC_Logo.png as fallback.
_HOST_ASSETS_DIR = _HERE.parent / "Host"
_ABOUT_LOGO_NAME = "3DHC_Logo.png"
_ABOUT_CONTACT_EMAIL = "jsmith.carlsbad@gmail.com"

# Match Software/Pico/config.py MAX_CURRENT_PER_COIL_MA (drive / shunt design limit).
PICO_MAX_COIL_MA = 500.0
_PWM_FREQ_HZ_CHOICES = (3000, 5000)
_MAX_CURRENT_MA_CHOICES = (20.0, 50.0, 80.0, 100.0, PICO_MAX_COIL_MA)

# Host UI version (single source of truth for the PySide app). Bump MINOR after each user-verified fix;
# bump MAJOR only for incompatible protocol/UI changes. Git commit messages should cite this and
# coil_driver_app.py VERSION as a tested pair.
CALIBRATOR_UI_VERSION_MAJOR = 1
CALIBRATOR_UI_VERSION_MINOR = 28
CALIBRATOR_UI_VERSION = "%d.%d" % (CALIBRATOR_UI_VERSION_MAJOR, CALIBRATOR_UI_VERSION_MINOR)

_HELP_ABOUT_TITLE = "About Calibrator"


def _resolve_about_logo_path() -> Path | None:
    for base in (_HOST_ASSETS_DIR, _HERE):
        p = base / _ABOUT_LOGO_NAME
        if p.is_file():
            return p
    return None


# Pico serial protocol (line-oriented, newline-terminated):
#   TXT:: <text>  — human-readable log for CalibratorTestOutput (debug, boot, I2C scan, etc.)
#   TM::  key=value ... — machine telemetry (not shown in the log); parsed for LEDs / future gauges.
PREFIX_TXT = "TXT::"
PREFIX_TM = "TM::"

# Common baud rates for Pico / USB CDC
_BAUD_CHOICES = ("9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600")

# Measured mA QLCDNumber: black background; digit color only (Flat segments — required for stylesheet).
_MEAS_LCD_BG = "black"
_MEAS_LCD_NO_DATA = "#ffffff"
_MEAS_LCD_GREEN = "#43a047"
_MEAS_LCD_AMBER = "#ffb300"
_MEAS_LCD_RED = "#e53935"
_MEAS_LCD_NEUTRAL = "#e0e0e0"
# Within ±5% of target → green; within top 10% of channel limit → amber; over limit → red.
_MEAS_TARGET_TOL = 0.05
_MEAS_NEAR_MAX_FRAC = 0.10

# Coil bus voltage QLCDNumber (12 V nominal): green in band; red low / high; amber moderately high.
_COIL_V_LOW_RED = 11.8
_COIL_V_GREEN_HI = 12.3
_COIL_V_AMBER_HI = 12.5

# Voltage override test LCDs: ±this band (V) around spinbox target → green; below → amber; above → red.
_TEST_VOLT_TOL_V = 0.25
# When TM:: meas_ok=0 (INA read missing), cap commanded set_*_v while nudging toward target (open-loop safety).
_VOLT_OVERRIDE_MAX_CMD_V_IF_MEAS_BAD = 3.0
# Helmholtz pair (ideal spacing = R): axial |B| at midpoint, B = 8/(5^(3/2)) * μ0 * N * I / R [T].
_MU0_SI = 4.0 * math.pi * 1e-7
_HELMHOLTZ_PAIR_AXIS_CENTER_FACTOR = 8.0 / (5.0 ** 1.5)

# Null-indicator: |mA| floor per axis; Gauss uniformity = (max−min)/mean ≤ this fraction.
_NULL_INDICATOR_I_MIN_ABS_MA = 2.0
_NULL_INDICATOR_B_UNIFORM_FRAC = 0.01


def _helmholtz_pair_axis_center_gauss(
    i_a: float, radius_m: float, n_turns: float
) -> float:
    """|B| in Gauss; I in A, R (coil radius) in m, N series turns per pair (same I)."""
    if radius_m <= 0.0 or n_turns <= 0.0:
        return float("nan")
    b_t = (
        _HELMHOLTZ_PAIR_AXIS_CENTER_FACTOR
        * _MU0_SI
        * float(n_turns)
        * abs(float(i_a))
        / float(radius_m)
    )
    return b_t * 1e4

# Avoid freezing the UI thread: bound serial parsing per tick; trim the boot log (TXT:: flood).
_MAX_SERIAL_LINES_PER_TICK = 40
_MAX_PICO_LOG_BLOCKS = 2000
# After Connect: process RX in slices (lines) so the event loop stays responsive during hw_report.
_CONNECT_RX_PUMP_SLICE_LINES = 10
_CONNECT_RX_PUMP_MAX_SLICES = 600
# After opening COM on Windows, DTR/RTS can reset RP2040; clear them, then wait before first commands.
_CONNECT_SETTLE_NO_SOFT_RESET_S = 0.45
# Stale link: after at least one TM/TXT, silence longer than this → yellow.
_LINK_STALE_AFTER_TRAFFIC_S = 3.0
# Before any TM/TXT, allow this long after RX starts (wrong COM, REPL, slow CDC, or Pico boot) before STALE.
_LINK_STALE_BEFORE_FIRST_TRAFFIC_S = 8.0

# LED indicator colors (display-only QRadioButton ::indicator)
_LED_COLORS = {
    "red": "#e53935",
    "green": "#43a047",
    "yellow": "#fbc02d",
    "amber": "#ffb300",
    "gray": "#757575",
}


def _apply_led_color(rb: QRadioButton, color_key: str) -> None:
    """Style the radio’s round indicator as a solid LED; color_key in _LED_COLORS."""
    color = _LED_COLORS.get(color_key, _LED_COLORS["gray"])
    name = rb.objectName()
    rb.setStyleSheet(
        f"""
        QRadioButton#{name} {{
            color: palette(windowText);
            spacing: 6px;
        }}
        QRadioButton#{name}::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 9px;
            background-color: {color};
            border: 1px solid #424242;
        }}
        QRadioButton#{name}::indicator:checked,
        QRadioButton#{name}::indicator:unchecked {{
            background-color: {color};
        }}
        """
    )


def _setup_display_only_led(rb: QRadioButton) -> None:
    """Not used as a real radio: no selection, no clicks; LED look via stylesheet."""
    rb.setAutoExclusive(False)
    rb.setCheckable(True)
    rb.setChecked(False)
    rb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    rb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)


def _is_bluetooth_port(p: serial.tools.list_ports.ListPortInfo) -> bool:
    """Exclude Bluetooth virtual COM ports on Windows (and similar)."""
    desc = (p.description or "").lower()
    manu = (p.manufacturer or "").lower()
    hwid = (p.hwid or "").lower()
    if "bluetooth" in desc or "bluetooth" in manu:
        return True
    if "bluetooth" in hwid:
        return True
    if "standard serial over bluetooth" in desc:
        return True
    return False


def enumerate_com_ports() -> list[str]:
    """List COM device names, excluding Bluetooth."""
    out: list[str] = []
    for p in serial.tools.list_ports.comports():
        if _is_bluetooth_port(p):
            continue
        dev = p.device
        if dev:
            out.append(dev)

    def _com_key(dev: str):
        m = re.match(r"COM(\d+)$", dev, re.I)
        if m:
            return (0, int(m.group(1)))
        return (1, dev.lower())

    return sorted(set(out), key=_com_key)


def load_ini() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    if _INI_PATH.is_file():
        cp.read(_INI_PATH, encoding="utf-8")
    if not cp.has_section("serial"):
        cp.add_section("serial")
    if not cp.has_option("serial", "port"):
        cp.set("serial", "port", "")
    if not cp.has_option("serial", "baud"):
        cp.set("serial", "baud", "115200")
    if not cp.has_option("serial", "soft_reset_on_connect"):
        cp.set("serial", "soft_reset_on_connect", "0")
    if not cp.has_section("settings"):
        cp.add_section("settings")
    if not cp.has_option("settings", "pwm_freq_hz"):
        cp.set("settings", "pwm_freq_hz", "5000")
    if not cp.has_option("settings", "max_ma_mA"):
        cp.set("settings", "max_ma_mA", "100")
    for _ax in ("X", "Y", "Z"):
        if not cp.has_option("settings", f"enable_{_ax}"):
            cp.set("settings", f"enable_{_ax}", "0")
    if not cp.has_section("debug"):
        cp.add_section("debug")
    if not cp.has_option("debug", "DEBUG"):
        cp.set("debug", "DEBUG", "0")
    if not cp.has_section("helmholtz"):
        cp.add_section("helmholtz")
    for _ax in ("x", "y", "z"):
        if not cp.has_option("helmholtz", f"{_ax}_diameter_mm"):
            cp.set("helmholtz", f"{_ax}_diameter_mm", "0")
        if not cp.has_option("helmholtz", f"{_ax}_turns"):
            cp.set("helmholtz", f"{_ax}_turns", "0")
        if not cp.has_option("helmholtz", f"{_ax}_r_ohm"):
            cp.set("helmholtz", f"{_ax}_r_ohm", "0")
    return cp


def save_ini(cp: configparser.ConfigParser) -> None:
    with open(_INI_PATH, "w", encoding="utf-8", newline="\n") as f:
        cp.write(f)


def _init_measured_ma_lcd(lcd: QLCDNumber) -> None:
    """Match OLD host: flat segments + black field so only digit color changes."""
    lcd.setFixedSize(120, 45)
    lcd.setDigitCount(6)
    lcd.setMode(QLCDNumber.Mode.Dec)
    lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
    lcd.display("---")
    lcd.setStyleSheet(
        f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
    )


def _meas_lcd_digit_color(meas: float, target: float, limit: float) -> str:
    """
    Red: over-range (measured above Settings → Max Current mA).
    Green: within ±5% of target mA.
    Amber: within top 10% of channel limit (high current, not necessarily on target).
    Else: neutral light gray.
    """
    eps = 1e-3
    lim = max(limit, eps)
    if meas > lim + eps:
        return _MEAS_LCD_RED
    # On-target band
    if abs(target) < 0.01:
        if abs(meas) < 0.5:
            return _MEAS_LCD_GREEN
    else:
        if abs(meas - target) <= _MEAS_TARGET_TOL * abs(target):
            return _MEAS_LCD_GREEN
    # Near maximum (90%..100% of limit)
    if meas >= lim * (1.0 - _MEAS_NEAR_MAX_FRAC) - eps:
        return _MEAS_LCD_AMBER
    return _MEAS_LCD_NEUTRAL


def _init_volts_lcd(lcd: QLCDNumber) -> None:
    """Flat segments + black field; 2 decimal places for ~12 V bus."""
    lcd.setFixedSize(120, 45)
    lcd.setDigitCount(5)
    lcd.setMode(QLCDNumber.Mode.Dec)
    lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
    if hasattr(lcd, "setSmallDecimalPoint"):
        lcd.setSmallDecimalPoint(True)
    lcd.display("---")
    lcd.setStyleSheet(
        f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
    )


def _init_gauss_lcd(lcd: QLCDNumber) -> None:
    """|B| in Gauss from Helmholtz model; flat segments like other meters."""
    lcd.setFixedSize(120, 45)
    lcd.setDigitCount(6)
    lcd.setMode(QLCDNumber.Mode.Dec)
    lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
    if hasattr(lcd, "setSmallDecimalPoint"):
        lcd.setSmallDecimalPoint(True)
    lcd.display("---")
    lcd.setStyleSheet(
        f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
    )


def _volts_lcd_digit_color(v: float) -> str:
    """12 V target: green 11.8–12.3; red <11.8 or >12.5; amber (12.3, 12.5]."""
    if v < _COIL_V_LOW_RED:
        return _MEAS_LCD_RED
    if v > _COIL_V_AMBER_HI:
        return _MEAS_LCD_RED
    if v > _COIL_V_GREEN_HI:
        return _MEAS_LCD_AMBER
    return _MEAS_LCD_GREEN


def _test_volt_lcd_digit_color(meas: float, target: float, tol: float = _TEST_VOLT_TOL_V) -> str:
    """Green within ±tol of target; amber when below band (too low); red when above band."""
    if abs(meas - target) <= tol:
        return _MEAS_LCD_GREEN
    if meas < target - tol:
        return _MEAS_LCD_AMBER
    return _MEAS_LCD_RED


def _load_ui() -> QMainWindow | None:
    if not _UI_PATH.is_file():
        print("Missing UI file:", _UI_PATH, file=sys.stderr)
        return None
    f = QFile(str(_UI_PATH))
    if not f.open(QIODevice.ReadOnly):
        print("Cannot open:", _UI_PATH, file=sys.stderr)
        return None
    loader = QUiLoader()
    win = loader.load(f, None)
    f.close()
    if win is None:
        print("QUiLoader.load failed:", _UI_PATH, file=sys.stderr)
        return None
    return win


class CalibratorController:
    """Wires UI widgets, INI, COM list, and pyserial."""

    def _read_debug_level(self) -> int:
        raw = "0"
        sec = "debug"
        if self._ini.has_section(sec):
            if self._ini.has_option(sec, "DEBUG"):
                raw = self._ini.get(sec, "DEBUG", fallback="0")
            else:
                for opt in self._ini.options(sec):
                    if opt.lower() == "debug":
                        raw = self._ini.get(sec, opt, fallback="0")
                        break
        try:
            v = int(str(raw).strip())
        except ValueError:
            v = 0
        return max(0, min(9, v))

    def _dbg(self, level: int, *args) -> None:
        """Print to terminal if DEBUG in CalibratorUI.ini [debug] is >= level."""
        if self._debug_level < level:
            return
        print("[CalibratorUI DBG%d]" % level, *args, flush=True)

    def __init__(self, win: QMainWindow) -> None:
        self._win = win
        self._ini = load_ini()
        self._debug_level = self._read_debug_level()
        try:
            sys.stderr.write(
                "[CalibratorUI] UI %s ini=%s effective_DEBUG=%d (stdout trace: [debug] DEBUG=1..9)\n"
                % (CALIBRATOR_UI_VERSION, _INI_PATH, self._debug_level)
            )
            if self._debug_level >= 3:
                sys.stderr.write(
                    "[CalibratorUI] DEBUG>=3: TM CSV -> %s (file created on first TM:: after connect)\n"
                    % (_TM_CSV_PATH.resolve(),)
                )
            elif self._debug_level < 3:
                sys.stderr.write(
                    "[CalibratorUI] TM CSV (test_1.csv) is disabled; set [debug] DEBUG=3 in %s\n"
                    % (_INI_PATH.resolve(),)
                )
            sys.stderr.flush()
        except Exception:
            pass
        self._serial: serial.Serial | None = None
        self._tm_csv_fp = None
        self._tm_csv_writer: csv.writer | None = None
        # Yellow "Connected" LED when serial is open but Pico reports fault (wired later).
        self._pico_has_error: bool = False
        # No TM:: / TXT:: traffic within timeout (firmware hung / wrong port / unplugged).
        self._pico_alive_stale: bool = False
        self._last_alive_reply_ts: float | None = None
        # True only after at least one TM:: or TXT:: line this connection (avoids bogus STALE on elif branch).
        self._serial_saw_tm_txt_this_link: bool = False
        self._connect_mono_ts: float | None = None
        self._keepalive_stale_dbg_done: bool = False
        # DEBUG≥2: one-shot TM line sample per link (see _apply_tm_line).
        self._tm_dbg_first_tm_after_connect: bool = False
        self._tm_dbg_setx_absent_x_present_pending: bool = False
        # Placeholders until host↔Pico protocol (set mA ack, closed-loop telem).
        self._configured_ok: bool = False
        self._closed_loop_ok: bool = False
        self._pico_version: str | None = None
        self._settings_pwm_hz: int = 5000
        self._settings_max_ma: float = 100.0
        # TM-derived (DC State LED, Initialized); _cl_before_tm saved before each TM line updates closed_loop_ok.
        self._meas_ok: bool | None = None
        self._cl_before_tm = False

        self._combo_port = win.findChild(QComboBox, "comboBox_CalibratorPort")
        self._combo_baud = win.findChild(QComboBox, "comboBox_CalbratorBaud")
        self._btn_connect = win.findChild(QPushButton, "pushButton_ConnectCalibrator")
        self._led_connected = win.findChild(QRadioButton, "radioButton_Connected")
        self._led_configured = win.findChild(QRadioButton, "radioButton_Configured")
        self._led_closed_loop = win.findChild(QRadioButton, "radioButton_ClosedLoop")
        self._led_initialized = win.findChild(QRadioButton, "radioButton_Initialized")
        self._led_dc_state = win.findChild(QRadioButton, "radioButton_DCState")
        self._text_out = win.findChild(QTextEdit, "textEdit_CalibratorTestOutput")
        self._btn_clear_text = win.findChild(QPushButton, "pushButton_ClearCalibratorText")

        # Master coil enable (optional): one checkbox → firmware enable_x/y/z same state.
        self._master_coils_enable: QCheckBox | None = win.findChild(
            QCheckBox, "checkBox_TestVoltageSetting"
        )
        self._axis_rows: list[
            tuple[str, QSpinBox | None, QPushButton | None, QLCDNumber, QCheckBox | None]
        ] = []
        for ax in ("X", "Y", "Z"):
            sp = win.findChild(QSpinBox, f"spinBox_{ax}mA_target")
            pb = win.findChild(QPushButton, f"pushButton_{ax}_Set_mA")
            lcd = win.findChild(QLCDNumber, f"lcdNumber_{ax}_mA")
            if lcd is None:
                lcd = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Measured")
            chk = win.findChild(QCheckBox, f"checkBox_{ax}_Enabled")
            if not lcd:
                raise RuntimeError(
                    f"UI missing measured mA LCD for axis {ax} "
                    f"(lcdNumber_{ax}_mA, or legacy lcdNumber_{ax}_Measured)"
                )
            _init_measured_ma_lcd(lcd)
            if sp is not None:
                sp.setRange(0, 5000)
                sp.setValue(0)
            if chk is not None:
                chk.setChecked(False)
            self._axis_rows.append((ax, sp, pb, lcd, chk))
        if self._master_coils_enable is None:
            for ax, _sp, _pb, _lcd, chk in self._axis_rows:
                if chk is None:
                    raise RuntimeError(
                        "UI: add checkBox_TestVoltageSetting (master enable) or keep checkBox_X/Y/Z_Enabled per axis."
                    )
        else:
            self._master_coils_enable.setToolTip(
                "Master: enables or disables all three coil drivers on the Pico (enable_x, enable_y, enable_z). "
                "Not saved in CalibratorUI.ini — always off when the app starts."
            )

        self._axis_volts_lcd: list[tuple[str, QLCDNumber]] = []
        for ax in ("X", "Y", "Z"):
            vlcd = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Volts")
            if not vlcd:
                raise RuntimeError(
                    f"UI missing coil volts LCD for axis {ax} (lcdNumber_{ax}_Volts)"
                )
            _init_volts_lcd(vlcd)
            self._axis_volts_lcd.append((ax, vlcd))

        self._axis_gauss_lcd: list[tuple[str, QLCDNumber]] = []
        _g_x = win.findChild(QLCDNumber, "lcdNumber_X_Gauss")
        _g_y = win.findChild(QLCDNumber, "lcdNumber_Y_Gauss")
        _g_z = win.findChild(QLCDNumber, "lcdNumber_Z_Gauss")
        if _g_x and _g_y and _g_z:
            for ax, glcd in (("X", _g_x), ("Y", _g_y), ("Z", _g_z)):
                _init_gauss_lcd(glcd)
                glcd.setToolTip(
                    "|B| (Gauss) at Helmholtz midpoint: ini [helmholtz] "
                    f"{ax.lower()}_diameter_mm, {ax.lower()}_turns. "
                    "Current for the model uses I=|V|/R from TM coil_V or set_*_v and "
                    f"{ax.lower()}_r_ohm when set; else TM measured mA. Refreshes every telemetry line."
                )
                self._axis_gauss_lcd.append((ax, glcd))
        elif _g_x or _g_y or _g_z:
            self._dbg(
                1,
                "Gauss LCDs incomplete (need lcdNumber_X_Gauss, lcdNumber_Y_Gauss, "
                "lcdNumber_Z_Gauss); field estimate disabled",
            )

        self._null_frame: QFrame | None = None
        self._null_label: QLabel | None = None
        self._null_indicator_active: bool | None = None
        _nf = win.findChild(QFrame, "frame_NullIndicator")
        _nl = win.findChild(QLabel, "label_NullIndicatorText")
        if _nf is not None and _nl is not None:
            self._null_frame = _nf
            self._null_label = _nl
            self._apply_null_indicator_style(False, force=True)
            _nl.setToolTip(
                "Green when |Ix|,|Iy|,|Iz| exceed a small floor and the three Gauss model "
                "estimates differ by ≤1% — a UI ‘triaxial magnitude balance’ cue, not a vector "
                "magnetometer proof of B⃗=0."
            )
        elif _nf is not None or _nl is not None:
            self._dbg(
                1,
                "Null indicator incomplete (need frame_NullIndicator and label_NullIndicatorText).",
            )

        # Optional: voltage override (Designer objectNames must match exactly).
        self._volt_override_chk: QCheckBox | None = None
        self._volt_override_spins: dict[str, QDoubleSpinBox] = {}
        self._volt_override_lcds: dict[str, QLCDNumber] = {}
        self._volt_ov_cmd_v: dict[str, float] = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        vo_chk = win.findChild(QCheckBox, "checkBox_TestVoltageSetting")
        vo_spins: dict[str, QDoubleSpinBox | None] = {}
        vo_lcds: dict[str, QLCDNumber | None] = {}
        for ax in ("X", "Y", "Z"):
            vo_spins[ax] = win.findChild(QDoubleSpinBox, f"doubleSpinBox_Test_{ax}_V")
            vo_lcds[ax] = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Test_Volts")
        if (
            vo_chk
            and all(vo_spins[a] is not None for a in ("X", "Y", "Z"))
            and all(vo_lcds[a] is not None for a in ("X", "Y", "Z"))
        ):
            self._volt_override_chk = vo_chk
            for ax in ("X", "Y", "Z"):
                sp = vo_spins[ax]
                lc = vo_lcds[ax]
                assert sp is not None and lc is not None
                self._volt_override_spins[ax] = sp
                self._volt_override_lcds[ax] = lc
                sp.setRange(0.0, 20.0)
                sp.setDecimals(2)
                sp.setSingleStep(0.1)
                sp.setValue(0.0)
                _init_volts_lcd(lc)
            if vo_chk is self._master_coils_enable:
                vo_chk.setToolTip(
                    "Master enable for all three coil drivers (enable_x/y/z). With Test V widgets present: "
                    "host sends set_<axis>_v toward doubleSpinBox_Test_*_V using TM:: coil_V_*; test LCDs "
                    "green within ±0.25 V, amber below, red above."
                )
            else:
                vo_chk.setToolTip(
                    "Override: host sends set_<axis>_v toward doubleSpinBox_Test_*_V using TM:: coil_V_* "
                    "when coils are enabled. Green within ±0.25 V; amber below; red above."
                )
            vo_chk.stateChanged.connect(self._on_volt_override_chk_changed)
        elif vo_chk or any(vo_spins.values()) or any(vo_lcds.values()):
            self._dbg(
                1,
                "Voltage override widgets incomplete (need checkBox_TestVoltageSetting, "
                "doubleSpinBox_Test_X_V / _Y_ / _Z_, lcdNumber_X_Test_Volts / _Y_ / _Z_); "
                "override disabled",
            )

        self._btn_set_coil_v: QPushButton | None = win.findChild(
            QPushButton, "pushButton_Set_Coil_Voltages"
        )
        if (
            self._btn_set_coil_v is not None
            and self._volt_override_chk is not None
            and len(self._volt_override_spins) == 3
        ):
            self._btn_set_coil_v.setToolTip(
                "Apply all three doubleSpinBox_Test_[XYZ]_V values to the Pico (set_x_v / set_y_v / set_z_v). "
                "Voltage override must be on."
            )
            self._btn_set_coil_v.clicked.connect(self._on_set_coil_voltages_clicked)
        elif self._btn_set_coil_v is not None:
            self._dbg(
                1,
                "pushButton_Set_Coil_Voltages ignored until voltage override widget set is complete.",
            )

        if not self._combo_port or not self._combo_baud or not self._btn_connect:
            raise RuntimeError(
                "UI missing widgets: comboBox_CalibratorPort, comboBox_CalbratorBaud, pushButton_ConnectCalibrator"
            )
        if (
            not self._led_connected
            or not self._led_configured
            or not self._led_closed_loop
            or not self._led_initialized
            or not self._led_dc_state
        ):
            raise RuntimeError(
                "UI missing status LEDs: Connected, Configured, ClosedLoop, Initialized, DCState"
            )
        if not self._text_out or not self._btn_clear_text:
            raise RuntimeError(
                "UI missing textEdit_CalibratorTestOutput or pushButton_ClearCalibratorText"
            )
        self._btn_safe = win.findChild(QPushButton, "pushButton_SafeCalibrator")
        if not self._btn_safe:
            raise RuntimeError("UI missing pushButton_SafeCalibrator")

        self._rx_buf = bytearray()
        # Last (display_text, stylesheet) per QLCDNumber — skip redundant setStyleSheet (expensive at TM rate).
        self._lcd_meas_cache: dict[str, tuple[str, str]] = {}
        self._lcd_volts_cache: dict[str, tuple[str, str]] = {}
        self._lcd_test_volts_cache: dict[str, tuple[str, str]] = {}
        self._lcd_gauss_cache: dict[str, tuple[str, str]] = {}
        # (coil radius_m, N turns) per axis from [helmholtz]; None → show --- on Gauss LCD.
        self._helm_geom: dict[str, tuple[float, float] | None] = {
            "X": None,
            "Y": None,
            "Z": None,
        }
        # DC coil resistance (Ω) per axis for I≈|V|/R when TM gives coil_V_* or set_*_v (Gauss drive current).
        self._helm_r_ohm: dict[str, float | None] = {"X": None, "Y": None, "Z": None}
        self._connect_rx_pump_slices: int = 0
        self._serial_timer = QTimer(self._win)
        self._serial_timer.setInterval(50)
        self._serial_timer.timeout.connect(self._poll_serial)

        for rb in (
            self._led_connected,
            self._led_configured,
            self._led_closed_loop,
            self._led_initialized,
            self._led_dc_state,
        ):
            _setup_display_only_led(rb)

        self._status_main = QLabel("")
        self._status_conn = QLabel("Connection: Disconnected")
        self._btn_reset = QPushButton("Reset")
        self._btn_reset.setToolTip(
            "Send safe_reset: Pico drives all coil PWM lines off (same shutdown as SAFE). Clears host fault LED."
        )
        sb = win.statusBar()
        sb.addWidget(self._status_main, 1)
        sb.addPermanentWidget(self._btn_reset)
        sb.addPermanentWidget(self._status_conn)

        self._populate_baud_combo()
        self._refresh_com_ports(select_saved=True)
        self._apply_ini_to_widgets()
        self._apply_settings_from_ini()
        self._reload_helmholtz_geometry()

        self._setup_settings_menu()
        self._sync_soft_reset_menu_from_ini()
        self._setup_help_menu()

        self._btn_connect.clicked.connect(self._on_connect_clicked)
        self._btn_safe.clicked.connect(self._on_safe_calibrator)
        self._btn_reset.clicked.connect(self._on_reset_calibrator)
        self._btn_clear_text.clicked.connect(self._on_clear_calibrator_text)
        self._combo_port.currentIndexChanged.connect(self._on_serial_widget_changed)
        self._combo_baud.currentIndexChanged.connect(self._on_serial_widget_changed)

        if self._master_coils_enable is not None:
            self._master_coils_enable.stateChanged.connect(
                self._on_master_coils_enable_changed
            )
        for ax, _sp, pb, _lcd, chk in self._axis_rows:
            if pb is not None:
                pb.clicked.connect(lambda checked=False, a=ax: self._on_set_axis_ma(a))
            if chk is not None and self._master_coils_enable is None:
                chk.stateChanged.connect(lambda _st, a=ax: self._on_axis_enable_changed(a))

        self._set_connected_ui(False)
        self._set_status("Ready.")
        self._dbg(1, "startup; DEBUG level", self._debug_level, "ini", _INI_PATH)

    def _populate_baud_combo(self) -> None:
        self._combo_baud.clear()
        for b in _BAUD_CHOICES:
            self._combo_baud.addItem(b)

    def _apply_ini_to_widgets(self) -> None:
        port = self._ini.get("serial", "port", fallback="").strip()
        baud_str = self._ini.get("serial", "baud", fallback="115200").strip()

        idx = self._combo_baud.findText(baud_str)
        if idx >= 0:
            self._combo_baud.setCurrentIndex(idx)
        else:
            self._combo_baud.insertItem(0, baud_str)
            self._combo_baud.setCurrentIndex(0)

        if port:
            idxp = self._combo_port.findText(port)
            if idxp >= 0:
                self._combo_port.setCurrentIndex(idxp)
            else:
                self._combo_port.insertItem(0, port)
                self._combo_port.setCurrentIndex(0)

    def _apply_settings_from_ini(self) -> None:
        try:
            hz = int(self._ini.get("settings", "pwm_freq_hz", fallback="5000"))
        except ValueError:
            hz = 5000
        if hz not in _PWM_FREQ_HZ_CHOICES:
            hz = 5000
        self._settings_pwm_hz = hz
        try:
            m = float(self._ini.get("settings", "max_ma_mA", fallback="100"))
        except ValueError:
            m = 100.0
        valid = [float(x) for x in _MAX_CURRENT_MA_CHOICES]
        if m not in valid:
            m = min(valid, key=lambda x: abs(x - m))
        self._settings_max_ma = m
        if self._master_coils_enable is not None:
            # Safety: never restore master enable from ini — always start unchecked.
            self._master_coils_enable.blockSignals(True)
            self._master_coils_enable.setChecked(False)
            self._master_coils_enable.blockSignals(False)
        else:
            for ax, _sp, _pb, _lcd, chk in self._axis_rows:
                if chk is None:
                    continue
                raw = self._ini.get("settings", f"enable_{ax}", fallback="0").strip()
                on = raw in ("1", "true", "True", "yes", "YES", "on", "ON")
                chk.blockSignals(True)
                chk.setChecked(on)
                chk.blockSignals(False)

    def _coils_axis_enabled(self, axis: str) -> bool:
        """True if this logical axis is considered enabled for serial / UI (master or per-axis)."""
        if self._master_coils_enable is not None:
            return self._master_coils_enable.isChecked()
        row = next((r for r in self._axis_rows if r[0] == axis), None)
        if row is None:
            return False
        chk = row[4]
        return bool(chk is not None and chk.isChecked())

    def _reload_helmholtz_geometry(self) -> None:
        """Read [helmholtz] x_diameter_mm, x_turns, x_r_ohm, … for Gauss estimate and I=|V|/R."""
        sec = "helmholtz"
        for ax in ("X", "Y", "Z"):
            self._helm_geom[ax] = None
            self._helm_r_ohm[ax] = None
        if not self._ini.has_section(sec):
            return
        for ax in ("X", "Y", "Z"):
            al = ax.lower()
            try:
                ro = float(self._ini.get(sec, f"{al}_r_ohm", fallback="0").strip())
            except ValueError:
                ro = 0.0
            if ro > 0.0:
                self._helm_r_ohm[ax] = ro
            try:
                d_mm = float(
                    self._ini.get(sec, f"{al}_diameter_mm", fallback="0").strip()
                )
            except ValueError:
                d_mm = 0.0
            try:
                n_turn = float(self._ini.get(sec, f"{al}_turns", fallback="0").strip())
            except ValueError:
                n_turn = 0.0
            if d_mm <= 0.0 or n_turn <= 0.0:
                continue
            r_m = (d_mm / 1000.0) * 0.5
            if r_m <= 0.0:
                continue
            self._helm_geom[ax] = (r_m, n_turn)

    def _settings_persist_to_ini(self) -> None:
        self._ini.set("settings", "pwm_freq_hz", str(self._settings_pwm_hz))
        self._ini.set("settings", "max_ma_mA", str(self._settings_max_ma))
        # Master enable is not written to ini (safety). Legacy per-axis checkboxes still persist enable_*.
        if self._master_coils_enable is None:
            for ax, _sp, _pb, _lcd, chk in self._axis_rows:
                if chk is None:
                    continue
                self._ini.set("settings", f"enable_{ax}", "1" if chk.isChecked() else "0")
        mb = self._win.menuBar()
        for a in mb.actions():
            m = a.menu()
            if m is not None and m.title().replace("&", "") == "Settings":
                sr = self._find_menu_action(m, "Soft reset on connect")
                if sr is not None:
                    self._ini.set(
                        "serial", "soft_reset_on_connect", "1" if sr.isChecked() else "0"
                    )
                break
        save_ini(self._ini)

    @staticmethod
    def _menu_has_action(menu, label: str) -> bool:
        for act in menu.actions():
            if act.isSeparator():
                continue
            if act.text().replace("&", "") == label:
                return True
        return False

    def _ensure_menu_action(self, menu, label: str, slot) -> None:
        if self._menu_has_action(menu, label):
            return
        a = QAction(label, self._win)
        a.triggered.connect(slot)
        menu.addAction(a)

    @staticmethod
    def _find_menu_action(menu, label_plain: str) -> QAction | None:
        for act in menu.actions():
            if act.isSeparator():
                continue
            if act.text().replace("&", "") == label_plain:
                return act
        return None

    def _soft_reset_on_connect_pref(self) -> bool:
        try:
            return self._ini.getboolean("serial", "soft_reset_on_connect", fallback=False)
        except ValueError:
            return False

    def _sync_soft_reset_menu_from_ini(self) -> None:
        mb = self._win.menuBar()
        sm = None
        for a in mb.actions():
            m = a.menu()
            if m is not None and m.title().replace("&", "") == "Settings":
                sm = m
                break
        if sm is None:
            return
        act = self._find_menu_action(sm, "Soft reset on connect")
        if act is None:
            return
        act.blockSignals(True)
        act.setChecked(self._soft_reset_on_connect_pref())
        act.blockSignals(False)

    def _on_soft_reset_on_connect_toggled(self, on: bool) -> None:
        self._ini.set("serial", "soft_reset_on_connect", "1" if on else "0")
        save_ini(self._ini)
        self._set_status(
            "Soft reset on connect: %s (saved to CalibratorUI.ini)."
            % ("on — use when Pico is stuck in >>> REPL" if on else "off — normal when firmware is already running")
        )

    def _setup_settings_menu(self) -> None:
        """Wires Settings: create menu if missing; add only actions not already in .ui."""
        mb = self._win.menuBar()
        sm = None
        for a in mb.actions():
            m = a.menu()
            if m is not None and m.title().replace("&", "") == "Settings":
                sm = m
                break
        if sm is None:
            sm = mb.addMenu("Settings")
        self._ensure_menu_action(sm, "Save", self._settings_save)
        self._ensure_menu_action(sm, "Restore", self._settings_restore)
        if not self._menu_has_action(sm, "Frequency..."):
            sm.addSeparator()
        self._ensure_menu_action(sm, "Frequency...", self._settings_dialog_frequency)
        self._ensure_menu_action(sm, "Max Current...", self._settings_dialog_max_ma)
        if not self._menu_has_action(sm, "Soft reset on connect"):
            sm.addSeparator()
            sr = QAction("Soft reset on connect", self._win)
            sr.setCheckable(True)
            sr.setToolTip(
                "When on, Connect sends Ctrl+C and Ctrl+D (MicroPython soft reset). "
                "Use only if the Pico is stuck at the >>> REPL. When off (default), Connect talks to a running app "
                "(e.g. READY DEPLOY / SAFE) without resetting."
            )
            sr.toggled.connect(self._on_soft_reset_on_connect_toggled)
            sm.addAction(sr)

    def _setup_help_menu(self) -> None:
        act = self._win.findChild(QAction, "actionAbout_Calibrator")
        if act is not None:
            act.triggered.connect(self._show_help_about_dialog)
            return
        mb = self._win.menuBar()
        for top in mb.actions():
            m = top.menu()
            if m is not None and m.title().replace("&", "") == "Help":
                sub = self._find_menu_action(m, _HELP_ABOUT_TITLE)
                if sub is not None:
                    sub.triggered.connect(self._show_help_about_dialog)
                else:
                    a = QAction(_HELP_ABOUT_TITLE, self._win)
                    a.triggered.connect(self._show_help_about_dialog)
                    m.addAction(a)
                return
        hm = mb.addMenu("Help")
        a = QAction(_HELP_ABOUT_TITLE, self._win)
        a.triggered.connect(self._show_help_about_dialog)
        hm.addAction(a)

    def _show_help_about_dialog(self) -> None:
        dlg = QDialog(self._win)
        dlg.setWindowTitle(_HELP_ABOUT_TITLE)
        dlg.setModal(True)
        dlg.setStyleSheet(
            "QDialog { background-color: #1a1d2e; color: #e8e8e8; }"
            "QLabel { color: #e8e8e8; }"
            "QPushButton { background-color: #2d334d; color: #e8e8e8; padding: 6px 18px; "
            "border: 1px solid #3d4666; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3a4260; }"
        )
        lay = QVBoxLayout(dlg)
        logo_path = _resolve_about_logo_path()
        if logo_path is not None:
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                max_w = 560
                if pix.width() > max_w:
                    pix = pix.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
                im = QLabel()
                im.setPixmap(pix)
                im.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                lay.addWidget(im)
        if self._serial is None:
            pico_html = html.escape("Pico: not connected")
        elif self._pico_version:
            pico_html = "Pico firmware version: " + html.escape(self._pico_version)
        else:
            pico_html = html.escape("Pico: connected — firmware version not reported yet")
        ver_ui = html.escape(CALIBRATOR_UI_VERSION)
        email_e = html.escape(_ABOUT_CONTACT_EMAIL)
        info = QLabel(
            "<p style='margin-top:12px;'><b>Calibrator host application</b></p>"
            "<p>Calibrator UI version: <b>%s</b><br/>%s</p>"
            "<p><b>Python libraries</b></p>"
            "<p>PySide6<br/>pyserial</p>"
            "<p><b>Attribution</b></p>"
            "<p>Primary author &amp; contact: "
            '<a href="mailto:%s" style="color:#7eb6ff;">%s</a><br/>'
            "Editor and AI-assisted development: Cursor</p>"
            % (ver_ui, pico_html, email_e, email_e)
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setOpenExternalLinks(True)
        lay.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept)
        lay.addWidget(buttons)
        dlg.exec()

    def _settings_save(self) -> None:
        self._settings_persist_to_ini()
        self._set_status("Settings saved to CalibratorUI.ini.")

    def _settings_restore(self) -> None:
        self._ini = load_ini()
        self._debug_level = self._read_debug_level()
        if self._debug_level < 3:
            self._close_tm_csv()
        self._apply_settings_from_ini()
        self._apply_ini_to_widgets()
        self._sync_soft_reset_menu_from_ini()
        self._reload_helmholtz_geometry()
        self._set_status("Settings restored from CalibratorUI.ini.")
        self._dbg(1, "settings restore; DEBUG level now", self._debug_level)

    def _settings_dialog_frequency(self) -> None:
        dlg = QDialog(self._win)
        dlg.setWindowTitle("PWM frequency")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        cb = QComboBox()
        for hz in _PWM_FREQ_HZ_CHOICES:
            cb.addItem(f"{hz // 1000} kHz ({hz} Hz)", hz)
        idx = cb.findData(self._settings_pwm_hz)
        if idx >= 0:
            cb.setCurrentIndex(idx)
        form.addRow("Frequency:", cb)
        lay.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._settings_pwm_hz = int(cb.currentData())
            self._settings_persist_to_ini()
            self._set_status(f"PWM frequency set to {self._settings_pwm_hz} Hz (saved).")

    def _settings_dialog_max_ma(self) -> None:
        dlg = QDialog(self._win)
        dlg.setWindowTitle("Max current (per channel)")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        cb = QComboBox()
        for m in _MAX_CURRENT_MA_CHOICES[:-1]:
            cb.addItem(f"{int(m)} mA", m)
        last = _MAX_CURRENT_MA_CHOICES[-1]
        cb.addItem(f"{int(last)} mA (design max)", last)
        for i in range(cb.count()):
            d = cb.itemData(i)
            if d is not None and abs(float(d) - self._settings_max_ma) < 0.01:
                cb.setCurrentIndex(i)
                break
        form.addRow("Alarm limit:", cb)
        lay.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            raw = cb.itemData(cb.currentIndex())
            self._settings_max_ma = float(raw) if raw is not None else 100.0
            self._settings_persist_to_ini()
            self._set_status(f"Max current set to {self._settings_max_ma:.0f} mA (saved).")

    def _refresh_com_ports(self, select_saved: bool = False) -> None:
        saved = self._ini.get("serial", "port", fallback="").strip()
        ports = enumerate_com_ports()
        self._combo_port.blockSignals(True)
        self._combo_port.clear()
        for p in ports:
            self._combo_port.addItem(p)
        if saved and saved not in ports:
            self._combo_port.insertItem(0, saved)
        if select_saved and saved:
            idx = self._combo_port.findText(saved)
            if idx >= 0:
                self._combo_port.setCurrentIndex(idx)
        self._combo_port.blockSignals(False)

    def _current_port(self) -> str:
        return self._combo_port.currentText().strip()

    def _current_baud(self) -> int:
        t = self._combo_baud.currentText().strip()
        try:
            return int(t)
        except ValueError:
            return 115200

    def _save_serial_ini(self) -> None:
        self._ini.set("serial", "port", self._current_port())
        self._ini.set("serial", "baud", str(self._current_baud()))
        save_ini(self._ini)

    def _on_serial_widget_changed(self, _index: int) -> None:
        if self._serial is None:
            self._save_serial_ini()

    def _set_status(self, text: str) -> None:
        self._status_main.setText(text)

    def _on_clear_calibrator_text(self) -> None:
        self._text_out.clear()

    def _append_pico_log_line(self, text: str) -> None:
        """Append one line to the Calibrator log (TXT:: payload, no prefix)."""
        self._text_out.append(text.rstrip("\r\n"))
        self._text_out.moveCursor(QTextCursor.MoveOperation.End)
        doc = self._text_out.document()
        n = doc.blockCount()
        if n > _MAX_PICO_LOG_BLOCKS:
            excess = n - _MAX_PICO_LOG_BLOCKS
            cur = QTextCursor(doc)
            cur.movePosition(QTextCursor.MoveOperation.Start)
            start = cur.position()
            moved = 0
            while moved < excess and cur.movePosition(
                QTextCursor.MoveOperation.NextBlock,
                QTextCursor.MoveMode.MoveAnchor,
            ):
                moved += 1
            if moved > 0:
                cur.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
                cur.removeSelectedText()
                self._text_out.moveCursor(QTextCursor.MoveOperation.End)
                self._dbg(
                    1,
                    "log: trimmed",
                    moved,
                    "oldest block(s); cap",
                    _MAX_PICO_LOG_BLOCKS,
                )

    @staticmethod
    def _lcd_key(lcd: QLCDNumber) -> str:
        return lcd.objectName() or str(id(lcd))

    def _lcd_set_if_changed(
        self,
        lcd: QLCDNumber,
        text: str,
        style: str,
        cache: dict[str, tuple[str, str]],
    ) -> None:
        key = self._lcd_key(lcd)
        t = (text, style)
        if cache.get(key) == t:
            return
        lcd.display(text)
        lcd.setStyleSheet(style)
        cache[key] = t

    def _try_parse_pico_version_from_txt_payload(self, payload: str) -> None:
        """Recognize boot STATUS VERSION … or command reply OK VERSION … from Pico."""
        s = payload.strip()
        m = re.match(r"OK VERSION\s+(\S+)", s, re.I)
        if m:
            self._pico_version = m.group(1)
            self._note_pico_liveness()
            self._refresh_connection_status_line()
            self._dbg(1, "Pico firmware version (OK VERSION):", self._pico_version)
            return
        parts = s.split()
        for i, p in enumerate(parts):
            if p.upper() == "VERSION" and i + 1 < len(parts):
                ver = parts[i + 1]
                if re.match(r"^\d+(?:\.\d+)?$", ver):
                    self._pico_version = ver
                    self._note_pico_liveness()
                    self._refresh_connection_status_line()
                    self._dbg(1, "Pico firmware version (boot text):", self._pico_version)
                return

    def _refresh_connection_status_line(self) -> None:
        """Permanent status: connection + Pico firmware version when known."""
        if self._serial is None:
            self._status_conn.setText("Connection: Disconnected")
            return
        port = self._current_port()
        baud = self._current_baud()
        suffix = ""
        if self._pico_alive_stale:
            suffix = " — no telemetry"
        if self._pico_version:
            self._status_conn.setText(
                f"Connection: Connected ({port} @ {baud} baud) — Pico {self._pico_version}{suffix}"
            )
        else:
            self._status_conn.setText(
                f"Connection: Connected ({port} @ {baud} baud) — Pico ...{suffix}"
            )

    @staticmethod
    def _line_looks_like_tm_telemetry(s: str) -> bool:
        """True if line is TM:: or a coil_driver-style key=value telemetry row (even when framing drops TM::)."""
        t = s.strip()
        if not t:
            return False
        if re.match(r"(?i)^TXT::", t) or t.upper().startswith("STATUS"):
            return False
        if re.match(r"(?i)^TM::\s*", t):
            return True
        return bool(
            re.search(
                r"(?:^|\s)(?:meas_ok|X_ma|Y_ma|Z_ma|set_[XYZ]_v|closed_loop|coil_V_[XYZ]|"
                r"ina_[XYZ]_ch|diag_Ch[123]_ma|diag_[XYZ]_duty|alarm)\s*=",
                t,
            )
        )

    @staticmethod
    def _repair_tm_orphan_set_x_prefix(line: str) -> str:
        """If line looks like TM payload but starts with '=value' (lost 'set_X_v' name), restore that token.

        Seen on Windows CDC when a long TM:: row is split so the first assembled 'line' begins with the tail
        of set_X_v=0.000 (i.e. '=0.000 set_Y_v=...') while the prefix stayed in the buffer or prior chunk.
        """
        t = line.strip("\r\n").strip()
        if re.match(r"(?i)^TM::", t):
            return line
        m = re.match(r"^=(\d+(?:\.\d+)?|nan)\s+", t, re.I)
        if not m:
            return line
        rest = t[m.end() :].lstrip()
        if re.match(r"(?i)^set_[yz]_v\s*=", rest):
            return "set_X_v=" + m.group(1) + " " + rest
        return line

    @staticmethod
    def _parse_tm_tokens(line: str) -> dict[str, str]:
        """Parse TM:: key=value tokens (space-separated). Prefix match is case-insensitive."""
        m = re.match(r"\s*TM::\s*", line, re.I)
        if m:
            rest = line[m.end() :].strip()
        else:
            rest = line.strip()
        out: dict[str, str] = {}
        for tok in rest.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                out[k.strip()] = v.strip()
        return out

    @staticmethod
    def _tm_int(kv: dict[str, str], key: str) -> int | None:
        if key not in kv:
            return None
        try:
            return int(float(kv[key]))
        except ValueError:
            return None

    @staticmethod
    def _tm_float(kv: dict[str, str], key: str) -> float | None:
        if key not in kv:
            return None
        s = kv[key].strip().lower()
        if s == "nan":
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _tm_measured_ma(self, kv: dict[str, str], ax: str) -> float | None:
        """Logical-axis mA from TM:: X_ma/Y_ma/Z_ma, else same sample via diag_Ch1/2/3_ma + ina_*_ch (firmware 3.35+)."""
        m = self._tm_float(kv, f"{ax}_ma")
        if m is not None:
            return m
        ch = self._tm_int(kv, f"ina_{ax}_ch")
        if ch is None or ch < 0 or ch > 2:
            return None
        return self._tm_float(kv, "diag_Ch%d_ma" % (ch + 1))

    def _tm_axis_current_a_for_gauss(self, kv: dict[str, str], ax: str) -> float | None:
        """Axis current (A) for Helmholtz |B| model: I=|V|/R from TM when [helmholtz] *_r_ohm set, else TM mA."""
        r_ohm = self._helm_r_ohm.get(ax)
        if r_ohm is not None and r_ohm > 0.0:
            v = self._tm_float(kv, f"coil_V_{ax}")
            if v is None or not math.isfinite(v):
                v = self._tm_float(kv, f"set_{ax}_v")
            if v is not None and math.isfinite(v):
                i_calc = abs(float(v)) / float(r_ohm)
                if math.isfinite(i_calc):
                    return float(i_calc)
        m_ma = self._tm_measured_ma(kv, ax)
        if m_ma is None:
            return None
        i_m = abs(float(m_ma)) / 1000.0
        return i_m if math.isfinite(i_m) else None

    def _tm_gauss_axis_G(self, kv: dict[str, str], ax: str) -> float | None:
        """|B| in Gauss at Helmholtz midpoint for one axis (same model as Gauss LCDs)."""
        geom = self._helm_geom.get(ax)
        if geom is None:
            return None
        i_a = self._tm_axis_current_a_for_gauss(kv, ax)
        if i_a is None:
            return None
        r_m, n_turn = geom
        g = _helmholtz_pair_axis_center_gauss(i_a, r_m, n_turn)
        if g != g:
            return None
        return g

    def _close_tm_csv(self) -> None:
        if self._tm_csv_fp is not None:
            try:
                self._tm_csv_fp.flush()
                self._tm_csv_fp.close()
            except Exception:
                pass
            self._tm_csv_fp = None
            self._tm_csv_writer = None

    def _ensure_tm_csv(self) -> None:
        if self._debug_level < 3:
            return
        if self._tm_csv_writer is not None and self._tm_csv_fp is not None:
            try:
                if not self._tm_csv_fp.closed:
                    return
            except Exception:
                pass
        try:
            p = _TM_CSV_PATH
            new_file = (not p.is_file()) or (p.stat().st_size == 0)
            if not new_file:
                try:
                    with p.open("r", encoding="utf-8", errors="replace") as rf:
                        hdr = rf.readline()
                    if "Gauss_X" not in hdr:
                        self._close_tm_csv()
                        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        p.rename(p.parent / ("test_1_archived_%s.csv" % stamp))
                        new_file = True
                except OSError:
                    pass
            self._tm_csv_fp = p.open(
                "a", newline="", encoding="utf-8", errors="replace"
            )
            self._tm_csv_writer = csv.writer(self._tm_csv_fp)
            if new_file:
                self._tm_csv_writer.writerow(
                    [
                        "unix_s",
                        "set_X_v",
                        "set_Y_v",
                        "set_Z_v",
                        "X_ma",
                        "Y_ma",
                        "Z_ma",
                        "coil_V_X",
                        "coil_V_Y",
                        "coil_V_Z",
                        "meas_ok",
                        "Gauss_X",
                        "Gauss_Y",
                        "Gauss_Z",
                    ]
                )
                self._tm_csv_fp.flush()
        except Exception as e:
            self._dbg(1, "TM CSV: open failed:", e)
            self._close_tm_csv()

    def _append_tm_csv_row(self, kv: dict[str, str]) -> None:
        """DEBUG≥3: append one row to test_1.csv and print a compact TM_CSV line."""
        if self._debug_level < 3:
            return
        self._ensure_tm_csv()
        if self._tm_csv_writer is None or self._tm_csv_fp is None:
            return

        def cell_f(key: str) -> float | None:
            return self._tm_float(kv, key)

        def num(v: float | None) -> float | str:
            if v is None:
                return ""
            return round(v, 6)

        try:
            ts = time.time()
            sx = cell_f("set_X_v")
            sy = cell_f("set_Y_v")
            sz = cell_f("set_Z_v")
            xm = self._tm_measured_ma(kv, "X")
            ym = self._tm_measured_ma(kv, "Y")
            zm = self._tm_measured_ma(kv, "Z")
            cvx = cell_f("coil_V_X")
            cvy = cell_f("coil_V_Y")
            cvz = cell_f("coil_V_Z")
            mk = self._tm_int(kv, "meas_ok")
            gx = self._tm_gauss_axis_G(kv, "X")
            gy = self._tm_gauss_axis_G(kv, "Y")
            gz = self._tm_gauss_axis_G(kv, "Z")
            self._tm_csv_writer.writerow(
                [
                    round(ts, 6),
                    num(sx),
                    num(sy),
                    num(sz),
                    num(xm),
                    num(ym),
                    num(zm),
                    num(cvx),
                    num(cvy),
                    num(cvz),
                    "" if mk is None else mk,
                    num(gx),
                    num(gy),
                    num(gz),
                ]
            )
            self._tm_csv_fp.flush()
            self._dbg(
                3,
                "TM_CSV",
                "t=%.3f" % ts,
                "set_V=(%s,%s,%s)"
                % (
                    f"{sx:.4f}" if sx is not None else "-",
                    f"{sy:.4f}" if sy is not None else "-",
                    f"{sz:.4f}" if sz is not None else "-",
                ),
                "mA=(%s,%s,%s)"
                % (
                    f"{xm:.2f}" if xm is not None else "-",
                    f"{ym:.2f}" if ym is not None else "-",
                    f"{zm:.2f}" if zm is not None else "-",
                ),
                "G=(%s,%s,%s)"
                % (
                    f"{gx:.2f}" if gx is not None else "-",
                    f"{gy:.2f}" if gy is not None else "-",
                    f"{gz:.2f}" if gz is not None else "-",
                ),
                "meas_ok=%s" % ("-" if mk is None else str(mk)),
            )
        except Exception as e:
            self._dbg(1, "TM CSV: row failed:", e)

    def _update_measured_lcds_from_tm(self, kv: dict[str, str]) -> None:
        """Refresh X/Y/Z measured LCDs from TM:: key=value (realtime for all axes)."""
        meas_ok = self._tm_int(kv, "meas_ok")
        if meas_ok is None:
            meas_ok = 1  # legacy TM lines without meas_ok
        trust_meas = meas_ok != 0
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        neutral_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NEUTRAL};"
        )
        for ax, sp, _pb, lcd, _chk in self._axis_rows:
            m = self._tm_measured_ma(kv, ax)
            # mA LCD banding vs axis mA spin (TM set_*_v is volts — do not mix with mA here).
            tgt = float(sp.value()) if sp is not None else 0.0
            lim = self._tm_float(kv, f"lim_{ax}_ma")
            if lim is None:
                lim = float(self._settings_max_ma)
            if m is None:
                self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_meas_cache)
                continue
            if not trust_meas:
                self._lcd_set_if_changed(
                    lcd, f"{m:.1f}", neutral_style, self._lcd_meas_cache
                )
                continue
            c = _meas_lcd_digit_color(m, tgt, lim)
            self._lcd_set_if_changed(
                lcd,
                f"{m:.1f}",
                f"background-color: {_MEAS_LCD_BG}; color: {c};",
                self._lcd_meas_cache,
            )

        self._update_volts_lcds_from_tm(kv)

    def _update_volts_lcds_from_tm(self, kv: dict[str, str]) -> None:
        """Refresh X/Y/Z coil bus V from TM:: coil_V_X/Y/Z (INA bus voltage)."""
        meas_ok = self._tm_int(kv, "meas_ok")
        if meas_ok is None:
            meas_ok = 1
        trust_meas = meas_ok != 0
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        neutral_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NEUTRAL};"
        )
        for ax, lcd in self._axis_volts_lcd:
            v = self._tm_float(kv, f"coil_V_{ax}")
            if v is None:
                self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_volts_cache)
                continue
            if not trust_meas:
                self._lcd_set_if_changed(
                    lcd, f"{v:.2f}", neutral_style, self._lcd_volts_cache
                )
                continue
            c = _volts_lcd_digit_color(v)
            self._lcd_set_if_changed(
                lcd,
                f"{v:.2f}",
                f"background-color: {_MEAS_LCD_BG}; color: {c};",
                self._lcd_volts_cache,
            )

    def _update_gauss_lcds_from_tm(self, kv: dict[str, str]) -> None:
        """|B| (Gauss) at Helmholtz midpoint; current from V/R (ini) or TM mA — every TM:: (real-time)."""
        if not self._axis_gauss_lcd:
            return
        meas_ok = self._tm_int(kv, "meas_ok")
        if meas_ok is None:
            meas_ok = 1
        trust_meas = meas_ok != 0
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        neutral_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NEUTRAL};"
        )
        for ax, lcd in self._axis_gauss_lcd:
            geom = self._helm_geom.get(ax)
            if geom is None:
                self._lcd_set_if_changed(
                    lcd, "---", nodata_style, self._lcd_gauss_cache
                )
                continue
            i_a = self._tm_axis_current_a_for_gauss(kv, ax)
            if i_a is None:
                self._lcd_set_if_changed(
                    lcd, "---", nodata_style, self._lcd_gauss_cache
                )
                continue
            r_m, n_turn = geom
            g = _helmholtz_pair_axis_center_gauss(i_a, r_m, n_turn)
            if g != g:
                self._lcd_set_if_changed(
                    lcd, "---", nodata_style, self._lcd_gauss_cache
                )
                continue
            if not trust_meas:
                self._lcd_set_if_changed(
                    lcd, f"{g:.2f}", neutral_style, self._lcd_gauss_cache
                )
                continue
            self._lcd_set_if_changed(
                lcd,
                f"{g:.2f}",
                neutral_style,
                self._lcd_gauss_cache,
            )

    def _apply_null_indicator_style(self, active: bool, force: bool = False) -> None:
        """Frame + label colors for triaxial magnitude-balance cue (see module docstring)."""
        if self._null_frame is None or self._null_label is None:
            return
        if (
            not force
            and self._null_indicator_active is not None
            and self._null_indicator_active == active
        ):
            return
        self._null_indicator_active = active
        name_f = self._null_frame.objectName()
        name_l = self._null_label.objectName()
        if active:
            bg = "#c8e6c9"
            fg = "#1b5e20"
            text = (
                "Triaxial cue ON: |mA| above floor on X, Y, Z and "
                "|Bx|,|By|,|Bz| model estimates within 1%."
            )
        else:
            bg = "#eceff1"
            fg = "#455a64"
            text = (
                "Triaxial cue OFF: need measurable current on all axes and "
                "three Gauss estimates within 1% spread."
            )
        self._null_label.setText(text)
        self._null_frame.setStyleSheet(
            f"QFrame#{name_f} {{ background-color: {bg}; border: 1px solid #90a4ae; "
            f"border-radius: 6px; }}"
        )
        self._null_label.setStyleSheet(
            f"QLabel#{name_l} {{ color: {fg}; background: transparent; padding: 6px; }}"
        )

    def _update_null_indicator_from_tm(self, kv: dict[str, str]) -> None:
        """True when all |mA| > floor and Gauss triplet spread ≤ 1% (requires [helmholtz])."""
        if self._null_frame is None:
            return
        meas_ok = self._tm_int(kv, "meas_ok")
        trust_meas = (meas_ok != 0) if meas_ok is not None else True
        if not trust_meas:
            self._apply_null_indicator_style(False)
            return
        i_floor = _NULL_INDICATOR_I_MIN_ABS_MA
        gs: list[float] = []
        for ax in ("X", "Y", "Z"):
            geom = self._helm_geom.get(ax)
            if geom is None:
                self._apply_null_indicator_style(False)
                return
            i_a = self._tm_axis_current_a_for_gauss(kv, ax)
            if i_a is None or (i_a * 1000.0) <= i_floor:
                self._apply_null_indicator_style(False)
                return
            r_m, n_turn = geom
            g = _helmholtz_pair_axis_center_gauss(float(i_a), r_m, n_turn)
            if g != g:
                self._apply_null_indicator_style(False)
                return
            gs.append(float(g))
        gmean = sum(gs) / 3.0
        spread = (max(gs) - min(gs)) / max(gmean, 1e-9)
        self._apply_null_indicator_style(
            spread <= _NULL_INDICATOR_B_UNIFORM_FRAC + 1e-15
        )

    def _reset_measured_lcds_no_data(self) -> None:
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        for _ax, _sp, _pb, lcd, _chk in self._axis_rows:
            self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_meas_cache)
        for _ax, lcd in self._axis_volts_lcd:
            self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_volts_cache)
        self._reset_test_volt_lcds_no_data()
        self._reset_gauss_lcds_no_data()
        if self._null_frame is not None:
            self._null_indicator_active = None
            self._apply_null_indicator_style(False, force=True)

    def _reset_gauss_lcds_no_data(self) -> None:
        if not self._axis_gauss_lcd:
            return
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        for _ax, lcd in self._axis_gauss_lcd:
            self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_gauss_cache)

    def _reset_test_volt_lcds_no_data(self) -> None:
        if not self._volt_override_lcds:
            return
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        for _ax, lcd in self._volt_override_lcds.items():
            self._lcd_set_if_changed(
                lcd, "---", nodata_style, self._lcd_test_volts_cache
            )

    def _on_volt_override_chk_changed(self, _state: int) -> None:
        if self._volt_override_chk is None:
            return
        if not self._volt_override_chk.isChecked():
            self._volt_ov_cmd_v = {"X": 0.0, "Y": 0.0, "Z": 0.0}
            if self._serial is not None:
                try:
                    blob = b"".join(
                        f"set_{ax.lower()}_v 0.000\r\n".encode("ascii", errors="replace")
                        for ax in ("X", "Y", "Z")
                    )
                    self._serial.write(blob)
                    self._serial.flush()
                except Exception as e:
                    self._set_status(f"Voltage override off (set_*_v 0): {e}")
                    return
            self._set_status("Voltage override off — sent set_x_v/set_y_v/set_z_v 0.")
        else:
            self._volt_ov_cmd_v = {"X": 0.0, "Y": 0.0, "Z": 0.0}
            self._set_status(
                "Voltage override on — enable each axis; host sends set_*_v toward Test V spinboxes."
            )

    def _on_set_coil_voltages_clicked(self) -> None:
        """Apply doubleSpinBox_Test_X/Y/Z_V to Pico (set_x_v / set_y_v / set_z_v). Override must be on."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        if (
            self._volt_override_chk is None
            or len(self._volt_override_spins) != 3
        ):
            self._set_status("Voltage override UI is incomplete — Set coil voltages unavailable.")
            return
        if not self._volt_override_chk.isChecked():
            self._set_status(
                "Turn on voltage override first — then Set applies Test V spinboxes."
            )
            return
        try:
            for ax in ("X", "Y", "Z"):
                row = next((r for r in self._axis_rows if r[0] == ax), None)
                spin = self._volt_override_spins.get(ax)
                if spin is None or row is None:
                    continue
                tgt = max(0.0, float(spin.value()))
                en = self._coils_axis_enabled(ax)
                if not en:
                    self._volt_ov_cmd_v[ax] = 0.0
                    self._send_axis_set_v(ax, 0.0)
                    continue
                self._volt_ov_cmd_v[ax] = tgt
                self._send_axis_set_v(ax, tgt)
            self._set_status(
                "Set coil voltages: sent set_x_v / set_y_v / set_z_v from Test V spinboxes."
            )
        except Exception as e:
            self._set_status(f"Set coil voltages failed: {e}")

    def _send_axis_set_v(self, axis: str, volts: float) -> None:
        if self._serial is None:
            return
        axl = axis.lower()
        v = max(0.0, min(45.0, float(volts)))
        line = f"set_{axl}_v {v:.3f}\r\n"
        try:
            self._serial.write(line.encode("ascii", errors="replace"))
            self._serial.flush()
        except Exception as e:
            self._set_status(f"{axis} set_*_v write failed: {e}")

    def _volt_override_pwm_adjust(self, kv: dict[str, str]) -> None:
        """Nudge set_<axis>_v using TM:: coil_V_* vs doubleSpinBox_Test_*_V (Pico 5.x voltage mode)."""
        if self._volt_override_chk is None or not self._volt_override_chk.isChecked():
            return
        if self._serial is None:
            return
        mk = self._tm_int(kv, "meas_ok")
        trust_meas = (mk != 0) if mk is not None else True
        v_cmd_cap = 20.0 if trust_meas else min(20.0, _VOLT_OVERRIDE_MAX_CMD_V_IF_MEAS_BAD)
        for ax in ("X", "Y", "Z"):
            row = next((r for r in self._axis_rows if r[0] == ax), None)
            if row is None or not self._coils_axis_enabled(ax):
                continue
            vbus = self._tm_float(kv, f"coil_V_{ax}")
            spin = self._volt_override_spins.get(ax)
            if spin is None:
                continue
            target = float(spin.value())
            tol = _TEST_VOLT_TOL_V
            if target <= 1e-6:
                if self._volt_ov_cmd_v[ax] > 1e-6:
                    self._volt_ov_cmd_v[ax] = 0.0
                    self._send_axis_set_v(ax, 0.0)
                continue
            v_eff = 0.0 if vbus is None else float(vbus)
            err = target - v_eff
            cmd = float(self._volt_ov_cmd_v[ax])
            if abs(err) <= tol:
                continue
            step_v = max(0.05, min(0.5, abs(err) * 0.15))
            if err > tol:
                cmd = min(min(target, v_cmd_cap), cmd + step_v)
            else:
                cmd = max(0.0, cmd - step_v)
            cmd = max(0.0, min(v_cmd_cap, cmd))
            if abs(cmd - float(self._volt_ov_cmd_v[ax])) > 1e-4:
                self._volt_ov_cmd_v[ax] = cmd
                self._send_axis_set_v(ax, cmd)

    def _update_test_volt_lcds_from_tm(self, kv: dict[str, str]) -> None:
        if not self._volt_override_lcds:
            return
        meas_ok = self._tm_int(kv, "meas_ok")
        trust_meas = meas_ok != 0 if meas_ok is not None else True
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        neutral_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NEUTRAL};"
        )
        ov = (
            self._volt_override_chk is not None
            and self._volt_override_chk.isChecked()
        )
        for ax in ("X", "Y", "Z"):
            lcd = self._volt_override_lcds.get(ax)
            if lcd is None:
                continue
            v = self._tm_float(kv, f"coil_V_{ax}")
            en = self._coils_axis_enabled(ax)
            spin = self._volt_override_spins.get(ax)
            target = float(spin.value()) if spin is not None else 0.0

            if v is None:
                self._lcd_set_if_changed(
                    lcd, "---", nodata_style, self._lcd_test_volts_cache
                )
                continue
            if not ov:
                self._lcd_set_if_changed(
                    lcd, f"{v:.2f}", neutral_style, self._lcd_test_volts_cache
                )
                continue
            if not trust_meas:
                self._lcd_set_if_changed(
                    lcd, f"{v:.2f}", neutral_style, self._lcd_test_volts_cache
                )
                continue
            if not en:
                self._lcd_set_if_changed(
                    lcd, f"{v:.2f}", neutral_style, self._lcd_test_volts_cache
                )
                continue
            c = _test_volt_lcd_digit_color(v, target)
            self._lcd_set_if_changed(
                lcd,
                f"{v:.2f}",
                f"background-color: {_MEAS_LCD_BG}; color: {c};",
                self._lcd_test_volts_cache,
            )

    def _on_safe_calibrator(self) -> None:
        """Send `safe`: Pico coils off, zero setpoints, disables — not latched (Pico ≥3.37)."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        try:
            self._dbg(1, "action: SAFE (safe)")
            if self._volt_override_chk is not None and self._volt_override_chk.isChecked():
                self._volt_ov_cmd_v = {"X": 0.0, "Y": 0.0, "Z": 0.0}
            self._serial.write(b"safe\r\n")
            self._serial.flush()
            self._set_status("SAFE sent (coils off; re-enable / Set to run again).")
        except Exception as e:
            self._set_status(f"SAFE write failed: {e}")

    def _on_reset_calibrator(self) -> None:
        """Send safe_reset: Pico clears enables and commanded V; all bridge PWM outputs low (same as SAFE)."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        try:
            self._dbg(1, "action: Reset (safe_reset)")
            if self._volt_override_chk is not None and self._volt_override_chk.isChecked():
                self._volt_ov_cmd_v = {"X": 0.0, "Y": 0.0, "Z": 0.0}
            self._serial.write(b"safe_reset\r\n")
            self._serial.flush()
            self._set_status("safe_reset sent (Pico PWM/coils off).")
            self._pico_has_error = False
            self._update_status_leds()
        except Exception as e:
            self._set_status(f"Reset write failed: {e}")

    def _on_set_axis_ma(self, axis: str) -> None:
        """Send set_<axis>_v from doubleSpinBox_Test_<axis>_V (Pico 5.x); axis must be Enabled."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        row = next((r for r in self._axis_rows if r[0] == axis), None)
        if row is None:
            return
        _ax, _spin_ma, _pb, _lcd, _chk = row
        if not self._coils_axis_enabled(axis):
            self._set_status(
                "Coils are not enabled — turn on the coil enable checkbox before Set."
            )
            return
        vspin = self._volt_override_spins.get(axis)
        if vspin is None:
            self._set_status(
                f"Set {axis}: need doubleSpinBox_Test_{axis}_V (full voltage-override widget set in .ui)."
            )
            return
        val = max(0.0, float(vspin.value()))
        axl = axis.lower()
        line = f"set_{axl}_v {val:.3f}\r\n"
        try:
            self._dbg(1, "action: Set", axis, f"{val:.3f} V", "from", vspin.objectName())
            if self._debug_level >= 2:
                self._dbg(2, "Set TX", line.strip())
            self._serial.write(line.encode("ascii", errors="replace"))
            self._serial.flush()
            if self._volt_override_chk is not None and self._volt_override_chk.isChecked():
                self._volt_ov_cmd_v[axis] = val
            self._set_status(f"Set {axis}: {val:.3f} V (set_{axl}_v)")
        except Exception as e:
            self._set_status(f"Serial write failed: {e}")

    def _apply_tm_line(self, line: str) -> None:
        """Telemetry line: updates status LEDs; not copied to the text log."""
        line = self._repair_tm_orphan_set_x_prefix(line)
        kv = self._parse_tm_tokens(line)
        if self._debug_level >= 2:
            s_dbg = line.strip("\r\n").strip()
            if len(s_dbg) > 420:
                s_dbg = s_dbg[:417] + "..."
            has_sx = "set_X_v" in kv or "set_x_v" in kv
            has_xsig = "X_ma" in kv or "coil_V_X" in kv
            if self._tm_dbg_setx_absent_x_present_pending and (not has_sx) and has_xsig:
                self._tm_dbg_setx_absent_x_present_pending = False
                self._tm_dbg_first_tm_after_connect = False
                self._dbg(
                    2,
                    "TM dbg (no set_X_v/set_x_v token but X_ma or coil_V_X present):",
                    s_dbg,
                )
            elif self._tm_dbg_first_tm_after_connect:
                self._tm_dbg_first_tm_after_connect = False
                self._dbg(2, "TM dbg (first TM line this link):", s_dbg)
        self._cl_before_tm = self._closed_loop_ok
        va = self._tm_int(kv, "alarm")
        vs = self._tm_int(kv, "safe")
        if va is not None or vs is not None:
            self._pico_has_error = ((va or 0) != 0) or ((vs or 0) != 0)
        v = self._tm_int(kv, "cfg")
        if v is not None:
            self._configured_ok = v != 0
        v = self._tm_int(kv, "closed_loop")
        if v is not None:
            self._closed_loop_ok = v != 0
        mk = self._tm_int(kv, "meas_ok")
        if mk is not None:
            self._meas_ok = mk != 0
        self._update_status_leds()
        self._update_measured_lcds_from_tm(kv)
        self._update_test_volt_lcds_from_tm(kv)
        self._volt_override_pwm_adjust(kv)
        self._update_gauss_lcds_from_tm(kv)
        self._update_null_indicator_from_tm(kv)
        self._note_pico_liveness()
        self._append_tm_csv_row(kv)

    def _process_serial_line(self, line: str) -> None:
        s = line.strip("\r\n").strip()
        if s.startswith("\ufeff"):
            s = s[1:].lstrip()
        if not s:
            return
        if self._debug_level >= 3 and not re.match(r"(?i)^TM::", s):
            self._dbg(3, "RX (non-TM)", repr(s)[:500])
        # Case-insensitive prefix; length-safe payload (handles TXT:: vs TXT::␠ from firmware).
        m_txt = re.match(r"(?i)^TXT::\s*", s)
        if m_txt:
            payload = s[m_txt.end() :]
            if payload.strip() == "OK ALIVE":
                self._note_pico_liveness()
                return
            self._note_pico_liveness()
            pl = payload.strip()
            # Immediate fault LED: TM:: safe=1 can lag ~TELEM period; firmware echoes these at command time.
            if pl == "OK SAFE" or pl.startswith("ERROR: Safe State"):
                self._pico_has_error = True
                self._update_status_leds()
            elif pl.startswith("OK safe_reset") or pl.startswith("STATUS safe_reset OK"):
                self._pico_has_error = False
                self._update_status_leds()
            if self._debug_level >= 2:
                self._dbg(2, "TXT", payload[:220].replace("\r", " "))
            self._try_parse_pico_version_from_txt_payload(payload)
            self._append_pico_log_line(payload)
            return
        if re.match(r"(?i)^TM::", s):
            self._apply_tm_line(s)
            return
        if self._line_looks_like_tm_telemetry(s):
            self._apply_tm_line(s)
            return
        # Anything else (unprefixed boot noise, mis-framed lines): show so nothing is silent.
        if self._debug_level >= 2:
            self._dbg(2, "OTHER (unprefixed)", s[:220].replace("\r", " "))
        self._append_pico_log_line(s)

    def _serial_drain_bytes_only(self) -> int:
        """Read USB CDC into _rx_buf only (no line parsing). Used during Connect wait loops."""
        if self._serial is None:
            return 0
        try:
            chunk = self._serial.read(4096)
            if chunk:
                self._rx_buf.extend(chunk)
                return len(chunk)
        except Exception:
            pass
        return 0

    @staticmethod
    def _serial_clear_dtr_rts(ser: serial.Serial) -> None:
        """Avoid RP2040 reset / CDC glitch when the OS toggles control lines on port open (common on Windows)."""
        try:
            ser.dtr = False
            ser.rts = False
        except (AttributeError, ValueError, OSError):
            pass

    def _connect_rx_pump_slice(self) -> None:
        """Spread post-connect RX processing across timer slices so the window stays responsive."""
        if self._serial is None:
            self._connect_rx_pump_slices = 0
            return
        self._connect_rx_pump_slices += 1
        if self._connect_rx_pump_slices > _CONNECT_RX_PUMP_MAX_SLICES:
            self._dbg(1, "connect: RX pump stopped (slice cap)")
            self._connect_rx_pump_slices = 0
            pl = 5
            QTimer.singleShot(20, lambda pl=pl: self._post_connect_serial_catchup(pl))
            return
        QApplication.processEvents()
        self._poll_serial(max_lines=_CONNECT_RX_PUMP_SLICE_LINES)
        pending = bool(self._rx_buf)
        try:
            if self._serial.in_waiting > 0:
                pending = True
        except Exception:
            pass
        if pending:
            QTimer.singleShot(1, self._connect_rx_pump_slice)
        else:
            self._connect_rx_pump_slices = 0
            # Windows CDC can deliver hw_report/TXT:: a few ms after the pump sees an empty buffer.
            pl = 5
            QTimer.singleShot(20, lambda pl=pl: self._post_connect_serial_catchup(pl))

    def _post_connect_serial_catchup(self, passes_left: int) -> None:
        if self._serial is None or passes_left <= 0:
            return
        self._poll_serial()
        if passes_left > 1:
            nxt = passes_left - 1
            QTimer.singleShot(50, lambda n=nxt: self._post_connect_serial_catchup(n))

    def _poll_serial(self, max_lines: int | None = None) -> None:
        if self._serial is None:
            return
        if max_lines is None:
            line_cap = _MAX_SERIAL_LINES_PER_TICK
        else:
            line_cap = max(1, min(int(max_lines), _MAX_SERIAL_LINES_PER_TICK))
        try:
            # Drain up to 4 KiB per tick. On Windows, in_waiting can stay 0 until read() runs.
            chunk = self._serial.read(4096)
            if chunk:
                self._rx_buf.extend(chunk)
                if self._debug_level >= 2:
                    self._dbg(2, "serial read", len(chunk), "bytes; rx_buf total", len(self._rx_buf))
        except Exception:
            return
        processed = 0
        while processed < line_cap:
            # Prefer \n so a stray \r mid-line (before \n) does not split TM:: rows (fixes ".00 Y_ma=" garbage).
            nl = self._rx_buf.find(b"\n")
            if nl >= 0:
                raw = bytes(self._rx_buf[:nl])
                del self._rx_buf[: nl + 1]
                while raw.endswith(b"\r"):
                    raw = raw[:-1]
            else:
                cr = self._rx_buf.find(b"\r")
                if cr >= 0:
                    raw = bytes(self._rx_buf[:cr])
                    del self._rx_buf[: cr + 1]
                else:
                    break
            processed += 1
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                text = raw.decode("latin-1", errors="replace")
            try:
                self._process_serial_line(text)
            except Exception as e:
                try:
                    self._append_pico_log_line(
                        "[CalibratorUI] serial line handler error: %s" % (e,)
                    )
                except Exception:
                    pass
        if self._debug_level >= 1 and processed >= line_cap:
            nl = self._rx_buf.find(b"\n")
            cr = self._rx_buf.find(b"\r")
            if nl >= 0 or cr >= 0:
                self._dbg(
                    1,
                    "serial: processed",
                    processed,
                    "lines this tick (cap);",
                    len(self._rx_buf),
                    "bytes still buffered with more line(s) pending",
                )
        self._check_pico_alive_stale()

    def _note_pico_liveness(self) -> None:
        """Update last traffic time; clear stale LED/status if recovering."""
        self._serial_saw_tm_txt_this_link = True
        self._last_alive_reply_ts = time.monotonic()
        if not self._pico_alive_stale:
            return
        self._pico_alive_stale = False
        self._update_status_leds()
        self._refresh_connection_status_line()

    def _check_pico_alive_stale(self) -> None:
        """Stale = no TM::/TXT:: for too long while connected (yellow LED + status)."""
        if self._serial is None:
            return
        now = time.monotonic()
        stale = False
        if not self._serial_saw_tm_txt_this_link:
            # Do not use _last_alive_reply_ts until real traffic — avoids false STALE if that field is stale.
            if self._connect_mono_ts is not None and (
                now - self._connect_mono_ts
            ) > _LINK_STALE_BEFORE_FIRST_TRAFFIC_S:
                stale = True
        elif self._last_alive_reply_ts is not None and (
            now - self._last_alive_reply_ts
        ) > _LINK_STALE_AFTER_TRAFFIC_S:
            stale = True
        if stale != self._pico_alive_stale:
            self._pico_alive_stale = stale
            self._update_status_leds()
            self._refresh_connection_status_line()
            if stale:
                if not self._keepalive_stale_dbg_done:
                    self._dbg(
                        1,
                        "link: marked STALE (no Pico traffic in time window — TXT/TM)",
                    )
                    self._keepalive_stale_dbg_done = True
            else:
                self._keepalive_stale_dbg_done = False
                self._dbg(1, "link: recovered (Pico traffic seen)")

    def _update_status_leds(self) -> None:
        """Connected: red/yellow/green. Configured / closed loop: wired when protocol exists."""
        if self._serial is None:
            _apply_led_color(self._led_connected, "red")
            self._pico_has_error = False
        elif self._pico_has_error or self._pico_alive_stale:
            _apply_led_color(self._led_connected, "yellow")
        else:
            _apply_led_color(self._led_connected, "green")

        if self._configured_ok:
            _apply_led_color(self._led_configured, "green")
        else:
            _apply_led_color(self._led_configured, "gray")

        if self._closed_loop_ok:
            _apply_led_color(self._led_closed_loop, "green")
        else:
            _apply_led_color(self._led_closed_loop, "gray")

        # Initialized: INA / sense path ready (meas_ok from Pico TM).
        if self._serial is None:
            _apply_led_color(self._led_initialized, "gray")
        elif self._meas_ok is True:
            _apply_led_color(self._led_initialized, "green")
        elif self._meas_ok is False:
            _apply_led_color(self._led_initialized, "yellow")
        else:
            _apply_led_color(self._led_initialized, "yellow")

        # DC State: green in closed-loop; red on fault or fall-out of closed-loop; gray otherwise.
        if self._serial is None:
            _apply_led_color(self._led_dc_state, "gray")
        elif self._pico_has_error:
            _apply_led_color(self._led_dc_state, "red")
        elif self._closed_loop_ok:
            _apply_led_color(self._led_dc_state, "green")
        elif self._cl_before_tm and not self._closed_loop_ok:
            _apply_led_color(self._led_dc_state, "red")
        else:
            _apply_led_color(self._led_dc_state, "gray")

    def set_pico_error(self, has_error: bool) -> None:
        """Call when host detects Pico fault (e.g. serial line / future status). Yellow if True."""
        self._pico_has_error = bool(has_error)
        self._update_status_leds()

    def set_configured_led(self, ok: bool) -> None:
        """Future: set mA acknowledged by Pico."""
        self._configured_ok = bool(ok)
        self._update_status_leds()

    def set_closed_loop_led(self, ok: bool) -> None:
        """Future: closed-loop status from Pico telemetry."""
        self._closed_loop_ok = bool(ok)
        self._update_status_leds()

    def _set_connected_ui(self, connected: bool) -> None:
        if connected:
            self._btn_connect.setText("Disconnect")
            self._refresh_connection_status_line()
            self._combo_port.setEnabled(False)
            self._combo_baud.setEnabled(False)
        else:
            self._btn_connect.setText("Connect")
            self._status_conn.setText("Connection: Disconnected")
            self._combo_port.setEnabled(True)
            self._combo_baud.setEnabled(True)
        self._update_status_leds()

    def _on_connect_clicked(self) -> None:
        if self._serial is not None:
            self._disconnect()
            return
        self._connect()

    def _connect(self) -> None:
        port = self._current_port()
        if not port:
            self._set_status("Select a COM port.")
            QMessageBox.warning(self._win, "Calibrator", "Select a COM port.")
            return
        baud = self._current_baud()
        try:
            # timeout=0: non-blocking reads in _poll_serial (Windows often needs read() not only in_waiting).
            self._serial = serial.Serial(
                port,
                baud,
                timeout=0,
                write_timeout=2,
                dsrdtr=False,
                rtscts=False,
            )
            self._serial_clear_dtr_rts(self._serial)
        except Exception as e:
            self._set_status(f"Open failed: {e}")
            QMessageBox.critical(self._win, "Calibrator", f"Could not open {port}:\n{e}")
            self._serial = None
            return
        self._dbg(
            1,
            "connect: opened",
            port,
            baud,
            "soft_reset_on_connect=",
            int(self._soft_reset_on_connect_pref()),
        )
        self._pico_has_error = False
        self._configured_ok = False
        self._closed_loop_ok = False
        self._meas_ok = None
        self._cl_before_tm = False
        self._pico_version = None
        self._pico_alive_stale = False
        self._last_alive_reply_ts = None
        self._serial_saw_tm_txt_this_link = False
        self._keepalive_stale_dbg_done = False
        self._tm_dbg_first_tm_after_connect = self._debug_level >= 2
        self._tm_dbg_setx_absent_x_present_pending = self._debug_level >= 2
        self._connect_mono_ts = None  # set when RX timer starts (after settle), not at USB open
        self._save_serial_ini()
        self._rx_buf.clear()
        self._connect_rx_pump_slices = 0
        # Do not start the serial poll timer until after the handshake wait: otherwise
        # processEvents() during the wait runs _poll_serial and floods QTextEdit (Not Responding).
        self._reset_measured_lcds_no_data()
        self._set_connected_ui(True)
        self._set_status(f"Opened {port} @ {baud} baud.")
        if self._soft_reset_on_connect_pref():
            # Stuck >>> REPL: Ctrl+C then Ctrl+D = soft reset → main.py runs again.
            try:
                self._serial.write(b"\x03\x04")
                self._serial.flush()
            except Exception:
                pass
            self._set_status("Pico soft reset sent; waiting for boot…")
            self._dbg(1, "connect: sent soft reset (Ctrl+C Ctrl+D); boot wait 1.6s")
            t_boot = time.monotonic() + 1.6
            settle_bytes = 0
            while time.monotonic() < t_boot:
                QApplication.processEvents()
                time.sleep(0.02)
                settle_bytes += self._serial_drain_bytes_only()
            self._dbg(1, "connect: boot-wait drained", settle_bytes, "raw bytes (pre-handshake)")
        else:
            # Firmware already running (e.g. READY DEPLOY / SAFE): do not reset; drain CDC and query.
            self._set_status("Connecting (no soft reset)…")
            self._dbg(
                1,
                "connect: no soft reset; settle %.2fs + drain serial"
                % (_CONNECT_SETTLE_NO_SOFT_RESET_S,),
            )
            t_settle = time.monotonic() + _CONNECT_SETTLE_NO_SOFT_RESET_S
            settle_bytes = 0
            while time.monotonic() < t_settle:
                QApplication.processEvents()
                time.sleep(0.02)
                settle_bytes += self._serial_drain_bytes_only()
            self._dbg(1, "connect: settle drained", settle_bytes, "raw bytes (pre-handshake)")
        self._set_status(f"Opened {port} @ {baud} baud.")
        # Baseline for "no traffic yet" STALE: opening the port can predate CDC + firmware streaming by seconds.
        self._connect_mono_ts = time.monotonic()
        self._serial_timer.start()
        QTimer.singleShot(0, self._connect_rx_pump_slice)
        QTimer.singleShot(100, self._send_axis_enables_to_pico)
        # Boot TXT:: is emitted once at Pico start; if we did not soft-reset, that stream was missed.
        if not self._soft_reset_on_connect_pref():
            QTimer.singleShot(280, self._request_hw_report_after_connect)

    def _send_axis_enables_to_pico(self) -> None:
        """After connect: push set_*_v from Test V spinboxes (when present), then enable_X/Y/Z.

        Pico 5.x applies PWM only when an axis is enabled *and* set_*_v > 0. Sending enables alone
        leaves set_*_v at zero on the Pico; the spin values are the single source for command volts.
        """
        if self._serial is None:
            return
        try:
            pre = b""
            if len(self._volt_override_spins) == 3:
                for ax in ("X", "Y", "Z"):
                    row = next((r for r in self._axis_rows if r[0] == ax), None)
                    spin = self._volt_override_spins.get(ax)
                    if spin is None or row is None:
                        continue
                    tgt = max(0.0, float(spin.value()))
                    en = self._coils_axis_enabled(ax)
                    axl = ax.lower()
                    if not en:
                        self._volt_ov_cmd_v[ax] = 0.0
                        pre += f"set_{axl}_v 0.000\r\n".encode("ascii", errors="replace")
                    else:
                        self._volt_ov_cmd_v[ax] = tgt
                        pre += f"set_{axl}_v {tgt:.3f}\r\n".encode("ascii", errors="replace")
            parts = b"".join(
                f"enable_{ax.lower()} {1 if self._coils_axis_enabled(ax) else 0}\r\n".encode(
                    "ascii", errors="replace"
                )
                for ax in ("X", "Y", "Z")
            )
            self._serial.write(pre + parts)
            self._serial.flush()
            self._dbg(
                1,
                "connect: sent",
                ("set_*_v then " if pre else "") + "enable_x/y/z from GUI",
            )
        except Exception as e:
            self._dbg(1, "connect: enable send failed:", e)

    def _on_master_coils_enable_changed(self, _state: int = 0) -> None:
        """Single master checkbox: send enable_x/y/z to Pico (not persisted to ini)."""
        if self._master_coils_enable is None:
            return
        on = self._master_coils_enable.isChecked()
        if self._serial is None:
            return
        iv = 1 if on else 0
        try:
            blob = b"".join(
                f"enable_{ax.lower()} {iv}\r\n".encode("ascii", errors="replace")
                for ax in ("X", "Y", "Z")
            )
            self._serial.write(blob)
            self._serial.flush()
            self._dbg(1, "master coils enable:", iv)
        except Exception as e:
            self._set_status(f"enable write failed: {e}")
            return
        if self._volt_override_chk is not None and self._volt_override_chk.isChecked():
            if not on:
                self._volt_ov_cmd_v = {"X": 0.0, "Y": 0.0, "Z": 0.0}
            else:
                for ax in ("X", "Y", "Z"):
                    spin = self._volt_override_spins.get(ax)
                    if spin is None or float(spin.value()) <= 1e-6:
                        continue
                    if float(self._volt_ov_cmd_v.get(ax, 0.0)) > 1e-6:
                        continue
                    v0 = max(0.0, float(spin.value()))
                    self._volt_ov_cmd_v[ax] = v0
                    self._send_axis_set_v(ax, v0)
                    self._dbg(
                        1,
                        "volt override: immediate set_*_v from Test V spin (master enable)",
                        ax,
                        v0,
                        "V",
                    )

    def _on_axis_enable_changed(self, axis: str) -> None:
        """Persist checkbox to ini; if connected, notify Pico immediately."""
        if self._master_coils_enable is not None:
            return
        row = next((r for r in self._axis_rows if r[0] == axis), None)
        if row is None:
            return
        chk = row[4]
        if chk is None:
            return
        self._ini.set("settings", f"enable_{axis}", "1" if chk.isChecked() else "0")
        save_ini(self._ini)
        if self._serial is None:
            return
        val = 1 if chk.isChecked() else 0
        axl = axis.lower()
        try:
            self._serial.write(f"enable_{axl} {val}\r\n".encode("ascii", errors="replace"))
            self._serial.flush()
            self._dbg(1, "enable:", axis, val)
        except Exception as e:
            self._set_status(f"enable_{axl} write failed: {e}")
            return
        if (
            self._volt_override_chk is not None
            and self._volt_override_chk.isChecked()
            and val == 0
        ):
            self._volt_ov_cmd_v[axis] = 0.0
        if (
            self._volt_override_chk is not None
            and self._volt_override_chk.isChecked()
            and val != 0
        ):
            spin = self._volt_override_spins.get(axis)
            if spin is not None and float(spin.value()) > 1e-6:
                if float(self._volt_ov_cmd_v[axis]) <= 1e-6:
                    v0 = max(0.0, float(spin.value()))
                    self._volt_ov_cmd_v[axis] = v0
                    self._send_axis_set_v(axis, v0)
                    self._dbg(
                        1,
                        "volt override: immediate set_*_v from Test V spin on enable",
                        axis,
                        v0,
                        "V",
                    )

    def _request_hw_report_after_connect(self) -> None:
        """Ask Pico to re-print hw_report so textEdit gets boot-equivalent TXT:: after a late COM open."""
        if self._serial is None:
            return
        try:
            self._serial.write(b"hw_report\r\n")
            self._serial.flush()
            self._dbg(1, "connect: sent hw_report (boot TXT:: was likely missed without soft reset)")
        except Exception as e:
            self._dbg(1, "connect: hw_report send failed:", e)

    def _disconnect(self) -> None:
        self._dbg(1, "disconnect: stopping timers and closing serial")
        self._connect_rx_pump_slices = 0
        self._connect_mono_ts = None
        self._last_alive_reply_ts = None
        self._serial_saw_tm_txt_this_link = False
        self._pico_alive_stale = False
        self._keepalive_stale_dbg_done = False
        self._tm_dbg_first_tm_after_connect = False
        self._tm_dbg_setx_absent_x_present_pending = False
        self._serial_timer.stop()
        self._rx_buf.clear()
        if self._serial is not None:
            try:
                self._serial.write(
                    b"enable_x 0\r\nenable_y 0\r\nenable_z 0\r\nhost_disconnect\r\n"
                )
                self._serial.flush()
                time.sleep(0.08)
            except Exception:
                pass
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._lcd_meas_cache.clear()
        self._lcd_volts_cache.clear()
        self._lcd_test_volts_cache.clear()
        self._lcd_gauss_cache.clear()
        if self._null_frame is not None:
            self._null_indicator_active = None
            self._apply_null_indicator_style(False, force=True)
        self._pico_has_error = False
        self._configured_ok = False
        self._closed_loop_ok = False
        self._meas_ok = None
        self._cl_before_tm = False
        self._pico_version = None
        self._save_serial_ini()
        self._set_connected_ui(False)
        self._set_status("Disconnected.")
        self._reset_measured_lcds_no_data()

    def shutdown(self) -> None:
        self._disconnect()
        self._save_serial_ini()


def main() -> int:
    app = QApplication(sys.argv)
    win = _load_ui()
    if win is None:
        return 1
    win.setWindowTitle("Calibrator — UI %s" % CALIBRATOR_UI_VERSION)

    try:
        ctrl = CalibratorController(win)
    except Exception as e:
        QMessageBox.critical(None, "Calibrator", str(e))
        return 1

    app.aboutToQuit.connect(ctrl.shutdown)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
