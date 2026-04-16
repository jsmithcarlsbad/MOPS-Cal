# OWON XDM1041 — headless client (Calibrator)

This folder is a **small extraction** of the SCPI logic from the MIT-licensed desktop GUI:

- **Upstream (do not push CoilDriver changes there):** [jsmithcarlsbad/XDM1041-GUI](https://github.com/jsmithcarlsbad/XDM1041-GUI)

Use **`XDM1041`** from Python scripts to drive the **same** meter the GUI uses (separate COM port from the Pico).

## Install

Use the repo **HostApp** venv or any env with **pyserial** (see `Software/HostApp/requirements.txt`).

```text
.venv\Scripts\python.exe -m pip install pyserial
```

## Smoke test

```text
cd Software\Tools\xdm1041
..\.venv\Scripts\python.exe dmm_cli.py COM5
```

Options: `--mode dc_current`, `--rate medium`, `--debug`.

## 3D Helmholtz bench logging (lab supply only)

See **`Hardware/BENCH_TEST_3DHC.md`**. Interactive CSV session:

```text
python bench_3dhc_log.py --port COM4
```

Quick lead sanity (AAA / short): **`timed_lead_demo.py`**.

## Remote protocol (Pico ↔ PC GUI)

The upstream **`REMOTE_PROTOCOL.md`** describes the **second UART** when the **full GUI** bridges the Pico. This **`client.py`** path talks **directly** to the meter instead — use one or the other for a given COM port, not both.

## API sketch

```python
from xdm1041.client import XDM1041

with XDM1041("COM5", debug_serial=False) as dmm:
    print(dmm.open())  # first call in 'with' — use pattern below instead

# Correct pattern:
dmm = XDM1041("COM5")
idn = dmm.open()
try:
    dmm.set_auto_range()
    dmm.configure_mode("dc_volts")
    dmm.set_sample_rate("fast")
    v = dmm.read_primary_float()
finally:
    dmm.close()
```

Or use `with XDM1041("COM5") as dmm:` after we fix context manager to call open() — **fixed**: `__enter__` calls `open()` but `open()` returns idn; use:

```python
with XDM1041("COM5") as dmm:
    print(dmm.query("*IDN?"))
```

Fix the README example - __enter__ calls open() which returns str but we discard. Good.

Actually __enter__ calls self.open() which returns idn - user might want idn = dmm.open() before with - let me fix __enter__ to not duplicate - currently __enter__ calls open() which returns str - we could return self and user calls query - the README with `print(dmm.open())` inside with is wrong because open() already called in __enter__

I'll fix client __enter__ to call open() and return self - user does dmm.query("*IDN?") or we store idn on self._idn

Simpler: document
```python
with XDM1041("COM5") as dmm:
    print(dmm.query("*IDN?"))
```

Remove wrong README block with "print(dmm.open())"

I'll fix README and fix dmm_cli - it calls dmm.open() then finally dmm.close() but doesn't use `with` - the try/finally uses dmm before assignment if open fails - bug:

```python
dmm = XDM1041(args.port, debug_serial=args.debug)
try:
    idn = dmm.open()
...
finally:
    dmm.close()
```

If open() raises, dmm exists and close() is ok. Good.

README fix only


StrReplace