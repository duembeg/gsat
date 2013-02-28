#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gcs.py:
----------------------------------------------------------------------------"""

__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
"GCODE Step and Alignment Tool (gcs) is a cross-platform GCODE debug/step for "\
"Grbl like GCODE interpreters. With features similar to software debuggers. Features "\
"Such as breakpoint, change current program counter, inspection and modification "\
"of variables."


# define authorship information
__authors__     = ['Wilhelm Duembeg']
__author__      = ','.join(__authors__)
__credits__     = []
__copyright__   = 'Copyright (c) 2013'
__license__     = 'GPL v2'
__license_str__ = __license__ + '\nhttp://www.gnu.org/licenses/gpl-2.0.txt'

# maintenance information
__maintainer__  = 'Wilhelm Duembeg'
__email__       = 'duembeg.github@gmail.com'

# define version information
__requires__        = ['pySerial', 'wxPython']
__version_info__    = (1, 0, 0)
__version__         = 'v%i.%02i.%02i' % __version_info__
__revision__        = __version__


"""----------------------------------------------------------------------------
   Dependencies:
----------------------------------------------------------------------------"""
import os
import sys
import glob
import threading
import serial
import re
import Queue
import time
import shutil
from optparse import OptionParser
import wx
import wx.combo
from wx import stc as stc
from wx.lib.mixins import listctrl as listmix
from wx.lib.agw import aui as aui
from wx.lib.agw import floatspin as fs
#from wx.lib.agw import flatmenu as fm
from wx.lib.wordwrap import wordwrap
from wx.lib import scrolledpanel as scrolled

from icons import *


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

# -----------------------------------------------------------------------------
# MENU & TOOL BAR IDs
# -----------------------------------------------------------------------------
gID_TOOLBAR_OPEN                 = wx.NewId()
gID_TOOLBAR_LINK_STATUS          = wx.NewId()
gID_TOOLBAR_PROGRAM_STATUS       = wx.NewId()
gID_TOOLBAR_MACHINE_STATUS       = wx.NewId()
gID_MENU_MAIN_TOOLBAR            = wx.NewId()
gID_MENU_RUN_TOOLBAR             = wx.NewId()
gID_MENU_STATUS_TOOLBAR          = wx.NewId()
gID_MENU_OUTPUT_PANEL            = wx.NewId()
gID_MENU_COMAMND_PANEL           = wx.NewId()
gID_MENU_MACHINE_STATUS_PANEL    = wx.NewId()
gID_MENU_MACHINE_JOGGING_PANEL   = wx.NewId()
gID_MENU_CV2_PANEL               = wx.NewId()
gID_MENU_LOAD_DEFAULT_LAYOUT     = wx.NewId()
gID_MENU_SAVE_DEFAULT_LAYOUT     = wx.NewId()
gID_MENU_RESET_DEFAULT_LAYOUT    = wx.NewId()
gID_MENU_LOAD_LAYOUT             = wx.NewId()
gID_MENU_SAVE_LAYOUT             = wx.NewId()
gID_MENU_RUN                     = wx.NewId()
gID_MENU_STEP                    = wx.NewId()
gID_MENU_STOP                    = wx.NewId()
gID_MENU_BREAK_TOGGLE            = wx.NewId()
gID_MENU_BREAK_REMOVE_ALL        = wx.NewId()
gID_MENU_SET_PC                  = wx.NewId()
gID_MENU_GOTO_PC                 = wx.NewId()
gID_MENU_ABORT                   = wx.NewId()
gID_MENU_IN2MM                   = wx.NewId()
gID_MENU_MM2IN                   = wx.NewId()
gID_MENU_G812G01                 = wx.NewId()

gID_TIMER_MACHINE_REFRESH        = wx.NewId()

gID_CV2_GOTO_CAM                 = wx.NewId()
gID_CV2_GOTO_TOOL                = wx.NewId()
gID_CV2_CAPTURE_TIMER            = wx.NewId()

# -----------------------------------------------------------------------------
# regular expressions
# -----------------------------------------------------------------------------

# grbl version, example "Grbl 0.8c ['$' for help]"
gReGrblVersion = re.compile(r'Grbl\s*(.*)\s*\[.*\]')

# status, example "<Run,MPos:20.163,0.000,0.000,WPos:20.163,0.000,0.000>"
gReMachineStatus = re.compile(r'<(.*),MPos:(.*),(.*),(.*),WPos:(.*),(.*),(.*)>')

# comments example "( comment string )" or "; comment string"
gReGcodeComments = [re.compile(r'\(.*\)'), re.compile(r';.*')]

# -----------------------------------------------------------------------------
# Grbl commands
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# state machine commands
# -----------------------------------------------------------------------------

""" ---------------------------------------------------------------------------

STATE TABLE::
state     | RUN UI  | STOP UI | STEP UI | BREAK PT| ERROR   | ST END  |
-----------------------------------------------------------------------
 IDLE     | RUN     | IGNORE  | STEP    | IGNORE  | IGNORE  | IGNORE  |
-----------------------------------------------------------------------
 RUN      | IGNORE  | IDLE    | IGNORE  | BREAK   | IDLE    | IDLE    |
-----------------------------------------------------------------------
 STEP     | IGNORE  | IDLE    | IGNORE  | IGNORE  | IDLE    | IDLE    |
-----------------------------------------------------------------------
 BREAK    | RUN     | IDLE    | STEP    | IGNORE  | IDLE    | IGNORE  |
-----------------------------------------------------------------------
 USER     | IGNORE  | IGNORE  | IGNORE  | IGNORE  | IDLE    | IDLE    |
-----------------------------------------------------------------------

--------------------------------------------------------------------------- """

gSTATE_IDLE  =  100
gSTATE_RUN   =  200
gSTATE_STEP  =  300
gSTATE_BREAK =  400

# -----------------------------------------------------------------------------
# Thread/MainWindow communication events
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Thread/ComputerVisionWindow communication events
# -----------------------------------------------------------------------------
gEV_CMD_CV_EXIT            = 1000

gEV_CMD_CV_IMAGE           = 3000


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
         '/code/CaretLineBackground'         :(False, '#C299A9'), #A9C299, 9D99C2
         '/code/LineNumber'                  :(True , True),
         '/code/LineNumberForeground'        :(False, '#000000'),
         '/code/LineNumberBackground'        :(False, '#99A9C2'),
         '/code/ReadOnly'                    :(True , True),
         '/code/WindowForeground'            :(False, '#000000'),
         '/code/WindowBackground'            :(False, '#FFFFFF'),


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
         '/jogging/Custom1Label'             :(False, "Goto CAM"),
         '/jogging/Custom1XIsOffset'         :(True , True),
         '/jogging/Custom1XValue'            :(True , 0),
         '/jogging/Custom1YIsOffset'         :(True , True),
         '/jogging/Custom1YValue'            :(True , 0),
         '/jogging/Custom1ZIsOffset'         :(True , True),
         '/jogging/Custom1ZValue'            :(True , 0),
         '/jogging/Custom2Label'             :(False, "Goto Tool"),
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
EVT_THREAD_QUEQUE_EVENT_ID = wx.NewId()

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

"""----------------------------------------------------------------------------
   gcsLog:
   custom wxLog
----------------------------------------------------------------------------"""
class gcsLog(wx.PyLog):
    def __init__(self, textCtrl, logTime=0):
        wx.PyLog.__init__(self)
        self.tc = textCtrl
        self.logTime = logTime

    def DoLogString(self, message, timeStamp):
        #print message, timeStamp
        #if self.logTime:
        #    message = time.strftime("%X", time.localtime(timeStamp)) + \
        #              ": " + message
        if self.tc:
            self.tc.AppendText(message + '\n')

"""----------------------------------------------------------------------------
   gcsGeneralSettingsPanel:
   General settings panel.
----------------------------------------------------------------------------"""
class gcsGeneralSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # file settings
      text = wx.StaticText(self, label="Files:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      # Add file save backup check box
      self.cbBackupFile = wx.CheckBox(self, wx.ID_ANY, "Create a backup copy of file before saving")
      self.cbBackupFile.SetValue(self.configData.Get('/mainApp/BackupFile'))
      vBoxSizer.Add(self.cbBackupFile, flag=wx.LEFT, border=25)

      # Add file history spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      self.scFileHistory = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scFileHistory.SetRange(0,100)
      self.scFileHistory.SetValue(self.configData.Get('/mainApp/MaxFileHistory'))
      hBoxSizer.Add(self.scFileHistory, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Recent file history size")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      # tools settings
      text = wx.StaticText(self, label="Tools:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      # Add Inch to mm round digits spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.scIN2MMRound = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scIN2MMRound.SetRange(0,100)
      self.scIN2MMRound.SetValue(self.configData.Get('/mainApp/RoundInch2mm'))
      hBoxSizer.Add(self.scIN2MMRound, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Inch to mm round digits")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      # Add mm to Inch round digits spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.scMM2INRound = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scMM2INRound.SetRange(0,100)
      self.scMM2INRound.SetValue(self.configData.Get('/mainApp/Roundmm2Inch'))
      hBoxSizer.Add(self.scMM2INRound, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "mm to Inch round digits")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)


      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/mainApp/BackupFile', self.cbBackupFile.GetValue())
      self.configData.Set('/mainApp/MaxFileHistory', self.scFileHistory.GetValue())
      self.configData.Set('/mainApp/RoundInch2mm', self.scIN2MMRound.GetValue())
      self.configData.Set('/mainApp/Roundmm2Inch', self.scMM2INRound.GetValue())

"""----------------------------------------------------------------------------
   gcsStyledTextCtrlSettingsPanel:
   Program settings.
----------------------------------------------------------------------------"""
class gcsStyledTextCtrlSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, key, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData
      self.key = key

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # Scrolling section
      text = wx.StaticText(self, label="Scrolling:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      spText = wx.StaticText(self, label="Auto Scroll:")
      hBoxSizer.Add(spText, 0,flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

      if self.key == 'code':
         asList = ["Never", "Always", "On Kill Focus", "On Goto PC"]
      else:
         asList = ["Never", "Always", "On Kill Focus"]

      self.asComboBox = wx.ComboBox(self, -1,
         value=asList[self.configData.Get('/%s/AutoScroll' % self.key)],
         choices=asList, style=wx.CB_READONLY)
      hBoxSizer.Add(self.asComboBox, 0,
         flag=wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, wx.LEFT|wx.EXPAND|wx.ALIGN_LEFT, border=20)

      # General Controls
      text = wx.StaticText(self, label="General:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      gBoxSizer = wx.GridSizer(1,3)

      self.checkReadOnly = wx.CheckBox (self, label="ReadOnly")
      self.checkReadOnly.SetValue(self.configData.Get('/%s/ReadOnly' % self.key))
      gBoxSizer.Add(self.checkReadOnly, 0, wx.ALIGN_CENTER)

      self.checkLineNumbers = wx.CheckBox (self, label="Line Numbers")
      self.checkLineNumbers.SetValue(self.configData.Get('/%s/LineNumber' % self.key))
      gBoxSizer.Add(self.checkLineNumbers, 0, wx.ALIGN_CENTER)

      self.checkCaretLine = wx.CheckBox (self, label="Highlight Caret Line")
      self.checkCaretLine.SetValue(self.configData.Get('/%s/CaretLine' % self.key))
      gBoxSizer.Add(self.checkCaretLine, 0, wx.ALIGN_CENTER)

      vBoxSizer.Add(gBoxSizer, 0, wx.ALL|wx.EXPAND, border=5)

      # Colors
      text = wx.StaticText(self, label="Colors:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)


      vColorSizer = wx.BoxSizer(wx.VERTICAL)
      foregroundColorSizer = wx.FlexGridSizer(2,3,0,0)
      backgroundColorSizer = wx.FlexGridSizer(2,3,0,0)

      # Foreground
      text = wx.StaticText(self, label="Foreground:")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

      text = wx.StaticText(self, label="Window")
      foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_BOTTOM|wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Line Numbers")
      foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_BOTTOM|wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Highlight Line")
      foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_BOTTOM|wx.LEFT|wx.RIGHT, border=20)

      self.windowForeground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/WindowForeground' % self.key))
      foregroundColorSizer.Add(self.windowForeground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.lineNumbersForeground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/LineNumberForeground' % self.key))
      foregroundColorSizer.Add(self.lineNumbersForeground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.caretLineForeground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/CaretLineForeground' % self.key))
      foregroundColorSizer.Add(self.caretLineForeground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      vColorSizer.Add(foregroundColorSizer, 0, flag=wx.LEFT, border=10)

      # Background
      text = wx.StaticText(self, label="")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)
      text = wx.StaticText(self, label="Background:")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

      text = wx.StaticText(self, label="Window")
      backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_BOTTOM|wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Line Numbers")
      backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_BOTTOM|wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Highlight Line")
      backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_BOTTOM|wx.LEFT|wx.RIGHT, border=20)


      self.windowBackground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/WindowBackground' % self.key))
      backgroundColorSizer.Add(self.windowBackground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.lineNumbersBackground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/LineNumberBackground' % self.key))
      backgroundColorSizer.Add(self.lineNumbersBackground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.caretLineBackground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/CaretLineBackground' % self.key))
      backgroundColorSizer.Add(self.caretLineBackground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      vColorSizer.Add(backgroundColorSizer, 0, flag=wx.LEFT, border=10)

      vBoxSizer.Add(vColorSizer, 0, wx.LEFT|wx.ALIGN_LEFT, border=10)

      # finish up
      self.SetSizerAndFit(vBoxSizer)

   def UpdatConfigData(self):
      asValue = self.asComboBox.GetSelection()
      if asValue > 0:
         self.configData.Set('/%s/AutoScroll' % self.key,
            self.asComboBox.GetSelection())

      self.configData.Set('/%s/ReadOnly' % self.key,
         self.checkReadOnly.GetValue())

      self.configData.Set('/%s/WindowForeground' % self.key,
         self.windowForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
      self.configData.Set('/%s/WindowBackground' % self.key,
         self.windowBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

      self.configData.Set('/%s/CaretLine' % self.key,
         self.checkCaretLine.GetValue())
      self.configData.Set('/%s/CaretLineForeground' % self.key,
         self.caretLineForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
      self.configData.Set('/%s/CaretLineBackground' % self.key,
         self.caretLineBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

      self.configData.Set('/%s/LineNumber' % self.key,
         self.checkLineNumbers.GetValue())
      self.configData.Set('/%s/LineNumberForeground' % self.key,
         self.lineNumbersForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
      self.configData.Set('/%s/LineNumberBackground' % self.key,
         self.lineNumbersBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

"""----------------------------------------------------------------------------
   gcsLinkSettingsPanel:
   Link settings.
----------------------------------------------------------------------------"""
class gcsLinkSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)
      flexGridSizer = wx.FlexGridSizer(2,2)
      gridSizer = wx.GridSizer(1,3)

      vBoxSizer.Add(flexGridSizer, 0, flag=wx.LEFT|wx.TOP|wx.RIGHT, border=20)
      vBoxSizer.Add(gridSizer, 0, flag=wx.ALL, border=5)

      # get serial port list and baud rate speeds
      spList = self.configData.Get('/link/PortList')
      brList = self.configData.Get('/link/BaudList')

      # Add serial port controls
      spText = wx.StaticText(self, label="Serial Port:")
      flexGridSizer.Add(spText, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

      self.spComboBox = wx.ComboBox(self, -1, value=self.configData.Get('/link/Port'),
         choices=spList, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
      flexGridSizer.Add(self.spComboBox,
         flag=wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      # Add baud rate controls
      srText = wx.StaticText(self, label="Baud Rate:")
      flexGridSizer.Add(srText, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

      self.sbrComboBox = wx.ComboBox(self, -1, value=self.configData.Get('/link/Baud'),
         choices=brList, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
      flexGridSizer.Add(self.sbrComboBox,
         flag=wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/link/Port', self.spComboBox.GetValue())
      self.configData.Set('/link/Baud', self.sbrComboBox.GetValue())

"""----------------------------------------------------------------------------
   gcsCliSettingsPanel:
   CLI settings.
----------------------------------------------------------------------------"""
class gcsCliSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # Add cehck box
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.cb = wx.CheckBox(self, wx.ID_ANY, "Save Command History")
      self.cb.SetValue(self.configData.Get('/cli/SaveCmdHistory'))
      hBoxSizer.Add(self.cb, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)
      vBoxSizer.Add(hBoxSizer, flag=wx.TOP|wx.LEFT, border=20)

      # Add spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.sc = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.sc.SetRange(1,1000)
      self.sc.SetValue(self.configData.Get('/cli/CmdMaxHistory'))
      hBoxSizer.Add(self.sc, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Max Command History")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/cli/SaveCmdHistory', self.cb.GetValue())
      self.configData.Set('/cli/CmdMaxHistory', self.sc.GetValue())

"""----------------------------------------------------------------------------
   gcsMachineSettingsPanel:
   Machine settings.
----------------------------------------------------------------------------"""
class gcsMachineSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # Add check box
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.cb = wx.CheckBox(self, wx.ID_ANY, "Auto Refresh")
      self.cb.SetValue(self.configData.Get('/machine/AutoRefresh'))
      self.cb.SetToolTip(
         wx.ToolTip("Send '?' Status request (experimental)"))
      hBoxSizer.Add(self.cb, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)
      vBoxSizer.Add(hBoxSizer, flag=wx.TOP|wx.LEFT, border=20)

      # Add spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      self.sc = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.sc.SetRange(1,1000000)
      self.sc.SetValue(self.configData.Get('/machine/AutoRefreshPeriod'))
      hBoxSizer.Add(self.sc, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Auto Refresh Period (milliseconds)")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/machine/AutoRefresh', self.cb.GetValue())
      self.configData.Set('/machine/AutoRefreshPeriod', self.sc.GetValue())

"""----------------------------------------------------------------------------
   gcsJoggingSettingsPanel:
   Machine settings.
----------------------------------------------------------------------------"""
class gcsJoggingSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      text = wx.StaticText(self, label="General:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      # Add cehck box
      self.cb = wx.CheckBox(self, wx.ID_ANY, "XYZ Read Only Status")
      self.cb.SetValue(self.configData.Get('/jogging/XYZReadOnly'))
      self.cb.SetToolTip(
         wx.ToolTip("If disable the XYZ fields in jogging status are editable"))
      vBoxSizer.Add(self.cb, flag=wx.LEFT|wx.BOTTOM, border=20)

      # Custom controls
      text = wx.StaticText(self, label="Custom Controls:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      box1, c1CtrlArray = self.CreateCustomControlSettings(1)
      box2, c2CtrlArray = self.CreateCustomControlSettings(2)
      box3, c3CtrlArray = self.CreateCustomControlSettings(3)
      box4, c4CtrlArray = self.CreateCustomControlSettings(4)

      self.customCtrlArray = [c1CtrlArray, c2CtrlArray, c3CtrlArray, c4CtrlArray]

      vBoxSizer.Add(box1, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      vBoxSizer.Add(box2, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      vBoxSizer.Add(box3, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      vBoxSizer.Add(box4, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      self.SetSizer(vBoxSizer)

   def CreateCustomControlSettings(self, cn):
      # Custom controls
      vCustomSizer = wx.BoxSizer(wx.VERTICAL)
      text = wx.StaticText(self, label="Custom Control %d:" % cn)
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vCustomSizer.Add(text, 0, flag=wx.ALL, border=5)

      # Label
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      text = wx.StaticText(self, label="Label:")
      hBoxSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
      tcLabel = wx.TextCtrl(self, -1,
         self.configData.Get('/jogging/Custom%dLabel' % cn), size=(125, -1))
      hBoxSizer.Add(tcLabel, 0, flag=wx.ALIGN_CENTER_VERTICAL)

      vCustomSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      # other controls
      gCustomSizer = wx.FlexGridSizer(3,3,0,0)

      text = wx.StaticText(self, label="X Settings:")
      gCustomSizer.Add(text, flag=wx.LEFT|wx.TOP|wx.ALIGN_BOTTOM, border=5)
      text = wx.StaticText(self, label="Y Settings:")
      gCustomSizer.Add(text, flag=wx.LEFT|wx.TOP|wx.ALIGN_BOTTOM, border=5)
      text = wx.StaticText(self, label="Z Settings:")
      gCustomSizer.Add(text, flag=wx.LEFT|wx.TOP|wx.ALIGN_BOTTOM, border=5)

      # check boxes
      cbXIsOffset = wx.CheckBox(self, wx.ID_ANY, "Is Offset")
      cbXIsOffset.SetValue(self.configData.Get('/jogging/Custom%dXIsOffset' % cn))
      cbXIsOffset.SetToolTip(wx.ToolTip("If set the value is treated as an offset"))
      gCustomSizer.Add(cbXIsOffset, flag=wx.ALL, border=5)

      cbYIsOffset = wx.CheckBox(self, wx.ID_ANY, "Is Offset")
      cbYIsOffset.SetValue(self.configData.Get('/jogging/Custom%dYIsOffset' % cn))
      cbYIsOffset.SetToolTip(wx.ToolTip("If set the value is treated as an offset"))
      gCustomSizer.Add(cbYIsOffset, flag=wx.ALL, border=5)

      cbZIsOffset = wx.CheckBox(self, wx.ID_ANY, "Is Offset")
      cbZIsOffset.SetValue(self.configData.Get('/jogging/Custom%dZIsOffset' % cn))
      cbZIsOffset.SetToolTip(wx.ToolTip("If set the value is treated as an offset"))
      gCustomSizer.Add(cbZIsOffset, flag=wx.ALL, border=5)

      # spin controls
      scXValue = fs.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      scXValue.SetFormat("%f")
      scXValue.SetDigits(4)
      scXValue.SetValue(self.configData.Get('/jogging/Custom%dXValue' % cn))
      gCustomSizer.Add(scXValue, flag=wx.ALL, border=5)

      scYValue = fs.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      scYValue.SetFormat("%f")
      scYValue.SetDigits(4)
      scYValue.SetValue(self.configData.Get('/jogging/Custom%dYValue' % cn))
      gCustomSizer.Add(scYValue,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      scZValue = fs.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      scZValue.SetFormat("%f")
      scZValue.SetDigits(4)
      scZValue.SetValue(self.configData.Get('/jogging/Custom%dZValue' % cn))
      gCustomSizer.Add(scZValue,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)


      #st = wx.StaticText(self, wx.ID_ANY, "X")
      #hBoxSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

      vCustomSizer.Add(gCustomSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      return vCustomSizer, [
         tcLabel,
         cbXIsOffset, cbYIsOffset, cbZIsOffset,
         scXValue   , scYValue   , scZValue
      ]

   def UpdatConfigData(self):
      self.configData.Set('/jogging/XYZReadOnly', self.cb.GetValue())

      for cn in range(4):
         cnp1 = cn+1
         self.configData.Set('/jogging/Custom%dLabel' % cnp1,
            self.customCtrlArray[cn][0].GetValue())

         self.configData.Set('/jogging/Custom%dXIsOffset' % cnp1,
            self.customCtrlArray[cn][1].GetValue())
         self.configData.Set('/jogging/Custom%dYIsOffset' % cnp1,
            self.customCtrlArray[cn][2].GetValue())
         self.configData.Set('/jogging/Custom%dZIsOffset' % cnp1,
            self.customCtrlArray[cn][3].GetValue())

         self.configData.Set('/jogging/Custom%dXValue' % cnp1,
            self.customCtrlArray[cn][4].GetValue())
         self.configData.Set('/jogging/Custom%dYValue' % cnp1,
            self.customCtrlArray[cn][5].GetValue())
         self.configData.Set('/jogging/Custom%dZValue' % cnp1,
            self.customCtrlArray[cn][6].GetValue())

"""----------------------------------------------------------------------------
   gcsSettingsDialog:
   Dialog to control program settings
----------------------------------------------------------------------------"""
class gcsSettingsDialog(wx.Dialog):
   def __init__(self, parent, configData, id=wx.ID_ANY, title="Settings",
      style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER):

      wx.Dialog.__init__(self, parent, id, title, style=style)

      self.configData = configData

      self.InitUI()

   def InitUI(self):
      sizer = wx.BoxSizer(wx.VERTICAL)

      # init note book
      self.imageList = wx.ImageList(16, 16)
      self.imageList.Add(imgGeneralSettings.GetBitmap())
      self.imageList.Add(imgPlugConnect.GetBitmap())
      self.imageList.Add(imgProgram.GetBitmap())
      self.imageList.Add(imgLog.GetBitmap())
      self.imageList.Add(imgCli.GetBitmap())
      self.imageList.Add(imgMachine.GetBitmap())
      self.imageList.Add(imgMove.GetBitmap())
      self.imageList.Add(imgEye.GetBitmap())

      if os.name == 'nt':
         self.noteBook = wx.Notebook(self, size=(640,400))
      else:
         self.noteBook = wx.Notebook(self, size=(640,400), style=wx.BK_LEFT)

      self.noteBook.AssignImageList(self.imageList)

      # add pages
      self.AddGeneralPage(0)
      self.AddLinkPage(1)
      self.AddProgramPage(2)
      self.AddOutputPage(3)
      self.AddCliPage(4)
      self.AddMachinePage(5)
      self.AddJoggingPage(6)
      self.AddCV2Panel(7)

      #self.noteBook.Layout()
      sizer.Add(self.noteBook, 1, wx.ALL|wx.EXPAND, 5)

      # buttons
      line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
      sizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.TOP, border=5)

      btnsizer = wx.StdDialogButtonSizer()

      btn = wx.Button(self, wx.ID_OK)
      btnsizer.AddButton(btn)

      btn = wx.Button(self, wx.ID_CANCEL)
      btnsizer.AddButton(btn)

      btnsizer.Realize()

      sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5)

      self.SetSizerAndFit(sizer)
      #self.SetAutoLayout(True)

   def AddGeneralPage(self, page):
      self.generalPage = gcsGeneralSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.generalPage, "General")
      self.noteBook.SetPageImage(page, page)

   def AddLinkPage(self, page):
      self.linkPage = gcsLinkSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.linkPage, "Link")
      self.noteBook.SetPageImage(page, page)

   def AddProgramPage(self, page):
      self.programPage = gcsStyledTextCtrlSettingsPanel(
         self.noteBook, self.configData, "code")
      self.noteBook.AddPage(self.programPage, "Program")
      self.noteBook.SetPageImage(page, page)

   def AddOutputPage(self, page):
      self.outputPage = gcsStyledTextCtrlSettingsPanel(
         self.noteBook, self.configData, "output")
      self.noteBook.AddPage(self.outputPage, "Output")
      self.noteBook.SetPageImage(page, page)

   def AddCliPage(self, page):
      self.cliPage = gcsCliSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.cliPage, "Cli")
      self.noteBook.SetPageImage(page, page)

   def AddMachinePage(self, page):
      self.machinePage = gcsMachineSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.machinePage, "Machine")
      self.noteBook.SetPageImage(page, page)

   def AddJoggingPage(self, page):
      self.jogPage = gcsJoggingSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.jogPage, "Jogging")
      self.noteBook.SetPageImage(page, page)

   def AddCV2Panel(self, page):
      self.CV2Page = gcsCV2SettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.CV2Page, " OpenCV2")
      self.noteBook.SetPageImage(page, page)

   def UpdatConfigData(self):
      self.generalPage.UpdatConfigData()
      self.linkPage.UpdatConfigData()
      self.programPage.UpdatConfigData()
      self.outputPage.UpdatConfigData()
      self.cliPage.UpdatConfigData()
      self.machinePage.UpdatConfigData()
      self.jogPage.UpdatConfigData()
      self.CV2Page.UpdatConfigData()


"""----------------------------------------------------------------------------
   gcsCliPanel:
   Control to handle CLI (Command Line Interface)
----------------------------------------------------------------------------"""
class gcsCliPanel(wx.Panel):
   def __init__(self, parent, configData, *args, **kwargs):
      wx.Panel.__init__(self, parent, *args, **kwargs)

      self.stateData = gcsStateData()
      self.cliCommand = ""
      self.configData = configData

      self.InitConfig()
      self.InitUI()

   def InitConfig(self):
      self.cliSaveCmdHistory = self.configData.Get('/cli/SaveCmdHistory')
      self.cliCmdMaxHistory = self.configData.Get('/cli/CmdMaxHistory')
      self.cliCmdHistory = self.configData.Get('/cli/CmdHistory')

   def InitUI(self):
      sizer = wx.BoxSizer(wx.VERTICAL)
      self.comboBox = wx.ComboBox(self, style=wx.CB_DROPDOWN|wx.TE_PROCESS_ENTER)
      self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter, self.comboBox)
      sizer.Add(self.comboBox, 1, wx.EXPAND|wx.ALL, border=1)
      self.SetSizerAndFit(sizer)

   def UpdateUI(self, stateData):
      self.stateData = stateData
      if stateData.serialPortIsOpen and not stateData.swState == gSTATE_RUN:
         self.comboBox.Enable()
      else:
         self.comboBox.Disable()

   def GetCommand(self):
      return self.cliCommand

   def OnEnter(self, e):
      cliCommand = self.comboBox.GetValue()

      if cliCommand != self.cliCommand:
         if self.comboBox.GetCount() > self.cliCmdMaxHistory:
            self.comboBox.Delete(0)

         self.cliCommand = cliCommand
         self.comboBox.Append(self.cliCommand)

      self.comboBox.SetValue("")
      e.Skip()

   def Load(self, configFile):
      # read cmd hsitory
      configData = self.cliCmdHistory
      if len(configData) > 0:
         cliCommandHistory = configData.split("|")
         for cmd in cliCommandHistory:
            cmd = cmd.strip()
            if len(cmd) > 0:
               self.comboBox.Append(cmd.strip())

         self.cliCommand = cliCommandHistory[len(cliCommandHistory) - 1]

   def Save(self, configFile):
      # write cmd history
      if self.cliSaveCmdHistory:
         cliCmdHistory = self.comboBox.GetItems()
         if len(cliCmdHistory) > 0:
            cliCmdHistory =  "|".join(cliCmdHistory)
            self.configData.Set('/cli/CmdHistory', cliCmdHistory)

   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.InitConfig()


"""----------------------------------------------------------------------------
   gcsStcStyledTextCtrl:
   Text control to display data
----------------------------------------------------------------------------"""
class gcsStcStyledTextCtrl(stc.StyledTextCtrl):
   def __init__(self, parent, config_data, id=wx.ID_ANY, pos=wx.DefaultPosition,
      size=wx.DefaultSize, style=0, name=stc.STCNameStr):

      stc.StyledTextCtrl.__init__(self, parent, id, pos, size,
         style, name)

      self.stateData = gcsStateData()
      self.configData = config_data
      self.autoScroll = False

      self.InitConfig()
      self.InitUI()

      # bind events
      self.Bind(wx.EVT_LEFT_DOWN, self.OnCaretChange)
      self.Bind(wx.EVT_LEFT_UP, self.OnCaretChange)
      self.Bind(wx.EVT_KEY_DOWN, self.OnCaretChange)
      self.Bind(wx.EVT_KEY_UP, self.OnCaretChange)
      self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

   def InitConfig(self):
      self.configReadOnly = self.configData.Get('/output/ReadOnly')
      self.configAutoScroll = self.configData.Get('/output/AutoScroll')
      self.configWindowForeground = self.configData.Get('/output/WindowForeground')
      self.configWindowBackground = self.configData.Get('/output/WindowBackground')
      self.configLineNumber = self.configData.Get('/output/LineNumber')
      self.configLineNumberForeground = self.configData.Get('/output/LineNumberForeground')
      self.configLineNumberBackground = self.configData.Get('/output/LineNumberBackground')
      self.configCaretLine = self.configData.Get('/output/CaretLine')
      self.configCaretLineForeground = self.configData.Get('/output/CaretLineForeground')
      self.configCaretLineBackground = self.configData.Get('/output/CaretLineBackground')

      self.SetReadOnly(self.configReadOnly)

      if (self.configAutoScroll == 1) or (self.configAutoScroll == 2):
         self.autoScroll = True

   def InitUI(self):
      # global default style
      if wx.Platform == '__WXMSW__':
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,face:Courier New"\
         % (self.configWindowForeground, self.configWindowBackground))
      elif wx.Platform == '__WXMAC__':
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,face:Monaco"\
            % (self.configWindowForeground, self.configWindowBackground))
      else:
         defsize = wx.SystemSettings.GetFont(wx.SYS_ANSI_FIXED_FONT).GetPointSize()
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,face:Courier,size:%d"\
            % (self.configWindowForeground, self.configWindowBackground, defsize))

      self.StyleClearAll()

      self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, "fore:%s,back:%s"\
         % (self.configLineNumberForeground, self.configLineNumberBackground))

      # margin 0 for line numbers
      if self.configLineNumber:
         self.SetMarginType(0, stc.STC_MARGIN_NUMBER)
         self.SetMarginWidth(0, 50)
      else:
         self.SetMarginType(0, stc.STC_MARGIN_SYMBOL)
         self.SetMarginWidth(0, 1)

      # define markers
      self.markerCaretLine = 2
      self.MarkerDefine(self.markerCaretLine, stc.STC_MARK_ROUNDRECT,
         self.configCaretLineForeground, self.configCaretLineBackground)

      # disable two otehr margins
      self.SetMarginMask(1, pow(2,0))
      self.SetMarginMask(2, pow(2,1))


   def UpdateUI(self, stateData):
      self.stateData = stateData

   def OnCaretChange(self, e):
      wx.CallAfter(self.CaretChange)
      e.Skip()

   def OnKillFocus(self, e):
      if self.configAutoScroll == 2:
         self.autoScroll = True
      e.Skip()

   def CaretChange(self):
      self.MarkerDeleteAll(self.markerCaretLine)

      if self.configCaretLine:
         self.MarkerAdd(self.GetCurrentLine(), self.markerCaretLine)

      if self.configAutoScroll >= 2:
         self.autoScroll = False

   def AppendText(self, string):
      readOnly = self.GetReadOnly()
      self.SetReadOnly(False)
      stc.StyledTextCtrl.AppendText(self, string)
      self.SetReadOnly(readOnly)

      if self.autoScroll:
         wx.CallAfter(self.ScrollToEnd)

   def ScrollToEnd(self):
      line = self.GetLineCount() - 1
      self.MarkerDeleteAll(self.markerCaretLine)

      if self.configCaretLine:
         self.MarkerAdd(line, self.markerCaretLine)

      self.GotoLine(line)
      #self.ScrollToLine(self.GetLineCount())

   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.InitConfig()
      self.InitUI()

"""----------------------------------------------------------------------------
   gcsGcodeStcStyledTextCtrl:
   Text control to display GCODE
----------------------------------------------------------------------------"""
class gcsGcodeStcStyledTextCtrl(gcsStcStyledTextCtrl):
   def __init__(self, parent, config_data, id=wx.ID_ANY, pos=wx.DefaultPosition,
      size=wx.DefaultSize, style=0, name=stc.STCNameStr):

      gcsStcStyledTextCtrl.__init__(self, parent, config_data, id, pos, size,
         style, name)

      self.stateData = gcsStateData()
      self.configData = config_data

      self.InitConfig()
      self.InitUI()

   def InitConfig(self):
      self.configReadOnly = self.configData.Get('/code/ReadOnly')
      self.configAutoScroll = self.configData.Get('/code/AutoScroll')
      self.configWindowForeground = self.configData.Get('/code/WindowForeground')
      self.configWindowBackground = self.configData.Get('/code/WindowBackground')
      self.configLineNumber = self.configData.Get('/code/LineNumber')
      self.configLineNumberForeground = self.configData.Get('/code/LineNumberForeground')
      self.configLineNumberBackground = self.configData.Get('/code/LineNumberBackground')
      self.configCaretLine = self.configData.Get('/code/CaretLine')
      self.configCaretLineForeground = self.configData.Get('/code/CaretLineForeground')
      self.configCaretLineBackground = self.configData.Get('/code/CaretLineBackground')


      self.SetReadOnly(self.configReadOnly)

      if (self.configAutoScroll == 1) or (self.configAutoScroll == 2) or (self.configAutoScroll == 3):
         self.autoScroll = True

   def InitUI(self):
      # global default style
      if wx.Platform == '__WXMSW__':
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,face:Courier New"\
         % (self.configWindowForeground, self.configWindowBackground))
      elif wx.Platform == '__WXMAC__':
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,face:Monaco"\
            % (self.configWindowForeground, self.configWindowBackground))
      else:
         defsize = wx.SystemSettings.GetFont(wx.SYS_ANSI_FIXED_FONT).GetPointSize()
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,face:Courier,size:%d"\
            % (self.configWindowForeground, self.configWindowBackground, defsize))

      self.StyleClearAll()

      self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, "fore:%s,back:%s"\
         % (self.configLineNumberForeground, self.configLineNumberBackground))

      # margin 0 for line numbers
      if self.configLineNumber:
         self.SetMarginType(0, stc.STC_MARGIN_NUMBER)
         self.SetMarginWidth(0, 50)
      else:
         self.SetMarginType(0, stc.STC_MARGIN_SYMBOL)
         self.SetMarginWidth(0, 1)

      # margin 1 for markers
      self.SetMarginType(1, stc.STC_MARGIN_SYMBOL)
      self.SetMarginWidth(1, 16)

      # margin 2 for markers
      self.SetMarginType(2, stc.STC_MARGIN_SYMBOL)
      self.SetMarginWidth(2, 16)

      # define markers
      self.markerPC = 0
      self.markerBreakpoint = 1
      self.markerCaretLine = 2
      self.MarkerDefine(self.markerPC, stc.STC_MARK_ARROW, "BLACK", "GREEN")
      self.MarkerDefine(self.markerBreakpoint, stc.STC_MARK_CIRCLE, "BLACK", "RED")
      self.MarkerDefine(self.markerCaretLine, stc.STC_MARK_ROUNDRECT,
         self.configCaretLineForeground, self.configCaretLineBackground)

      self.SetMarginMask(1, pow(2,self.markerBreakpoint))
      self.SetMarginMask(2, pow(2,self.markerPC))


      #self.SetLexer(stc.STC_LEX_PYTHON)
      #self.SetKeyWords(0, "G00 G01 G02 G03 G04 G05 G20 G21 G90 G92 G94 M2 M3 M5 M9 T6 S")

      # comment-blocks
      self.StyleSetSpec(stc.STC_P_COMMENTBLOCK, "fore:#7F7F7F")

      # end of line where string is not closed
      #self.StyleSetSpec(stc.STC_P_STRINGEOL, "fore:#000000")

      #self.StyleSetSpec(stc.STC_P_WORD, "fore:#00007F")

      '''
      self.StyleSetSpec(stc.STC_STYLE_CONTROLCHAR,
         "face:%(other)s" % faces)
      self.StyleSetSpec(stc.STC_STYLE_BRACELIGHT,
         "fore:#FFFFFF,back:#0000FF,bold")
      self.StyleSetSpec(stc.STC_STYLE_BRACEBAD,
         "fore:#000000,back:#FF0000,bold")

      # make the Python styles ...
      # default
      self.StyleSetSpec(stc.STC_P_DEFAULT,
         "fore:#000000,face:%(helv)s,size:%(size)d" % faces)
      # comments
      self.StyleSetSpec(stc.STC_P_COMMENTLINE,
         "fore:#007F00,face:%(other)s,size:%(size)d" % faces)
      # number
      self.StyleSetSpec(stc.STC_P_NUMBER,
         "fore:#007F7F,size:%(size)d" % faces)
      # string
      self.StyleSetSpec(stc.STC_P_STRING,
         "fore:#7F007F,face:%(helv)s,size:%(size)d" % faces)
      # single quoted string
      self.StyleSetSpec(stc.STC_P_CHARACTER,
         "fore:#7F007F,face:%(helv)s,size:%(size)d" % faces)
      # keyword
      self.StyleSetSpec(stc.STC_P_WORD,
         "fore:#00007F,bold,size:%(size)d" % faces)

      # comment-blocks
      self.StyleSetSpec(stc.STC_P_COMMENTBLOCK,
         "fore:#7F7F7F,size:%(size)d" % faces)
      # end of line where string is not closed
      self.StyleSetSpec(stc.STC_P_STRINGEOL,
         "fore:#000000,face:%(mono)s,back:#E0C0E0,eol,size:%(size)d"\
         % faces)
      '''

   def UpdateUI(self, stateData):
      self.stateData = stateData

      if (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         self.SetReadOnly(self.configReadOnly)
      else:
         # cannot update while we are on a non-IDLE state
         self.SetReadOnly(True)

   def UpdatePC(self, pc):
      if pc > -1:
         self.MarkerDeleteAll(self.markerPC)
         self.handlePC = self.MarkerAdd(pc, self.markerPC)

         if self.autoScroll:
            self.MarkerDeleteAll(self.markerCaretLine)
            self.MarkerAdd(pc, self.markerCaretLine)
            self.GotoLine(pc)

   def GoToPC(self):
      pc = self.MarkerLineFromHandle(self.handlePC)

      if self.configAutoScroll == 3:
         self.autoScroll = True

      if pc > -1:
         self.MarkerDeleteAll(self.markerCaretLine)
         self.MarkerAdd(pc, self.markerCaretLine)
         self.GotoLine(pc)

   def UpdateBreakPoint(self, pc, enable):
      if pc == -1 and enable == False:
         self.MarkerDeleteAll(self.markerBreakpoint)
      else:
         markerBits = self.MarkerGet(pc)
         if (markerBits & pow(2,self.markerBreakpoint)):
            self.MarkerDelete(pc, self.markerBreakpoint)
         else:
            self.MarkerAdd(pc, self.markerBreakpoint)

   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.InitConfig()
      self.InitUI()

"""----------------------------------------------------------------------------
   gcsMachineStatusPanel:
   Status information about machine, controls to enable auto and manual
   refresh.
----------------------------------------------------------------------------"""
class gcsMachineStatusPanel(wx.ScrolledWindow):
   def __init__(self, parent, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent

      self.stateData = gcsStateData()

      self.machineDataColor = wx.RED

      self.InitUI()
      width,height = self.GetSize()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

   def InitUI(self):
      gridSizer = wx.GridSizer(2,2)

      # Add Static Boxes ------------------------------------------------------
      wBox, self.wX, self.wY, self.wZ = self.CreatePositionStaticBox("Work Position")
      mBox, self.mX, self.mY, self.mZ = self.CreatePositionStaticBox("Machine Position")
      sBox, self.sConncted, self.sState = self.CreateStatusStaticBox("Status")

      gridSizer.Add(wBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      gridSizer.Add(mBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      gridSizer.Add(sBox, 0, flag=wx.ALL|wx.EXPAND, border=5)

      # Add Buttons -----------------------------------------------------------
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)
      self.refreshButton = wx.Button(self, wx.ID_REFRESH)
      self.refreshButton.SetToolTip(
         wx.ToolTip("Refresh machine status"))
      self.Bind(wx.EVT_BUTTON, self.OnRefresh, self.refreshButton)
      vBoxSizer.Add(self.refreshButton, 0, flag=wx.TOP, border=5)
      self.refreshButton.Disable()

      gridSizer.Add(vBoxSizer, 0, flag=wx.EXPAND|wx.ALIGN_LEFT|wx.ALL, border=5)


      # Finish up init UI
      self.SetSizer(gridSizer)
      self.Layout()

   def UpdateUI(self, stateData, statusData=None):
      self.stateData = stateData
      # adata is expected to be an array of strings as follows
      # statusData[0] : Machine state
      # statusData[1] : Machine X
      # statusData[2] : Machine Y
      # statusData[3] : Machine Z
      # statusData[4] : Work X
      # statusData[5] : Work Y
      # statusData[6] : Work Z
      if statusData is not None:
         self.mX.SetLabel(statusData[1])
         self.mY.SetLabel(statusData[2])
         self.mZ.SetLabel(statusData[3])
         self.wX.SetLabel(statusData[4])
         self.wY.SetLabel(statusData[5])
         self.wZ.SetLabel(statusData[6])
         self.sState.SetLabel(statusData[0])
         #self.sSpindle.SetLabel("?")

      if stateData.serialPortIsOpen:
         self.refreshButton.Enable()
         self.sConncted.SetLabel("Yes")
      else:
         self.refreshButton.Disable()
         self.sConncted.SetLabel("No")

      self.Update()

   def CreateStaticBox(self, label):
      # Static box -------------------------------------------------
      staticBox = wx.StaticBox(self, -1, label)
      staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)

      return staticBoxSizer

   def CreatePositionStaticBox(self, label):
      # Position static box -------------------------------------------------
      positionBoxSizer = self.CreateStaticBox(label)
      flexGridSizer = wx.FlexGridSizer(3,2)
      positionBoxSizer.Add(flexGridSizer, 1, flag=wx.EXPAND)

      # Add X pos
      xText = wx.StaticText(self, label="X:")
      xPosition = wx.StaticText(self, label=gZeroString)
      xPosition.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(xText, 0, flag=wx.ALIGN_RIGHT)
      flexGridSizer.Add(xPosition, 0, flag=wx.ALIGN_LEFT)

      # Add Y Pos
      yText = wx.StaticText(self, label="Y:")
      yPosition = wx.StaticText(self, label=gZeroString)
      yPosition.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(yText, 0, flag=wx.ALIGN_RIGHT)
      flexGridSizer.Add(yPosition, 0, flag=wx.ALIGN_LEFT)

      # Add Z Pos
      zText = wx.StaticText(self, label="Z:")
      zPosition = wx.StaticText(self, label=gZeroString)
      zPosition.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(zText, 0, flag=wx.ALIGN_RIGHT)
      flexGridSizer.Add(zPosition, 0, flag=wx.ALIGN_LEFT)

      return positionBoxSizer, xPosition, yPosition, zPosition

   def CreateStatusStaticBox(self, label):
      # Position static box -------------------------------------------------
      positionBoxSizer = self.CreateStaticBox(label)
      flexGridSizer = wx.FlexGridSizer(3,2)
      positionBoxSizer.Add(flexGridSizer, 1, flag=wx.EXPAND)

      # Add Connected Status
      connectedText = wx.StaticText(self, label="Connected:")
      connectedStatus = wx.StaticText(self, label="No")
      connectedStatus.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(connectedText, 0, flag=wx.ALIGN_LEFT)
      flexGridSizer.Add(connectedStatus, 0, flag=wx.ALIGN_LEFT)

      # Add Running Status
      runningText = wx.StaticText(self, label="State:")
      runningStatus = wx.StaticText(self, label="Idle")
      runningStatus.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(runningText, 0, flag=wx.ALIGN_LEFT)
      flexGridSizer.Add(runningStatus, 0, flag=wx.ALIGN_LEFT)

      # Add Spindle Status
      #spindleText = wx.StaticText(self, label="Spindle:")
      #spindleStatus = wx.StaticText(self, label=gOffString)
      #spindleStatus.SetForegroundColour(self.machineDataColor)
      #flexGridSizer.Add(spindleText, 0, flag=wx.ALIGN_LEFT)
      #flexGridSizer.Add(spindleStatus, 0, flag=wx.ALIGN_LEFT)

      return positionBoxSizer, connectedStatus, runningStatus#, spindleStatus

   def OnRefresh(self, e):
      self.mainWindow.GetMachineStatus()

   def UpdateSettings(self, config_data):
      self.configData = config_data
      #self.InitConfig()


"""----------------------------------------------------------------------------
   gcsJoggingPanel:
   Jog controls for the machine as well as custom user controls.
----------------------------------------------------------------------------"""
class gcsJoggingPanel(wx.ScrolledWindow):
   def __init__(self, parent, config_data, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent

      self.configData = config_data
      self.stateData = gcsStateData()

      self.useMachineWorkPosition = False

      self.memoX = gZeroString
      self.memoY = gZeroString
      self.memoZ = gZeroString

      self.InitConfig()
      self.InitUI()
      width,height = self.GetSizeTuple()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

      self.UpdateSettings(self.configData)

   def InitConfig(self):
      self.configXYZReadOnly      = self.configData.Get('/jogging/XYZReadOnly')

      self.configCustom1Label     = self.configData.Get('/jogging/Custom1Label')
      self.configCustom1XIsOffset = self.configData.Get('/jogging/Custom1XIsOffset')
      self.configCustom1XValue    = self.configData.Get('/jogging/Custom1XValue')
      self.configCustom1YIsOffset = self.configData.Get('/jogging/Custom1YIsOffset')
      self.configCustom1YValue    = self.configData.Get('/jogging/Custom1YValue')
      self.configCustom1ZIsOffset = self.configData.Get('/jogging/Custom1ZIsOffset')
      self.configCustom1ZValue    = self.configData.Get('/jogging/Custom1ZValue')

      self.configCustom2Label     = self.configData.Get('/jogging/Custom2Label')
      self.configCustom2XIsOffset = self.configData.Get('/jogging/Custom2XIsOffset')
      self.configCustom2XValue    = self.configData.Get('/jogging/Custom2XValue')
      self.configCustom2YIsOffset = self.configData.Get('/jogging/Custom2YIsOffset')
      self.configCustom2YValue    = self.configData.Get('/jogging/Custom2YValue')
      self.configCustom2ZIsOffset = self.configData.Get('/jogging/Custom2ZIsOffset')
      self.configCustom2ZValue    = self.configData.Get('/jogging/Custom2ZValue')

      self.configCustom3Label     = self.configData.Get('/jogging/Custom3Label')
      self.configCustom3XIsOffset = self.configData.Get('/jogging/Custom3XIsOffset')
      self.configCustom3XValue    = self.configData.Get('/jogging/Custom3XValue')
      self.configCustom3YIsOffset = self.configData.Get('/jogging/Custom3YIsOffset')
      self.configCustom3YValue    = self.configData.Get('/jogging/Custom3YValue')
      self.configCustom3ZIsOffset = self.configData.Get('/jogging/Custom3ZIsOffset')
      self.configCustom3ZValue    = self.configData.Get('/jogging/Custom3ZValue')

      self.configCustom4Label     = self.configData.Get('/jogging/Custom4Label')
      self.configCustom4XIsOffset = self.configData.Get('/jogging/Custom4XIsOffset')
      self.configCustom4XValue    = self.configData.Get('/jogging/Custom4XValue')
      self.configCustom4YIsOffset = self.configData.Get('/jogging/Custom4YIsOffset')
      self.configCustom4YValue    = self.configData.Get('/jogging/Custom4YValue')
      self.configCustom4ZIsOffset = self.configData.Get('/jogging/Custom4ZIsOffset')
      self.configCustom4ZValue    = self.configData.Get('/jogging/Custom4ZValue')

   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.InitConfig()

      if self.configXYZReadOnly:
         self.jX.SetEditable(False)
         self.jX.SetBackgroundColour(gReadOnlyBkColor)
         self.jY.SetEditable(False)
         self.jY.SetBackgroundColour(gReadOnlyBkColor)
         self.jZ.SetEditable(False)
         self.jZ.SetBackgroundColour(gReadOnlyBkColor)
      else:
         self.jX.SetEditable(True)
         self.jX.SetBackgroundColour(gEdityBkColor)
         self.jY.SetEditable(True)
         self.jY.SetBackgroundColour(gEdityBkColor)
         self.jZ.SetEditable(True)
         self.jZ.SetBackgroundColour(gEdityBkColor)

      self.custom1Button.SetLabel(self.configCustom1Label)
      self.custom2Button.SetLabel(self.configCustom2Label)
      self.custom3Button.SetLabel(self.configCustom3Label)
      self.custom4Button.SetLabel(self.configCustom4Label)

   def InitUI(self):
      vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)
      hPanelBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      # Add Controls ----------------------------------------------------------
      joggingControls = self.CreateJoggingControls()
      vPanelBoxSizer.Add(joggingControls, 0, flag=wx.ALL|wx.EXPAND, border=5)

      positionStatusControls = self.CreatePositionStatusControls()
      hPanelBoxSizer.Add(positionStatusControls, 0, flag=wx.EXPAND)

      gotoControls = self.CreateGotoControls()
      hPanelBoxSizer.Add(gotoControls, 0, flag=wx.LEFT|wx.EXPAND, border=10)

      utilControls = self.CreateUtilControls()
      hPanelBoxSizer.Add(utilControls, 0, flag=wx.LEFT|wx.EXPAND, border=10)

      vPanelBoxSizer.Add(hPanelBoxSizer, 1, flag=wx.ALL|wx.EXPAND, border=5)

      # Finish up init UI
      self.SetSizer(vPanelBoxSizer)
      self.Layout()

   def UpdateUI(self, stateData, statusData=None):
      self.stateData = stateData
      # adata is expected to be an array of strings as follows
      # statusData[0] : Machine state
      # statusData[1] : Machine X
      # statusData[2] : Machine Y
      # statusData[3] : Machine Z
      # statusData[4] : Work X
      # statusData[5] : Work Y
      # statusData[6] : Work Z
      if statusData is not None and self.useMachineWorkPosition:
         self.jX.SetValue(statusData[4])
         self.jY.SetValue(statusData[5])
         self.jZ.SetValue(statusData[6])

      if stateData.serialPortIsOpen:
         self.resettoZeroPositionButton.Enable()
         self.resettoCurrentPositionButton.Enable()
         self.goZeroButton.Enable()
         self.goToCurrentPositionButton.Enable()
         self.goHomeButton.Enable()
         self.positiveXButton.Enable()
         self.negativeXButton.Enable()
         self.positiveYButton.Enable()
         self.negativeYButton.Enable()
         self.positiveZButton.Enable()
         self.negativeZButton.Enable()
         self.spindleOnButton.Enable()
         self.spindleOffButton.Enable()
         self.custom1Button.Enable()
         self.custom2Button.Enable()
         self.custom3Button.Enable()
         self.custom4Button.Enable()
      else:
         self.resettoZeroPositionButton.Disable()
         self.resettoCurrentPositionButton.Disable()
         self.goZeroButton.Disable()
         self.goToCurrentPositionButton.Disable()
         self.goHomeButton.Disable()
         self.positiveXButton.Disable()
         self.negativeXButton.Disable()
         self.positiveYButton.Disable()
         self.negativeYButton.Disable()
         self.positiveZButton.Disable()
         self.negativeZButton.Disable()
         self.spindleOnButton.Disable()
         self.spindleOffButton.Disable()
         self.custom1Button.Disable()
         self.custom2Button.Disable()
         self.custom3Button.Disable()
         self.custom4Button.Disable()


   def CreateJoggingControls(self):
      # Add Buttons -----------------------------------------------------------
      hButtonBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      vYButtonBoxSizer = wx.BoxSizer(wx.VERTICAL)
      vZButtonBoxSizer = wx.BoxSizer(wx.VERTICAL)
      vOtherButtonBoxSizer = wx.BoxSizer(wx.VERTICAL)

      buttonSize = (50,50)

      self.negativeXButton = wx.Button(self, label="-X", size=buttonSize)
      self.negativeXButton.SetToolTip(
         wx.ToolTip("Move X axis on negative direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnXNeg, self.negativeXButton)
      hButtonBoxSizer.Add(self.negativeXButton, flag=wx.ALIGN_CENTER_VERTICAL)

      self.positiveYButton = wx.Button(self, label="+Y", size=buttonSize)
      self.positiveYButton.SetToolTip(
         wx.ToolTip("Move Y axis on positive direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnYPos, self.positiveYButton)
      vYButtonBoxSizer.Add(self.positiveYButton)

      self.negativeYButton = wx.Button(self, label="-Y", size=buttonSize)
      self.negativeYButton.SetToolTip(
         wx.ToolTip("Move Y axis on negative direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnYNeg, self.negativeYButton)
      vYButtonBoxSizer.Add(self.negativeYButton)
      hButtonBoxSizer.Add(vYButtonBoxSizer, flag=wx.ALIGN_CENTER_VERTICAL)

      self.positiveXButton = wx.Button(self, label="+X", size=buttonSize)
      self.positiveXButton.SetToolTip(
         wx.ToolTip("Move X axis on positive direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnXPos, self.positiveXButton)
      hButtonBoxSizer.Add(self.positiveXButton, flag=wx.ALIGN_CENTER_VERTICAL)

      spacerText = wx.StaticText(self, label="   ")
      hButtonBoxSizer.Add(spacerText, flag=wx.ALIGN_CENTER_VERTICAL)

      self.positiveZButton = wx.Button(self, label="+Z", size=buttonSize)
      self.positiveZButton.SetToolTip(
         wx.ToolTip("Move Z axis on positive direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnZPos, self.positiveZButton)
      vZButtonBoxSizer.Add(self.positiveZButton)

      self.negativeZButton = wx.Button(self, label="-Z", size=buttonSize)
      self.negativeZButton.SetToolTip(
         wx.ToolTip("Move Z axis on negative direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnZNeg, self.negativeZButton)
      vZButtonBoxSizer.Add(self.negativeZButton)
      hButtonBoxSizer.Add(vZButtonBoxSizer, flag=wx.ALIGN_CENTER_VERTICAL)

      spacerText = wx.StaticText(self, label="     ")
      hButtonBoxSizer.Add(spacerText, flag=wx.ALIGN_CENTER_VERTICAL)

      self.spindleOnButton = wx.Button(self, label="SP ON", size=(60,50))
      self.spindleOnButton.SetToolTip(wx.ToolTip("Spindle ON"))
      self.Bind(wx.EVT_BUTTON, self.OnSpindleOn, self.spindleOnButton)
      vOtherButtonBoxSizer.Add(self.spindleOnButton)

      self.spindleOffButton = wx.Button(self, label="SP OFF", size=(60,50))
      self.spindleOffButton.SetToolTip(wx.ToolTip("Spindle OFF"))
      self.Bind(wx.EVT_BUTTON, self.OnSpindleOff, self.spindleOffButton)
      vOtherButtonBoxSizer.Add(self.spindleOffButton)

      hButtonBoxSizer.Add(vOtherButtonBoxSizer, flag=wx.ALIGN_BOTTOM)

      return hButtonBoxSizer

   def CreatePositionStatusControls(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # add status controls
      spinText = wx.StaticText(self, -1, "Step Size:  ")
      vBoxSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      self.spinCtrl = fs.FloatSpin(self, -1,
         min_val=0, max_val=99999, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      self.spinCtrl.SetFormat("%f")
      self.spinCtrl.SetDigits(4)

      vBoxSizer.Add(self.spinCtrl, 0,
         flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, border=5)

      spinText = wx.StaticText(self, -1, "Jogging Status:  ")
      vBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL)

      flexGridSizer = wx.FlexGridSizer(4,2)
      vBoxSizer.Add(flexGridSizer,0 , flag=wx.ALL|wx.EXPAND, border=5)

      # Add X pos
      xText = wx.StaticText(self, label="X:")
      self.jX = wx.TextCtrl(self, value=gZeroString)
      flexGridSizer.Add(xText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jX, 1, flag=wx.EXPAND)

      # Add Y Pos
      yText = wx.StaticText(self, label="Y:")
      self.jY = wx.TextCtrl(self, value=gZeroString)
      flexGridSizer.Add(yText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jY, 1, flag=wx.EXPAND)

      # Add Z Pos
      zText = wx.StaticText(self, label="Z:")
      self.jZ = wx.TextCtrl(self, value=gZeroString)
      flexGridSizer.Add(zText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jZ, 1, flag=wx.EXPAND)

      # Add Spindle status
      spindleText = wx.StaticText(self, label="SP:")
      self.jSpindle = wx.TextCtrl(self, value=gOffString, style=wx.TE_READONLY)
      self.jSpindle.SetBackgroundColour(gReadOnlyBkColor)
      flexGridSizer.Add(spindleText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jSpindle, 1, flag=wx.EXPAND)

      # Add Checkbox for sync with work position
      self.useWorkPosCheckBox = wx.CheckBox (self, label="Use Work Pos")
      self.useWorkPosCheckBox.SetToolTip(
         wx.ToolTip("Use Machine status to update Jogging position (experimental)"))
      self.Bind(wx.EVT_CHECKBOX, self.OnUseMachineWorkPosition, self.useWorkPosCheckBox)
      vBoxSizer.Add(self.useWorkPosCheckBox)

      return vBoxSizer

   def CreateGotoControls(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      spinText = wx.StaticText(self, -1, "")
      vBoxSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      # add Buttons
      self.resettoZeroPositionButton = wx.Button(self, label="Reset to Zero")
      self.resettoZeroPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToZeroPos, self.resettoZeroPositionButton)
      vBoxSizer.Add(self.resettoZeroPositionButton, flag=wx.TOP|wx.EXPAND, border=5)

      self.goZeroButton = wx.Button(self, label="Goto Zero")
      self.goZeroButton.SetToolTip(
         wx.ToolTip("Move to Machine Working position X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnGoZero, self.goZeroButton)
      vBoxSizer.Add(self.goZeroButton, flag=wx.EXPAND)

      self.resettoCurrentPositionButton = wx.Button(self, label="Reset to Jog")
      self.resettoCurrentPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToCurrentPos, self.resettoCurrentPositionButton)
      vBoxSizer.Add(self.resettoCurrentPositionButton, flag=wx.EXPAND)

      self.goToCurrentPositionButton = wx.Button(self, label="Goto Jog")
      self.goToCurrentPositionButton.SetToolTip(
         wx.ToolTip("Move to to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnGoPos, self.goToCurrentPositionButton)
      vBoxSizer.Add(self.goToCurrentPositionButton, flag=wx.EXPAND)

      self.goHomeButton = wx.Button(self, label="Goto Home")
      self.goHomeButton.SetToolTip(
         wx.ToolTip("Execute Machine Homing Cycle"))
      self.Bind(wx.EVT_BUTTON, self.OnGoHome, self.goHomeButton)
      vBoxSizer.Add(self.goHomeButton, flag=wx.EXPAND)


      return vBoxSizer

   def CreateUtilControls(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      spinText = wx.StaticText(self, -1, "")
      vBoxSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      # add position stack
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      self.pushStackButton = wx.Button(self, label="+", style=wx.BU_EXACTFIT)
      self.pushStackButton.SetToolTip(
         wx.ToolTip("Adds current jog position values to jog memory stack"))
      self.Bind(wx.EVT_BUTTON, self.OnPushStack, self.pushStackButton)
      hBoxSizer.Add(self.pushStackButton, 1, flag=wx.EXPAND)

      self.jogMemoryStackComboBox = wx.combo.BitmapComboBox(self, -1, value="", size=(10,-1),
         choices=[], style=wx.CB_READONLY|wx.CB_DROPDOWN)
      self.jogMemoryStackComboBox.SetToolTip(wx.ToolTip("jog memory stack"))
      self.Bind(wx.EVT_COMBOBOX, self.OnPopStack, self.jogMemoryStackComboBox)
      hBoxSizer.Add(self.jogMemoryStackComboBox, 1, flag=wx.EXPAND)

      vBoxSizer.Add(hBoxSizer, flag=wx.TOP|wx.EXPAND, border=5)

      # add custom buttons
      self.custom1Button = wx.Button(self, label=self.configCustom1Label)
      self.custom1Button.SetToolTip(wx.ToolTip("Move to pre-defined position (1)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom1Button, self.custom1Button)
      vBoxSizer.Add(self.custom1Button, flag=wx.EXPAND)

      self.custom2Button = wx.Button(self, label=self.configCustom2Label)
      self.custom2Button.SetToolTip(wx.ToolTip("Move to pre-defined position (2)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom2Button, self.custom2Button)
      vBoxSizer.Add(self.custom2Button, flag=wx.EXPAND)

      self.custom3Button = wx.Button(self, label=self.configCustom3Label)
      self.custom3Button.SetToolTip(wx.ToolTip("Move to pre-defined position (3)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom3Button, self.custom3Button)
      vBoxSizer.Add(self.custom3Button, flag=wx.EXPAND)

      self.custom4Button = wx.Button(self, label=self.configCustom4Label)
      self.custom4Button.SetToolTip(wx.ToolTip("Move to pre-defined position (4)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom4Button, self.custom4Button)
      vBoxSizer.Add(self.custom4Button, flag=wx.EXPAND)

      return vBoxSizer

   def AxisJog(self, staticControl, cmdString, opAdd):
      fAxisPos = float(staticControl.GetValue())

      if opAdd:
         fAxisPos += self.spinCtrl.GetValue()
      else:
         fAxisPos -= self.spinCtrl.GetValue()

      fAxisStrPos = gNumberFormatString % (fAxisPos)
      staticControl.SetValue(fAxisStrPos)
      self.mainWindow.SerialWrite(cmdString.replace("<VAL>",fAxisStrPos))

   def OnXPos(self, e):
      self.AxisJog(self.jX, gGRBL_CMD_JOG_X, opAdd=True)

   def OnXNeg(self, e):
      self.AxisJog(self.jX, gGRBL_CMD_JOG_X, opAdd=False)

   def OnYPos(self, e):
      self.AxisJog(self.jY, gGRBL_CMD_JOG_Y, opAdd=True)

   def OnYNeg(self, e):
      self.AxisJog(self.jY, gGRBL_CMD_JOG_Y, opAdd=False)

   def OnZPos(self, e):
      self.AxisJog(self.jZ, gGRBL_CMD_JOG_Z, opAdd=True)

   def OnZNeg(self, e):
      self.AxisJog(self.jZ, gGRBL_CMD_JOG_Z, opAdd=False)

   def OnSpindleOn(self, e):
      self.jSpindle.SetValue(gOnString)
      self.mainWindow.SerialWrite(gGRBL_CMD_SPINDLE_ON)

   def OnSpindleOff(self, e):
      self.jSpindle.SetValue(gOffString)
      self.mainWindow.SerialWrite(gGRBL_CMD_SPINDLE_OFF)

   def OnUseMachineWorkPosition(self, e):
      self.useMachineWorkPosition = e.IsChecked()

   def OnResetToZeroPos(self, e):
      self.jX.SetValue(gZeroString)
      self.jY.SetValue(gZeroString)
      self.jZ.SetValue(gZeroString)
      self.mainWindow.SerialWrite(gGRBL_CMD_RESET_TO_ZERO_POS)

   def OnResetToCurrentPos(self, e):
      rstCmd = gGRBL_CMD_RESET_TO_VAL_POS
      rstCmd = rstCmd.replace("<XVAL>", self.jX.GetValue())
      rstCmd = rstCmd.replace("<YVAL>", self.jY.GetValue())
      rstCmd = rstCmd.replace("<ZVAL>", self.jZ.GetValue())
      self.mainWindow.SerialWrite(rstCmd)

   def OnGoZero(self, e):
      self.jX.SetValue(gZeroString)
      self.jY.SetValue(gZeroString)
      self.jZ.SetValue(gZeroString)
      self.mainWindow.SerialWrite(gGRBL_CMD_GO_ZERO)

   def OnGoPos(self, e):
      goPosCmd = gGRBL_CMD_GO_POS
      goPosCmd = goPosCmd.replace("<XVAL>", self.jX.GetValue())
      goPosCmd = goPosCmd.replace("<YVAL>", self.jY.GetValue())
      goPosCmd = goPosCmd.replace("<ZVAL>", self.jZ.GetValue())
      self.mainWindow.SerialWrite(goPosCmd)

   def OnGoHome(self, e):
      self.mainWindow.SerialWrite(gGRBL_CMD_EXE_HOME_CYCLE)

   def OnPushStack(self, e):
      xVal = self.jX.GetValue()
      yVal = self.jY.GetValue()
      zVal = self.jZ.GetValue()

      self.jogMemoryStackComboBox.Append("X%s,Y%s,Z%s" % (xVal, yVal, zVal))

   def OnPopStack(self, e):
      strXYZ = self.jogMemoryStackComboBox.GetValue()
      self.jX.SetValue(re.search("X(\S+),Y", strXYZ).group(1))
      self.jY.SetValue(re.search("Y(\S+),Z", strXYZ).group(1))
      self.jZ.SetValue(re.search("Z(\S+)", strXYZ).group(1))

   def OnCustomButton(self, xo, xv, yo, yv, zo, zv):
      fXPos = float(self.jX.GetValue())
      fYPos = float(self.jY.GetValue())
      fZPos = float(self.jZ.GetValue())
      fXVal = float(xv)
      fYVal = float(yv)
      fZVal = float(zv)

      fXnp = fXVal
      if xo:
         fXnp = fXPos + fXVal

      fYnp = fYVal
      if yo:
         fYnp = fYPos + fYVal

      fZnp = fZVal
      if zo:
         fZnp = fZPos + fZVal

      self.jX.SetValue(str(fXnp))
      self.jY.SetValue(str(fYnp))
      self.jZ.SetValue(str(fZnp))

      goPosCmd = gGRBL_CMD_GO_POS
      goPosCmd = goPosCmd.replace("<XVAL>", str(fXnp))
      goPosCmd = goPosCmd.replace("<YVAL>", str(fYnp))
      goPosCmd = goPosCmd.replace("<ZVAL>", str(fZnp))
      self.mainWindow.SerialWrite(goPosCmd)


   def OnCustom1Button(self, e):
      self.OnCustomButton(
         self.configCustom1XIsOffset, self.configCustom1XValue,
         self.configCustom1YIsOffset, self.configCustom1YValue,
         self.configCustom1ZIsOffset, self.configCustom1ZValue
      )

   def OnCustom2Button(self, e):
      self.OnCustomButton(
         self.configCustom2XIsOffset, self.configCustom2XValue,
         self.configCustom2YIsOffset, self.configCustom2YValue,
         self.configCustom2ZIsOffset, self.configCustom2ZValue
      )

   def OnCustom3Button(self, e):
      self.OnCustomButton(
         self.configCustom3XIsOffset, self.configCustom3XValue,
         self.configCustom3YIsOffset, self.configCustom3YValue,
         self.configCustom3ZIsOffset, self.configCustom3ZValue
      )

   def OnCustom4Button(self, e):
      self.OnCustomButton(
         self.configCustom4XIsOffset, self.configCustom4XValue,
         self.configCustom4YIsOffset, self.configCustom4YValue,
         self.configCustom4ZIsOffset, self.configCustom4ZValue
      )

   def OnRefresh(self, e):
      pass


"""----------------------------------------------------------------------------
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
   gcsMainWindow:
   Main Window Inits the UI and other panels, it also controls the worker
   threads and resources such as serial port.
-------------------------------------------------------------------------------
----------------------------------------------------------------------------"""
class gcsMainWindow(wx.Frame):

   def __init__(self, parent, id=wx.ID_ANY, title="", cmd_line_options=None,
      pos=wx.DefaultPosition, size=(800, 600), style=wx.DEFAULT_FRAME_STYLE):

      wx.Frame.__init__(self, parent, id, title, pos, size, style)

      # init config file
      self.configFile = wx.FileConfig("gcs", style=wx.CONFIG_USE_LOCAL_FILE)

      self.SetIcon(imgGCSBlack32x32.GetIcon())

      # register for thread events
      EVT_THREAD_QUEUE_EVENT(self, self.OnThreadEvent)

      # create serial obj
      self.serPort = serial.Serial()

      # create app data obj
      self.stateData = gcsStateData()

      # create app data obj
      self.configData = gcsConfigData()
      self.configData.Load(self.configFile)
      self.configData.Add('/link/PortList', self.GetSerialPortList())
      self.configData.Add('/link/BaudList', self.GetSerialBaudRateList())
      self.InitConfig()

      # init some variables
      self.serialPortThread = None
      self.machineAutoRefreshTimer = None

      self.cmdLineOptions = cmd_line_options

      # thread communication queues
      self.mw2tQueue = Queue.Queue()
      self.t2mwQueue = Queue.Queue()

      # register for close events
      self.Bind(wx.EVT_CLOSE, self.OnClose)

      self.InitUI()
      self.Centre()
      self.Show()

   def InitConfig(self):
      self.saveBackupFile = self.configData.Get('/mainApp/BackupFile')
      self.maxFileHistory = self.configData.Get('/mainApp/MaxFileHistory')
      self.roundInch2mm = self.configData.Get('/mainApp/RoundInch2mm')
      self.roundmm2Inch = self.configData.Get('/mainApp/Roundmm2Inch')
      self.linkPort = self.configData.Get('/link/Port')
      self.linkBaud = self.configData.Get('/link/Baud')
      self.machineAutoRefresh = self.configData.Get('/machine/AutoRefresh')
      self.machineAutoRefreshPeriod = self.configData.Get('/machine/AutoRefreshPeriod')

   def InitUI(self):
      """ Init main UI """

      # init aui manager
      self.aui_mgr = aui.AuiManager()

      # notify AUI which frame to use
      self.aui_mgr.SetManagedWindow(self)

      #self.connectionPanel = gcsConnectionPanel(self)
      self.machineStatusPanel = gcsMachineStatusPanel(self)
      self.CV2Panel = gcsCV2Panel(self, self.configData, self.cmdLineOptions)
      self.machineJoggingPanel = gcsJoggingPanel(self, self.configData)

      # output Window
      self.outputText = gcsStcStyledTextCtrl(self, self.configData, style=wx.NO_BORDER)
      wx.Log_SetActiveTarget(gcsLog(self.outputText))

      # for serious debugging
      #wx.Log_SetActiveTarget(wx.LogStderr())
      #wx.Log_SetTraceMask(wx.TraceMessages)

      # main gcode list control
      self.gcText = gcsGcodeStcStyledTextCtrl(self, self.configData, style=wx.NO_BORDER)

      # cli interface
      self.cliPanel = gcsCliPanel(self, self.configData)
      self.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter, self.cliPanel.comboBox)
      self.cliPanel.Load(self.configFile)

      # add the panes to the manager
      self.aui_mgr.AddPane(self.gcText,
         aui.AuiPaneInfo().Name("GCODE_PANEL").CenterPane().Caption("G-Code")\
            .CloseButton(True).MaximizeButton(True).BestSize(600,600))


      self.aui_mgr.AddPane(self.cliPanel,
         aui.AuiPaneInfo().Name("CLI_PANEL").Bottom().Row(2).Caption("Command")\
            .CloseButton(True).MaximizeButton(True).BestSize(600,30)
      )

      self.aui_mgr.AddPane(self.outputText,
         aui.AuiPaneInfo().Name("OUTPUT_PANEL").Bottom().Position(1).Caption("Output")\
            .CloseButton(True).MaximizeButton(True)
      )

      self.aui_mgr.AddPane(self.CV2Panel,
         aui.AuiPaneInfo().Name("CV2_PANEL").Right().Row(1).Caption("Computer Vision")\
            .CloseButton(True).MaximizeButton(True).BestSize(640,530).Hide().Layer(1)
      )

      self.aui_mgr.AddPane(self.machineJoggingPanel,
         aui.AuiPaneInfo().Name("MACHINE_JOGGING_PANEL").Right().Row(1).Caption("Machine Jogging")\
            .CloseButton(True).MaximizeButton(True).BestSize(360,340).Layer(1)
      )

      self.aui_mgr.AddPane(self.machineStatusPanel,
         aui.AuiPaneInfo().Name("MACHINE_STATUS_PANEL").Right().Row(1).Caption("Machine Status")\
            .CloseButton(True).MaximizeButton(True).BestSize(320,180).Layer(1)
      )


      self.CreateMenu()
      self.CreateToolBar()

      # tell the manager to "commit" all the changes just made
      self.aui_mgr.SetAGWFlags(self.aui_mgr.GetAGWFlags()|aui.AUI_MGR_ALLOW_ACTIVE_PANE )

      # load default layout
      perspectiveDefault = self.aui_mgr.SavePerspective()
      self.SaveLayoutData('/mainApp/ResetLayout')

      self.LoadLayoutData('/mainApp/DefaultLayout', False)

      # finish up
      self.aui_mgr.Update()
      wx.CallAfter(self.UpdateUI)
      self.SetPC(0)

   def CreateMenu(self):

      # Create the menubar
      #self.menuBar = FM.FlatMenuBar(self, wx.ID_ANY, 32, 5, options = FM_OPT_SHOW_TOOLBAR | FM_OPT_SHOW_CUSTOMIZE)
      #self.menuBar = fm.FlatMenuBar(self, wx.ID_ANY, options=fm.FM_OPT_SHOW_TOOLBAR)
      self.menuBar = wx.MenuBar()

      #------------------------------------------------------------------------
      # File menu
      fileMenu = wx.Menu()
      self.menuBar.Append(fileMenu,                            "&File")

      openItem = wx.MenuItem(fileMenu, wx.ID_OPEN,             "&Open")
      openItem.SetBitmap(imgOpen.GetBitmap())
      fileMenu.AppendItem(openItem)

      recentMenu = wx.Menu()
      fileMenu.AppendMenu(wx.ID_ANY,                           "&Recent Files",
         recentMenu)

      # load history
      self.fileHistory = wx.FileHistory(self.maxFileHistory)
      self.fileHistory.Load(self.configFile)
      self.fileHistory.UseMenu(recentMenu)
      self.fileHistory.AddFilesToMenu()

      saveItem = wx.MenuItem(fileMenu, wx.ID_SAVE,             "&Save")
      if os.name != 'nt':
         saveItem.SetBitmap(imgSave.GetBitmap())
      fileMenu.AppendItem(saveItem)

      saveAsItem = wx.MenuItem(fileMenu, wx.ID_SAVEAS,         "Save &As")
      if os.name != 'nt':
         saveAsItem.SetBitmap(imgSave.GetBitmap())
      fileMenu.AppendItem(saveAsItem)

      exitItem = wx.MenuItem(fileMenu, wx.ID_EXIT,             "E&xit")
      exitItem.SetBitmap(imgExit.GetBitmap())
      fileMenu.AppendItem(exitItem)

      #------------------------------------------------------------------------
      # Edit menu
      #viewEdit = wx.Menu()
      #self.menuBar.Append(viewEdit,                   "&Edit")

      #viewEdit.Append(wx.ID_PREFERENCES,              "&Settings")

      #------------------------------------------------------------------------
      # View menu
      viewMenu = wx.Menu()
      self.menuBar.Append(viewMenu,                            "&View")

      viewMenu.AppendCheckItem(gID_MENU_MAIN_TOOLBAR,          "&Main Tool Bar")
      viewMenu.AppendCheckItem(gID_MENU_RUN_TOOLBAR,           "&Run Tool Bar")
      viewMenu.AppendCheckItem(gID_MENU_STATUS_TOOLBAR,        "Status &Tool Bar")
      viewMenu.AppendSeparator()
      viewMenu.AppendCheckItem(gID_MENU_OUTPUT_PANEL,          "&Output")
      viewMenu.AppendCheckItem(gID_MENU_COMAMND_PANEL,         "&Command (CLI)")
      viewMenu.AppendCheckItem(gID_MENU_MACHINE_STATUS_PANEL,  "Machine &Status")
      viewMenu.AppendCheckItem(gID_MENU_MACHINE_JOGGING_PANEL, "Machine &Jogging")
      viewMenu.AppendCheckItem(gID_MENU_CV2_PANEL,             "Computer &Vision")
      viewMenu.AppendSeparator()
      viewMenu.Append(gID_MENU_LOAD_DEFAULT_LAYOUT,            "&Load Layout")
      viewMenu.Append(gID_MENU_SAVE_DEFAULT_LAYOUT,            "S&ave Layout")
      viewMenu.Append(gID_MENU_RESET_DEFAULT_LAYOUT,           "R&eset Layout")
      #viewMenu.Append(gID_MENU_LOAD_LAYOUT,                    "Loa&d Layout...")
      #viewMenu.Append(gID_MENU_SAVE_LAYOUT,                    "Sa&ve Layout...")
      viewMenu.AppendSeparator()

      settingsItem = wx.MenuItem(viewMenu, wx.ID_PREFERENCES,     "&Settings")
      settingsItem.SetBitmap(imgSettings.GetBitmap())
      viewMenu.AppendItem(settingsItem)


      #------------------------------------------------------------------------
      # Run menu
      runMenu = wx.Menu()
      self.menuBar.Append(runMenu,                    "&Run")

      runItem = wx.MenuItem(runMenu, gID_MENU_RUN,    "&Run\tF5")
      if os.name != 'nt':
         runItem.SetBitmap(imgPlay.GetBitmap())
      runMenu.AppendItem(runItem)

      stepItem = wx.MenuItem(runMenu, gID_MENU_STEP,  "S&tep")
      if os.name != 'nt':
         stepItem.SetBitmap(imgStep.GetBitmap())
      runMenu.AppendItem(stepItem)

      stopItem = wx.MenuItem(runMenu, gID_MENU_STOP,  "&Stop")
      if os.name != 'nt':
         stopItem.SetBitmap(imgStop.GetBitmap())
      runMenu.AppendItem(stopItem)

      runMenu.AppendSeparator()
      breakItem = wx.MenuItem(runMenu, gID_MENU_BREAK_TOGGLE,
                                                      "Brea&kpoint Toggle\tF9")
      if os.name != 'nt':
         breakItem.SetBitmap(imgBreak.GetBitmap())
      runMenu.AppendItem(breakItem)

      runMenu.Append(gID_MENU_BREAK_REMOVE_ALL,       "Breakpoint &Remove All")
      runMenu.AppendSeparator()

      setPCItem = wx.MenuItem(runMenu, gID_MENU_SET_PC,"Set &PC")
      if os.name != 'nt':
         setPCItem.SetBitmap(imgMapPin.GetBitmap())
      runMenu.AppendItem(setPCItem)

      gotoPCItem = wx.MenuItem(runMenu, gID_MENU_GOTO_PC,
                                                      "&Goto PC")
      if os.name != 'nt':
         gotoPCItem.SetBitmap(imgGotoMapPin.GetBitmap())
      runMenu.AppendItem(gotoPCItem)

      runMenu.AppendSeparator()

      abortItem = wx.MenuItem(runMenu, gID_MENU_ABORT,"&Abort")
      if os.name != 'nt':
         abortItem.SetBitmap(imgAbort.GetBitmap())
      runMenu.AppendItem(abortItem)

      #------------------------------------------------------------------------
      # Tool menu
      toolMenu = wx.Menu()
      self.menuBar.Append(toolMenu,                   "&Tools")

      toolMenu.Append(gID_MENU_IN2MM,                 "&Inch to mm")
      toolMenu.Append(gID_MENU_MM2IN,                 "&mm to Inch")
      toolMenu.AppendSeparator()
      toolMenu.Append(gID_MENU_G812G01,               "&G81 to G01")

      #------------------------------------------------------------------------
      # Help menu
      helpMenu = wx.Menu()
      self.menuBar.Append(helpMenu,                   "&Help")

      aboutItem = wx.MenuItem(helpMenu, wx.ID_ABOUT,  "&About", "About GCS")
      aboutItem.SetBitmap(imgAbout.GetBitmap())
      helpMenu.AppendItem(aboutItem)


      #------------------------------------------------------------------------
      # Bind events to handlers

      #------------------------------------------------------------------------
      # File menu bind
      self.Bind(wx.EVT_MENU,        self.OnFileOpen,     id=wx.ID_OPEN)
      self.Bind(wx.EVT_MENU_RANGE,  self.OnFileHistory,  id=wx.ID_FILE1, id2=wx.ID_FILE9)
      self.Bind(wx.EVT_MENU,        self.OnFileSave,     id=wx.ID_SAVE)
      self.Bind(wx.EVT_MENU,        self.OnFileSaveAs,   id=wx.ID_SAVEAS)
      self.Bind(wx.EVT_MENU,        self.OnClose,        id=wx.ID_EXIT)
      self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN,
                           self.OnDropDownToolBarOpen,   id=gID_TOOLBAR_OPEN)

      self.Bind(wx.EVT_UPDATE_UI, self.OnFileSaveUpdate, id=wx.ID_SAVE)
      self.Bind(wx.EVT_UPDATE_UI, self.OnFileSaveAsUpdate,
                                                         id=wx.ID_SAVEAS)

      #------------------------------------------------------------------------
      # View menu bind
      self.Bind(wx.EVT_MENU, self.OnSettings,            id=wx.ID_PREFERENCES)

      #------------------------------------------------------------------------
      # View menu bind
      self.Bind(wx.EVT_MENU, self.OnMainToolBar,         id=gID_MENU_MAIN_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnRunToolBar,          id=gID_MENU_RUN_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnStatusToolBar,       id=gID_MENU_STATUS_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnOutput,              id=gID_MENU_OUTPUT_PANEL)
      self.Bind(wx.EVT_MENU, self.OnCommand,             id=gID_MENU_COMAMND_PANEL)
      self.Bind(wx.EVT_MENU, self.OnMachineStatus,       id=gID_MENU_MACHINE_STATUS_PANEL)
      self.Bind(wx.EVT_MENU, self.OnMachineJogging,      id=gID_MENU_MACHINE_JOGGING_PANEL)
      self.Bind(wx.EVT_MENU, self.OnComputerVision,      id=gID_MENU_CV2_PANEL)
      self.Bind(wx.EVT_MENU, self.OnLoadDefaultLayout,   id=gID_MENU_LOAD_DEFAULT_LAYOUT)
      self.Bind(wx.EVT_MENU, self.OnSaveDefaultLayout,   id=gID_MENU_SAVE_DEFAULT_LAYOUT)
      self.Bind(wx.EVT_MENU, self.OnResetDefaultLayout,  id=gID_MENU_RESET_DEFAULT_LAYOUT)

      self.Bind(wx.EVT_UPDATE_UI, self.OnMainToolBarUpdate,
                                                         id=gID_MENU_MAIN_TOOLBAR)
      self.Bind(wx.EVT_UPDATE_UI, self.OnRunToolBarUpdate,
                                                         id=gID_MENU_RUN_TOOLBAR)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStatusToolBarUpdate,
                                                         id=gID_MENU_STATUS_TOOLBAR)
      self.Bind(wx.EVT_UPDATE_UI, self.OnOutputUpdate,   id=gID_MENU_OUTPUT_PANEL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnCommandUpdate,  id=gID_MENU_COMAMND_PANEL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnMachineStatusUpdate,
                                                         id=gID_MENU_MACHINE_STATUS_PANEL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnMachineJoggingUpdate,
                                                         id=gID_MENU_MACHINE_JOGGING_PANEL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnComputerVisionUpdate,
                                                         id=gID_MENU_CV2_PANEL)

      #------------------------------------------------------------------------
      # Run menu bind
      self.Bind(wx.EVT_MENU, self.OnRun,                 id=gID_MENU_RUN)
      self.Bind(wx.EVT_MENU, self.OnStep,                id=gID_MENU_STEP)
      self.Bind(wx.EVT_MENU, self.OnStop,                id=gID_MENU_STOP)
      self.Bind(wx.EVT_MENU, self.OnBreakToggle,         id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_MENU, self.OnBreakRemoveAll,      id=gID_MENU_BREAK_REMOVE_ALL)
      self.Bind(wx.EVT_MENU, self.OnSetPC,               id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_MENU, self.OnGoToPC,              id=gID_MENU_GOTO_PC)
      self.Bind(wx.EVT_MENU, self.OnAbort,               id=gID_MENU_ABORT)

      self.Bind(wx.EVT_BUTTON, self.OnRun,               id=gID_MENU_RUN)
      self.Bind(wx.EVT_BUTTON, self.OnStep,              id=gID_MENU_STEP)
      self.Bind(wx.EVT_BUTTON, self.OnStop,              id=gID_MENU_STOP)
      self.Bind(wx.EVT_BUTTON, self.OnBreakToggle,       id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_BUTTON, self.OnSetPC,             id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_BUTTON, self.OnGoToPC,            id=gID_MENU_GOTO_PC)
      self.Bind(wx.EVT_BUTTON, self.OnAbort,             id=gID_MENU_ABORT)

      self.Bind(wx.EVT_UPDATE_UI, self.OnRunUpdate,      id=gID_MENU_RUN)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStepUpdate,     id=gID_MENU_STEP)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStopUpdate,     id=gID_MENU_STOP)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakToggleUpdate,
                                                         id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakRemoveAllUpdate,
                                                         id=gID_MENU_BREAK_REMOVE_ALL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnSetPCUpdate,    id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_UPDATE_UI, self.OnGoToPCUpdate,   id=gID_MENU_GOTO_PC)
      self.Bind(wx.EVT_UPDATE_UI, self.OnAbortUpdate,    id=gID_MENU_ABORT)

      #------------------------------------------------------------------------
      # tools menu bind
      self.Bind(wx.EVT_MENU, self.OnInch2mm,             id=gID_MENU_IN2MM)
      self.Bind(wx.EVT_MENU, self.Onmm2Inch,             id=gID_MENU_MM2IN)
      self.Bind(wx.EVT_MENU, self.OnG812G01,             id=gID_MENU_G812G01)

      self.Bind(wx.EVT_UPDATE_UI, self.OnInch2mmUpdate,  id=gID_MENU_IN2MM)
      self.Bind(wx.EVT_UPDATE_UI, self.Onmm2InchUpdate,  id=gID_MENU_MM2IN)
      self.Bind(wx.EVT_UPDATE_UI, self.OnG812G01Update,  id=gID_MENU_G812G01)

      #------------------------------------------------------------------------
      # Help menu bind
      self.Bind(wx.EVT_MENU, self.OnAbout,               id=wx.ID_ABOUT)


      #------------------------------------------------------------------------
      # Status tool bar
      self.Bind(wx.EVT_MENU, self.OnLinkStatus,          id=gID_TOOLBAR_LINK_STATUS)
      self.Bind(wx.EVT_MENU, self.OnGetMachineStatus,    id=gID_TOOLBAR_MACHINE_STATUS)


      #------------------------------------------------------------------------
      # Create shortcut keys for menu
      acceleratorTable = wx.AcceleratorTable([
         #(wx.ACCEL_ALT,       ord('X'),         wx.ID_EXIT),
         #(wx.ACCEL_CTRL,      ord('H'),         helpID),
         #(wx.ACCEL_CTRL,      ord('F'),         findID),
         (wx.ACCEL_NORMAL,    wx.WXK_F5,        gID_MENU_RUN),
         (wx.ACCEL_NORMAL,    wx.WXK_F9,        gID_MENU_BREAK_TOGGLE),
      ])

      self.SetAcceleratorTable(acceleratorTable)

      # finish up...
      self.SetMenuBar(self.menuBar)

   def CreateToolBar(self):
      iconSize = (16, 16)

      #------------------------------------------------------------------------
      # Main Tool Bar
      self.appToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
         agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            aui.AUI_TB_TEXT |
            aui.AUI_TB_HORZ_TEXT |
            #aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE
         )


      self.appToolBar.SetToolBitmapSize(iconSize)

      self.appToolBar.AddSimpleTool(gID_TOOLBAR_OPEN, "Open", imgOpen.GetBitmap(),
         "Open\tCtrl+O")

      self.appToolBar.AddSimpleTool(wx.ID_SAVE, "Save", imgSave.GetBitmap(),
         "Save\tCtrl+S")
      self.appToolBar.SetToolDisabledBitmap(wx.ID_SAVE, imgSaveDisabled.GetBitmap())

      self.appToolBar.AddSimpleTool(wx.ID_SAVEAS, "Save As", imgSave.GetBitmap(),
         "Save As")
      self.appToolBar.SetToolDisabledBitmap(wx.ID_SAVEAS, imgSaveDisabled.GetBitmap())

      self.appToolBar.SetToolDropDown(gID_TOOLBAR_OPEN, True)

      self.appToolBar.AddSeparator()

      self.appToolBarFind = wx.TextCtrl(self.appToolBar, size=(100,-1))
      self.appToolBar.AddControl(self.appToolBarFind)
      self.appToolBarFind.SetToolTipString("Find Text")
      self.appToolBar.AddSimpleTool(wx.ID_FIND, "", imgFind.GetBitmap(),
         "Find Next\tF3")

      self.appToolBarGotoLine = wx.TextCtrl(self.appToolBar, size=(50,-1))
      self.appToolBar.AddControl(self.appToolBarGotoLine)
      self.appToolBarGotoLine.SetToolTipString("Line Number")
      self.appToolBar.AddSimpleTool(wx.ID_FIND, "", imgGotoLine.GetBitmap(),
         "Goto Line")

      self.appToolBar.Realize()

      self.aui_mgr.AddPane(self.appToolBar,
         aui.AuiPaneInfo().Name("MAIN_TOOLBAR").Caption("Main Tool Bar").ToolbarPane().Top().Position(1))

      #------------------------------------------------------------------------
      # GCODE Tool Bar
      self.gcodeToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
         agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            #aui.AUI_TB_TEXT |
            #aui.AUI_TB_HORZ_TEXT |
            #aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE
      )

      self.gcodeToolBar.SetToolBitmapSize(iconSize)

      self.gcodeToolBar.AddSimpleTool(gID_MENU_RUN, "Run", imgPlay.GetBitmap(),
         "Run\tF5")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_RUN, imgPlayDisabled.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_STEP, "Step", imgStep.GetBitmap(),
         "Step")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_STEP, imgStepDisabled.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_STOP, "Stop", imgStop.GetBitmap(),
         "Stop")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_STOP, imgStopDisabled.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_BREAK_TOGGLE, "Break Toggle",
         imgBreak.GetBitmap(), "Breakpoint Toggle\tF9")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_BREAK_TOGGLE, imgBreakDisabled.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_SET_PC, "Set PC", imgMapPin.GetBitmap(),
         "Set PC")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_SET_PC, imgMapPinDisabled.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_GOTO_PC, "Goto PC", imgGotoMapPin.GetBitmap(),
         "Goto PC")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_GOTO_PC, imgGotoMapPinDisabled.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_ABORT, "Abort", imgAbort.GetBitmap(),
         "Abort")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_ABORT, imgAbortDisabled.GetBitmap())

      self.gcodeToolBar.Realize()

      self.aui_mgr.AddPane(self.gcodeToolBar,
         aui.AuiPaneInfo().Name("GCODE_TOOLBAR").Caption("Program Tool Bar").ToolbarPane().Top().Position(2).Gripper())

      #------------------------------------------------------------------------
      # Status Tool Bar
      self.statusToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
         agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            #aui.AUI_TB_TEXT |
            aui.AUI_TB_HORZ_TEXT |
            #aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE
      )

      self.statusToolBar.SetToolBitmapSize(iconSize)

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_LINK_STATUS, "123456789", imgPlugDisconnect.GetBitmap(),
         "Link Status (link/unlink)")
      self.statusToolBar.SetToolDisabledBitmap(gID_MENU_RUN, imgPlugDisconnect.GetBitmap())

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_PROGRAM_STATUS, "123456", imgProgram.GetBitmap(),
         "Program Status")
      self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_PROGRAM_STATUS, imgProgram.GetBitmap())

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_MACHINE_STATUS, "123456", imgMachine.GetBitmap(),
         "Machine Status (refresh)")
      self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_MACHINE_STATUS, imgMachineDisabled.GetBitmap())

      self.statusToolBar.Realize()

      self.aui_mgr.AddPane(self.statusToolBar,
         aui.AuiPaneInfo().Name("STATUS_TOOLBAR").Caption("Status Tool Bar").ToolbarPane().Top().Position(2).Gripper())

      # finish up
      self.appToolBar.Refresh()
      self.gcodeToolBar.Refresh()
      self.statusToolBar.Refresh()

   def UpdateUI(self):
      self.cliPanel.UpdateUI(self.stateData)
      self.gcText.UpdateUI(self.stateData)
      self.machineStatusPanel.UpdateUI(self.stateData)
      self.machineJoggingPanel.UpdateUI(self.stateData)
      self.CV2Panel.UpdateUI(self.stateData)

      # Force update tool bar items
      self.OnStatusToolBarForceUpdate()
      self.OnRunToolBarForceUpdate()

      self.aui_mgr.Update()

   """-------------------------------------------------------------------------
   gcsMainWindow: UI Event Handlers
   -------------------------------------------------------------------------"""

   #---------------------------------------------------------------------------
   # File Menu Handlers
   #---------------------------------------------------------------------------
   def OnFileOpen(self, e):
      """ File Open """
      # get current file data
      currentPath = self.stateData.gcodeFileName
      (currentDir, currentFile) = os.path.split(currentPath)

      if len(currentDir) == 0:
         currentDir = os.getcwd()

      # init file dialog
      dlgFile = wx.FileDialog(
         self, message="Choose a file",
         defaultDir=currentDir,
         defaultFile=currentFile,
         wildcard=gWILDCARD,
         style=wx.OPEN | wx.FD_FILE_MUST_EXIST
         )

      if dlgFile.ShowModal() == wx.ID_OK:
         # got file, open and present progress
         self.stateData.gcodeFileName = dlgFile.GetPath()
         self.lineNumber = 0

         # save history
         self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)
         self.fileHistory.Save(self.configFile)
         self.configFile.Flush()

         self.OnDoFileOpen(e, self.stateData.gcodeFileName)

   def OnDropDownToolBarOpen(self, e):
      if not e.IsDropDownClicked():
         self.OnFileOpen(e)
      else:
         toolbBar = e.GetEventObject()
         toolbBar.SetToolSticky(e.GetId(), True)

         historyCount =  self.fileHistory.GetCount()

         if historyCount > 0:
            # create the popup menu
            menuPopup = wx.Menu()

            for index in range(historyCount):
               m = wx.MenuItem(menuPopup, wx.ID_FILE1+index,
                  "&%d %s" % (index,self.fileHistory.GetHistoryFile(index)))
               menuPopup.AppendItem(m)

            # line up our menu with the button
            rect = toolbBar.GetToolRect(e.GetId())
            pt = toolbBar.ClientToScreen(rect.GetBottomLeft())
            pt = self.ScreenToClient(pt)

            self.PopupMenu(menuPopup, pt)

         # make sure the button is "un-stuck"
         toolbBar.SetToolSticky(e.GetId(), False)

   def OnFileHistory(self, e):
      fileNumber = e.GetId() - wx.ID_FILE1
      self.stateData.gcodeFileName = self.fileHistory.GetHistoryFile(fileNumber)
      self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)  # move up the list
      self.fileHistory.Save(self.configFile)
      self.configFile.Flush()

      self.OnDoFileOpen(e, self.stateData.gcodeFileName)

   def OnDoFileOpen(self, e, fileName=None):
      if os.path.exists(fileName):
         self.stateData.gcodeFileName = fileName

         readOnly = self.gcText.GetReadOnly()
         self.gcText.SetReadOnly(False)
         self.gcText.LoadFile(self.stateData.gcodeFileName)
         self.gcText.SetReadOnly(readOnly)

         self.stateData.fileIsOpen = True
         self.SetTitle("%s - %s" % (os.path.basename(self.stateData.gcodeFileName), __appname__))

         self.stateData.breakPoints = set()
         self.SetPC(0)
         self.gcText.GoToPC()
         self.UpdateUI()
      else:
         dlg = wx.MessageDialog(self,
            "The file doesn't exits.\n" \
            "File: %s\n\n" \
            "Please check the path and try again." % fileName, "",
            wx.OK|wx.ICON_STOP)
         result = dlg.ShowModal()
         dlg.Destroy()

      #self.gcText.SetReadOnly(True)

   def OnFileSave(self, e):
      if not self.stateData.fileIsOpen:
         self.OnFileSaveAs(e)
      else:
         if self.saveBackupFile:
            shutil.copyfile(self.stateData.gcodeFileName,self.stateData.gcodeFileName+"~")

         self.gcText.SaveFile(self.stateData.gcodeFileName)

   def OnFileSaveUpdate(self, e):
      e.Enable(self.gcText.GetModify())

   def OnFileSaveAs(self, e):
      # get current file data
      currentPath = self.stateData.gcodeFileName
      (currentDir, currentFile) = os.path.split(currentPath)

      if len(currentDir) == 0:
         currentDir = os.getcwd()

      # init file dialog
      dlgFile = wx.FileDialog(
         self, message="Create a file",
         defaultDir=currentDir,
         defaultFile=currentFile,
         wildcard=gWILDCARD,
         style=wx.SAVE
         )

      if dlgFile.ShowModal() == wx.ID_OK:
         # got file, open and present progress
         self.stateData.gcodeFileName = dlgFile.GetPath()
         self.lineNumber = 0

         # save history
         self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)
         self.fileHistory.Save(self.configFile)
         self.configFile.Flush()

         self.gcText.SaveFile(self.stateData.gcodeFileName)

         self.UpdateUI()

   def OnFileSaveAsUpdate(self, e):
      e.Enable(self.stateData.fileIsOpen or self.gcText.GetModify())


   #---------------------------------------------------------------------------
   # Edit Menu Handlers
   #---------------------------------------------------------------------------
   def OnSettings(self, e):
      #wx.LogMessage("Link Port: %s" % self.configData.dataLinkPort)
      #wx.LogMessage("Link Baud: %s" % self.configData.dataLinkBaud)
      #wx.LogMessage("Cli Save: %s" % str(self.configData.dataCliSaveCmdHistory))
      #wx.LogMessage("Cli Cmd: %s" % str(self.configData.dataCliCmdMaxHistory))
      #wx.LogMessage("Machine Auto: %s" % str(self.configData.dataMachineAutoRefresh))
      #wx.LogMessage("Machine Auto Period: %s" % str(self.configData.dataMachineAutoRefreshPeriod))


      dlg = gcsSettingsDialog(self, self.configData)

      result = dlg.ShowModal()

      if result == wx.ID_OK:
         dlg.UpdatConfigData()

         self.InitConfig()

         # re open serial port if open
         if self.stateData.serialPortIsOpen and \
            (self.stateData.serialPort != self.linkPort or self.stateData.serialBaud != self.linkBaud):

            self.SerialClose()
            self.SerialOpen(self.linkPort, self.linkBaud)

         if self.stateData.machineStatusAutoRefresh != self.machineAutoRefresh or \
            self.stateData.machineStatusAutoRefreshPeriod != self.machineAutoRefreshPeriod:

            self.AutoRefreshTimerStop()
            self.AutoRefreshTimerStart()

         self.gcText.UpdateSettings(self.configData)
         self.outputText.UpdateSettings(self.configData)
         self.cliPanel.UpdateSettings(self.configData)
         self.machineStatusPanel.UpdateSettings(self.configData)
         self.machineJoggingPanel.UpdateSettings(self.configData)
         self.CV2Panel.UpdateSettings(self.configData)

      dlg.Destroy()

      #wx.LogMessage("Link Port: %s" % self.configData.dataLinkPort)
      #wx.LogMessage("Link Baud: %s" % self.configData.dataLinkBaud)
      #wx.LogMessage("Cli Save: %s" % str(self.configData.dataCliSaveCmdHistory))
      #wx.LogMessage("Cli Cmd: %s" % str(self.configData.dataCliCmdMaxHistory))
      #wx.LogMessage("Machine Auto: %s" % str(self.configData.dataMachineAutoRefresh))
      #wx.LogMessage("Machine Auto Period: %s" % str(self.configData.dataMachineAutoRefreshPeriod))

   #---------------------------------------------------------------------------
   # View Menu Handlers
   #---------------------------------------------------------------------------
   def OnViewMenu(self, e, pane):
      panelInfo = self.aui_mgr.GetPane(pane)

      if panelInfo.IsShown():
         panelInfo.Hide()
      else:
         panelInfo.Show()

      self.aui_mgr.Update()

   def OnViewMenuUpdate(self, e, pane):
      panelInfo = self.aui_mgr.GetPane(pane)
      if panelInfo.IsShown():
         e.Check(True)
      else:
         e.Check(False)
      #self.aui_mgr.Update()

   def OnViewMenuToolBar(self, e, toolBar):
      self.OnViewMenu(e, toolBar)

      panelInfo = self.aui_mgr.GetPane(toolBar)
      if panelInfo.IsShown() and panelInfo.IsDocked():
         toolBar.SetGripperVisible(True)
         self.aui_mgr.Update()

   def OnMainToolBar(self, e):
      self.OnViewMenuToolBar(e, self.appToolBar)

   def OnMainToolBarUpdate(self, e):
      self.OnViewMenuUpdate(e, self.appToolBar)

   def OnRunToolBar(self, e):
      self.OnViewMenuToolBar(e, self.gcodeToolBar)

   def OnRunToolBarUpdate(self, e):
      self.OnViewMenuUpdate(e, self.gcodeToolBar)

   def OnStatusToolBar(self, e):
      self.OnViewMenuToolBar(e, self.statusToolBar)

   def OnStatusToolBarUpdate(self, e):
      self.OnViewMenuUpdate(e, self.statusToolBar)

   def OnOutput(self, e):
      self.OnViewMenu(e, self.outputText)

   def OnOutputUpdate(self, e):
      self.OnViewMenuUpdate(e, self.outputText)

   def OnCommand(self, e):
      self.OnViewMenu(e, self.cliPanel)

   def OnCommandUpdate(self, e):
      self.OnViewMenuUpdate(e, self.cliPanel)

   def OnMachineStatus(self, e):
      self.OnViewMenu(e, self.machineStatusPanel)

   def OnMachineStatusUpdate(self, e):
      self.OnViewMenuUpdate(e, self.machineStatusPanel)

   def OnMachineJogging(self, e):
      self.OnViewMenu(e, self.machineJoggingPanel)

   def OnMachineJoggingUpdate(self, e):
      self.OnViewMenuUpdate(e, self.machineJoggingPanel)

   def OnComputerVision(self, e):
      self.OnViewMenu(e, self.CV2Panel)

   def OnComputerVisionUpdate(self, e):
      self.OnViewMenuUpdate(e, self.CV2Panel)

   def OnLoadDefaultLayout(self, e):
      self.LoadLayoutData('/mainApp/DefaultLayout')
      self.aui_mgr.Update()

   def OnSaveDefaultLayout(self, e):
      self.SaveLayoutData('/mainApp/DefaultLayout')

   def OnResetDefaultLayout(self, e):
      self.configFile.DeleteGroup('/mainApp/DefaultLayout')
      self.LoadLayoutData('/mainApp/ResetLayout')

   #---------------------------------------------------------------------------
   # Run Menu/ToolBar Handlers
   #---------------------------------------------------------------------------
   def OnRunToolBarForceUpdate(self):
      self.OnRunUpdate()
      self.OnStepUpdate()
      self.OnStopUpdate()
      self.OnBreakToggleUpdate()
      self.OnSetPCUpdate()
      self.OnGoToPCUpdate()
      self.OnAbortUpdate()
      self.gcodeToolBar.Refresh()

   def OnRun(self, e):
      if self.serialPortThread is not None:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)

         self.mw2tQueue.put(threadEvent(gEV_CMD_RUN,
            [self.stateData.gcodeFileLines, self.stateData.programCounter, self.stateData.breakPoints]))
         self.mw2tQueue.join()

         self.gcText.GoToPC()
         self.stateData.swState = gSTATE_RUN
         self.UpdateUI()

   def OnRunUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen and \
         (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_RUN, state)

   def OnStep(self, e):
      if self.serialPortThread is not None:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)

         self.mw2tQueue.put(threadEvent(gEV_CMD_STEP,
            [self.stateData.gcodeFileLines, self.stateData.programCounter, self.stateData.breakPoints]))
         self.mw2tQueue.join()

         self.stateData.swState = gSTATE_STEP
         self.UpdateUI()

   def OnStepUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen and \
         (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_STEP, state)

   def OnStop(self, e):
      self.Stop()

   def OnStopUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen and \
         self.stateData.swState != gSTATE_IDLE and \
         self.stateData.swState != gSTATE_BREAK:

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_STOP, state)

   def OnBreakToggle(self, e):
      pc = self.gcText.GetCurrentLine()
      enable = False

      if pc in self.stateData.breakPoints:
         self.stateData.breakPoints.remove(pc)
      else:
         self.stateData.breakPoints.add(pc)
         enable = True

      self.gcText.UpdateBreakPoint(pc, enable)

   def OnBreakToggleUpdate(self, e=None):
      state = False
      if (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_BREAK_TOGGLE, state)

   def OnBreakRemoveAll(self, e):
      self.breakPoints = set()
      self.gcText.UpdateBreakPoint(-1, False)

   def OnBreakRemoveAllUpdate(self, e):
      if (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         e.Enable(True)
      else:
         e.Enable(False)

   def OnSetPC(self, e):
      self.SetPC()

   def OnSetPCUpdate(self, e=None):
      state = False
      if (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_SET_PC, state)

   def OnGoToPC(self, e):
      self.gcText.GoToPC()

   def OnGoToPCUpdate(self, e=None):
      state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_GOTO_PC, state)

   def OnAbort(self, e):
      self.serPort.write("!\n")
      self.Stop()
      self.outputText.AppendText("> !\n")
      self.outputText.AppendText(
         "*** ABORT!!! a feed-hold command (!) has been sent to Grbl, you can\n"\
         "    use cycle-restart command (~) to continue.\n"\
         "    \n"
         "    Note: If this is not desirable please reset Grbl, by closing and opening\n"\
         "    the serial link port.\n")

   def OnAbortUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen:
         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_ABORT, state)

   #---------------------------------------------------------------------------
   # Tools Menu Handlers
   #---------------------------------------------------------------------------
   def OnToolUpdateIdle(self, e):
      state = False
      if (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):
         state = True

      e.Enable(state)

   def OnInch2mm(self, e):
      dlg = wx.MessageDialog(self,
         "Your about to convert the current file from inches to metric.\n"\
         "This is an experimental feature, do you want to continue?",
         "",
         wx.OK|wx.CANCEL|wx.ICON_WARNING)

      if dlg.ShowModal() == wx.ID_OK:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)
         lines = self.ConvertInchAndmm(
            self.stateData.gcodeFileLines, in_to_mm=True, round_to=self.roundInch2mm)

         readOnly = self.gcText.GetReadOnly()
         self.gcText.SetReadOnly(False)
         self.gcText.SetText("".join(lines))
         self.gcText.SetReadOnly(readOnly)

      dlg.Destroy()

   def OnInch2mmUpdate(self, e):
      self.OnToolUpdateIdle(e)

   def Onmm2Inch(self, e):
      dlg = wx.MessageDialog(self,
         "Your about to convert the current file from metric to inches.\n"\
         "This is an experimental feature, do you want to continue?",
         "",
         wx.OK|wx.CANCEL|wx.ICON_WARNING)

      if dlg.ShowModal() == wx.ID_OK:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)
         lines = self.ConvertInchAndmm(
            self.stateData.gcodeFileLines, in_to_mm=False, round_to=self.roundmm2Inch)

         readOnly = self.gcText.GetReadOnly()
         self.gcText.SetReadOnly(False)
         self.gcText.SetText("".join(lines))
         self.gcText.SetReadOnly(readOnly)

      dlg.Destroy()

   def Onmm2InchUpdate(self, e):
      self.OnToolUpdateIdle(e)

   def OnG812G01(self, e):
      dlg = wx.MessageDialog(self,
         "Your about to convert the current file from G81 to G01.\n"\
         "This is an experimental feature, do you want to continue?",
         "",
         wx.OK|wx.CANCEL|wx.ICON_WARNING)

      if dlg.ShowModal() == wx.ID_OK:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)
         lines = self.ConvertG812G01(self.stateData.gcodeFileLines)

         readOnly = self.gcText.GetReadOnly()
         self.gcText.SetReadOnly(False)
         self.gcText.SetText("".join(lines))
         self.gcText.SetReadOnly(readOnly)

      dlg.Destroy()

   def OnG812G01Update(self, e):
      self.OnToolUpdateIdle(e)

   #---------------------------------------------------------------------------
   # Status Menu/ToolBar Handlers
   #---------------------------------------------------------------------------
   def OnStatusToolBarForceUpdate(self):
      # Link status
      if self.stateData.serialPortIsOpen:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Linked")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, imgPlugConnect.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, imgPlugConnect.GetBitmap())
      else:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Unlinked")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, imgPlugDisconnect.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, imgPlugDisconnect.GetBitmap())

      # Program status
      if self.stateData.swState == gSTATE_IDLE:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Idle")
      elif self.stateData.swState == gSTATE_RUN:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Run")
      elif self.stateData.swState == gSTATE_STEP:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Step")
      elif self.stateData.swState == gSTATE_BREAK:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Break")

      #Machine status
      self.statusToolBar.EnableTool(gID_TOOLBAR_MACHINE_STATUS, self.stateData.serialPortIsOpen)
      self.statusToolBar.SetToolLabel(gID_TOOLBAR_MACHINE_STATUS, self.stateData.machineStatusString)

      self.statusToolBar.Refresh()

   def OnLinkStatus(self, e):
      if self.stateData.serialPortIsOpen:
         self.SerialClose()
      else:
         self.SerialOpen(self.configData.Get('/link/Port'), self.configData.Get('/link/Baud'))

   def OnGetMachineStatus(self, e):
      self.GetMachineStatus()

   #---------------------------------------------------------------------------
   # Help Menu Handlers
   #---------------------------------------------------------------------------
   def OnAbout(self, e):
      # First we create and fill the info object
      aboutDialog = wx.AboutDialogInfo()
      aboutDialog.Name = __appname__
      aboutDialog.Version = __version__
      aboutDialog.Copyright = __copyright__
      if os.name == 'nt':
         aboutDialog.Description = wordwrap(__description__, 520, wx.ClientDC(self))
      else:
         aboutDialog.Description = __description__
      aboutDialog.WebSite = ("https://github.com/duembeg/gcs", "gcs home page")
      #aboutDialog.Developers = __authors__

      aboutDialog.License = __license_str__

      # Then we call wx.AboutBox giving it that info object
      wx.AboutBox(aboutDialog)

   #---------------------------------------------------------------------------
   # Other UI Handlers
   #---------------------------------------------------------------------------
   def OnCliEnter(self, e):
      cliCommand = self.cliPanel.GetCommand()

      if len(cliCommand) > 0:
         serialData = "%s\n" % (cliCommand)
         self.SerialWrite(serialData)

   def OnClose(self, e):
      if self.stateData.serialPortIsOpen:
         self.SerialClose()

      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_EXIT, None))
         self.mw2tQueue.join()

      self.cliPanel.Save(self.configFile)
      self.configData.Save(self.configFile)
      self.aui_mgr.UnInit()

      self.Destroy()
      e.Skip()

   """-------------------------------------------------------------------------
   gcsMainWindow: General Functions
   -------------------------------------------------------------------------"""
   def AutoRefreshTimerStart(self):
      self.stateData.machineStatusAutoRefresh = self.machineAutoRefresh
      self.stateData.machineStatusAutoRefreshPeriod = self.machineAutoRefreshPeriod

      if self.stateData.machineStatusAutoRefresh:
         if self.machineAutoRefreshTimer is not None:
            self.machineAutoRefreshTimer.Stop()
         else:
            t = self.machineAutoRefreshTimer = wx.Timer(self, gID_TIMER_MACHINE_REFRESH)
            self.Bind(wx.EVT_TIMER, self.OnAutoRefreshTimerAction, t)

         self.machineAutoRefreshTimer.Start(self.stateData.machineStatusAutoRefreshPeriod)

   def AutoRefreshTimerStop(self):
      if self.machineAutoRefreshTimer is not None:
         self.machineAutoRefreshTimer.Stop()

   def OnAutoRefreshTimerAction(self, e):
      if self.stateData.grblDetected and (self.stateData.swState == gSTATE_IDLE or \
         self.stateData.swState == gSTATE_BREAK):

         # only do this if we are in IDLE or BREAK, it will cause probelms
         # if status requets are sent randomly wile running program
         self.SerialWrite(gGRBL_CMD_GET_STATUS)

   def GetSerialPortList(self):
      spList = []

      if os.name == 'nt':
         # Scan for available ports.
         for i in range(256):
            try:
               s = serial.Serial(i)
               spList.append('COM'+str(i + 1))
               #s.close()
            except:# serial.SerialException:
                pass
      else:
         spList = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')

      if len(spList) < 1:
         spList = ['None']

      return spList

   def GetSerialBaudRateList(self):
      sbList = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
      return sbList

   def SerialOpen(self, port, baud):
      self.serPort.baudrate = baud

      if port != "None":
         portName = port
         if os.name == 'nt':
            portName=r"\\.\%s" % (str(port))

         self.serPort.port = portName
         self.serPort.timeout=1
         self.serPort.open()

         if self.serPort.isOpen():
            self.serialPortThread = gcsSserialPortThread(self, self.serPort, self.mw2tQueue,
               self.t2mwQueue, self.cmdLineOptions)

            self.stateData.serialPortIsOpen = True
            self.stateData.serialPort = port
            self.stateData.serialBaud = baud
            self.AutoRefreshTimerStart()
      else:
         dlg = wx.MessageDialog(self,
            "There is no valid serial port detected.\n" \
            "connect a valid serial device and press\n"
            "the serial (Refresh) button.", "",
            wx.OK|wx.ICON_STOP)
         result = dlg.ShowModal()
         dlg.Destroy()

      self.UpdateUI()

   def SerialClose(self):
      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_EXIT, None))
         self.mw2tQueue.join()
      self.serialPortThread = None
      self.serPort.close()

      self.stateData.serialPortIsOpen = False
      self.stateData.grblDetected = False
      self.AutoRefreshTimerStop()
      self.UpdateUI()

   def SerialWrite(self, serialData):
      if self.stateData.serialPortIsOpen:
         if self.stateData.swState == gSTATE_RUN:
            # if we are in run state let thread do teh writing
            if self.serialPortThread is not None:
               self.mw2tQueue.put(threadEvent(gEV_CMD_SEND, serialData))
               self.mw2tQueue.join()
         else:
            txtOutputData = "> %s" %(serialData)
            wx.LogMessage("")
            self.outputText.AppendText(txtOutputData)
            self.serPort.write(serialData)

      elif self.cmdLineOptions.verbose:
         print "gcsMainWindow ERROR: attempt serial write with port closed!!"

   def Stop(self):
      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_STOP, None))
         self.mw2tQueue.join()

         self.stateData.swState = gSTATE_IDLE
         self.UpdateUI()

   def SetPC(self, pc=None):
      if pc is None:
         pc = self.gcText.GetCurrentLine()

      self.stateData.programCounter = pc
      self.gcText.UpdatePC(pc)

   def MachineStatusAutoRefresh(self, autoRefresh):
      self.stateData.machineStatusAutoRefresh = autoRefresh

      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_AUTO_STATUS, self.stateData.machineStatusAutoRefresh))
         self.mw2tQueue.join()

      if autoRefresh:
         self.GetMachineStatus()

   def GetMachineStatus(self):
      if self.stateData.serialPortIsOpen:
         self.SerialWrite(gGRBL_CMD_GET_STATUS)

   def LoadLayoutData(self, key, update=True):
      dimesnionsData = layoutData = self.configFile.Read(key+"/Dimensions")
      if len(dimesnionsData) > 0:
         dimesnionsData = dimesnionsData.split("|")

         winPposition = eval(dimesnionsData[0])
         winSize = eval(dimesnionsData[1])
         winIsMaximized = eval(dimesnionsData[2])
         winIsIconized = eval(dimesnionsData[3])

         if winIsMaximized:
            self.Maximize(True)
         elif winIsIconized:
            self.Iconize(True)
         else:
            self.Maximize(False)
            self.Iconize(False)
            self.SetPosition(winPposition)
            self.SetSize(winSize)

      layoutData = self.configFile.Read(key+"/Perspective")
      if len(layoutData) > 0:
         self.aui_mgr.LoadPerspective(layoutData, update)

   def SaveLayoutData(self, key):
      layoutData = self.aui_mgr.SavePerspective()

      winPposition = self.GetPosition()
      winSize = self.GetSize()
      winIsIconized = self.IsIconized()
      winIsMaximized = self.IsMaximized()

      dimensionsData = "|".join([
         str(winPposition),
         str(winSize),
         str(winIsMaximized),
         str(winIsIconized)
      ])

      self.configFile.Write(key+"/Dimensions", dimensionsData)
      self.configFile.Write(key+"/Perspective", layoutData)

   def ConvertInchAndmm(self, lines, in_to_mm=True, round_to=-1):
      ret_lienes=[]

      # itarate input lines
      for line in lines:

         # check for G20/G21 anc hange accordingly
         if in_to_mm:
            re_matches = re.findall(r"G20", line)
            if len(re_matches) > 0:
               line = line.replace("G20", "G21")
               #line = line.replace("INCHES", "MILLIMETERS")
         else:
            re_matches = re.findall(r"G21", line)
            if len(re_matches) > 0:
               line = line.replace("G21", "G20")
               #line = line.replace("MILLIMETERS", "INCHES")

         # check for G with units to convert code
         re_matches = re.findall(r"((X|Y|Z|R|F)([-+]?\d*\.\d*))", line)
         #re_matches = re.findall(r"((Z|R|F)([-+]?\d*\.\d*))", line)
         #import pdb;pdb.set_trace()
         if len(re_matches) > 0:
            # convert here
            # re_match item: string to (replace, literal, value)
            for match in re_matches:
               current_val = float(match[2])
               if in_to_mm:
                  convert_val = 25.4 * current_val
               else:
                  convert_val = current_val / 25.4

               if round_to > -1:
                  convert_val = round(convert_val, round_to)

               current_str = match[0]
               convert_str = match[1] + str(convert_val)

               line = line.replace(current_str, convert_str)

         ret_lienes.append(line)

      return ret_lienes

   def ConvertG812G01(self, lines):
      ret_lienes=[]
      state = 0
      R = 0
      Z = 0
      F = 0

      for line in lines:

         # check for empty lines
         if len(line.strip()) == 0:
            if state != 0:
               state = 0

         # check for G code
         match = re.match(r"G81\s*R(\d*\.\d*)\s*Z([-+]?\d*\.\d*)\sF(\d*\.\d*)", line)
         if match is not None:
            state = 81
            R = match.group(1)
            Z = match.group(2)
            F = match.group(3)

         # in 81 state, convert G81 XY lines to G01
         if state == 81:
            match = re.match(r".*X([-+]?\d*\.\d*)\sY([-+]?\d*\.\d*)", line)
            if match is not None:
               X = match.group(1)
               Y = match.group(2)

               line = \
                  "G00 X%s Y%s ( rapid move to drill zone. )\n" \
                  "G01 Z%s F%s ( plunge. )\n" \
                  "G00 Z%s ( retract )\n" % (X,Y,Z,F,R)

         ret_lienes.append(line)

      return ret_lienes

   """-------------------------------------------------------------------------
   gcsMainWindow: Serial Port Thread Event Handlers
   Handle events coming from serial port thread
   -------------------------------------------------------------------------"""
   def OnThreadEvent(self, e):
      while (not self.t2mwQueue.empty()):
         # get dat from queue
         te = self.t2mwQueue.get()

         if te.event_id == gEV_ABORT:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_ABORT."
            self.outputText.AppendText(te.data)
            self.serialPortThread = None
            self.SerialClose()

         elif te.event_id == gEV_DATA_IN:
            teData = te.data

            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_DATA_IN."
            self.outputText.AppendText("%s" % teData)


            # -----------------------------------------------------------------
            # lest try to see if we have any other good data
            # -----------------------------------------------------------------

            # Grbl version, also useful to detect grbl connect
            rematch = gReGrblVersion.match(teData)
            if rematch is not None:
               if self.stateData.swState == gSTATE_RUN:
                  # something went really bad we shouldn't see this while-in
                  # RUN state
                  self.Stop()
                  dlg = wx.MessageDialog(self,
                     "Detected Grbl reset string while-in RUN.\n" \
                     "Something went terribly wrong, STOPPING!!\n", "",
                     wx.OK|wx.ICON_STOP)
                  result = dlg.ShowModal()
                  dlg.Destroy()
               else:
                  self.stateData.grblDetected = True
                  if self.stateData.machineStatusAutoRefresh:
                     self.GetMachineStatus()
               self.UpdateUI()

            # Grbl status data
            rematch = gReMachineStatus.match(teData)
            if rematch is not None:
               statusData = rematch.groups()
               if self.cmdLineOptions.vverbose:
                  print "gcsMainWindow re.status.match %s" % str(statusData)
               self.stateData.machineStatusString = statusData[0]
               self.machineStatusPanel.UpdateUI(self.stateData, statusData)
               self.machineJoggingPanel.UpdateUI(self.stateData, statusData)
               self.UpdateUI()

         elif te.event_id == gEV_DATA_OUT:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_DATA_OUT."
            self.outputText.AppendText("> %s" % te.data)

         elif te.event_id == gEV_PC_UPDATE:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_PC_UPDATE [%s]." % str(te.data)
            self.SetPC(te.data)

         elif te.event_id == gEV_RUN_END:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_RUN_END."
            self.stateData.swState = gSTATE_IDLE
            self.Refresh()
            self.UpdateUI()
            self.SetPC(0)

         elif te.event_id == gEV_STEP_END:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_STEP_END."
            self.stateData.swState = gSTATE_IDLE
            self.UpdateUI()

         elif te.event_id == gEV_HIT_BRK_PT:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_HIT_BRK_PT."
            self.stateData.swState = gSTATE_BREAK
            self.UpdateUI()

         # item acknowledgment
         self.t2mwQueue.task_done()

"""----------------------------------------------------------------------------
   get_cli_params:
   Get and process command line parameters.
----------------------------------------------------------------------------"""
def get_cli_params():
   ''' define, retrieve and error check command line interface (cli) params
   '''

   usage = \
      "usage: %prog [options]"

   parser = OptionParser(usage=usage)
   #parser.add_option("-f", "--file", dest="filename",
   #   help="write report to FILE", metavar="FILE")

   parser.add_option("-v", "--verbose",
      dest="verbose", action="store_true", default=False,
      help="print extra information while processing input file.")

   parser.add_option("--vv", "--vverbose",
      dest="vverbose", action="store_true", default=False,
      help="print extra extra information while processing input file.")

   (options, args) = parser.parse_args()

   # check arguments sanity
   if options.vverbose:
      options.verbose = True

   if not wx.VERSION >= (2,7,0,0):
      options.error()
      error(1)

   return (options, args)

"""----------------------------------------------------------------------------
   gcsSserialPortThread:
   Threads that monitor serial port for new data and sends events to
   main window.
----------------------------------------------------------------------------"""
class gcsSserialPortThread(threading.Thread):
   """Worker Thread Class."""
   def __init__(self, notify_window, serial, in_queue, out_queue, cmd_line_options):
      """Init Worker Thread Class."""
      threading.Thread.__init__(self)

      # init local variables
      self.notifyWindow = notify_window
      self.serPort = serial
      self.mw2tQueue = in_queue
      self.t2mwQueue = out_queue
      self.cmdLineOptions = cmd_line_options

      self.gcodeDataLines = []
      self.breakPointSet = set()
      self.initialProgramCounter = 0
      self.workingCounterWorking = 0

      self.reGcodeComments = gReGcodeComments

      self.swState = gSTATE_IDLE

      self.machineAutoStatus = False

      # start thread
      self.start()

   """-------------------------------------------------------------------------
   gcsSserialPortThread: Main Window Event Handlers
   Handle events coming from main UI
   -------------------------------------------------------------------------"""
   def ProcessQueue(self):
      # process events from queue ---------------------------------------------
      if not self.mw2tQueue.empty():
         # get item from queue
         e = self.mw2tQueue.get()

         if e.event_id == gEV_CMD_EXIT:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread got event gEV_CMD_EXIT."
            self.endThread = True
            self.swState = gSTATE_IDLE

         elif e.event_id == gEV_CMD_RUN:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread got event gEV_CMD_RUN, swState->gSTATE_RUN"
            self.gcodeDataLines = e.data[0]
            self.initialProgramCounter = e.data[1]
            self.workingProgramCounter = self.initialProgramCounter
            self.breakPointSet =  e.data[2]
            self.swState = gSTATE_RUN

         elif e.event_id == gEV_CMD_STEP:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread got event gEV_CMD_STEP, swState->gSTATE_STEP"
            self.gcodeDataLines = e.data[0]
            self.initialProgramCounter = e.data[1]
            self.workingProgramCounter = self.initialProgramCounter
            self.breakPointSet =  e.data[2]
            self.swState = gSTATE_STEP

         elif e.event_id == gEV_CMD_STOP:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread got event gEV_CMD_STOP, swState->gSTATE_IDLE"

            self.swState = gSTATE_IDLE

         elif e.event_id == gEV_CMD_SEND:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread got event gEV_CMD_SEND."
            self.SerialWrite(e.data)
            responseData = self.WaitForResponse()

         elif e.event_id == gEV_CMD_AUTO_STATUS:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread got event gEV_CMD_AUTO_STATUS."
            self.machineAutoStatus = e.data

         else:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread got unknown event!! [%s]." % str(e.event_id)

         # item qcknowledge
         self.mw2tQueue.task_done()

   """-------------------------------------------------------------------------
   gcsSserialPortThread: General Functions
   -------------------------------------------------------------------------"""
   def SerialWrite(self, serialData):
      # sent data to UI
      self.t2mwQueue.put(threadEvent(gEV_DATA_OUT, serialData))
      wx.PostEvent(self.notifyWindow, threadQueueEvent(None))

      # send command
      self.serPort.write(serialData)

      if self.cmdLineOptions.verbose:
         print serialData.strip()

   def SerialRead(self):
      serialData = self.serPort.readline()

      if len(serialData) > 0:
         # add data to queue and signal main window to consume
         self.t2mwQueue.put(threadEvent(gEV_DATA_IN, serialData))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))

      if self.cmdLineOptions.verbose:
         if (len(serialData) > 0) or (self.swState != gSTATE_IDLE and \
            self.swState != gSTATE_BREAK):
            print "->%s<-" % serialData.strip()

      return serialData

   def WaitForResponse(self):
      waitForResponse = True

      while (waitForResponse):
         response = self.SerialRead()

         if len(response.lower().strip()) > 0:
            waitForResponse = False

         self.ProcessQueue()

         if self.endThread:
            waitForResponse = False
            return

      if self.machineAutoStatus:
         #self.t2mwQueue.put(threadEvent(gEV_DATA_OUT, gGRBL_CMD_GET_STATUS))
         #wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         #self.serPort.write(gGRBL_CMD_GET_STATUS)
         #self.ProcessIdleSate()
         pass

   def RunStepSendGcode(self, gcodeData):
      gcode = gcodeData.strip()

      if len(gcode) > 0:
         gcode = "%s\n" % (gcode)

         # write data
         self.SerialWrite(gcode)


         # wait for response
         responseData = self.WaitForResponse()

      else:
         # remove hack to slow things down for debugiing
         #response = self.serPort.readline()
         pass

      self.workingProgramCounter += 1

      # if we stop early make sure to update PC to main UI
      if self.swState == gSTATE_IDLE:
         self.t2mwQueue.put(threadEvent(gEV_PC_UPDATE, self.workingProgramCounter))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))


   def ProcessRunSate(self):
      # send data to serial port ----------------------------------------------

      # check if we are done with gcode
      if self.workingProgramCounter >= len(self.gcodeDataLines):
         self.swState = gSTATE_IDLE
         self.t2mwQueue.put(threadEvent(gEV_RUN_END, None))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         if self.cmdLineOptions.vverbose:
            print "** gcsSserialPortThread reach last PC, swState->gSTATE_IDLE"
         return

      # update PC
      self.t2mwQueue.put(threadEvent(gEV_PC_UPDATE, self.workingProgramCounter))
      wx.PostEvent(self.notifyWindow, threadQueueEvent(None))

      # check for break point hit
      if (self.workingProgramCounter in self.breakPointSet) and \
         (self.workingProgramCounter != self.initialProgramCounter):
         self.swState = gSTATE_BREAK
         self.t2mwQueue.put(threadEvent(gEV_HIT_BRK_PT, None))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         if self.cmdLineOptions.vverbose:
            print "** gcsSserialPortThread encounter breakpoint PC[%s], swState->gSTATE_BREAK" % \
               (self.workingProgramCounter)
         return

      gcode = self.gcodeDataLines[self.workingProgramCounter]

      # don't sent unecessary data save the bits for speed
      for reComments in self.reGcodeComments:
         gcode = reComments.sub("", gcode)

      self.RunStepSendGcode(gcode)

      if self.machineAutoStatus:
         self.SerialWrite(gGRBL_CMD_GET_STATUS)
         responseData = self.WaitForResponse()


   def ProcessStepSate(self):
      # send data to serial port ----------------------------------------------

      # check if we are done with gcode
      if self.workingProgramCounter >= len(self.gcodeDataLines):
         self.swState = gSTATE_IDLE
         self.t2mwQueue.put(threadEvent(gEV_STEP_END, None))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         if self.cmdLineOptions.vverbose:
            print "** gcsSserialPortThread reach last PC, swState->gSTATE_IDLE"
         return

      # update PC
      self.t2mwQueue.put(threadEvent(gEV_PC_UPDATE, self.workingProgramCounter))
      wx.PostEvent(self.notifyWindow, threadQueueEvent(None))

      # end IDLE state
      if self.workingProgramCounter > self.initialProgramCounter:
         self.swState = gSTATE_IDLE
         self.t2mwQueue.put(threadEvent(gEV_STEP_END, None))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         if self.cmdLineOptions.vverbose:
            print "** gcsSserialPortThread finish STEP cmd, swState->gSTATE_IDLE"
         return

      gcode = self.gcodeDataLines[self.workingProgramCounter]

      # don't sent unecessary data save the bits for speed
      for reComments in self.reGcodeComments:
         gcode = reComments.sub("", gcode)

      self.RunStepSendGcode(gcode)

   def ProcessIdleSate(self):
      if self.machineAutoStatus:
         #self.SerialWrite(gGRBL_CMD_GET_STATUS)
         #responseData = self.WaitForResponse()
         self.SerialRead()
      else:
         self.SerialRead()

   def run(self):
      """Run Worker Thread."""
      # This is the code executing in the new thread.
      self.endThread = False

      if self.cmdLineOptions.vverbose:
         print "** gcsSserialPortThread start."

      while(self.endThread != True):

         # process input queue for new commands or actions
         self.ProcessQueue()

         # check if we need to exit now
         if self.endThread:
            break

         if self.serPort.isOpen():
            if self.swState == gSTATE_RUN:
               self.ProcessRunSate()
            elif self.swState == gSTATE_STEP:
               self.ProcessStepSate()
            elif self.swState == gSTATE_IDLE:
               self.ProcessIdleSate()
            elif self.swState == gSTATE_BREAK:
               self.ProcessIdleSate()
            else:
               print "** gcsSserialPortThread unexpected state [%d], moving back to IDLE." \
                  ", swState->gSTATE_IDLE " % (self.swState)
               self.ProcessIdleSate()
               self.swState = gSTATE_IDLE
         else:
            if self.cmdLineOptions.vverbose:
               print "** gcsSserialPortThread unexpected serial port closed, ABORT."

            # add data to queue and signal main window to consume
            self.t2mwQueue.put(threadEvent(gEV_ABORT, "** Serial Port is close, thread terminating.\n"))
            wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
            break

      if self.cmdLineOptions.vverbose:
         print "** gcsSserialPortThread exit."

"""----------------------------------------------------------------------------
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
   Computer Vision Section:
   Code related to the operation and interaction with OpenCV.
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
----------------------------------------------------------------------------"""
"""----------------------------------------------------------------------------
   gcsCV2SettingsPanel:
   CV2 settings.
----------------------------------------------------------------------------"""
class gcsCV2SettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)
      flexGridSizer = wx.FlexGridSizer(2,2)

      # Add check box
      self.cb = wx.CheckBox(self, wx.ID_ANY, "Enable CV2") #, style=wx.ALIGN_RIGHT)
      self.cb.SetValue(self.configData.Get('/cv2/Enable'))
      flexGridSizer.Add(self.cb,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "")
      flexGridSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)


      # Add spin ctrl for capture device
      self.scDevice = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scDevice.SetRange(-1,100)
      self.scDevice.SetValue(self.configData.Get('/cv2/CaptureDevice'))
      flexGridSizer.Add(self.scDevice,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "CV2 Capture Device")
      flexGridSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

      # Add spin ctrl for capture period
      self.scPeriod = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scPeriod.SetRange(1,1000000)
      self.scPeriod.SetValue(self.configData.Get('/cv2/CapturePeriod'))
      self.scPeriod.SetToolTip(
         wx.ToolTip("NOTE: UI may become unresponsive if this value is too short\n"\
                    "Suggested value 100ms or grater"
      ))
      flexGridSizer.Add(self.scPeriod,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "CV2 Capture Period (milliseconds)")
      flexGridSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)


      # Add spin ctrl for capture width
      self.scWidth = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scWidth.SetRange(1,10000)
      self.scWidth.SetValue(self.configData.Get('/cv2/CaptureWidth'))
      flexGridSizer.Add(self.scWidth,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "CV2 Capture Width")
      flexGridSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

      # Add spin ctrl for capture height
      self.scHeight = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scHeight.SetRange(1,10000)
      self.scHeight.SetValue(self.configData.Get('/cv2/CaptureHeight'))
      flexGridSizer.Add(self.scHeight,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "CV2 Capture Height")
      flexGridSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

      vBoxSizer.Add(flexGridSizer, 0, flag=wx.ALL|wx.EXPAND, border=20)
      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/cv2/Enable', self.cb.GetValue())
      self.configData.Set('/cv2/CaptureDevice', self.scDevice.GetValue())
      self.configData.Set('/cv2/CapturePeriod', self.scPeriod.GetValue())
      self.configData.Set('/cv2/CaptureWidth', self.scWidth.GetValue())
      self.configData.Set('/cv2/CaptureHeight', self.scHeight.GetValue())

"""----------------------------------------------------------------------------
   gcsCV2Panel:
   Status information about machine, controls to enable auto and manual
   refresh.
----------------------------------------------------------------------------"""
class gcsCV2Panel(wx.ScrolledWindow):
   def __init__(self, parent, config_data, cmd_line_options, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.capture = False
      self.mainWindow = parent
      self.stateData = gcsStateData()
      self.configData = config_data
      self.captureTimer = None
      self.cmdLineOptions = cmd_line_options
      self.settingsChanged = True
      self.scrollUnit = 10

      # thread communication queues
      self.cvw2tQueue = Queue.Queue()
      self.t2cvwQueue = Queue.Queue()

      self.visionThread = None
      self.captureTimer = wx.Timer(self, gID_CV2_CAPTURE_TIMER)
      self.bmp = None

      self.InitConfig()
      self.InitUI()

      # register for events
      self.Bind(wx.EVT_TIMER, self.OnCaptureTimer, id=gID_CV2_CAPTURE_TIMER)
      self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
      self.Bind(wx.EVT_SHOW, self.OnShow)

      # register for thread events
      EVT_THREAD_QUEUE_EVENT(self, self.OnThreadEvent)

   def InitConfig(self):
      self.cv2Enable = self.configData.Get('/cv2/Enable')
      self.cv2CaptureDevice = self.configData.Get('/cv2/CaptureDevice')
      self.cv2CapturePeriod = self.configData.Get('/cv2/CapturePeriod')
      self.cv2CaptureWidth = self.configData.Get('/cv2/CaptureWidth')
      self.cv2CaptureHeight = self.configData.Get('/cv2/CaptureHeight')

   def InitUI(self):
      vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # capture panel
      scSizer = wx.BoxSizer(wx.VERTICAL)
      self.scrollPanel = scrolled.ScrolledPanel(self, -1)
      self.capturePanel = wx.BitmapButton(self.scrollPanel, -1, style = wx.NO_BORDER)
      scSizer.Add(self.capturePanel)
      self.scrollPanel.SetSizer(scSizer)
      self.scrollPanel.SetAutoLayout(True)

      #self.capturePanel.Bind(wx.EVT_MOTION, self.OnCapturePanelMouse)
      #self.capturePanel.Enable(False)

      vPanelBoxSizer.Add(self.scrollPanel, 1, wx.EXPAND)

      # buttons
      line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
      vPanelBoxSizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.TOP, border=5)

      btnsizer = wx.StdDialogButtonSizer()

      self.centerScrollButton = wx.Button(self, label="Center")
      self.centerScrollButton.SetToolTip(wx.ToolTip("Center scroll bars"))
      self.Bind(wx.EVT_BUTTON, self.OnCenterScroll, self.centerScrollButton)
      btnsizer.Add(self.centerScrollButton)

      self.captureButton = wx.ToggleButton(self, label="Capture")
      self.captureButton.SetToolTip(wx.ToolTip("Toggle video capture on/off"))
      self.Bind(wx.EVT_TOGGLEBUTTON, self.OnCapture, self.captureButton)
      self.Bind(wx.EVT_UPDATE_UI, self.OnCaptureUpdate, self.captureButton)
      btnsizer.Add(self.captureButton)

      btnsizer.Realize()

      vPanelBoxSizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5)

      # Finish up init UI
      self.SetSizer(vPanelBoxSizer)
      self.SetAutoLayout(True)
      width,height = self.GetSize()
      self.SetScrollbars(self.scrollUnit, self.scrollUnit,
         width/self.scrollUnit, height/self.scrollUnit)

   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.settingsChanged = True

      self.InitConfig()

      if self.capture and self.IsShown():
         self.StopCapture()
         self.StartCapture()

   def UpdateUI(self, stateData, statusData=None):
      self.stateData = stateData

   def UpdateCapturePanel(self):

      if self.settingsChanged:
         self.settingsChanged = False

         self.scrollPanel.GetSizer().Layout()

         width,height = self.capturePanel.GetSize()

         self.scrollPanel.SetScrollbars(self.scrollUnit, self.scrollUnit,
            width/self.scrollUnit, height/self.scrollUnit)

         self.scrollPanel.GetSizer().Layout()

         self.CenterScroll()
         self.Refresh()


   def OnCapture(self, w):
      if self.capture:
         self.StopCapture()
      else:
         self.StartCapture()

   def OnCaptureUpdate(self, e):
      e.Enable(self.cv2Enable)

      if self.capture:
         self.captureButton.SetValue(True)
      else:
         self.captureButton.SetValue(False)

   def OnCaptureTimer(self, e):
      self.ProcessThreadQueue()

   def OnCenterScroll(self, e):
      self.CenterScroll()

   def OnDestroy(self, e):
      self.StopCapture()
      e.Skip()

   def OnShow(self, e):
      if self.capture and not e.GetShow():
         self.StopCapture()
      e.Skip()

   def OnThreadEvent(self, e):
      self.ProcessThreadQueue()

   def CenterScroll(self):
      x,y = self.capturePanel.GetClientSize()
      sx, sy = self.scrollPanel.GetSize()
      sux, suy = self.scrollPanel.GetScrollPixelsPerUnit()

      self.scrollPanel.Scroll((x-sx)/2/sux, (y-sy)/2/suy)

   def ProcessThreadQueue(self):
      goitem = False

      while (not self.t2cvwQueue.empty()):
         te = self.t2cvwQueue.get()
         goitem = True

         if te.event_id == gEV_CMD_CV_IMAGE:
            if self.cmdLineOptions.vverbose:
               print "** gcsCV2Panel got event gEV_CMD_CV_IMAGE."
            image = te.data

            if image is not None:
               self.bmp = wx.BitmapFromBuffer(image.width, image.height, image.tostring())
               self.capturePanel.SetBitmapLabel(self.bmp)
               #self.capturePanel.SetBitmapDisabled(self.bmp)

               if self.settingsChanged:
                  wx.CallAfter(self.UpdateCapturePanel)


      # acknoledge thread
      if goitem:
         self.t2cvwQueue.task_done()

   def StartCapture(self):
      self.capture = True

      if self.visionThread is None and self.cv2Enable:
         self.visionThread = gcsComputerVisionThread(self, self.cvw2tQueue, self.t2cvwQueue,
            self.configData, self.cmdLineOptions)

      if self.captureTimer is not None and self.cv2Enable:
         self.captureTimer.Start(self.cv2CapturePeriod)

   def StopCapture(self):
      self.capture = False

      if self.captureTimer is not None:
         self.captureTimer.Stop()

      if self.visionThread is not None:
         self.cvw2tQueue.put(threadEvent(gEV_CMD_CV_EXIT, None))

         goitem = False
         while (not self.t2cvwQueue.empty()):
            te = self.t2cvwQueue.get()
            goitem = True

         # make sure to unlock thread
         if goitem:
            self.t2cvwQueue.task_done()

         #self.cvw2tQueue.join()
         self.visionThread = None

"""----------------------------------------------------------------------------
   gcsComputerVisionThread:
   Threads that capture and processes vide frames.
----------------------------------------------------------------------------"""
class gcsComputerVisionThread(threading.Thread):
   """Worker Thread Class."""
   def __init__(self, notify_window, in_queue, out_queue, config_data, cmd_line_options):
      """Init Worker Thread Class."""
      threading.Thread.__init__(self)

      # init local variables
      self.notifyWindow = notify_window
      self.cvw2tQueue = in_queue
      self.t2cvwQueue = out_queue
      self.cmdLineOptions = cmd_line_options
      self.configData = config_data

      if self.cmdLineOptions.vverbose:
         print "gcsComputerVisionThread ALIVE."

      self.InitConfig()

      # start thread
      self.start()

   def InitConfig(self):
      self.cv2Enable = self.configData.Get('/cv2/Enable')
      self.cv2CaptureDevice = self.configData.Get('/cv2/CaptureDevice')
      self.cv2CapturePeriod = self.configData.Get('/cv2/CapturePeriod')
      self.cv2CaptureWidth = self.configData.Get('/cv2/CaptureWidth')
      self.cv2CaptureHeight = self.configData.Get('/cv2/CaptureHeight')


   """-------------------------------------------------------------------------
   gcscomputerVisionThread: Main Window Event Handlers
   Handle events coming from main UI
   -------------------------------------------------------------------------"""
   def ProcessQueue(self):
      # process events from queue ---------------------------------------------
      if not self.cvw2tQueue.empty():
         # get item from queue
         e = self.cvw2tQueue.get()

         if e.event_id == gEV_CMD_CV_EXIT:
            if self.cmdLineOptions.vverbose:
               print "** gcscomputerVisionThread got event gEV_CMD_EXIT."
            self.endThread = True

         # item qcknowledge
         self.cvw2tQueue.task_done()

   """-------------------------------------------------------------------------
   gcscomputerVisionThread: General Functions
   -------------------------------------------------------------------------"""
   def CaptureFrame(self):
      frame = self.cv.QueryFrame(self.captureDevice)

      if self.cmdLineOptions.vverbose:
         print "** gcscomputerVisionThread Capture Frame."

      #cv.ShowImage("Window",frame)
      if frame is not None:
         offset=(0,0)
         width = self.cv2CaptureWidth
         height = self.cv2CaptureHeight
         widthHalf = width/2
         heightHalf = height/2

         self.cv.Line(frame, (widthHalf, 0),  (widthHalf,height) , 255)
         self.cv.Line(frame, (0,heightHalf), (width,heightHalf) , 255)
         self.cv.Circle(frame, (widthHalf,heightHalf), 66, 255)
         self.cv.Circle(frame, (widthHalf,heightHalf), 22, 255)

         offset=(0,0)

         self.cv.CvtColor(frame, frame, self.cv.CV_BGR2RGB)

         # important cannot call any wx. UI fucntions from this thread
         # bad things will happen
         #sizePanel = self.capturePanel.GetClientSize()
         #image = self.cv.CreateImage(sizePanel, frame.depth, frame.nChannels)

         #self.cv.Resize(frame, image, self.cv.CV_INTER_NN)
         #self.cv.Resize(frame, image, self.cv.CV_INTER_LINEAR)
         image = frame

         return frame


   def run(self):
      """
      Worker Thread.
      This is the code executing in the new thread context.
      """
      import cv2.cv as cv
      self.cv=cv

      #set up camera
      self.captureDevice = self.cv.CaptureFromCAM(self.cv2CaptureDevice)

      # let camera hardware settle
      time.sleep(1)

      # init sensor frame size
      self.cv.SetCaptureProperty(self.captureDevice,
         self.cv.CV_CAP_PROP_FRAME_WIDTH, self.cv2CaptureWidth)

      self.cv.SetCaptureProperty(self.captureDevice,
         self.cv.CV_CAP_PROP_FRAME_HEIGHT, self.cv2CaptureHeight)

      # init before work loop
      self.endThread = False

      if self.cmdLineOptions.vverbose:
         print "** gcscomputerVisionThread start."

      while(self.endThread != True):

         # capture frame
         frame = self.CaptureFrame()

         # sned frame to window, and wait...
         #wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         self.t2cvwQueue.put(threadEvent(gEV_CMD_CV_IMAGE, frame))
         self.t2cvwQueue.join()

         # sleep for a period
         time.sleep(self.cv2CapturePeriod/1000)

         # process input queue for new commands or actions
         self.ProcessQueue()

         # check if we need to exit now
         if self.endThread:
            break

      if self.cmdLineOptions.vverbose:
         print "** gcscomputerVisionThread exit."


"""----------------------------------------------------------------------------
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
   start here: (ENTRY POINT FOR SCRIPT, MAIN, Main)
   Python script start up code.
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
----------------------------------------------------------------------------"""

if __name__ == '__main__':

   (cmd_line_options, cli_args) = get_cli_params()

   app = wx.App(0)
   gcsMainWindow(None, title=__appname__, cmd_line_options=cmd_line_options)
   app.MainLoop()
