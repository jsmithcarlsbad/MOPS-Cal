"""
mt102_interface.py — Threaded MT-102 magnetometer serial interface.

Wire format matches MSP430 `main.c` / `serial.c` (see ``C:\\MT102\\MSP430 code\\src``).

**Sensor / ``M`` packet semantics** (HMC1053 + MSP430): documented in
``C:\\MT102\\MSP430 code\\HMC1053_INTERFACE_ANALYSIS.md``. The three integers after ``M``
are ``Val_X``, ``Val_Y``, ``Val_Z``: **differential SD16 readings** (current minus
previous mid-scale-centered sample), with **Set/Reset phase** optionally inverting them.
They are **not** “Gauss” or “nT” on the wire.

**F-cal + corrected field:** match Sandel ``C:\\MT102\\MagCal\\win_src\\MagnetometerParser.cpp``
(case ``'M'``): offsets plus soft-iron with ``MAG_SF_UC`` only **inside** those terms; the
parser stores **Int16** corrected counts (no extra ``× MAG_SF_UC`` on the result). Host
code uses the same math; **Gauss for display** = corrected counts ``×`` ``mag_raw_to_gauss``
from CalibratorUI.ini (tune against a traceable Gaussmeter).

- **M (broadcast):** ``M`` + ``Val_X`` + ``Val_Y`` + ``Val_Z`` (``serial_tx_integer`` = 4
  nibbles each) + ``system_status`` (``serial_txhex``, 2 nibbles) + checksum (2 nibbles)
  + ``\\r\\n``. Total 17 bytes before CRLF. Nibbles 10–15 are ``:``–``?`` (``+'0'`` in C),
  not ``A``–``F``. Checksum = sum of all preceding TX characters ``& 0xFF`` (see
  ``serial_txch`` / ``serial_tx_eom``).

- **F (after QUE):** ``F`` + ``serial_txhex(FLASH_SIZE)`` (2 nibbles) + ``384`` data
  nibbles (192 bytes ``flash_mem``) + checksum + ``\\r\\n`` → length **389** before CRLF.

Uses a worker thread for non-blocking reads. ``QUE`` triggers ``Q`` + version + ``F`` flash.
"""

import datetime
import math
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

try:
    import serial
except ImportError:
    serial = None  # type: ignore

# MagnetometerParser.cpp — only scales soft-iron cross terms, not the final vector.
MAG_SF_UC = 0.01

# Flash layout: 9 scale factors (×12 chars), 3 offsets (×12), serial (×12), ...
MAG_FLASH_BYTES = 192
# main.c: FLASH_SIZE = 192 → F + 2 (size nibbles) + 384 (data) + 2 (checksum) before CRLF
_F_LINE_LEN = 1 + 2 + MAG_FLASH_BYTES * 2 + 2
# main.c broadcast: M + 4+4+4 (XYZ) + 2 (system_status) + 2 (checksum) before CRLF
_M_LINE_LEN = 1 + 12 + 2 + 2


def calc_checksum(data: str) -> str:
    """MT-102 checksum: sum of bytes & 0xFF, as 2 ASCII chars (nibbles 10–15 → ':'–'?')."""
    chk = sum(ord(c) for c in data) & 0xFF
    return chr((chk >> 4) + 48) + chr((chk & 0xF) + 48)


def prep_send(data: str) -> bytes:
    """Format command for MT-102: data + checksum + \\r\\n."""
    return (data + calc_checksum(data) + "\r\n").encode("ascii")


def _i16(n: int) -> int:
    """Wrap to 16-bit signed (same range as MSP430 ``serial_tx_integer`` / MagCal Int16)."""
    n = int(n) & 0xFFFF
    if n >= 0x8000:
        n -= 0x10000
    return n


def _trunc_to_i16(v: float) -> float:
    """Truncate toward zero to Int16, matching MSVC-style assignment in MagnetometerParser."""
    n = int(math.trunc(v))
    return float(max(-32768, min(32767, n)))


@dataclass
class MagData:
    """M-packet ``Val_X/Y/Z``: differential demagged SD16 counts (see HMC1053_INTERFACE_ANALYSIS.md)."""

    x: int
    y: int
    z: int
    # From main.c after serial_txhex(system_status); serial.h STATUS_RX_ENA = 0x01 (bit 0).
    system_status: int = 0


@dataclass
class FlashCalData:
    """
    Calibration data from MT-102 flash (F packet).
    Layout per MAGCAL importFactoryCalData_: 9 scale factors /1000, 3 offsets, serial.
    """

    offsets: tuple[int, int, int] = (0, 0, 0)  # X, Y, Z
    scale_matrix: tuple[tuple[float, float, float], ...] = field(
        default_factory=lambda: ((10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0))
    )  # XX,XY,XZ / YX,YY,YZ / ZX,ZY,ZZ
    serial_number: str = ""

    def fcal_corrected_counts(self, mag: MagData) -> tuple[float, float, float]:
        """
        Factory F-cal corrected ``M`` vector in **MagnetometerParser** Int16 domain
        (counts, not Gauss). Matches ``MagnetometerParser.cpp`` ``case 'M':`` math.
        """
        ox, oy, oz = self.offsets
        x = _i16(int(mag.x) + int(ox))
        y = _i16(int(mag.y) + int(oy))
        z = _i16(int(mag.z) + int(oz))
        s = self.scale_matrix
        fp = MAG_SF_UC
        gx = float(x) - (
            s[0][0] * fp * x + s[0][1] * fp * y + s[0][2] * fp * z
        )
        gy = float(y) - (
            s[1][0] * fp * x + s[1][1] * fp * y + s[1][2] * fp * z
        )
        gz = float(z) - (
            s[2][0] * fp * x + s[2][1] * fp * y + s[2][2] * fp * z
        )
        return (_trunc_to_i16(gx), _trunc_to_i16(gy), _trunc_to_i16(gz))

    def raw_to_gauss(self, mag: MagData, gauss_per_count: float) -> tuple[float, float, float]:
        """
        ``fcal_corrected_counts`` × ``gauss_per_count`` (from ini). Tune ``mag_raw_to_gauss``
        against a traceable Gaussmeter at your bench pose.
        """
        cx, cy, cz = self.fcal_corrected_counts(mag)
        k = float(gauss_per_count)
        return (cx * k, cy * k, cz * k)


def _parse_4char_field(s4: str) -> int:
    """One 4-character field: standard hex, or MT102 nibble encoding (0-9 and :;...?)."""
    if len(s4) != 4:
        return 0
    bs = s4.encode("ascii")
    try:
        v = int(s4, 16)
    except ValueError:
        v = _four_nibbles_to_s16(bs)
    if v >= 0x8000:
        v -= 0x10000
    return v


def _get_next_int_value(data: str, index: int) -> tuple[int, int]:
    """
    Read triple-redundant value (3 × 4 hex chars). Return (value, next_index).
    Per MAGCAL GetNextIntValue_: take consensus of 3 stored values.
    """
    if index + 12 > len(data):
        return (0, index + 12)
    try:
        v1 = _parse_4char_field(data[index : index + 4])
        v2 = _parse_4char_field(data[index + 4 : index + 8])
        v3 = _parse_4char_field(data[index + 8 : index + 12])
    except (ValueError, IndexError):
        return (0, index + 12)
    if v1 == v2 == v3:
        return (v1, index + 12)
    if v1 == v2 or v1 == v3:
        return (v1, index + 12)
    if v2 == v3:
        return (v2, index + 12)
    return (0, index + 12)


def _parse_f_packet(data: str) -> FlashCalData | None:
    """
    Parse F packet payload (after F + 2-char size). Data = 384 hex chars (192 bytes).
    Returns FlashCalData or None if invalid.
    """
    if len(data) < 384:
        return None
    idx = 0
    scales: list[float] = []
    for _ in range(9):
        val, idx = _get_next_int_value(data, idx)
        scales.append(val / 1000.0)
    offsets_list: list[int] = []
    for _ in range(3):
        val, idx = _get_next_int_value(data, idx)
        offsets_list.append(val)
    sn_val, _ = _get_next_int_value(data, idx)
    matrix = (
        (scales[0], scales[1], scales[2]),
        (scales[3], scales[4], scales[5]),
        (scales[6], scales[7], scales[8]),
    )
    return FlashCalData(
        offsets=tuple(offsets_list),
        scale_matrix=matrix,
        serial_number=str(sn_val & 0xFFFF),
    )


# M packet: M + 12 nibbles XYZ + 2 nibbles system_status + 2 nibbles checksum + \r\n
# MT-102 uses :;<=>? for nibbles 10-15 (serial_txhex: nibble + '0' in C).
_M_PATTERN = re.compile(rb"^M([0-9A-Fa-f:;<=>?]{4})([0-9A-Fa-f:;<=>?]{4})([0-9A-Fa-f:;<=>?]{4})")


def _is_mt102_nibble_byte(c: int) -> bool:
    """True if c is a valid MT-102 wire nibble character (0-9 or : through ?)."""
    return (ord("0") <= c <= ord("9")) or (ord(":") <= c <= ord("?"))


def _nibble_to_hex(c: int) -> int:
    """Convert MT-102 nibble char (0-9 or :;<=>?) to 0-15."""
    if ord("0") <= c <= ord("9"):
        return c - ord("0")
    if ord(":") <= c <= ord("?"):
        return c - ord(":") + 10
    return 0


def _four_nibbles_to_s16(b: bytes) -> int:
    """Convert 4 MT-102 nibble chars to 16-bit signed."""
    if len(b) < 4:
        return 0
    val = (_nibble_to_hex(b[0]) << 12) | (_nibble_to_hex(b[1]) << 8) | (_nibble_to_hex(b[2]) << 4) | _nibble_to_hex(b[3])
    if val >= 0x8000:
        val -= 0x10000
    return val


def _mt102_checksum_byte(two: bytes) -> int | None:
    """Last two MT-102 nibble chars -> 8-bit checksum value. None if invalid."""
    if len(two) != 2:
        return None
    if not _is_mt102_nibble_byte(two[0]) or not _is_mt102_nibble_byte(two[1]):
        return None
    hi = _nibble_to_hex(two[0])
    lo = _nibble_to_hex(two[1])
    return (hi << 4) | lo


def _validate_packet(line: bytes) -> bool:
    """Validate MT-102 line checksum: last 2 chars are nibbles (0-9 or :;...?), not only hex digits."""
    if len(line) < 3:
        return False
    try:
        body = line[:-2].decode("ascii")
        got = _mt102_checksum_byte(line[-2:])
        if got is None:
            return False
        calc = sum(ord(c) for c in body) & 0xFF
        return calc == got
    except (ValueError, UnicodeDecodeError):
        return False


def _parse_m_packet(line: bytes) -> MagData | None:
    """
    Parse M broadcast line (without \\r\\n), per main.c: ``M`` + XYZ + ``system_status`` + chk.
    Exact length ``_M_LINE_LEN`` (17) and checksum required.
    """
    if len(line) != _M_LINE_LEN or not _validate_packet(line):
        return None
    m = _M_PATTERN.match(line)
    if not m:
        return None
    try:
        x = _four_nibbles_to_s16(m.group(1))
        y = _four_nibbles_to_s16(m.group(2))
        z = _four_nibbles_to_s16(m.group(3))
        st = (_nibble_to_hex(line[13]) << 4) | _nibble_to_hex(line[14])
        return MagData(x=x, y=y, z=z, system_status=st)
    except (ValueError, IndexError):
        return None


class MT102Interface:
    """
    Threaded MT-102 interface. Connects via serial (or serial_factory for mocks),
    parses M packets in a worker thread, and exposes get_mag_data() for the UI.
    """

    def __init__(
        self,
        on_error: Callable[[str], None] | None = None,
        serial_factory: Callable[[str, int], object] | None = None,
    ):
        self._on_error = on_error or (lambda _: None)
        self._serial_factory = serial_factory
        self._serial: object | None = None
        self._serial_tx: object | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest: MagData | None = None
        self._cal_data: FlashCalData | None = None
        #: ASCII hex payload (384 chars) from last parsed ``F`` line — for ``F_BLOCK_CAPTURE.md``.
        self._f_payload_hex: str | None = None
        # Diagnostic counters for troubleshooting "no data"
        self._bytes_received = 0
        self._m_packets_parsed = 0
        self._f_packets_parsed = 0
        self._last_raw: bytes = b""

    def connect(self, port: str, baud: int = 9600, port_tx: str | None = None) -> bool:
        """Open serial. If port_tx is set, use port for RX (RS-422) and port_tx for TX (RS-232)."""
        if serial is None and self._serial_factory is None:
            self._on_error("pyserial not installed")
            return False
        try:
            if self._serial_factory:
                self._serial = self._serial_factory(port, baud)
                self._serial_tx = None
            else:
                self._serial = serial.Serial(port=port, baudrate=baud, timeout=0.1)
                self._serial_tx = serial.Serial(port=port_tx, baudrate=baud, timeout=0.1) if port_tx and port_tx != port else None
            self._stop.clear()
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()
            # Let the reader thread enter its loop before the first QUE (improves F-cal capture).
            time.sleep(0.05)
            # Send QUE to wake MT-102 (use TX port for commands)
            ser_tx = self._serial_tx if self._serial_tx is not None else self._serial
            if hasattr(ser_tx, "write"):
                ser_tx.write(prep_send("QUE"))
            return True
        except Exception as e:
            self._on_error(str(e))
            self._serial = None
            self._serial_tx = None
            return False

    def disconnect(self) -> None:
        """Stop worker and close serial."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        for ser in (self._serial, self._serial_tx):
            if ser and hasattr(ser, "close"):
                try:
                    ser.close()
                except Exception:
                    pass
        self._serial = None
        self._serial_tx = None
        with self._lock:
            self._latest = None
            self._cal_data = None
            self._f_payload_hex = None
        self._bytes_received = 0
        self._m_packets_parsed = 0
        self._f_packets_parsed = 0
        self._last_raw = b""

    def get_debug_info(self) -> dict:
        """Return diagnostic counters for troubleshooting no-data issues."""
        with self._lock:
            return {
                "bytes_received": self._bytes_received,
                "m_packets_parsed": self._m_packets_parsed,
                "f_packets_parsed": self._f_packets_parsed,
                "last_raw": self._last_raw[-128:] if self._last_raw else b"",
            }

    def get_cal_data(self) -> FlashCalData | None:
        """Return calibration from last F packet (after QUE). None if not yet received."""
        with self._lock:
            return self._cal_data

    def build_f_block_capture_markdown(self) -> str | None:
        """Markdown documenting the last captured F payload + parsed matrix/offsets (host bench artifact)."""
        with self._lock:
            cal = self._cal_data
            payload = self._f_payload_hex
            n_f = self._f_packets_parsed
        if cal is None or payload is None or len(payload) < 384:
            return None
        s = cal.scale_matrix
        ox, oy, oz = cal.offsets
        yx, yy, yz_ = s[1][0], s[1][1], s[1][2]
        cross_y = abs(yx) + abs(yz_)
        lines = [
            "# MT-102 F-block capture",
            "",
            "Parsed from the last valid `F` line after `QUE` (factory flash cal). "
            "See `mt102_interface.FlashCalData` / `MagnetometerParser.cpp` case `'M'`.",
            "",
            f"- **Captured (host local time):** {datetime.datetime.now().isoformat(timespec='seconds')}",
            f"- **F packets parsed (this session):** {n_f}",
            f"- **Serial (from F block):** {cal.serial_number}",
            "",
            "## Offsets (added to raw M counts as Int16 before soft-iron subtraction)",
            "",
            "| Axis | Value |",
            "|------|-------|",
            f"| X | {ox} |",
            f"| Y | {oy} |",
            f"| Z | {oz} |",
            "",
            "## Soft-iron matrix (stored /1000 in flash; used as below with `MAG_SF_UC = 0.01`)",
            "",
            "Corrected Int16 counts: each axis subtracts `0.01 * (row · [x,y,z])` using **offset** x,y,z.",
            "",
            "| | col (× x) | col (× y) | col (× z) |",
            "|---|-------------|-------------|-------------|",
            f"| **X row** | {s[0][0]:.6g} | {s[0][1]:.6g} | {s[0][2]:.6g} |",
            f"| **Y row** | {yx:.6g} | {yy:.6g} | {yz_:.6g} |",
            f"| **Z row** | {s[2][0]:.6g} | {s[2][1]:.6g} | {s[2][2]:.6g} |",
            "",
            "### Hint for “Y looks wrong” vs X/Z",
            "",
            f"- **|YX| + |YZ|** (cross terms into the Y correction) **= {cross_y:.6g}**; **|YY|** **= {abs(yy):.6g}**.",
            "- If cross terms are large vs `YY`, factory soft-iron is **mixing X/Z into Y**; with legacy axis routing that can show up as odd **Y Gauss** sign/magnitude vs the other channels.",
            "",
            "## Raw F payload (384 ASCII hex chars = 192 bytes mag-cal prefix)",
            "",
            "```text",
        ]
        for i in range(0, 384, 64):
            lines.append(payload[i : i + 64])
        lines.extend(["```", ""])
        return "\n".join(lines)

    def request_cal_data(self) -> bool:
        """Send QUE to request Q+F response. Cal data parsed from F packet."""
        return self.send_command("QUE")

    def is_connected(self) -> bool:
        """True if serial is open."""
        if self._serial is None:
            return False
        if hasattr(self._serial, "is_open"):
            return bool(self._serial.is_open)
        return True

    def get_mag_data(self, timeout: float = 0) -> MagData | None:
        """Return latest M packet data, or None if none available."""
        with self._lock:
            return self._latest

    def send_command(self, cmd: str) -> bool:
        """Send command to MT-102 (uses TX port for dual-port mode)."""
        ser = self._serial_tx if self._serial_tx is not None else self._serial
        if ser is None or not hasattr(ser, "write"):
            return False
        try:
            ser.write(prep_send(cmd))
            return True
        except Exception:
            return False

    def _worker(self) -> None:
        """Read serial, parse M packets, update _latest."""
        buf = bytearray()
        while not self._stop.is_set() and self._serial:
            try:
                if hasattr(self._serial, "in_waiting") and self._serial.in_waiting > 0:
                    chunk = self._serial.read(256)
                    if chunk:
                        self._bytes_received += len(chunk)
                        with self._lock:
                            self._last_raw = bytes(chunk)
                        buf.extend(chunk)
                else:
                    self._stop.wait(0.02)
            except Exception as e:
                self._on_error(str(e))
                break
            # Parse lines
            while b"\r" in buf or b"\n" in buf:
                idx = buf.find(b"\r")
                if idx < 0:
                    idx = buf.find(b"\n")
                if idx < 0:
                    break
                line = bytes(buf[:idx]).strip()
                del buf[: idx + 1]
                if buf and buf[0:1] == b"\n":
                    del buf[0:1]
                if line.startswith(b"M"):
                    mag = _parse_m_packet(line)
                    if mag:
                        self._m_packets_parsed += 1
                        with self._lock:
                            self._latest = mag
                elif (
                    line[:1] in (b"F", b"f")
                    and len(line) == _F_LINE_LEN
                    and _validate_packet(line)
                ):
                    # F + 2 nibbles FLASH_SIZE + 384 data nibbles + 2 nibbles checksum (main.c)
                    try:
                        data = line[3:-2].decode("ascii")
                        if len(data) >= 384:
                            cal = _parse_f_packet(data[:384])
                            if cal:
                                self._f_packets_parsed += 1
                                with self._lock:
                                    self._cal_data = cal
                                    self._f_payload_hex = data[:384]
                    except (ValueError, UnicodeDecodeError):
                        pass
