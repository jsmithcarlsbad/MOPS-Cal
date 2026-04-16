# Run NGSpice in batch on rc_smoke.cir (writes rc_smoke_out.txt here).
# Optional: set NGSPICE_BIN to full path of ngspice_con.exe (or ngspice.exe).
$ErrorActionPreference = "Stop"
$SimDir = $PSScriptRoot
$DefaultExe = "D:\NGSPICE\Spice64\bin\ngspice_con.exe"
$Ngspice = if ($env:NGSPICE_BIN) { $env:NGSPICE_BIN } else { $DefaultExe }
if (-not (Test-Path -LiteralPath $Ngspice)) {
    Write-Error "NGSpice not found at ``$Ngspice``. Install NGSpice or set env NGSPICE_BIN to ngspice_con.exe."
}
$Cir = Join-Path $SimDir "rc_smoke.cir"
if (-not (Test-Path -LiteralPath $Cir)) {
    Write-Error "Missing netlist: $Cir"
}
Push-Location $SimDir
try {
    & $Ngspice -b (Resolve-Path $Cir)
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $out = Join-Path $SimDir "rc_smoke_out.txt"
    if (Test-Path -LiteralPath $out) {
        Write-Host "OK: $out"
        Get-Content $out -TotalCount 6
    } else {
        Write-Warning "Expected output not found: $out"
    }
} finally {
    Pop-Location
}
