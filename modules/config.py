"""----------------------------------------------------------------------------
   config.py
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

gZeroString = "0.0000"
gNumberFormatString = "%0.4f"
gOnString = "On"
gOffString = "Off"

# --------------------------------------------------------------------------
# Grbl commands
# --------------------------------------------------------------------------
gGRBL_CMD_GET_STATUS          = "?\n"
gGRBL_CMD_RESET_TO_ZERO_POS   = "G92 X0 Y0 Z0\n"
gGRBL_CMD_RESET_TO_VAL_POS    = "G92 X<XVAL> Y<YVAL> Z<ZVAL>\n"
gGRBL_CMD_GO_ZERO             = "G00 X0 Y0 Z0\n"
gGRBL_CMD_GO_POS              = "G00 X<XVAL> Y<YVAL> Z<ZVAL>\n"
gGRBL_CMD_EXE_HOME_CYCLE      = "G28 X0 Y0 Z0\n"
gGRBL_CMD_JOG_X               = "G00 X<VAL>\n"
gGRBL_CMD_JOG_Y               = "G00 Y<VAL>\n"
gGRBL_CMD_JOG_Z               = "G00 Z<VAL>\n"
gGRBL_CMD_SPINDLE_ON          = "M3\n"
gGRBL_CMD_SPINDLE_OFF         = "M5\n"

# --------------------------------------------------------------------------
# state machine states
# --------------------------------------------------------------------------

""" ------------------------------------------------------------------------

STATE TABLE::
state    | RUN UI  | STOP UI | STEP UI | BREAK PT| ERROR   | ST END  |
-----------------------------------------------------------------------
IDLE     | RUN     | IGNORE  | STEP    | IGNORE  | IGNORE  | IGNORE  |
-----------------------------------------------------------------------
RUN      | IGNORE  | IDLE    | IGNORE  | BREAK   | IDLE    | IDLE    |
-----------------------------------------------------------------------
STEP     | IGNORE  | IDLE    | IGNORE  | IGNORE  | IDLE    | IDLE    |
-----------------------------------------------------------------------
BREAK    | RUN     | IDLE    | STEP    | IGNORE  | IDLE    | IGNORE  |
----------------------------------------------------------------------
USER     | IGNORE  | IGNORE  | IGNORE  | IGNORE  | IDLE    | IDLE    |
-----------------------------------------------------------------------

------------------------------------------------------------------------ """

gSTATE_IDLE  =  100
gSTATE_RUN   =  200
gSTATE_STEP  =  300
gSTATE_BREAK =  400

# --------------------------------------------------------------------------
# Thread/MainWindow communication events
# --------------------------------------------------------------------------
# EVENT ID             EVENT CODE
gEV_CMD_EXIT         = 1000
gEV_CMD_RUN          = 1030
gEV_CMD_STEP         = 1040
gEV_CMD_STOP         = 1050
gEV_CMD_SEND         = 1060
gEV_CMD_AUTO_STATUS  = 1070

gEV_ABORT            = 2000
gEV_RUN_END          = 2010
gEV_STEP_END         = 2020
gEV_DATA_OUT         = 2030
gEV_DATA_IN          = 2040
gEV_HIT_BRK_PT       = 2050
gEV_PC_UPDATE        = 2060

"""----------------------------------------------------------------------------
   gcsStateData:
   provides various data information
----------------------------------------------------------------------------"""
class gcsStateData():
   def __init__(self):

      # state status
      self.swState = gSTATE_IDLE

      # link status
      self.grblDetected = False
      self.serialPortIsOpen = False
      self.serialPort = ""
      self.serialPortBaud = "9600"

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
   gcsStateData:
   provides various data information
----------------------------------------------------------------------------"""
class gcsConfigData():
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
         '/machine/AutoRefresh'              :(True , False),
         '/machine/AutoRefreshPeriod'        :(True , 1000),

      # jogging keys
         '/jogging/XYZReadOnly'              :(True , True),
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
