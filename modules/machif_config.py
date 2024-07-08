"""----------------------------------------------------------------------------
   machif_config.py

   Copyright (C) 2013 Wilhelm Duembeg

   This file is part of gsat. gsat is a cross-platform GCODE debug/step for
   Grbl like GCODE interpreters. With features similar to software debuggers.
   Features such as breakpoint, change current program counter, inspection
   and modification of variables.

   gsat is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 2 of the License, or
   (at your option) any later version.

   gsat is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with gsat.  If not, see <http://www.gnu.org/licenses/>.

----------------------------------------------------------------------------"""

import modules.machif_g2core as mi_g2core
import modules.machif_tinyg as mi_tinyg
import modules.machif_grbl as mi_grbl
import modules.machif_smoothie as mi_smoothie

# --------------------------------------------------------------------------
# Device type, this data needs to be in sync with the machif_* files
# --------------------------------------------------------------------------
MACHIF_NONE = None
# gMACHIF_GRBL            = 1000
# gMACHIF_TINYG           = 1100
# gMACHIF_G2CORE          = 1200
# gMACHIF_SMOOTHIE        = 1300

MACHIF_GRBL = mi_grbl.MachIf_GRBL()
MACHIF_TINYG = mi_tinyg.MachIf_TinyG()
MACHIF_G2CORE = mi_g2core.MachIf_g2core()
MACHIF_SMOOTHIE = mi_smoothie.MachIf_Smoothie()

MACHIF_CLS_LIST = [
    MACHIF_GRBL,
    MACHIF_TINYG,
    MACHIF_G2CORE,
    MACHIF_SMOOTHIE
]

MACHIF_LIST = [mach_if_cls.getName() for mach_if_cls in MACHIF_CLS_LIST]


def GetMachIfName(machIfId):
    """ translate ID to string.
    """
    machIfName = "None"

    for mach_if in MACHIF_CLS_LIST:
        if machIfId == mach_if.getId():
            machIfName = mach_if.getName()
            break

    return machIfName


def GetMachIfId(deviceStr):
    """ translate string to ID.
    """
    machIfId = MACHIF_NONE

    for mach_if in MACHIF_CLS_LIST:
        if deviceStr == mach_if.getName():
            machIfId = mach_if.getId()
            break

    # special backward compatibility
    if machIfId == MACHIF_NONE:
        if deviceStr in ["TinyG2"]:
            machIfId = MACHIF_G2CORE.getId()

        elif deviceStr in ["Grbl", "GRBL"]:
            machIfId = MACHIF_GRBL.getId()

    return machIfId


def GetMachIfModule(machIfId):
    """ translate string to ID.
    """
    machIfModule = None

    for mach_if in MACHIF_CLS_LIST:
        if machIfId == mach_if.getId():
            machIfModule = mach_if.factory()
            break

    return machIfModule
