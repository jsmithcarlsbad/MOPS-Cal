#!/usr/bin/env python3
"""
CalibratorUI — PySide6 host for the CoilDriver Pico (serial).

Loads **CalibratorUI_DROK.ui** only. Settings in CalibratorUI.ini (UTF-8).

  [serial]: Pico `pico_port` + `baud` (alias `port` is written with the same value on save); MT-102
  `rs422_port`, `rs232_port`, `baud_rate`.
  **Calibration** menu (Designer: ``menuSite_Calibration`` or ``menuCalibration``): runtime title **Calibration**; host adds
  ``Generate cross-coupling matrix…`` (programmatic ``QAction``). Per-axis display scaling uses
  ``doubleSpinBox_[XYZ]_Gauss_CalFactor`` (Gauss CalFactor), not menu dialogs.
  ``objectName`` may be on the menubar ``QAction`` or the ``QMenu`` — both are resolved.
  Connect all (`pushButton_ConnectAll`): opens Pico serial first, then MT-102 from ini (dual COM + threaded reader),
  then Wit HWT901 on ``[serial] wit901_port`` (default COM10) via ``wit901_mag_stream`` protocol in a **daemon thread**;
  **Axis convention (mag + UI):** Honeywell mag axis **errata** is addressed on the MT-102 **PCB rework** (trace swap)
  so **reworked** units report X/Y/Z in the same ordering sense as Wit901 (and a consistent world frame). The host does
  **not** remap MT-102. Set ``[serial] mt102_swapped_xy`` to ``true``/``T``/``1`` when the connected MT-102 is **legacy**
  (mag X/Y still swapped on the stream); the host then swaps Wit901 **Gauss** X/Y **after** conversion so ``W901_Gauss_*``
  and Wit LCDs match that stream for plots. Use ``false``/``F``/``0`` for **reworked** MT-102 (correct axes, matches Wit901).
  When the key is missing, ``load_ini`` seeds ``mt102_swapped_xy = F``. The GUI snapshots 901 Gauss on the **same timer pass** as
  MT102 for ``MagTest.xlsx`` rows (DEBUG=5, openpyxl).
  Disconnect closes Wit901, then MT-102, then Pico (host_disconnect). 3D view embeds after `show()` (PyVista/Qt).
  **External Drive** (optional ``checkBox_ExternalDrive``): bench mode — no Pico. Checking the box disconnects the Pico
  if connected, opens MT-102 + Wit901 only, starts the same poll timer for real-time LCDs, disables Pico/coil
  controls, and appends MT-102 + Wit901 samples to ``ExternalDrive.xlsx`` (coil V columns blank; ``bench_V_*`` /
  ``bench_I_*`` columns for you to fill from the external supply). Unchecking disconnects sensors and restores normal UI.
  Optional ``radioButton_F_CalApplied`` (Designer): LED-style — **gray** only when MT-102 is not connected;
  **bright red** when connected but F-cal not loaded yet; **lime** when flash F-cal is present (``get_cal_data()``).
  On first F-cal parse this session, the host writes ``F_BLOCK_CAPTURE.md`` (parsed offsets, 3×3 soft-iron matrix, raw 384-char payload).
  Optional MT-102 field Gauss LCDs (Designer): ``lcdNumber_Mt102_X_Gauss`` and/or ``lcdNumber_MT102_{X,Y,Z}_Gauss``
  (capital ``G``) or ``lcdNumber_MT102_*_gauss`` — host tries every spelling so one typo axis does not stay at 0.
  Field Gauss (MT102 + Wit901) minimum size and font track **sensed attitude** LCDs
  (``lcdNumber_Mt102_X`` / ``lcdNumber_MT102_Y`` / ``lcdNumber_MT102_Z``): same digit height class;
  MT102 field Gauss uses 7 digit slots (like attitude); Wit901 uses 8 for a signed 4-decimal readout.
  Wit901 field Gauss: use **three** ``QLCDNumber`` widgets named exactly ``lcdNumber_Wit901_X_Gauss``,
  ``lcdNumber_Wit901_Y_Gauss``, ``lcdNumber_Wit901_Z_Gauss`` (host binds these first, then optional regex/label variants).
  Updated each ``_mag_poll`` tick.
  **Gauss (apples-to-apples):** Wit901 X/Y/Z use ``wit901_mag_stream.lsbs_to_gauss`` (Wit int16 → ±16 µT full scale,
  then **G = µT / 100**). MT102 X/Y/Z Gauss use factory F-cal corrected counts × ``[mt102_display] mag_raw_to_gauss``.
  Both paths are **Gauss** for LCDs and ``MagTest.xlsx``; magnitude agreement still depends
  on sensor position and soft iron. ``mt102_swapped_xy`` drives Wit901 Gauss X/Y remap vs legacy MT-102 (see above).

Serial line protocol (newline-terminated):
  TXT:: <text> — shown in textEdit_CalibratorTestOutput (boot, I2C scan, command replies).
  TM:: key=value ... — telemetry (alarm, cfg, closed_loop, meas_ok, DROK measured_ma / measured_vdc, etc.).
    (Host: TM lines that lost the leading prefix may be repaired if they start with '=float set_Y_v=' — restores set_X_v.)
    **Coil current (mA):** the **DROK** PSU measures coil current; the **Pico** reads it (e.g. Modbus) and forwards it in TM
    as ``X_ma`` / ``Y_ma`` / ``Z_ma``, ``measured_ma`` (and related diag keys). This host shows those values on
    **lcdNumber_[XYZ]_Coil_Current**. Bus voltage uses **lcdNumber_[XYZ]_Coil_Volts** from TM ``coil_V_*``, ``measured_vdc``, etc.
    Helmholtz modeled Gauss (axis Gauss LCDs, null-indicator model, TM CSV Gauss columns) uses **only** that TM coil mA as the
    applied current — the host does **not** infer current from V/R. Optional per-axis TM current scale factors in ini may be added later.
    Unprefixed TM-shaped rows use the same parser and are not copied
    to the text log.
  On connect: by default the host does not reset the Pico — it clears DTR/RTS after opening the COM port (Windows often toggles them and resets RP2040), then waits briefly for boot / CDC.
    If soft reset on connect is off, boot TXT:: was usually already sent before the port opened; the host then sends hw_report so the text log fills with the Pico hardware summary (same as firmware boot report).
    Firmware prints TXT:: OK VERSION … and a hardware report at boot, then streams TM:: every control loop (~LOOP_Hz) with X/Y/Z always present; no host keepalive.
    Optional Settings → "Soft reset on connect" (CalibratorUI.ini [serial] soft_reset_on_connect=1): Ctrl+C then Ctrl+D (MicroPython soft reset),
    then a short boot wait — use only when stuck in >>> REPL.
  Link “fresh” on any TXT:: or TM:: line. Stale: no traffic for ~8 s before the first line after connect, or >3 s after traffic stops (status line + STALE dbg at DEBUG==1 once per episode).
  On Disconnect / app quit: host sends host_disconnect (coils off, deploy-ready).
  Status bar Reset sends `safe_reset` when supported by the connected firmware. SAFE (`safe`) is a temporary
  shutdown of drive output for the connected axis/unit (per firmware); the serial link may stay open. To restore the
  same post-connect enable_x/y/z handshake the operator disconnects and reconnects serial (or follows firmware
  paths such as host_operate when physical Operate allows). Soft reset on connect (Ctrl+C Ctrl+D) restarts firmware when enabled in ini.
  Settings (menu, saved in CalibratorUI.ini [settings]): PWM 3/5 kHz (host display; firmware may fix Hz independently).
  Optional frame_NullIndicator + label_NullIndicatorText: host-defined “null-like” banner when
  |mA| is above a floor on all axes and the three Gauss estimates are within 1% spread (not B⃗=0).
  **DROK UI widgets** follow ``Software/HostApp/calibrator_DROK_UI_RequiredChanges.txt`` (authoritative list). The host
  does **not** wire legacy Test-V / voltage-override / Test-NULL bench widgets.
  **Coil enable (firmware):** while Pico serial is open, the host sends **enable_x/y/z 1** on connect; on disconnect it
  sends **enable_* 0** then **host_disconnect**. There is no separate UI axis enable — serial connection implies enabled
  until **SAFE** or firmware clears output; reconnect serial to re-send enables after a SAFE-style disable.
  **CalibratorUI_DROK.ui** uses **lcdNumber_[XYZ]_Coil_Current** (DROK-measured mA via Pico TM) and **lcdNumber_[XYZ]_Coil_Volts** from TM.

  Debug (terminal stdout): CalibratorUI.ini [debug] DEBUG = integer 0–9 (default 0).
    ``_dbg(N, ...)`` prints **only** when ``DEBUG == N`` and ``N > 0`` (exact level; no cumulative lower levels).
    One stderr line always shows ini path and effective DEBUG (even when DEBUG=0). Feature gates (TM CSV file,
    etc.) still use DEBUG thresholds documented below.
    0 = no DBG stdout. 1 = connect/disconnect, actions, serial cap trim, Pico version, widget warnings.
    2 = (unused; reserved.) 3 = MT102 connect / F-cal / skip-fail lines only.
    4 = TM CSV + TM/serial chunk trace (``serial read``, ``RX (unprefixed)``, ``TM_CSV``, ``TXT``, TM-diag).
    5 = MT102: ``MagTest.xlsx`` (timestamp, coil V, RAW; Gauss columns only after factory
    F-cal loads; plus ``W901_Gauss_*`` (after ``mt102_swapped_xy``) and ``W901_Raw_Gauss_*`` (UART frame, no swap)
    from Wit901 on the same poll). No DBG5 MT102 stdout stream. Requires ``openpyxl``.
    6 = (unused; reserved.)

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
import threading
import time
from collections.abc import Callable
from pathlib import Path

import serial
import serial.tools.list_ports
from PySide6.QtCore import QFile, QIODevice, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QPixmap, QTextCursor
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
    QGridLayout,
    QLabel,
    QLCDNumber,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QMainWindow,
    QMenu,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from mt102_interface import MT102Interface
except ImportError:
    MT102Interface = None  # type: ignore[misc, assignment]

try:
    import wit901_mag_stream as _w9_pkg
except ImportError:
    _w9_pkg = None  # type: ignore[misc, assignment]

try:
    from viewer3d import Viewer3D
except ImportError:
    Viewer3D = None  # type: ignore[misc, assignment]

try:
    from openpyxl import Workbook as _OpenpyxlWorkbook
except ImportError:
    _OpenpyxlWorkbook = None  # type: ignore[misc, assignment]

# --- Paths ---
_HERE = Path(__file__).resolve().parent
_UI_PATH = _HERE / "CalibratorUI_DROK.ui"
_INI_PATH = _HERE / "CalibratorUI.ini"
# DEBUG≥4: append TM snapshot rows here (CSV for Excel/plot tools; not .xls binary).
_TM_CSV_DEBUG_MIN = 4
_MT102_TRACE_DEBUG_MIN = 5
_TM_CSV_PATH = _HERE / "test_1.csv"
_MAG_TEST_XLSX_PATH = _HERE / "MagTest.xlsx"
_MAG_TEST_XLSX_SAVE_EVERY_N = 25
# External Drive mode (MT-102 + Wit901 only, no Pico): log sensor rows here for bench supply experiments.
_EXTERNAL_DRIVE_XLSX_PATH = _HERE / "ExternalDrive.xlsx"
_EXTERNAL_DRIVE_SAVE_EVERY_N = 25
# First successful MT-102 F-cal on connect: raw payload + matrix written here (bench artifact).
_F_BLOCK_CAPTURE_PATH = _HERE / "F_BLOCK_CAPTURE.md"
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
CALIBRATOR_UI_VERSION_MINOR = 50
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

# TM ``set_*_v`` vs ``coil_V_*`` on Coil_Volts LCD when setpoint is “low”: match band (V) → green / amber / red.
_TM_SETPOINT_MATCH_TOL_V = 0.25
# Helmholtz pair (ideal spacing = R): axial |B| at midpoint, B = 8/(5^(3/2)) * μ0 * N * I / R [T].
_MU0_SI = 4.0 * math.pi * 1e-7
_HELMHOLTZ_PAIR_AXIS_CENTER_FACTOR = 8.0 / (5.0 ** 1.5)

# Null-indicator: |mA| floor per axis; Gauss uniformity = (max−min)/mean ≤ this fraction.
_NULL_INDICATOR_I_MIN_ABS_MA = 2.0
_NULL_INDICATOR_B_UNIFORM_FRAC = 0.01

# MT-102 (mag) — UI + data monitor (see CalibratorUI.ini [serial] mt102_* and [mt102_limits] / [mt102_display])
# Gauss = (MagnetometerParser F-corrected Int16 count) × this factor. Old 0.01 matched an
# erroneous extra scale in host code; tune against a traceable Gaussmeter (see mt102_interface).
MAG_RAW_TO_GAUSS = 1e-5
MT102_RAW_GREEN = 2500
MT102_RAW_AMBER = 4000
MT102_GAUSS_GREEN = 0.6
MT102_GAUSS_AMBER = 1.0
MT102_DATA_MONITOR_MAX_LINES = 500
MT102_LCD_BG = "black"
MT102_AMBER = "#FFBF00"
_DEFAULT_MT102_BAUD = 9600
_DEFAULT_WIT901_PORT = "COM10"
_DEFAULT_WIT901_BAUD = 9600


class _Mt102ErrBridge(QObject):
    """Thread-safe: worker calls err.emit(msg); UI slot runs on the Qt GUI thread."""

    err = Signal(str)


class Wit901MagReader:
    """Threaded Wit UART reader (0x54 mag frames); UI correlates via get_latest_gauss() on the Qt thread."""

    def __init__(self, on_error: Callable[[str], None]) -> None:
        self._on_error = on_error
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ser: serial.Serial | None = None
        self._lock = threading.Lock()
        self._latest: tuple[float, float, float] | None = None

    def get_latest_gauss(self) -> tuple[float, float, float] | None:
        with self._lock:
            if self._latest is None:
                return None
            return self._latest

    def connect(self, port: str, baud: int, *, read_timeout: float = 0.25) -> bool:
        if _w9_pkg is None:
            self._on_error("wit901_mag_stream import failed")
            return False
        port = (port or "").strip()
        if not port:
            return False
        self.disconnect()
        self._stop.clear()
        try:
            self._ser = serial.Serial(
                port=port,
                baudrate=int(baud),
                timeout=read_timeout,
                write_timeout=2.0,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except Exception as e:
            self._ser = None
            self._on_error("open %s: %s" % (port, e))
            return False
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        return True

    def disconnect(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=3.5)
        self._thread = None
        ser = self._ser
        self._ser = None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        with self._lock:
            self._latest = None

    def _apply_frames(self, buf: bytearray) -> None:
        if _w9_pkg is None:
            return
        for frame in _w9_pkg.pop_wit_packets(buf):
            if frame[1] != _w9_pkg.FRAME_MAG:
                continue
            hx, hy, hz = _w9_pkg.parse_mag_frame(frame)
            x = _w9_pkg.lsbs_to_gauss(hx)
            y = _w9_pkg.lsbs_to_gauss(hy)
            z = _w9_pkg.lsbs_to_gauss(hz)
            if self._stop.is_set():
                return
            with self._lock:
                self._latest = (x, y, z)

    def _worker(self) -> None:
        ser = self._ser
        if ser is None or _w9_pkg is None:
            return
        rx_grace_ms = 750.0
        reg_hx = int(getattr(_w9_pkg, "_REG_HX", 0x3A))
        buf = bytearray()
        try:
            try:
                _w9_pkg.wit_init_stream(ser, flush_rx=False)
            except Exception as e:
                self._on_error("init failed: %s" % (e,))
                return
            try:
                grace0 = _w9_pkg.capture_rx_window(ser, max(rx_grace_ms, 400.0))
            except Exception as e:
                self._on_error("rx: %s" % (e,))
                return
            if grace0:
                buf.extend(grace0)
                self._apply_frames(buf)
            poll_s = 1.0
            last_poll = time.monotonic() - poll_s
            while not self._stop.is_set():
                now = time.monotonic()
                pieces: list[bytes] = []
                polled = False
                if poll_s > 0 and (now - last_poll) >= poll_s:
                    if self._stop.is_set():
                        break
                    try:
                        _w9_pkg.wit_read_block(ser, reg_hx)
                    except Exception as e:
                        self._on_error("poll write: %s" % (e,))
                        break
                    last_poll = now
                    polled = True
                    try:
                        grace_p = _w9_pkg.capture_rx_window(ser, rx_grace_ms)
                    except Exception as e:
                        self._on_error("poll rx: %s" % (e,))
                        break
                    if grace_p:
                        pieces.append(grace_p)
                if not polled and not self._stop.is_set():
                    try:
                        chunk = _w9_pkg.read_serial_chunk(ser, max_block=512)
                    except Exception as e:
                        self._on_error("read: %s" % (e,))
                        break
                    if chunk:
                        pieces.append(chunk)
                if polled and not self._stop.is_set():
                    try:
                        extra = _w9_pkg.read_serial_chunk(ser, max_block=512)
                    except Exception as e:
                        self._on_error("read: %s" % (e,))
                        break
                    if extra:
                        pieces.append(extra)
                for raw in pieces:
                    buf.extend(raw)
                    self._apply_frames(buf)
                if not pieces:
                    time.sleep(0.02)
        finally:
            pass


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
    "lime": "#39ff14",
    "red_bright": "#ff1744",
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


# CalibratorUI_DROK.ui — display-only LED radios (not used as real radio groups).
# objectNames must match the .ui file (includes Designer typos where applicable).
_DROK_DISPLAY_ONLY_LED_OBJECT_NAMES: tuple[str, ...] = (
    "radioButton_ConnnectedGaussSource",
    "radioButton_X_Coil_LED_Connected",
    "radioButton_X_LED_Coil_OCP",
    "radioButton_X_Coil_LED_OVP",
    "radioButton_X_Coil_LED_Detected",
    "radioButton_X_Coil_LED_InvertedPolarity",
    "radioButton_Y_Coil_LED_Connected",
    "radioButton_Y_Coil_LED_OCP",
    "radioButton_Y_Coil_LED_OVP",
    "radioButton_Y_Coil_LED__Detected",
    "radioButton_Y_Coil_LED_InvertedPolarity",
    "radioButton_Z_Coil_LED_Connected",
    "radioButton_Z_Coil_LED_OCP",
    "radioButton_Z_Coil_LED_OVP",
    "radioButton_Z_Coil_LED_Detected",
    "radioButton_Z_Coil_LED_InvertedPolarity",
    "radioButton_X_LED_Coil_CC",
    "radioButton_Y_LED_Coil_CC",
    "radioButton_Z_LED_Coil_CC",
)


def _setup_display_only_leds_from_names(win: QMainWindow, names: tuple[str, ...]) -> None:
    """Apply ``_setup_display_only_led`` + gray default to each present ``QRadioButton`` (DROK UI carry-forward)."""
    for name in names:
        rb = win.findChild(QRadioButton, name)
        if rb is None:
            continue
        _setup_display_only_led(rb)
        _apply_led_color(rb, "gray")


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


def _serial_mt102_swapped_xy(cp: configparser.ConfigParser) -> bool:
    """True when MT-102 mag X/Y on the stream are still the legacy (pre-rework) swap — Wit901 Gauss X/Y is then swapped for alignment.

    Reads ``[serial] mt102_swapped_xy`` (``true``/``false``, ``T``/``F``, ``1``/``0``, ``yes``/``no``, etc.).
    If the option is missing, returns ``False`` (reworked / no swap).
    """
    if not cp.has_section("serial") or not cp.has_option("serial", "mt102_swapped_xy"):
        return False
    raw = cp.get("serial", "mt102_swapped_xy").strip()
    u = raw.upper()
    if u in ("1", "TRUE", "YES", "ON", "Y", "T"):
        return True
    if u in ("0", "FALSE", "NO", "OFF", "N", "F"):
        return False
    try:
        return cp.getboolean("serial", "mt102_swapped_xy")
    except ValueError:
        return False


def load_ini() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    if _INI_PATH.is_file():
        cp.read(_INI_PATH, encoding="utf-8")
    if not cp.has_section("serial"):
        cp.add_section("serial")
    if not cp.has_option("serial", "port"):
        cp.set("serial", "port", "")
    if not cp.has_option("serial", "pico_port"):
        # Match rs422_port / rs232_port naming; legacy key `port` is kept in sync on save.
        cp.set("serial", "pico_port", cp.get("serial", "port", fallback="").strip())
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
    # MT-102 (dual COM): RS422 = RX, RS232 = TX/commands — same names as legacy calibrator.ini
    if not cp.has_option("serial", "rs422_port"):
        cp.set("serial", "rs422_port", "")
    if not cp.has_option("serial", "rs232_port"):
        cp.set("serial", "rs232_port", "")
    if not cp.has_option("serial", "baud_rate"):
        cp.set("serial", "baud_rate", str(_DEFAULT_MT102_BAUD))
    if not cp.has_option("serial", "wit901_port"):
        cp.set("serial", "wit901_port", _DEFAULT_WIT901_PORT)
    if not cp.has_option("serial", "wit901_baud"):
        cp.set("serial", "wit901_baud", str(_DEFAULT_WIT901_BAUD))
    if not cp.has_option("serial", "mt102_swapped_xy"):
        cp.set("serial", "mt102_swapped_xy", "F")
    if not cp.has_section("mt102_limits"):
        cp.add_section("mt102_limits")
    for _opt, _val in (
        ("raw_green", str(MT102_RAW_GREEN)),
        ("raw_amber", str(MT102_RAW_AMBER)),
        ("gauss_green", str(MT102_GAUSS_GREEN)),
        ("gauss_amber", str(MT102_GAUSS_AMBER)),
    ):
        if not cp.has_option("mt102_limits", _opt):
            cp.set("mt102_limits", _opt, _val)
    if not cp.has_section("mt102_display"):
        cp.add_section("mt102_display")
    if not cp.has_option("mt102_display", "mag_raw_to_gauss"):
        cp.set("mt102_display", "mag_raw_to_gauss", str(MAG_RAW_TO_GAUSS))
    if not cp.has_option("mt102_display", "mag_declination_deg"):
        cp.set("mt102_display", "mag_declination_deg", "0")
    # Legacy mistaken default: MagCal matrix uses 0.01 *inside* soft-iron terms only; Gauss is still
    # corrected Int16 counts × a small G/count (~1e-5). 0.01 here produced ~tens–150 "G" at rest.
    try:
        _mrg = float(cp.get("mt102_display", "mag_raw_to_gauss", fallback=str(MAG_RAW_TO_GAUSS)).strip())
    except ValueError:
        cp.set("mt102_display", "mag_raw_to_gauss", format(MAG_RAW_TO_GAUSS, ".15g"))
    else:
        if math.isclose(_mrg, 0.01, rel_tol=0.0, abs_tol=1e-9):
            cp.set("mt102_display", "mag_raw_to_gauss", format(MAG_RAW_TO_GAUSS, ".15g"))
            try:
                save_ini(cp)
            except OSError:
                pass
    return cp


def save_ini(cp: configparser.ConfigParser) -> None:
    """Persist ``cp`` to CalibratorUI.ini.

    Before writing, merge any (section, option) that exists on disk but is missing from ``cp``.
    That way keys or whole sections added or edited while the app was running are not erased when
    the host saves (Settings, disconnect serial, Calibration menu actions, etc.).
    In-memory values always win for keys the app already holds.
    """
    if _INI_PATH.is_file():
        disk_cp = configparser.ConfigParser()
        try:
            disk_cp.read(_INI_PATH, encoding="utf-8")
        except configparser.Error:
            pass
        else:
            for sec in disk_cp.sections():
                if not cp.has_section(sec):
                    cp.add_section(sec)
                for key, val in disk_cp.items(sec):
                    if not cp.has_option(sec, key):
                        cp.set(sec, key, val)
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


def _coil_volts_lcd_color(meas_v: float, set_v: float | None) -> str:
    """INA coil bus V on LCD: low commanded V → color vs TM set_*_v; else 12 V rail banding."""
    if set_v is not None and math.isfinite(set_v) and abs(set_v) < _COIL_V_LOW_RED:
        return _meas_vs_setpoint_volt_color(meas_v, set_v, tol=_TM_SETPOINT_MATCH_TOL_V)
    return _volts_lcd_digit_color(meas_v)


def _meas_vs_setpoint_volt_color(
    meas: float, target: float, tol: float = _TM_SETPOINT_MATCH_TOL_V
) -> str:
    """Green within ±tol of TM setpoint; amber when below band; red when above."""
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
        """Print to stdout only when effective DEBUG equals ``level`` (and level > 0)."""
        if self._debug_level <= 0 or level <= 0 or self._debug_level != level:
            return
        print("[CalibratorUI DBG%d]" % level, *args, flush=True)

    def __init__(self, win: QMainWindow) -> None:
        self._win = win
        self._ini = load_ini()
        self._debug_level = self._read_debug_level()
        try:
            sys.stderr.write(
                "[CalibratorUI] UI %s ini=%s effective_DEBUG=%d (stdout DBG: exact N only; TM CSV>=%d; MagTest.xlsx DEBUG==%d)\n"
                % (
                    CALIBRATOR_UI_VERSION,
                    _INI_PATH,
                    self._debug_level,
                    _TM_CSV_DEBUG_MIN,
                    _MT102_TRACE_DEBUG_MIN,
                )
            )
            if self._debug_level == _TM_CSV_DEBUG_MIN:
                sys.stderr.write(
                    "[CalibratorUI] DEBUG=%d: TM CSV -> %s (file created on first TM:: after connect)\n"
                    % (_TM_CSV_DEBUG_MIN, _TM_CSV_PATH.resolve())
                )
            elif self._debug_level < _TM_CSV_DEBUG_MIN:
                sys.stderr.write(
                    "[CalibratorUI] TM CSV (test_1.csv) needs DEBUG>=%d in %s\n"
                    % (_TM_CSV_DEBUG_MIN, _INI_PATH.resolve())
                )
            if self._debug_level == _MT102_TRACE_DEBUG_MIN:
                sys.stderr.write(
                    "[CalibratorUI] DEBUG=%d: MT102 wide data monitor; MagTest rows -> %s (needs openpyxl)\n"
                    % (_MT102_TRACE_DEBUG_MIN, _MAG_TEST_XLSX_PATH.resolve())
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
        # DEBUG==_TM_CSV_DEBUG_MIN: one-shot TM line sample per link (see _apply_tm_line).
        self._tm_dbg_first_tm_after_connect: bool = False
        self._tm_dbg_setx_absent_x_present_pending: bool = False
        # Last TM:: token map (Pico); coil_V for DEBUG==_MT102_TRACE_DEBUG_MIN MagTest.xlsx rows + UI.
        self._last_tm_kv: dict[str, str] | None = None
        # Placeholders until host↔Pico protocol (set mA ack, closed-loop telem).
        self._configured_ok: bool = False
        self._closed_loop_ok: bool = False
        self._pico_version: str | None = None
        self._settings_pwm_hz: int = 5000
        self._settings_max_ma: float = 100.0
        # TM-derived (DC State LED, Initialized); _cl_before_tm saved before each TM line updates closed_loop_ok.
        self._meas_ok: bool | None = None
        self._cl_before_tm = False
        self._mt102: object | None = None
        self._viewer3d: QWidget | None = None
        self._mt102_err_bridge = _Mt102ErrBridge(win)
        self._mt102_err_bridge.err.connect(self._on_mt102_thread_error)
        self._wit901_err_bridge = _Mt102ErrBridge(win)
        self._wit901_err_bridge.err.connect(self._on_wit901_thread_error)
        self._wit901 = Wit901MagReader(lambda m: self._wit901_err_bridge.err.emit(str(m)))
        self._mt102_raw_green = MT102_RAW_GREEN
        self._mt102_raw_amber = MT102_RAW_AMBER
        self._mt102_gauss_green = MT102_GAUSS_GREEN
        self._mt102_gauss_amber = MT102_GAUSS_AMBER
        self._mag_raw_to_gauss = MAG_RAW_TO_GAUSS
        self._mag_declination_deg = 0.0
        self._reload_mt102_ini_preferences()
        if self._mag_raw_to_gauss >= 0.009:
            try:
                sys.stderr.write(
                    "[CalibratorUI] WARNING: [mt102_display] mag_raw_to_gauss=%s is very large; "
                    "displayed G = corrected_counts × this (legacy 0.01 → ~40–150 G at rest). "
                    "Try ~1e-5 or adjust Gauss CalFactor / mag_raw_to_gauss in ini. ini: %s\n"
                    % (self._mag_raw_to_gauss, _INI_PATH.resolve())
                )
            except Exception:
                pass
        self._dbg_mt102_f_cal_logged = False
        self._mt102_f_block_md_written = False
        self._mt102_cal_que_mono: float = 0.0
        self._mt102_fcal_polls_without_cal = 0
        self._mt102_fcal_missing_logged = False
        # Populated on first MT-102 Gauss UI refresh: (QLCDNumber, "X"|"Y"|"Z") via objectName regex.
        self._mt102_field_gauss_lcds: list[tuple[QLCDNumber, str]] | None = None
        # User-added Wit901 Gauss readouts: QLCDNumber and/or QLabel per axis.
        self._wit901_field_gauss_lcds: list[tuple[QWidget, str]] | None = None
        # True after Wit901MagReader.connect succeeds (used for Gauss source combo).
        self._wit901_uart_open: bool = False
        # CalibratorUI_DROK.ui: Axis Gauss readouts = (MT102 or Wit901) × cal factor.
        self._drok_axis_gauss_lcds: list[tuple[str, QLCDNumber]] = []
        self._gauss_cal_spins: dict[str, QDoubleSpinBox] = {}
        self._gauss_combo_seeded: bool = False
        self._last_mt102_field_gauss: tuple[float, float, float, bool] = (
            float("nan"),
            float("nan"),
            float("nan"),
            False,
        )
        self._mag_test_wb: object | None = None
        self._mag_test_ws: object | None = None
        self._mag_test_xlsx_row_count = 0
        self._mag_test_xlsx_missing_logged = False
        self._external_drive_wb: object | None = None
        self._external_drive_ws: object | None = None
        self._external_drive_row_count = 0
        self._external_drive_active = False

        self._combo_port = win.findChild(QComboBox, "comboBox_CalibratorPort")
        self._combo_baud = win.findChild(QComboBox, "comboBox_CalbratorBaud")
        self._btn_connect = win.findChild(QPushButton, "pushButton_ConnectAll")
        self._led_f_cal_applied: QRadioButton | None = win.findChild(
            QRadioButton, "radioButton_F_CalApplied"
        )
        self._text_out = win.findChild(QTextEdit, "textEdit_CalibratorTestOutput")
        self._btn_clear_text = win.findChild(QPushButton, "pushButton_ClearCalibratorText")

        self._axis_rows: list[
            tuple[str, QSpinBox | None, QPushButton | None, QLCDNumber, QCheckBox | None]
        ] = []
        for ax in ("X", "Y", "Z"):
            lcd = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Coil_Current")
            if not lcd:
                raise RuntimeError(
                    "CalibratorUI_DROK.ui: missing lcdNumber_%s_Coil_Current" % ax
                )
            sp = win.findChild(QSpinBox, f"spinBox_{ax}mA_target")
            pb = win.findChild(QPushButton, f"pushButton_{ax}_Set_mA")
            chk = win.findChild(QCheckBox, f"checkBox_{ax}_Enabled")
            _init_measured_ma_lcd(lcd)
            if sp is not None:
                sp.setRange(0, 5000)
                sp.setValue(0)
            if chk is not None:
                chk.setChecked(False)
            self._axis_rows.append((ax, sp, pb, lcd, chk))

        self._axis_volts_lcd: list[tuple[str, QLCDNumber]] = []
        for ax in ("X", "Y", "Z"):
            vlcd = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Coil_Volts")
            if not vlcd:
                raise RuntimeError(
                    "CalibratorUI_DROK.ui: missing lcdNumber_%s_Coil_Volts" % ax
                )
            _init_volts_lcd(vlcd)
            self._axis_volts_lcd.append((ax, vlcd))

        self._axis_gauss_lcd: list[tuple[str, QLCDNumber]] = []

        self._combo_gauss_source = win.findChild(QComboBox, "comboBox_SelectedGaussSource")
        if self._combo_gauss_source is not None:
            self._combo_gauss_source.setEnabled(False)
        for ax in ("X", "Y", "Z"):
            gsp = win.findChild(QDoubleSpinBox, f"doubleSpinBox_{ax}_Gauss_CalFactor")
            if gsp is not None:
                self._gauss_cal_spins[ax] = gsp
        for ax in ("X", "Y", "Z"):
            ag = win.findChild(QLCDNumber, f"lcdNumber_{ax}_Axis_Gauss")
            if ag is not None:
                _init_gauss_lcd(ag)
                self._drok_axis_gauss_lcds.append((ax, ag))
        if self._combo_gauss_source is not None and self._drok_axis_gauss_lcds:
            self._combo_gauss_source.currentIndexChanged.connect(
                lambda _i: self._refresh_drok_axis_gauss_lcds(
                    self._last_mt102_field_gauss[3],
                    self._last_mt102_field_gauss[0],
                    self._last_mt102_field_gauss[1],
                    self._last_mt102_field_gauss[2],
                )
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

        if not self._combo_port or not self._combo_baud or not self._btn_connect:
            raise RuntimeError(
                "UI missing widgets: comboBox_CalibratorPort, comboBox_CalbratorBaud, pushButton_ConnectAll"
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
        self._lcd_gauss_cache: dict[str, tuple[str, str]] = {}
        # (coil radius_m, N turns) per axis from [helmholtz]; None → show --- on Gauss LCD.
        self._helm_geom: dict[str, tuple[float, float] | None] = {
            "X": None,
            "Y": None,
            "Z": None,
        }
        self._connect_rx_pump_slices: int = 0
        self._serial_timer = QTimer(self._win)
        self._serial_timer.setInterval(50)
        self._serial_timer.timeout.connect(self._poll_serial)

        if self._led_f_cal_applied is not None:
            _setup_display_only_led(self._led_f_cal_applied)
            _apply_led_color(self._led_f_cal_applied, "gray")

        _setup_display_only_leds_from_names(win, _DROK_DISPLAY_ONLY_LED_OBJECT_NAMES)

        # DROK CC status (TM:: drok_cc_led + drok_axis); widgets in CalibratorUI_DROK.ui radioButton_[XYZ]_LED_Coil_CC.
        self._led_cc_coil: dict[str, QRadioButton] = {}
        for ax in ("X", "Y", "Z"):
            rb_cc = win.findChild(QRadioButton, "radioButton_%s_LED_Coil_CC" % ax)
            if rb_cc is not None:
                _apply_led_color(rb_cc, "red")
                self._led_cc_coil[ax] = rb_cc

        self._status_main = QLabel("")
        self._status_conn = QLabel("Connection: Disconnected")
        self._btn_reset = QPushButton("Reset")
        self._btn_reset.setToolTip(
            "Send safe_reset when the connected firmware supports it (coil / output shutdown)."
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
        self._setup_calibration_menu()

        self._btn_connect.clicked.connect(self._on_connect_clicked)
        self._chk_external_drive: QCheckBox | None = win.findChild(
            QCheckBox, "checkBox_ExternalDrive"
        )
        if self._chk_external_drive is not None:
            self._chk_external_drive.setToolTip(
                "External Drive (bench): disconnects Pico and connects MT-102 + Wit901 only. "
                "Power coils from an external supply; GUI shows MT-102 and Wit901 in real time and logs to "
                "ExternalDrive.xlsx (bench V/I columns left blank for your notes). Uncheck to restore normal mode."
            )
            self._chk_external_drive.toggled.connect(self._on_external_drive_toggled)
        self._btn_safe.clicked.connect(self._on_safe_calibrator)
        self._btn_reset.clicked.connect(self._on_reset_calibrator)
        self._btn_clear_text.clicked.connect(self._on_clear_calibrator_text)
        _btn_mt102_clear = win.findChild(QPushButton, "pushButton_ClearDisplayedData")
        if _btn_mt102_clear is not None:
            _btn_mt102_clear.clicked.connect(self._on_clear_mt102_data)
        self._combo_port.currentIndexChanged.connect(self._on_serial_widget_changed)
        self._combo_baud.currentIndexChanged.connect(self._on_serial_widget_changed)

        self._set_connected_ui(False)
        self._set_status("Ready.")
        self._dbg(1, "startup; DEBUG level", self._debug_level, "ini", _INI_PATH)

    def _populate_baud_combo(self) -> None:
        self._combo_baud.clear()
        for b in _BAUD_CHOICES:
            self._combo_baud.addItem(b)

    def _apply_ini_to_widgets(self) -> None:
        port = (
            self._ini.get("serial", "pico_port", fallback="").strip()
            or self._ini.get("serial", "port", fallback="").strip()
        )
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
    def _coils_axis_enabled(self, axis: str) -> bool:
        """True when Pico serial is open — connection implies coil axes are enabled for host/firmware sync."""
        _ = axis
        return self._serial is not None

    def _reload_helmholtz_geometry(self) -> None:
        """Read [helmholtz] x_diameter_mm, x_turns, … for Helmholtz |B| model (current always from TM mA)."""
        sec = "helmholtz"
        for ax in ("X", "Y", "Z"):
            self._helm_geom[ax] = None
        if not self._ini.has_section(sec):
            return
        for ax in ("X", "Y", "Z"):
            al = ax.lower()
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
        if self._debug_level < _TM_CSV_DEBUG_MIN:
            self._close_tm_csv()
        self._apply_settings_from_ini()
        self._apply_ini_to_widgets()
        self._sync_soft_reset_menu_from_ini()
        self._reload_helmholtz_geometry()
        self._reload_mt102_ini_preferences()
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

    def _find_menu_by_object_name(self, object_name: str) -> QMenu | None:
        """
        Return a ``QMenu`` by Designer ``objectName``.

        Qt Designer often sets ``objectName`` on the **menubar QAction** (e.g. ``menuSite_Calibration``)
        that owns the dropdown, not on the ``QMenu`` itself — check both.
        """
        mb = self._win.menuBar()
        found = mb.findChild(QMenu, object_name, Qt.FindChildOption.FindChildrenRecursively)
        if found is not None:
            return found
        for a in mb.actions():
            sub = a.menu()
            if sub is None:
                continue
            if sub.objectName() == object_name or a.objectName() == object_name:
                return sub
        return None

    def _setup_calibration_menu(self) -> None:
        """Top menu **Calibration**: cross-coupling matrix generator (Gauss CalFactor is on the main form).

        Resolves ``menuCalibration`` (preferred) or legacy ``menuSite_Calibration`` from Designer.
        """
        menu = self._find_menu_by_object_name("menuCalibration")
        if menu is None:
            menu = self._find_menu_by_object_name("menuSite_Calibration")
        if menu is None:
            self._dbg(
                1,
                "UI: no menubar QMenu for objectName menuCalibration or menuSite_Calibration — "
                "Calibration entries not added.",
            )
            return
        mb = self._win.menuBar()
        for a in mb.actions():
            if a.menu() is menu:
                a.setText("Calibration")
                break
        menu.setTitle("Calibration")
        self._ensure_menu_action_on_menu(
            menu,
            "Generate cross-coupling matrix…",
            self._dialog_generate_cross_coupling_matrix,
        )

    @staticmethod
    def _ensure_menu_action_on_menu(menu: QMenu, label: str, slot) -> None:
        if CalibratorController._menu_has_action(menu, label):
            return
        act = QAction(label, menu)
        act.triggered.connect(slot)
        menu.addAction(act)

    def _read_mt102_gauss_triple_now(self) -> tuple[float, float, float] | None:
        """Return (Gx, Gy, Gz) from the connected MT-102, or ``None`` if unavailable."""
        if MT102Interface is None or not getattr(self, "_mt102", None) or self._mt102 is None:
            return None
        if not self._mt102.is_connected():
            return None
        try:
            cal = self._mt102.get_cal_data()
            mag = self._mt102.get_mag_data(timeout=0)
        except Exception:
            return None
        if cal is None or mag is None:
            return None
        try:
            gx, gy, gz = cal.raw_to_gauss(mag, self._mag_raw_to_gauss)
        except Exception:
            return None
        if not all(math.isfinite(v) for v in (gx, gy, gz)):
            return None
        return (float(gx), float(gy), float(gz))

    def _dialog_generate_cross_coupling_matrix(self) -> None:
        """
        Build the 3×3 coil cross-coupling matrix **M** (T/A): ``B_T = M @ I`` with ``I`` in amperes.

        For each isolated drive (X, then Y, then Z), set **I** (A) to that axis’s **Pico TM DROK-measured** coil
        current: **I = (Pico TM DROK-reported mA for that axis) / 1000**, i.e. the **Coil Current** LCD for that axis
        at the time of the B reading — and enter the measured ``B`` in Gauss;
        column *i* of ``M`` is ``(B_x, B_y, B_z)`` in tesla divided by ``I_i``.
        Saves ``[coil_cross_coupling]`` keys ``k_xx`` … ``k_zz`` in ``CalibratorUI.ini``.
        """
        dlg = QDialog(self._win)
        dlg.setWindowTitle("Generate cross-coupling matrix")
        dlg.setModal(True)
        outer = QVBoxLayout(dlg)
        info = QLabel(
            "Drive one axis at a time with all others at 0 A. For each row, set I (A) = that axis’s Pico TM "
            "DROK-reported coil current in mA ÷ 1000 (same as the Coil Current LCD at your reading). "
            "Enter the MT-102 field (Gauss) in the same axis frame. "
            "Column i of M (T/A) is "
            "(B_x, B_y, B_z) in tesla divided by I for that drive. Optional: fill B from the live MT-102."
        )
        info.setWordWrap(True)
        outer.addWidget(info)

        grid = QGridLayout()
        headers = ("Drive", "I (A)", "Bx (G)", "By (G)", "Bz (G)", "")
        for c, h in enumerate(headers):
            if h:
                grid.addWidget(QLabel(h), 0, c)
        labels = ("X only", "Y only", "Z only")
        i_spins: list[QDoubleSpinBox] = []
        bx_spins: list[QDoubleSpinBox] = []
        by_spins: list[QDoubleSpinBox] = []
        bz_spins: list[QDoubleSpinBox] = []
        for r, lab in enumerate(labels, start=1):
            grid.addWidget(QLabel(lab), r, 0)
            sp_i = QDoubleSpinBox()
            sp_i.setRange(-200.0, 200.0)
            sp_i.setDecimals(6)
            sp_i.setSingleStep(0.001)
            sp_i.setValue(0.0)
            grid.addWidget(sp_i, r, 1)
            i_spins.append(sp_i)
            row_b = []
            for _ in range(3):
                sp_b = QDoubleSpinBox()
                sp_b.setRange(-1.0e6, 1.0e6)
                sp_b.setDecimals(6)
                sp_b.setSingleStep(0.1)
                sp_b.setValue(0.0)
                row_b.append(sp_b)
            grid.addWidget(row_b[0], r, 2)
            grid.addWidget(row_b[1], r, 3)
            grid.addWidget(row_b[2], r, 4)
            bx_spins.append(row_b[0])
            by_spins.append(row_b[1])
            bz_spins.append(row_b[2])
            btn = QPushButton("Fill B from MT-102")
            row_idx = r - 1

            def _make_fill(idx: int) -> Callable[[], None]:
                def _go() -> None:
                    g = self._read_mt102_gauss_triple_now()
                    if g is None:
                        QMessageBox.warning(
                            self._win,
                            "Calibration",
                            "MT-102 is not connected or has no fresh Gauss reading.",
                        )
                        return
                    bx_spins[idx].setValue(g[0])
                    by_spins[idx].setValue(g[1])
                    bz_spins[idx].setValue(g[2])

                return _go

            btn.clicked.connect(_make_fill(row_idx))
            grid.addWidget(btn, r, 5)

        outer.addLayout(grid)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        outer.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        eps_i = 1e-12
        cols: list[tuple[float, float, float]] = []
        for idx in range(3):
            I = float(i_spins[idx].value())
            if not math.isfinite(I) or abs(I) < eps_i:
                QMessageBox.warning(
                    self._win,
                    "Calibration",
                    "Each drive row needs a non-zero, finite current (A).",
                )
                return
            bx = float(bx_spins[idx].value())
            by = float(by_spins[idx].value())
            bz = float(bz_spins[idx].value())
            if not all(math.isfinite(v) for v in (bx, by, bz)):
                QMessageBox.warning(
                    self._win,
                    "Calibration",
                    "All Gauss entries must be finite.",
                )
                return
            tx = bx * 1.0e-4
            ty = by * 1.0e-4
            tz = bz * 1.0e-4
            cols.append((tx / I, ty / I, tz / I))

        k_xx, k_yx, k_zx = cols[0]
        k_xy, k_yy, k_zy = cols[1]
        k_xz, k_yz, k_zz = cols[2]

        def _det3(
            a00: float,
            a01: float,
            a02: float,
            a10: float,
            a11: float,
            a12: float,
            a20: float,
            a21: float,
            a22: float,
        ) -> float:
            return (
                a00 * (a11 * a22 - a12 * a21)
                - a01 * (a10 * a22 - a12 * a20)
                + a02 * (a10 * a21 - a11 * a20)
            )

        det_m = _det3(k_xx, k_xy, k_xz, k_yx, k_yy, k_yz, k_zx, k_zy, k_zz)
        if not math.isfinite(det_m):
            QMessageBox.warning(self._win, "Calibration", "Matrix determinant is not finite.")
            return

        sec = "coil_cross_coupling"
        if not self._ini.has_section(sec):
            self._ini.add_section(sec)
        pairs = (
            ("k_xx", k_xx),
            ("k_xy", k_xy),
            ("k_xz", k_xz),
            ("k_yx", k_yx),
            ("k_yy", k_yy),
            ("k_yz", k_yz),
            ("k_zx", k_zx),
            ("k_zy", k_zy),
            ("k_zz", k_zz),
        )
        for key, val in pairs:
            self._ini.set(sec, key, format(val, ".15g"))
        save_ini(self._ini)
        self._set_status(
            "Calibration: saved [coil_cross_coupling] k_xx…k_zz (T/A). det(M) = %s"
            % format(det_m, ".6g")
        )
        QMessageBox.information(
            self._win,
            "Calibration",
            "Cross-coupling matrix M (T/A) saved to CalibratorUI.ini under [coil_cross_coupling].\n\n"
            "det(M) = %s\n\n"
            "Use I = M⁻¹ B with B in tesla when inverting." % format(det_m, ".6g"),
        )

    def _refresh_com_ports(self, select_saved: bool = False) -> None:
        saved = (
            self._ini.get("serial", "pico_port", fallback="").strip()
            or self._ini.get("serial", "port", fallback="").strip()
        )
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
        cur = self._current_port()
        self._ini.set("serial", "pico_port", cur)
        self._ini.set("serial", "port", cur)
        self._ini.set("serial", "baud", str(self._current_baud()))
        save_ini(self._ini)

    def _on_serial_widget_changed(self, _index: int) -> None:
        if self._serial is None:
            self._save_serial_ini()

    def _set_status(self, text: str) -> None:
        self._status_main.setText(text)

    def _on_clear_calibrator_text(self) -> None:
        self._text_out.clear()

    def _on_clear_mt102_data(self) -> None:
        te = self._win.findChild(QTextEdit, "textEdit_MT102_Data")
        if not te and hasattr(self._win, "centralWidget"):
            cw = self._win.centralWidget()
            if cw:
                te = cw.findChild(QTextEdit, "textEdit_MT102_Data")
        if te is not None:
            te.clear()

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
                r"ina_[XYZ]_ch|diag_Ch[123]_ma|diag_[XYZ]_duty|alarm|drok_cc_led|drok_axis)\s*=",
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
        if t.startswith("'"):
            t = t[1:].lstrip()
        if re.match(r"(?i)^TM::", t):
            return t
        m = re.match(r"^=(\d+(?:\.\d+)?|nan)\s+", t, re.I)
        if not m:
            return t
        rest = t[m.end() :].lstrip()
        if re.match(r"(?i)^set_[yz]_v\s*=", rest):
            return "set_X_v=" + m.group(1) + " " + rest
        return t

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
        """Logical-axis mA from Pico TM (DROK PSU measurement): X_ma/Y_ma/Z_ma, else measured_ma + drok_axis, else diag shunts."""
        m = self._tm_float(kv, f"{ax}_ma")
        if m is not None:
            return m
        m0 = self._tm_float(kv, "measured_ma")
        if m0 is not None:
            dax = (kv.get("drok_axis") or kv.get("DROK_AXIS") or "").strip().upper()[:1]
            if not dax:
                return m0
            if dax == ax.strip().upper()[:1]:
                return m0
        ch = self._tm_int(kv, f"ina_{ax}_ch")
        if ch is None or ch < 0 or ch > 2:
            return None
        return self._tm_float(kv, "diag_Ch%d_ma" % (ch + 1))

    def _tm_axis_current_a_for_gauss(self, kv: dict[str, str], ax: str) -> float | None:
        """Axis current (A) through the coil for the Helmholtz |B| model: always TM mA from DROK (Pico), never V/R on the host."""
        m_ma = self._tm_measured_ma(kv, ax)
        if m_ma is None:
            return None
        i_m = abs(float(m_ma)) / 1000.0
        return i_m if math.isfinite(i_m) else None

    def _coil_v_xyz_from_last_tm(self) -> tuple[float | None, float | None, float | None]:
        """Pico TM:: coil_V_* or set_*_v (V); None if no TM yet or key missing."""
        kv = self._last_tm_kv
        if not kv:
            return (None, None, None)
        trip: list[float | None] = []
        for ax in ("X", "Y", "Z"):
            v = self._tm_float(kv, "coil_V_%s" % ax)
            if v is None:
                v = self._tm_float(kv, "set_%s_v" % ax)
            if v is None:
                v = self._tm_float(kv, "set_%s_v" % ax.lower())
            trip.append(v)
        return (trip[0], trip[1], trip[2])

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
        if self._debug_level < _TM_CSV_DEBUG_MIN:
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
            self._dbg(_TM_CSV_DEBUG_MIN, "TM CSV: open failed:", e)
            self._close_tm_csv()

    def _append_tm_csv_row(self, kv: dict[str, str]) -> None:
        """DEBUG≥4: append one row to test_1.csv and print a compact TM_CSV line."""
        if self._debug_level < _TM_CSV_DEBUG_MIN:
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
                _TM_CSV_DEBUG_MIN,
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
            self._dbg(_TM_CSV_DEBUG_MIN, "TM CSV: row failed:", e)

    def _update_measured_lcds_from_tm(self, kv: dict[str, str]) -> None:
        """Refresh X/Y/Z coil-current LCDs from TM (DROK-measured mA via Pico, realtime)."""
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
                v = self._tm_float(kv, "measured_vdc")
            if v is None:
                self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_volts_cache)
                continue
            if not trust_meas:
                self._lcd_set_if_changed(
                    lcd, f"{v:.2f}", neutral_style, self._lcd_volts_cache
                )
                continue
            set_v = self._tm_float(kv, f"set_{ax}_v")
            c = _coil_volts_lcd_color(v, set_v)
            self._lcd_set_if_changed(
                lcd,
                f"{v:.2f}",
                f"background-color: {_MEAS_LCD_BG}; color: {c};",
                self._lcd_volts_cache,
            )

    def _update_gauss_lcds_from_tm(self, kv: dict[str, str]) -> None:
        """|B| (Gauss) at Helmholtz midpoint; axis I from TM mA only (DROK via Pico) — each TM::."""
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

    def _update_cc_coil_leds_from_tm(self, kv: dict[str, str]) -> None:
        """DROK TM:: ``drok_cc_led`` (0 red / 1 lime CC / 2 yellow) for ``drok_axis`` (or all axes if unknown)."""
        if not self._led_cc_coil:
            return
        led = self._tm_int(kv, "drok_cc_led")
        if led is None:
            return
        axn = (kv.get("drok_axis") or kv.get("DROK_AXIS") or "").strip().upper()[:1]
        if axn in ("X", "Y", "Z"):
            axes = (axn,)
        else:
            axes = ("X", "Y", "Z")
        if led == 1:
            color = "lime"
        elif led == 2:
            color = "yellow"
        else:
            color = "red"
        for ax in axes:
            rb = self._led_cc_coil.get(ax)
            if rb is not None:
                _apply_led_color(rb, color)

    def _reset_cc_coil_leds_disconnected(self) -> None:
        for rb in self._led_cc_coil.values():
            _apply_led_color(rb, "red")

    def _reset_measured_lcds_no_data(self) -> None:
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        for _ax, _sp, _pb, lcd, _chk in self._axis_rows:
            self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_meas_cache)
        for _ax, lcd in self._axis_volts_lcd:
            self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_volts_cache)
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

    def _on_safe_calibrator(self) -> None:
        """Send `safe`: temporary drive-off / disable for the connected axis (firmware); COM may stay open."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        try:
            self._dbg(1, "action: SAFE (safe)")
            self._serial.write(b"safe\r\n")
            self._serial.flush()
            self._set_status(
                "SAFE sent (temporary disable — output off). Disconnect and reconnect serial to re-arm enables."
            )
        except Exception as e:
            self._set_status(f"SAFE write failed: {e}")

    def _on_reset_calibrator(self) -> None:
        """Send safe_reset: Pico clears enables and commanded V; all bridge PWM outputs low (same as SAFE)."""
        if self._serial is None:
            self._set_status("Not connected.")
            return
        try:
            self._dbg(1, "action: Reset (safe_reset)")
            self._serial.write(b"safe_reset\r\n")
            self._serial.flush()
            self._set_status("safe_reset sent (Pico PWM/coils off).")
            self._pico_has_error = False
            self._update_status_leds()
        except Exception as e:
            self._set_status(f"Reset write failed: {e}")

    def _apply_tm_line(self, line: str) -> None:
        """Telemetry line: updates status LEDs; not copied to the text log."""
        line = self._repair_tm_orphan_set_x_prefix(line)
        kv = self._parse_tm_tokens(line)
        if self._debug_level == _TM_CSV_DEBUG_MIN:
            s_dbg = line.strip("\r\n").strip()
            if len(s_dbg) > 420:
                s_dbg = s_dbg[:417] + "..."
            has_sx = "set_X_v" in kv or "set_x_v" in kv
            has_xsig = "X_ma" in kv or "coil_V_X" in kv
            if self._tm_dbg_setx_absent_x_present_pending and (not has_sx) and has_xsig:
                self._tm_dbg_setx_absent_x_present_pending = False
                self._tm_dbg_first_tm_after_connect = False
                self._dbg(
                    _TM_CSV_DEBUG_MIN,
                    "TM dbg (no set_X_v/set_x_v token but X_ma or coil_V_X present):",
                    s_dbg,
                )
            elif self._tm_dbg_first_tm_after_connect:
                self._tm_dbg_first_tm_after_connect = False
                self._dbg(_TM_CSV_DEBUG_MIN, "TM dbg (first TM line this link):", s_dbg)
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
        self._update_gauss_lcds_from_tm(kv)
        self._update_null_indicator_from_tm(kv)
        self._update_cc_coil_leds_from_tm(kv)
        self._note_pico_liveness()
        self._append_tm_csv_row(kv)
        self._last_tm_kv = dict(kv)

    def _process_serial_line(self, line: str) -> None:
        s = line.strip("\r\n").strip()
        if s.startswith("\ufeff"):
            s = s[1:].lstrip()
        if not s:
            return
        s = self._repair_tm_orphan_set_x_prefix(s)
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
            if self._debug_level == _TM_CSV_DEBUG_MIN:
                self._dbg(_TM_CSV_DEBUG_MIN, "TXT", payload[:220].replace("\r", " "))
            self._try_parse_pico_version_from_txt_payload(payload)
            self._append_pico_log_line(payload)
            return
        if re.match(r"(?i)^TM::", s):
            self._apply_tm_line(s)
            return
        if self._line_looks_like_tm_telemetry(s):
            self._apply_tm_line(s)
            return
        # Truly non-telemetry (boot noise, mis-framed lines). Do not log TM-shaped rows here —
        # orphan `=0.000 set_Y_v=...` lines are repaired + handled above.
        if self._debug_level == _TM_CSV_DEBUG_MIN:
            self._dbg(_TM_CSV_DEBUG_MIN, "RX (unprefixed)", repr(s)[:500])
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
        # Run _mag_poll after USB TM:: processing (below) so MagTest.xlsx / LCDs and
        # _last_tm_kv refer to the same telemetry window; MT102 sample is still current.
        if self._serial is None:
            self._mag_poll()
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
                if self._debug_level == _TM_CSV_DEBUG_MIN:
                    self._dbg(
                        _TM_CSV_DEBUG_MIN,
                        "serial read",
                        len(chunk),
                        "bytes; rx_buf total",
                        len(self._rx_buf),
                    )
        except Exception:
            self._mag_poll()
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
        if self._debug_level == 1 and processed >= line_cap:
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
        self._mag_poll()

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
        """CalibratorUI_DROK.ui has no legacy Pico status radio LEDs; keep hook for callers."""
        return

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

    def _reload_mt102_ini_preferences(self) -> None:
        """LCD color limits and declination from [mt102_limits] / [mt102_display]."""
        ini = self._ini
        if ini.has_section("mt102_limits"):
            try:
                self._mt102_raw_green = int(
                    ini.get("mt102_limits", "raw_green", fallback=str(MT102_RAW_GREEN))
                )
            except ValueError:
                self._mt102_raw_green = MT102_RAW_GREEN
            try:
                self._mt102_raw_amber = int(
                    ini.get("mt102_limits", "raw_amber", fallback=str(MT102_RAW_AMBER))
                )
            except ValueError:
                self._mt102_raw_amber = MT102_RAW_AMBER
            try:
                self._mt102_gauss_green = float(
                    ini.get("mt102_limits", "gauss_green", fallback=str(MT102_GAUSS_GREEN))
                )
            except ValueError:
                self._mt102_gauss_green = MT102_GAUSS_GREEN
            try:
                self._mt102_gauss_amber = float(
                    ini.get("mt102_limits", "gauss_amber", fallback=str(MT102_GAUSS_AMBER))
                )
            except ValueError:
                self._mt102_gauss_amber = MT102_GAUSS_AMBER
        if ini.has_section("mt102_display"):
            try:
                # Gauss = fcal_corrected_counts × mag_raw_to_gauss (see mt102_interface + ini).
                self._mag_raw_to_gauss = float(
                    ini.get(
                        "mt102_display",
                        "mag_raw_to_gauss",
                        fallback=str(MAG_RAW_TO_GAUSS),
                    )
                )
            except ValueError:
                self._mag_raw_to_gauss = MAG_RAW_TO_GAUSS
            try:
                self._mag_declination_deg = float(
                    ini.get("mt102_display", "mag_declination_deg", fallback="0")
                )
            except ValueError:
                self._mag_declination_deg = 0.0

    def _on_mt102_thread_error(self, msg: str) -> None:
        self._set_status("MT-102: %s" % (msg,))

    def _on_wit901_thread_error(self, msg: str) -> None:
        self._set_status("Wit901: %s" % (msg,))
        self._dbg(3, "Wit901:", msg)

    @staticmethod
    def _find_lcd_number(window: QMainWindow, object_name: str) -> QLCDNumber | None:
        lcd = window.findChild(QLCDNumber, object_name)
        if lcd is not None:
            return lcd
        cw = window.centralWidget() if hasattr(window, "centralWidget") else None
        if cw is not None:
            lcd = cw.findChild(QLCDNumber, object_name)
            if lcd is not None:
                return lcd
        return None

    @staticmethod
    def _find_label_widget(window: QMainWindow, object_name: str) -> QLabel | None:
        lab = window.findChild(QLabel, object_name)
        if lab is not None:
            return lab
        cw = window.centralWidget() if hasattr(window, "centralWidget") else None
        if cw is not None:
            lab = cw.findChild(QLabel, object_name)
            if lab is not None:
                return lab
        return None

    _RE_MT102_FIELD_GAUSS_LCD = re.compile(
        r"^lcdNumber_(?:MT102|Mt102)_([XYZ])_(?:[Gg]auss)$"
    )
    _RE_WIT901_FIELD_GAUSS_LCD = re.compile(
        r"^lcdNumber_(?:Wit901|WIT901|WIT_901|wit901)_([XYZxyz])_(?:[Gg]auss)$"
    )
    _RE_WIT901_FIELD_GAUSS_LABEL = re.compile(
        r"^label_(?:Wit901|WIT901|WIT_901|wit901)_([XYZxyz])_(?:[Gg]auss)$"
    )
    _WIT901_GAUSS_FALLBACK_LCD_NAMES: tuple[tuple[str, str], ...] = (
        ("X", "lcdNumber_Wit901_X_Gauss"),
        ("Y", "lcdNumber_Wit901_Y_Gauss"),
        ("Z", "lcdNumber_Wit901_Z_Gauss"),
    )
    _WIT901_GAUSS_FALLBACK_LABEL_NAMES: tuple[tuple[str, str], ...] = (
        ("X", "label_Wit901_X_Gauss"),
        ("Y", "label_Wit901_Y_Gauss"),
        ("Z", "label_Wit901_Z_Gauss"),
    )
    # Sensed attitude (degrees) — used as visual reference for field Gauss LCD numeral size.
    _MT102_ATTITUDE_LCD_NAMES = (
        "lcdNumber_Mt102_X",
        "lcdNumber_MT102_Y",
        "lcdNumber_MT102_Z",
    )

    def _reference_mt102_attitude_lcd(self) -> QLCDNumber | None:
        for name in self._MT102_ATTITUDE_LCD_NAMES:
            lcd = self._find_lcd_number(self._win, name)
            if lcd is not None:
                return lcd
        return None

    def _field_gauss_lcd_match_attitude_size(self, lcd: QLCDNumber, *, gauss_digit_count: int) -> None:
        """Match segment size to sensed-attitude LCDs: same height; width ∝ digit slots vs attitude (7)."""
        ref = self._reference_mt102_attitude_lcd()
        if ref is None:
            lcd.setMinimumSize(max(lcd.minimumWidth(), 160), max(lcd.minimumHeight(), 56))
            return
        ref_w = max(ref.minimumWidth(), ref.width(), ref.sizeHint().width())
        ref_h = max(ref.minimumHeight(), ref.height(), ref.sizeHint().height())
        att_digits = 7
        nd = max(7, int(gauss_digit_count))
        scale = float(nd) / float(att_digits)
        target_w = int(max(ref_w * scale * 1.08, ref_w * scale + 16))
        target_h = int(max(ref_h * 1.06, ref_h + 4))
        lcd.setMinimumSize(max(lcd.minimumWidth(), target_w), max(lcd.minimumHeight(), target_h))
        lcd.setFont(QFont(ref.font()))

    def _field_gauss_label_match_attitude(self, lab: QLabel) -> None:
        """Match QLabel readout font/height to sensed-attitude LCDs (segment size proxy)."""
        ref = self._reference_mt102_attitude_lcd()
        if ref is None:
            lab.setMinimumHeight(max(lab.minimumHeight(), 48))
            return
        ref_h = max(ref.minimumHeight(), ref.height(), ref.sizeHint().height())
        ref_w = max(ref.minimumWidth(), ref.width(), ref.sizeHint().width())
        lab.setMinimumSize(
            max(lab.minimumWidth(), int(ref_w * 1.05)),
            max(lab.minimumHeight(), ref_h),
        )
        lab.setFont(QFont(ref.font()))

    def _discover_mt102_field_gauss_lcds(self) -> list[tuple[QLCDNumber, str]]:
        """Bind MT-102 *field* Gauss seven-segments by objectName (any Mt/MT + Gauss/gauss spelling)."""
        out: list[tuple[QLCDNumber, str]] = []
        seen: set[int] = set()
        for lcd in self._win.findChildren(QLCDNumber):
            m = self._RE_MT102_FIELD_GAUSS_LCD.match(lcd.objectName())
            if not m:
                continue
            lid = id(lcd)
            if lid in seen:
                continue
            seen.add(lid)
            out.append((lcd, m.group(1)))
            lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
            if hasattr(lcd, "setSmallDecimalPoint"):
                lcd.setSmallDecimalPoint(True)
            self._field_gauss_lcd_match_attitude_size(lcd, gauss_digit_count=7)
        return out

    def _discover_wit901_field_gauss_lcds(self) -> list[tuple[QWidget, str]]:
        """Bind Wit901 Gauss readouts. Prefer exact ``lcdNumber_Wit901_[XYZ]_Gauss`` QLCDNumbers."""
        by_ax: dict[str, QWidget] = {}
        # 1) Exact Designer names (QLCDNumber only — avoids regex picking a wrong sibling first).
        for ax, oname in self._WIT901_GAUSS_FALLBACK_LCD_NAMES:
            lcd = self._find_lcd_number(self._win, oname)
            if lcd is not None:
                by_ax[ax] = lcd
        # 2) Regex variants only for axes still missing
        for lcd in self._win.findChildren(QLCDNumber):
            oname = (lcd.objectName() or "").strip()
            m = self._RE_WIT901_FIELD_GAUSS_LCD.match(oname)
            if not m:
                continue
            ax = m.group(1).upper()
            if ax not in by_ax:
                by_ax[ax] = lcd
        for lab in self._win.findChildren(QLabel):
            oname = (lab.objectName() or "").strip()
            m = self._RE_WIT901_FIELD_GAUSS_LABEL.match(oname)
            if not m:
                continue
            ax = m.group(1).upper()
            if ax not in by_ax:
                by_ax[ax] = lab
        for ax, oname in self._WIT901_GAUSS_FALLBACK_LABEL_NAMES:
            if ax in by_ax:
                continue
            lab = self._find_label_widget(self._win, oname)
            if lab is not None:
                by_ax[ax] = lab
        out: list[tuple[QWidget, str]] = []
        for ax in ("X", "Y", "Z"):
            w = by_ax.get(ax)
            if w is None:
                continue
            if isinstance(w, QLCDNumber):
                w.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
                if hasattr(w, "setSmallDecimalPoint"):
                    w.setSmallDecimalPoint(True)
                self._field_gauss_lcd_match_attitude_size(w, gauss_digit_count=8)
            elif isinstance(w, QLabel):
                self._field_gauss_label_match_attitude(w)
                w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            out.append((w, ax))
        if len(out) != 3 and not getattr(self, "_wit901_field_gauss_disc_warned", False):
            self._wit901_field_gauss_disc_warned = True
            try:
                hint_lcd = sorted(
                    {
                        (x.objectName() or "").strip()
                        for x in self._win.findChildren(QLCDNumber)
                        if (x.objectName() or "").strip()
                        and (
                            "901" in (x.objectName() or "").lower()
                            or "wit" in (x.objectName() or "").lower()
                        )
                    }
                )[:30]
                hint_lab = sorted(
                    {
                        (x.objectName() or "").strip()
                        for x in self._win.findChildren(QLabel)
                        if (x.objectName() or "").strip()
                        and (
                            "901" in (x.objectName() or "").lower()
                            or "wit" in (x.objectName() or "").lower()
                        )
                    }
                )[:30]
                sys.stderr.write(
                    "[CalibratorUI] Wit901 Gauss: found %d widget(s) %s; expected 3. "
                    "Use three QLCDNumber: lcdNumber_Wit901_X_Gauss, lcdNumber_Wit901_Y_Gauss, "
                    "lcdNumber_Wit901_Z_Gauss (exact names). Optional: label_Wit901_*_Gauss QLabel. "
                    "QLCDNumber hints: %s  QLabel hints: %s\n"
                    % (
                        len(out),
                        [(w.objectName(), ax) for w, ax in out],
                        hint_lcd or ["(none)"],
                        hint_lab or ["(none)"],
                    )
                )
            except Exception:
                pass
        return out

    def _wit901_merge_missing_axis_lcds(self) -> None:
        """If regex missed an axis, attach widgets by canonical ``objectName`` (same session)."""
        cur = self._wit901_field_gauss_lcds
        if cur is None:
            return
        have = {ax for _, ax in cur}
        for ax, oname in self._WIT901_GAUSS_FALLBACK_LCD_NAMES:
            if ax in have:
                continue
            lcd = self._find_lcd_number(self._win, oname)
            if lcd is not None:
                lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
                if hasattr(lcd, "setSmallDecimalPoint"):
                    lcd.setSmallDecimalPoint(True)
                self._field_gauss_lcd_match_attitude_size(lcd, gauss_digit_count=8)
                cur.append((lcd, ax))
                have.add(ax)
        for ax, oname in self._WIT901_GAUSS_FALLBACK_LABEL_NAMES:
            if ax in have:
                continue
            lab = self._find_label_widget(self._win, oname)
            if lab is None:
                continue
            self._field_gauss_label_match_attitude(lab)
            lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cur.append((lab, ax))
            have.add(ax)

    def _refresh_wit901_gauss_lcds(
        self, w901_g: tuple[float, float, float] | None
    ) -> None:
        """Drive Wit901 Gauss widgets from one ``_snapshot_wit901_gauss()`` tuple (``mt102_swapped_xy`` applied)."""
        if self._wit901_field_gauss_lcds is None:
            self._wit901_field_gauss_lcds = self._discover_wit901_field_gauss_lcds()
        self._wit901_merge_missing_axis_lcds()
        if not self._wit901_field_gauss_lcds:
            return
        vals: dict[str, float | None] = {"X": None, "Y": None, "Z": None}
        if w901_g is not None and len(w901_g) == 3:
            x, y, z = (float(w901_g[0]), float(w901_g[1]), float(w901_g[2]))
            vals["X"] = x if math.isfinite(x) else None
            vals["Y"] = y if math.isfinite(y) else None
            vals["Z"] = z if math.isfinite(z) else None
        for w, ax in self._wit901_field_gauss_lcds:
            v = vals[ax]
            if isinstance(w, QLCDNumber):
                w.setDigitCount(8)
                w.setMode(QLCDNumber.Mode.Dec)
                if v is not None:
                    w.display("%+.4f" % v)
                    color = self._mag_lcd_color_gauss(
                        v, self._mt102_gauss_green, self._mt102_gauss_amber
                    )
                else:
                    w.display("---")
                    color = _MEAS_LCD_NO_DATA
                w.setStyleSheet(
                    "background-color: %s; color: %s;" % (MT102_LCD_BG, color)
                )
            elif isinstance(w, QLabel):
                if v is not None:
                    w.setText("%+.4f" % v)
                    color = self._mag_lcd_color_gauss(
                        v, self._mt102_gauss_green, self._mt102_gauss_amber
                    )
                else:
                    w.setText("---")
                    color = _MEAS_LCD_NO_DATA
                w.setStyleSheet(
                    "background-color: %s; color: %s; padding: 2px 6px;"
                    % (MT102_LCD_BG, color)
                )

    def _reset_gauss_source_combo_for_disconnect(self) -> None:
        """Clear Gauss source selector (DROK UI) when sensors disconnect."""
        self._gauss_combo_seeded = False
        c = getattr(self, "_combo_gauss_source", None)
        if c is None:
            return
        c.blockSignals(True)
        c.clear()
        c.blockSignals(False)
        c.setEnabled(False)

    def _populate_gauss_source_combo(self) -> None:
        """Fill ``comboBox_SelectedGaussSource`` after MT-102 and/or Wit901 are live (DROK UI)."""
        c = getattr(self, "_combo_gauss_source", None)
        if c is None:
            return
        mt_ok = False
        m = getattr(self, "_mt102", None)
        if m is not None:
            try:
                mt_ok = bool(m.is_connected())
            except Exception:
                mt_ok = False
        w9_ok = bool(getattr(self, "_wit901_uart_open", False))
        if not mt_ok and not w9_ok:
            self._reset_gauss_source_combo_for_disconnect()
            return
        prev = c.currentText().strip() if c.count() else ""
        c.blockSignals(True)
        c.clear()
        if mt_ok:
            c.addItem("MT102")
        if w9_ok:
            c.addItem("WIT901")
        c.blockSignals(False)
        c.setEnabled(c.count() > 0)
        self._gauss_combo_seeded = True
        if prev:
            idx = c.findText(prev)
            if idx >= 0:
                c.setCurrentIndex(idx)
        elif c.count() > 0:
            c.setCurrentIndex(0)

    def _refresh_drok_axis_gauss_lcds(
        self,
        have_mt102_field_gauss: bool,
        gx: float,
        gy: float,
        gz: float,
    ) -> None:
        """Drive ``lcdNumber_*_Axis_Gauss`` from MT102 or Wit901 × per-axis cal spin (DROK UI)."""
        if not self._drok_axis_gauss_lcds:
            return
        combo = self._combo_gauss_source
        if combo is None or combo.count() == 0:
            label = "MT102"
        else:
            label = (combo.currentText() or "MT102").strip().upper()
        use_mt = "MT" in label or "102" in label
        w901_t = self._snapshot_wit901_gauss()
        nodata_style = (
            f"background-color: {_MEAS_LCD_BG}; color: {_MEAS_LCD_NO_DATA};"
        )
        vals: dict[str, float | None] = {"X": None, "Y": None, "Z": None}
        if use_mt:
            if have_mt102_field_gauss and all(
                math.isfinite(v) for v in (gx, gy, gz)
            ):
                vals = {"X": float(gx), "Y": float(gy), "Z": float(gz)}
        else:
            if w901_t is not None and len(w901_t) == 3:
                x, y, z = float(w901_t[0]), float(w901_t[1]), float(w901_t[2])
                if all(math.isfinite(v) for v in (x, y, z)):
                    vals = {"X": x, "Y": y, "Z": z}
        for ax, lcd in self._drok_axis_gauss_lcds:
            cal = self._gauss_cal_spins.get(ax)
            try:
                factor = float(cal.value()) if cal is not None else 1.0
            except Exception:
                factor = 1.0
            if factor != factor or abs(factor) > 1e9:
                factor = 1.0
            raw = vals.get(ax)
            if raw is None or raw != raw:
                self._lcd_set_if_changed(lcd, "---", nodata_style, self._lcd_gauss_cache)
                continue
            out = float(raw) * factor
            c = self._mag_lcd_color_gauss(
                out, self._mt102_gauss_green, self._mt102_gauss_amber
            )
            self._lcd_set_if_changed(
                lcd,
                "%.3f" % out,
                f"background-color: {_MEAS_LCD_BG}; color: {c};",
                self._lcd_gauss_cache,
            )

    def _snapshot_wit901_gauss_raw(self) -> tuple[float, float, float] | None:
        """Wit901 Gauss (X,Y,Z) from ``wit901_mag_stream`` with **no** ``mt102_swapped_xy`` remap."""
        w = getattr(self, "_wit901", None)
        if w is None:
            return None
        try:
            g = w.get_latest_gauss()
        except Exception:
            return None
        if g is None or len(g) != 3:
            return None
        return (float(g[0]), float(g[1]), float(g[2]))

    def _wit901_gauss_after_mt102_swap(
        self, g: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        """Apply ``[serial] mt102_swapped_xy`` X/Y interchange to a raw Wit901 Gauss triple."""
        gx, gy, gz = g
        ini = getattr(self, "_ini", None)
        if ini is not None and _serial_mt102_swapped_xy(ini):
            return (gy, gx, gz)
        return (gx, gy, gz)

    def _snapshot_wit901_gauss_raw_and_display(
        self,
    ) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None]:
        """One UART snapshot: ``(raw, display)`` where display = raw after ``mt102_swapped_xy``."""
        raw = self._snapshot_wit901_gauss_raw()
        if raw is None:
            return None, None
        return raw, self._wit901_gauss_after_mt102_swap(raw)

    def _snapshot_wit901_gauss(self) -> tuple[float, float, float] | None:
        """Latest Wit901 Gauss for LCDs/sheets (same as display tuple from ``_snapshot_wit901_gauss_raw_and_display``)."""
        raw = self._snapshot_wit901_gauss_raw()
        if raw is None:
            return None
        return self._wit901_gauss_after_mt102_swap(raw)

    @staticmethod
    def _field_vector_to_rotation(
        bx: float, by: float, bz: float, mag_declination_deg: float = 0.0
    ) -> tuple[float, float, float]:
        """Magnetic field vector (consistent units) → viewer roll, pitch, yaw (degrees)."""
        mag_len = math.sqrt(bx * bx + by * by + bz * bz)
        if mag_len < 1e-9:
            return (0.0, 0.0, 0.0)
        nx, ny, nz = bx / mag_len, by / mag_len, bz / mag_len
        heading_mag = math.degrees(math.atan2(ny, nx))
        yaw = heading_mag + mag_declination_deg
        pitch = -math.degrees(math.asin(max(-1, min(1, nz))))
        roll = 90.0 * nx if abs(nx) > 0.3 else 0.0
        return (roll, pitch, yaw)

    @staticmethod
    def _mag_data_to_rotation(mag, mag_declination_deg: float = 0.0) -> tuple[float, float, float]:
        """Raw mag counts → viewer rotation (same geometry as _field_vector_to_rotation)."""
        return CalibratorController._field_vector_to_rotation(
            float(mag.x), float(mag.y), float(mag.z), mag_declination_deg
        )

    @staticmethod
    def _mag_lcd_color_raw(raw_val: int, green: int, amber: int) -> str:
        a = abs(int(raw_val))
        if a <= green:
            return _MEAS_LCD_GREEN
        if a <= amber:
            return MT102_AMBER
        return _MEAS_LCD_RED

    @staticmethod
    def _mag_lcd_color_gauss(gauss_val: float, green: float, amber: float) -> str:
        a = abs(float(gauss_val))
        if a <= green:
            return _MEAS_LCD_GREEN
        if a <= amber:
            return MT102_AMBER
        return _MEAS_LCD_RED

    def _disconnect_wit901_only(self) -> None:
        self._wit901_uart_open = False
        w = getattr(self, "_wit901", None)
        if w is not None:
            try:
                w.disconnect()
            except Exception:
                pass
        try:
            self._refresh_wit901_gauss_lcds(None)
        except Exception:
            pass
        self._wit901_field_gauss_lcds = None
        self._populate_gauss_source_combo()

    def _disconnect_mt102_only(self) -> None:
        if getattr(self, "_mt102", None) is not None:
            try:
                self._mt102.disconnect()
            except Exception:
                pass
            self._mt102 = None
            self._dbg_mt102_f_cal_logged = False
            self._mt102_f_block_md_written = False
            self._mt102_cal_que_mono = 0.0
            self._mt102_fcal_polls_without_cal = 0
            self._mt102_fcal_missing_logged = False
            self._close_mag_test_xlsx()
            self._close_external_drive_xlsx()
            self._refresh_mt102_fcal_applied_led()
            self._populate_gauss_source_combo()
        vd = getattr(self, "_viewer3d", None)
        if vd is not None and hasattr(vd, "set_rotation"):
            try:
                vd.set_rotation(0, 0, 0)
            except Exception:
                pass

    def _connect_mt102_after_pico(self) -> None:
        """After Pico serial is up: open MT-102 from ini (RS422 RX + RS232 TX when both set)."""
        if MT102Interface is None:
            self._dbg(3, "MT102: skipped (mt102_interface import failed)")
            return
        rs422 = self._ini.get("serial", "rs422_port", fallback="").strip()
        rs232 = self._ini.get("serial", "rs232_port", fallback="").strip()
        if not rs422:
            rs422 = self._ini.get("serial", "mt102_rs422_port", fallback="").strip()
        if not rs232:
            rs232 = self._ini.get("serial", "mt102_rs232_port", fallback="").strip()
        try:
            br = self._ini.get(
                "serial", "baud_rate", fallback=str(_DEFAULT_MT102_BAUD)
            ).strip()
            if not br:
                br = self._ini.get(
                    "serial", "mt102_baud", fallback=str(_DEFAULT_MT102_BAUD)
                ).strip()
            baud = int(br)
        except ValueError:
            baud = _DEFAULT_MT102_BAUD
        if not rs422 and not rs232:
            self._dbg(3, "MT102: skipped (rs422_port and rs232_port empty in ini)")
            return
        use_dual = bool(rs422 and rs232)
        if use_dual:
            port, port_tx = rs422, rs232
        else:
            port = rs422 or rs232
            port_tx = None
            if not port or port == "(no ports)":
                self._dbg(3, "MT102: skipped (no valid COM in ini)")
                return
        try:
            self._mt102 = MT102Interface(
                on_error=lambda m: self._mt102_err_bridge.err.emit(str(m)),
                serial_factory=None,
            )
            if not self._mt102.connect(port, baud, port_tx=port_tx):
                self._mt102 = None
                raise RuntimeError("MT-102 connect() returned False")
        except Exception as e:
            self._mt102 = None
            self._dbg(3, "MT102 connect failed:", e)
            QMessageBox.warning(
                self._win,
                "MT-102",
                "Pico is connected, but MT-102 failed to open:\n%s\n\n"
                "Check [serial] rs422_port / rs232_port / baud_rate in %s."
                % (e, _INI_PATH.name),
            )
            return
        te = self._win.findChild(QTextEdit, "textEdit_MT102_Data")
        if te is not None:
            te.clear()
        msg = (
            "MT-102: RX=%s TX=%s @ %d"
            % (port, port_tx if port_tx else "(same)", baud)
            if use_dual
            else "MT-102: %s @ %d" % (port, baud)
        )
        self._dbg(3, "connect:", msg)
        self._set_status("%s | %s" % (self._status_main.text(), msg))
        self._mt102_fcal_missing_logged = False
        self._mt102_fcal_polls_without_cal = 0
        try:
            if hasattr(self._mt102, "request_cal_data"):
                self._mt102.request_cal_data()
            self._mt102_cal_que_mono = time.monotonic()
        except Exception:
            pass

    def _connect_wit901_if_configured(self) -> None:
        """Open Wit HWT901 on ``[serial] wit901_port`` after MT-102 (non-fatal if it fails)."""
        if _w9_pkg is None:
            self._dbg(3, "Wit901: skipped (wit901_mag_stream import failed)")
            return
        port = self._ini.get("serial", "wit901_port", fallback=_DEFAULT_WIT901_PORT).strip()
        if not port:
            self._dbg(3, "Wit901: skipped (wit901_port empty)")
            return
        # Skip Wit901 only when Pico serial is actually open on that COM (combo can match Pico port while idle).
        if self._serial is not None:
            pico = self._current_port().strip()
            if pico and port.replace(" ", "").upper() == pico.replace(" ", "").upper():
                self._dbg(3, "Wit901: skipped (same COM as Pico)")
                return
        try:
            baud = int(
                self._ini.get("serial", "wit901_baud", fallback=str(_DEFAULT_WIT901_BAUD)).strip()
            )
        except ValueError:
            baud = _DEFAULT_WIT901_BAUD
        w = getattr(self, "_wit901", None)
        if w is None:
            return
        if not w.connect(port, baud):
            QMessageBox.warning(
                self._win,
                "Wit901",
                "Pico (and possibly MT-102) connected, but Wit901 failed to open.\n"
                "Check [serial] wit901_port / wit901_baud in %s." % (_INI_PATH.name,),
            )
            return
        self._dbg(3, "Wit901: opened", port, "@", baud)
        self._wit901_uart_open = True
        self._populate_gauss_source_combo()
        self._set_status("%s | Wit901 %s @ %d" % (self._status_main.text(), port, baud))
        try:
            sys.stderr.write(
                "[CalibratorUI] Wit901 field is Gauss: wit901_mag_stream int16 → "
                "(16/32768) µT/LSB, G = µT/100 (same unit as MT102 Gauss columns). "
                "[serial] mt102_swapped_xy=true|T|1 when MT-102 stream still has legacy swapped mag X/Y (Wit901 Gauss "
                "X/Y is then swapped for alignment); F/false/0 for reworked units (default F from load_ini).\n"
            )
            sys.stderr.flush()
        except Exception:
            pass

    def _refresh_mt102_fcal_applied_led(self) -> None:
        """Indicator ``radioButton_F_CalApplied``: gray if MT-102 not connected; else lime or red."""
        rb = self._led_f_cal_applied
        if rb is None:
            return
        m = getattr(self, "_mt102", None)
        if m is None:
            _apply_led_color(rb, "gray")
            return
        try:
            if not m.is_connected():
                _apply_led_color(rb, "gray")
                return
            cal = m.get_cal_data() if hasattr(m, "get_cal_data") else None
            _apply_led_color(rb, "lime" if cal is not None else "red_bright")
        except Exception:
            _apply_led_color(rb, "red_bright")

    def _maybe_request_mt102_fcal(self) -> None:
        """Re-send QUE until flash F-cal is parsed (QUE-only TX; safe on MT-102)."""
        m = getattr(self, "_mt102", None)
        if m is None or not hasattr(m, "get_cal_data") or not hasattr(m, "request_cal_data"):
            return
        try:
            if m.get_cal_data() is not None:
                return
            if not m.is_connected():
                return
        except Exception:
            return
        now = time.monotonic()
        if now - self._mt102_cal_que_mono < 1.5:
            return
        self._mt102_cal_que_mono = now
        try:
            m.request_cal_data()
        except Exception:
            pass

    def _close_mag_test_xlsx(self) -> None:
        """Flush and close DEBUG=5 MagTest workbook (MT-102 disconnect or app disconnect)."""
        wb = self._mag_test_wb
        if wb is None:
            return
        try:
            wb.save(str(_MAG_TEST_XLSX_PATH))
        except Exception as e:
            try:
                sys.stderr.write(
                    "[CalibratorUI] MagTest.xlsx save failed: %s\n" % (e,)
                )
            except Exception:
                pass
        self._mag_test_wb = None
        self._mag_test_ws = None
        self._mag_test_xlsx_row_count = 0

    def _ensure_mag_test_xlsx(self) -> bool:
        """Open ``MagTest.xlsx`` with header row when DEBUG=5 and openpyxl is installed."""
        if self._debug_level != _MT102_TRACE_DEBUG_MIN:
            return False
        if _OpenpyxlWorkbook is None:
            if not self._mag_test_xlsx_missing_logged:
                self._mag_test_xlsx_missing_logged = True
                try:
                    sys.stderr.write(
                        "[CalibratorUI] DEBUG=5: pip install openpyxl to write %s\n"
                        % (_MAG_TEST_XLSX_PATH.resolve(),)
                    )
                except Exception:
                    pass
            return False
        if self._mag_test_wb is not None:
            return True
        try:
            wb = _OpenpyxlWorkbook()
            ws = wb.active
            ws.title = "MagTest"
            ws.append(
                [
                    "timestamp",
                    "coil_V_X",
                    "coil_V_Y",
                    "coil_V_Z",
                    "RAW_X",
                    "Gauss_X",
                    "RAW_Y",
                    "Gauss_Y",
                    "RAW_Z",
                    "Gauss_Z",
                    "W901_Gauss_X",
                    "W901_Gauss_Y",
                    "W901_Gauss_Z",
                    "W901_Raw_Gauss_X",
                    "W901_Raw_Gauss_Y",
                    "W901_Raw_Gauss_Z",
                ]
            )
            self._mag_test_wb = wb
            self._mag_test_ws = ws
            self._mag_test_xlsx_row_count = 0
            wb.save(str(_MAG_TEST_XLSX_PATH))
        except Exception as e:
            self._mag_test_wb = None
            self._mag_test_ws = None
            try:
                sys.stderr.write(
                    "[CalibratorUI] MagTest.xlsx init failed: %s\n" % (e,)
                )
            except Exception:
                pass
            return False
        return True

    def _append_mag_test_xlsx_row(
        self,
        vx: float | None,
        vy: float | None,
        vz: float | None,
        mag: object,
        gx: float,
        gy: float,
        gz: float,
        w901_g: tuple[float, float, float] | None = None,
        w901_g_raw: tuple[float, float, float] | None = None,
    ) -> None:
        """One DEBUG=5 row: host time, TM coil V, MT102 raw + Gauss; Wit901 Gauss (swapped) + raw same poll."""
        if not self._ensure_mag_test_xlsx():
            return
        ws = self._mag_test_ws
        wb = self._mag_test_wb
        if ws is None or wb is None:
            return

        def _fin(v: float | None) -> float | None:
            if v is None or not math.isfinite(v):
                return None
            return float(v)

        def _fin_g(v: float) -> float | None:
            if not math.isfinite(v):
                return None
            return float(v)

        def _fin_g3(
            g: tuple[float, float, float] | None,
        ) -> tuple[float | None, float | None, float | None]:
            if g is None:
                return (None, None, None)
            a, b, c = g
            return (_fin_g(float(a)), _fin_g(float(b)), _fin_g(float(c)))

        wx, wy, wz = _fin_g3(w901_g)
        wrx, wry, wrz = _fin_g3(w901_g_raw)

        try:
            ws.append(
                [
                    datetime.datetime.now(),
                    _fin(vx),
                    _fin(vy),
                    _fin(vz),
                    int(getattr(mag, "x")),
                    _fin_g(gx),
                    int(getattr(mag, "y")),
                    _fin_g(gy),
                    int(getattr(mag, "z")),
                    _fin_g(gz),
                    wx,
                    wy,
                    wz,
                    wrx,
                    wry,
                    wrz,
                ]
            )
            self._mag_test_xlsx_row_count += 1
            if self._mag_test_xlsx_row_count % _MAG_TEST_XLSX_SAVE_EVERY_N == 0:
                wb.save(str(_MAG_TEST_XLSX_PATH))
        except Exception as e:
            try:
                sys.stderr.write(
                    "[CalibratorUI] MagTest.xlsx append failed: %s\n" % (e,)
                )
            except Exception:
                pass
            self._close_mag_test_xlsx()

    def _close_external_drive_xlsx(self) -> None:
        wb = self._external_drive_wb
        if wb is None:
            return
        try:
            wb.save(str(_EXTERNAL_DRIVE_XLSX_PATH))
        except Exception as e:
            try:
                sys.stderr.write(
                    "[CalibratorUI] ExternalDrive.xlsx save failed: %s\n" % (e,)
                )
            except Exception:
                pass
        self._external_drive_wb = None
        self._external_drive_ws = None
        self._external_drive_row_count = 0

    def _ensure_external_drive_xlsx(self) -> bool:
        if _OpenpyxlWorkbook is None:
            return False
        if self._external_drive_wb is not None:
            return True
        try:
            wb = _OpenpyxlWorkbook()
            ws = wb.active
            ws.title = "ExternalDrive"
            ws.append(
                [
                    "timestamp",
                    "coil_V_X",
                    "coil_V_Y",
                    "coil_V_Z",
                    "RAW_X",
                    "Gauss_X",
                    "RAW_Y",
                    "Gauss_Y",
                    "RAW_Z",
                    "Gauss_Z",
                    "W901_Gauss_X",
                    "W901_Gauss_Y",
                    "W901_Gauss_Z",
                    "W901_Raw_Gauss_X",
                    "W901_Raw_Gauss_Y",
                    "W901_Raw_Gauss_Z",
                    "bench_V_X",
                    "bench_V_Y",
                    "bench_V_Z",
                    "bench_I_X",
                    "bench_I_Y",
                    "bench_I_Z",
                ]
            )
            self._external_drive_wb = wb
            self._external_drive_ws = ws
            self._external_drive_row_count = 0
            wb.save(str(_EXTERNAL_DRIVE_XLSX_PATH))
        except Exception as e:
            self._external_drive_wb = None
            self._external_drive_ws = None
            try:
                sys.stderr.write(
                    "[CalibratorUI] ExternalDrive.xlsx init failed: %s\n" % (e,)
                )
            except Exception:
                pass
            return False
        return True

    def _append_external_drive_xlsx_row(
        self,
        vx: float | None,
        vy: float | None,
        vz: float | None,
        mag: object,
        gx: float,
        gy: float,
        gz: float,
        w901_g: tuple[float, float, float] | None = None,
        w901_g_raw: tuple[float, float, float] | None = None,
    ) -> None:
        """Append one row while External Drive mode is active (Pico off; coil V usually blank)."""
        if not self._external_drive_active:
            return
        if not self._ensure_external_drive_xlsx():
            return
        ws = self._external_drive_ws
        wb = self._external_drive_wb
        if ws is None or wb is None:
            return

        def _fin(v: float | None) -> float | None:
            if v is None or not math.isfinite(v):
                return None
            return float(v)

        def _fin_g(v: float) -> float | None:
            if not math.isfinite(v):
                return None
            return float(v)

        def _fin_g3(
            g: tuple[float, float, float] | None,
        ) -> tuple[float | None, float | None, float | None]:
            if g is None:
                return (None, None, None)
            a, b, c = g
            return (_fin_g(float(a)), _fin_g(float(b)), _fin_g(float(c)))

        wx, wy, wz = _fin_g3(w901_g)
        wrx, wry, wrz = _fin_g3(w901_g_raw)
        try:
            ws.append(
                [
                    datetime.datetime.now(),
                    _fin(vx),
                    _fin(vy),
                    _fin(vz),
                    int(getattr(mag, "x")),
                    _fin_g(gx),
                    int(getattr(mag, "y")),
                    _fin_g(gy),
                    int(getattr(mag, "z")),
                    _fin_g(gz),
                    wx,
                    wy,
                    wz,
                    wrx,
                    wry,
                    wrz,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ]
            )
            self._external_drive_row_count += 1
            if self._external_drive_row_count % _EXTERNAL_DRIVE_SAVE_EVERY_N == 0:
                wb.save(str(_EXTERNAL_DRIVE_XLSX_PATH))
        except Exception as e:
            try:
                sys.stderr.write(
                    "[CalibratorUI] ExternalDrive.xlsx append failed: %s\n" % (e,)
                )
            except Exception:
                pass
            self._close_external_drive_xlsx()

    def _mag_poll(self) -> None:
        """Poll MT-102 for M packets; update data monitor, optional LCDs, 3D viewer."""
        gx = gy = gz = float("nan")
        have_g = False

        def _finish_axis_gauss() -> None:
            self._last_mt102_field_gauss = (gx, gy, gz, have_g)
            self._refresh_drok_axis_gauss_lcds(have_g, gx, gy, gz)

        self._refresh_wit901_gauss_lcds(self._snapshot_wit901_gauss())
        if not getattr(self, "_mt102", None) or self._mt102 is None:
            _finish_axis_gauss()
            return
        try:
            if not self._mt102.is_connected():
                self._disconnect_mt102_only()
                self._set_status("MT-102 connection lost — check cable or port")
                _finish_axis_gauss()
                return
        except Exception:
            _finish_axis_gauss()
            return
        self._maybe_request_mt102_fcal()
        self._refresh_mt102_fcal_applied_led()
        try:
            mag = self._mt102.get_mag_data(timeout=0)
        except Exception:
            _finish_axis_gauss()
            return
        if not self._dbg_mt102_f_cal_logged and hasattr(self._mt102, "get_cal_data"):
            try:
                c0 = self._mt102.get_cal_data()
                if c0 is not None:
                    self._dbg_mt102_f_cal_logged = True
                    self._dbg(
                        3,
                        "MT102: factory F-cal loaded; field = MagnetometerParser math × "
                        "ini [mt102_display] mag_raw_to_gauss. serial=%s"
                        % (getattr(c0, "serial_number", "?"),),
                    )
                    if not self._mt102_f_block_md_written:
                        fn = getattr(self._mt102, "build_f_block_capture_markdown", None)
                        if callable(fn):
                            md = fn()
                            if md:
                                try:
                                    _F_BLOCK_CAPTURE_PATH.write_text(
                                        md, encoding="utf-8", newline="\n"
                                    )
                                    self._mt102_f_block_md_written = True
                                    self._dbg(
                                        3,
                                        "MT102: F-block capture →",
                                        str(_F_BLOCK_CAPTURE_PATH.resolve()),
                                    )
                                except OSError as e:
                                    self._dbg(
                                        3,
                                        "MT102: F_BLOCK_CAPTURE.md write failed:",
                                        str(e),
                                    )
            except Exception:
                pass
        if mag is None:
            te = self._win.findChild(QTextEdit, "textEdit_MT102_Data")
            if not te and hasattr(self._win, "centralWidget"):
                cw = self._win.centralWidget()
                if cw:
                    te = cw.findChild(QTextEdit, "textEdit_MT102_Data")
            if te and hasattr(self._mt102, "get_debug_info"):
                info = self._mt102.get_debug_info()
                br = info.get("bytes_received", 0)
                mp = info.get("m_packets_parsed", 0)
                fp = info.get("f_packets_parsed", 0)
                last_raw = info.get("last_raw", b"")[:64]
                raw_hex = " ".join("%02X" % b for b in last_raw) if last_raw else "(none)"
                msg = "RX: %s bytes, %s M packets, %s F (flash cal) packets\n" % (br, mp, fp)
                msg += "Check: MT-102 output → rs422_port, QUE on rs232_port, baud_rate in ini\n"
                if br == 0:
                    msg += "If bytes stay 0: try swapping rs232_port ↔ rs422_port in ini\n"
                if br > 0 and mp == 0:
                    msg += "Last raw (hex): %s\n" % raw_hex
                te.setPlainText(msg)
            _finish_axis_gauss()
            return
        cal = None
        try:
            if hasattr(self._mt102, "get_cal_data"):
                cal = self._mt102.get_cal_data()
        except Exception:
            cal = None
        if cal is None:
            self._mt102_fcal_polls_without_cal += 1
            if (
                self._mt102_fcal_polls_without_cal >= 240
                and not self._mt102_fcal_missing_logged
            ):
                self._mt102_fcal_missing_logged = True
                self._dbg(
                    3,
                    "MT102: factory F-cal still missing after repeated QUE; "
                    "Gauss/G columns stay blank until the F packet parses.",
                )
            gx = gy = gz = float("nan")
            have_g = False
        else:
            self._mt102_fcal_polls_without_cal = 0
            try:
                gx, gy, gz = cal.raw_to_gauss(mag, self._mag_raw_to_gauss)
                have_g = all(math.isfinite(v) for v in (gx, gy, gz))
            except Exception:
                _finish_axis_gauss()
                return
        if (
            self._debug_level == _MT102_TRACE_DEBUG_MIN
            and not self._external_drive_active
        ):
            vx, vy, vz = self._coil_v_xyz_from_last_tm()
            w901_raw, w901_g = self._snapshot_wit901_gauss_raw_and_display()
            self._append_mag_test_xlsx_row(
                vx, vy, vz, mag, gx, gy, gz, w901_g=w901_g, w901_g_raw=w901_raw
            )
        if self._external_drive_active:
            evx, evy, evz = self._coil_v_xyz_from_last_tm()
            ew901_raw, ew901_g = self._snapshot_wit901_gauss_raw_and_display()
            self._append_external_drive_xlsx_row(
                evx, evy, evz, mag, gx, gy, gz, w901_g=ew901_g, w901_g_raw=ew901_raw
            )
        for name, val in (
            ("lcdNumber_MT102_X_raw", mag.x),
            ("lcdNumber_MT102_Y_raw", mag.y),
            ("lcdNumber_MT102_Z_raw", mag.z),
        ):
            lcd = self._find_lcd_number(self._win, name)
            if lcd:
                lcd.setDigitCount(4)
                lcd.setMode(QLCDNumber.Mode.Hex)
                lcd.display(val & 0xFFFF)
                color = self._mag_lcd_color_raw(
                    val, self._mt102_raw_green, self._mt102_raw_amber
                )
                lcd.setStyleSheet(
                    "background-color: %s; color: %s;" % (MT102_LCD_BG, color)
                )
        # Discover once: UI mixes Mt102 vs MT102 and Gauss vs gauss; findChild-by-fixed-list can miss Y/Z.
        if self._mt102_field_gauss_lcds is None:
            self._mt102_field_gauss_lcds = self._discover_mt102_field_gauss_lcds()
            n = len(self._mt102_field_gauss_lcds)
            if n != 3 and not getattr(self, "_mt102_field_gauss_disc_warned", False):
                self._mt102_field_gauss_disc_warned = True
                try:
                    sys.stderr.write(
                        "[CalibratorUI] MT102 field Gauss: found %d QLCDNumber(s) %s; "
                        "expected 3 matching lcdNumber_(MT102|Mt102)_[XYZ]_(Gauss|gauss).\n"
                        % (
                            n,
                            [(lcd.objectName(), ax) for lcd, ax in self._mt102_field_gauss_lcds],
                        )
                    )
                except Exception:
                    pass
        vals = {"X": gx, "Y": gy, "Z": gz}
        for lcd, ax in self._mt102_field_gauss_lcds:
            val = vals[ax]
            lcd.setDigitCount(7)
            lcd.setMode(QLCDNumber.Mode.Dec)
            if have_g:
                lcd.display("%.3f" % val)
                color = self._mag_lcd_color_gauss(
                    val, self._mt102_gauss_green, self._mt102_gauss_amber
                )
            else:
                lcd.display("---")
                color = _MEAS_LCD_NO_DATA
            lcd.setStyleSheet(
                "background-color: %s; color: %s;" % (MT102_LCD_BG, color)
            )
        te = self._win.findChild(QTextEdit, "textEdit_MT102_Data")
        if not te and hasattr(self._win, "centralWidget"):
            cw = self._win.centralWidget()
            if cw:
                te = cw.findChild(QTextEdit, "textEdit_MT102_Data")
        if te:
            txt = te.toPlainText()
            wide = self._debug_level == _MT102_TRACE_DEBUG_MIN
            hdr = (
                "coilVx  coilVy  coilVz   RAW_X   RAW_Y   RAW_Z      G_X      G_Y      G_Z\n"
                if wide
                else "RAW          X        Y        Z\n"
            )
            if not txt.strip() or txt.strip().startswith("RX:"):
                te.setPlainText(hdr)
            lines = te.toPlainText().splitlines()
            if len(lines) >= MT102_DATA_MONITOR_MAX_LINES:
                cur = te.textCursor()
                cur.beginEditBlock()
                cur.movePosition(QTextCursor.MoveOperation.Start)
                if lines and ("RAW" in lines[0] or "coilVx" in lines[0]):
                    cur.movePosition(QTextCursor.MoveOperation.NextBlock)
                cur.movePosition(
                    QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor
                )
                cur.removeSelectedText()
                cur.endEditBlock()
            if wide:
                vx, vy, vz = self._coil_v_xyz_from_last_tm()

                def _cell_coil_v(v: float | None) -> str:
                    return "%7.3f" % v if v is not None else "%7s" % "-"

                if have_g:
                    line = "%s %s %s %7d %7d %7d %8.4f %8.4f %8.4f\n" % (
                        _cell_coil_v(vx),
                        _cell_coil_v(vy),
                        _cell_coil_v(vz),
                        mag.x,
                        mag.y,
                        mag.z,
                        gx,
                        gy,
                        gz,
                    )
                else:
                    line = (
                        "%s %s %s %7d %7d %7d %8s %8s %8s\n"
                        % (
                            _cell_coil_v(vx),
                            _cell_coil_v(vy),
                            _cell_coil_v(vz),
                            mag.x,
                            mag.y,
                            mag.z,
                            "---",
                            "---",
                            "---",
                        )
                    )
            else:
                raw_hex = "0x%04X" % (mag.x & 0xFFFF)
                if have_g:
                    line = "%-10s %8.3f %8.3f %8.3f\n" % (raw_hex, gx, gy, gz)
                else:
                    line = "%-10s %8s %8s %8s\n" % (raw_hex, "---", "---", "---")
            cur = te.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            te.setTextCursor(cur)
            te.insertPlainText(line)
            sb = te.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        decl = float(self._mag_declination_deg)
        # 3D pose uses the same factory F-cal B vector as the Gauss LCDs (never raw counts).
        vd = getattr(self, "_viewer3d", None)
        if have_g:
            rx, ry, rz = self._field_vector_to_rotation(gx, gy, gz, decl)
            if vd is not None and hasattr(vd, "set_rotation_immediate"):
                try:
                    vd.set_rotation_immediate(rx, ry, rz)
                except Exception:
                    pass
            for lcd_name, deg in (
                ("lcdNumber_Mt102_X", ry),
                ("lcdNumber_MT102_Y", rx),
                ("lcdNumber_MT102_Z", rz),
            ):
                lcd = self._find_lcd_number(self._win, lcd_name)
                if lcd:
                    lcd.setDigitCount(7)
                    lcd.setMode(QLCDNumber.Mode.Dec)
                    lcd.display("%.1f" % deg)
        else:
            for lcd_name in (
                "lcdNumber_Mt102_X",
                "lcdNumber_MT102_Y",
                "lcdNumber_MT102_Z",
            ):
                lcd = self._find_lcd_number(self._win, lcd_name)
                if lcd:
                    lcd.setDigitCount(7)
                    lcd.setMode(QLCDNumber.Mode.Dec)
                    lcd.display("---")
        _finish_axis_gauss()
        self._refresh_mt102_fcal_applied_led()

    def _install_viewer3d(self) -> None:
        """Embed PyVista viewer in frame_3DModelView after the main window is shown."""
        if getattr(self, "_viewer3d", None) is not None:
            return
        frame_3d = self._win.findChild(QFrame, "frame_3DModelView")
        if frame_3d is None:
            return
        if Viewer3D is None:
            layout = frame_3d.layout()
            if layout is None:
                layout = QVBoxLayout(frame_3d)
            layout.addWidget(
                QLabel(
                    "3D viewer requires pyvista and pyvistaqt.\n"
                    "Install: pip install pyvista pyvistaqt"
                )
            )
            return
        frame_3d.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        frame_3d.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, False)
        layout = frame_3d.layout()
        if layout is None:
            layout = QVBoxLayout(frame_3d)
        layout.setContentsMargins(0, 0, 0, 0)
        self._viewer3d = Viewer3D(frame_3d)
        layout.addWidget(self._viewer3d)
        self._viewer3d.set_rotation(0, 0, 0)

    def _set_connected_ui(self, connected: bool) -> None:
        if connected:
            self._btn_connect.setText("Disconnect all")
            self._refresh_connection_status_line()
            self._combo_port.setEnabled(False)
            self._combo_baud.setEnabled(False)
        else:
            self._btn_connect.setText("Connect all")
            self._status_conn.setText("Connection: Disconnected")
            self._combo_port.setEnabled(True)
            self._combo_baud.setEnabled(True)
        self._update_status_leds()

    def _set_pico_path_widgets_enabled(self, enabled: bool) -> None:
        """External Drive bench mode: disable Pico COM, coil-related controls, SAFE/Reset."""
        if self._combo_port is not None:
            self._combo_port.setEnabled(enabled)
        if self._combo_baud is not None:
            self._combo_baud.setEnabled(enabled)
        if self._btn_connect is not None:
            self._btn_connect.setEnabled(enabled)
        if self._btn_safe is not None:
            self._btn_safe.setEnabled(enabled)
        if getattr(self, "_btn_reset", None) is not None:
            self._btn_reset.setEnabled(enabled)
        for _ax, sp, pb, _lcd, chk in self._axis_rows:
            if sp is not None:
                sp.setEnabled(enabled)
            if pb is not None:
                pb.setEnabled(enabled)
            if chk is not None:
                chk.setEnabled(enabled)

    def _connect_external_drive_sensors(self) -> None:
        """Open MT-102 then Wit901; no Pico. Caller starts `_serial_timer` for `_mag_poll`."""
        self._disconnect_wit901_only()
        self._disconnect_mt102_only()
        self._connect_mt102_after_pico()
        if getattr(self, "_mt102", None) is None:
            self._set_status("External Drive: MT-102 did not open — check ini [serial] ports.")
            return
        self._connect_wit901_if_configured()

    def _stop_external_drive_mode(self) -> None:
        """Disconnect sensors, stop mag poll timer, re-enable Pico widgets."""
        self._external_drive_active = False
        self._close_external_drive_xlsx()
        self._disconnect_wit901_only()
        self._disconnect_mt102_only()
        try:
            self._serial_timer.stop()
        except Exception:
            pass
        self._set_pico_path_widgets_enabled(True)
        self._status_conn.setText("Connection: Disconnected")
        self._set_status("External Drive off — use Connect All for Pico.")

    def _on_external_drive_toggled(self, checked: bool) -> None:
        if self._chk_external_drive is None:
            return
        if checked:
            if self._serial is not None:
                self._disconnect()
            self._set_pico_path_widgets_enabled(False)
            self._external_drive_active = True
            self._connect_external_drive_sensors()
            if getattr(self, "_mt102", None) is None:
                self._external_drive_active = False
                self._set_pico_path_widgets_enabled(True)
                self._chk_external_drive.blockSignals(True)
                self._chk_external_drive.setChecked(False)
                self._chk_external_drive.blockSignals(False)
                QMessageBox.warning(
                    self._win,
                    "External Drive",
                    "MT-102 did not connect. Check [serial] rs422_port / rs232_port / baud_rate in CalibratorUI.ini.",
                )
                return
            try:
                self._serial_timer.start()
            except Exception:
                pass
            self._populate_gauss_source_combo()
            self._status_conn.setText(
                "Connection: External drive (MT-102 + Wit901, no Pico)"
            )
            self._set_status(
                "External Drive: sensors live; logging to ExternalDrive.xlsx (openpyxl)."
            )
        else:
            self._stop_external_drive_mode()

    def _on_connect_clicked(self) -> None:
        if self._external_drive_active:
            return
        if self._serial is not None:
            self._disconnect()
            return
        self._connect()

    def _connect(self) -> None:
        if self._external_drive_active:
            return
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
        self._tm_dbg_first_tm_after_connect = self._debug_level == _TM_CSV_DEBUG_MIN
        self._tm_dbg_setx_absent_x_present_pending = self._debug_level == _TM_CSV_DEBUG_MIN
        self._last_tm_kv = None
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
        if self._text_out is not None:
            self._append_pico_log_line(
                "[CalibratorUI] This log shows Pico TXT:: only; TM:: carries DROK-measured coil mA / V to the current and volts LCDs. "
                "If LCDs stay ---, try soft_reset_on_connect=1 in CalibratorUI.ini [serial] or power-cycle the Pico / verify COM."
            )
        QTimer.singleShot(0, self._connect_rx_pump_slice)
        QTimer.singleShot(100, self._send_axis_enables_to_pico)
        # Boot TXT:: is emitted once at Pico start; if we did not soft-reset, that stream was missed.
        if not self._soft_reset_on_connect_pref():
            QTimer.singleShot(280, self._request_hw_report_after_connect)
        self._connect_mt102_after_pico()
        self._connect_wit901_if_configured()
        self._populate_gauss_source_combo()

    def _send_axis_enables_to_pico(self) -> None:
        """After connect: send enable_x/y/z 1 for all axes (serial connection implies enabled)."""
        if self._serial is None:
            return
        try:
            parts = b"".join(
                f"enable_{ax.lower()} {1 if self._coils_axis_enabled(ax) else 0}\r\n".encode(
                    "ascii", errors="replace"
                )
                for ax in ("X", "Y", "Z")
            )
            self._serial.write(parts)
            self._serial.flush()
            self._dbg(1, "connect: sent", "enable_x/y/z 1 (connected)")
        except Exception as e:
            self._dbg(1, "connect: enable send failed:", e)

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
        self._disconnect_wit901_only()
        self._disconnect_mt102_only()
        self._connect_rx_pump_slices = 0
        self._connect_mono_ts = None
        self._last_alive_reply_ts = None
        self._serial_saw_tm_txt_this_link = False
        self._pico_alive_stale = False
        self._keepalive_stale_dbg_done = False
        self._tm_dbg_first_tm_after_connect = False
        self._tm_dbg_setx_absent_x_present_pending = False
        self._last_tm_kv = None
        self._close_mag_test_xlsx()
        self._close_external_drive_xlsx()
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
        self._reset_gauss_source_combo_for_disconnect()
        self._reset_cc_coil_leds_disconnected()
        self._reset_measured_lcds_no_data()

    def shutdown(self) -> None:
        """App exit: `_disconnect` already persists serial keys to ini."""
        self._disconnect()


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
    QTimer.singleShot(0, ctrl._install_viewer3d)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
