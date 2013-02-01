#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gcode-step.py: 
----------------------------------------------------------------------------"""

__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
"GCODE Step and Alignment Tool (gstat) is a cross-platform GCODE debug/step for "\
"grbl like GCODE interpreters. With features similar to software debuggers. Features "\
"Such as breakpoint, change current program counter, inspection and modification "\
"of variables."


# define authorship information
__authors__     = ['Wilhelm Duembeg']
__author__      = ','.join(__authors__)
__credits__     = []
__copyright__   = 'Copyright (c) 2013'
__license__     = 'GPL'

# maintenance information
__maintainer__  = 'Wilhelm Duembeg'
__email__       = 'duembeg.github@gmail.com'

# define version information
__requires__        = ['pySerial', 'wxPython']
__version_info__    = (0, 0, 1)
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
import wx
from optparse import OptionParser
from wx.lib.mixins import listctrl as listmix
from wx.lib.agw import aui as aui
from wx.lib.agw import floatspin as FS
from wx.lib.wordwrap import wordwrap
from wx import stc as stc
from wx.lib.embeddedimage import PyEmbeddedImage
from wx.lib.imageutils import grayOut

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


gWILDCARD = "ngc (*.ngc)|*.ngc|" \
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

# -----------------------------------------------------------------------------
# config file keys
# -----------------------------------------------------------------------------
gConfigKeySaveCmdHistory         = "/cli/SaveCmdHistory"
gConfigKeyCmdHistory             = "/cli/CmdHistory"
gConfigKeyCmdMaxHistory          = "/cli/CmdMaxHistory"

gConfigWindowMaxFileHistory      = "/window/MaxFileHistory"
gConfigWindowDefaultLayout       = "/window/DefaultLayout"
gConfigWindowResetLayout         = "/window/ResetLayout"


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
gGRBL_CMD_GET_STATUS = "?\n"
gGRBL_CMD_RESET_TO_ZERO_POS = "G92 X0 Y0 Z0\n"
gGRBL_CMD_RESET_TO_VAL_POS = "G92 X<XVAL> Y<YVAL> Z<ZVAL>\n"
gGRBL_CMD_GO_ZERO = "G0 X0 Y0 Z0\n"
gGRBL_CMD_GO_POS = "G0 X<XVAL> Y<YVAL> Z<ZVAL>\n"
gGRBL_CMD_EXE_HOME_CYCLE = "G28 X0 Y0 Z0\n"
gGRBL_CMD_JOG_X = "G0 X<VAL>\n"
gGRBL_CMD_JOG_Y = "G0 Y<VAL>\n"
gGRBL_CMD_JOG_Z = "G0 Z<VAL>\n"
gGRBL_CMD_SPINDLE_ON = "M3\n"
gGRBL_CMD_SPINDLE_OFF = "M5\n"

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
           
"""----------------------------------------------------------------------------
   Embedded Images
   These images generated by /usr/bin/img2py
   
   Most of these images came form (http://somerandomdude.com/work/iconic/) 
   Images license : This work is licensed under Creative Commons' 
   Attribution-ShareAlike 3.0 United States (CC BY-SA 3.0) 
   http://creativecommons.org/licenses/by-sa/3.0/us/
----------------------------------------------------------------------------"""
#------------------------------------------------------------------------------
# imgPlay
#------------------------------------------------------------------------------
imgPlayBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAkAAAAMCAYAAACwXJejAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAD1JREFUeNpiYGBgOA/EBgwEwH8obiBG0X98pv7HghuIUYRi"
    "KiNUAB9oZGIgEhC0jiyHEwwCvIFJMFoAAgwA9owpXlnrpyAAAAAASUVORK5CYII=")
    
imgPlayGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAkAAAAMCAYAAACwXJejAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAFpJREFUeNpiWLVm/XkgNmDAA5iAGKQApLABlyJGoOR/JP4F"
    "IE4MCwm8gG4SMsBqKrpJDNhMxacIBhqZGIgALHjk4NbhUtQIlGzAZRLWIGDBpRtdEVbdyAAg"
    "wABvdyig5iK8MwAAAABJRU5ErkJggg==")

#------------------------------------------------------------------------------
# imgNext
#------------------------------------------------------------------------------
imgNextBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAEpJREFUeNpiYGBgOA/EBgxEAkYg/g9lNwJxAw51KOL/kTAu"
    "25DVoHBguIFUDei2EaUB2TY4n4mBDEAVJxHtaYLBSlbEkZQ0AAIMAP0iRUaBrrwYAAAAAElF"
    "TkSuQmCC")
    
imgNextGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAG5JREFUeNpiWLVm/XkgNmAgEjACFf+HshvDQgIbsCkCqmnA"
    "pgEELgBxIlDjBTQNcDVMaIaBnHYe2UR0wIRDvB6X31jw+A9mWyMxNjCQ6iRYABiihxwuJ+EM"
    "YhYspmIEKy4NOE0FySFHCklJAyDAANgNMTiyyuGLAAAAAElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgStop
#------------------------------------------------------------------------------
imgStopBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAIAAADZF8uwAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAABBJREFUeNpiYBgFQxUABBgAAbwAAZK5hs4AAAAASUVORK5C"
    "YII=")

imgStopGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAIAAADZF8uwAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAABpJREFUeNpiXLVmPQMhwMRABBhVRG9FAAEGAJNWAh2OVT6Z"
    "AAAAAElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgBreak
#------------------------------------------------------------------------------
imgBreakBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAABHNCSVQICAgIfAhkiAAAAAlw"
    "SFlzAAAOxAAADsQBlSsOGwAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwA"
    "AABnSURBVCiRlZLBCYAwDEWf9eLRETKCR7d0BFfoZu0GekmqBJHkQaCU9xNICw8CnEADLq2m"
    "d4Jjc6Kvps7o/Ce/QzIDB7D7kR8swEqw+5gy6SFMycgW6Am/F6AmAhWSa7Vk6uEMIfA1bljY"
    "QE3Ku/NzAAAAAElFTkSuQmCC")
    
imgBreakGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAABHNCSVQICAgIfAhkiAAAAAlw"
    "SFlzAAAOxAAADsQBlSsOGwAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwA"
    "AACQSURBVCiRldFBDcJAEEbhr6MACUigEuqgTZraIXXCmZBQB0gACUhYCRwYCOkBlnecvH9m"
    "dqeRHE/nLfbosclywYJ5Goc7NCnvcPkQ1xR00zjcmux8/SJ/htrINX7J0tlH7lxLH5Xd31Pi"
    "DxmE52NqKeH5z7UsgblySsEcecHuR+h1uHvANA43tDisgiVrbToeRb4ma1Mqad0AAAAASUVO"
    "RK5CYII=")

#------------------------------------------------------------------------------
# imgMapPin
#------------------------------------------------------------------------------
imgMapPinBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAQCAYAAAArij59AAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAG5JREFUeNpiYICAACC+D8T/ofg+VAwu+R8HBiuC6TwPFQiA"
    "smEmoapGN5WJgQhA0Ir5eBw5nyhfgMB7LJLvkd0xH5fx+AIrAN0373EZDwP9SAr6sSlQQFKg"
    "gCvQzkMxHDCjKfgJxCeB+AJMACDAAMwHRnRv4T3AAAAAAElFTkSuQmCC")
    
imgMapPinGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAQCAYAAAArij59AAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAKFJREFUeNpiZACCVWvWBwCpfiBWYICAB0BcGBYSuIERKrme"
    "ATsIZILqBIELIAEovgAV62dBMrYRZCTUSgaoqQpMDAQAC9RBIFPqoTpBoB7mWJCCA0CcAMQG"
    "WBx7AGTFRjw2bGSEOuo9kBJAk/wAdLQgzJEbsOgGi8EUYLMGLMYI46FZAzYe2QQQWICNjaxg"
    "Ig42AgCtOQ/C6CHJgE8nQIABAPO2MFm6XNGsAAAAAElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgGoToMapPin
#------------------------------------------------------------------------------
imgGoToMapPinBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QEeDxgqvS66/wAAAH9JREFUOMtjYBhKQICB"
    "gWE/AwPDfyjeDxUjGsA0n4dimCEoYD5UEpvJMM0wADMEDhKQnIfNEJwGOCDh83gMuY/FC/cZ"
    "kDRgw8g29mOR7yfFAAMs8gakeAHZG3DnkxKI6N7oxxbX+KKRgYGBQQHJAAVyU+R+5ATEQoYB"
    "CwdXDgMA7JJL1nAmIzsAAAAASUVORK5CYII=")

imgGoToMapPinGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAA"
    "CXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH3QEeDxgX5Ub27gAAANFJREFUOMvNkM0NwjAM"
    "hT+iDsAIjFA2CCNEinJmBDZBTAC9RpHSDdoNyAZ0BEbgYpBV8dNyAUuW/Pves+HXtpg6GFNe"
    "AhmwUuoBV80guy8XyS2QqxHLEaiBTfDuOgKwQAnerWX2DFijlrfAVgA6kfz5BzFlq/K9ACBS"
    "H0piyhdgpU6ogaECuhfgtfTWkrfAThEAtGbGE5tnNQNslBfVLFIDIHhXgEH1h+BdMcG7PnjX"
    "y31P79eSx7FRDCfg9GYZ4PAinm4x5S6m/Hh89QVGw1/ZDZmwQ5xuOfBFAAAAAElFTkSuQmCC")
    
#------------------------------------------------------------------------------
# imgLink
#------------------------------------------------------------------------------
imgLinkBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAIJJREFUeNqMklENwCAMRJGABCQgASk4Q0IlTAISkICErU3a"
    "pTkgocmFj3uFgxLCXUVWZ707M7FITdHj4I5wZk01hwMNjie4QYxl9wSwVHXgkp8AtotWXQc2"
    "WGYxC2Rt6hM2+KMLwFNj/7V7DQ/n01CsYZzgAEPxjYQxMH+8+SOfAAMA5uhAq8s6MmkAAAAA"
    "SUVORK5CYII=")
    
imgLinkGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAMJJREFUeNqMUcENwjAQC1EHYISOEDYgGxQJ8YYROgITdAR4"
    "IyTYIGzQjNARMkJ9yFedIkCcZF3b89lOunJ/1O3+WKMlIDQfhi3aAHT89AJkIQC5qciBSkKY"
    "gAJsOc5A9F/IV2BTux/2u+JNjIWMwYmRApUzn51GGiqy1NP0UV10oWPmHm6SOYu9COD9gt6q"
    "gDcRC2MltSf5yFlvHZaMmrkiRzhO7wX+lLpGxlBytmdI5jaccZKrPauyXVBy5EF/1izAANwx"
    "SG7WniymAAAAAElFTkSuQmCC")

#------------------------------------------------------------------------------
# imgProgram
#------------------------------------------------------------------------------
imgProgramBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAADtJREFUeNpiZGBg+M9AAmAB4kYGWoP/eHADqU46wEB3wIjN"
    "nYQ0/B8UTgKpcYBivPHwH8nJ80FsgAADAED0F9tfAEgbAAAAAElFTkSuQmCC")

imgProgramGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAENJREFUeNpiXLVm/X8GEgALEDcy0BIwEnBSY1hIYAMpTjrA"
    "QHcA8kMDqcFaP/BOAgUtUJ0DkOlArJNAhsYDcQJAgAEA5GUVItPEBAYAAAAASUVORK5CYII=")

#------------------------------------------------------------------------------
# imgMachine
#------------------------------------------------------------------------------
imgMachineBlack = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAJBJREFUeNpiYMAECkD8H4oV0CWZobQBEG8HYk4gDofyQUAA"
    "iBWBeDoQnwTiFzCN55FMxYVBahiYoBoWMhAGC2EaQO7UR5JYAMSMULwASRykRoERah0yYETj"
    "o8gzoUl+QOMLMOAIxvlInpuPJIcuDg/mAiJCqQDZFqKDlQEp4s5DTUF3RgFUzgBXeONNGgAB"
    "BgCNuTduNsD3hAAAAABJRU5ErkJggg==")
    
imgMachineGray = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAALNJREFUeNpiZEADq9asVwBS96FcxbCQwAfI8oxQRQZAaj4Q"
    "LwRifSBOgMovAOKLQBwPxIlAzRdYoBIgxQZQjAwSkNggNYZMUM5CBsIArIYJ6mZ9JIkFQKsZ"
    "QRjqJBjQB6llBBL/kY2BKkQOBBR5JjRrP6ApFkB3F0iDIpLVAkBF85Hk+5GdClILC9YCNEls"
    "oBDo3AkwJ8UTEUrxyH5IBOILIFPQQmYBVOwCVA0DI6lJAyDAABhTNnd80v1mAAAAAElFTkSu"
    "QmCC")

#------------------------------------------------------------------------------
# imgTarget
#------------------------------------------------------------------------------
imgTarget = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAJxJREFUeNrEU8ENgCAMZARGcQRGYARHYCNGcoSOwAhYk5ac"
    "SE0UEy+5T3u9pi04d4ZnJubGrBCvEkuiGWJhkojrwEBJor0UFxBlZoR8lJjmC5p46HwkgrMR"
    "oBHpOAmctXgVgaJITE1Uf9S2hWUotnagJhkW25IRulkGBDvpNT+iH4GejjC9ROuMBQzo7ozT"
    "D2n6KX/ymV5/512AAQBxnm3Jdo79HgAAAABJRU5ErkJggg==")

#------------------------------------------------------------------------------
# imgX
#------------------------------------------------------------------------------
imgX = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9i"
    "ZSBJbWFnZVJlYWR5ccllPAAAAHlJREFUeNpiYMAECUC8H4j/o+H9UDmcQAGIz2PRiI7PQ9Vi"
    "aH5PhGYYfo9uyHkSNCO7BO5ndNMbsGhowOJKcJjsx6IQ3WBY4DVgCViszktAMiQBh0thGKcf"
    "E9CiFqs6JgYqAIq9QHEgUhyNFCckqiRlijMT2dkZIMAAQSOoo+oDrMMAAAAASUVORK5CYII=")

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
   gcsStateData:
   provides various data information
----------------------------------------------------------------------------"""
class gcsAppData():
   def __init__(self):
      self.swState = gSTATE_IDLE
      
      self.serialPortIsOpen = False
      self.grblDetected = False
      self.machineStatusAutoRefresh = False      
      
      self.programCounter = 0
      self.breakPoints = set()

      self.fileIsOpen = False
      self.gcodeFileName = ""
      self.gcodeFileLines = []
      self.gcodeFileNumLines = 0


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
   gcsCliComboBox:
   Control to handle CLI (Command Line Interface)
----------------------------------------------------------------------------"""
class gcsCliComboBox(wx.ComboBox):
   def __init__(self, parent, ID=wx.ID_ANY, value ="", pos=wx.DefaultPosition,
                 size=wx.DefaultSize, choices=[], style=0):
      
      wx.ComboBox.__init__(self, parent, ID, value, pos, size, choices,
         style=wx.CB_DROPDOWN|wx.TE_PROCESS_ENTER)
         
      self.appData = gcsAppData()
      self.cliCommand = ""
      self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter, self)
      
      self.cliSaveCmdHistory = True
      self.cliCmdMaxCmdHistory = 100
      
   def UpdateUI(self, appData):
      self.appData = appData
      if appData.serialPortIsOpen and not appData.swState == gSTATE_RUN:
         self.Enable()
      else:
         self.Disable()
      
   def GetCommand(self):
      return self.cliCommand
      
   def OnEnter(self, e):
      cliCommand = self.GetValue()
      
      if cliCommand != self.cliCommand:
         if self.GetCount() > self.cliCmdMaxCmdHistory:
            self.Delete(0)
            
         self.cliCommand = cliCommand
         self.Append(self.cliCommand)
         
      self.SetValue("")
      e.Skip()
      
   def LoadConfig(self, configFile):
      # read save cmd history
      configData = configFile.Read(gConfigKeySaveCmdHistory)
      
      if len(configData) > 0:
         self.cliSaveCmdHistory = eval(configData)
         
      # read cmd history max count
      configData = configFile.Read(gConfigKeyCmdMaxHistory)
      
      if len(configData) > 0:
         self.cliCmdMaxCmdHistory = eval(configData)
         
      # read cmd hsitory
      configData = configFile.Read(gConfigKeyCmdHistory)
      if len(configData) > 0:
         cliCommandHistory = configData.split(",")
         for cmd in cliCommandHistory:
            cmd = cmd.strip()
            if len(cmd) > 0:
               self.Append(cmd.strip())
               
         self.cliCommand = cliCommandHistory[len(cliCommandHistory) - 1]
            
   def SaveConfig(self, configFile):
      # write dave cmd history
      configFile.Write(gConfigKeySaveCmdHistory, str(self.cliSaveCmdHistory))
      
      # write cmd history max count
      configFile.Write(gConfigKeyCmdMaxHistory, str(self.cliCmdMaxCmdHistory))
      
      # write cmd history
      if self.cliSaveCmdHistory:
         cliCmdHistory = self.GetItems()
         if len(cliCmdHistory) > 0:
            cliCmdHistory =  ",".join(cliCmdHistory)
            configFile.Write(gConfigKeyCmdHistory, cliCmdHistory)
      
"""----------------------------------------------------------------------------
   gcsListCtrl:
   List control to display data status
----------------------------------------------------------------------------"""
class gcsListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
   def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
      
      wx.ListCtrl.__init__(self, parent, ID, pos, size, 
         style=wx.LC_REPORT|
            wx.LC_NO_HEADER|
            wx.LC_SINGLE_SEL|
            wx.LC_HRULES|
            wx.LC_VRULES)
            
      listmix.ListCtrlAutoWidthMixin.__init__(self)
      
      self.appData = gcsAppData()
      
   def AddRow(self, index, strNmae, strData):
      self.InsertStringItem(index, strNmae)
      self.SetStringItem(index, 1, strData)
      #self.SetItemTextColour(index, self.normalTxtColor)
      
   def UpdateData(self, index, strData):
      self.SetStringItem(index, 1, strData)
      #self.SetItemTextColour(index, self.normalTxtColor)

   def RefrehControl(self):
      self.SetColumnWidth(0, wx.LIST_AUTOSIZE)
      self.SetColumnWidth(1, wx.LIST_AUTOSIZE)
      self.SetSize(self.GetSize());
      
   def UpdateUI(self, appData):
      pass
      
            
"""----------------------------------------------------------------------------
   gcsGcodeListCtrl:
   List control to display GCODE and interact with breakpoints
----------------------------------------------------------------------------"""
class gcsGcodeListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
   def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
      
      wx.ListCtrl.__init__(self, parent, ID, pos, size, 
         style=wx.LC_REPORT|
            wx.LC_SINGLE_SEL|
            wx.LC_HRULES|
            wx.LC_VRULES)
            
      listmix.ListCtrlAutoWidthMixin.__init__(self)
      
      self.appData = gcsAppData()
      
      self.InitUI()
        
   def InitUI(self):
      self.InsertColumn(0, 'PC',width=50)
      self.InsertColumn(1, 'GCODE', width=wx.LIST_AUTOSIZE)
      self.InsertColumn(2, 'Sent', width=50)
      self.InsertColumn(3, 'Response', width=wx.LIST_AUTOSIZE)
      
      self.normalBkColor = self.GetItemBackgroundColour(0)
      self.normalBkColor = wx.WHITE
      self.normalTxtColor = wx.BLACK
      self.pcBkColor = wx.GREEN
      self.pcTxtColor = wx.GREEN
      self.brkPointBkColor = wx.RED
      self.brkPointTxtColor = wx.RED
      self.lastPC = 0
      self.autoScroll = True
      
      self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect)
      
   def UpdateUI(self, appData):
      self.appData = appData
      self.UpdatePC(self.appData.programCounter)
      
   def OnSelect(self, e):
      self.autoScroll = False
      
   def AddRow(self, pc, strLine):
      self.InsertStringItem(pc, str(pc))
      self.SetStringItem(pc, 1, strLine)
      self.SetStringItem(pc, 2, " ")
      self.SetStringItem(pc, 3, " ")
      self.SetItemTextColour(pc, self.normalTxtColor)

   def RefrehControl(self):
      self.SetColumnWidth(0, 50)
      self.SetColumnWidth(1, wx.LIST_AUTOSIZE)
      self.SetColumnWidth(2, 50)
      self.SetColumnWidth(3, wx.LIST_AUTOSIZE)
      self.SetSize(self.GetSize());
      
   def UpdatePC(self, pc):
      if self.GetItemCount() > 0:
         self.SetItemBackgroundColour(self.lastPC, self.normalBkColor)
         self.SetItemBackgroundColour(pc, self.pcBkColor)
      
         if self.autoScroll:
            self.EnsureVisible(pc)
            
      self.lastPC = pc
      
   def GoToPC(self, pc):
      if pc < self.GetItemCount():
         self.EnsureVisible(pc)
   
   def UpdateBreakPoint(self, pc, enable):
      if pc < self.GetItemCount():
         if enable:
            self.SetItemTextColour(pc, self.brkPointTxtColor)
         else:
            self.SetItemTextColour(pc, self.normalTxtColor)
            
   def GetAutoScroll(self):
      return self.autoScroll
   
   def SetAutoScroll(self, autoScroll):
      self.autoScroll = autoScroll

      
"""----------------------------------------------------------------------------
   gcsGcodeStcStyledTextCtrl:
   Text control to display GCODE and interact with breakpoints
----------------------------------------------------------------------------"""
class gcsGcodeStcStyledTextCtrl(stc.StyledTextCtrl):
   def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, 
      size=wx.DefaultSize, style=0, name=stc.STCNameStr): 
      
      stc.StyledTextCtrl.__init__(self, parent, id, pos, size, 
         style, name)
         
      self.handlePC = 0
      self.autoScroll = False
         
      self.InitUI()
      
      # bind events
      self.Bind(wx.EVT_LEFT_DOWN, self.OnCaretChange)
      self.Bind(wx.EVT_LEFT_UP, self.OnCaretChange)      
      self.Bind(wx.EVT_KEY_DOWN, self.OnCaretChange)
      self.Bind(wx.EVT_KEY_UP, self.OnCaretChange)
         
   def InitUI(self):
      # margin 1 for line numbers
      self.SetMarginType(0, stc.STC_MARGIN_NUMBER)
      self.SetMarginWidth(0, 50)
      
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
      self.MarkerDefine(self.markerCaretLine, stc.STC_MARK_ROUNDRECT, "BLACK", "#8B9BBA")
      #self.MarkerDefine(self.markerCaretLine, stc.STC_MARK_ROUNDRECT, "BLACK", 
      #   wx.SystemSettings_GetColour(wx.SYS_COLOUR_HIGHLIGHT))
      
      
      self.SetMarginMask(1, pow(2,self.markerBreakpoint))
      self.SetMarginMask(2, pow(2,self.markerPC))
      
      # other settings
      self.SetReadOnly(True)
      #self.SetCaretLineVisible(True)
      #self.EnsureCaretVisible()
      #self.SetCaretLineBack("yellow")
      
      self.SetLexer(stc.STC_LEX_PYTHON)
      self.SetKeyWords(0, "G00 G01 G20 G21 G90 G92 G94 M2 M3 M5 M9 T6 S")

      # more global default styles for all languages
      #self.StyleSetSpec(stc.STC_STYLE_LINENUMBER,
      #   "back:#CCC0C0")
      
      #self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, 'fore:#000000,back:#99A9C2')
      #self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, 'fore:#000000,back:#5D7BCA')
      
      # comment-blocks
      self.StyleSetSpec(stc.STC_P_COMMENTBLOCK,
         "fore:#7F7F7F")
      # end of line where string is not closed
      self.StyleSetSpec(stc.STC_P_STRINGEOL,
         "fore:#000000")
         
      self.StyleSetSpec(stc.STC_P_WORD,
         "fore:#00007F")
         
      
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
      
   def UpdateUI(self, appData):
      pass
      #self.CaretChange()
      
   def OnCaretChange(self, e):
      wx.CallAfter(self.CaretChange)
      e.Skip()   
      
   def CaretChange(self):
      self.MarkerDeleteAll(self.markerCaretLine)
      self.MarkerAdd(self.GetCurrentLine(), self.markerCaretLine)
      self.autoScroll = False
      
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
      
   def GetAutoScroll(self):
      return self.autoScroll
   
   def SetAutoScroll(self, autoScroll):
      self.autoScroll = autoScroll
      


"""----------------------------------------------------------------------------
   gcsConnectionPanel:
   controls to connect disconnect with the machine.
----------------------------------------------------------------------------"""
class gcsConnectionPanel(wx.ScrolledWindow):
   def __init__(self, parent, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent
      
      self.InitUI()
      width,height = self.GetSizeTuple()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)
      flexGridSizer = wx.FlexGridSizer(2,2)
      gridSizer = wx.GridSizer(1,3)
      
      #vBoxSizer.Add(wx.StaticText(self))
      vBoxSizer.Add(flexGridSizer, 0, flag=wx.LEFT|wx.TOP|wx.RIGHT, border=5)
      vBoxSizer.Add(gridSizer, 0, flag=wx.ALL, border=5)

      # get serial port list and baud rate speeds
      spList = self.mainWindow.GetSerialPortList()
      brList = self.mainWindow.GetSerialBaudRateList()
     
      # Add serial port controls
      spText = wx.StaticText(self, label="Serial Port:")
      flexGridSizer.Add(spText, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      
      self.spComboBox = wx.ComboBox(self, -1, value=spList[0], 
         choices=spList, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
      flexGridSizer.Add(self.spComboBox, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
      
      # Add baud rate controls
      srText = wx.StaticText(self, label="Baud Rate:")
      flexGridSizer.Add(srText, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      
      self.sbrComboBox = wx.ComboBox(self, -1, value=brList[3], 
         choices=brList, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
      flexGridSizer.Add(self.sbrComboBox, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
      
      
      # Add open/close/refresh buttons
      self.openButton = wx.Button(self, label="Open")
      self.openButton.SetToolTip(wx.ToolTip("Open serial port"))
      self.Bind(wx.EVT_BUTTON, self.OnOpen, self.openButton)
      gridSizer.Add(self.openButton)

      self.closeButton = wx.Button(self, label="Close")
      self.closeButton.SetToolTip(wx.ToolTip("Close serial port"))
      self.Bind(wx.EVT_BUTTON, self.OnClose, self.closeButton)
      self.closeButton.Disable()
      gridSizer.Add(self.closeButton)
      
      self.closeRefresh = wx.Button(self, wx.ID_REFRESH)
      self.closeRefresh.SetToolTip(wx.ToolTip("Refresh serial port list"))
      self.Bind(wx.EVT_BUTTON, self.OnRefresh, self.closeRefresh)
      gridSizer.Add(self.closeRefresh)
      
      self.SetSizer(vBoxSizer)
      self.Layout()
      
   def UpdateUI(self, appData):
      self.appData = appData
      if appData.serialPortIsOpen:
         self.openButton.Disable()
         self.closeButton.Enable()
         self.closeRefresh.Disable()
      else:
         self.openButton.Enable()
         self.closeButton.Disable()
         self.closeRefresh.Enable()
         
   def OnOpen(self, e):
      self.mainWindow.SerialOpen(self.spComboBox.GetValue(), 
         self.sbrComboBox.GetValue())

   def OnClose(self, e):
      self.mainWindow.SerialClose()

   def OnRefresh(self, e):
      spList = self.mainWindow.GetSerialPortList()
      brList = self.mainWindow.GetSerialBaudRateList()
      
      self.spComboBox.Clear()
      for sPort in spList:
         self.spComboBox.Append(sPort)
      self.spComboBox.SetValue(spList[0])
      
      self.sbrComboBox.Clear()
      for sBaoudRate in brList:
         self.sbrComboBox.Append(sBaoudRate)
      self.sbrComboBox.SetValue(brList[3])

"""----------------------------------------------------------------------------
   gcsMachineStatusPanel:
   Status information about machine, controls to enable auto and manual 
   refresh.
----------------------------------------------------------------------------"""
class gcsMachineStatusPanel(wx.ScrolledWindow):
   def __init__(self, parent, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent
      
      self.machineDataColor = wx.RED
      
      self.InitUI()
      width,height = self.GetSizeTuple()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)
      gridSizer = wx.GridSizer(2,2)
      
      # Add Static Boxes ------------------------------------------------------
      wBox, self.wX, self.wY, self.wZ = self.CreatePositionStaticBox("Work Position")
      mBox, self.mX, self.mY, self.mZ = self.CreatePositionStaticBox("Machine Position")
      sBox, self.sConncted, self.sState, self.sSpindle = self.CreateStatusStaticBox("Status")
     
      gridSizer.Add(wBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      gridSizer.Add(mBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      gridSizer.Add(sBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      
      # Add Buttons -----------------------------------------------------------
      self.autoRefreshCheckBox = wx.CheckBox (self, label="Auto Refresh")
      self.autoRefreshCheckBox.SetToolTip(
         wx.ToolTip("Aromatically update machine status (experimental)"))
      self.Bind(wx.EVT_CHECKBOX, self.OnAutoRefresh, self.autoRefreshCheckBox)
      vBoxSizer.Add(self.autoRefreshCheckBox)
      
      self.refreshButton = wx.Button(self, wx.ID_REFRESH)
      self.refreshButton.SetToolTip(
         wx.ToolTip("Refresh machine status"))
      self.Bind(wx.EVT_BUTTON, self.OnRefresh, self.refreshButton)
      vBoxSizer.Add(self.refreshButton)
      self.refreshButton.Disable()
      
      gridSizer.Add(vBoxSizer, 0, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      
      # Finish up init UI
      self.SetSizer(gridSizer)
      self.Layout()
      
   def UpdateUI(self, appData, statusData=None):
      self.appData = appData
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
         self.sSpindle.SetLabel("Unknown")
         
      if appData.serialPortIsOpen:
         self.refreshButton.Enable()
         self.sConncted.SetLabel("Yes")
      else:
         self.refreshButton.Disable()
         self.sConncted.SetLabel("No")
      
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
      spindleText = wx.StaticText(self, label="Spindle:")
      spindleStatus = wx.StaticText(self, label=gOffString)
      spindleStatus.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(spindleText, 0, flag=wx.ALIGN_LEFT)
      flexGridSizer.Add(spindleStatus, 0, flag=wx.ALIGN_LEFT)

      return positionBoxSizer, connectedStatus, runningStatus, spindleStatus
      
   def OnRefresh(self, e):
      self.mainWindow.GetMachineStatus()

   def OnAutoRefresh(self, e):
      self.mainWindow.MachineStatusAutoRefresh(e.IsChecked())


"""----------------------------------------------------------------------------
   gcsMachineJoggingPanel:
   Status information about machine, controls to enable auto and manual 
   refresh.
----------------------------------------------------------------------------"""
class gcsMachineJoggingPanel(wx.ScrolledWindow):
   def __init__(self, parent, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent
      
      self.useMachineWorkPosition = False
      
      self.InitUI()
      width,height = self.GetSizeTuple()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

   def InitUI(self):
      vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)
      
      # Add Controls ----------------------------------------------------------
      buttonBox = self.CreateButtons()
      vPanelBoxSizer.Add(buttonBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      
      joggingPositionBox, self.jX, self.jY, self.jZ, self.jSpindle = self.CreatePositionStaticBox("Jogging Status")
      vPanelBoxSizer.Add(joggingPositionBox, 1, flag=wx.ALL|wx.EXPAND, border=5)
      
      # Finish up init UI
      self.SetSizer(vPanelBoxSizer)
      self.Layout()

   def UpdateUI(self, appData, statusData=None):
      self.appData = appData
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
         
      if appData.serialPortIsOpen:
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
      
   def CreatePositionStaticBox(self, label):
      # Position static box ---------------------------------------------------
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      vBoxLeftSizer = wx.BoxSizer(wx.VERTICAL)
      vBoxRightSizer = wx.BoxSizer(wx.VERTICAL)
      
      hBoxSizer.Add(vBoxLeftSizer, 0, flag=wx.EXPAND)
      hBoxSizer.Add(vBoxRightSizer, 0, flag=wx.EXPAND|wx.ALIGN_LEFT|wx.LEFT|wx.TOP, border=5)
      
      positionBoxSizer = self.CreateStaticBox(label)      
      flexGridSizer = wx.FlexGridSizer(4,2)
      positionBoxSizer.Add(flexGridSizer, 1, flag=wx.EXPAND)
      vBoxLeftSizer.Add(positionBoxSizer, 0, flag=wx.EXPAND)

      # Add X pos
      xText = wx.StaticText(self, label="X:")
      xPosition = wx.TextCtrl(self, value=gZeroString)
      flexGridSizer.Add(xText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(xPosition, 1, flag=wx.EXPAND)
      
      # Add Y Pos
      yText = wx.StaticText(self, label="Y:")
      yPosition = wx.TextCtrl(self, value=gZeroString)
      flexGridSizer.Add(yText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(yPosition, 1, flag=wx.EXPAND)
      
      # Add Z Pos
      zText = wx.StaticText(self, label="Z:")
      zPosition = wx.TextCtrl(self, value=gZeroString)
      flexGridSizer.Add(zText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(zPosition, 1, flag=wx.EXPAND)

      # Add Spindle status
      spindleText = wx.StaticText(self, label="SP:")
      spindleStatus = wx.TextCtrl(self, value=gOffString, style=wx.TE_READONLY)
      spindleStatus.SetBackgroundColour(gReadOnlyBkColor)
      flexGridSizer.Add(spindleText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(spindleStatus, 1, flag=wx.EXPAND)
      
      # add spin ctrl
      spinBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      vBoxLeftSizer.Add(spinBoxSizer)
      
      spinText = wx.StaticText(self, -1, "Step Size:  ")
      spinBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      
      self.spinCtrl = FS.FloatSpin(self, -1, 
         min_val=0, max_val=99999, increment=0.10, value=1.0, 
         agwStyle=FS.FS_LEFT)
      self.spinCtrl.SetFormat("%f")
      self.spinCtrl.SetDigits(4)

      spinBoxSizer.Add(self.spinCtrl, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      
      # Add Checkbox for sync with work position
      self.useWorkPosCheckBox = wx.CheckBox (self, label="Use Work Pos")
      self.useWorkPosCheckBox.SetToolTip(
         wx.ToolTip("Use Machine status to update Jogging position (experimental)"))
      self.Bind(wx.EVT_CHECKBOX, self.OnUseMachineWorkPosition, self.useWorkPosCheckBox)
      vBoxLeftSizer.Add(self.useWorkPosCheckBox)
      
      # add Buttons
      self.resettoZeroPositionButton = wx.Button(self, label="Rst to Zero")
      self.resettoZeroPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToZeroPos, self.resettoZeroPositionButton)
      vBoxRightSizer.Add(self.resettoZeroPositionButton, flag=wx.EXPAND)
      
      self.resettoCurrentPositionButton = wx.Button(self, label="Rst to Pos")
      self.resettoCurrentPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToCurrentPos, self.resettoCurrentPositionButton)
      vBoxRightSizer.Add(self.resettoCurrentPositionButton, flag=wx.EXPAND)

      self.goZeroButton = wx.Button(self, label="Go Zero Pos")
      self.goZeroButton.SetToolTip(
         wx.ToolTip("Move to Machine Working position X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnGoZero, self.goZeroButton)
      vBoxRightSizer.Add(self.goZeroButton, flag=wx.EXPAND)
      
      self.goToCurrentPositionButton = wx.Button(self, label="Go to Pos")
      self.goToCurrentPositionButton.SetToolTip(
         wx.ToolTip("Move to to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnGoPos, self.goToCurrentPositionButton)
      vBoxRightSizer.Add(self.goToCurrentPositionButton, flag=wx.EXPAND)

      self.goHomeButton = wx.Button(self, label="Go Home Pos")
      self.goHomeButton.SetToolTip(
         wx.ToolTip("Execute Machine Homing Cycle"))
      self.Bind(wx.EVT_BUTTON, self.OnGoHome, self.goHomeButton)
      vBoxRightSizer.Add(self.goHomeButton, flag=wx.EXPAND)
      
      
      return hBoxSizer, xPosition, yPosition, zPosition, spindleStatus
      
   def CreateButtons(self):      
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

   def OnUseMachineWorkPosition(self, e):
      self.useMachineWorkPosition = e.IsChecked()
      
   def OnRefresh(self, e):
      pass

"""----------------------------------------------------------------------------
   gcsMainWindow:
   Main Window Inits the UI and other panels, it also controls the worker 
   threads and resources such as serial port.
----------------------------------------------------------------------------"""
class gcsMainWindow(wx.Frame):
   
   def __init__(self, parent, id=wx.ID_ANY, title="", cmd_line_options=None, 
      pos=wx.DefaultPosition, size=(800, 600), style=wx.DEFAULT_FRAME_STYLE):
      
      wx.Frame.__init__(self, parent, id, title, pos, size, style)
      
      # init config file
      self.configFile = wx.FileConfig("gstat", style=wx.CONFIG_USE_LOCAL_FILE)
        
      # register for thread events
      EVT_THREAD_QUEUE_EVENT(self, self.OnThreadEvent)
      
      # create serial obj
      self.serPort = serial.Serial()
      
      # create app data obj
      self.appData = gcsAppData()
            
      # init some variables
      self.serialPortThread = None
      
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
      
      #self.CreateStatusBar()
      #self.GetStatusBar().SetStatusText("Ready")
      
      
      self.connectionPanel = gcsConnectionPanel(self)
      self.machineStatusPanel = gcsMachineStatusPanel(self)
      self.machineJoggingPanel = gcsMachineJoggingPanel(self)
      
      # output Window
      self.outputText = wx.TextCtrl(self, 
         style=wx.TE_MULTILINE|wx.TE_RICH2|wx.TE_READONLY)
      self.outputText.SetBackgroundColour(gReadOnlyBkColor)
      
      wx.Log_SetActiveTarget(gcsLog(self.outputText))
        
      # for serious debugging
      #wx.Log_SetActiveTarget(wx.LogStderr())
      #wx.Log_SetTraceMask(wx.TraceMessages)
      
      # main gcode list control
      self.gcText = gcsGcodeStcStyledTextCtrl(self, style=wx.NO_BORDER)
      self.gcText.SetAutoScroll(True)
      
      # cli interface
      self.cliPanel = gcsCliComboBox(self)
      self.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter, self.cliPanel)
      self.cliPanel.LoadConfig(self.configFile)

      # add the panes to the manager
      self.aui_mgr.AddPane(self.gcText,
         aui.AuiPaneInfo().Name("GCODE_PANEL").CenterPane().Caption("GCODE"))
      
      self.aui_mgr.AddPane(self.connectionPanel,
         aui.AuiPaneInfo().Name("CON_PANEL").Right().Position(1).Caption("Connection").BestSize(300,120))

      self.aui_mgr.AddPane(self.machineStatusPanel,
         aui.AuiPaneInfo().Name("MACHINE_STATUS_PANEL").Right().Position(2).Caption("Machine Status").BestSize(300,180))
      
      self.aui_mgr.AddPane(self.machineJoggingPanel,
         aui.AuiPaneInfo().Name("MACHINE_JOGGING_PANEL").Right().Position(3).Caption("Machine Jogging").BestSize(300,310))
         
      self.aui_mgr.AddPane(self.outputText,
         aui.AuiPaneInfo().Name("OUTPUT_PANEL").Bottom().Row(2).Caption("Output").BestSize(600,150))
         
      self.aui_mgr.AddPane(self.cliPanel,
         aui.AuiPaneInfo().Name("CLI_PANEL").Bottom().Row(1).Caption("Command").BestSize(600,30))

      self.CreateMenu()
      self.CreateToolBar()
      
      # tell the manager to "commit" all the changes just made
      self.aui_mgr.SetAGWFlags(self.aui_mgr.GetAGWFlags()|aui.AUI_MGR_ALLOW_ACTIVE_PANE )

      # load default layout
      perspectiveDefault = self.aui_mgr.SavePerspective()
      self.SaveLayoutData(gConfigWindowResetLayout)
      
      self.LoadLayoutData(gConfigWindowDefaultLayout, False)
      
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
      maxFileHistory = self.configFile.ReadInt(gConfigWindowMaxFileHistory)
      if maxFileHistory == 0:
         maxFileHistory = 8 
         self.configFile.WriteInt(gConfigWindowMaxFileHistory, maxFileHistory)
               
      self.fileHistory = wx.FileHistory(maxFileHistory)
      self.fileHistory.Load(self.configFile)
      self.fileHistory.UseMenu(recentMenu)
      self.fileHistory.AddFilesToMenu()      
      
      fileMenu.Append(wx.ID_EXIT,                     "E&xit")
      
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
      viewMenu.AppendSeparator()
      viewMenu.Append(gID_MENU_LOAD_DEFAULT_LAYOUT,            "&Load Layout")
      viewMenu.Append(gID_MENU_SAVE_DEFAULT_LAYOUT,            "S&ave Layout")
      viewMenu.Append(gID_MENU_RESET_DEFAULT_LAYOUT,           "R&eset Layout")
      #viewMenu.Append(gID_MENU_LOAD_LAYOUT,                    "Loa&d Layout...")
      #viewMenu.Append(gID_MENU_SAVE_LAYOUT,                    "Sa&ve Layout...")
      
      #------------------------------------------------------------------------
      # Run menu
      runMenu = wx.Menu()
      self.menuBar.Append(runMenu, "&Run")
      
      runItem = wx.MenuItem(runMenu, gID_MENU_RUN,    "&Run\tF5")
      runItem.SetBitmap(imgPlayBlack.GetBitmap())
      runItem.SetDisabledBitmap(imgPlayGray.GetBitmap())
      runMenu.AppendItem(runItem)      
      
      stepItem = wx.MenuItem(runMenu, gID_MENU_STEP,  "S&tep")
      stepItem.SetBitmap(imgNextBlack.GetBitmap())
      stepItem.SetDisabledBitmap(imgNextGray.GetBitmap())      
      runMenu.AppendItem(stepItem)      
      
      stopItem = wx.MenuItem(runMenu, gID_MENU_STOP,  "&Stop")
      stopItem.SetBitmap(imgStopBlack.GetBitmap())
      stopItem.SetDisabledBitmap(imgStopGray.GetBitmap())            
      runMenu.AppendItem(stopItem)      

      runMenu.AppendSeparator()
      breakItem = wx.MenuItem(runMenu, gID_MENU_BREAK_TOGGLE, 
                                                      "Brea&kpoint Toggle\tF9")
      breakItem.SetBitmap(imgBreakBlack.GetBitmap())
      breakItem.SetDisabledBitmap(imgBreakGray.GetBitmap())
      runMenu.AppendItem(breakItem)
      
      runMenu.Append(gID_MENU_BREAK_REMOVE_ALL,       "Breakpoint &Remove All")
      runMenu.AppendSeparator()

      setPCItem = wx.MenuItem(runMenu, gID_MENU_SET_PC,"Set &PC")
      setPCItem.SetBitmap(imgMapPinBlack.GetBitmap())
      setPCItem.SetDisabledBitmap(imgMapPinGray.GetBitmap())            
      runMenu.AppendItem(setPCItem)      

      gotoPCItem = wx.MenuItem(runMenu, gID_MENU_GOTO_PC,
                                                      "&Goto PC")
      gotoPCItem.SetBitmap(imgGoToMapPinBlack.GetBitmap())
      gotoPCItem.SetDisabledBitmap(imgGoToMapPinGray.GetBitmap())            
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
      self.Bind(wx.EVT_MENU,        self.OnOpen,         id=wx.ID_OPEN)
      self.Bind(wx.EVT_MENU_RANGE,  self.OnFileHistory,  id=wx.ID_FILE1, id2=wx.ID_FILE9)
      self.Bind(wx.EVT_MENU,        self.OnClose,        id=wx.ID_EXIT)
      self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN, 
                           self.OnDropDownToolBarOpen,   id=gID_TOOLBAR_OPEN)      
                           
      #------------------------------------------------------------------------
      # View menu bind
      self.Bind(wx.EVT_MENU, self.OnMainToolBar,         id=gID_MENU_MAIN_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnRunToolBar,          id=gID_MENU_RUN_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnStatusToolBar,       id=gID_MENU_STATUS_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnOutput,              id=gID_MENU_OUTPUT_PANEL)
      self.Bind(wx.EVT_MENU, self.OnCommand,             id=gID_MENU_COMAMND_PANEL)
      self.Bind(wx.EVT_MENU, self.OnMachineStatus,       id=gID_MENU_MACHINE_STATUS_PANEL)
      self.Bind(wx.EVT_MENU, self.OnMachineJogging,      id=gID_MENU_MACHINE_JOGGING_PANEL)
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
      
      self.gcodeToolBar.AddSimpleTool(gID_MENU_STEP, "Step", imgNextBlack.GetBitmap(),
         "Step")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_STEP, imgNextGray.GetBitmap())
      
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

      self.gcodeToolBar.AddSimpleTool(gID_MENU_GOTO_PC, "Goto PC", imgGoToMapPinBlack.GetBitmap(),
         "Goto PC")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_GOTO_PC, imgGoToMapPinGray.GetBitmap())         
      
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
      self.cliPanel.UpdateUI(self.appData)
      self.gcText.UpdateUI(self.appData)
      self.connectionPanel.UpdateUI(self.appData)
      self.machineStatusPanel.UpdateUI(self.appData)
      self.machineJoggingPanel.UpdateUI(self.appData)
      
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
   def OnOpen(self, e):
      """ File Open """
      # get current file data
      currentPath = self.appData.gcodeFileName
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
         self.appData.gcodeFileName = dlgFile.GetPath()
         self.lineNumber = 0
        
         # save history
         self.fileHistory.AddFileToHistory(self.appData.gcodeFileName)
         self.fileHistory.Save(self.configFile)
         self.configFile.Flush()  
         
         self.FileOpen(self.appData.gcodeFileName)
         
   def OnDropDownToolBarOpen(self, e):
      if not e.IsDropDownClicked():
         self.OnOpen(e)
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
      self.appData.gcodeFileName = self.fileHistory.GetHistoryFile(fileNumber)
      self.fileHistory.AddFileToHistory(self.appData.gcodeFileName)  # move up the list
      self.fileHistory.Save(self.configFile)
      self.configFile.Flush()  
      
      self.FileOpen(self.appData.gcodeFileName)
         
   def FileOpen(self, fileName):
      if os.path.exists(fileName):
         self.appData.gcodeFileName = fileName
         self.appData.gcodeFileNumLines = 0
         
         #self.gcText.DeleteAllItems()
         self.gcText.SetReadOnly(False)         
         self.gcText.ClearAll()
         fileLines = []

         statinfo = os.stat(self.appData.gcodeFileName)
         fileSize = statinfo.st_size
         gcodeFile = open(self.appData.gcodeFileName, 'r')
         
         # create opne fiel progress
         dlgProgress = wx.ProgressDialog(
            "Open", "Reading file...",
            maximum = fileSize,
            parent=self,
            style = 
               wx.PD_APP_MODAL | 
               wx.PD_AUTO_HIDE | 
               wx.PD_ELAPSED_TIME | 
               wx.PD_CAN_ABORT
         )
         
         updateChunk = fileSize/100
         lastUpdate = 0
         keepGoing = True
         
         for strLine in gcodeFile:
            # add line to list control
            self.gcText.AppendText(strLine)
            self.appData.gcodeFileNumLines += 1 
            fileLines.append(strLine)

            # update progress dialog
            currentPosition = gcodeFile.tell()
            if (currentPosition - lastUpdate) > updateChunk:
               lastUpdate = currentPosition
               (keepGoing, skip) = dlgProgress.Update(currentPosition)
               
            if not keepGoing:
               break
         
         # finish up
         dlgProgress.Update(fileSize)
         dlgProgress.Destroy()
         gcodeFile.close()
         
         if keepGoing:
            self.appData.gcodeFileLines = fileLines
            self.appData.fileIsOpen = True
         else:
            self.appData.gcodeFileName = ""
            self.appData.gcodeFileLines = []
            self.appData.gcodeFileNumLines = 0
            self.appData.fileIsOpen = False
            self.gcText.DeleteAllItems()

         self.appData.breakPoints = set()
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
      
      self.gcText.SetReadOnly(True)
      
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
      
   def OnLoadDefaultLayout(self, e):
      self.LoadLayoutData(gConfigWindowDefaultLayout)
      self.aui_mgr.Update()
   
   def OnSaveDefaultLayout(self, e):
      self.SaveLayoutData(gConfigWindowDefaultLayout)
      
   def OnResetDefaultLayout(self, e):
      self.configFile.DeleteGroup(gConfigWindowDefaultLayout)
      self.LoadLayoutData(gConfigWindowResetLayout)
   
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
         self.mw2tQueue.put(threadEvent(gEV_CMD_RUN, 
            [self.appData.gcodeFileLines, self.appData.programCounter, self.appData.breakPoints]))
         self.mw2tQueue.join()
         
         self.gcText.SetAutoScroll(True)
         self.gcText.GoToPC()
         self.appData.swState = gSTATE_RUN
         self.UpdateUI()
         
   def OnRunUpdate(self, e=None):
      state = False
      if self.appData.fileIsOpen and \
         self.appData.serialPortIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         state = True
         
      if e is not None:
         e.Enable(state)
      
      self.gcodeToolBar.EnableTool(gID_MENU_RUN, state)

   def OnStep(self, e):
      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_STEP, 
            [self.appData.gcodeFileLines, self.appData.programCounter, self.appData.breakPoints]))
         self.mw2tQueue.join()
         
         self.appData.swState = gSTATE_STEP
         self.UpdateUI()

   def OnStepUpdate(self, e=None):
      state = False
      if self.appData.fileIsOpen and \
         self.appData.serialPortIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         state = True
         
      if e is not None:
         e.Enable(state)
      
      self.gcodeToolBar.EnableTool(gID_MENU_STEP, state)
      
   def OnStop(self, e):
      self.Stop()
      
   def OnStopUpdate(self, e=None):
      state = False   
      if self.appData.fileIsOpen and \
         self.appData.serialPortIsOpen and \
         self.appData.swState != gSTATE_IDLE and \
         self.appData.swState != gSTATE_BREAK:
         
         state = True
         
      if e is not None:
         e.Enable(state)
      
      self.gcodeToolBar.EnableTool(gID_MENU_STOP, state)
         
   def OnBreakToggle(self, e):
      pc = self.gcText.GetCurrentLine()
      enable = False
      
      if pc in self.appData.breakPoints:
         self.appData.breakPoints.remove(pc)
      else:
         self.appData.breakPoints.add(pc)
         enable = True
      
      self.gcText.UpdateBreakPoint(pc, enable)
      
   def OnBreakToggleUpdate(self, e=None):
      state = False
      if self.appData.fileIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         state = True         
         
      if e is not None:
         e.Enable(state)
      
      self.gcodeToolBar.EnableTool(gID_MENU_BREAK_TOGGLE, state)
         
   def OnBreakRemoveAll(self, e):
      self.breakPoints = set()
      self.gcText.UpdateBreakPoint(-1, False)
      
   def OnBreakRemoveAllUpdate(self, e):
      if self.appData.fileIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         e.Enable(True)
      else:
         e.Enable(False)
         
   def OnSetPC(self, e):
      self.SetPC()
      
   def OnSetPCUpdate(self, e=None):
      state = False
      if self.appData.fileIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):

         state = True         
         
      if e is not None:
         e.Enable(state)
      
      self.gcodeToolBar.EnableTool(gID_MENU_SET_PC, state)
      
   def OnGoToPC(self, e):
      self.gcText.SetAutoScroll(True)
      self.gcText.GoToPC()
      
   def OnGoToPCUpdate(self, e=None):
      state = False   
      if self.appData.fileIsOpen:
         state = True         
         
      if e is not None:
         e.Enable(state)
      
      self.gcodeToolBar.EnableTool(gID_MENU_GOTO_PC, state)
      
   #---------------------------------------------------------------------------
   # Status Menu/ToolBar Handlers
   #---------------------------------------------------------------------------
   def OnStatusToolBarForceUpdate(self):   
      # Link status
      if self.appData.serialPortIsOpen:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "LINKED")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkBlack.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkBlack.GetBitmap())
      else:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "UNLINKED")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkGray.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, imgLinkGray.GetBitmap())
         
      # Program status
      if self.appData.swState == gSTATE_IDLE:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "IDLE")
      elif self.appData.swState == gSTATE_RUN:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "RUN")
      elif self.appData.swState == gSTATE_STEP:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "STEP")
      elif self.appData.swState == gSTATE_BREAK:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "BREAK")
         
      #Machine status
      self.statusToolBar.EnableTool(gID_TOOLBAR_MACHINE_STATUS, self.appData.serialPortIsOpen)
      self.statusToolBar.SetToolLabel(gID_TOOLBAR_MACHINE_STATUS, "IDLE")
      
      self.statusToolBar.Refresh()
      
      
   #---------------------------------------------------------------------------
   # Help Menu Handlers
   #---------------------------------------------------------------------------
   def OnAbout(self, event):
      # First we create and fill the info object
      aboutDialog = wx.AboutDialogInfo()
      aboutDialog.Name = __appname__
      aboutDialog.Version = __version__
      aboutDialog.Copyright = __copyright__
      #aboutDialog.Description = __description__
      aboutDialog.Description = wordwrap(__description__, 400, wx.ClientDC(self))
      aboutDialog.WebSite = ("https://github.com/duembeg/gcs", "GCode Step home page")
      #aboutDialog.Developers = __authors__

      #aboutDialog.License = wordwrap(licenseText, 500, wx.ClientDC(self))

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
      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_EXIT, None))
         self.mw2tQueue.join()

      self.cliPanel.SaveConfig(self.configFile)
      self.aui_mgr.UnInit()
      
      self.Destroy()
      e.Skip()

   """-------------------------------------------------------------------------
   gcsMainWindow: General Functions
   -------------------------------------------------------------------------"""
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
      brList = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
      return brList
      
   def SerialOpen(self, port, baudrate):
      self.serPort.baudrate = baudrate
      
      if port != "None":
         if os.name == 'nt':
            port=r"\\.\%s" % (str(port))
            
         self.serPort.port = port
         self.serPort.timeout=1
         self.serPort.open()
         
         if self.serPort.isOpen():
            self.serialPortThread = gcsSserialPortThread(self, self.serPort, self.mw2tQueue, 
               self.t2mwQueue, self.cmdLineOptions)
               
            self.mw2tQueue.put(threadEvent(gEV_CMD_AUTO_STATUS, self.appData.machineStatusAutoRefresh))
            self.mw2tQueue.join()
               
            self.appData.serialPortIsOpen = True
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
      
      self.appData.serialPortIsOpen = False
      self.GrblDetected = False
      self.UpdateUI()
   
   def Stop(self):
      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_STOP, None))
         self.mw2tQueue.join()
         
         self.appData.swState = gSTATE_IDLE
         self.UpdateUI()
      
   def SetPC(self, pc=None):
      if pc is None:
         pc = self.gcText.GetCurrentLine()

      self.appData.programCounter = pc
      self.gcText.UpdatePC(pc)
      
   def MachineStatusAutoRefresh(self, autoRefresh):
      self.appData.machineStatusAutoRefresh = autoRefresh

      if self.serialPortThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_AUTO_STATUS, self.appData.machineStatusAutoRefresh))
         self.mw2tQueue.join()
      
      if autoRefresh:
         self.GetMachineStatus()
      
   def GetMachineStatus(self):
      if self.appData.serialPortIsOpen:
         self.SerialWrite(gGRBL_CMD_GET_STATUS)
         
   def SerialWrite(self, serialData):
      if self.appData.serialPortIsOpen:
         txtOutputData = "> %s" %(serialData)
         wx.LogMessage("")
         self.outputText.AppendText(txtOutputData)
      
         if self.appData.swState == gSTATE_RUN:
            # if we are in run state let thread do teh writing
            if self.serialPortThread is not None:
               self.mw2tQueue.put(threadEvent(gEV_CMD_SEND, serialData))
               self.mw2tQueue.join()
         else:
            self.serPort.write(serialData)
            
         # this won't work well is too  early, mechanical movement
         # say G01X300 might take a long time, but grbl will reutn almost
         # immediately with "ok"
         #if self.appData.machineStatusAutoRefresh and serialData != "?":
         #   self.serPort.write("?")

      elif self.cmdLineOptions.verbose:
         print "gcsMainWindow ERROR: attempt serial write with port closed!!"
         
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
               if self.appData.swState == gSTATE_RUN:
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
                  self.appData.grblDetected = True
                  if self.appData.machineStatusAutoRefresh:
                     self.GetMachineStatus()
               self.UpdateUI()                     
            
            # Grbl status data
            rematch = gReMachineStatus.match(teData)
            if rematch is not None:
               statusData = rematch.groups()
               if self.cmdLineOptions.vverbose:
                  print "gcsMainWindow re.status.match %s" % str(statusData)
               self.machineStatusPanel.UpdateUI(self.appData, statusData)
               self.machineJoggingPanel.UpdateUI(self.appData, statusData)
            
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
            self.appData.swState = gSTATE_IDLE
            self.Refresh()
            self.UpdateUI()
            self.SetPC(0)
            
         elif te.event_id == gEV_STEP_END:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_STEP_END."
            self.appData.swState = gSTATE_IDLE
            self.UpdateUI()

         elif te.event_id == gEV_HIT_BRK_PT:
            if self.cmdLineOptions.vverbose:
               print "gcsMainWindow got event gEV_HIT_BRK_PT."
            self.appData.swState = gSTATE_BREAK
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
   start here:
   Python script start up code.
----------------------------------------------------------------------------"""
if __name__ == '__main__':
   
   (cmd_line_options, cli_args) = get_cli_params()

   app = wx.App(0)
   gcsMainWindow(None, title=__appname__, cmd_line_options=cmd_line_options)
   app.MainLoop()
