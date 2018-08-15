#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gsat-console.py:

   Copyright (C) 2018-2018 Wilhelm Duembeg

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

import os
import sys
from optparse import OptionParser
import wx
import time

import modules.config as gc
import modules.machif_progexec as mi_progexec

__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
    "GCODE Step and Alignment Tool (gsat) is a cross-platform GCODE "\
    "debug/step for grbl like GCODE interpreters. With features similar to "\
    "software debuggers. Features Such as breakpoint, change current program "\
    "counter, inspection and modification of variables."


def get_cli_params():
    ''' define, retrieve and error check command line interface (cli) params
    '''

    usage = \
        "usage: %prog [options]"

    parser = OptionParser(usage=usage)
    parser.add_option("-g", "--gcode",
                      dest="gcode",
                      help="gcode file.",
                      metavar="FILE")

    parser.add_option("--vm", "--verbose_mask",
                      dest="verbose_mask",
                      default=None,
                      help="select verbose mask. UI, MACHIF, MACHIF_MOD, "
                      "MACHIF_EXEC, SERIALIF, SERIALIF_STR, SERIALIF_HEX",
                      metavar="")

    (options, args) = parser.parse_args()

    if options.verbose_mask is not None:
        options.verbose_mask = gc.decode_verbose_mask_string(
            options.verbose_mask)

    if wx.VERSION < (2, 8, 0, 0):
        print "** Required wxPython 2.7 or grater."
        options.error()
        sys.exit(1)

    return (options, args)


"""----------------------------------------------------------------------------
   main
----------------------------------------------------------------------------"""
if __name__ == '__main__':

    machifProgExec = None
    gcodeFileLines = []
    (cmd_line_options, cli_args) = get_cli_params()

    try:
        configFile = wx.FileConfig("gsat", style=wx.CONFIG_USE_LOCAL_FILE)

        configData = gc.gsatConfigData()
        configData.load(configFile)
        stateData = gc.gsatStateData()

        gc.init_config(cmd_line_options, configData, stateData)

        if os.path.exists(cmd_line_options.gcode):
            gcode_file = file(cmd_line_options.gcode)
            gcode_data = gcode_file.read()

            gcodeFileLines = gcode_data.splitlines(True)

        machifProgExec = mi_progexec.MachIfExecuteThread(None)

        # TODO: need code to check port is open
        time.sleep(2)

        machifProgExec.eventPut(gc.EV_CMD_CLEAR_ALARM)

        machifProgExec.eventPut(gc.EV_CMD_RUN,[gcodeFileLines, 0, set()])

        time.sleep(20)

    finally:
        if machifProgExec is not None:
            machifProgExec.eventPut(gc.EV_CMD_EXIT)
