#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gsat.py:

   Copyright (C) 2013-2018 Wilhelm Duembeg

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

import modules.config as gc
import modules.wnd_main as mw

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

    parser = OptionParser(usage=usage, version="%prog " + mw.__revision__)
    parser.add_option("-c", "--config",
                      dest="config",
                      help="Use alternate configuration file name, location "
                      "will be in HOME folder regardless of file name.",
                      metavar="FILE")

    parser.add_option("-v", "--verbose",
                      dest="verbose",
                      action="store_true",
                      default=False,
                      help="print extra information while processing input "
                      "file.")

    parser.add_option("--vv", "--vverbose",
                      dest="vverbose",
                      action="store_true",
                      default=False,
                      help="print extra extra information while processing "
                      "input file.")

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

    elif options.verbose:
        options.verbose_mask = gc.VERBOSE_MASK_SERIALIF_STR

    elif options.vverbose:
        options.verbose_mask = gc.VERBOSE_MASK_SERIALIF_HEX

    else:
        options.verbose_mask = 0

    # check arguments sanity
    if options.vverbose:
        options.verbose = True

    if wx.VERSION < (2, 8, 0, 0):
        print "** Required wxPython 2.7 or grater."
        parser.error()
        sys.exit(1)

    return (options, args)


"""----------------------------------------------------------------------------
   main
----------------------------------------------------------------------------"""
if __name__ == '__main__':

    if 'ubuntu' in os.getenv('DESKTOP_SESSION', 'unknown'):
        os.environ["UBUNTU_MENUPROXY"] = "0"

    (cmd_line_options, cli_args) = get_cli_params()

    config_fname = cmd_line_options.config

    if config_fname is None:
        config_fname = os.path.abspath(os.path.abspath(os.path.expanduser(
            "~/.gsat.json")))

    gc.init_config(cmd_line_options, config_fname, "foo")

    app = wx.App(0)
    mw.gsatMainWindow(None, title=__appname__,
                      cmd_line_options=cmd_line_options)
    app.MainLoop()
