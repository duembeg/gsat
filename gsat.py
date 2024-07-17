#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gsat.py:

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
import os
import sys
import argparse
import wx

import modules.config as gc
import modules.wnd_main as mw

import modules.version_info as vinfo


def get_cli_params():
    """
    define, retrieve and error check command line interface (cli) params

    """

    parser = argparse.ArgumentParser(description=vinfo.__description__)

    parser.add_argument(
        '-V', '--version',
        action='version',
        version=f"{sys.argv[0]} {vinfo.__revision__} ({vinfo.__appname__})")

    parser.add_argument(
        "-c", "--config",
        dest="config",
        help="Use alternate configuration file name",
        metavar="FILE")

    parser.add_argument(
        "-v", "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="print extra information to stdout")

    parser.add_argument(
        "--vv", "--vverbose",
        dest="vverbose",
        action="store_true",
        default=False,
        help="print extra++ information to stdout")

    mask_str = str(sorted(gc.VERBOSE_MASK_DICT.keys()))
    parser.add_argument(
        "--vm", "--verbose_mask",
        dest="verbose_mask",
        default=None,
        help="select verbose mask(s) separated by ','; the options are {}".format(mask_str),
        metavar="MASK")

    parser.add_argument(
        "-s", "--server",
        dest="server",
        action="store_true",
        default=False,
        help="run gsat server, allows other UIs like cnc pendants to connect via socket, "
        " on this mode remote host name config is ignored and localhost is used")

    options = parser.parse_args()

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

    if wx.VERSION < (4, 0, 0, 0):
        # print ("** Required wxPython 2.7 or grater.")
        parser.error("** Required wxPython 4.x or grater.")
        sys.exit(1)

    if sys.version_info < (3, 8, 2):
        parser.error("** Required Python 3.8.2 or grater.")
        sys.exit(1)

    return options


if __name__ == '__main__':

    import faulthandler
    faulthandler.enable()

    if 'ubuntu' in os.getenv('DESKTOP_SESSION', 'unknown'):
        os.environ["UBUNTU_MENUPROXY"] = "0"

    cmd_line_options = get_cli_params()

    config_fname = cmd_line_options.config

    if config_fname is None:
        config_fname = os.path.abspath(os.path.abspath(os.path.expanduser("~/.gsat.json")))

    gc.init_config(cmd_line_options, config_fname, "x")

    app = wx.App(0)
    mw.gsatMainWindow(None, title=vinfo.__appname__, cmd_line_options=cmd_line_options)

    app.MainLoop()
