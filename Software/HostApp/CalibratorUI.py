#!/usr/bin/env python3
"""
CalibratorUI — PySide6 host for the CoilDriver Pico (serial).

Loads CalibratorUI.ui from this directory. Settings in CalibratorUI.ini (ASCII).

Serial line protocol (newline-terminated):
  TXT:: <text> — shown in textEdit_CalibratorTestOutput (boot, I2C scan, command replies).
  TM:: key=value ... — telemetry: LEDs (alarm, cfg, closed_loop, ramp, settle, meas_ok); measured LCDs (meas_ok,
    X_ma/Y_ma/Z_ma, set_*_ma); coil bus volts (coil_V_X/Y/Z).
  On connect: host sends version + hw_report (Pico replies OK VERSION … and full TXT:: I2C/INA/H-bridge summary).
  While connected: host sends alive ~1 Hz; Pico replies TXT:: OK ALIVE (not logged). Stale >3 s → yellow LED + status hint.
  On Disconnect / app quit: host sends host_disconnect (coils off, deploy-ready; legacy abort still on Pico).
  Status bar Reset sends safe_reset (clear SAFE); SAFE button sends safe.
  Settings (menu, saved in CalibratorUI.ini [settings]): PWM 3/5 kHz, max mA (20–100 + design max).
    Each axis Set sends: set_<axis>_ma, set_<axis>_pwm_hz.

Run:
    pip install -r requirements.txt
    python CalibratorUI.py
"""

from __future__ import annotations

import configparser
import re
import sys
import time
from pathlib import Path

import serial
import serial.tools.list_ports
from PySide6.QtCore import QFile, QIODevice, Qt, QTimer
from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

# Match Software/Pico/config.py MAX_CURRENT_PER_COIL_MA (drive / shunt design limit).
PICO_MAX_COIL_MA = 500.0
_PWM_FREQ_HZ_CHOICES = (3000, 5000)
_MAX_CURRENT_MA_CHOICES = (20.0, 50.0, 80.0, 100.0, PICO_MAX_COIL_MA)

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
        cp.read(_INI_PATH, encoding="ascii")
    if not cp.has_section("serial"):
        cp.add_section("serial")
    if not cp.has_option("serial", "port"):
        cp.set("serial", "port", "")
    if not cp.has_option("serial", "baud"):
        cp.set("serial", "baud", "115200")
    if not cp.has_section("settings"):
        cp.add_section("settings")
    if not cp.has_option("settings", "pwm_freq_hz"):
        cp.set("settings", "pwm_freq_hz", "5000")
    if not cp.has_option("settings", "max_ma_mA"):
        cp.set("settings", "max_ma_mA", "100")
    return cp


def save_ini(cp: configparser.ConfigParser) -> None:
    with open(_INI_PATH, "w", encoding="ascii", newline="\n") as f:
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


def _volts_lcd_digit_color(v: float) -> str:
    """12 V target: green 11.8–12.3; red <11.8 or >12.5; amber (12.3, 12.5]."""
    if v < _COIL_V_LOW_RED:
        return _MEAS_LCD_RED
    if v > _COIL_V_AMBER_HI:
        return _MEAS_LCD_RED
    if v > _COIL_V_GREEN_HI:
        return _MEAS_LCD_AMBER
    return _MEAS_LCD_GREEN


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

    def __init__(self, win: QMainWindow) -> None:
        self._win = win
        self._ini = load_ini()
        self._serial: serial.Serial | None = None
        # Yellow "Connected" LED when serial is open but Pico reports fault (wired later).
        self._pico_has_error: bool = False
        # No OK ALIVE reply within timeout (firmware hung / wrong protocol).
        self._pico_alive_stale: bool = False
        self._last_alive_reply_ts: float | None = None
        self._connect_mono_ts: float | None = None
        # Placeholders until host↔Pico protocol (set mA ack, closed-loop telem).
        self._configured_ok: bool = False
        self._closed_loop_ok: bool = False
        self._pico_version: str | None = None
        self._settings_pwm_hz: int = 5000
        self._settings_max_ma: float = 100.0
        # TM-derived (DC State LED, Initialized); _cl_before_tm saved before each TM line updates closed_loop_ok.
        self._meas_ok: bool | None = None
        self._ramp = False
        self._settle = False
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

        self._axis_rows: list[
            tuple[str, QSpinBox, QPushButton, QLCDNumber, QCheckBox]
        ] = []
        for ax in ("X", "Y", "Z"):
            sp = win.findChild(QSpinBox, f"spinBox_{ax}mA_target")
            pb = win.findChild(QPushButton, f"pushButton_{ax}_Set_mA")
            lcd = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Measured")
            chk = win.findChild(QCheckBox, f"checkBox_{ax}_Enabled")
            if not sp or not pb or not lcd or not chk:
                raise RuntimeError(
                    f"UI missing coil widgets for axis {ax} "
                    f"(spinBox_{ax}mA_target, pushButton_{ax}_Set_mA, "
                    f"lcdNumber_{ax}_Measured, checkBox_{ax}_Enabled)"
                )
            _init_measured_ma_lcd(lcd)
            sp.setRange(0, 5000)
            sp.setValue(0)
            chk.setChecked(False)
            self._axis_rows.append((ax, sp, pb, lcd, chk))

        self._axis_volts_lcd: list[tuple[str, QLCDNumber]] = []
        for ax in ("X", "Y", "Z"):
            vlcd = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Volts")
            if not vlcd:
                raise RuntimeError(
                    f"UI missing coil volts LCD for axis {ax} (lcdNumber_{ax}_Volts)"
                )
            _init_volts_lcd(vlcd)
            self._axis_volts_lcd.append((ax, vlcd))

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
        self._serial_timer = QTimer(self._win)
        self._serial_timer.setInterval(50)
        self._serial_timer.timeout.connect(self._poll_serial)
        # alive ~1 Hz: Pico slave LCD link + explicit OK ALIVE for host liveness (not logged).
        self._heartbeat_timer = QTimer(self._win)
        self._heartbeat_timer.setInterval(1000)
        self._heartbeat_timer.timeout.connect(self._send_pico_link_heartbeat)

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
            "Send safe_reset to Pico — clears SAFE so mA / PWM work again (same role as old GUI Reset)."
        )
        sb = win.statusBar()
        sb.addWidget(self._status_main, 1)
        sb.addPermanentWidget(self._btn_reset)
        sb.addPermanentWidget(self._status_conn)

        self._populate_baud_combo()
        self._refresh_com_ports(select_saved=True)
        self._apply_ini_to_widgets()
        self._apply_settings_from_ini()

        self._setup_settings_menu()

        self._btn_connect.clicked.connect(self._on_connect_clicked)
        self._btn_safe.clicked.connect(self._on_safe_calibrator)
        self._btn_reset.clicked.connect(self._on_reset_calibrator)
        self._btn_clear_text.clicked.connect(self._on_clear_calibrator_text)
        self._combo_port.currentIndexChanged.connect(self._on_serial_widget_changed)
        self._combo_baud.currentIndexChanged.connect(self._on_serial_widget_changed)

        for ax, _sp, pb, _lcd, _chk in self._axis_rows:
            pb.clicked.connect(lambda checked=False, a=ax: self._on_set_axis_ma(a))

        self._set_connected_ui(False)
        self._set_status("Ready.")

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

    def _settings_persist_to_ini(self) -> None:
        self._ini.set("settings", "pwm_freq_hz", str(self._settings_pwm_hz))
        self._ini.set("settings", "max_ma_mA", str(self._settings_max_ma))
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

    def _settings_save(self) -> None:
        self._settings_persist_to_ini()
        self._set_status("Settings saved to CalibratorUI.ini.")

    def _settings_restore(self) -> None:
        self._ini = load_ini()
        self._apply_settings_from_ini()
        self._apply_ini_to_widgets()
        self._set_status("Settings restored from CalibratorUI.ini.")

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

    def _try_parse_pico_version_from_txt_payload(self, payload: str) -> None:
        """Recognize boot STATUS VERSION … or command reply OK VERSION … from Pico."""
        s = payload.strip()
        m = re.match(r"OK VERSION\s+(\S+)", s, re.I)
        if m:
            self._pico_version = m.group(1)
            self._note_pico_liveness()
            self._refresh_connection_status_line()
            return
        parts = s.split()
        for i, p in enumerate(parts):
            if p.upper() == "VERSION" and i + 1 < len(parts):
                ver = parts[i + 1]
                if re.match(r"^\d+(?:\.\d+)?$", ver):
                    self._pico_version = ver
                    self._note_pico_liveness()
                    self._refresh_connection_status_line()
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
            suffix = " — keepalive timeout"
        if self._pico_version:
            self._status_conn.setText(
                f"Connection: Connected ({port} @ {baud} baud) — Pico {self._pico_version}{suffix}"
            )
        else:
            self._status_conn.setText(
                f"Connection: Connected ({port} @ {baud} baud) — Pico ...{suffix}"
            )

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

    def _update_measured_lcds_from_tm(self, kv: dict[str, str]) -> None:
        """Refresh X/Y/Z measured LCDs from TM:: key=value (realtime for all axes)."""
        meas_ok = self._tm_int(kv, "meas_ok")
        if meas_ok is None:
            meas_ok = 1  # legacy TM lines without meas_ok
        for ax, sp, _pb, lcd, _chk in self._axis_rows:
            if meas_ok == 0:
                lcd.display("---")
                lcd.setStyleSheet(
                    f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
                )
                continue
            m = self._tm_float(kv, f"{ax}_ma")
            tgt = self._tm_float(kv, f"set_{ax}_ma")
            lim = self._tm_float(kv, f"lim_{ax}_ma")
            if tgt is None:
                tgt = float(sp.value())
            if lim is None:
                lim = float(self._settings_max_ma)
            if m is None:
                lcd.display("---")
                lcd.setStyleSheet(
                    f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
                )
                continue
            lcd.display(f"{m:.1f}")
            c = _meas_lcd_digit_color(m, tgt, lim)
            lcd.setStyleSheet(f"background-color: {_MEAS_LCD_BG}; color: {c};")

        self._update_volts_lcds_from_tm(kv)

    def _update_volts_lcds_from_tm(self, kv: dict[str, str]) -> None:
        """Refresh X/Y/Z coil bus V from TM:: coil_V_X/Y/Z (INA bus voltage)."""
        meas_ok = self._tm_int(kv, "meas_ok")
        if meas_ok is None:
            meas_ok = 1
        for ax, lcd in self._axis_volts_lcd:
            if meas_ok == 0:
                lcd.display("---")
                lcd.setStyleSheet(
                    f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
                )
                continue
            v = self._tm_float(kv, f"coil_V_{ax}")
            if v is None:
                lcd.display("---")
                lcd.setStyleSheet(
                    f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
                )
                continue
            lcd.display(f"{v:.2f}")
            c = _volts_lcd_digit_color(v)
            lcd.setStyleSheet(f"background-color: {_MEAS_LCD_BG}; color: {c};")

    def _reset_measured_lcds_no_data(self) -> None:
        for _ax, _sp, _pb, lcd, _chk in self._axis_rows:
            lcd.display("---")
            lcd.setStyleSheet(
                f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
            )
        for _ax, lcd in self._axis_volts_lcd:
            lcd.display("---")
            lcd.setStyleSheet(
                f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
            )

    def _on_safe_calibrator(self) -> None:
        """Immediate SAFE: Pico enters latched Safe State (PWM off); no delay."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        try:
            self._serial.write(b"safe\r\n")
            self._serial.flush()
            self._set_status("SAFE sent.")
        except Exception as e:
            self._set_status(f"SAFE write failed: {e}")

    def _on_reset_calibrator(self) -> None:
        """Clear Pico SAFE (safe_reset); allows set_*_ma again."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        try:
            self._serial.write(b"safe_reset\r\n")
            self._serial.flush()
            self._set_status("Reset (safe_reset) sent.")
            self._pico_has_error = False
            self._update_status_leds()
        except Exception as e:
            self._set_status(f"Reset write failed: {e}")

    def _on_set_axis_ma(self, axis: str) -> None:
        """Send set_<axis>_ma for this axis only if that axis is Enabled."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        row = next((r for r in self._axis_rows if r[0] == axis), None)
        if row is None:
            return
        _ax, spin, _pb, _lcd, chk = row
        if not chk.isChecked():
            self._set_status(f"Axis {axis} is not enabled — enable before Set.")
            return
        val = float(spin.value())
        axl = axis.lower()
        hz = self._settings_pwm_hz
        lines = [
            f"set_{axl}_ma {val:.2f}\r\n",
            f"set_{axl}_pwm_hz {hz}\r\n",
        ]
        try:
            # Pico latches SAFE on `safe`; set_*_ma / set_*_pwm_hz are refused until safe_reset.
            self._serial.write(b"safe_reset\r\n")
            for line in lines:
                self._serial.write(line.encode("ascii", errors="replace"))
            self._serial.flush()
            self._set_status(
                f"Set {axis}: {val:.2f} mA, PWM {hz} Hz"
            )
        except Exception as e:
            self._set_status(f"Serial write failed: {e}")

    def _apply_tm_line(self, line: str) -> None:
        """Telemetry line: updates status LEDs; not copied to the text log."""
        kv = self._parse_tm_tokens(line)
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
        r = self._tm_int(kv, "ramp")
        if r is not None:
            self._ramp = r != 0
        s = self._tm_int(kv, "settle")
        if s is not None:
            self._settle = s != 0
        self._update_status_leds()
        self._update_measured_lcds_from_tm(kv)

    def _process_serial_line(self, line: str) -> None:
        s = line.strip("\r\n").strip()
        if s.startswith("\ufeff"):
            s = s[1:].lstrip()
        if not s:
            return
        # Case-insensitive prefix; length-safe payload (handles TXT:: vs TXT::␠ from firmware).
        m_txt = re.match(r"(?i)^TXT::\s*", s)
        if m_txt:
            payload = s[m_txt.end() :]
            if payload.strip() == "OK ALIVE":
                self._note_pico_liveness()
                return
            self._try_parse_pico_version_from_txt_payload(payload)
            self._append_pico_log_line(payload)
            return
        if re.match(r"(?i)^TM::", s):
            self._apply_tm_line(s)
            return
        # Anything else (unprefixed boot noise, mis-framed lines): show so nothing is silent.
        self._append_pico_log_line(s)

    def _poll_serial(self) -> None:
        if self._serial is None:
            return
        try:
            # Drain up to 4 KiB per tick. On Windows, in_waiting can stay 0 until read() runs.
            chunk = self._serial.read(4096)
            if chunk:
                self._rx_buf.extend(chunk)
        except Exception:
            return
        while True:
            # Support \n, \r\n, and \r-only; \r-only never matches find(b"\n") alone.
            nl = self._rx_buf.find(b"\n")
            cr = self._rx_buf.find(b"\r")
            if nl >= 0 and (cr < 0 or nl < cr):
                raw = bytes(self._rx_buf[:nl])
                del self._rx_buf[: nl + 1]
                if raw.endswith(b"\r"):
                    raw = raw[:-1]
            elif cr >= 0:
                raw = bytes(self._rx_buf[: cr])
                del self._rx_buf[: cr + 1]
            else:
                break
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
        self._check_pico_alive_stale()

    def _note_pico_liveness(self) -> None:
        """Update last-alive time; clear keepalive-stale LED/status if recovering."""
        self._last_alive_reply_ts = time.monotonic()
        if not self._pico_alive_stale:
            return
        self._pico_alive_stale = False
        self._update_status_leds()
        self._refresh_connection_status_line()

    def _check_pico_alive_stale(self) -> None:
        """If OK ALIVE stops for >3 s while connected, flag stale (yellow LED + status)."""
        if self._serial is None:
            return
        now = time.monotonic()
        stale = False
        if self._last_alive_reply_ts is None:
            if self._connect_mono_ts is not None and (now - self._connect_mono_ts) > 3.0:
                stale = True
        elif (now - self._last_alive_reply_ts) > 3.0:
            stale = True
        if stale != self._pico_alive_stale:
            self._pico_alive_stale = stale
            self._update_status_leds()
            self._refresh_connection_status_line()

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

        # DC State: amber during ramp or settle; green in closed-loop PI (quasi-DC); red on fault or fall-out.
        if self._serial is None:
            _apply_led_color(self._led_dc_state, "gray")
        elif self._pico_has_error:
            _apply_led_color(self._led_dc_state, "red")
        elif self._ramp or self._settle:
            _apply_led_color(self._led_dc_state, "amber")
        elif self._closed_loop_ok:
            _apply_led_color(self._led_dc_state, "green")
        elif (
            self._cl_before_tm
            and not self._closed_loop_ok
            and not self._ramp
            and not self._settle
        ):
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
            self._serial = serial.Serial(port, baud, timeout=0)
        except Exception as e:
            self._set_status(f"Open failed: {e}")
            QMessageBox.critical(self._win, "Calibrator", f"Could not open {port}:\n{e}")
            self._serial = None
            return
        self._pico_has_error = False
        self._configured_ok = False
        self._closed_loop_ok = False
        self._meas_ok = None
        self._ramp = False
        self._settle = False
        self._cl_before_tm = False
        self._pico_version = None
        self._pico_alive_stale = False
        self._last_alive_reply_ts = None
        self._connect_mono_ts = time.monotonic()
        self._save_serial_ini()
        self._rx_buf.clear()
        # Do not reset_input_buffer here: opening COM often resets the Pico; clearing RX would
        # discard boot TXT:: lines and the reply to gui_status. Let the first poll() drain data.
        self._serial_timer.start()
        self._heartbeat_timer.start()
        self._reset_measured_lcds_no_data()
        self._set_connected_ui(True)
        self._set_status(f"Opened {port} @ {baud} baud.")
        # Brief pause so USB CDC / soft-reset can finish before we poke the device.
        time.sleep(0.2)
        try:
            # version: OK VERSION for status bar; hw_report: full I2C/INA/H-bridge TXT:: (boot spam is often missed)
            self._serial.write(b"version\r\nhw_report\r\n")
            self._serial.flush()
        except Exception:
            pass

    def _send_pico_link_heartbeat(self) -> None:
        """Pico: alive refreshes slave LCD link and returns OK ALIVE for host liveness."""
        if self._serial is None:
            return
        try:
            self._serial.write(b"alive\r\n")
            self._serial.flush()
        except Exception:
            pass

    def _disconnect(self) -> None:
        self._connect_mono_ts = None
        self._last_alive_reply_ts = None
        self._pico_alive_stale = False
        self._heartbeat_timer.stop()
        self._serial_timer.stop()
        self._rx_buf.clear()
        if self._serial is not None:
            try:
                # Safe state + deploy-ready (Pico host_disconnect; legacy abort also accepted).
                self._serial.write(b"host_disconnect\r\n")
                self._serial.flush()
                time.sleep(0.08)
            except Exception:
                pass
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._pico_has_error = False
        self._configured_ok = False
        self._closed_loop_ok = False
        self._meas_ok = None
        self._ramp = False
        self._settle = False
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
    win.setWindowTitle("Calibrator")

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
