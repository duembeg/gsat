#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gcode-step.py: 
----------------------------------------------------------------------------"""

__appname__ = "GCode Step"

__description__ = \
"gcode step (gcs) is a cross-platform GCODE debug/step for grbl like GCODE interpreter. "\
"with features similar to software buggered; like usage of breakpoint, change " \
"program counter, inspection/modification of variables, and continuing with the "\
"program flow."


# define authorship information
__authors__     = ['Wilhelm Duembeg']
__author__      = ','.join(__authors__)
__credits__     = []
__copyright__   = 'Copyright (c) 2013'
__license__     = 'GPL'

# maintanence information
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
# MENU & TOOLBAR IDs
# -----------------------------------------------------------------------------
gID_tbOpen = wx.NewId()
gID_Run = wx.NewId()
gID_BreakToggle = wx.NewId()
gID_BreakRemoveAll = wx.NewId()
gID_Step = wx.NewId()
gID_Stop = wx.NewId()
gID_SetPC = wx.NewId()
gID_GoToPC = wx.NewId()

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
   These iamges generated by /usr/bin/img2py
----------------------------------------------------------------------------"""
#------------------------------------------------------------------------------
# imgPlay
#------------------------------------------------------------------------------
imgPlay = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAKBmlUWHRYTUw6Y29tLmFkb2Jl"
    "LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRj"
    "emtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0i"
    "QWRvYmUgWE1QIENvcmUgNS4wLWMwNjAgNjEuMTM0Nzc3LCAyMDEwLzAyLzEyLTE3OjMyOjAw"
    "ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5"
    "LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0i"
    "IgogICAgeG1sbnM6eG1wUmlnaHRzPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvcmln"
    "aHRzLyIKICAgIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIK"
    "ICAgIHhtbG5zOklwdGM0eG1wQ29yZT0iaHR0cDovL2lwdGMub3JnL3N0ZC9JcHRjNHhtcENv"
    "cmUvMS4wL3htbG5zLyIKICAgIHhtbG5zOnBsdXNfMV89Imh0dHA6Ly9ucy51c2VwbHVzLm9y"
    "Zy9sZGYveG1wLzEuMC8iCiAgICB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFw"
    "LzEuMC8iCiAgICB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21t"
    "LyIKICAgIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUv"
    "UmVzb3VyY2VFdmVudCMiCiAgIHhtcFJpZ2h0czpNYXJrZWQ9IlRydWUiCiAgIHhtcDpNZXRh"
    "ZGF0YURhdGU9IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgIHhtcE1NOkluc3RhbmNl"
    "SUQ9InhtcC5paWQ6OUFGMzRFNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAgIHhtcE1N"
    "OkRvY3VtZW50SUQ9InhtcC5kaWQ6OUFGMzRFNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIi"
    "CiAgIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDo5QUYzNEU1NzgyMjhFMDEx"
    "OTg5Q0MwQTFBRDAyQjVDMiI+CiAgIDx4bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgIDxyZGY6"
    "QWx0PgogICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9u"
    "cyBBdHRyaWJ1dGlvbi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRm"
    "OkFsdD4KICAgPC94bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgPGRjOmNyZWF0b3I+CiAgICA8"
    "cmRmOlNlcT4KICAgICA8cmRmOmxpPkdlbnRsZWZhY2UgY3VzdG9tIHRvb2xiYXIgaWNvbnMg"
    "ZGVzaWduPC9yZGY6bGk+CiAgICA8L3JkZjpTZXE+CiAgIDwvZGM6Y3JlYXRvcj4KICAgPGRj"
    "OmRlc2NyaXB0aW9uPgogICAgPHJkZjpBbHQ+CiAgICAgPHJkZjpsaSB4bWw6bGFuZz0ieC1k"
    "ZWZhdWx0Ij5XaXJlZnJhbWUgbW9ubyB0b29sYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3Jk"
    "ZjpBbHQ+CiAgIDwvZGM6ZGVzY3JpcHRpb24+CiAgIDxkYzpzdWJqZWN0PgogICAgPHJkZjpC"
    "YWc+CiAgICAgPHJkZjpsaT5jdXN0b20gaWNvbiBkZXNpZ248L3JkZjpsaT4KICAgICA8cmRm"
    "OmxpPnRvb2xiYXIgaWNvbnM8L3JkZjpsaT4KICAgICA8cmRmOmxpPmN1c3RvbSBpY29uczwv"
    "cmRmOmxpPgogICAgIDxyZGY6bGk+aW50ZXJmYWNlIGRlc2lnbjwvcmRmOmxpPgogICAgIDxy"
    "ZGY6bGk+dWkgZGVzaWduPC9yZGY6bGk+CiAgICAgPHJkZjpsaT5ndWkgZGVzaWduPC9yZGY6"
    "bGk+CiAgICAgPHJkZjpsaT50YXNrYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3JkZjpCYWc+"
    "CiAgIDwvZGM6c3ViamVjdD4KICAgPGRjOnJpZ2h0cz4KICAgIDxyZGY6QWx0PgogICAgIDxy"
    "ZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9ucyBBdHRyaWJ1dGlv"
    "bi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRmOkFsdD4KICAgPC9k"
    "YzpyaWdodHM+CiAgIDxJcHRjNHhtcENvcmU6Q3JlYXRvckNvbnRhY3RJbmZvCiAgICBJcHRj"
    "NHhtcENvcmU6Q2lVcmxXb3JrPSJodHRwOi8vd3d3LmdlbnRsZWZhY2UuY29tIi8+CiAgIDxw"
    "bHVzXzFfOkltYWdlQ3JlYXRvcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAg"
    "cGx1c18xXzpJbWFnZUNyZWF0b3JOYW1lPSJnZW50bGVmYWNlLmNvbSIvPgogICAgPC9yZGY6"
    "U2VxPgogICA8L3BsdXNfMV86SW1hZ2VDcmVhdG9yPgogICA8cGx1c18xXzpDb3B5cmlnaHRP"
    "d25lcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgcGx1c18xXzpDb3B5cmln"
    "aHRPd25lck5hbWU9ImdlbnRsZWZhY2UuY29tIi8+CiAgICA8L3JkZjpTZXE+CiAgIDwvcGx1"
    "c18xXzpDb3B5cmlnaHRPd25lcj4KICAgPHhtcE1NOkhpc3Rvcnk+CiAgICA8cmRmOlNlcT4K"
    "ICAgICA8cmRmOmxpCiAgICAgIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiCiAgICAgIHN0RXZ0Omlu"
    "c3RhbmNlSUQ9InhtcC5paWQ6OUFGMzRFNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAg"
    "ICAgIHN0RXZ0OndoZW49IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgICAgIHN0RXZ0"
    "OmNoYW5nZWQ9Ii9tZXRhZGF0YSIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rv"
    "cnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hw"
    "YWNrZXQgZW5kPSJyIj8+M5nU3QAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJ"
    "ZTwAAAA8dEVYdEFMVFRhZwBUaGlzIGlzIHRoZSBpY29uIGZyb20gR2VudGxlZmFjZS5jb20g"
    "ZnJlZSBpY29ucyBzZXQuINhr6MQAAABEdEVYdENvcHlyaWdodABDcmVhdGl2ZSBDb21tb25z"
    "IEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVze92woAAAAEVpVFh0"
    "RGVzY3JpcHRpb24AAAAAAFRoaXMgaXMgdGhlIGljb24gZnJvbSBHZW50bGVmYWNlLmNvbSBm"
    "cmVlIGljb25zIHNldC4gvBH4GgAAAEhpVFh0Q29weXJpZ2h0AAAAAABDcmVhdGl2ZSBDb21t"
    "b25zIEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVzWILLBQAAAMpJ"
    "REFUeNpiYBhowIzMMTIyei8hIaEBxBdfvHjxgRgDGJE5urq6/2Hs////NwLxhKtXr+I1iAmZ"
    "8+fPHzj++/dvPRDfV1dXTyDaBSoqKv+xKQK65AIQF967d+8AXgPk5eX/47MNaMgBIE58/Pjx"
    "A5gYC7KC379/EwozByCuB+JErAaA/E4AHGBkZGxEFiDWBReAGgvfvXuHEQaEDPgA0vj58+cF"
    "RKUqdnb2/zDMwcHRwMnJKUBSsmRiYnrPzMw8n4WFRYFh5ACAAAMASMxZaop4eY0AAAAASUVO"
    "RK5CYII=")
    
#------------------------------------------------------------------------------
# imgNext
#------------------------------------------------------------------------------
imgNext = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAKBmlUWHRYTUw6Y29tLmFkb2Jl"
    "LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRj"
    "emtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0i"
    "QWRvYmUgWE1QIENvcmUgNS4wLWMwNjAgNjEuMTM0Nzc3LCAyMDEwLzAyLzEyLTE3OjMyOjAw"
    "ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5"
    "LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0i"
    "IgogICAgeG1sbnM6eG1wUmlnaHRzPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvcmln"
    "aHRzLyIKICAgIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIK"
    "ICAgIHhtbG5zOklwdGM0eG1wQ29yZT0iaHR0cDovL2lwdGMub3JnL3N0ZC9JcHRjNHhtcENv"
    "cmUvMS4wL3htbG5zLyIKICAgIHhtbG5zOnBsdXNfMV89Imh0dHA6Ly9ucy51c2VwbHVzLm9y"
    "Zy9sZGYveG1wLzEuMC8iCiAgICB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFw"
    "LzEuMC8iCiAgICB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21t"
    "LyIKICAgIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUv"
    "UmVzb3VyY2VFdmVudCMiCiAgIHhtcFJpZ2h0czpNYXJrZWQ9IlRydWUiCiAgIHhtcDpNZXRh"
    "ZGF0YURhdGU9IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgIHhtcE1NOkluc3RhbmNl"
    "SUQ9InhtcC5paWQ6Q0NERTU4NTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAgIHhtcE1N"
    "OkRvY3VtZW50SUQ9InhtcC5kaWQ6Q0NERTU4NTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIi"
    "CiAgIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpDQ0RFNTg1NzgyMjhFMDEx"
    "OTg5Q0MwQTFBRDAyQjVDMiI+CiAgIDx4bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgIDxyZGY6"
    "QWx0PgogICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9u"
    "cyBBdHRyaWJ1dGlvbi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRm"
    "OkFsdD4KICAgPC94bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgPGRjOmNyZWF0b3I+CiAgICA8"
    "cmRmOlNlcT4KICAgICA8cmRmOmxpPkdlbnRsZWZhY2UgY3VzdG9tIHRvb2xiYXIgaWNvbnMg"
    "ZGVzaWduPC9yZGY6bGk+CiAgICA8L3JkZjpTZXE+CiAgIDwvZGM6Y3JlYXRvcj4KICAgPGRj"
    "OmRlc2NyaXB0aW9uPgogICAgPHJkZjpBbHQ+CiAgICAgPHJkZjpsaSB4bWw6bGFuZz0ieC1k"
    "ZWZhdWx0Ij5XaXJlZnJhbWUgbW9ubyB0b29sYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3Jk"
    "ZjpBbHQ+CiAgIDwvZGM6ZGVzY3JpcHRpb24+CiAgIDxkYzpzdWJqZWN0PgogICAgPHJkZjpC"
    "YWc+CiAgICAgPHJkZjpsaT5jdXN0b20gaWNvbiBkZXNpZ248L3JkZjpsaT4KICAgICA8cmRm"
    "OmxpPnRvb2xiYXIgaWNvbnM8L3JkZjpsaT4KICAgICA8cmRmOmxpPmN1c3RvbSBpY29uczwv"
    "cmRmOmxpPgogICAgIDxyZGY6bGk+aW50ZXJmYWNlIGRlc2lnbjwvcmRmOmxpPgogICAgIDxy"
    "ZGY6bGk+dWkgZGVzaWduPC9yZGY6bGk+CiAgICAgPHJkZjpsaT5ndWkgZGVzaWduPC9yZGY6"
    "bGk+CiAgICAgPHJkZjpsaT50YXNrYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3JkZjpCYWc+"
    "CiAgIDwvZGM6c3ViamVjdD4KICAgPGRjOnJpZ2h0cz4KICAgIDxyZGY6QWx0PgogICAgIDxy"
    "ZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9ucyBBdHRyaWJ1dGlv"
    "bi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRmOkFsdD4KICAgPC9k"
    "YzpyaWdodHM+CiAgIDxJcHRjNHhtcENvcmU6Q3JlYXRvckNvbnRhY3RJbmZvCiAgICBJcHRj"
    "NHhtcENvcmU6Q2lVcmxXb3JrPSJodHRwOi8vd3d3LmdlbnRsZWZhY2UuY29tIi8+CiAgIDxw"
    "bHVzXzFfOkltYWdlQ3JlYXRvcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAg"
    "cGx1c18xXzpJbWFnZUNyZWF0b3JOYW1lPSJnZW50bGVmYWNlLmNvbSIvPgogICAgPC9yZGY6"
    "U2VxPgogICA8L3BsdXNfMV86SW1hZ2VDcmVhdG9yPgogICA8cGx1c18xXzpDb3B5cmlnaHRP"
    "d25lcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgcGx1c18xXzpDb3B5cmln"
    "aHRPd25lck5hbWU9ImdlbnRsZWZhY2UuY29tIi8+CiAgICA8L3JkZjpTZXE+CiAgIDwvcGx1"
    "c18xXzpDb3B5cmlnaHRPd25lcj4KICAgPHhtcE1NOkhpc3Rvcnk+CiAgICA8cmRmOlNlcT4K"
    "ICAgICA8cmRmOmxpCiAgICAgIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiCiAgICAgIHN0RXZ0Omlu"
    "c3RhbmNlSUQ9InhtcC5paWQ6Q0NERTU4NTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAg"
    "ICAgIHN0RXZ0OndoZW49IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgICAgIHN0RXZ0"
    "OmNoYW5nZWQ9Ii9tZXRhZGF0YSIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rv"
    "cnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hw"
    "YWNrZXQgZW5kPSJyIj8+zUdmfgAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJ"
    "ZTwAAAA8dEVYdEFMVFRhZwBUaGlzIGlzIHRoZSBpY29uIGZyb20gR2VudGxlZmFjZS5jb20g"
    "ZnJlZSBpY29ucyBzZXQuINhr6MQAAABEdEVYdENvcHlyaWdodABDcmVhdGl2ZSBDb21tb25z"
    "IEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVze92woAAAAEVpVFh0"
    "RGVzY3JpcHRpb24AAAAAAFRoaXMgaXMgdGhlIGljb24gZnJvbSBHZW50bGVmYWNlLmNvbSBm"
    "cmVlIGljb25zIHNldC4gvBH4GgAAAEhpVFh0Q29weXJpZ2h0AAAAAABDcmVhdGl2ZSBDb21t"
    "b25zIEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVzWILLBQAAALpJ"
    "REFUeNpiYBhowIjMMTIy+g8EG4A48cKFCx/Q5ZD5586dA+tlQhb8/fs3w58/fwKA+Ly2trYB"
    "uhwyhgEmbIqABij8/fv3vLq6egEhA1iQDQBqRPdiv7Kysj3IS1jkMA1ANhkJBAANMGBkZCTb"
    "ABBQwCVByAsw8ACXIcS4YAMTE1Piv3//3pNsANDfhZ8/f54AYvPw8JDkhQ9AzYHfv38/QIT3"
    "EICZmfk/EO9nZWUVwCEHxwzDBwAEGAB1DneqLVqvMgAAAABJRU5ErkJggg==")

#------------------------------------------------------------------------------
# imgStop
#------------------------------------------------------------------------------
imgStop = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAKBmlUWHRYTUw6Y29tLmFkb2Jl"
    "LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRj"
    "emtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0i"
    "QWRvYmUgWE1QIENvcmUgNS4wLWMwNjAgNjEuMTM0Nzc3LCAyMDEwLzAyLzEyLTE3OjMyOjAw"
    "ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5"
    "LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0i"
    "IgogICAgeG1sbnM6eG1wUmlnaHRzPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvcmln"
    "aHRzLyIKICAgIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIK"
    "ICAgIHhtbG5zOklwdGM0eG1wQ29yZT0iaHR0cDovL2lwdGMub3JnL3N0ZC9JcHRjNHhtcENv"
    "cmUvMS4wL3htbG5zLyIKICAgIHhtbG5zOnBsdXNfMV89Imh0dHA6Ly9ucy51c2VwbHVzLm9y"
    "Zy9sZGYveG1wLzEuMC8iCiAgICB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFw"
    "LzEuMC8iCiAgICB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21t"
    "LyIKICAgIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUv"
    "UmVzb3VyY2VFdmVudCMiCiAgIHhtcFJpZ2h0czpNYXJrZWQ9IlRydWUiCiAgIHhtcDpNZXRh"
    "ZGF0YURhdGU9IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgIHhtcE1NOkluc3RhbmNl"
    "SUQ9InhtcC5paWQ6RDdBMzNDNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAgIHhtcE1N"
    "OkRvY3VtZW50SUQ9InhtcC5kaWQ6RDdBMzNDNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIi"
    "CiAgIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpEN0EzM0M1NzgyMjhFMDEx"
    "OTg5Q0MwQTFBRDAyQjVDMiI+CiAgIDx4bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgIDxyZGY6"
    "QWx0PgogICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9u"
    "cyBBdHRyaWJ1dGlvbi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRm"
    "OkFsdD4KICAgPC94bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgPGRjOmNyZWF0b3I+CiAgICA8"
    "cmRmOlNlcT4KICAgICA8cmRmOmxpPkdlbnRsZWZhY2UgY3VzdG9tIHRvb2xiYXIgaWNvbnMg"
    "ZGVzaWduPC9yZGY6bGk+CiAgICA8L3JkZjpTZXE+CiAgIDwvZGM6Y3JlYXRvcj4KICAgPGRj"
    "OmRlc2NyaXB0aW9uPgogICAgPHJkZjpBbHQ+CiAgICAgPHJkZjpsaSB4bWw6bGFuZz0ieC1k"
    "ZWZhdWx0Ij5XaXJlZnJhbWUgbW9ubyB0b29sYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3Jk"
    "ZjpBbHQ+CiAgIDwvZGM6ZGVzY3JpcHRpb24+CiAgIDxkYzpzdWJqZWN0PgogICAgPHJkZjpC"
    "YWc+CiAgICAgPHJkZjpsaT5jdXN0b20gaWNvbiBkZXNpZ248L3JkZjpsaT4KICAgICA8cmRm"
    "OmxpPnRvb2xiYXIgaWNvbnM8L3JkZjpsaT4KICAgICA8cmRmOmxpPmN1c3RvbSBpY29uczwv"
    "cmRmOmxpPgogICAgIDxyZGY6bGk+aW50ZXJmYWNlIGRlc2lnbjwvcmRmOmxpPgogICAgIDxy"
    "ZGY6bGk+dWkgZGVzaWduPC9yZGY6bGk+CiAgICAgPHJkZjpsaT5ndWkgZGVzaWduPC9yZGY6"
    "bGk+CiAgICAgPHJkZjpsaT50YXNrYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3JkZjpCYWc+"
    "CiAgIDwvZGM6c3ViamVjdD4KICAgPGRjOnJpZ2h0cz4KICAgIDxyZGY6QWx0PgogICAgIDxy"
    "ZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9ucyBBdHRyaWJ1dGlv"
    "bi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRmOkFsdD4KICAgPC9k"
    "YzpyaWdodHM+CiAgIDxJcHRjNHhtcENvcmU6Q3JlYXRvckNvbnRhY3RJbmZvCiAgICBJcHRj"
    "NHhtcENvcmU6Q2lVcmxXb3JrPSJodHRwOi8vd3d3LmdlbnRsZWZhY2UuY29tIi8+CiAgIDxw"
    "bHVzXzFfOkltYWdlQ3JlYXRvcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAg"
    "cGx1c18xXzpJbWFnZUNyZWF0b3JOYW1lPSJnZW50bGVmYWNlLmNvbSIvPgogICAgPC9yZGY6"
    "U2VxPgogICA8L3BsdXNfMV86SW1hZ2VDcmVhdG9yPgogICA8cGx1c18xXzpDb3B5cmlnaHRP"
    "d25lcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgcGx1c18xXzpDb3B5cmln"
    "aHRPd25lck5hbWU9ImdlbnRsZWZhY2UuY29tIi8+CiAgICA8L3JkZjpTZXE+CiAgIDwvcGx1"
    "c18xXzpDb3B5cmlnaHRPd25lcj4KICAgPHhtcE1NOkhpc3Rvcnk+CiAgICA8cmRmOlNlcT4K"
    "ICAgICA8cmRmOmxpCiAgICAgIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiCiAgICAgIHN0RXZ0Omlu"
    "c3RhbmNlSUQ9InhtcC5paWQ6RDdBMzNDNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAg"
    "ICAgIHN0RXZ0OndoZW49IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgICAgIHN0RXZ0"
    "OmNoYW5nZWQ9Ii9tZXRhZGF0YSIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rv"
    "cnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hw"
    "YWNrZXQgZW5kPSJyIj8+PLZrqQAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJ"
    "ZTwAAAA8dEVYdEFMVFRhZwBUaGlzIGlzIHRoZSBpY29uIGZyb20gR2VudGxlZmFjZS5jb20g"
    "ZnJlZSBpY29ucyBzZXQuINhr6MQAAABEdEVYdENvcHlyaWdodABDcmVhdGl2ZSBDb21tb25z"
    "IEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVze92woAAAAEVpVFh0"
    "RGVzY3JpcHRpb24AAAAAAFRoaXMgaXMgdGhlIGljb24gZnJvbSBHZW50bGVmYWNlLmNvbSBm"
    "cmVlIGljb25zIHNldC4gvBH4GgAAAEhpVFh0Q29weXJpZ2h0AAAAAABDcmVhdGl2ZSBDb21t"
    "b25zIEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVzWILLBQAAADRJ"
    "REFUeNpiYBjygBGZY2ho+J8YTefPn4frY0GW+P37N8kuGDWA2gb8+vVrCHphGACAAAMAO94e"
    "nD00RxwAAAAASUVORK5CYII=")
    
#------------------------------------------------------------------------------
# imgRecord
#------------------------------------------------------------------------------
imgRecord = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAKBmlUWHRYTUw6Y29tLmFkb2Jl"
    "LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRj"
    "emtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0i"
    "QWRvYmUgWE1QIENvcmUgNS4wLWMwNjAgNjEuMTM0Nzc3LCAyMDEwLzAyLzEyLTE3OjMyOjAw"
    "ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5"
    "LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0i"
    "IgogICAgeG1sbnM6eG1wUmlnaHRzPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvcmln"
    "aHRzLyIKICAgIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIK"
    "ICAgIHhtbG5zOklwdGM0eG1wQ29yZT0iaHR0cDovL2lwdGMub3JnL3N0ZC9JcHRjNHhtcENv"
    "cmUvMS4wL3htbG5zLyIKICAgIHhtbG5zOnBsdXNfMV89Imh0dHA6Ly9ucy51c2VwbHVzLm9y"
    "Zy9sZGYveG1wLzEuMC8iCiAgICB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFw"
    "LzEuMC8iCiAgICB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21t"
    "LyIKICAgIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUv"
    "UmVzb3VyY2VFdmVudCMiCiAgIHhtcFJpZ2h0czpNYXJrZWQ9IlRydWUiCiAgIHhtcDpNZXRh"
    "ZGF0YURhdGU9IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgIHhtcE1NOkluc3RhbmNl"
    "SUQ9InhtcC5paWQ6OTJGMzRFNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAgIHhtcE1N"
    "OkRvY3VtZW50SUQ9InhtcC5kaWQ6OTJGMzRFNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIi"
    "CiAgIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDo5MkYzNEU1NzgyMjhFMDEx"
    "OTg5Q0MwQTFBRDAyQjVDMiI+CiAgIDx4bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgIDxyZGY6"
    "QWx0PgogICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9u"
    "cyBBdHRyaWJ1dGlvbi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRm"
    "OkFsdD4KICAgPC94bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgPGRjOmNyZWF0b3I+CiAgICA8"
    "cmRmOlNlcT4KICAgICA8cmRmOmxpPkdlbnRsZWZhY2UgY3VzdG9tIHRvb2xiYXIgaWNvbnMg"
    "ZGVzaWduPC9yZGY6bGk+CiAgICA8L3JkZjpTZXE+CiAgIDwvZGM6Y3JlYXRvcj4KICAgPGRj"
    "OmRlc2NyaXB0aW9uPgogICAgPHJkZjpBbHQ+CiAgICAgPHJkZjpsaSB4bWw6bGFuZz0ieC1k"
    "ZWZhdWx0Ij5XaXJlZnJhbWUgbW9ubyB0b29sYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3Jk"
    "ZjpBbHQ+CiAgIDwvZGM6ZGVzY3JpcHRpb24+CiAgIDxkYzpzdWJqZWN0PgogICAgPHJkZjpC"
    "YWc+CiAgICAgPHJkZjpsaT5jdXN0b20gaWNvbiBkZXNpZ248L3JkZjpsaT4KICAgICA8cmRm"
    "OmxpPnRvb2xiYXIgaWNvbnM8L3JkZjpsaT4KICAgICA8cmRmOmxpPmN1c3RvbSBpY29uczwv"
    "cmRmOmxpPgogICAgIDxyZGY6bGk+aW50ZXJmYWNlIGRlc2lnbjwvcmRmOmxpPgogICAgIDxy"
    "ZGY6bGk+dWkgZGVzaWduPC9yZGY6bGk+CiAgICAgPHJkZjpsaT5ndWkgZGVzaWduPC9yZGY6"
    "bGk+CiAgICAgPHJkZjpsaT50YXNrYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3JkZjpCYWc+"
    "CiAgIDwvZGM6c3ViamVjdD4KICAgPGRjOnJpZ2h0cz4KICAgIDxyZGY6QWx0PgogICAgIDxy"
    "ZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9ucyBBdHRyaWJ1dGlv"
    "bi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRmOkFsdD4KICAgPC9k"
    "YzpyaWdodHM+CiAgIDxJcHRjNHhtcENvcmU6Q3JlYXRvckNvbnRhY3RJbmZvCiAgICBJcHRj"
    "NHhtcENvcmU6Q2lVcmxXb3JrPSJodHRwOi8vd3d3LmdlbnRsZWZhY2UuY29tIi8+CiAgIDxw"
    "bHVzXzFfOkltYWdlQ3JlYXRvcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAg"
    "cGx1c18xXzpJbWFnZUNyZWF0b3JOYW1lPSJnZW50bGVmYWNlLmNvbSIvPgogICAgPC9yZGY6"
    "U2VxPgogICA8L3BsdXNfMV86SW1hZ2VDcmVhdG9yPgogICA8cGx1c18xXzpDb3B5cmlnaHRP"
    "d25lcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgcGx1c18xXzpDb3B5cmln"
    "aHRPd25lck5hbWU9ImdlbnRsZWZhY2UuY29tIi8+CiAgICA8L3JkZjpTZXE+CiAgIDwvcGx1"
    "c18xXzpDb3B5cmlnaHRPd25lcj4KICAgPHhtcE1NOkhpc3Rvcnk+CiAgICA8cmRmOlNlcT4K"
    "ICAgICA8cmRmOmxpCiAgICAgIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiCiAgICAgIHN0RXZ0Omlu"
    "c3RhbmNlSUQ9InhtcC5paWQ6OTJGMzRFNTc4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAg"
    "ICAgIHN0RXZ0OndoZW49IjIwMTEtMDEtMjVUMTM6NTU6MDkrMDE6MDAiCiAgICAgIHN0RXZ0"
    "OmNoYW5nZWQ9Ii9tZXRhZGF0YSIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rv"
    "cnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hw"
    "YWNrZXQgZW5kPSJyIj8+znw+ogAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJ"
    "ZTwAAAA8dEVYdEFMVFRhZwBUaGlzIGlzIHRoZSBpY29uIGZyb20gR2VudGxlZmFjZS5jb20g"
    "ZnJlZSBpY29ucyBzZXQuINhr6MQAAABEdEVYdENvcHlyaWdodABDcmVhdGl2ZSBDb21tb25z"
    "IEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVze92woAAAAEVpVFh0"
    "RGVzY3JpcHRpb24AAAAAAFRoaXMgaXMgdGhlIGljb24gZnJvbSBHZW50bGVmYWNlLmNvbSBm"
    "cmVlIGljb25zIHNldC4gvBH4GgAAAEhpVFh0Q29weXJpZ2h0AAAAAABDcmVhdGl2ZSBDb21t"
    "b25zIEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVzWILLBQAAAMlJ"
    "REFUeNpiYBjygBGboIGBQQMjI2M+kCkAFfrw////iRcuXGggaICOjs55kBk4LLxw5coVQ2QB"
    "ZmSOurp6w79//yKAmAEHlhAREWF8+/btAawuUFJSeo/kbFzgw7179wRhHBYYQ1paWuD3798C"
    "RIQbihq4AcBAYgAaQFksCAsLE+UFYBgIYg1EVlZWzr9//zoAMQMuDAzIzp8/fx7AGY2cnJzn"
    "gd7BGo3AtHHh+/fvhgT9xcLC0sDMzPweiP9D8XuQGMPwBAABBgAEr2rDXEadXwAAAABJRU5E"
    "rkJggg==")
 
#------------------------------------------------------------------------------
# imgLink
#------------------------------------------------------------------------------
imgLink = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAKBmlUWHRYTUw6Y29tLmFkb2Jl"
    "LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRj"
    "emtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0i"
    "QWRvYmUgWE1QIENvcmUgNS4wLWMwNjAgNjEuMTM0Nzc3LCAyMDEwLzAyLzEyLTE3OjMyOjAw"
    "ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5"
    "LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0i"
    "IgogICAgeG1sbnM6eG1wUmlnaHRzPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvcmln"
    "aHRzLyIKICAgIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIK"
    "ICAgIHhtbG5zOklwdGM0eG1wQ29yZT0iaHR0cDovL2lwdGMub3JnL3N0ZC9JcHRjNHhtcENv"
    "cmUvMS4wL3htbG5zLyIKICAgIHhtbG5zOnBsdXNfMV89Imh0dHA6Ly9ucy51c2VwbHVzLm9y"
    "Zy9sZGYveG1wLzEuMC8iCiAgICB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFw"
    "LzEuMC8iCiAgICB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21t"
    "LyIKICAgIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUv"
    "UmVzb3VyY2VFdmVudCMiCiAgIHhtcFJpZ2h0czpNYXJrZWQ9IlRydWUiCiAgIHhtcDpNZXRh"
    "ZGF0YURhdGU9IjIwMTEtMDEtMjVUMTM6NTU6MTErMDE6MDAiCiAgIHhtcE1NOkluc3RhbmNl"
    "SUQ9InhtcC5paWQ6NkRDNjI5NTg4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAgIHhtcE1N"
    "OkRvY3VtZW50SUQ9InhtcC5kaWQ6NkRDNjI5NTg4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIi"
    "CiAgIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDo2REM2Mjk1ODgyMjhFMDEx"
    "OTg5Q0MwQTFBRDAyQjVDMiI+CiAgIDx4bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgIDxyZGY6"
    "QWx0PgogICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9u"
    "cyBBdHRyaWJ1dGlvbi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRm"
    "OkFsdD4KICAgPC94bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgPGRjOmNyZWF0b3I+CiAgICA8"
    "cmRmOlNlcT4KICAgICA8cmRmOmxpPkdlbnRsZWZhY2UgY3VzdG9tIHRvb2xiYXIgaWNvbnMg"
    "ZGVzaWduPC9yZGY6bGk+CiAgICA8L3JkZjpTZXE+CiAgIDwvZGM6Y3JlYXRvcj4KICAgPGRj"
    "OmRlc2NyaXB0aW9uPgogICAgPHJkZjpBbHQ+CiAgICAgPHJkZjpsaSB4bWw6bGFuZz0ieC1k"
    "ZWZhdWx0Ij5XaXJlZnJhbWUgbW9ubyB0b29sYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3Jk"
    "ZjpBbHQ+CiAgIDwvZGM6ZGVzY3JpcHRpb24+CiAgIDxkYzpzdWJqZWN0PgogICAgPHJkZjpC"
    "YWc+CiAgICAgPHJkZjpsaT5jdXN0b20gaWNvbiBkZXNpZ248L3JkZjpsaT4KICAgICA8cmRm"
    "OmxpPnRvb2xiYXIgaWNvbnM8L3JkZjpsaT4KICAgICA8cmRmOmxpPmN1c3RvbSBpY29uczwv"
    "cmRmOmxpPgogICAgIDxyZGY6bGk+aW50ZXJmYWNlIGRlc2lnbjwvcmRmOmxpPgogICAgIDxy"
    "ZGY6bGk+dWkgZGVzaWduPC9yZGY6bGk+CiAgICAgPHJkZjpsaT5ndWkgZGVzaWduPC9yZGY6"
    "bGk+CiAgICAgPHJkZjpsaT50YXNrYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3JkZjpCYWc+"
    "CiAgIDwvZGM6c3ViamVjdD4KICAgPGRjOnJpZ2h0cz4KICAgIDxyZGY6QWx0PgogICAgIDxy"
    "ZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9ucyBBdHRyaWJ1dGlv"
    "bi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRmOkFsdD4KICAgPC9k"
    "YzpyaWdodHM+CiAgIDxJcHRjNHhtcENvcmU6Q3JlYXRvckNvbnRhY3RJbmZvCiAgICBJcHRj"
    "NHhtcENvcmU6Q2lVcmxXb3JrPSJodHRwOi8vd3d3LmdlbnRsZWZhY2UuY29tIi8+CiAgIDxw"
    "bHVzXzFfOkltYWdlQ3JlYXRvcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAg"
    "cGx1c18xXzpJbWFnZUNyZWF0b3JOYW1lPSJnZW50bGVmYWNlLmNvbSIvPgogICAgPC9yZGY6"
    "U2VxPgogICA8L3BsdXNfMV86SW1hZ2VDcmVhdG9yPgogICA8cGx1c18xXzpDb3B5cmlnaHRP"
    "d25lcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgcGx1c18xXzpDb3B5cmln"
    "aHRPd25lck5hbWU9ImdlbnRsZWZhY2UuY29tIi8+CiAgICA8L3JkZjpTZXE+CiAgIDwvcGx1"
    "c18xXzpDb3B5cmlnaHRPd25lcj4KICAgPHhtcE1NOkhpc3Rvcnk+CiAgICA8cmRmOlNlcT4K"
    "ICAgICA8cmRmOmxpCiAgICAgIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiCiAgICAgIHN0RXZ0Omlu"
    "c3RhbmNlSUQ9InhtcC5paWQ6NkRDNjI5NTg4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAg"
    "ICAgIHN0RXZ0OndoZW49IjIwMTEtMDEtMjVUMTM6NTU6MTErMDE6MDAiCiAgICAgIHN0RXZ0"
    "OmNoYW5nZWQ9Ii9tZXRhZGF0YSIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rv"
    "cnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hw"
    "YWNrZXQgZW5kPSJyIj8+/N9SLgAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJ"
    "ZTwAAAA8dEVYdEFMVFRhZwBUaGlzIGlzIHRoZSBpY29uIGZyb20gR2VudGxlZmFjZS5jb20g"
    "ZnJlZSBpY29ucyBzZXQuINhr6MQAAABEdEVYdENvcHlyaWdodABDcmVhdGl2ZSBDb21tb25z"
    "IEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVze92woAAAAEVpVFh0"
    "RGVzY3JpcHRpb24AAAAAAFRoaXMgaXMgdGhlIGljb24gZnJvbSBHZW50bGVmYWNlLmNvbSBm"
    "cmVlIGljb25zIHNldC4gvBH4GgAAAEhpVFh0Q29weXJpZ2h0AAAAAABDcmVhdGl2ZSBDb21t"
    "b25zIEF0dHJpYnV0aW9uIE5vbi1Db21tZXJjaWFsIE5vIERlcml2YXRpdmVzWILLBQAAAXtJ"
    "REFUeNqMU0GKwkAQzETjRU+BQECEDXgIBCR5gfOMPSZP2BcYXyB5QfITsy+IePHoLgiCh+zu"
    "xYuY2eqQkVkxWRuK6e6a6unpSZj2hAVBEDPGFjIWQiyLoojJZ/+JZ7NZCnF4n0eRbLvdRr0u"
    "sed5KZYQm+tT4SdVVdnwXwDfsizW2oHruhzLum6TsWi322UKR3niNb2twPV65YCGE6PL5ZJP"
    "p1Nf4RLiCF0FCBnEVGQPFI7j+A3nywJ/rjCZTDja5U3bOd0Vayp5+A4KcSW3vBUYj8fqtDOI"
    "31UxLKJhKrnscDhEdQHbtlXxGzZ+PxDP1QOOx2NUd4WnoA9iIaeNjTncvdI25T7k1WD56XTK"
    "b7xpmkLepyzLGDENqlDEc7ifxD0ati6nCWwogY0bDCoAHHoB5EPiW200GgnCcDhcq3nEoeQA"
    "3qbvwRja5PRk/X6fI/4xDOMV3Kr5hLPz+Zx0/jCDwSCFSNyD8tqzhpNjXddFgy+Kn9H9CjAA"
    "QATeMeb/OaYAAAAASUVORK5CYII=")
 
#------------------------------------------------------------------------------
# imgTarget
#------------------------------------------------------------------------------
imgTarget = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAKBmlUWHRYTUw6Y29tLmFkb2Jl"
    "LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRj"
    "emtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0i"
    "QWRvYmUgWE1QIENvcmUgNS4wLWMwNjAgNjEuMTM0Nzc3LCAyMDEwLzAyLzEyLTE3OjMyOjAw"
    "ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5"
    "LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0i"
    "IgogICAgeG1sbnM6eG1wUmlnaHRzPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvcmln"
    "aHRzLyIKICAgIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIK"
    "ICAgIHhtbG5zOklwdGM0eG1wQ29yZT0iaHR0cDovL2lwdGMub3JnL3N0ZC9JcHRjNHhtcENv"
    "cmUvMS4wL3htbG5zLyIKICAgIHhtbG5zOnBsdXNfMV89Imh0dHA6Ly9ucy51c2VwbHVzLm9y"
    "Zy9sZGYveG1wLzEuMC8iCiAgICB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFw"
    "LzEuMC8iCiAgICB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21t"
    "LyIKICAgIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUv"
    "UmVzb3VyY2VFdmVudCMiCiAgIHhtcFJpZ2h0czpNYXJrZWQ9IlRydWUiCiAgIHhtcDpNZXRh"
    "ZGF0YURhdGU9IjIwMTEtMDEtMjVUMTM6NTU6MDcrMDE6MDAiCiAgIHhtcE1NOkluc3RhbmNl"
    "SUQ9InhtcC5paWQ6Qjc5QzJGNTY4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAgIHhtcE1N"
    "OkRvY3VtZW50SUQ9InhtcC5kaWQ6Qjc5QzJGNTY4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIi"
    "CiAgIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpCNzlDMkY1NjgyMjhFMDEx"
    "OTg5Q0MwQTFBRDAyQjVDMiI+CiAgIDx4bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgIDxyZGY6"
    "QWx0PgogICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9u"
    "cyBBdHRyaWJ1dGlvbi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRm"
    "OkFsdD4KICAgPC94bXBSaWdodHM6VXNhZ2VUZXJtcz4KICAgPGRjOmNyZWF0b3I+CiAgICA8"
    "cmRmOlNlcT4KICAgICA8cmRmOmxpPkdlbnRsZWZhY2UgY3VzdG9tIHRvb2xiYXIgaWNvbnMg"
    "ZGVzaWduPC9yZGY6bGk+CiAgICA8L3JkZjpTZXE+CiAgIDwvZGM6Y3JlYXRvcj4KICAgPGRj"
    "OmRlc2NyaXB0aW9uPgogICAgPHJkZjpBbHQ+CiAgICAgPHJkZjpsaSB4bWw6bGFuZz0ieC1k"
    "ZWZhdWx0Ij5XaXJlZnJhbWUgbW9ubyB0b29sYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3Jk"
    "ZjpBbHQ+CiAgIDwvZGM6ZGVzY3JpcHRpb24+CiAgIDxkYzpzdWJqZWN0PgogICAgPHJkZjpC"
    "YWc+CiAgICAgPHJkZjpsaT5jdXN0b20gaWNvbiBkZXNpZ248L3JkZjpsaT4KICAgICA8cmRm"
    "OmxpPnRvb2xiYXIgaWNvbnM8L3JkZjpsaT4KICAgICA8cmRmOmxpPmN1c3RvbSBpY29uczwv"
    "cmRmOmxpPgogICAgIDxyZGY6bGk+aW50ZXJmYWNlIGRlc2lnbjwvcmRmOmxpPgogICAgIDxy"
    "ZGY6bGk+dWkgZGVzaWduPC9yZGY6bGk+CiAgICAgPHJkZjpsaT5ndWkgZGVzaWduPC9yZGY6"
    "bGk+CiAgICAgPHJkZjpsaT50YXNrYmFyIGljb25zPC9yZGY6bGk+CiAgICA8L3JkZjpCYWc+"
    "CiAgIDwvZGM6c3ViamVjdD4KICAgPGRjOnJpZ2h0cz4KICAgIDxyZGY6QWx0PgogICAgIDxy"
    "ZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+Q3JlYXRpdmUgQ29tbW9ucyBBdHRyaWJ1dGlv"
    "bi1Ob25Db21tZXJjaWFsIGxpY2Vuc2U8L3JkZjpsaT4KICAgIDwvcmRmOkFsdD4KICAgPC9k"
    "YzpyaWdodHM+CiAgIDxJcHRjNHhtcENvcmU6Q3JlYXRvckNvbnRhY3RJbmZvCiAgICBJcHRj"
    "NHhtcENvcmU6Q2lVcmxXb3JrPSJodHRwOi8vd3d3LmdlbnRsZWZhY2UuY29tIi8+CiAgIDxw"
    "bHVzXzFfOkltYWdlQ3JlYXRvcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAg"
    "cGx1c18xXzpJbWFnZUNyZWF0b3JOYW1lPSJnZW50bGVmYWNlLmNvbSIvPgogICAgPC9yZGY6"
    "U2VxPgogICA8L3BsdXNfMV86SW1hZ2VDcmVhdG9yPgogICA8cGx1c18xXzpDb3B5cmlnaHRP"
    "d25lcj4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgcGx1c18xXzpDb3B5cmln"
    "aHRPd25lck5hbWU9ImdlbnRsZWZhY2UuY29tIi8+CiAgICA8L3JkZjpTZXE+CiAgIDwvcGx1"
    "c18xXzpDb3B5cmlnaHRPd25lcj4KICAgPHhtcE1NOkhpc3Rvcnk+CiAgICA8cmRmOlNlcT4K"
    "ICAgICA8cmRmOmxpCiAgICAgIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiCiAgICAgIHN0RXZ0Omlu"
    "c3RhbmNlSUQ9InhtcC5paWQ6Qjc5QzJGNTY4MjI4RTAxMTk4OUNDMEExQUQwMkI1QzIiCiAg"
    "ICAgIHN0RXZ0OndoZW49IjIwMTEtMDEtMjVUMTM6NTU6MDcrMDE6MDAiCiAgICAgIHN0RXZ0"
    "OmNoYW5nZWQ9Ii9tZXRhZGF0YSIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rv"
    "cnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hw"
    "YWNrZXQgZW5kPSJyIj8+I2uc7gAAABl0RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJ"
    "ZTwAAAA8dEVYdEFMVFRhZwBUaGlzIGlzIHRoZSBpY29uIGZyb20gR2VudGxlZmFjZS5jb20g"
    "ZnJlZSBpY29ucyBzZXQuINhr6MQAAAAfdEVYdENvcHlyaWdodABST1lBTFRZIEZSRUUgTElD"
    "RU5TRSDe2YtpAAAARWlUWHREZXNjcmlwdGlvbgAAAAAAVGhpcyBpcyB0aGUgaWNvbiBmcm9t"
    "IEdlbnRsZWZhY2UuY29tIGZyZWUgaWNvbnMgc2V0LiC8EfgaAAAAI2lUWHRDb3B5cmlnaHQA"
    "AAAAAFJPWUFMVFkgRlJFRSBMSUNFTlNFICddCkoAAAFBSURBVHjapFPLbYNAEIXIQjIfYckH"
    "EOIAEogDF9OB04FdQVxCUoFpIRVYroB0kHSAL5zxmVMagM17EkgEwUZWkB6z82Zmdz67ivLP"
    "T5UZsyzbqapaCiHCsizvcz5Psg26rtu0bUsZPJRBmqY5xAswDmQG16qqcmkGSZJccOoZuOHk"
    "Y58B5Y087YspR1GUAyKO49OIE8OaPHX6zW4QBEEdhmEx5qCLiV7Qb9BX/Pm+z1qDvllv4wCW"
    "MNGvEAfE7NkX1fM8BtWSYXwBe+kUXNfdQWww70/g2DTNx+DgOI7AXXgedNi52bnnft+N7XZb"
    "A8WEExO9oN/sGFkfcLBt+zTXA/K0A++LBVuWdQGEaZqFYRgHrimpc037nw9E1/V8vV7XgBih"
    "Bv/60EvTNG0PCMoln5VsA9T6ja4r6Ph9yedHgAEAVlqNpuGNLjUAAAAASUVORK5CYII=")


    
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
   provides varius data information
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
      
      self.configKeySaveCmdHistory = "cliSaveCmdHistory"
      self.configKeyCmdHistory = "cliCmdHistory"
      self.configKeyCmdMaxHistory = "cliCmdMaxHistory"
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
         if self.GetCount() > gMaxCliCmdHistory:
            self.Delete(0)
            
         self.cliCommand = cliCommand
         self.Append(self.cliCommand)
         
      self.SetValue("")
      e.Skip()
      
   def LoadConfig(self, configFile):
      # read save cmd history
      configData = configFile.Read(self.configKeySaveCmdHistory)
      
      if len(configData) > 0:
         self.cliSaveCmdHistory = eval(configData)
         
      # read cmd history max count
      configData = configFile.Read(self.configKeyCmdMaxHistory)
      
      if len(configData) > 0:
         self.cliCmdMaxCmdHistory = eval(configData)
         
      # read cmd hsitory
      configData = configFile.Read(self.configKeyCmdHistory)
      if len(configData) > 0:
         cliCommandHistory = configData.split(",")
         for cmd in cliCommandHistory:
            cmd = cmd.strip()
            if len(cmd) > 0:
               self.Append(cmd.strip())
               
         self.cliCommand = cliCommandHistory[len(cliCommandHistory) - 1]
            
   def SaveConfig(self, configFile):
      # write dave cmd history
      configFile.Write(self.configKeySaveCmdHistory, str(self.cliSaveCmdHistory))
      
      # write cmd history max count
      configFile.Write(self.configKeyCmdMaxHistory, str(self.cliCmdMaxCmdHistory))
      
      # write cmd history
      if self.cliSaveCmdHistory:
         cliCmdHistory = self.GetItems()
         if len(cliCmdHistory) > 0:
            cliCmdHistory =  ",".join(cliCmdHistory)
            configFile.Write(self.configKeyCmdHistory, cliCmdHistory)
      
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
      
      # Add Cehckbox for sync with work position
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
   
   def __init__(self, parent, id=wx.ID_ANY, title="", cli_options=None, 
      pos=wx.DefaultPosition, size=(800, 600), style=wx.DEFAULT_FRAME_STYLE):
      
      wx.Frame.__init__(self, parent, id, title, pos, size, style)
      
      # init config file
      self.configFile = wx.FileConfig("gcs", style=wx.CONFIG_USE_LOCAL_FILE)
        
      # register for thread events
      EVT_THREAD_QUEUE_EVENT(self, self.OnThreadEvent)
      
      # create serial obj
      self.serPort = serial.Serial()
      
      # create app data obj
      self.appData = gcsAppData()
            
      # init some variables
      self.workThread = None
      
      self.cliOptions = cli_options
      
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
      self.outputTextctrl = wx.TextCtrl(self, 
         style=wx.TE_MULTILINE|wx.TE_RICH2|wx.TE_READONLY)
      self.outputTextctrl.SetBackgroundColour(gReadOnlyBkColor)
      
      wx.Log_SetActiveTarget(gcsLog(self.outputTextctrl))
        
      # for serious debugging
      #wx.Log_SetActiveTarget(wx.LogStderr())
      #wx.Log_SetTraceMask(wx.TraceMessages)

      
      # main gcode list control
      self.gcText = gcsGcodeStcStyledTextCtrl(self)
      self.gcText.SetAutoScroll(True)
      
      # cli interface
      self.cli = gcsCliComboBox(self)
      self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter, self.cli)
      self.cli.LoadConfig(self.configFile)

      # add the panes to the manager
      self.aui_mgr.AddPane(self.gcText,
         aui.AuiPaneInfo().CenterPane().Caption("GCODE"))
      
      self.aui_mgr.AddPane(self.connectionPanel, 
         aui.AuiPaneInfo().Right().Position(1).Caption("Connection").BestSize(300,120))

      self.aui_mgr.AddPane(self.machineStatusPanel,          
         aui.AuiPaneInfo().Right().Position(2).Caption("Machine Status").BestSize(300,180))
      
      self.aui_mgr.AddPane(self.machineJoggingPanel,          
         aui.AuiPaneInfo().Right().Position(3).Caption("Machine Jogging").BestSize(300,310))
         
      self.aui_mgr.AddPane(self.outputTextctrl, 
         aui.AuiPaneInfo().Bottom().Row(2).Caption("Output").BestSize(600,150))
         
      self.aui_mgr.AddPane(self.cli, 
         aui.AuiPaneInfo().Bottom().Row(1).Caption("Command").BestSize(600,30))

      self.CreateMenu()
      self.CreateToolBar()

      # tell the manager to "commit" all the changes just made
      perspectiveDefault = self.aui_mgr.SavePerspective()
      
      #print str(perspectiveDefault)
      
      # add code to load from file...
      
      self.aui_mgr.LoadPerspective(perspectiveDefault)
      self.aui_mgr.Update()
      
      wx.CallAfter(self.UpdateUI)
      
   def CreateMenu(self):
   
      # Create the menubar
      #self.menuBar = FM.FlatMenuBar(self, wx.ID_ANY, 32, 5, options = FM_OPT_SHOW_TOOLBAR | FM_OPT_SHOW_CUSTOMIZE)
      #self.menuBar = FM.FlatMenuBar(self, wx.ID_ANY, options=FM_OPT_SHOW_TOOLBAR)
      self.menuBar = wx.MenuBar()
      
      # load history
      self.fileHistory = wx.FileHistory(8)
      self.fileHistory.Load(self.configFile)
      
      #------------------------------------------------------------------------
      # File Menu
      fileMenu = wx.Menu()
      fileMenu.Append(wx.ID_OPEN, "&Open")

      recentMenu = wx.Menu()
      self.fileHistory.UseMenu(recentMenu)
      self.fileHistory.AddFilesToMenu()      
      fileMenu.AppendMenu(wx.ID_ANY, "&Recent Files", recentMenu)      
      
      fileMenu.Append(wx.ID_EXIT, "Exit")
      
      #------------------------------------------------------------------------
      # File Menu
      runMenu = wx.Menu()
      
      runItem = wx.MenuItem(runMenu, gID_Run, "&Run\tF5")
      runItem.SetBitmap(imgPlay.GetBitmap())
      runMenu.AppendItem(runItem)      
      
      stepItem = wx.MenuItem(runMenu, gID_Step, "S&tep")
      stepItem.SetBitmap(imgNext.GetBitmap())
      runMenu.AppendItem(stepItem)      
      
      stopItem = wx.MenuItem(runMenu, gID_Stop, "&Stop")
      stopItem.SetBitmap(imgStop.GetBitmap())
      runMenu.AppendItem(stopItem)      

      runMenu.AppendSeparator()
      breakItem = wx.MenuItem(runMenu, gID_BreakToggle, "Bra&kpoint Toggle\tF9")
      breakItem.SetBitmap(imgRecord.GetBitmap())
      runMenu.AppendItem(breakItem)
      runMenu.Append(gID_BreakRemoveAll, "Brakpoint &Remove All")
      runMenu.AppendSeparator()
      runMenu.Append(gID_SetPC, "Set &PC")
      runMenu.Append(gID_GoToPC, "Show PC")
      
      
      #------------------------------------------------------------------------
      # Help Menu
      helpMenu = wx.Menu()
      helpMenu.Append(wx.ID_ABOUT, "&About", "About GCS")

        

      #fileMenu  = FM.FlatMenu()
      #recentMenu = FM.FlatMenu()

      #item = FM.FlatMenuItem(fileMenu, wx.ID_OPEN, "&Open File\tCtrl+O", "Open File", wx.ITEM_NORMAL)
      #fileMenu.AppendItem(item)
      #self.menuBar.AddTool(wx.ID_OPEN, "Open File")
      #self.menuBar.AddSeparator()   # Toolbar separator

      #self.fileHistory.UseMenu(recentMenu)
      #self.fileHistory.AddFilesToMenu()
      #item = FM.FlatMenuItem(fileMenu, wx.ID_ANY, "&Recent Files", "", wx.ITEM_NORMAL, recentMenu)
      #fileMenu.AppendItem(item)      

      '''
      view_menu = wx.Menu()
      view_menu.Append(wx.ID_ANY, "Use a Size Reporter for the Content Pane")
      view_menu.AppendSeparator()   
      '''
      self.menuBar.Append(fileMenu, "&File")
      self.menuBar.Append(runMenu, "&Run")
      self.menuBar.Append(helpMenu, "&Help")
      
      #menuBar.Append(view_menu, "&View")

      self.SetMenuBar(self.menuBar)
      #self.menuBar.PositionAUI(self.aui_mgr)      
      
      #------------------------------------------------------------------------
      # Bind events to handlers
      self.Bind(wx.EVT_MENU, self.OnOpen, id=wx.ID_OPEN)
      self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN, self.OnDropDownToolBarOpen, id=gID_tbOpen)
      self.Bind(wx.EVT_MENU_RANGE, self.OnFileHistory, id=wx.ID_FILE1, id2=wx.ID_FILE9)
      self.Bind(wx.EVT_MENU, self.OnClose, id=wx.ID_EXIT)
      
      self.Bind(wx.EVT_MENU, self.OnRun, id=gID_Run)
      self.Bind(wx.EVT_MENU, self.OnStep, id=gID_Step)
      self.Bind(wx.EVT_MENU, self.OnStop, id=gID_Stop)
      self.Bind(wx.EVT_MENU, self.OnBreakToggle, id=gID_BreakToggle)
      self.Bind(wx.EVT_MENU, self.OnBreakRemoveAll, id=gID_BreakRemoveAll)      
      self.Bind(wx.EVT_MENU, self.OnSetPC, id=gID_SetPC)
      self.Bind(wx.EVT_MENU, self.OnGoToPC, id=gID_GoToPC)
      
      self.Bind(wx.EVT_BUTTON, self.OnRun, id=gID_Run)
      self.Bind(wx.EVT_BUTTON, self.OnStep, id=gID_Step)
      self.Bind(wx.EVT_BUTTON, self.OnStop, id=gID_Stop)
      self.Bind(wx.EVT_BUTTON, self.OnBreakToggle, id=gID_BreakToggle)
      self.Bind(wx.EVT_BUTTON, self.OnSetPC, id=gID_SetPC)
      self.Bind(wx.EVT_BUTTON, self.OnGoToPC, id=gID_GoToPC)
      
      self.Bind(wx.EVT_UPDATE_UI, self.OnRunUpdate, id=gID_Run)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStepUpdate, id=gID_Step)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStopUpdate, id=gID_Stop)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakToggleUpdate, id=gID_BreakToggle)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakRemoveAllUpdate, id=gID_BreakRemoveAll)      
      self.Bind(wx.EVT_UPDATE_UI, self.OnSetPCUpdate, id=gID_SetPC)
      self.Bind(wx.EVT_UPDATE_UI, self.OnGoToPCUpdate, id=gID_GoToPC)
      
      
      self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)
      
      #------------------------------------------------------------------------
      # Create shortcut keys for menu
      acceleratorTable = wx.AcceleratorTable([
         (wx.ACCEL_ALT,  ord('X'), wx.ID_EXIT),
         #(wx.ACCEL_CTRL, ord('H'), helpID),
         #(wx.ACCEL_CTRL, ord('F'), findID),
         (wx.ACCEL_NORMAL, wx.WXK_F5, gID_Run),
         (wx.ACCEL_NORMAL, wx.WXK_F9, gID_BreakToggle),
      ])
      
      self.SetAcceleratorTable(acceleratorTable)
      
      
   def CreateToolBar(self):
      #------------------------------------------------------------------------
      # Main Tool Bar
      self.appToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize, 
         agwStyle=aui.AUI_TB_DEFAULT_STYLE | 
            aui.AUI_TB_OVERFLOW | 
            aui.AUI_TB_TEXT | 
            aui.AUI_TB_HORZ_TEXT
         )

      iconSize = (16, 16)
      self.appToolBar.SetToolBitmapSize(iconSize)
            
      self.appToolBar.AddSimpleTool(gID_tbOpen, "Open", wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN, size=iconSize))
      self.appToolBar.AddSimpleTool(wx.ID_ABOUT, "About", wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, size=iconSize))
      self.appToolBar.SetToolDropDown(gID_tbOpen, True)
      self.appToolBar.Realize()

      self.aui_mgr.AddPane(self.appToolBar, 
         aui.AuiPaneInfo().Caption("Main ToolBar").ToolbarPane().Top().Position(1))
      
      #------------------------------------------------------------------------
      # GCODE Tool Bar

      self.gcodeToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize, 
         agwStyle=aui.AUI_TB_DEFAULT_STYLE | 
            aui.AUI_TB_OVERFLOW | 
            aui.AUI_TB_TEXT | 
            aui.AUI_TB_HORZ_TEXT)
      

      self.gcodeToolBar.SetToolBitmapSize(wx.Size(16, 16))
      
      #self.gcodeToolBar.AddSimpleTool(gID_Run, "Run", imgPlay.GetBitmap())
      runButton = wx.BitmapButton (self.gcodeToolBar, gID_Run, imgPlay.GetBitmap(), 
         style=wx.BORDER_NONE|wx.BU_EXACTFIT)
      runButton.SetToolTip(wx.ToolTip("Run\tF5"))
      self.gcodeToolBar.AddControl(runButton)
      
      #self.gcodeToolBar.AddSimpleTool(gID_Step, "Step", imgNext.GetBitmap())
      stepButton = wx.BitmapButton (self.gcodeToolBar, gID_Step, imgNext.GetBitmap(), 
         style=wx.BORDER_NONE|wx.BU_EXACTFIT)
      stepButton.SetToolTip(wx.ToolTip("Step"))
      self.gcodeToolBar.AddControl(stepButton)      
      
      #self.gcodeToolBar.AddSimpleTool(gID_Stop, "Stop", imgStop.GetBitmap())
      stopButton = wx.BitmapButton (self.gcodeToolBar, gID_Stop, imgStop.GetBitmap(), 
         style=wx.BORDER_NONE|wx.BU_EXACTFIT)
      stopButton.SetToolTip(wx.ToolTip("Stop"))
      self.gcodeToolBar.AddControl(stopButton)      
      
      self.gcodeToolBar.AddSeparator()
      #self.gcodeToolBar.AddSimpleTool(gID_BreakToggle, "Break Toggle", imgRecord.GetBitmap())
      breakToggleButton = wx.BitmapButton (self.gcodeToolBar, gID_BreakToggle, imgRecord.GetBitmap(), 
         style=wx.BORDER_NONE|wx.BU_EXACTFIT)
      breakToggleButton.SetToolTip(wx.ToolTip("Brakpoint Toggle\tF9"))
      self.gcodeToolBar.AddControl(breakToggleButton)      
      
      self.gcodeToolBar.AddSeparator()
      #self.gcodeToolBar.AddSimpleTool(gID_SetPC, "Set PC", wx.NullBitmap)
      setPCButton = wx.Button (self.gcodeToolBar, gID_SetPC, "Set PC",
         style=wx.BORDER_NONE|wx.BU_EXACTFIT)
      setPCButton.SetToolTip(wx.ToolTip("Set PC to current line"))
      self.gcodeToolBar.AddControl(setPCButton)      

      #self.gcodeToolBar.AddSimpleTool(gID_GoToPC, "Go to PC", wx.NullBitmap)
      goToPCButton = wx.Button (self.gcodeToolBar, gID_GoToPC, "Go to PC",
         style=wx.BORDER_NONE|wx.BU_EXACTFIT)
      goToPCButton.SetToolTip(wx.ToolTip("Show PC and follow it"))
      self.gcodeToolBar.AddControl(goToPCButton)      
      
      '''
      self.gcodeToolBar = wx.ToolBar(self, 
         style=wx.TB_HORIZONTAL |
         #wx.NO_BORDER |
         #wx.TB_FLAT
         #wx.TB_TEXT
      0)
      
      self.gcodeToolBar.SetToolBitmapSize(wx.Size(16, 16))
      
      self.gcodeToolBar.AddSimpleTool(gID_Run, imgPlay.GetBitmap(), "Run\tF5")
      #self.gcodeToolBar.AddControl(wx.StaticText(self.gcodeToolBar, -1, 'Run'))
      self.gcodeToolBar.AddSimpleTool(gID_Step, imgNext.GetBitmap(), "Step")
      self.gcodeToolBar.AddSimpleTool(gID_Stop, imgStop.GetBitmap(), "Stop")
      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_BreakToggle, imgRecord.GetBitmap(), "Break Toggle\tF9")
      '''
      
      self.gcodeToolBar.Realize()

      self.aui_mgr.AddPane(self.gcodeToolBar, 
         aui.AuiPaneInfo().Caption("GCODE ToolBar").ToolbarPane().Top().Position(2))

      self.appToolBar.Refresh()
      self.gcodeToolBar.Refresh()
      
   def UpdateUI(self):
      self.cli.UpdateUI(self.appData)
      self.gcText.UpdateUI(self.appData)
      self.connectionPanel.UpdateUI(self.appData)
      self.machineStatusPanel.UpdateUI(self.appData)
      self.machineJoggingPanel.UpdateUI(self.appData)
      
      self.appToolBar.Refresh()
      self.appToolBar.Update()
      
      self.gcodeToolBar.Refresh()
      self.gcodeToolBar.Update()
      
      self.Refresh()
      self.Update()
      
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
            self.workThread = gcsWorkThread(self, self.serPort, self.mw2tQueue, 
               self.t2mwQueue, self.cliOptions)
               
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
      if self.workThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_EXIT, None))
         self.mw2tQueue.join()
      self.workThread = None
      self.serPort.close()
      
      self.appData.serialPortIsOpen = False
      self.GrblDetected = False
      self.UpdateUI()
      
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
            "The file dosen't exits.\n" \
            "File: %s\n\n" \
            "Please check the path and try again." % fileName, "", 
            wx.OK|wx.ICON_STOP)
         result = dlg.ShowModal()
         dlg.Destroy()
      
      self.gcText.SetReadOnly(True)

      
   def OnRun(self, e):
      if self.workThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_RUN, 
            [self.appData.gcodeFileLines, self.appData.programCounter, self.appData.breakPoints]))
         self.mw2tQueue.join()
         
         self.gcText.SetAutoScroll(True)
         self.gcText.GoToPC()
         self.appData.swState = gSTATE_RUN
         self.UpdateUI()
         
   def OnRunUpdate(self, e):
      if self.appData.fileIsOpen and \
         self.appData.serialPortIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         e.Enable(True)
         self.gcodeToolBar.EnableTool(gID_Run, True)
      else:
         e.Enable(False)
         self.gcodeToolBar.EnableTool(gID_Run, False)
         
   def OnBreakToggle(self, e):
      pc = self.gcText.GetCurrentLine()
      enable = False
      
      if pc in self.appData.breakPoints:
         self.appData.breakPoints.remove(pc)
      else:
         self.appData.breakPoints.add(pc)
         enable = True
      
      self.gcText.UpdateBreakPoint(pc, enable)
      
   def OnBreakToggleUpdate(self, e):
      if self.appData.fileIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         e.Enable(True)
         self.gcodeToolBar.EnableTool(gID_BreakToggle, True)
      else:
         e.Enable(False)
         self.gcodeToolBar.EnableTool(gID_BreakToggle, False)
         
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
         
   def OnStep(self, e):
      if self.workThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_STEP, 
            [self.appData.gcodeFileLines, self.appData.programCounter, self.appData.breakPoints]))
         self.mw2tQueue.join()
         
         self.appData.swState = gSTATE_STEP
         self.UpdateUI()

   def OnStepUpdate(self, e):
      if self.appData.fileIsOpen and \
         self.appData.serialPortIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         e.Enable(True)
         self.gcodeToolBar.EnableTool(gID_Step, True)
      else:
         e.Enable(False)
         self.gcodeToolBar.EnableTool(gID_Step, False)
      
   def OnStop(self, e):
      self.Stop()
      
   def OnStopUpdate(self, e):
      if self.appData.fileIsOpen and \
         self.appData.serialPortIsOpen and \
         self.appData.swState != gSTATE_IDLE and \
         self.appData.swState != gSTATE_BREAK:
         
         e.Enable(True)
         self.gcodeToolBar.EnableTool(gID_Stop, True)
      else:
         e.Enable(False)
         self.gcodeToolBar.EnableTool(gID_Stop, False)
         
   def OnSetPC(self, e):
      self.SetPC()
      
   def OnSetPCUpdate(self, e):
      if self.appData.fileIsOpen and \
         (self.appData.swState == gSTATE_IDLE or \
          self.appData.swState == gSTATE_BREAK):
          
         e.Enable(True)
         self.gcodeToolBar.EnableTool(gID_SetPC, True)
      else:
         e.Enable(False)
         self.gcodeToolBar.EnableTool(gID_SetPC, False)
      
   def OnGoToPC(self, e):
      self.gcText.SetAutoScroll(True)
      self.gcText.GoToPC()
      
   def OnGoToPCUpdate(self, e):
      if self.appData.fileIsOpen:
         e.Enable(True)
         self.gcodeToolBar.EnableTool(gID_GoToPC, True)
      else:
         e.Enable(False)
         self.gcodeToolBar.EnableTool(gID_GoToPC, False)
      

   def OnEnter(self, e):
      cliCommand = self.cli.GetCommand()

      if len(cliCommand) > 0:
         serialData = "%s\n" % (cliCommand)
         self.SerialWrite(serialData)

   def OnAbout(self, event):
      # First we create and fill the info object
      aboutDialog = wx.AboutDialogInfo()
      aboutDialog.Name = __appname__
      aboutDialog.Version = __version__
      aboutDialog.Copyright = __copyright__
      aboutDialog.Description = wordwrap(__description__, 350, wx.ClientDC(self))
      aboutDialog.WebSite = ("https://github.com/duembeg/gcs", "GCode Step home page")
      #aboutDialog.Developers = __authors__

      #aboutDialog.License = wordwrap(licenseText, 500, wx.ClientDC(self))

      # Then we call wx.AboutBox giving it that info object
      wx.AboutBox(aboutDialog)
      
   def OnClose(self, e):
      if self.workThread is not None:
         self.mw2tQueue.put(threadEvent(gEV_CMD_EXIT, None))
         self.mw2tQueue.join()

      self.cli.SaveConfig(self.configFile)
      self.aui_mgr.UnInit()
      self.Destroy()
      
   def Stop(self):
      if self.workThread is not None:
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

      if self.workThread is not None:
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
         self.outputTextctrl.AppendText(txtOutputData)
      
         if self.appData.swState == gSTATE_RUN:
            # if we are in run state let thread do teh writing
            if self.workThread is not None:
               self.mw2tQueue.put(threadEvent(gEV_CMD_SEND, serialData))
               self.mw2tQueue.join()
         else:
            self.serPort.write(serialData)
            
         # this won't work well is too  early, mechanical movement
         # say G01X300 might take a long time, but grbl will reutn almost
         # immediately with "ok"
         #if self.appData.machineStatusAutoRefresh and serialData != "?":
         #   self.serPort.write("?")

      elif self.cliOptions.verbose:
         print "gcsMainWindow ERROR: attempt serial write with port closed!!"
      
   """-------------------------------------------------------------------------
   Handle events coming form working thread 
   -------------------------------------------------------------------------"""
   def OnThreadEvent(self, e):
      while (not self.t2mwQueue.empty()):
         # get dat from queue
         te = self.t2mwQueue.get()
         
         if te.event_id == gEV_ABORT:
            if self.cliOptions.vverbose:
               print "gcsMainWindow got event gEV_ABORT."
            self.outputTextctrl.AppendText(te.data)
            self.workThread = None               
            self.SerialClose()
            
         elif te.event_id == gEV_DATA_IN:
            teData = te.data
            
            if self.cliOptions.vverbose:
               print "gcsMainWindow got event gEV_DATA_IN."
            self.outputTextctrl.AppendText("%s" % teData)
            

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
               if self.cliOptions.vverbose:
                  print "gcsMainWindow re.status.match %s" % str(statusData)
               self.machineStatusPanel.UpdateUI(self.appData, statusData)
               self.machineJoggingPanel.UpdateUI(self.appData, statusData)
            
         elif te.event_id == gEV_DATA_OUT:
            if self.cliOptions.vverbose:
               print "gcsMainWindow got event gEV_DATA_OUT."
            self.outputTextctrl.AppendText("> %s" % te.data)
            
         elif te.event_id == gEV_PC_UPDATE:
            if self.cliOptions.vverbose:
               print "gcsMainWindow got event gEV_PC_UPDATE [%s]." % str(te.data)
            self.SetPC(te.data)
            
         elif te.event_id == gEV_RUN_END:
            if self.cliOptions.vverbose:
               print "gcsMainWindow got event gEV_RUN_END."
            self.appData.swState = gSTATE_IDLE
            self.Refresh()
            self.UpdateUI()
            self.SetPC(0)
            
         elif te.event_id == gEV_STEP_END:
            if self.cliOptions.vverbose:
               print "gcsMainWindow got event gEV_STEP_END."
            self.appData.swState = gSTATE_IDLE
            self.UpdateUI()

         elif te.event_id == gEV_HIT_BRK_PT:
            if self.cliOptions.vverbose:
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
   gcsWorkThread:
   Threads that monitor serial port for new data and sends events to 
   main window.
----------------------------------------------------------------------------"""
class gcsWorkThread(threading.Thread):
   """Worker Thread Class."""
   def __init__(self, notify_window, serial, in_queue, out_queue, cli_options):
      """Init Worker Thread Class."""
      threading.Thread.__init__(self)

      # init local variables
      self.notifyWindow = notify_window
      self.serPort = serial
      self.mw2tQueue = in_queue
      self.t2mwQueue = out_queue
      self.cliOptions = cli_options
      
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
   Handle events coming form main Window
   -------------------------------------------------------------------------"""
   def ProcessQueue(self):
      # process events from queue ---------------------------------------------
      if not self.mw2tQueue.empty():
         # get item from queue
         e = self.mw2tQueue.get()
         
         if e.event_id == gEV_CMD_EXIT:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread got event gEV_CMD_EXIT."
            self.endThread = True
            self.swState = gSTATE_IDLE
            
         elif e.event_id == gEV_CMD_RUN:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread got event gEV_CMD_RUN, swState->gSTATE_RUN"
            self.gcodeDataLines = e.data[0]
            self.initialProgramCounter = e.data[1]
            self.workingProgramCounter = self.initialProgramCounter
            self.breakPointSet =  e.data[2]
            self.swState = gSTATE_RUN
            
         elif e.event_id == gEV_CMD_STEP:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread got event gEV_CMD_STEP, swState->gSTATE_STEP"
            self.gcodeDataLines = e.data[0]
            self.initialProgramCounter = e.data[1]
            self.workingProgramCounter = self.initialProgramCounter
            self.breakPointSet =  e.data[2]
            self.swState = gSTATE_STEP
            
         elif e.event_id == gEV_CMD_STOP:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread got event gEV_CMD_STOP, swState->gSTATE_IDLE"
               
            self.swState = gSTATE_IDLE
         
         elif e.event_id == gEV_CMD_SEND:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread got event gEV_CMD_SEND."
            self.SerialWrite(e.data)
            responseData = self.WaitForResponse()
            
         elif e.event_id == gEV_CMD_AUTO_STATUS:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread got event gEV_CMD_AUTO_STATUS."
            self.machineAutoStatus = e.data
         
         else:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread got unknown event!! [%s]." % str(e.event_id)
            
         # item qcknowledge
         self.mw2tQueue.task_done()
         
   def SerialWrite(self, serialData):
      # sent data to UI
      self.t2mwQueue.put(threadEvent(gEV_DATA_OUT, serialData))
      wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         
      # send command
      self.serPort.write(serialData)
         
      if self.cliOptions.verbose:
         print serialData.strip()

   def SerialRead(self):
      serialData = self.serPort.readline()
   
      if len(serialData) > 0:
         # add data to queue and signal main window to consume
         self.t2mwQueue.put(threadEvent(gEV_DATA_IN, serialData))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         
      if self.cliOptions.verbose:
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
         if self.cliOptions.vverbose:
            print "** gcsWorkThread reach last PC, swState->gSTATE_IDLE"
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
         if self.cliOptions.vverbose:
            print "** gcsWorkThread encounter breakpoint PC[%s], swState->gSTATE_BREAK" % \
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
         if self.cliOptions.vverbose:
            print "** gcsWorkThread reach last PC, swState->gSTATE_IDLE"
         return

      # update PC
      self.t2mwQueue.put(threadEvent(gEV_PC_UPDATE, self.workingProgramCounter))
      wx.PostEvent(self.notifyWindow, threadQueueEvent(None))      
      
      # end IDLE state
      if self.workingProgramCounter > self.initialProgramCounter:
         self.swState = gSTATE_IDLE
         self.t2mwQueue.put(threadEvent(gEV_STEP_END, None))
         wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
         if self.cliOptions.vverbose:
            print "** gcsWorkThread finish STEP cmd, swState->gSTATE_IDLE"            
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
      
      if self.cliOptions.vverbose:
         print "** gcsWorkThread start."
      
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
               print "** gcsWorkThread unexpected state [%d], moving back to IDLE." \
                  ", swState->gSTATE_IDLE " % (self.swState)
               self.ProcessIdleSate()
               self.swState = gSTATE_IDLE
         else:
            if self.cliOptions.vverbose:
               print "** gcsWorkThread unexpected serial port closed, ABORT."
         
            # add data to queue and signal main window to consume
            self.t2mwQueue.put(threadEvent(gEV_ABORT, "** Serial Port is close, thread terminating.\n"))
            wx.PostEvent(self.notifyWindow, threadQueueEvent(None))
            break
            
      if self.cliOptions.vverbose:
         print "** gcsWorkThread exit."

"""----------------------------------------------------------------------------
   start here:
   Python script start up code.
----------------------------------------------------------------------------"""
if __name__ == '__main__':
   
   (cli_options, cli_args) = get_cli_params()

   app = wx.App(0)
   gcsMainWindow(None, title=__appname__, cli_options=cli_options)
   app.MainLoop()
