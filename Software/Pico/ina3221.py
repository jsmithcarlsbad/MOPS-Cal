# ina3221.py — TI INA3221 triple channel shunt/bus monitor (MicroPython)
# Datasheet: SLIS144 / SLOS576. Used by coil_driver_app (current_ma, bus_voltage_v).

# Shunt voltage registers: 16-bit two's complement, 40 µV/LSB (default).
_SHUNT_UV_LSB = 40e-6
# Bus voltage: 13-bit value in bits 15–3, 8 mV/LSB.
_BUS_V_LSB = 0.008

_REG_CONFIG = 0x00
_REG_SHUNT = (0x01, 0x03, 0x05)
_REG_BUS = (0x02, 0x04, 0x06)

# Continuous conversion, all channels on — common bench init (matches many Arduino libs).
_DEFAULT_CONFIG = 0x7127


class INA3221:
    def __init__(self, i2c, address, shunt_ohms):
        self.i2c = i2c
        self.addr = int(address)
        self._r = float(shunt_ohms)
        if self._r <= 0:
            raise ValueError("shunt_ohms must be > 0")
        self._write_u16(_REG_CONFIG, _DEFAULT_CONFIG)

    def _write_u16(self, reg, val):
        self.i2c.writeto(self.addr, bytes([reg, (val >> 8) & 0xFF, val & 0xFF]))

    def _read_u16(self, reg):
        self.i2c.writeto(self.addr, bytes([reg]))
        buf = self.i2c.readfrom(self.addr, 2)
        return (buf[0] << 8) | buf[1]

    def _read_s16(self, reg):
        v = self._read_u16(reg)
        if v & 0x8000:
            v -= 65536
        return v

    def shunt_raw(self, channel):
        """Signed 16-bit shunt voltage register (debug / health check)."""
        if channel < 0 or channel > 2:
            raise ValueError("channel 0..2")
        return self._read_s16(_REG_SHUNT[channel])

    def current_ma(self, channel):
        """Shunt-derived current for channel 0, 1, or 2 (mA)."""
        if channel < 0 or channel > 2:
            raise ValueError("channel 0..2")
        raw = self._read_s16(_REG_SHUNT[channel])
        v_shunt = raw * _SHUNT_UV_LSB
        return (v_shunt / self._r) * 1000.0

    def bus_voltage_v(self, channel):
        """Bus (load-side) voltage for channel 0, 1, or 2 (volts)."""
        if channel < 0 or channel > 2:
            raise ValueError("channel 0..2")
        raw = self._read_u16(_REG_BUS[channel])
        # Bits 15–3: 13-bit magnitude; lower bits are flags in full register map.
        return ((raw >> 3) & 0x1FFF) * _BUS_V_LSB
