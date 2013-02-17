#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gcs.py:
----------------------------------------------------------------------------"""

__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
"GCODE Step and Alignment Tool (gcs) is a cross-platform GCODE debug/step for "\
"grbl like GCODE interpreters. With features similar to software debuggers. Features "\
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
__version_info__    = (0, 8, 0)
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
import wx
from optparse import OptionParser
from wx.lib.mixins import listctrl as listmix
from wx.lib.agw import aui as aui
from wx.lib.agw import floatspin as FS
from wx.lib.wordwrap import wordwrap
from wx import stc as stc
from wx.lib.embeddedimage import PyEmbeddedImage
from wx.lib import scrolledpanel as scrolled


#from wx.lib.agw import flatmenu as FM
#from wx.lib.agw import ultimatelistctrl as ULC
#from wx.lib.agw.artmanager import ArtManager, RendererBase, DCSaver
#from wx.lib.agw.fmresources import ControlFocus, ControlPressed
#from wx.lib.agw.fmresources import FM_OPT_SHOW_CUSTOMIZE, FM_OPT_SHOW_TOOLBAR, FM_OPT_MINIBAR


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
         '/mainApp/MaxFileHistory'           :(True , 8),
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

      # CV2 keys
         '/cv2/Enable'                       :(True , False),
         '/cv2/CaptureDevice'                :(True , 0),
         '/cv2/CapturePeriod'                :(True , 100),
         '/cv2/CaptureWidth'                 :(True , 640),
         '/cv2/CaptureHeight'                :(True , 480),
         '/cv2/X-Offset'                     :(True , 0),
         '/cv2/Y-Offset'                     :(True , 0),
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
   Embedded Images
   These images generated by /usr/bin/img2py

   some icons by http://somerandomdude.com/work/iconic/
   some icons by Yusuke Kamiyamane. All rights reserved.
   Images license : This work is licensed under Creative Commons'
   Attribution-ShareAlike 3.0 United States (CC BY-SA 3.0)
   http://creativecommons.org/licenses/by-sa/3.0/us/
----------------------------------------------------------------------------"""
#------------------------------------------------------------------------------
# imgPlay
#------------------------------------------------------------------------------
imgPlayBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByQcz8ytbwAAAD1JREFUOMtjYBhs4DwD"
    "A4MBJQb8h+IGSg34T65r/mPBDZQaQJJr/hPAGK5honY00sQLDQMSjQ0DlpTpDtgBljgwXOs4"
    "7F8AAAAASUVORK5CYII=")

imgPlayGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDAltTu1DwAAAGhJREFUOMtjYBhUYNWa"
    "9edXrVlvQIoeJjS+AQMDw/lVa9Y3EGsAI5oL/iNxLzAwMCSGhQReIMUFJLsGnwsYiHENE5Fe"
    "xekaJkpjjoVIdTi9QIwBjWEhgQ3kuICoaGQhx1Z8BhBl6+ACAO6qKKDvuKECAAAAAElFTkSu"
    "QmCC")

#------------------------------------------------------------------------------
# imgStep
#------------------------------------------------------------------------------
imgStepBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByQo7nhZ2gAAAFVJREFUOMtjYBhM4DwD"
    "A4MBqZoYkdj/oXQjAwNDAw71DTjYcANgGJdrkNXglYThBkoNQHcNWQYguwbDACZqRiNNvEB2"
    "IBIdjSxYFOFLSI1UT8oDDtgBGphE0gAEAQAAAAAASUVORK5CYII=")

imgStepGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDAxr+FhcgAAAH5JREFUOMvNkssJgDAQ"
    "RJ/BgrSUgHi3kph2JJBSTEd6UcnBdf2BDiyEZDMz+4HfYAhxHEKsrv4rMoJpOfq2sb0gst2v"
    "OWYnzx24cVkgEQBUwJgrSjDKu9N6U57o0+rG33HA0xIAElBLk9FKEEeqESSgaxubNHvlRVX/"
    "+ip/jxlYXDC1MBW5zgAAAABJRU5ErkJggg==")

#------------------------------------------------------------------------------
# imgStop
#------------------------------------------------------------------------------
imgStopBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByQzZB2QNgAAACBJREFUOMtjYBhowIjE"
    "/k+OXiZKXTBqwKgBg8OAAQfsALZSAR8mQXhTAAAAAElFTkSuQmCC")

imgStopGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDA7TzSIbAAAACtJREFUOMtjYBhowAhj"
    "rFqz/j8pGsNCAhkZGBgYmCh1wagBowYMDgMGHgAAE+AEGJkQ9b4AAAAASUVORK5CYII=")

#------------------------------------------------------------------------------
# imgBreak
#------------------------------------------------------------------------------
imgBreakBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByUExbsEeAAAAGpJREFUOMvNks0JwCAM"
    "Rp+9dA1H6Mau4GZxA3uJIJL+BNvSwHcR3zOYwB8rAgkQoGpEz+IVvA3gGNE7hy+fwb3E7CTd"
    "gFuSJRCHQBoUOkF1fnYAWGZH1guKgyuWIDsE+ZUxTi/SI6v8ea07bSVKp5t5VZAAAAAASUVO"
    "RK5CYII=")

imgBreakGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDENmZUstAAAAKRJREFUOMvNksENwjAM"
    "RR+dICMwAhmhG6RS1XWibsK5qtRswAgwQkfwCFwcKYQACRf4t/z4v1iO4dc65MaybkfAAw4w"
    "agsQgHkah/0lYFm3E3BJgrkE6KdxuD0B9OXrm3AKsbGTLrnwFWG0xsdDCnANs3MlgGkAmBLg"
    "K3XZcGolJUBoAIQSYK7sQrT2EaD/2n+AxEXai0PUDbPAOQOJejbdwv/QHX1yKEbBwq96AAAA"
    "AElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgMapPin
#------------------------------------------------------------------------------
imgMapPinBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByUbSLMJjQAAAIVJREFUOMu1UsENgCAM"
    "vOjDNRiJDXEEGcMXbsAIvH3ppyRo2tJIvKRJU9rrXQPAwwPIAC6KTDUTfDP4DhNJ3ZxowFNe"
    "lXTBbWtVPTDhBwxbCMoRg8VCVMij1UZhtheuUTriZqyJBHFEPmejSE3aP1iF3AzXKHBfP1Wi"
    "EDF3CE4AO4BDeF9u6hE4W09LwyQAAAAASUVORK5CYII=")

imgMapPinGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDEdhCI80AAAALtJREFUOMulksEJwzAM"
    "RV9CB2g3yAgdpYaQc1foBCEThG7QszE42SAbJCNkg3aEXpRSjFw79IOxkOSvL1kFCqzzF6AH"
    "KnGtwK2pzRDmFpHHHh0mJCmVpF7uBTByliD2wUEh2GR3WzXrPKKqCpNL/oSmYJVKrVQGaL9i"
    "SYIJuAJnZZhTTgvjD8Vj8htlaE/gGLhfTW1OuUMcMn1RgjG3tSLWbNCGKj+1B4+InU1wj9j5"
    "sM7P1vl57yayp/IbNw0yBMDu12oAAAAASUVORK5CYII=")

#------------------------------------------------------------------------------
# imgGoToMapPin
#------------------------------------------------------------------------------
imgGotoMapPinBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByUthwmcFAAAAH9JREFUOMtjYBhKQICB"
    "gWE/AwPDfyjeDxUjGsA0n4dimCEoYD5UEpvJMM0wADMEDhKQnIfNEJwGOCDh83gMuY/FC/cZ"
    "kDRgw8g29mOR7yfFAAMs8gakeAHZG3DnkxKI6N7oxxbX+KKRgYGBQQHJAAVyU+R+5ATEQoYB"
    "CwdXDgMA7JJL1nAmIzsAAAAASUVORK5CYII=")

imgGotoMapPinGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDErS5ipSQAAANFJREFUOMvNkM0NwjAM"
    "hT+iDsAIjFA2CCNEinJmBDZBTAC9RpHSDdoNyAZ0BEbgYpBV8dNyAUuW/Pves+HXtpg6GFNe"
    "AhmwUuoBV80guy8XyS2QqxHLEaiBTfDuOgKwQAnerWX2DFijlrfAVgA6kfz5BzFlq/K9ACBS"
    "H0piyhdgpU6ogaECuhfgtfTWkrfAThEAtGbGE5tnNQNslBfVLFIDIHhXgEH1h+BdMcG7PnjX"
    "y31P79eSx7FRDCfg9GYZ4PAinm4x5S6m/Hh89QVGw1/ZDZmwQ5xuOfBFAAAAAElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgLink
#------------------------------------------------------------------------------
imgLinkBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByQPS3LssQAAAIZJREFUOMvVk7ENwCAM"
    "BK9LywiMwAiMks0YgREyAiMwAiOQxkiWlci0uKHA9/xbBk6rADRg7jRHoErzBB4FNw9OwJDm"
    "rsAFh124GNvu69HAALcC3fzVwGtwt5zdE1iZA5BN1iL31RPQVrOBh8T8ra9pazjtLskS6Lsw"
    "Zkm0UPVs2/zhqM91vQGtQLINi2ipAAAAAElFTkSuQmCC")

imgLinkGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDAXfezkjwAAANRJREFUOMvNksENgzAQ"
    "BIeIAiiBEkgH0AGWLL+TEighFVACvBES6YB0gEughJSQzzmyTkCUV3IfW/bu3u7Z8OtKvgEP"
    "45QBM1A4axKA9ACcAy1Qy9EDyIAC8AGX7pAL6ZQBK/AESrn2QBWwpw/kHjhrjLPmuSkgtt9k"
    "Z81VIgTbXvbsRWgVGeAerYt2owVqydwM41QCXuz2wzh1QB4Jbs9ABjaH55JoHXCRu+bIQZzR"
    "A16RK2fNuikgn0TXIrYD2R/NYFafJDjpgZvuvCUQyFX8zv9fL21vSWog3NHrAAAAAElFTkSu"
    "QmCC")

#------------------------------------------------------------------------------
# imgProgram
#------------------------------------------------------------------------------
imgProgramBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByQBrMrBtgAAAQ5JREFUOMulkztLA0EU"
    "Rs9MVsRC1zS+CKaxEASbgJDKPyuKjSgoEcVHgkJEZqMIgkUMiJpAAq67pFiQvVbqsroPyQdT"
    "DJw5zJ2PgZ9IymoB02RERpV8gWniVEkeQarkW7B/6diA2WuYstaFmwRJ6g1M88mdAaRgWZWE"
    "NwFAJ82jtRoDuGj3PaBVM+0ioOKc9dfh3fpVda1kBztnzWX/bdABVoLhuw24cVbFRgBQTs8v"
    "iYgbhigRscJQQhH5qJaLwyiX1YIAbB81FoDB1mF9KaOt3wKn59tAcP3iTQImt+D8/nExAt2Z"
    "rjcX2We30H99ngA4vn1Y3aydrlfmp7obByezef/CvzgrAcgdzWgZ/wSAzJS7vHbo9AAAAABJ"
    "RU5ErkJggg==")

imgProgramGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFCDAHYFv06wAAASFJREFUOMtjZICCVWvW"
    "/2cgAMJCAhnRxZgYSADYLGFEl0S3BZsmZDUkuQCboSzYFGw5eo7/2/OHH9jF5BR+vnqE1zCs"
    "Lvj2/OEHOTNH8Z+vHj0g5BqcXmBiYmRlYGBgkDV1UGNgYGDgVdQTxBYLWL3AJirF/uDEvp8s"
    "wpIan9+/uc/AwMDw8+tHfgYGhg9EGSCnriX2X02T998/Bsb////z8gk5Cvz///8P0V4wkuB9"
    "cvfo3s+m0nyf71+7yPno1P4PD65fkiQpDBgYGBjOvfjMz/jp7VNFS2c+5i/vbhNtwIFr9+Sg"
    "LvkICVAGbpJi4fWzJ5wMDAwMuy/e1PvDzS989+je5784+cSxqcUaiKEudjeRkzkaG78BxORK"
    "snMjNgAAn3VnJ3rOqJsAAAAASUVORK5CYII=")

#------------------------------------------------------------------------------
# imgMachine
#------------------------------------------------------------------------------
imgMachineBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAI5JREFUeNqsU4kJwCAMDE6UEdpN3FBHcAPdRDdoLSQQ0gi2"
    "GjgUcjnyAozNd1wEDxOGipiFQFbCaAVXIj9vEMGMoDg4SncWr7Lqh+DKQU4IJCUYO05CVL6k"
    "089Gvdp0XzKXYaWIhsBhcR1ssOUSRoRAaePAB1vGuLxI3MTS0ejfjLnzXkhO2XpMv8/5FmAA"
    "pdh8malagfIAAAAASUVORK5CYII=")

imgMachineGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAPhJREFUeNqkU8ENwjAMbCIGKJuEDdoNUgnxphN0BMQInaC8"
    "EVK7AWxANiEjYEt25VoGBFg6pU7P8Tl2XPHCzpdxD8tAbrvbNieL50VAoCC2zvpGDnLZdxwM"
    "yxVQAjLgBogq2QSoBKcGVYkVBPpR0BoNtVFxwqyAVDwE4ZNlyL5e3AHJ1pJrwqT+zVxHF9ex"
    "JA6GDI3qyqhKS4DeU6uCynA0ZPfKx5jBF38aHtCSHGkHg9spH2Na96bGiWRnOjBad7QSm5XR"
    "9/hCebUYZepE+UXpJY+9F/VkHhKj71yS5CQ9idiWwK8O/Ltob4L9jVCL/vKAX5/zU4ABAGYG"
    "WP8eAwg4AAAAAElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgTarget
#------------------------------------------------------------------------------
imgTargetBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAJxJREFUeNrEU8ENgCAMZARGcQRGYARHYCNGcoSOwAhYk5ac"
    "SE0UEy+5T3u9pi04d4ZnJubGrBCvEkuiGWJhkojrwEBJor0UFxBlZoR8lJjmC5p46HwkgrMR"
    "oBHpOAmctXgVgaJITE1Uf9S2hWUotnagJhkW25IRulkGBDvpNT+iH4GejjC9ROuMBQzo7ozT"
    "D2n6KX/ymV5/512AAQBxnm3Jdo79HgAAAABJRU5ErkJggg==")

#------------------------------------------------------------------------------
# imgX
#------------------------------------------------------------------------------
imgXBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAHlJREFUeNpiYMAECUC8H4j/o+H9UDmcQAGIz2PRiI7PQ9Vi"
    "aH5PhGYYfo9uyHkSNCO7BO5ndNMbsGhowOJKcJjsx6IQ3WBY4DVgCViszktAMiQBh0thGKcf"
    "E9CiFqs6JgYqAIq9QHEgUhyNFCckqiRlijMT2dkZIMAAQSOoo+oDrMMAAAAASUVORK5CYII=")

#------------------------------------------------------------------------------
# imgLog
#------------------------------------------------------------------------------
imgLogBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByMsplQLBAAAAC9JREFUOMtjYKAQMDIw"
    "MLyHsgWh9H9SDGBiGPKAEYsYSWEyTMOApDAZTQeDIAzYAXvGCBBY8UOKAAAAAElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgCli
#------------------------------------------------------------------------------
imgCliBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIDBQkxjNYgRwAAAOFJREFUOMvF07tKQ0EQ"
    "xvHfCUfBJiI2XjhlAkJSSKyt7HwE38AXsLROnyaQt0ib1kKwFKJ1CoOteA0YmwksB3OBFPma"
    "2Z3d+TOX3QxTa6hiTW0eIHpwhRpO0MT+CnE3mOaxecUYXzjAzwqA57SEJrZxj8tYL9NuuQdb"
    "uMU5huiitQDwgZc8cYzRxx2OA/CAbA6g+G8KF+hggEecLcigjsO85Gyjh2v8YgfVmFQ1fHth"
    "P6EMaEVq73F2FCV8R8AEbzGpUQooEsgo7ARPyVtJlc3uVUpB85ShgdOkqcXsYLO/8Q9y9Sm2"
    "hRFPhQAAAABJRU5ErkJggg==")

#------------------------------------------------------------------------------
# imgMove
#------------------------------------------------------------------------------
imgMoveBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAE9JREFUeNpiYMAP5kMxWQCk8T8Uz6dEM9mGMCBpJhuQZMB8"
    "EgyYj8vPpLhsPr4A+4/HNSgBy8RAJUCRF6gSiIMjHVA9Kc+nNB8QlZ0BAgwA0Tszh6S715cA"
    "AAAASUVORK5CYII=")

#------------------------------------------------------------------------------
# imgEye
#------------------------------------------------------------------------------
imgEyeBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QIFByMaae6enQAAAI9JREFUOMvNksEJgDAM"
    "RR9evHYER+gIjuAIukmdwBEczRHaDfQSoYRIBEX8kMtPfpomH/6IAKxABnaJLFzwxIMS6shS"
    "Y2JUhQnoJZJqPHriaDwQr5pENWYSPjncLtOxWaTxfyRXc1sDlAcXKw0wqSbnBHPFzSqHaCZv"
    "iQHovCW+csZXjFRbeTGsvNyx8udoD31xVkhwngFgAAAAAElFTkSuQmCC")


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
      #self.FitInside()

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
      #line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
      text = wx.StaticText(self, label="General:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      #vBoxSizer.Add(line, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, border=5)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      gBoxSizer = wx.GridSizer(1,3)

      self.checkReadOnly = wx.CheckBox (self, label="ReadOnly")
      self.checkReadOnly.SetValue(self.configData.Get('/%s/ReadOnly' % self.key))
      gBoxSizer.Add(self.checkReadOnly, 0, wx.ALIGN_CENTER)

      self.checkLineNumbers = wx.CheckBox (self, label="Line Numbers")
      self.checkLineNumbers.SetValue(self.configData.Get('/%s/LineNumber' % self.key))
      gBoxSizer.Add(self.checkLineNumbers, 0, wx.ALIGN_CENTER)

      self.checkCaretLine = wx.CheckBox (self, label="Highlite Caret Line")
      self.checkCaretLine.SetValue(self.configData.Get('/%s/CaretLine' % self.key))
      gBoxSizer.Add(self.checkCaretLine, 0, wx.ALIGN_CENTER)

      vBoxSizer.Add(gBoxSizer, 0, wx.ALL|wx.EXPAND, border=5)

      # Colors
      text = wx.StaticText(self, label="Colors:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)


      vColorSizer = wx.BoxSizer(wx.VERTICAL)
      foregroundColorSizer = wx.GridSizer(2,3)
      backgroundColorSizer = wx.GridSizer(2,3)

      # Foreground
      text = wx.StaticText(self, label="Foreground:")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

      text = wx.StaticText(self, label="Window:")
      foregroundColorSizer.Add(text, 0, flag=wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Line Numbers:")
      foregroundColorSizer.Add(text, 0, flag=wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Highlite Line")
      foregroundColorSizer.Add(text, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.windowForeground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/WindowForeground' % self.key))
      foregroundColorSizer.Add(self.windowForeground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.lineNumbersForeground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/LineNumberForeground' % self.key))
      foregroundColorSizer.Add(self.lineNumbersForeground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.caretLineForeground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/CaretLineForeground' % self.key))
      foregroundColorSizer.Add(self.caretLineForeground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      vColorSizer.Add(foregroundColorSizer, 0, flag=wx.ALL, border=10)

      # Background
      text = wx.StaticText(self, label="Background:")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

      text = wx.StaticText(self, label="Window:")
      backgroundColorSizer.Add(text, 0, flag=wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Line Numbers:")
      backgroundColorSizer.Add(text, 0, flag=wx.LEFT|wx.RIGHT, border=20)
      text = wx.StaticText(self, label="Highlite Line")
      backgroundColorSizer.Add(text, 0, flag=wx.LEFT|wx.RIGHT, border=20)


      self.windowBackground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/WindowBackground' % self.key))
      backgroundColorSizer.Add(self.windowBackground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.lineNumbersBackground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/LineNumberBackground' % self.key))
      backgroundColorSizer.Add(self.lineNumbersBackground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      self.caretLineBackground = wx.ColourPickerCtrl(self,
         col=self.configData.Get('/%s/CaretLineBackground' % self.key))
      backgroundColorSizer.Add(self.caretLineBackground, 0, flag=wx.LEFT|wx.RIGHT, border=20)

      vColorSizer.Add(backgroundColorSizer, 0, flag=wx.ALL, border=10)

      vBoxSizer.Add(vColorSizer, 0, wx.ALL|wx.ALIGN_LEFT, border=10)

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

      # Add cehck box
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
      self.imageList.Add(imgProgramBlack.GetBitmap())
      self.imageList.Add(imgLinkBlack.GetBitmap())
      self.imageList.Add(imgLogBlack.GetBitmap())
      self.imageList.Add(imgCliBlack.GetBitmap())
      self.imageList.Add(imgMachineBlack.GetBitmap())
      self.imageList.Add(imgMoveBlack.GetBitmap())
      self.imageList.Add(imgEyeBlack.GetBitmap())

      if os.name == 'nt':
         self.noteBook = wx.Notebook(self, size=(640,400))
      else:
         self.noteBook = wx.Notebook(self, size=(640,400), style=wx.BK_LEFT)

      self.noteBook.AssignImageList(self.imageList)

      # add pages
      self.AddLinkPage(0)
      self.AddProgramPage(1)
      self.AddOutputPage(2)
      self.AddCliPage(3)
      self.AddMachinePage(4)
      self.AddJoggingPage(5)
      self.AddCV2Panel(6)

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

   def AddProgramPage(self, page):
      self.programPage = gcsStyledTextCtrlSettingsPanel(
         self.noteBook, self.configData, "code")
      self.noteBook.AddPage(self.programPage, "Program")
      self.noteBook.SetPageImage(page, 0)

   def AddLinkPage(self, page):
      self.linkPage = gcsLinkSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.linkPage, "Link")
      self.noteBook.SetPageImage(page, 1)

   def AddOutputPage(self, page):
      self.outputPage = gcsStyledTextCtrlSettingsPanel(
         self.noteBook, self.configData, "output")
      self.noteBook.AddPage(self.outputPage, "Output")
      self.noteBook.SetPageImage(page, 2)

   def AddCliPage(self, page):
      self.cliPage = gcsCliSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.cliPage, "Cli")
      self.noteBook.SetPageImage(page, 3)

   def AddMachinePage(self, page):
      self.machinePage = gcsMachineSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.machinePage, "Machine")
      self.noteBook.SetPageImage(page, 4)

   def AddJoggingPage(self, page):
      win = wx.Panel(self.noteBook, -1)
      self.noteBook.AddPage(win, "Jogging")
      st = wx.StaticText(win, -1, "Jogging panel stuff goes here")
      self.noteBook.SetPageImage(page, 5)

   def AddCV2Panel(self, page):
      self.CV2Page = gcsCV2SettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.CV2Page, " OpenCV2")
      self.noteBook.SetPageImage(page, 6)

   def UpdatConfigData(self):
      self.programPage.UpdatConfigData()
      self.outputPage.UpdatConfigData()
      self.linkPage.UpdatConfigData()
      self.cliPage.UpdatConfigData()
      self.machinePage.UpdatConfigData()
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
      stc.StyledTextCtrl.AppendText(self, string)

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
   gcsMachineJoggingPanel:
   Status information about machine, controls to enable auto and manual
   refresh.
----------------------------------------------------------------------------"""
class gcsMachineJoggingPanel(wx.ScrolledWindow):
   def __init__(self, parent, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent

      self.stateData = gcsStateData()

      self.useMachineWorkPosition = False

      self.memoX = gZeroString
      self.memoY = gZeroString
      self.memoZ = gZeroString

      self.InitUI()
      width,height = self.GetSizeTuple()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

   def InitUI(self):
      vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)
      hPanelBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      # Add Controls ----------------------------------------------------------
      buttonBox = self.CreateJoggingButtons()
      vPanelBoxSizer.Add(buttonBox, 0, flag=wx.ALL|wx.EXPAND, border=5)

      positionStatus = self.CreatePositionStatus()
      hPanelBoxSizer.Add(positionStatus, 0, flag=wx.EXPAND)

      positionGotoButtons = self.CreateGotoButtons()
      hPanelBoxSizer.Add(positionGotoButtons, 0, flag=wx.LEFT|wx.EXPAND, border=10)


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


   def CreateStaticBox(self, label):
      # Static box ------------------------------------------------------------
      staticBox = wx.StaticBox(self, -1, label)
      staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.HORIZONTAL)

      return staticBoxSizer

   def CreatePositionStatus(self):
      vBoxLeftSizer = wx.BoxSizer(wx.VERTICAL)

      # add status controls
      spinText = wx.StaticText(self, -1, "Step Size:  ")
      vBoxLeftSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      self.spinCtrl = FS.FloatSpin(self, -1,
         min_val=0, max_val=99999, increment=0.10, value=1.0,
         agwStyle=FS.FS_LEFT)
      self.spinCtrl.SetFormat("%f")
      self.spinCtrl.SetDigits(4)

      vBoxLeftSizer.Add(self.spinCtrl, 0,
         flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, border=5)

      #positionBoxSizer = self.CreateStaticBox(label)
      spinText = wx.StaticText(self, -1, "Jogging Status:  ")
      vBoxLeftSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL)

      flexGridSizer = wx.FlexGridSizer(4,2)
      vBoxLeftSizer.Add(flexGridSizer,0 , flag=wx.ALL|wx.EXPAND, border=5)

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
      vBoxLeftSizer.Add(self.useWorkPosCheckBox)

      return vBoxLeftSizer

   def CreateGotoButtons(self):
      vBoxRightSizer = wx.BoxSizer(wx.VERTICAL)

      spinText = wx.StaticText(self, -1, "")
      vBoxRightSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      # add Buttons
      self.resettoZeroPositionButton = wx.Button(self, label="Reset to Zero")
      self.resettoZeroPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToZeroPos, self.resettoZeroPositionButton)
      vBoxRightSizer.Add(self.resettoZeroPositionButton, flag=wx.TOP|wx.EXPAND, border=5)

      self.goZeroButton = wx.Button(self, label="Goto Zero")
      self.goZeroButton.SetToolTip(
         wx.ToolTip("Move to Machine Working position X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnGoZero, self.goZeroButton)
      vBoxRightSizer.Add(self.goZeroButton, flag=wx.EXPAND)

      self.resettoCurrentPositionButton = wx.Button(self, label="Reset to Jog")
      self.resettoCurrentPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToCurrentPos, self.resettoCurrentPositionButton)
      vBoxRightSizer.Add(self.resettoCurrentPositionButton, flag=wx.EXPAND)

      self.goToCurrentPositionButton = wx.Button(self, label="Goto Jog")
      self.goToCurrentPositionButton.SetToolTip(
         wx.ToolTip("Move to to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnGoPos, self.goToCurrentPositionButton)
      vBoxRightSizer.Add(self.goToCurrentPositionButton, flag=wx.EXPAND)

      self.goHomeButton = wx.Button(self, label="Goto Home")
      self.goHomeButton.SetToolTip(
         wx.ToolTip("Execute Machine Homing Cycle"))
      self.Bind(wx.EVT_BUTTON, self.OnGoHome, self.goHomeButton)
      vBoxRightSizer.Add(self.goHomeButton, flag=wx.EXPAND)

      self.saveJogButton = wx.Button(self, label="Save Jog")
      self.saveJogButton.SetToolTip(
         wx.ToolTip("Saves current jogging values to memory"))
      self.Bind(wx.EVT_BUTTON, self.OnSaveJog, self.saveJogButton)
      vBoxRightSizer.Add(self.saveJogButton, flag=wx.EXPAND)

      self.loadJogButton = wx.Button(self, label="Load Jog")
      self.loadJogButton.SetToolTip(
         wx.ToolTip("Loads jogging from memory"))
      self.Bind(wx.EVT_BUTTON, self.OnLoadJog, self.loadJogButton)
      vBoxRightSizer.Add(self.loadJogButton, flag=wx.EXPAND)


      return vBoxRightSizer

   def CreateJoggingButtons(self):
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

   def OnLoadJog(self, e):
      self.jX.SetValue(self.memoX)
      self.jY.SetValue(self.memoY)
      self.jZ.SetValue(self.memoZ)

   def OnSaveJog(self, e):
         self.stackData = True
         self.memoX = self.jX.GetValue()
         self.memoY = self.jY.GetValue()
         self.memoZ = self.jZ.GetValue()

   def OnUseMachineWorkPosition(self, e):
      self.useMachineWorkPosition = e.IsChecked()

   def OnRefresh(self, e):
      pass

   def UpdateSettings(self, config_data):
      self.configData = config_data
      #self.InitConfig()


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

   def InitUI(self):
      """ Init main UI """

      # init aui manager
      self.aui_mgr = aui.AuiManager()

      # notify AUI which frame to use
      self.aui_mgr.SetManagedWindow(self)

      #self.connectionPanel = gcsConnectionPanel(self)
      self.machineStatusPanel = gcsMachineStatusPanel(self)
      self.CV2Panel = gcsCV2Panel(self, self.configData, self.cmdLineOptions)
      self.machineJoggingPanel = gcsMachineJoggingPanel(self)

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
         aui.AuiPaneInfo().Name("GCODE_PANEL").CenterPane().Caption("GCODE"))

      self.aui_mgr.AddPane(self.CV2Panel,
         aui.AuiPaneInfo().Name("CV2_PANEL").Right().Position(0).Caption("Computer Vision")\
            .BestSize(640,530).Hide()
      )

      self.aui_mgr.AddPane(self.machineJoggingPanel,
         aui.AuiPaneInfo().Name("MACHINE_JOGGING_PANEL").Right().Position(1).Caption("Machine Jogging")\
            .BestSize(320,340)
      )

      self.aui_mgr.AddPane(self.machineStatusPanel,
         aui.AuiPaneInfo().Name("MACHINE_STATUS_PANEL").Right().Position(2).Caption("Machine Status")\
            .BestSize(320,180)
      )

      self.aui_mgr.AddPane(self.cliPanel,
         aui.AuiPaneInfo().Name("CLI_PANEL").Bottom().Row(2).Caption("Command").BestSize(600,30)
      )

      self.aui_mgr.AddPane(self.outputText,
         aui.AuiPaneInfo().Name("OUTPUT_PANEL").Bottom().Row(1).Caption("Output").BestSize(600,150)
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

   def CreateMenu(self):

      # Create the menubar
      #self.menuBar = FM.FlatMenuBar(self, wx.ID_ANY, 32, 5, options = FM_OPT_SHOW_TOOLBAR | FM_OPT_SHOW_CUSTOMIZE)
      #self.menuBar = FM.FlatMenuBar(self, wx.ID_ANY, options=FM_OPT_SHOW_TOOLBAR)
      self.menuBar = wx.MenuBar()

      #------------------------------------------------------------------------
      # File menu
      fileMenu = wx.Menu()
      self.menuBar.Append(fileMenu,                   "&File")

      fileMenu.Append(wx.ID_OPEN,                     "&Open")

      recentMenu = wx.Menu()
      fileMenu.AppendMenu(wx.ID_ANY,                  "&Recent Files",
         recentMenu)

      # load history
      maxFileHistory = self.configData.Get('/mainApp/MaxFileHistory')
      self.fileHistory = wx.FileHistory(maxFileHistory)
      self.fileHistory.Load(self.configFile)
      self.fileHistory.UseMenu(recentMenu)
      self.fileHistory.AddFilesToMenu()

      fileMenu.Append(wx.ID_EXIT,                     "E&xit")

      #------------------------------------------------------------------------
      # Edit menu
      #viewEdit = wx.Menu()
      #self.menuBar.Append(viewEdit,                   "&Edit")

      #viewEdit.Append(wx.ID_PREFERENCES,              "&Settings")

      #------------------------------------------------------------------------
      # View menu
      viewMenu = wx.Menu()
      self.menuBar.Append(viewMenu,                   "&View")

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
      viewMenu.Append(wx.ID_PREFERENCES,                       "&Settings")

      #------------------------------------------------------------------------
      # Run menu
      runMenu = wx.Menu()
      self.menuBar.Append(runMenu, "&Run")

      runItem = wx.MenuItem(runMenu, gID_MENU_RUN,    "&Run\tF5")
      runItem.SetBitmap(imgPlayBlack.GetBitmap())
      runMenu.AppendItem(runItem)

      stepItem = wx.MenuItem(runMenu, gID_MENU_STEP,  "S&tep")
      stepItem.SetBitmap(imgStepBlack.GetBitmap())
      runMenu.AppendItem(stepItem)

      stopItem = wx.MenuItem(runMenu, gID_MENU_STOP,  "&Stop")
      stopItem.SetBitmap(imgStopBlack.GetBitmap())
      runMenu.AppendItem(stopItem)

      runMenu.AppendSeparator()
      breakItem = wx.MenuItem(runMenu, gID_MENU_BREAK_TOGGLE,
                                                      "Brea&kpoint Toggle\tF9")
      breakItem.SetBitmap(imgBreakBlack.GetBitmap())
      runMenu.AppendItem(breakItem)

      runMenu.Append(gID_MENU_BREAK_REMOVE_ALL,       "Breakpoint &Remove All")
      runMenu.AppendSeparator()

      setPCItem = wx.MenuItem(runMenu, gID_MENU_SET_PC,"Set &PC")
      setPCItem.SetBitmap(imgMapPinBlack.GetBitmap())
      runMenu.AppendItem(setPCItem)

      gotoPCItem = wx.MenuItem(runMenu, gID_MENU_GOTO_PC,
                                                      "&Goto PC")
      gotoPCItem.SetBitmap(imgGotoMapPinBlack.GetBitmap())
      runMenu.AppendItem(gotoPCItem)

      #------------------------------------------------------------------------
      # Help menu
      helpMenu = wx.Menu()
      self.menuBar.Append(helpMenu,                   "&Help")

      helpMenu.Append(wx.ID_ABOUT,                    "&About",
         "About GCS")

      #------------------------------------------------------------------------
      # Bind events to handlers

      #------------------------------------------------------------------------
      # File menu bind
      self.Bind(wx.EVT_MENU,        self.OnFileOpen,     id=wx.ID_OPEN)
      self.Bind(wx.EVT_MENU_RANGE,  self.OnFileHistory,  id=wx.ID_FILE1, id2=wx.ID_FILE9)
      self.Bind(wx.EVT_MENU,        self.OnClose,        id=wx.ID_EXIT)
      self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN,
                           self.OnDropDownToolBarOpen,   id=gID_TOOLBAR_OPEN)

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

      self.Bind(wx.EVT_BUTTON, self.OnRun,               id=gID_MENU_RUN)
      self.Bind(wx.EVT_BUTTON, self.OnStep,              id=gID_MENU_STEP)
      self.Bind(wx.EVT_BUTTON, self.OnStop,              id=gID_MENU_STOP)
      self.Bind(wx.EVT_BUTTON, self.OnBreakToggle,       id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_BUTTON, self.OnSetPC,             id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_BUTTON, self.OnGoToPC,            id=gID_MENU_GOTO_PC)

      self.Bind(wx.EVT_UPDATE_UI, self.OnRunUpdate,      id=gID_MENU_RUN)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStepUpdate,     id=gID_MENU_STEP)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStopUpdate,     id=gID_MENU_STOP)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakToggleUpdate,
                                                         id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakRemoveAllUpdate,
                                                         id=gID_MENU_BREAK_REMOVE_ALL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnSetPCUpdate,    id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_UPDATE_UI, self.OnGoToPCUpdate,   id=gID_MENU_GOTO_PC)

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

      self.appToolBar.AddSimpleTool(gID_TOOLBAR_OPEN, "Open", wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN, size=iconSize))
      self.appToolBar.AddSimpleTool(wx.ID_ABOUT, "About", wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, size=iconSize))
      self.appToolBar.SetToolDropDown(gID_TOOLBAR_OPEN, True)
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

      self.gcodeToolBar.AddSimpleTool(gID_MENU_RUN, "Run", imgPlayBlack.GetBitmap(),
         "Run\tF5")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_RUN, imgPlayGray.GetBitmap())
      #self.gcodeToolBar.AddTool(gID_MENU_RUN, "Run", imgPlayBlack.GetBitmap(),
      #   imgPlayGray.GetBitmap(), aui.ITEM_NORMAL, "Run\tF5", "", None)

      self.gcodeToolBar.AddSimpleTool(gID_MENU_STEP, "Step", imgStepBlack.GetBitmap(),
         "Step")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_STEP, imgStepGray.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_STOP, "Stop", imgStopBlack.GetBitmap(),
         "Stop")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_STOP, imgStopGray.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_BREAK_TOGGLE, "Break Toggle",
         imgBreakBlack.GetBitmap(), "Breakpoint Toggle\tF9")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_BREAK_TOGGLE, imgBreakGray.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_SET_PC, "Set PC", imgMapPinBlack.GetBitmap(),
         "Set PC")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_SET_PC, imgMapPinGray.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_GOTO_PC, "Goto PC", imgGotoMapPinBlack.GetBitmap(),
         "Goto PC")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_GOTO_PC, imgGotoMapPinGray.GetBitmap())

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

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_LINK_STATUS, "123456789", imgLinkGray.GetBitmap(),
         "Link Status")
      self.statusToolBar.SetToolDisabledBitmap(gID_MENU_RUN, imgLinkGray.GetBitmap())

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_PROGRAM_STATUS, "123456", imgProgramBlack.GetBitmap(),
         "Program Status")
      self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_PROGRAM_STATUS, imgProgramBlack.GetBitmap())

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_MACHINE_STATUS, "123456", imgMachineBlack.GetBitmap(),
         "Machine Status")
      self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_MACHINE_STATUS, imgMachineGray.GetBitmap())

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

         # re open serial port if open
         if self.stateData.serialPortIsOpen and \
            (self.stateData.serialPort != self.configData.Get('/link/Port') or \
            self.stateData.serialBaud != self.configData.Get('/link/Baud')):

            self.SerialClose()
            self.SerialOpen(self.configData.Get('/link/Port'), self.configData.Get('/link/Baud'))

         if self.stateData.machineStatusAutoRefresh != self.configData.Get('/machine/AutoRefresh') or \
            self.stateData.machineStatusAutoRefreshPeriod != self.configData.Get('/machine/AutoRefreshPeriod'):

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
      print "got here"
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
      if self.stateData.fileIsOpen and \
         self.stateData.serialPortIsOpen and \
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
      if self.stateData.fileIsOpen and \
         self.stateData.serialPortIsOpen and \
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
      if self.stateData.fileIsOpen and \
         self.stateData.serialPortIsOpen and \
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
      if self.stateData.fileIsOpen and \
         (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_BREAK_TOGGLE, state)

   def OnBreakRemoveAll(self, e):
      self.breakPoints = set()
      self.gcText.UpdateBreakPoint(-1, False)

   def OnBreakRemoveAllUpdate(self, e):
      if self.stateData.fileIsOpen and \
         (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         e.Enable(True)
      else:
         e.Enable(False)

   def OnSetPC(self, e):
      self.SetPC()

   def OnSetPCUpdate(self, e=None):
      state = False
      if self.stateData.fileIsOpen and \
         (self.stateData.swState == gSTATE_IDLE or \
          self.stateData.swState == gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_SET_PC, state)

   def OnGoToPC(self, e):
      self.gcText.GoToPC()

   def OnGoToPCUpdate(self, e=None):
      state = False
      if self.stateData.fileIsOpen:
         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_GOTO_PC, state)

   #---------------------------------------------------------------------------
   # Status Menu/ToolBar Handlers
   #---------------------------------------------------------------------------
   def OnStatusToolBarForceUpdate(self):
      # Link status
      if self.stateData.serialPortIsOpen:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Linked")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkBlack.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkBlack.GetBitmap())
      else:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Unlinked")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkGray.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkGray.GetBitmap())

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
      #aboutDialog.Description = __description__
      aboutDialog.Description = wordwrap(__description__, 400, wx.ClientDC(self))
      aboutDialog.WebSite = ("https://github.com/duembeg/gcs", "GCode Step home page")
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
      self.stateData.machineStatusAutoRefresh = self.configData.Get('/machine/AutoRefresh')
      self.stateData.machineStatusAutoRefreshPeriod = self.configData.Get('/machine/AutoRefreshPeriod')

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
                     "Detected GRBL reset string while-in RUN.\n" \
                     "Something went terribly wrong, S TOPING!!\n", "",
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

      # Add cehck box
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
                    "Sugested value 100ms or grater"
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


      # Add spin ctrl for offset x
      self.scXoffset = FS.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=FS.FS_LEFT)
      self.scXoffset.SetFormat("%f")
      self.scXoffset.SetDigits(4)
      self.scXoffset.SetValue(self.configData.Get('/cv2/X-Offset'))
      flexGridSizer.Add(self.scXoffset,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "CAM X Offset")
      flexGridSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

      # Add spin ctrl for offset y
      self.scYoffset = FS.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=FS.FS_LEFT)
      self.scYoffset.SetFormat("%f")
      self.scYoffset.SetDigits(4)
      self.scYoffset.SetValue(self.configData.Get('/cv2/Y-Offset'))
      flexGridSizer.Add(self.scYoffset,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "CAM Y Offset")
      flexGridSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

      vBoxSizer.Add(flexGridSizer, 0, flag=wx.ALL|wx.EXPAND, border=20)
      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/cv2/Enable', self.cb.GetValue())
      self.configData.Set('/cv2/CaptureDevice', self.scDevice.GetValue())
      self.configData.Set('/cv2/CapturePeriod', self.scPeriod.GetValue())
      self.configData.Set('/cv2/CaptureWidth', self.scWidth.GetValue())
      self.configData.Set('/cv2/CaptureHeight', self.scHeight.GetValue())
      self.configData.Set('/cv2/X-Offset', self.scXoffset.GetValue())
      self.configData.Set('/cv2/Y-Offset', self.scYoffset.GetValue())

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

      if self.cmdLineOptions.vverbose:
         print "gcsCV2Panel ALIVE."


      # thread communication queues
      self.cvw2tQueue = Queue.Queue()
      self.t2cvwQueue = Queue.Queue()

      self.visionThread = None
      self.captureTimer = wx.Timer(self, gID_CV2_CAPTURE_TIMER)
      self.bmp = None

      self.InitConfig()
      self.InitUI()

      # register for events
      self.Bind(wx.EVT_PAINT, self.OnPaint)
      self.Bind(wx.EVT_IDLE, self.OnIdle)
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

      self.capturePanel = wx.Panel(self.scrollPanel, -1,
         size=wx.Size(self.cv2CaptureWidth, self.cv2CaptureHeight))

      scSizer.Add(self.capturePanel)
      self.scrollPanel.SetSizer(scSizer)
      self.scrollPanel.SetAutoLayout(True)
      width,height = self.capturePanel.GetSize()
      scu = 10
      self.scrollPanel.SetScrollbars(scu, scu, width/scu, height/scu)

      self.scrollPanel.Bind(wx.EVT_SCROLLWIN, self.OnScroll)

      vPanelBoxSizer.Add(self.scrollPanel, 1, wx.EXPAND)

      # buttons
      line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
      vPanelBoxSizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.TOP, border=5)

      btnsizer = wx.StdDialogButtonSizer()

      self.gotoToolButton = wx.Button(self, gID_CV2_GOTO_TOOL, label="Goto Tool")
      self.gotoToolButton.SetToolTip(wx.ToolTip("Move Tool to target"))
      #self.Bind(wx.EVT_BUTTON, self.gotoToolButton, self.OnGotoTool)
      btnsizer.Add(self.gotoToolButton)

      self.gotoCamButton = wx.Button(self, gID_CV2_GOTO_CAM, label="Goto CAM")
      self.gotoCamButton.SetToolTip(wx.ToolTip("Move CAM corss-hair to target"))
      #self.Bind(wx.EVT_BUTTON, self.gotoCamButton, self.onGotoCAM)
      btnsizer.Add(self.gotoCamButton)

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
      scu = 10
      self.SetScrollbars(scu, scu, width/scu, height/scu)


   def UpdateUI(self, stateData, statusData=None):
      self.stateData = stateData

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

   def OnIdle(self, e):
      self.Paint()
      e.Skip()

   def OnPaint(self, e):
      self.Paint()
      e.Skip()

   def OnScroll(self, e):
      if not self.capture:
         wx.CallAfter(self.Paint)
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
               self.Paint()

      # acknoledge thread
      if goitem:
         self.t2cvwQueue.task_done()

   def Paint(self):
      if self.bmp is not None:
         offset=(0,0)
         dc = wx.ClientDC(self.capturePanel)
         dc.DrawBitmap(self.bmp, offset[0], offset[1], False)

   def StartCapture(self):
      self.capture = True

      if self.visionThread is None and self.cv2Enable:
         self.visionThread = gcsComputerVisionThread(self, self.cvw2tQueue, self.t2cvwQueue,
            self.configData, self.cmdLineOptions)

      if self.captureTimer is not None and self.cv2Enable:
         self.captureTimer.Start(self.cv2CapturePeriod)

      wx.CallAfter(self.UpdateScroll)

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

   def UpdateSettings(self, config_data):
      self.configData = config_data

      self.InitConfig()

      if self.capture and self.IsShown():
         self.StopCapture()
         self.StartCapture()

   def UpdateScroll(self):
      #self.capturePanel.SetSize(wx.Size(
      #   self.configData.dataCV2CaptureWidth, self.configData.dataCV2CaptureHeight))
      #scSizer = wx.BoxSizer(wx.VERTICAL)
      #scSizer.Add(self.capturePanel)
      #self.scrollPanel.SetSizer(scSizer)
      #self.scrollPanel.SetAutoLayout(True)
      #print str(self.capturePanel.GetSize())
      #width,height = self.capturePanel.GetSize()
      #scu = 10
      #self.scrollPanel.SetScrollbars(scu, scu, width/scu, height/scu)
      self.CenterScroll()
      self.Refresh()

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
