"""----------------------------------------------------------------------------
   con_main.py

   Copyright (C) 2021 Wilhelm Duembeg

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
import signal
import curses
import queue

import modules.version_info as vinfo
import modules.config as gc
import modules.machif_progexec as mi_progexec
import modules.remote_server as remote_server
import modules.remote_client as remote_client

text_queue = queue.Queue()


def verbose_data_ascii(direction, data):
    return "[%03d] %s %s" % (len(data), direction, data.strip())


def verbose_data_hex(direction, data):
    return "[%03d] %s ASCII:%s HEX:%s" % (
        len(data), direction, data.strip(), ':'.join(x.encode("utf-8").hex() for x in data))


class StdoutWrapper(object):
    def __init__(self, win):
        self.out = sys.stdout
        self.win = win
        # self.lock = threading.RLock()

    def write(self, message):
        text_queue.put(message)
        # with self.lock:
        #     self.win.addstr(message)
        #     self.win.refresh()

    def flush(self):
        pass
        # self.out.flush()


class CursesHandler(logging.Handler):
    def __init__(self, win):
        logging.Handler.__init__(self)
        self.win = win

    def emit(self, record):
        try:
            msg = str(self.format(record))
            text_queue.put(msg)
            # self.win.addstr("{}\n".format(msg))
            # print (msg)
            # self.win.box()
            # self.win.touchwin()
            # self.win.refresh()

        except (KeyboardInterrupt, SystemExit):
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
        self.device_str = ""
        self.remote_str = ""
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

        self.sta_height = 15
        self.sta_width = self.scr_x_max
        self.sta_begin_x = 0
        self.sta_begin_y = 0

        self.stdout_height = self.scr_y_max - (self.sta_begin_y + self.sta_height)
        self.stdout_width = self.scr_x_max
        self.stdout_begin_x = 0
        self.stdout_begin_y = (self.sta_begin_y + self.sta_height)

    def process_keypad(self):
        retVal = False

        c = self.sta_box.getch(1, len(self.user_cmd)+1)

        if (c != -1):
            # print c
            print(curses.keyname(c))

            if c in [curses.KEY_RESIZE]:
                self.resize()

            elif c in [curses.KEY_F2]:
                if not self.machifProgExec:
                    if self.remoteClient:
                        self.remoteClient.add_event(gc.EV_CMD_EXIT, 0, -1)
                    else:
                        if self.cmd_line_options.server:
                            self.remoteClient = remote_client.RemoteClientThread(self, host='localhost')
                        else:
                            self.remoteClient = remote_client.RemoteClientThread(self)

            elif c in [curses.KEY_F3]:
                if self.remoteClient:
                    if self.machif:
                        self.remoteClient.add_event(gc.EV_CMD_CLOSE)
                        self.machif = None
                    else:
                        self.remoteClient.add_event(gc.EV_CMD_OPEN)
                        self.machif = self.remoteClient
                else:
                    if self.machif:
                        self.machifProgExec.add_event(gc.EV_CMD_EXIT, 0, -1)
                        self.machif = None
                    else:
                        self.machifProgExec = mi_progexec.MachIfExecuteThread(self)
                        self.machif = self.machifProgExec

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

        self.update_status()
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

                print("> {}".format(str(e.data).strip()))

            elif e.event_id == gc.EV_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HELLO from 0x{:x}".format(id(e.sender)))

            elif e.event_id == gc.EV_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GOOD_BYE from 0x{:x}".format(id(e.sender)))

            elif e.event_id == gc.EV_SER_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_OPEN from 0x{:x} {}".format(id(e.sender), e.sender))

                if self.remoteClient is not None:
                    self.remoteClient.add_event(gc.EV_CMD_GET_STATUS)
                    self.machif = self.remoteClient
                elif self.machifProgExec:
                    self.machif = self.machifProgExec

            elif e.event_id == gc.EV_SER_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_CLOSE from 0x{:x} {}".format(id(e.sender), e.sender))

                self.device_str = ""
                self.machif = None

            elif e.event_id == gc.EV_RMT_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_HELLO from 0x{:x} {}".format(id(e.sender), e.sender))

                print(e.data)

            elif e.event_id == gc.EV_RMT_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_HELLO from 0x{:x} {}".format(id(e.sender), e.sender))

                self.remote_str = ""
                self.device_str = ""

            elif e.event_id == gc.EV_RMT_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_OPEN from 0x{:x} {}".format(id(e.sender), e.sender))

                print(e.data)

                if self.remoteClient is not None:
                    self.remoteClient.add_event(gc.EV_CMD_GET_CONFIG)
                    self.remoteClient.add_event(gc.EV_CMD_GET_SYSTEM_INFO)
                    self.remoteClient.add_event(gc.EV_CMD_GET_SW_STATE)

                    # if self.configData.get('/remote/AutoGcodeRequest', False):
                    #     self.machif.add_event(gc.EV_CMD_GET_GCODE)

            elif e.event_id == gc.EV_RMT_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_CLOSE from 0x{:x} {}".format(id(e.sender), e.sender))

            elif e.event_id == gc.EV_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_EXIT from 0x{:x} {}".format(id(e.sender), e.sender))

                self.remote_str = ""
                self.device_str = ""
                self.remoteClient = None
                self.machifProgExec = None

            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.error("got unknown event!! [{}]".format(str(e.event_id)))

            self.update_status()

    def process_text_queue(self):
        # process text from queue
        try:
            text = text_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if len(text.strip()):
                if text.endswith('\n'):
                    self.stdout_box.addstr(text)
                    # self.stdout_box.addstr("{}\n".format(verbose_data_hex("#", text)))
                else:
                    self.stdout_box.addstr("{}\n".format(text))
                self.stdout_box.refresh()

    def resize(self):
        self.screen.clear()

        self.layout()

        # self.screen.addstr(1, 2, "{} Console {}".format(__appname__, __revision__))
        # self.screen.refresh()

        self.sta_box.erase()
        self.sta_box.resize(self.sta_height, self.sta_width)
        self.sta_box.box()
        self.sta_box.addstr(0, 2, f"{vinfo.__appname__} Console {vinfo.__version__}")
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
                with open("foobar.txt") as gcode_file:
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
                self.process_text_queue()
                self.process_queue()
                self.process_keypad()
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

            if 'r' in data:
                r = data['r']

                if 'machif' in r:
                    firmware_version_str = ""
                    if 'fb' in r:
                        firmware_version_str = r['fb']

                    if 'fv' in r:
                        firmware_version_str = "fb:{} fv:{}".format(firmware_version_str, r['fv'])

                    if len(r['machif']):
                        self.device_str = "{} ({})".format(r['machif'], firmware_version_str)

            if 'swstate' in data:
                self.sw_st = gc.get_sw_status_str(int(data['swstate']))

            if 'rx_data' in data:
                rx_data = str(data['rx_data']).strip()
                print("{}".format(rx_data))

        if (self.cmd_line_options.no_curses is False):
            self.sta_box.erase()
            # self.sta_box.clear()
            self.sta_box.box()

            self.sta_box.addstr(0, 2, f"{vinfo.__appname__} Console {vinfo.__version__}")
            self.sta_box.addstr(2, 2, "{:<30}".format("DRO"), curses.A_REVERSE)

            self.sta_box.addstr(3, 3, "X:{:>9.3f}  ".format(self.posx))
            self.sta_box.addstr(4, 3, "Y:{:>9.3f}  ".format(self.posy))
            self.sta_box.addstr(5, 3, "Z:{:>9.3f}  ".format(self.posz))
            self.sta_box.addstr(6, 3, "FR:{:>8.2f}  ".format(self.feed_rate))
            self.sta_box.addstr(7, 3, "GPOS: {:<19}".format(self.pc_str))

            self.sta_box.addstr(3, 20, "A:{:>9.3f}".format(self.posa))
            self.sta_box.addstr(4, 20, "B:{:>9.3f}".format(self.posb))
            self.sta_box.addstr(5, 20, "C:{:>9.3f}".format(self.posc))
            self.sta_box.addstr(6, 20, "ST:{:>8}".format(self.machif_st))

            self.sta_box.addstr(3, 35, "Soft ST:  {:<8}".format(self.sw_st))
            self.sta_box.addstr(4, 35, "Run time: {:<8}".format(self.run_time))
            self.sta_box.addstr(5, 35, "Device:   {:<8}".format(self.device_str))

            if self.remoteClient:
                try:
                    self.sta_box.addstr(6, 35, "Remote:   {:<8}".format(self.remoteClient.get_hostname()))
                except:
                    pass

            self.sta_box.addstr(9, 3,  "F1 :Help")

            if self.remoteClient:
                self.sta_box.addstr(9, 23, "F2 :Discon Remote")
            else:
                self.sta_box.addstr(9, 23, "F2 :Connect Remote")

            if self.machif:
                self.sta_box.addstr(9, 43, "F3 :Discon Device")
            else:
                self.sta_box.addstr(9, 43, "F3 :Connect Device")

            self.sta_box.addstr(9, 63, "F4 :Load G-code")
            self.sta_box.addstr(10, 3, "F5 :Run")
            self.sta_box.addstr(10, 23, "F6 :Pause")
            self.sta_box.addstr(10, 43, "F7 :Step")
            self.sta_box.addstr(10, 63, "F8 :Stop")
            self.sta_box.addstr(11, 3, "F9 :Queue Flush")
            self.sta_box.addstr(11, 23, "F10:Refresh")
            self.sta_box.addstr(11, 43, "F11:Cycle Start")
            self.sta_box.addstr(11, 63, "F12:Hold")

            # self.sta_box.touchwin()
            self.sta_box.refresh()
            # self.stdout_box.refresh()
