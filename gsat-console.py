#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gsat-console.py:

   Copyright (C) 2018 Wilhelm Duembeg

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
import sys
import argparse
import curses

import modules.config as gc
import modules.con_main as cm
import modules.version_info as vinfo


def get_cli_params():
    """
    define, retrieve and error check command line interface (cli) params

    """

    # parser = argparse.ArgumentParser(description=__description__)
    parser = argparse.ArgumentParser()

    parser.add_argument('--version',
                        action='version',
                        version=f"{sys.argv[0]} {vinfo.__revision__} ({vinfo.__appname__})")

    parser.add_argument("-c", "--config",
                        dest="config",
                        default=None,
                        help="Use alternate configuration file name",
                        metavar="FILE")

    parser.add_argument("-g", "--gcode",
                        dest="gcode",
                        default="None",
                        help="gcode file.",
                        metavar="FILE")

    parser.add_argument("-r", "--run",
                        dest="run",
                        action="store_true",
                        default=False,
                        help="run gcode immediately, must have --gcode")

    parser.add_argument("-s", "--server",
                        dest="server",
                        action="store_true",
                        default=False,
                        help="run gsat server on local host, and automatically connect")

    parser.add_argument("--nc", "--ncurses", "--no-curses",
                        dest="no_curses",
                        action="store_true",
                        default=False,
                        help="Don't use curses user interface")

    mask_str = str(sorted(gc.VERBOSE_MASK_DICT.keys()))
    parser.add_argument("--vm", "--verbose_mask",
                        dest="verbose_mask",
                        default=None,
                        help="select verbose mask(s) separated by ',' options are {}".format(mask_str),
                        metavar="MASK")

    options = parser.parse_args()

    if options.verbose_mask is not None:
        options.verbose_mask = gc.decode_verbose_mask_string(options.verbose_mask)

    if len(options.gcode):
        options.gcode = str(options.gcode).strip()

    if options.run and options.gcode == "None":
        print("Error: --gcode option must be included when using --run option\n")
        parser.print_usage()
        exit(1)

    if sys.version_info < (3, 8, 0):
        parser.error("** Required Python 3.8.2 or grater.")
        sys.exit(1)

    return options


"""----------------------------------------------------------------------------
    main
----------------------------------------------------------------------------"""
cli_options = None


def main(screen=None):
    global cli_options

    app = cm.ConsoleApp(cli_options)

    app.run()


if __name__ == '__main__':

    cli_options = get_cli_params()

    try:
        if cli_options.no_curses:
            main()
        else:
            curses.wrapper(main)

    finally:
        if cli_options is False:
            pass
            # curses.nocbreak()
            # curses.echo()
            # curses.curs_set(1)
            # curses.endwin()
