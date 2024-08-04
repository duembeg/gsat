#!/usr/bin/env python
"""----------------------------------------------------------------------------
    gsat-server.py:

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
import os
import sys
import logging
import argparse

import modules.config as gc
import modules.remote_server as rs
import modules.remote_ws_server as rsws
import modules.version_info as vinfo


def get_cli_params():
    """
    define, retrieve and error check command line interface (cli) params

    """

    # parser = argparse.ArgumentParser(description=__description__)
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-V', '--version',
        action='version',
        version=f"{sys.argv[0]} {vinfo.__revision__} ({vinfo.__appname__})")

    parser.add_argument(
        "-c", "--config",
        dest="config",
        default=None,
        help="Use alternate configuration file name",
        metavar="FILE")

    mask_str = str(sorted(gc.VERBOSE_MASK_DICT.keys()))
    parser.add_argument(
        "--vm", "--verbose_mask",
        dest="verbose_mask",
        default=None,
        help="select verbose mask(s) separated by ',' options are {}".format(mask_str),
        metavar="MASK")

    options = parser.parse_args()

    if options.verbose_mask is not None:
        options.verbose_mask = gc.decode_verbose_mask_string(options.verbose_mask)

    if sys.version_info < (3, 8, 0):
        parser.error("** Required Python 3.8.2 or grater.")
        sys.exit(1)

    return options


"""----------------------------------------------------------------------------
    main
----------------------------------------------------------------------------"""


class GsatServer(gc.EventQueueIf):
    def __init__(self):
        gc.EventQueueIf.__init__(self)

        self.useWebSockets = True
        self.configData = gc.CONFIG_DATA

        self.logger = logging.getLogger()
        if gc.test_verbose_mask(gc.VERBOSE_MASK_UI_ALL):
            self.logger.info(f"init logging id:0x{id(self):x}")

    def __del__(self):
        pass

    def run(self):
        self.useWebSockets = self.configData.get('/remote/WebSockets')

        try:
            if self.useWebSockets:
                server = rsws.RemoteServer(self)
            else:
                server = rs.RemoteServer(self)

            # wait for server events
            while True:
                ev = self._eventQueue.get()

                if ev.event_id == gc.EV_HELLO:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_UI_EV):
                        self.logger.info(f"EV_HELLO from 0x{id(ev.sender):x}")

                elif ev.event_id == gc.EV_GOOD_BYE:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_UI_EV):
                        self.logger.info(f"EV_GOOD_BYE from 0x{id(ev.sender):x}")

        finally:
            if server is not None:
                server.add_event(gc.EV_CMD_EXIT, 0, -1)


def main():
    cli_options = get_cli_params()
    config_fname = cli_options.config

    if config_fname is None:
        config_fname = os.path.abspath(os.path.abspath(os.path.expanduser("~/.gsat.json")))

    gc.init_config(cli_options, config_fname, "log_file")

    server = GsatServer()
    server.run()

    print("gsat-server: exiting")


if __name__ == '__main__':
    main()
