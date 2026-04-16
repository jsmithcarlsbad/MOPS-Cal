# SPDX-License-Identifier: MIT
# Copyright (c) 2025 jsmith.carlsbad@gmail.com (XDM1041-GUI); adapted here for headless use.
#
# Upstream GUI + protocol: https://github.com/jsmithcarlsbad/XDM1041-GUI
# This file copies only the SCPI transport + mode table + numeric parsing needed for scripts.
# Do not push CoilDriver-specific edits to the upstream repository.

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

import serial

# Primary display reading (OWON XDM family) — same as upstream ``SCPI_READ_PRIMARY``.
SCPI_READ_PRIMARY = "MEAS1?"


@dataclass(frozen=True)
class _MeasurementMode:
    id: str
    configure_cmd: str


# CONFigure:* commands per OWON XDM family — same list as upstream ``XDM_MEASUREMENT_MODES``.
_MEASUREMENT_MODES: tuple[_MeasurementMode, ...] = (
    _MeasurementMode("dc_volts", "CONFigure:VOLT:DC"),
    _MeasurementMode("ac_volts", "CONFigure:VOLT:AC"),
    _MeasurementMode("ohms", "CONFigure:RES"),
    _MeasurementMode("dc_current", "CONFigure:CURR:DC"),
    _MeasurementMode("ac_current", "CONFigure:CURR:AC"),
    _MeasurementMode("frequency", "CONFigure:FREQ"),
    _MeasurementMode("capacitance", "CONFigure:CAP"),
    _MeasurementMode("diode", "CONFigure:DIOD"),
    _MeasurementMode("continuity", "CONFigure:CONT"),
    _MeasurementMode("temperature", "CONFigure:TEMP"),
)

_MODE_BY_ID: dict[str, _MeasurementMode] = {m.id: m for m in _MEASUREMENT_MODES}
MEASUREMENT_MODE_IDS: tuple[str, ...] = tuple(m.id for m in _MEASUREMENT_MODES)


@dataclass(frozen=True)
class _SampleRate:
    id: str
    rate_cmd: str


_SAMPLE_RATES: tuple[_SampleRate, ...] = (
    _SampleRate("fast", "RATE F"),
    _SampleRate("medium", "RATE M"),
    _SampleRate("slow", "RATE S"),
)
_RATE_BY_ID: dict[str, _SampleRate] = {r.id: r for r in _SAMPLE_RATES}


def _normalize_scpi_numeric_token(s: str) -> str:
    t = (s or "").strip()
    if not t:
        return ""
    t = re.sub(r"[\u03a9\u2126]", "", t)
    t = re.sub(r"(?i)\s*(ohm|ohms)\s*$", "", t).strip()
    t = re.sub(r"\s+", "", t)
    if not t:
        return ""
    tl = t.lower()
    eloc = tl.find("e")
    if eloc >= 0:
        mant, exp_part = t[:eloc], t[eloc:]
    else:
        mant, exp_part = t, ""
    if "," in mant and "." not in mant and mant.count(",") == 1:
        mant = mant.replace(",", ".")
    else:
        mant = mant.replace(",", "")
    return mant + exp_part


def parse_measurement_float(s: str) -> Optional[float]:
    """Parse meter text like ``1E 9``, ``+2.005E+03 OHM`` after normalization (upstream-style)."""
    compact = _normalize_scpi_numeric_token(s)
    if not compact:
        return None
    compact = compact.replace("D", "E").replace("d", "e")
    try:
        return float(compact.replace("E", "e"))
    except ValueError:
        pass
    m = re.search(r"[+-]?(?:\d+\.\d+|\d+)(?:[eE][+-]?\d+)?", compact)
    if not m:
        return None
    try:
        return float(m.group(0).replace("E", "e"))
    except ValueError:
        return None


LogFn = Callable[[str, str], None]


def _scpi_read_line(ser: serial.Serial, *, log: LogFn | None = None) -> str:
    buf = bytearray()
    while True:
        chunk = ser.read(64)
        if not chunk:
            raise serial.SerialTimeoutException("Timeout waiting for meter response")
        buf.extend(chunk)
        if len(buf) >= 2 and buf[-2:] == b"\r\n":
            break
        if len(buf) > 4096:
            raise serial.SerialException("Response too long or malformed")
    line = buf.decode("ascii", errors="replace").strip()
    if log:
        log("<<", line)
    return line


def _scpi_write_line(ser: serial.Serial, cmd: str, *, log: LogFn | None = None) -> None:
    payload = cmd.strip() + "\n"
    if log:
        log(">>", payload.rstrip("\n"))
    ser.write(payload.encode("ascii", errors="replace"))


def _drain_scpi_lines(ser: serial.Serial, *, log: LogFn | None = None, max_lines: int = 8) -> None:
    saved_timeout = ser.timeout
    ser.timeout = 0.05
    try:
        for _ in range(max_lines):
            raw = ser.readline()
            if not raw:
                break
            line = raw.decode("ascii", errors="replace").strip()
            if line and log:
                log("<<", line)
    finally:
        ser.timeout = saved_timeout


def _scpi_query(ser: serial.Serial, cmd: str, *, log: LogFn | None = None) -> str:
    payload = cmd.strip() + "\n"
    if log:
        log(">>", payload.rstrip("\n"))
    ser.write(payload.encode("ascii", errors="replace"))
    return _scpi_read_line(ser, log=log)


class XDM1041:
    """Blocking SCPI client for one OWON XDM1041 on a serial port (no Qt)."""

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        timeout: float = 2.0,
        debug_serial: bool = False,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._debug_serial = debug_serial
        self._ser: serial.Serial | None = None
        self._idn: str | None = None
        self._active_mode_id: str | None = None
        self._active_rate_id: str | None = None

    def _log(self, direction: str, payload: str) -> None:
        if self._debug_serial:
            print(f"[XDM1041 serial] {direction} {payload!r}", flush=True)

    def _serial_log(self) -> LogFn | None:
        if not self._debug_serial:
            return None

        def _fn(direction: str, payload: str) -> None:
            self._log(direction, payload)

        return _fn

    def open(self) -> str:
        """Open the port and return ``*IDN?`` response."""
        if self._ser is not None and self._ser.is_open:
            raise RuntimeError("Already open")
        self._ser = serial.Serial(
            port=self._port,
            baudrate=int(self._baudrate),
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=float(self._timeout),
        )
        log = self._serial_log()
        try:
            self._idn = _scpi_query(self._ser, "*IDN?", log=log)
            return self._idn
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self._ser is not None:
            try:
                if self._ser.is_open:
                    self._ser.close()
            except OSError:
                pass
            self._ser = None
        self._idn = None
        self._active_mode_id = None
        self._active_rate_id = None

    def __enter__(self) -> "XDM1041":
        self.open()  # *IDN? during bring-up; ignore return or call ``query("*IDN?")`` again if desired
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def idn(self) -> str:
        """Last ``*IDN?`` from ``open()``."""
        if not self._idn:
            raise RuntimeError("Not connected")
        return self._idn

    @property
    def ser(self) -> serial.Serial:
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("Serial port is not open")
        return self._ser

    def query(self, cmd: str) -> str:
        return _scpi_query(self.ser, cmd, log=self._serial_log())

    def write_line(self, cmd: str) -> None:
        _scpi_write_line(self.ser, cmd, log=self._serial_log())
        _drain_scpi_lines(self.ser, log=self._serial_log())

    def set_auto_range(self) -> None:
        """Instrument auto-range (matches remote-open behaviour in upstream GUI)."""
        self.write_line("AUTO")

    def set_sample_rate(self, rate_id: str) -> None:
        r = _RATE_BY_ID.get(rate_id)
        if r is None:
            raise ValueError(f"Unknown sample rate id {rate_id!r}; use {tuple(_RATE_BY_ID)}")
        if self._active_rate_id != rate_id:
            self.write_line(r.rate_cmd)
            self._active_rate_id = rate_id

    def configure_mode(self, mode_id: str) -> None:
        m = _MODE_BY_ID.get(mode_id)
        if m is None:
            raise ValueError(f"Unknown mode id {mode_id!r}; use {MEASUREMENT_MODE_IDS}")
        if self._active_mode_id != mode_id:
            self.write_line(m.configure_cmd)
            self._active_mode_id = mode_id

    def read_primary_raw(self) -> str:
        return _scpi_query(self.ser, SCPI_READ_PRIMARY, log=self._serial_log())

    def read_primary_float(self) -> Optional[float]:
        return parse_measurement_float(self.read_primary_raw())
