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
import threading

try:
    import queue
except ImportError:
    import Queue as queue

from modules.version_info import *
import modules.config as gc
import modules.machif_progexec as mi_progexec
import modules.remote_server as remote_server
import modules.remote_client as remote_client


class StdoutWrapper(object):
    def __init__(self, win):
        self.out = sys.stdout
        self.win = win
        self.lock = threading.RLock()

    def write(self, message):
        with self.lock:
            # self.out.write(message)
            self.win.addstr(message)
            # self.win.touchwin()
            self.win.refresh()
            # print (message)

    def flush(self):
        pass
        # self.out.flush()


class CursesHandler(logging.Handler):
    def __init__(self, win):
        logging.Handler.__init__(self)
        self.win = win
        self.lock = threading.RLock()

    def emit(self, record):
        try:
            msg = str(self.format(record))

            with self.lock:
                # self.win.addstr("{}\n".format(msg))
                print (msg)
                # self.win.box()
                # self.win.touchwin()
                # self.win.refresh()

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            raise


class ConsoleApp(gc.EventQueueIf):

    def __init__(self, cmd_line_options):
        gc.EventQueueIf.__init__(self)

        self.machifProgExec = None
        self.remoteServer = None
        self.remoteClient = None
        self.machif = None
        self.gcodeFileLines = []

        self.cmd_line_options = cmd_line_options
        self.config_fname = cmd_line_options.config

        self.time_to_exit_gracefully = False

        self.user_cmd = ""
        self.user_cmd_history = []
        self.user_cmd_history_iter = iter(self.user_cmd_history)

        self.posx = 0
        self.posy = 0
        self.posz = 0
        self.posa = 0
        self.posb = 0
        self.posc = 0
        self.feed_rate = 0
        self.machif_st = "Idle"
        self.sw_st = "Idle"
        self.controller_str = ""
        self.server_str = ""
        self.run_time = ""
        self.pc_str = ""

        self.init()

    def exit_gracefully(self, signum=None, stack=None):
        self.time_to_exit_gracefully = True

    def init(self):
        # hook for exit signal and clean up
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGHUP, self.exit_gracefully)
        signal.signal(signal.SIGCONT, self.exit_gracefully)

        if (self.cmd_line_options.no_curses is False):
            self.screen = curses.initscr()
            curses.curs_set(0)
            curses.noecho()

            self.layout()

            self.screen.refresh()

            # create status box
            self.sta_box = curses.newwin(
                self.sta_height,
                self.sta_width,
                self.sta_begin_y,
                self.sta_begin_x
            )

            self.sta_box.box()
            self.sta_box.keypad(True)
            self.sta_box.timeout(0)

            self.stdout_box = curses.newwin(
                self.stdout_height,
                self.stdout_width,
                self.stdout_begin_y,
                self.stdout_begin_x
            )

            self.stdout_box.border(' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ')
            # self.stdout_box.box()
            self.stdout_box.refresh()

            # # self.stdout_box = self.outer_stdout_box.subwin(
            # #     self.stdout_height-1,
            # #     self.stdout_width-1,
            # #     self.stdout_begin_y+1,
            # #     self.stdout_begin_x+1
            # # )

            self.stdout_box.scrollok(True)

            # re direct stdout
            stdout_wrapper = StdoutWrapper(self.stdout_box)
            self.org_sys_stdout = sys.stdout
            sys.stdout = stdout_wrapper
            # sys.stderr = stdout_wrapper

            # self.update_status()
            self.resize()

    def layout(self):
        self.scr_y_max, self.scr_x_max = self.screen.getmaxyx()

        self.cli_height = 3
        self.cli_width = self.scr_x_max
        self.cli_begin_x = 0
        self.cli_begin_y = self.scr_y_max - self.cli_height

        self.sta_height = 10
        self.sta_width = self.scr_x_max
        self.sta_begin_x = 0
        self.sta_begin_y = 0

        self.stdout_height = self.scr_y_max - (self.sta_begin_y + self.sta_height)
        self.stdout_width = self.scr_x_max
        self.stdout_begin_x = 0
        self.stdout_begin_y = (self.sta_begin_y + self.sta_height)

    def proccess_keypad(self):
        retVal = False

        c = self.sta_box.getch(1, len(self.user_cmd)+1)

        if (c != -1):
            # print c
            print (curses.keyname(c))

            if c in [curses.KEY_RESIZE]:
                self.resize()

            # elif (c in [curses.KEY_ENTER, '\n', 10]):
            #     # print self.userCmd, len(self.userCmd)
            #     self.userCmdHistory.append(self.userCmd)
            #     self.userCmdHistoryIter = iter(reversed(self.userCmdHistory))

            #     args = re.split(' |=', self.userCmd)
            #     # print len(args)
            #     # print args

            #     cmd = args[0].lower()

            #     if (cmd in self.cmdList.keys()):
            #         func = self.cmdList.get(cmd).get('func')
            #         funcCall = "rv = " + func % str(args[1:])
            #         # print funcCall

            #         exec(funcCall) in locals()
            #         retVal = rv
            #     else:
            #         print ("ERROR: Unknown command [%s]" % (self.userCmd))

            #     self.userCmd = ""
            #     self.cmdWin.addstr(1, 1, "".center(self.xMax - 2))

            # elif (c in [curses.KEY_BACKSPACE]):
            #     if (len(self.userCmd) > 0):
            #         self.userCmd = self.userCmd[:-1]
            #         # self.cmdWin.clean()
            #         self.cmdWin.addstr(1, 1, self.userCmd + " ")

            # elif c < 256 and chr(c) in string.printable:
            #     self.userCmd = self.userCmd + chr(c)
            #     # self.cmdWin.clear()
            #     self.cmdWin.addstr(1, 1, self.userCmd)

            # # elif c in [curses.KEY_UP]:
            # elif curses.keyname(c) in ['kUP3']:
            #     # print "up"
            #     self.consoleApp.jog({
            #         "y": self.consoleApp.jogStepSize,
            #         "feed": self.consoleApp.jogFeedRate
            #     })

            # # elif c in [curses.KEY_DOWN]:
            # elif curses.keyname(c) in ['kDN3']:
            #     # print "down"
            #     self.consoleApp.jog({
            #         "y": -self.consoleApp.jogStepSize,
            #         "feed": self.consoleApp.jogFeedRate
            #     })

            # # elif c in [curses.KEY_LEFT]:
            # elif curses.keyname(c) in ['kLFT3']:
            #     # print "left"
            #     self.consoleApp.jog({
            #         "x": -self.consoleApp.jogStepSize,
            #         "feed": self.consoleApp.jogFeedRate
            #     })

            # # elif c in [curses.KEY_RIGHT]:
            # elif curses.keyname(c) in ['kRIT3']:
            #     # print "right"
            #     self.consoleApp.jog({
            #         "x": self.consoleApp.jogStepSize,
            #         "feed": self.consoleApp.jogFeedRate
            #     })

            # # elif c in [curses.KEY_PPAGE]:
            # elif curses.keyname(c) in ['kNXT3']:
            #     # print "page up"
            #     self.consoleApp.jog({
            #         "z": self.consoleApp.jogStepSize,
            #         "feed": self.consoleApp.jogFeedRate
            #     })

            # # elif c in [curses.KEY_NPAGE]:
            # elif curses.keyname(c) in ['kPRV3']:
            #     # print "page down"
            #     self.consoleApp.jog({
            #         "z": -self.consoleApp.jogStepSize,
            #         "feed": self.consoleApp.jogFeedRate
            #     })

            # # elif curses.keyname(c) in ['^P']:
            # elif c in [curses.KEY_UP]:
            #     # print "ctrl+p"
            #     try:
            #         self.userCmd = self.userCmdHistoryIter.next()
            #         # print self.userCmd
            #         self.cmdWin.addstr(1, 1, "".center(self.xMax - 2))
            #         self.cmdWin.addstr(1, 1, self.userCmd)
            #     except StopIteration:
            #         # print "no more data"
            #         pass

        return retVal

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

            if e.event_id == gc.EV_DATA_STATUS:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_STATUS from 0x{:x}".format(id(e.sender)))

                self.update_status(e.data)

            elif e.event_id == gc.EV_DATA_OUT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_OUT")

                print ("> {}".format(str(e.data).strip()))

            elif e.event_id == gc.EV_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HELLO from 0x{:x}".format(id(e.sender)))

            elif e.event_id == gc.EV_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GOOD_BYE from 0x{:x}".format(id(e.sender)))

            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.error("got unknown event!! [{}]".format(str(e.event_id)))

    def resize(self):
        self.screen.clear()

        self.layout()

        # self.screen.addstr(1, 2, "{} Console {}".format(__appname__, __revision__))
        # self.screen.refresh()

        self.sta_box.erase()
        self.sta_box.resize(self.sta_height, self.sta_width)
        self.sta_box.box()
        self.sta_box.addstr(0, 2, "{} Console {}".format(__appname__, __revision__))
        self.sta_box.addstr(1, 2, "DRO")
        self.sta_box.refresh()

        # self.stdOutWin.erase()
        self.stdout_box.resize(self.stdout_height, self.stdout_width)
        # self.stdout_box.resize(self.stdout_height-1, self.stdout_width-1)
        self.stdout_box.border(' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ')
        # self.stdout_box.addstr(0, 2, "Output")
        self.stdout_box.redrawwin()
        self.stdout_box.refresh()
        # self.stdout_box.touchwin()
        # self.stdout_box.redrawwin()
        # self.stdout_box.refresh()

        self.update_status()

    def run(self):
        try:

            if self.config_fname is None:
                self.config_fname = os.path.abspath(os.path.abspath(os.path.expanduser("~/.gsat.json")))

            if self.cmd_line_options.no_curses:
                gc.init_config(self.cmd_line_options, self.config_fname, "log_file")
            else:
                log_handler = CursesHandler(self.stdout_box)
                gc.init_config(self.cmd_line_options, self.config_fname, "log_file", log_handler)

            self.logger = logging.getLogger()

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

                if self.cmd_line_options.run:
                    self.machif.add_event(gc.EV_CMD_CLEAR_ALARM)

                    runDict = dict({
                        'gcodeFileName': self.cmd_line_options.gcode,
                        'gcodeLines': gcodeFileLines,
                        'gcodePC': 0,
                        'breakPoints': set()})

                    self.machif.add_event(gc.EV_CMD_RUN, runDict)

            while not self.time_to_exit_gracefully:
                self.process_queue()
                self.proccess_keypad()
                time.sleep(0.010)

        finally:
            if self.remoteServer is not None:
                self.remoteServer.add_event(gc.EV_CMD_EXIT, 0, -1)

            if self.remoteClient is not None:
                self.remoteClient.add_event(gc.EV_CMD_EXIT, 0, -1)

            if self.machifProgExec is not None:
                self.machifProgExec.add_event(gc.EV_CMD_EXIT, 0, -1)

            if (self.cmd_line_options.no_curses is False):
                sys.stdout = self.org_sys_stdout

    def update_status(self, data=None):

        if data:
            if 'sr' in data:
                sr = data['sr']

                if 'posx' in sr:
                    self.posx = sr['posx']

                if 'posy' in sr:
                    self.posy = sr['posy']

                if 'posz' in sr:
                    self.posz = sr['posz']

                if 'posa' in sr:
                    self.posa = sr['posa']

                if 'posb' in sr:
                    self.posb = sr['posb']

                if 'posc' in sr:
                    self.posc = sr['posc']

                if 'vel' in sr:
                    self.feed_rate = sr['vel']

                if 'stat' in sr:
                    self.machif_st = sr['stat']

                if 'prcnt' in sr:
                    self.pc_str = sr['prcnt']

                if 'rtime' in sr:
                    run_time = sr['rtime']
                    hours, reminder = divmod(run_time, 3600)
                    minutes, reminder = divmod(reminder, 60)
                    seconds, mseconds = divmod(reminder, 1)
                    self.run_time = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

            if 'swstate' in data:
                self.sw_st = gc.get_sw_status_str(int(data['swstate']))

            if 'rx_data' in data:
                rx_data = str(data['rx_data']).strip()
                print ("{}".format(rx_data))

        if (self.cmd_line_options.no_curses is False):
            self.sta_box.erase()
            #self.sta_box.clear()
            self.sta_box.box()

            self.sta_box.addstr(0, 2, "{} Console {}".format(__appname__, __revision__))
            #self.sta_box.addstr(1, 2, "DRO")

            self.sta_box.addstr(2, 3, "X: {:>9.3f}  ".format(self.posx), curses.A_REVERSE)
            self.sta_box.addstr(3, 3, "Y: {:>9.3f}  ".format(self.posy), curses.A_REVERSE)
            self.sta_box.addstr(4, 3, "Z: {:>9.3f}  ".format(self.posz), curses.A_REVERSE)
            self.sta_box.addstr(5, 3, "FR: {:>8.1f}  ".format(self.feed_rate), curses.A_REVERSE)
            self.sta_box.addstr(6, 3, "GPOS: {:<20}".format(self.pc_str), curses.A_REVERSE)

            self.sta_box.addstr(2, 17, "A: {:>9.3f}".format(self.posa), curses.A_REVERSE)
            self.sta_box.addstr(3, 17, "B: {:>9.3f}".format(self.posb), curses.A_REVERSE)
            self.sta_box.addstr(4, 17, "C: {:>9.3f}".format(self.posc), curses.A_REVERSE)
            self.sta_box.addstr(5, 17, "   {:>9}".format(""), curses.A_REVERSE)

            self.sta_box.addstr(2, 31, "Ctrl ST:  {:<8}".format(self.machif_st), curses.A_REVERSE)
            self.sta_box.addstr(3, 31, "Soft ST:  {:<8}".format(self.sw_st), curses.A_REVERSE)
            self.sta_box.addstr(4, 31, "Run time: {:<8}".format(self.run_time), curses.A_REVERSE)

            # self.sta_box.addstr(1, 18, "State")
            # self.sta_box.addstr(2, 19, "APP:  {:<20s}".format("%s, %d" % (
            #     config.STATE_DICT[self.consoleApp.consoleAppState],
            #     self.consoleApp.consoleAppState)))
            # self.sta_box.addstr(3, 19, "MACH: {:<20s}".format(
            #     self.consoleApp.machifState))


            self.sta_box.touchwin()
            self.sta_box.refresh()
            # self.stdout_box.refresh()
