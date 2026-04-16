#!/usr/bin/env python3
"""
Wit Motion UART: stream magnetometer field as ASCII **X Y Z in Gauss** (one row
per valid 0x54 frame). Status and errors go to **stderr**; **stdout** is only
numeric columns (optional header row) for piping/logging.

Sends Wit unlock / stream-on / return mask (magnetometer) / save unless
``--no-init``. Sends a periodic register read (default 1 s) so the host keeps
requesting data. Requires: ``pip install pyserial``.
"""

from __future__ import annotations

import argparse
import struct
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("PySerial is required: pip install pyserial", file=sys.stderr)
    sys.exit(1)

FRAME_HEAD = 0x55
FRAME_MAG = 0x54
FRAME_LEN = 11

# Wit host → module: FF AA reg dataL dataH
_CMD_UNLOCK = bytes((0xFF, 0xAA, 0x69, 0x88, 0xB5))
_CMD_SAVE = bytes((0xFF, 0xAA, 0x00, 0x00, 0x00))
# RSW 0x02: magnetometer UART packets only (less traffic than full mask)
_RSW_MAG_ONLY = (0x10, 0x00)
_REG_HX = 0x3A

# Wit int16 scale: ±32768 → ±16 µT (per Wit docs). 1 G = 100 µT → Gauss = µT / 100.
_LSB_TO_UT = 16.0 / 32768.0
_UT_TO_GAUSS = 1.0 / 100.0


def lsbs_to_gauss(lsbs: int) -> float:
    return lsbs * _LSB_TO_UT * _UT_TO_GAUSS


def _write_all(ser: serial.Serial, payload: bytes, label: str) -> None:
    off = 0
    while off < len(payload):
        n = ser.write(payload[off:])
        if n is None or n <= 0:
            raise serial.SerialException(f"{label}: write returned {n!r}")
        off += n
    ser.flush()
    ow = getattr(ser, "out_waiting", 0)
    if ow:
        t0 = time.monotonic()
        while getattr(ser, "out_waiting", 0) > 0:
            if time.monotonic() - t0 > 2.0:
                raise serial.SerialException(
                    f"{label}: TX buffer did not drain (out_waiting={getattr(ser, 'out_waiting', 'n/a')})"
                )
            time.sleep(0.01)


def wit_tx(ser: serial.Serial, payload: bytes, pause_s: float = 0.08, *, label: str = "wit") -> None:
    _write_all(ser, payload, label)
    time.sleep(pause_s)


def wit_read_block(ser: serial.Serial, start_reg: int) -> None:
    lo = start_reg & 0xFF
    hi = (start_reg >> 8) & 0xFF
    wit_tx(ser, bytes((0xFF, 0xAA, 0x27, lo, hi)), 0.02, label="read_regs")


def wit_init_stream(ser: serial.Serial, *, flush_rx: bool) -> int:
    """Unlock, UART stream on, magnetometer-only return mask, save. Returns bytes sent."""
    total = 0
    rsw_lo, rsw_hi = _RSW_MAG_ONLY
    steps: tuple[tuple[bytes, float, str], ...] = (
        (_CMD_UNLOCK, 0.15, "unlock"),
        (bytes((0xFF, 0xAA, 0x2D, 0x01, 0x00)), 0.08, "powonsend_on"),
        (bytes((0xFF, 0xAA, 0x02, rsw_lo, rsw_hi)), 0.08, "return_mask"),
        (_CMD_SAVE, 0.2, "save"),
    )
    for cmd, pause, name in steps:
        wit_tx(ser, cmd, pause, label=name)
        total += len(cmd)
    if flush_rx:
        ser.reset_input_buffer()
    return total


def capture_rx_window(ser: serial.Serial, ms: float, *, tick_s: float = 0.012) -> bytes:
    if ms <= 0:
        return b""
    out = bytearray()
    saved_timeout = ser.timeout
    ser.timeout = tick_s
    try:
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end:
            try:
                n = getattr(ser, "in_waiting", 0) or 0
                if n:
                    out.extend(ser.read(min(n, 4096)))
                else:
                    b = ser.read(256)
                    if b:
                        out.extend(b)
            except serial.SerialException:
                ser.timeout = saved_timeout
                raise
            time.sleep(0.003)
    finally:
        ser.timeout = saved_timeout
    return bytes(out)


def read_serial_chunk(ser: serial.Serial, max_block: int = 512) -> bytes:
    parts: list[bytes] = []

    def _drain_pending() -> None:
        for _ in range(256):
            n = getattr(ser, "in_waiting", 0) or 0
            if n <= 0:
                break
            parts.append(ser.read(min(n, max_block)))

    _drain_pending()
    if parts:
        return b"".join(parts)
    first = ser.read(1)
    if not first:
        return b""
    parts.append(first)
    _drain_pending()
    return b"".join(parts)


def checksum_ok(frame: bytes) -> bool:
    return (sum(frame[:10]) & 0xFF) == frame[10]


def parse_mag_frame(frame: bytes) -> tuple[int, int, int]:
    hx, hy, hz = struct.unpack_from("<hhh", frame, 2)
    return hx, hy, hz


def pop_wit_packets(buf: bytearray) -> list[bytes]:
    """Pull valid 11-byte Wit frames from buffer; drop gaps/bad checksums silently."""
    out: list[bytes] = []
    while len(buf) >= FRAME_LEN:
        k = next((i for i in range(len(buf) - FRAME_LEN + 1) if buf[i] == FRAME_HEAD), None)
        if k is None:
            if len(buf) > 4096:
                n = len(buf) - 20
                del buf[:n]
            return out
        if k > 0:
            del buf[:k]
        if len(buf) < FRAME_LEN:
            return out
        frame = bytes(buf[:FRAME_LEN])
        if not checksum_ok(frame):
            del buf[0]
            continue
        del buf[:FRAME_LEN]
        out.append(frame)
    return out


def emit_mag_gauss_rows(buf: bytearray, last_mag: float, warned_no_mag: bool) -> tuple[float, bool]:
    for frame in pop_wit_packets(buf):
        if frame[1] != FRAME_MAG:
            continue
        last_mag = time.monotonic()
        warned_no_mag = False
        hx, hy, hz = parse_mag_frame(frame)
        x, y, z = lsbs_to_gauss(hx), lsbs_to_gauss(hy), lsbs_to_gauss(hz)
        print(f"{x:14.8f}  {y:14.8f}  {z:14.8f}", flush=True)
    return last_mag, warned_no_mag


def _serial_io_fail(port: str, err: Exception) -> None:
    print(f"\nSerial I/O failed on {port}: {err}", file=sys.stderr)
    print(
        "Another program may be using this COM port, or the driver rejected the call.",
        file=sys.stderr,
    )


def _print_com_ports() -> None:
    for info in list_ports.comports():
        print(f"{info.device}\t{info.description}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Stream Wit Motion magnetometer as ASCII X Y Z (Gauss) on stdout.",
    )
    p.add_argument(
        "--list-ports",
        action="store_true",
        help="List COM ports and exit",
    )
    p.add_argument("--port", default="COM10", help="Serial port (default COM10)")
    p.add_argument("--baud", type=int, default=9600, help="Baud rate (default 9600)")
    p.add_argument(
        "--read-timeout",
        type=float,
        default=0.25,
        metavar="SEC",
        help="Serial read timeout in seconds (default 0.25)",
    )
    p.add_argument(
        "--exclusive",
        action="store_true",
        help="Windows: open COM exclusively",
    )
    p.add_argument(
        "--no-init",
        action="store_true",
        help="Do not send Wit setup commands (listen only)",
    )
    p.add_argument(
        "--poll",
        type=float,
        default=1.0,
        metavar="SEC",
        help="Register read every SEC s (0=off). Default 1.0",
    )
    p.add_argument(
        "--dtr-on",
        action="store_true",
        help="Assert DTR after open (some USB-serial boards)",
    )
    p.add_argument(
        "--flush-init-rx",
        action="store_true",
        help="Clear RX buffer after init commands",
    )
    p.add_argument(
        "--no-header",
        action="store_true",
        help="Do not print X Y Z column header on stdout",
    )
    args = p.parse_args()

    if args.list_ports:
        print("Serial ports:", flush=True)
        _print_com_ports()
        return 0

    rx_grace_ms = 750.0
    idle_listen_ms = 0.0

    open_kw: dict = dict(
        port=args.port,
        baudrate=args.baud,
        timeout=args.read_timeout,
        write_timeout=2.0,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )
    if sys.platform == "win32" and args.exclusive:
        open_kw["exclusive"] = True

    try:
        ser = serial.Serial(**open_kw)
    except TypeError:
        open_kw.pop("exclusive", None)
        try:
            ser = serial.Serial(**open_kw)
        except serial.SerialException as e:
            print(f"Could not open {args.port}: {e}", file=sys.stderr)
            return 1
    except serial.SerialException as e:
        print(f"Could not open {args.port}: {e}", file=sys.stderr)
        return 1

    if args.dtr_on:
        try:
            ser.dtr = True
        except (AttributeError, serial.SerialException):
            pass

    with ser:
        print(
            f"Serial open: {args.port} @ {args.baud}  "
            f"stdout=X Y Z Gauss  stderr=status",
            file=sys.stderr,
            flush=True,
        )

        if not args.no_header:
            print("           X_G           Y_G           Z_G", flush=True)

        buf = bytearray()
        last_mag = time.monotonic()
        loop_start = time.monotonic()
        seen_any_rx = False
        warned_no_rx = False
        warned_no_mag = False

        if not args.no_init:
            print("Sending Wit init (magnetometer stream, save)…", file=sys.stderr, flush=True)
            try:
                n_tx = wit_init_stream(ser, flush_rx=args.flush_init_rx)
            except serial.SerialException as e:
                print(f"Init write failed: {e}", file=sys.stderr)
                return 1
            print(f"Host→module: {n_tx} B written.", file=sys.stderr, flush=True)
            try:
                grace0 = capture_rx_window(ser, max(rx_grace_ms, 400.0))
            except serial.SerialException as e:
                _serial_io_fail(args.port, e)
                return 1
            if grace0:
                seen_any_rx = True
                buf.extend(grace0)
                last_mag, warned_no_mag = emit_mag_gauss_rows(buf, last_mag, warned_no_mag)

        poll_s = args.poll
        last_poll = time.monotonic() - poll_s if poll_s > 0 else time.monotonic()

        if poll_s > 0:
            print(
                f"Poll every {poll_s:g} s (FF AA 27 {_REG_HX:02X} 00). Use --poll 0 to disable.",
                file=sys.stderr,
                flush=True,
            )
        print("Streaming Gauss (Ctrl+C to stop).", file=sys.stderr, flush=True)

        try:
            while True:
                now = time.monotonic()
                pieces: list[bytes] = []
                polled = False
                if poll_s > 0 and (now - last_poll) >= poll_s:
                    try:
                        wit_read_block(ser, _REG_HX)
                    except serial.SerialException as e:
                        print(f"\nPoll write failed: {e}", file=sys.stderr)
                        return 1
                    last_poll = now
                    polled = True
                    win_ms = rx_grace_ms + (idle_listen_ms if idle_listen_ms > 0 else 0)
                    try:
                        grace_p = capture_rx_window(ser, win_ms)
                    except serial.SerialException as e:
                        _serial_io_fail(args.port, e)
                        return 1
                    if grace_p:
                        pieces.append(grace_p)

                if not polled:
                    if idle_listen_ms > 0:
                        try:
                            idle_b = capture_rx_window(ser, idle_listen_ms)
                        except serial.SerialException as e:
                            _serial_io_fail(args.port, e)
                            return 1
                        if idle_b:
                            pieces.append(idle_b)
                    else:
                        try:
                            chunk = read_serial_chunk(ser, max_block=512)
                        except serial.SerialException as e:
                            _serial_io_fail(args.port, e)
                            return 1
                        if chunk:
                            pieces.append(chunk)

                if polled:
                    try:
                        extra = read_serial_chunk(ser, max_block=512)
                    except serial.SerialException as e:
                        _serial_io_fail(args.port, e)
                        return 1
                    if extra:
                        pieces.append(extra)

                for raw in pieces:
                    seen_any_rx = True
                    buf.extend(raw)
                last_mag, warned_no_mag = emit_mag_gauss_rows(buf, last_mag, warned_no_mag)

                now = time.monotonic()
                if not warned_no_rx and not seen_any_rx and (now - loop_start) >= 3.0:
                    try:
                        iw = getattr(ser, "in_waiting", 0) or 0
                    except serial.SerialException:
                        iw = "n/a"
                    print(
                        f"(No bytes yet — in_waiting={iw}. Try --dtr-on or --read-timeout 1.0)",
                        file=sys.stderr,
                        flush=True,
                    )
                    warned_no_rx = True
                if seen_any_rx and not warned_no_mag and (now - last_mag) >= 6.0:
                    print(
                        "(RX bytes but no valid 0x54 magnet frame — try --baud or --no-init.)",
                        file=sys.stderr,
                        flush=True,
                    )
                    warned_no_mag = True
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr, flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
