"""Headless OWON XDM1041 (USB-SCPI) helpers for Calibrator bench automation.

Derived from logic in `XDM1041_GUI.py` in the upstream MIT project — do not push changes there.
"""

from .client import MEASUREMENT_MODE_IDS, XDM1041, parse_measurement_float

__all__ = ["XDM1041", "MEASUREMENT_MODE_IDS", "parse_measurement_float"]
