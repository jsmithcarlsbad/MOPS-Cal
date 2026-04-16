# NGSpice — `Hardware/sim`

Smoke netlist **`rc_smoke.cir`** (RC transient) checks that batch NGSpice runs from this repo.

**Run (PowerShell):**

```powershell
.\Hardware\sim\run_spice.ps1
```

**Run (cmd):**

```cmd
Hardware\sim\run_spice.bat
```

**Override install path:** set environment variable **`NGSPICE_BIN`** to the full path of **`ngspice_con.exe`** (recommended for batch) or **`ngspice.exe`**.

Output **`rc_smoke_out.txt`** is written next to the netlist (ignored by git).
