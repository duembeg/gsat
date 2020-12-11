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
import argparse
import time

from modules.version_info import *

import modules.config as gc
import modules.machif_progexec as mi_progexec
import modules.remote_server as remote_server

'''
__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
    "GCODE Step and Alignment Tool (gsat) is a cross-platform GCODE "\
    "debug/step for grbl like GCODE interpreters. With features similar to "\
    "software debuggers. Features Such as breakpoint, change current program "\
    "counter, inspection and modification of variables."
'''

def get_cli_params():
    ''' define, retrieve and error check command line interface (cli) params
    '''

    parser = argparse.ArgumentParser(
        description=__description__, version="{} {} ({})".format(sys.argv[0], __revision__, __appname__))

    parser.add_argument("-c", "--config",
                        dest="config",
                        default=None,
                        help="Use alternate configuration file name, location "
                        "will be in HOME folder regardless of file name.",
                        metavar="FILE")

    parser.add_argument("-g", "--gcode",
                        dest="gcode",
                        default="None",
                        help="gcode file.",
                        metavar="FILE")

    mask_str = str(sorted(gc.VERBOSE_MASK_DICT.keys()))
    parser.add_argument("--vm", "--verbose_mask",
                        dest="verbose_mask",
                        default=None,
                        help="select verbose mask(s) separated by ',' options are {}".format(mask_str),
                        metavar="MASK")

    parser.add_argument("-s", "--server",
                        dest="server",
                        action="store_true",
                        default=False,
                        help="run gsat server")

    options = parser.parse_args()

    if options.verbose_mask is not None:
        options.verbose_mask = gc.decode_verbose_mask_string(
            options.verbose_mask)

    return options


"""----------------------------------------------------------------------------
   main
----------------------------------------------------------------------------"""
if __name__ == '__main__':

    machifProgExec = None
    remoteSever = None
    gcodeFileLines = []

    cmd_line_options = get_cli_params()

    try:
        config_fname = cmd_line_options.config

        if config_fname is None:
            config_fname = os.path.abspath(os.path.abspath(os.path.expanduser(
                "~/.gsat.json")))

        gc.init_config(cmd_line_options, config_fname, "foo")

        if cmd_line_options.server:
            remoteServer = remote_server.RemoteServerThread(None)

        elif os.path.exists(cmd_line_options.gcode):
            gcode_file = file(cmd_line_options.gcode)
            gcode_data = gcode_file.read()

            gcodeFileLines = gcode_data.splitlines(True)

            machifProgExec = mi_progexec.MachIfExecuteThread(None)

            # TODO: need code to check port is open
            time.sleep(2)

            machifProgExec.add_event(gc.EV_CMD_CLEAR_ALARM, 0, self)

            runDict = dict({
                'gcodeFileName': cmd_line_options.gcode,
                'gcodeLines': gcodeFileLines,
                'gcodePC': 0,
                'breakPoints': set()})

            machifProgExec.add_event(gc.EV_CMD_RUN, runDict, self)

            time.sleep(20)

        while True:
            time.sleep(1)

    finally:
        if remoteServer is not None:
            remoteServer.add_event(gc.EV_CMD_EXIT, 0, -1)

        if machifProgExec is not None:
            machifProgExec.add_event(gc.EV_CMD_EXIT, 0, -1)
