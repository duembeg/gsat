"""----------------------------------------------------------------------------
   con_main.py

   Copyright (C) 2021-2021 Wilhelm Duembeg

   This file is part of gsat. gsat is a cross-platform GCODE debug/step for
   grbl like GCODE interpreters. With features similar to software debuggers.
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
import time
# import pyfiglet
import signal
import curses
import string
import re

try:
    import queue
except ImportError:
    import Queue as queue

import modules.config as gc
import modules.machif_progexec as mi_progexec
import modules.remote_server as remote_server
import modules.remote_client as remote_client



class Log(object):
    def __init__(self, win):
        self.out = sys.stdout
        self.win = win

    def write(self, message):
        # self.out.write(message)
        self.win.addstr(message)
        self.win.refresh()

    def flush(self):
        pass
        # self.out.flush()


class ConsoleApp(gc.EventQueueIf):

    def __init__(self, cmd_line_options):
        gc.EventQueueIf.__init__(self)

        self.machifProgExec = None
        self.remoteSever = None
        self.remoteClient = None
        self.machif = None
        self.gcodeFileLines = []

        self.cmd_line_options = cmd_line_options
        self.config_fname = cmd_line_options.config

        self.logger = logging.getLogger()

    def process_queue(self):
        """ Handle events coming from main UI
        """
        # process events from queue
        try:
            e = self._eventQueue.get_nowait()
        except queue.Empty:
            pass
        else:

            self.lastEventID = e.event_id

            if e.event_id == gc.EV_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HELLO from 0x{:x}".format(id(e.sender)))

            elif e.event_id == gc.EV_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GOOD_BYE from 0x{:x}".format(id(e.sender)))

            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.error("got unknown event!! [{}]".format(str(e.event_id)))


    def run(self):
        try:

            if self.config_fname is None:
                self.config_fname = os.path.abspath(os.path.abspath(os.path.expanduser("~/.gsat.json")))

            gc.init_config(self.cmd_line_options, self.config_fname, "foo")

            if self.cmd_line_options.server:
                self.remoteServer = remote_server.RemoteServerThread(None)
                time.sleep(1)
                self.remoteClient = remote_client.RemoteClientThread(self, host='localhost')

            if os.path.exists(os.path.expanduser(self.cmd_line_options.gcode)):
                gcode_file = file(os.path.expanduser(self.cmd_line_options.gcode))
                gcode_data = gcode_file.read()

                gcodeFileLines = gcode_data.splitlines(True)

                if self.remoteClient is None:
                    self.machifProgExec = mi_progexec.MachIfExecuteThread(self)
                    self.machif = self.machifProgExec
                else:
                    self.remoteClient.add_event(gc.EV_CMD_OPEN)
                    self.machif = self.remoteClient

                # TODO: need code to check port is open
                time.sleep(2)

                self.machif.add_event(gc.EV_CMD_CLEAR_ALARM)

                runDict = dict({
                    'gcodeFileName': self.cmd_line_options.gcode,
                    'gcodeLines': gcodeFileLines,
                    'gcodePC': 0,
                    'breakPoints': set()})

                self.machif.add_event(gc.EV_CMD_RUN, runDict)

            while True:
                self.process_queue()
                time.sleep(0.010)

        finally:
            if self.remoteServer is not None:
                self.remoteServer.add_event(gc.EV_CMD_EXIT, 0, -1)

            if self.remoteClient is not None:
                self.remoteClient.add_event(gc.EV_CMD_EXIT, 0, -1)

            if self.machifProgExec is not None:
                self.machifProgExec.add_event(gc.EV_CMD_EXIT, 0, -1)
