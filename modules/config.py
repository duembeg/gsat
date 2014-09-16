"""----------------------------------------------------------------------------
   config.py

   Copyright (C) 2013-2014 Wilhelm Duembeg

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
gEdityBkColor = wx.WHITE
gReadOnlyBkColor = wx.Colour(242, 241, 240)


gWILDCARD = \
   "ngc (*.ngc)|*.ngc|" \
   "nc (*.nc)|*.nc|" \
   "gcode (*.gcode)|*.gcode|" \
   "All files (*.*)|*.*"

gZeroString = "0.000"
gNumberFormatString = "%0.3f"
gOnString = "On"
gOffString = "Off"

# --------------------------------------------------------------------------
# device commands
# --------------------------------------------------------------------------
gDEVICE_CMD_GO_TO_POS         = "G00 <AXIS><VAL>\n"
gDEVICE_CMD_ALL_GO_TO_POS     = "G00 X<XVAL> Y<YVAL> Z<ZVAL>\n"
gDEVICE_CMD_JOG_X             = "G00 X<VAL>\n"
gDEVICE_CMD_JOG_Y             = "G00 Y<VAL>\n"
gDEVICE_CMD_JOG_Z             = "G00 Z<VAL>\n"
gDEVICE_CMD_SPINDLE_ON        = "M3\n"
gDEVICE_CMD_SPINDLE_OFF       = "M5\n"

# --------------------------------------------------------------------------
# TinyG/TinyG2 commands
# --------------------------------------------------------------------------
gTINYG_CMD_GET_STATUS         = "?\n"
gTINYG_CMD_RESET_TO_VAL       = "G28.3 <AXIS><VAL>\n"
gTINYG_CMD_ALL_RESET_TO_VAL   = "G28.3 X<XVAL> Y<YVAL> Z<ZVAL>\n"
gTINYG_CMD_GO_HOME            = "G28.2 <AXIS>0\n"
gTINYG_CMD_ALL_GO_HOME        = "G28.2 X0 Y0 Z0\n"

# --------------------------------------------------------------------------
# Grbl commands
# --------------------------------------------------------------------------
gGRBL_CMD_GET_STATUS          = "?\n"
gGRBL_CMD_RESET_TO_VAL        = "G92 <AXIS><VAL>\n"
gGRBL_CMD_ALL_RESET_TO_VAL    = "G92 X<XVAL> Y<YVAL> Z<ZVAL>\n"
gGRBL_CMD_GO_HOME             = "G28.2 <AXIS>0\n"
gGRBL_CMD_ALL_GO_HOME         = "G28.2 X0 Y0 Z0\n"

# --------------------------------------------------------------------------
# state machine states and transition
# --------------------------------------------------------------------------

""" ------------------------------------------------------------------------

STATE TABLE::
state    | RUN UI  | STOP UI | STEP UI | BREAK PT| ERROR   | ST END  | ABORT   |
--------------------------------------------------------------------------------
ABORT    | IGNORED | IGNORE  | IGNORE  | IGNORE  | IGNORE  | IGNORE  | IGNORE  |
---------------------------------------------------------------------------------
IDLE     | RUN     | IGNORE  | STEP    | IGNORE  | IGNORE  | IGNORE  | ABORT   |
---------------------------------------------------------------------------------
RUN      | IGNORE  | IDLE    | IGNORE  | BREAK   | IDLE    | IDLE    | ABORT   |
---------------------------------------------------------------------------------
STEP     | IGNORE  | IDLE    | IGNORE  | IGNORE  | IDLE    | IDLE    | ABORT   |
---------------------------------------------------------------------------------
BREAK    | RUN     | IDLE    | STEP    | IGNORE  | IDLE    | IGNORE  | ABORT   |
---------------------------------------------------------------------------------
USER     | IGNORE  | IGNORE  | IGNORE  | IGNORE  | IDLE    | IDLE    | ABORT   |
---------------------------------------------------------------------------------

------------------------------------------------------------------------ """

gSTATE_ABORT  = 001
gSTATE_IDLE  =  100
gSTATE_RUN   =  200
gSTATE_STEP  =  300
gSTATE_BREAK =  400

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
gEV_CMD_NULL         = 0100
gEV_CMD_EXIT         = 1000
gEV_CMD_RUN          = 1030
gEV_CMD_STEP         = 1040
gEV_CMD_STOP         = 1050
gEV_CMD_SEND         = 1060
gEV_CMD_SEND_W_ACK   = 1062
gEV_CMD_AUTO_STATUS  = 1070

gEV_NULL             = 0100
gEV_ABORT            = 2000
gEV_RUN_END          = 2010
gEV_STEP_END         = 2020
gEV_DATA_OUT         = 2030
gEV_DATA_IN          = 2040
gEV_HIT_BRK_PT       = 2050
gEV_PC_UPDATE        = 2060
gEV_HIT_MSG          = 2070
gEV_SER_RXDATA       = 2080

# --------------------------------------------------------------------------
# Device type
# --------------------------------------------------------------------------
gDEV_NONE            = 0000
gDEV_GRBL            = 1000
gDEV_TINYG           = 1100
gDEV_TINYG2          = 1200

gDEV_LIST = ["None", "Grbl", "TinyG", "TinyG2"]

"""----------------------------------------------------------------------------
   gsatStateData:
   provides various data information
----------------------------------------------------------------------------"""
class gsatStateData():
   def __init__(self):

      # state status
      self.swState = gSTATE_IDLE

      # link status
      self.grblDetected = False
      self.serialPortIsOpen = False
      self.serialPort = ""
      self.serialPortBaud = "9600"
      self.deviceID = 0
      self.deviceDetected = False

      # machine status
      self.machineStatusAutoRefresh = False
      self.machineStatusAutoRefreshPeriod = 1
      self.machineStatusString ="Idle"

      # program status
      self.programCounter = 0
      self.breakPoints = set()
      self.fileIsOpen = False
      self.gcodeFileName = ""
      self.gcodeFileLines = []

"""----------------------------------------------------------------------------
   gsatStateData:
   provides various data information
----------------------------------------------------------------------------"""
class gsatConfigData():
   def __init__(self):
      # -----------------------------------------------------------------------
      # config keys

      self.config = {
      #  key                                 CanEval, Default Value
      # main app keys
         '/mainApp/BackupFile'               :(True , True),
         '/mainApp/MaxFileHistory'           :(True , 8),
         '/mainApp/RoundInch2mm'             :(True , 4),
         '/mainApp/Roundmm2Inch'             :(True , 4),
         #'/mainApp/DefaultLayout/Dimensions' :(False, ""),
         #'/mainApp/DefaultLayout/Perspective':(False, ""),
         #'/mainApp/ResetLayout/Dimensions'   :(False, ""),
         #'/mainApp/ResetLayout/Perspective'  :(False, ""),

      # code keys
         # 0:NoAutoScroll 1:AlwaysAutoScroll 2:SmartAutoScroll 3:OnGoToPCAutoScroll
         '/code/AutoScroll'                  :(True , 3),
         '/code/CaretLine'                   :(True , True),
         '/code/CaretLineForeground'         :(False, '#000000'),
         '/code/CaretLineBackground'         :(False, '#EFEFEF'), #C299A9 #A9C299, 9D99C2
         '/code/LineNumber'                  :(True , True),
         '/code/LineNumberForeground'        :(False, '#000000'),
         '/code/LineNumberBackground'        :(False, '#99A9C2'),
         '/code/ReadOnly'                    :(True , True),
         '/code/WindowForeground'            :(False, '#000000'),
         '/code/WindowBackground'            :(False, '#FFFFFF'),
         '/code/GCodeHighlight'              :(False, '#0000FF'),
         '/code/AxisHighlight'               :(False, '#007F00'), #007F7F
         '/code/ParametersHighlight'         :(False, '#7F0000'),
         '/code/GCodeLineNumberHighlight'    :(False, '#BFBFBF'),
         '/code/CommentsHighlight'           :(False, '#FFC300'),


      # output keys
         # 0:NoAutoScroll 1:AlwaysAutoScroll 2:SmartAutoScroll
         '/output/AutoScroll'                :(True , 2),
         '/output/CaretLine'                 :(True , False),
         '/output/CaretLineForeground'       :(False, '#000000'),
         '/output/CaretLineBackground'       :(False, '#C299A9'),
         '/output/LineNumber'                :(True , False),
         '/output/LineNumberForeground'      :(False, '#000000'),
         '/output/LineNumberBackground'      :(False, '#FFFFFF'),
         '/output/ReadOnly'                  :(True , False),
         '/output/WindowForeground'          :(False, '#000000'),
         '/output/WindowBackground'          :(False, '#FFFFFF'),


      # link keys
         '/link/Port'                        :(False, ""),
         '/link/Baud'                        :(False, "9600"),

      # cli keys
         '/cli/SaveCmdHistory'               :(True , True),
         '/cli/CmdMaxHistory'                :(True , 100),
         '/cli/CmdHistory'                   :(False, ""),

      # machine keys
         '/machine/Device'                   :(False, "None"),
         '/machine/AutoRefresh'              :(True , False),
         '/machine/AutoRefreshPeriod'        :(True , 1000),
         '/machine/InitScript'               :(False, ""),

      # jogging keys
         '/jogging/XYZReadOnly'              :(True , False),
         '/jogging/AutoMPOS'                 :(True , True),
         '/jogging/ReqUpdateOnJogSetOp'      :(True , True),
         '/jogging/Custom1Label'             :(False, "Custom 1"),
         '/jogging/Custom1XIsOffset'         :(True , True),
         '/jogging/Custom1XValue'            :(True , 0),
         '/jogging/Custom1YIsOffset'         :(True , True),
         '/jogging/Custom1YValue'            :(True , 0),
         '/jogging/Custom1ZIsOffset'         :(True , True),
         '/jogging/Custom1ZValue'            :(True , 0),
         '/jogging/Custom2Label'             :(False, "Custom 2"),
         '/jogging/Custom2XIsOffset'         :(True , True),
         '/jogging/Custom2XValue'            :(True , 0),
         '/jogging/Custom2YIsOffset'         :(True , True),
         '/jogging/Custom2YValue'            :(True , 0),
         '/jogging/Custom2ZIsOffset'         :(True , True),
         '/jogging/Custom2ZValue'            :(True , 0),
         '/jogging/Custom3Label'             :(False, "Custom 3"),
         '/jogging/Custom3XIsOffset'         :(True , True),
         '/jogging/Custom3XValue'            :(True , 0),
         '/jogging/Custom3YIsOffset'         :(True , True),
         '/jogging/Custom3YValue'            :(True , 0),
         '/jogging/Custom3ZIsOffset'         :(True , True),
         '/jogging/Custom3ZValue'            :(True , 0),
         '/jogging/Custom4Label'             :(False, "Custom 4"),
         '/jogging/Custom4XIsOffset'         :(True , True),
         '/jogging/Custom4XValue'            :(True , 0),
         '/jogging/Custom4YIsOffset'         :(True , True),
         '/jogging/Custom4YValue'            :(True , 0),
         '/jogging/Custom4ZIsOffset'         :(True , True),
         '/jogging/Custom4ZValue'            :(True , 0),


      # CV2 keys
         '/cv2/Enable'                       :(True , False),
         '/cv2/Crosshair'                    :(True , True),
         '/cv2/CaptureDevice'                :(True , 0),
         '/cv2/CapturePeriod'                :(True , 100),
         '/cv2/CaptureWidth'                 :(True , 640),
         '/cv2/CaptureHeight'                :(True , 480),
      }

   def Add(self, key, val, canEval=True):
      configEntry = self.config.get(key)
      self.config[key] = (canEval, val)

   def Get(self, key):
      retVal = None
      if key in self.config.keys():
         configEntry = self.config.get(key)
         retVal = configEntry[1]

      return retVal

   def Set(self, key, val):
      if key in self.config.keys():
         configEntry = self.config.get(key)
         self.config[key] = (configEntry[0], val)

   def Load(self, configFile):
      for key in self.config.keys():
         configEntry = self.config.get(key)
         configRawData = str(configFile.Read(key))

         if len(configRawData) > 0:
            if configEntry[0]:
               configData = eval(configRawData)
            else:
               configData = configRawData

            self.config[key] = (configEntry[0], configData)

   def Save(self, configFile):
      keys = sorted(self.config.keys())
      for key in keys:
         configEntry = self.config.get(key)
         configFile.Write(key, str(configEntry[1]))


"""----------------------------------------------------------------------------
   EVENTS definitions to interact with multiple windows:
----------------------------------------------------------------------------"""
EVT_THREAD_QUEQUE_EVENT_ID = 0x7ECAFE

def EVT_THREAD_QUEUE_EVENT(win, func):
   """Define thread data event."""
   win.Connect(-1, -1, EVT_THREAD_QUEQUE_EVENT_ID, func)

class threadQueueEvent(wx.PyEvent):
   """Simple event to carry arbitrary data."""
   def __init__(self, data):
      """Init Result Event."""
      wx.PyEvent.__init__(self)
      self.SetEventType(EVT_THREAD_QUEQUE_EVENT_ID)
      self.data = data

class threadEvent():
   def __init__(self, event_id, data):
      self.event_id = event_id
      self.data = data


