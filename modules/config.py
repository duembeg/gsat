"""----------------------------------------------------------------------------
   config.py

   Copyright (C) 2013-2017 Wilhelm Duembeg

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

import wx

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
state    | RUN UI  | PAUSE UI| STEP UI | STOP UI |  BREAK PT| ERROR   | ST END  | ABORT   | SER CLOSE |
-------------------------------------------------------------------------------------------------------
ABORT    | IGNORED | IGNORE  | IGNORE  | IDLE    |  IGNORE  | IGNORE  | IGNORE  | IGNORE  | IDLE      |
-------------------------------------------------------------------------------------------------------
IDLE     | RUN     | IGNORE  | STEP    | IGNORE  |  IGNORE  | IGNORE  | IGNORE  | ABORT   | IGNORE    |
-------------------------------------------------------------------------------------------------------
RUN      | IGNORE  | PAUSE   | IGNORE  | IDLE    |  BREAK   | IDLE    | IDLE    | ABORT   | IDLE      |
-------------------------------------------------------------------------------------------------------
STEP     | RUN     | PAUSE   | IGNORE  | IDLE    |  IGNORE  | IDLE    | IDLE    | ABORT   | IDLE      |
-------------------------------------------------------------------------------------------------------
BREAK    | RUN     | PAUSE   | STEP    | IDLE    |  IGNORE  | IDLE    | IGNORE  | ABORT   | IDLE      |
-------------------------------------------------------------------------------------------------------
PAUSE    | RUN     | IGNORE  | STEP    | IDLE    |  IGNORE  | IDLE    | IGNORE  | ABORT   | IDLE      |
-------------------------------------------------------------------------------------------------------
USER     | IGNORE  | IGNORE  | IGNORE  | IGNORE  |  IGNORE  | IDLE    | IDLE    | ABORT   | IDLE      |
---------------------------------------------------------------------------------

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
EV_CMD_RELATIVE_MOVE = 1150
EV_CMD_RAPID_MOVE = 1160
EV_CMD_RAPID_MOVE_RELATIVE = 1170
EV_CMD_CLEAR_ALARM = 1180
EV_CMD_PROBE = 1190
EV_CMD_SET_AXIS = 1200
EV_CMD_HOME = 1210


EV_NULL = 100
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


def init_config(cmd_line_options, config_data, state_data):
    """ Initialize config vars
    """
    global CMD_LINE_OPTIONS
    global CONFIG_DATA
    global STATE_DATA

    CMD_LINE_OPTIONS = cmd_line_options
    CONFIG_DATA = config_data
    STATE_DATA = state_data

class gsatStateData():
    """-------------------------------------------------------------------------
    provides various data information
    -------------------------------------------------------------------------"""
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


class gsatConfigData():
    """-------------------------------------------------------------------------
    provides various data information
    -------------------------------------------------------------------------"""

    def __init__(self):
        # -----------------------------------------------------------------------
        # config keys

        self.config = {
            #  key                                 CanEval, Default Value
            # main app keys
            '/mainApp/DisplayRunTimeDialog': (True, True),
            '/mainApp/BackupFile': (True, True),
            '/mainApp/MaxFileHistory': (True, 10),
            '/mainApp/RoundInch2mm': (True, 4),
            '/mainApp/Roundmm2Inch': (True, 4),
            #'/mainApp/DefaultLayout/Dimensions' :(False, ""),
            #'/mainApp/DefaultLayout/Perspective':(False, ""),
            #'/mainApp/ResetLayout/Dimensions'   :(False, ""),
            #'/mainApp/ResetLayout/Perspective'  :(False, ""),

            # code keys
            # 0:NoAutoScroll 1:AlwaysAutoScroll 2:SmartAutoScroll 3:OnGoToPCAutoScroll
            '/code/AutoScroll': (True, 3),
            '/code/CaretLine': (True, True),
            '/code/CaretLineForeground': (False, '#000000'),
            # C299A9 #A9C299, 9D99C2
            '/code/CaretLineBackground': (False, '#EFEFEF'),
            '/code/LineNumber': (True, True),
            '/code/LineNumberForeground': (False, '#000000'),
            '/code/LineNumberBackground': (False, '#99A9C2'),
            '/code/ReadOnly': (True, True),
            '/code/WindowForeground': (False, '#000000'),
            '/code/WindowBackground': (False, '#FFFFFF'),
            '/code/GCodeHighlight': (False, '#0000ff'),  # 0000FF'
            '/code/MCodeHighlight': (False, '#7f007f'),  # 742b77
            '/code/AxisHighlight': (False, '#ff0000'),  # 007F00
            '/code/ParametersHighlight': (False, '#ff0000'),
            '/code/Parameters2Highlight': (False, '#f4b730'),
            '/code/GCodeLineNumberHighlight': (False, '#BFBFBF'),
            '/code/CommentsHighlight': (False, '#007F00'),  # FFC300


            # output keys
            # 0:NoAutoScroll 1:AlwaysAutoScroll 2:SmartAutoScroll
            '/output/AutoScroll': (True, 2),
            '/output/CaretLine': (True, False),
            '/output/CaretLineForeground': (False, '#000000'),
            '/output/CaretLineBackground': (False, '#C299A9'),
            '/output/LineNumber': (True, False),
            '/output/LineNumberForeground': (False, '#000000'),
            '/output/LineNumberBackground': (False, '#FFFFFF'),
            '/output/ReadOnly': (True, False),
            '/output/WindowForeground': (False, '#000000'),
            '/output/WindowBackground': (False, '#FFFFFF'),


            # link keys
            '/link/Port': (False, ""),
            '/link/Baud': (False, "115200"),

            # cli keys
            '/cli/SaveCmdHistory': (True, True),
            '/cli/CmdMaxHistory': (True, 100),
            '/cli/CmdHistory': (False, ""),

            # machine keys
            '/machine/Device': (False, "grbl"),
            '/machine/Port': (False, ""),
            '/machine/Baud': (False, "115200"),
            '/machine/AutoStatus': (True, False),
            '/machine/AutoRefresh': (True, False),
            '/machine/AutoRefreshPeriod': (True, 200),
            '/machine/InitScriptEnable': (True, True),
            '/machine/InitScript': (False, ""),

            # jogging keys
            '/jogging/XYZReadOnly': (True, False),
            '/jogging/AutoMPOS': (True, True),
            '/jogging/ReqUpdateOnJogSetOp': (True, True),
            '/jogging/NumKeypadPendant': (True, False),
            '/jogging/ZJogMovesLast': (True, False),
            '/jogging/Custom1Label': (False, "Custom 1"),
            '/jogging/Custom1Script': (False, ""),
            '/jogging/Custom2Label': (False, "Custom 2"),
            '/jogging/Custom2Script': (False, ""),
            '/jogging/Custom3Label': (False, "Custom 3"),
            '/jogging/Custom3Script': (False, ""),
            '/jogging/Custom4Label': (False, "Custom 4"),
            '/jogging/Custom4Script': (False, ""),
            '/jogging/SpindleSpeed': (True, 12000),
            '/jogging/ProbeDistance': (True, 19.6000),
            '/jogging/ProbeMaxDistance': (True, -40.0000),
            '/jogging/ProbeFeedRate': (True, 100.0000),
            '/jogging/JogFeedRate': (True, 1000),
            '/jogging/RapidJog': (True, True),

            # CV2 keys
            '/cv2/Enable': (True, False),
            '/cv2/Crosshair': (True, True),
            '/cv2/CaptureDevice': (True, 0),
            '/cv2/CapturePeriod': (True, 100),
            '/cv2/CaptureWidth': (True, 640),
            '/cv2/CaptureHeight': (True, 480),
        }

    def add(self, key, val, canEval=True):
        """ Add new key value pair
        """
        self.config[key] = (canEval, val)

    def get(self, key):
        """ Get value for a given key
        """
        retVal = None
        if key in self.config.keys():
            configEntry = self.config.get(key)
            retVal = configEntry[1]

        return retVal

    def set(self, key, val):
        """ Set value for a given key
        """
        if key in self.config.keys():
            configEntry = self.config.get(key)
            self.config[key] = (configEntry[0], val)

    def load(self, configFile):
        """ Load data from config file
        """
        for key in self.config.keys():
            configEntry = self.config.get(key)
            configRawData = str(configFile.Read(key))

            if len(configRawData) > 0:
                if configEntry[0]:
                    configData = eval(configRawData)
                else:
                    configData = configRawData

                self.config[key] = (configEntry[0], configData)

    def save(self, configFile):
        """ Save data to config file
        """
        keys = sorted(self.config.keys())
        for key in keys:
            configEntry = self.config.get(key)
            configFile.Write(key, str(configEntry[1]))


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


class SimpleEvent():
    """ Simple event to carry arbitrary data.
    """
    def __init__(self, event_id, data):
        self.event_id = event_id
        self.data = data
