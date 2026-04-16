@echo off
setlocal
cd /d "%~dp0"
if defined NGSPICE_BIN (
  set "EXE=%NGSPICE_BIN%"
) else (
  set "EXE=D:\NGSPICE\Spice64\bin\ngspice_con.exe"
)
if not exist "%EXE%" (
  echo NGSpice not found: "%EXE%"
  echo Set NGSPICE_BIN to ngspice_con.exe full path.
  exit /b 1
)
"%EXE%" -b "%~dp0rc_smoke.cir"
if errorlevel 1 exit /b %errorlevel%
if exist "%~dp0rc_smoke_out.txt" (
  echo OK: "%~dp0rc_smoke_out.txt"
  powershell -NoProfile -Command "Get-Content -LiteralPath '%~dp0rc_smoke_out.txt' -TotalCount 8"
) else (
  echo Warning: rc_smoke_out.txt not created.
)
endlocal
