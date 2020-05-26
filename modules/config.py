"""----------------------------------------------------------------------------
   config.py

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
import logging
from logging import handlers, Formatter

import Queue
import wx

try:
    import simplejson as json
except ImportError:
    import json

import os

"""----------------------------------------------------------------------------
   Globals:
----------------------------------------------------------------------------"""
EDIT_BK_COLOR = wx.WHITE
READ_ONLY_BK_COLOR = wx.Colour(242, 241, 240)

FILE_WILDCARD = \
    "gcode (*.ngc; *.nc; *.gcode)|*.ngc;*.nc;*.gcode|"\
    "ngc (*.ngc)|*.ngc|" \
    "nc (*.nc)|*.nc|" \
    "gcode (*.gcode)|*.gcode|" \
    "All files (*.*)|*.*"

ZERO_STRING = "0.000"
NUMBER_FORMAT_STRING = "%0.3f"
ON_STRING = "On"
OFF_STRING = "Off"

CMD_LINE_OPTIONS = {}
CONFIG_DATA = None
STATE_DATA = None

# --------------------------------------------------------------------------
# device commands
# --------------------------------------------------------------------------
DEVICE_CMD_RAPID_LINEAR_MOVE = "G0"      # G00 <AXIS><VAL>
DEVICE_CMD_LINEAR_MOVE = "G1"      # G01 <AXIS><VAL>
DEVICE_CMD_ARC_CW_MOVE = "G2"
DEVICE_CMD_ARC_CCW_MOVE = "G3"
DEVICE_CMD_SPINDLE_CW_ON = "M3"
DEVICE_CMD_SPINDLE_CCW_ON = "M4"
DEVICE_CMD_SPINDLE_OFF = "M5"
DEVICE_CMD_COOLANT_ON = "M7"
DEVICE_CMD_COOLANT_OFF = "M9"
DEVICE_CMD_HOME_AXIS = "G28.2"   # G28.2 <AXIS>0
DEVICE_CMD_SET_AXIS = "G28.3"   # G28.3 <AXIS><VAL>
DEVICE_CMD_ABSOLUTE = "G90"     # G90
DEVICE_CMD_INCREMENTAL = "G91"     # G91
DEVICE_CMD_OFFSET_AXIS = "G92"     # G92 <AXIS><VAL>


# --------------------------------------------------------------------------
# state machine states and transition
# --------------------------------------------------------------------------

""" ------------------------------------------------------------------------

STATE TABLE::
state| RUN   | PAUSE | STEP  | STOP  | BRK PT| ERROR | ST END| ABORT | SER CL|
------------------------------------------------------------------------------
ABORT| IGNORE| IGNORE| IGNORE| IDLE  | IGNORE| IGNORE| IGNORE| IGNORE| IDLE  |
------------------------------------------------------------------------------
IDLE | RUN   | IGNORE| STEP  | IGNORE| IGNORE| IGNORE| IGNORE| ABORT | IGNORE|
------------------------------------------------------------------------------
RUN  | IGNORE| PAUSE | IGNORE| IDLE  | BREAK | BREAK | IDLE  | ABORT | IDLE  |
------------------------------------------------------------------------------
STEP | RUN   | PAUSE | IGNORE| IDLE  | IGNORE| IDLE  | IDLE  | ABORT | IDLE  |
------------------------------------------------------------------------------
BREAK| RUN   | PAUSE | STEP  | IDLE  | IGNORE| IDLE  | IGNORE| ABORT | IDLE  |
------------------------------------------------------------------------------
PAUSE| RUN   | IGNORE| STEP  | IDLE  | IGNORE| IDLE  | IGNORE| ABORT | IDLE  |
------------------------------------------------------------------------------
USER | IGNORE| IGNORE| IGNORE| IGNORE| IGNORE| IDLE  | IDLE  | ABORT | IDLE  |
------------------------------------------------------------------------------

------------------------------------------------------------------------ """

STATE_ABORT = 1
STATE_IDLE = 100
STATE_RUN = 200
STATE_STEP = 300
STATE_BREAK = 400
STATE_PAUSE = 500

'''
Notes:
Abort state is a special state, where the serial thread is waiting to be
terminated, there will not be any state transition until serial port is
open again and will start in IDLE state.

'''
# --------------------------------------------------------------------------
# Thread/MainWindow communication events
# --------------------------------------------------------------------------
# EVENT ID             EVENT CODE
EV_CMD_NULL = 100
EV_CMD_EXIT = 200
EV_CMD_OPEN = 300
EV_CMD_RUN = 1000
EV_CMD_STEP = 1010
EV_CMD_STOP = 1020
EV_CMD_SEND = 1030
EV_CMD_SEND_W_ACK = 1040
EV_CMD_AUTO_STATUS = 1050
EV_CMD_OK_TO_POST = 1060
EV_CMD_GET_STATUS = 1070
EV_CMD_SER_TXDATA = 1080
EV_CMD_CYCLE_START = 1090
EV_CMD_FEED_HOLD = 1100
EV_CMD_QUEUE_FLUSH = 1110
EV_CMD_RESET = 1120
EV_CMD_MOVE = 1130
EV_CMD_MOVE_RELATIVE = 1140
EV_CMD_RAPID_MOVE = 1160
EV_CMD_RAPID_MOVE_RELATIVE = 1170
EV_CMD_CLEAR_ALARM = 1180
EV_CMD_PROBE = 1190
EV_CMD_SET_AXIS = 1200
EV_CMD_HOME = 1210
EV_CMD_JOG_MOVE = 1220
EV_CMD_JOG_MOVE_RELATIVE = 1230
EV_CMD_JOG_RAPID_MOVE = 1240
EV_CMD_JOG_RAPID_MOVE_RELATIVE = 1250
EV_CMD_JOG_STOP = 1260


EV_NULL = 100
EV_HELLO = 110
EV_GOODBY = 120
EV_EXIT = 200
EV_ABORT = 2000
EV_RUN_END = 2010
EV_STEP_END = 2020
EV_DATA_OUT = 2030
EV_DATA_IN = 2040
EV_HIT_BRK_PT = 2050
EV_PC_UPDATE = 2060
EV_HIT_MSG = 2070
EV_SER_RXDATA = 2080
EV_SER_TXDATA = 2090
EV_SER_PORT_OPEN = 2100
EV_SER_PORT_CLOSE = 2110
EV_TIMER = 2120
EV_DATA_STATUS = 2130
EV_DEVICE_DETECTED = 2140

# --------------------------------------------------------------------------
# VERBOSE MASK
# --------------------------------------------------------------------------
VERBOSE_MASK = 0

VERBOSE_MASK_UI = 0x000000FF
VERBOSE_MASK_UI_EV = 0x00000001
VERBOSE_MASK_MACHIF = 0x0000FF00
VERBOSE_MASK_MACHIF_EXEC = 0x00000F00
VERBOSE_MASK_MACHIF_EXEC_EV = 0x00000100
VERBOSE_MASK_MACHIF_MOD = 0x0000F000
VERBOSE_MASK_MACHIF_MOD_EV = 0x00001000
VERBOSE_MASK_MACHIF_EV = \
    VERBOSE_MASK_MACHIF_EXEC_EV | VERBOSE_MASK_MACHIF_EXEC_EV
VERBOSE_MASK_SERIALIF = 0x000F0000
VERBOSE_MASK_SERIALIF_STR = 0x00010000
VERBOSE_MASK_SERIALIF_HEX = 0x00020000
VERBOSE_MASK_SERIALIF_EV = 0x00040000
VERBOSE_MASK_EVENTIF = \
    VERBOSE_MASK_MACHIF_EXEC_EV | VERBOSE_MASK_MACHIF_MOD_EV |\
    VERBOSE_MASK_SERIALIF_EV


def decode_verbose_mask_string(verbose_mask_str):
    """ Decode and init gc VERBOSE_MASK
    """
    global VERBOSE_MASK

    mask_list = verbose_mask_str.split(",")

    for mask in mask_list:
        mask = str(mask).lower()
        if "ui" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_UI

        if "ui_ev" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_UI_EV

        if "machif" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_MACHIF

        if "machif_ev" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_MACHIF_EV

        if "machif_exec" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_MACHIF_EXEC

        if "machif_exec_ev" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_MACHIF_EXEC_EV

        if "machif_mod" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_MACHIF_MOD

        if "machif_mod_ev" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_MACHIF_MOD_EV

        if "serialif" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_SERIALIF

        if "serialif_str" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_SERIALIF_STR

        if "serialif_hex" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_SERIALIF_HEX

        if "serialif_ev" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_SERIALIF_EV

        if "eventif" == mask:
            VERBOSE_MASK |= VERBOSE_MASK_EVENTIF

    return VERBOSE_MASK


# --------------------------------------------------------------------------
# LOGGING MASK
# --------------------------------------------------------------------------

def init_logger(filename):
    log_path = filename

    logger = logging.getLogger()

    ch = logging.StreamHandler()
    # ch_format = Formatter("%(levelname)s : %(message)s")
    ch_format = Formatter("%(asctime)s - m:%(module)s l:%(lineno)d >> "
                          "%(levelname)s :"
                          "%(message)s",
                          datefmt='%Y%m%d %I:%M:%S %p')
    ch.setFormatter(ch_format)
    logger.addHandler(ch)

    # create a rotating file handler and add it to the logger
    # fh = handlers.RotatingFileHandler(log_path,
    #   maxBytes=5000000, backupCount=4)
    # fh_format = Formatter("%(asctime)s - m:%(module)s l:%(lineno)d "
    #                       "t:%(thread)d >> %(levelname)s : %(message)s",
    #                       datefmt='%Y%m%d %I:%M:%S %p')
    # fh.setFormatter(log_format)
    # logger.addHandler(handler)

    # set the root logging level
    logger.setLevel(logging.INFO)

    # logger.info('>>> start')


def init_config(cmd_line_options, config_file, log_file):
    """ Initialize config vars
    """
    global CMD_LINE_OPTIONS
    global CONFIG_DATA
    global STATE_DATA

    CMD_LINE_OPTIONS = cmd_line_options

    init_logger('log_file')

    CONFIG_DATA = gsatConfigData(config_file)
    CONFIG_DATA.load()

    STATE_DATA = gsatStateData()


class gsatStateData():
    """ Provides various data information
    """

    def __init__(self):

        # state status
        self.swState = STATE_IDLE

        # link status
        self.grblDetected = False
        self.serialPortIsOpen = False
        self.serialPort = ""
        self.serialPortBaud = "115200"
        self.machIfId = 0
        self.machIfName = "None"
        self.deviceDetected = False

        # machine status
        self.machineStatusAutoRefresh = False
        self.machineStatusAutoRefreshPeriod = 1
        self.machineStatusString = "Idle"

        # program status
        self.programCounter = 0
        self.breakPoints = set()
        self.fileIsOpen = False
        self.gcodeFileName = ""
        self.gcodeFileLines = []


class ConfigData(object):
    """ Provides various data information
    """
    def __init__(self, config_fname=None):

        self.configFileName = config_fname

        self.datastore = dict()

    def add(self, key_path, val):
        """ Add new key value pair
        """
        if type(key_path) is list:
            key_list = key_path
        else:
            key_list = key_path.split("/")

            if key_list[0] == "":
                key_list.pop(0)

        node = self.get(key_list[:-1])

        if node is None:
            node = self.datastore

            for key in key_list[:-1]:
                if key in node:
                    node = node[key]
                else:
                    node[key] = dict()
                    node = node[key]

        node[key_list[-1:][0]] = val

    def get(self, key_path, defualt_rv=None):
        """ Get value for a given key
        """
        return_val = defualt_rv

        if type(key_path) is list:
            key_list = key_path
        else:
            key_list = key_path.split("/")

            if key_list[0] == "":
                key_list.pop(0)

        if key_list:
            node = self.datastore

            for key in key_list:
                if key in node:
                    node = node[key]
                else:
                    key = None
                    break

            if key is not None:
                return_val = node

        return return_val

    def set(self, key_path, val):
        """ Set value for a given key
        """
        self.add(key_path, val)

    def load(self):
        """ Load data from config file
        """
        if self.configFileName is not None:
            if os.path.exists(self.configFileName):
                datastore = dict()

                with open(self.configFileName, 'r') as f:
                    datastore = json.load(f)

                # need to do deep merge, update not sufficient
                def deep_update(destination_dict, source_dict):
                    for key in source_dict.keys():
                        if isinstance(source_dict[key], dict):
                            # get node or create one
                            node = destination_dict.setdefault(key, {})
                            deep_update(node, source_dict[key])
                        else:
                            destination_dict[key] = source_dict[key]

                deep_update(self.datastore, datastore)

    def save(self):
        """ Save data to config file
        """
        if self.configFileName is not None:
            with open(self.configFileName, 'w') as f:
                json.dump(self.datastore, f, indent=3, sort_keys=True)

    def dump(self):
        """ dups config to stdout
        """
        data = json.dumps(self.datastore, indent=3, sort_keys=True)
        print data


class gsatConfigData(ConfigData):
    """ Provides various data information
    """
    configDefault = {
        "cli": {
            "CmdHistory": "",
            "CmdMaxHistory": 100,
            "SaveCmdHistory": True,
        },
        "code": {
            "AutoScroll": 3,
            "AxisHighlight": "#ff0000",
            "CaretLine": True,
            "CaretLineBackground": "#EFEFEF",
            "CaretLineForeground": "#000000",
            "CommentsHighlight": "#007F00",
            "FontFace": "System",
            "FontSize": -1,
            "FontStyle": "normal",
            "GCodeHighlight": "#0000ff",
            "GCodeLineNumberHighlight": "#BFBFBF",
            "LineNumber": True,
            "LineNumberBackground": "#99A9C2",
            "LineNumberForeground": "#000000",
            "MCodeHighlight": "#7f007f",
            "Parameters2Highlight": "#f4b730",
            "ParametersHighlight": "#ff0000",
            "ReadOnly": True,
            "WindowBackground": "#FFFFFF",
            "WindowForeground": "#000000"
        },
        "cv2": {
            "CaptureDevice": 0,
            "CaptureHeight": 480,
            "CapturePeriod": 100,
            "CaptureWidth": 640,
            "Crosshair": True,
            "Enable": False
        },
        "jogging": {
            "AutoMPOS": False,
            "CustomButtons" : {
                "Custom1": {
                    "Label": "Custom 1",
                    "Script": "",
                },
                "Custom2": {
                    "Label": "Custom 2",
                    "Script": "",
                },
                "Custom3": {
                    "Label": "Custom 3",
                    "Script": "",
                },
                "Custom4": {
                    "Label": "Custom 4",
                    "Script": "",
                }
            },
            "JogFeedRate": 1000,
            "JogInteractive": False,
            "JogRapid": True,
            "NumKeypadPendant": False,
            "ProbeDistance": 19.6,
            "ProbeFeedRate": 100.0,
            "ProbeMaxDistance": -40.0,
            "ReqUpdateOnJogSetOp": True,
            "SpindleSpeed": 12000,
            "XYZReadOnly": False,
            "ZJogSafeMove": False
        },
        "machine": {
            "AutoRefresh": True,
            "AutoRefreshPeriod": 200,
            "AutoStatus": False,
            "Baud": "115200",
            "Device": "grbl",
            "InitScript": "",
            "InitScriptEnable": True,
            "Port": ""
        },
        "mainApp": {
            "BackupFile": True,
            "DisplayRunTimeDialog": True,
            "RoundInch2mm": 4,
            "Roundmm2Inch": 4,
            "FileHistory": {
                "FilesMaxHistory": 10,
            },
        },
        "output": {
            "AutoScroll": 2,
            "CaretLine": False,
            "CaretLineBackground": "#C299A9",
            "CaretLineForeground": "#000000",
            "FontFace": "System",
            "FontSize": -1,
            "FontStyle": "normal",
            "LineNumber": False,
            "LineNumberBackground": "#FFFFFF",
            "LineNumberForeground": "#000000",
            "ReadOnly": False,
            "WindowBackground": "#FFFFFF",
            "WindowForeground": "#000000"
        }
    }

    def __init__(self, config_fname):
        super(gsatConfigData, self).__init__(config_fname)
        self.datastore.update(self.configDefault)


"""----------------------------------------------------------------------------
   EVENTS definitions to interact with multiple windows:
----------------------------------------------------------------------------"""
EVT_THREAD_QUEQUE_EVENT_ID = 0x7ECAFE


def reg_thread_queue_data_event(win, func):
    """ register for thread queue data event.
    """
    win.Connect(-1, -1, EVT_THREAD_QUEQUE_EVENT_ID, func)


class ThreadQueueEvent(wx.PyEvent):
    """ Simple event to carry arbitrary data.
    """

    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_THREAD_QUEQUE_EVENT_ID)
        self.data = data


class SimpleEvent(object):
    """ Simple event to carry arbitrary data.
    """

    def __init__(self, event_id, data, sender=None):
        self.event_id = event_id
        self.data = data
        self.sender = sender


class EventQueueIf():
    """ Class that implement simple queue APIs
    """

    def __init__(self):
        self._eventListeners = dict()
        self._eventQueue = Queue.Queue()

    def addEventListener(self, listener):
        self._eventListeners[id(listener)] = listener

    def eventPut(self, event_id, event_data=None, sender=None):
        self._eventQueue.put(SimpleEvent(event_id, event_data, sender))

    def notifyEventListeners(self, event_id, data=None):
        for listener in self._eventListeners.keys():
            self._eventListeners[listener].eventPut(event_id, data, self)

    def removeEventListener(self, listener):
        if id(listener) in self._eventListeners:
            self._eventListeners.pop(id(listener))
