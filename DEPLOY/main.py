# main.py — MicroPython entry point (auto-start on every boot / reset)
#
# On power-up or reset, MicroPython runs boot.py (if present), then this file.
# This file always imports coil_driver_app and calls main() so the coil driver
# runs automatically — no manual start required.
#
# REPL vs deploy while the app is running:
# - The USB serial port is shared. While coil_driver_app.main() is running, the
#   interactive prompt (>>>) is not shown until you interrupt the script.
# - Interactive REPL: open the serial terminal and press Ctrl+C once. That raises
#   KeyboardInterrupt, stops main(), and you get the >>> prompt to try code.
# - Deploy (mpremote): deploy.py runs "python -m mpremote", which uses Micro-
#   Python's raw REPL (a machine protocol for file I/O), not the >>> prompt.
#   It usually interrupts or resets the board as needed, then copies files from
#   ./DEPLOY to the device. You do not need the >>> prompt open to deploy.

try:
    import coil_driver_app

    coil_driver_app.main()
except Exception as e:
    import sys

    print("FATAL:", e)
    sys.print_exception(e)
