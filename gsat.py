#!/usr/bin/env python
"""Compatibility shim. Day-to-day UI is gsat-pyside.py; legacy wx is gsat-wx.py."""

import sys

print("gsat.py is a compatibility shim.")
print("  Use gsat-pyside.py for the day-to-day UI.")
print("  Legacy: gsat-wx.py (maintenance only; may be removed in a future major).")
sys.exit(1)
