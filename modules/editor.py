"""----------------------------------------------------------------------------
   editor.py

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

import os
import re
import wx
from wx import stc as stc
from wx.lib import scrolledpanel as scrolled
from wx.lib import colourselect as  csel

import modules.config as gc


def hex_to_rgb(hex_color):
   m = re.match(r'^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$',
      hex_color, re.IGNORECASE)
   return (int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16))

"""----------------------------------------------------------------------------
   gsatStyledTextCtrlSettingsPanel:
   Program settings.
----------------------------------------------------------------------------"""
class gsatStyledTextCtrlSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, config_data, key, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = config_data
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
      foregroundColorSizer = wx.GridSizer(1,6,0,0)
      backgroundColorSizer = wx.GridSizer(1,6,0,0)
      syntaxColorSizer = wx.GridSizer(2,6,0,0)

      # Foreground
      text = wx.StaticText(self, label="Foreground:")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

      text = wx.StaticText(self, label="Window")
      foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      self.windowForeground = csel.ColourSelect(self, -1, "",
         hex_to_rgb(self.configData.Get('/%s/WindowForeground' % self.key)))
      foregroundColorSizer.Add(self.windowForeground, 0,
         flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

      text = wx.StaticText(self, label="Line Numbers")
      foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      self.lineNumbersForeground = csel.ColourSelect(self, -1, "",
         hex_to_rgb(self.configData.Get('/%s/LineNumberForeground' % self.key)))
      foregroundColorSizer.Add(self.lineNumbersForeground, 0,
         flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

      text = wx.StaticText(self, label="Highlight Line")
      foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      self.caretLineForeground = csel.ColourSelect(self, -1, "",
         hex_to_rgb(self.configData.Get('/%s/CaretLineForeground' % self.key)))
      foregroundColorSizer.Add(self.caretLineForeground, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

      vColorSizer.Add(foregroundColorSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      # Background
      text = wx.StaticText(self, label="")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)
      text = wx.StaticText(self, label="Background:")
      vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

      text = wx.StaticText(self, label="Window")
      backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      self.windowBackground = csel.ColourSelect(self, -1, "",
         hex_to_rgb(self.configData.Get('/%s/WindowBackground' % self.key)))
      backgroundColorSizer.Add(self.windowBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

      text = wx.StaticText(self, label="Line Numbers")
      backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      self.lineNumbersBackground = csel.ColourSelect(self, -1, "",
         hex_to_rgb(self.configData.Get('/%s/LineNumberBackground' % self.key)))
      backgroundColorSizer.Add(self.lineNumbersBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)


      text = wx.StaticText(self, label="Highlight Line")
      backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
      self.caretLineBackground = csel.ColourSelect(self, -1, "",
         hex_to_rgb(self.configData.Get('/%s/CaretLineBackground' % self.key)))
      backgroundColorSizer.Add(self.caretLineBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

      vColorSizer.Add(backgroundColorSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      if self.key == 'code':
         # Syntax highlighting
         text = wx.StaticText(self, label="")
         vColorSizer.Add(text, 0, flag=wx.ALL, border=5)
         text = wx.StaticText(self, label="Syntax highlighting:")
         vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

         text = wx.StaticText(self, label="G Codes")
         syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
         self.gCodeHighlight = csel.ColourSelect(self, -1, "",
            hex_to_rgb(self.configData.Get('/%s/GCodeHighlight' % self.key)))
         syntaxColorSizer.Add(self.gCodeHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)


         text = wx.StaticText(self, label="Axis Codes")
         syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
         self.axisHighlight = csel.ColourSelect(self, -1, "",
            hex_to_rgb(self.configData.Get('/%s/AxisHighlight' % self.key)))
         syntaxColorSizer.Add(self.axisHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)


         text = wx.StaticText(self, label="Parameters")
         syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
         self.parametersHighlight = csel.ColourSelect(self, -1, "",
            hex_to_rgb(self.configData.Get('/%s/ParametersHighlight' % self.key)))
         syntaxColorSizer.Add(self.parametersHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

         text = wx.StaticText(self, label="Comments")
         syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
         self.commentsHighlight = csel.ColourSelect(self, -1, "",
            hex_to_rgb(self.configData.Get('/%s/CommentsHighlight' % self.key)))
         syntaxColorSizer.Add(self.commentsHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

         text = wx.StaticText(self, label="G-Code Line #")
         syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
         self.gCodeLineNumberHighlight = csel.ColourSelect(self, -1, "",
            hex_to_rgb(self.configData.Get('/%s/GCodeLineNumberHighlight' % self.key)))
         syntaxColorSizer.Add(self.gCodeLineNumberHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT)

         vColorSizer.Add(syntaxColorSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)


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

      if self.key == 'code':
         self.configData.Set('/%s/GCodeHighlight' % self.key,
            self.gCodeHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

         self.configData.Set('/%s/AxisHighlight' % self.key,
            self.axisHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

         self.configData.Set('/%s/ParametersHighlight' % self.key,
            self.parametersHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

         self.configData.Set('/%s/CommentsHighlight' % self.key,
            self.commentsHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

         self.configData.Set('/%s/GCodeLineNumberHighlight' % self.key,
            self.gCodeLineNumberHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

"""----------------------------------------------------------------------------
   gsatStcStyledTextCtrl:
   Text control to display data
----------------------------------------------------------------------------"""
class gsatStcStyledTextCtrl(stc.StyledTextCtrl):
   def __init__(self, parent, config_data, state_data, id=wx.ID_ANY, pos=wx.DefaultPosition,
      size=wx.DefaultSize, style=0, name=stc.STCNameStr):

      stc.StyledTextCtrl.__init__(self, parent, id, pos, size,
         style, name)

      self.configData = config_data
      self.stateData = state_data
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

   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.InitConfig()
      self.InitUI()
      self.GotoLine(self.GetCurrentLine())

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

   def FindFirstText(self, text):
      lastLine = self.GetLineCount()
      endPos = self.GetLineEndPosition(lastLine)
      pos = self.FindText(0, endPos, text)

      if pos > 0:
         self.GotoPos(pos+len(text))
         self.SetSelection(pos,pos+len(text))

   def FindNextText(self, text):
      begPos = self.GetCurrentPos()
      lastLine = self.GetLineCount()
      endPos = self.GetLineEndPosition(lastLine)
      pos = self.FindText(begPos, endPos, text)

      if pos > 0:
         self.GotoPos(pos+len(text))
         self.SetSelection(pos,pos+len(text))

   def GotoLine(self, line):
      lines = self.GetLineCount()

      if line > lines:
         line = lines

      if line < 0:
         line = 0

      self.MarkerDeleteAll(self.markerCaretLine)

      if self.configCaretLine:
         self.MarkerAdd(line, self.markerCaretLine)

      stc.StyledTextCtrl.GotoLine(self, line)

   def ScrollToEnd(self):
      line = self.GetLineCount() - 1
      self.GotoLine(line)
      #self.ScrollToLine(self.GetLineCount())

"""----------------------------------------------------------------------------
   gsatGcodeStcStyledTextCtrl:
   Text control to display GCODE
----------------------------------------------------------------------------"""
class gsatGcodeStcStyledTextCtrl(gsatStcStyledTextCtrl):
   def __init__(self, parent, config_data, state_data, id=wx.ID_ANY, pos=wx.DefaultPosition,
      size=wx.DefaultSize, style=0, name=stc.STCNameStr):

      gsatStcStyledTextCtrl.__init__(self, parent, config_data, state_data, id, pos, size,
         style, name)

      self.InitConfig()
      self.InitUI()

   def InitConfig(self):
      self.configReadOnly                 = self.configData.Get('/code/ReadOnly')
      self.configAutoScroll               = self.configData.Get('/code/AutoScroll')
      self.configWindowForeground         = self.configData.Get('/code/WindowForeground')
      self.configWindowBackground         = self.configData.Get('/code/WindowBackground')
      self.configLineNumber               = self.configData.Get('/code/LineNumber')
      self.configLineNumberForeground     = self.configData.Get('/code/LineNumberForeground')
      self.configLineNumberBackground     = self.configData.Get('/code/LineNumberBackground')
      self.configCaretLine                = self.configData.Get('/code/CaretLine')
      self.configCaretLineForeground      = self.configData.Get('/code/CaretLineForeground')
      self.configCaretLineBackground      = self.configData.Get('/code/CaretLineBackground')
      self.configGCodeHighlight           = self.configData.Get('/code/GCodeHighlight')
      self.configAxisHighlight            = self.configData.Get('/code/AxisHighlight')
      self.configParametersHighlight      = self.configData.Get('/code/ParametersHighlight')
      self.configGCodeLineNumberHighlight = self.configData.Get('/code/GCodeLineNumberHighlight')
      self.configCommentsHighlight        = self.configData.Get('/code/CommentsHighlight')


      self.SetReadOnly(self.configReadOnly)

      if (self.configAutoScroll == 1) or (self.configAutoScroll == 2) or (self.configAutoScroll == 3):
         self.autoScroll = True

   def InitUI(self):

      # global default style
      if wx.Platform == '__WXMSW__':
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,bold,face:Courier New"\
         % (self.configWindowForeground, self.configWindowBackground))
      elif wx.Platform == '__WXMAC__':
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,bold,face:Monaco"\
            % (self.configWindowForeground, self.configWindowBackground))
      else:
         defsize = wx.SystemSettings.GetFont(wx.SYS_ANSI_FIXED_FONT).GetPointSize()
         self.StyleSetSpec(stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,bold,face:Courier,size:%d"\
            % (self.configWindowForeground, self.configWindowBackground, defsize))

      self.StyleClearAll()

      self.StyleSetSpec(stc.STC_STYLE_LINENUMBER, "fore:%s,back:%s,bold"\
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


      self.SetLexer(stc.STC_LEX_CONTAINER)

      self.Bind(stc.EVT_STC_STYLENEEDED, self.onStyleNeeded)

      # g-code
      self.StyleSetSpec(stc.STC_P_OPERATOR, "fore:%s" % self.configGCodeHighlight)
      self.reGCode = re.compile(r'[GM]\d+\.{0,1}\d*', re.IGNORECASE)

      # axis
      self.StyleSetSpec(stc.STC_P_WORD, "fore:%s" % self.configAxisHighlight)
      self.reAxis = re.compile(r'([ABCIJKUVWXYZ])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

      # parameters
      self.StyleSetSpec(stc.STC_P_WORD2, "fore:%s" % self.configParametersHighlight)
      self.reParams = re.compile(r'([DEFHLOPQRST])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

      # g-code line number
      self.StyleSetSpec(stc.STC_P_IDENTIFIER, "fore:%s" % self.configGCodeLineNumberHighlight)
      self.reLineNumber = re.compile(r'N\d+', re.IGNORECASE)

      # comments
      self.StyleSetSpec(stc.STC_P_COMMENTLINE, "fore:%s" % self.configCommentsHighlight)
      self.reComments = []
      self.reComments.append(re.compile(r'\(.*\)'))
      self.reComments.append(re.compile(r';.*'))

   def onStyleNeeded(self, e):
      stStart = self.GetEndStyled()    # this is the first character that needs styling
      stEnd = e.GetPosition()          # this is the last character that needs styling
      stData = self.GetTextRange(stStart, stEnd)

      # need to do styling on line, make sure we don't get stock on a loop
      # if the first char to style is a new line, getting line form pos will
      # always return the same line. Nex styling car will always be the
      # end of line char.
      if stData[0] == "\n":
         stStart = stStart + 1

      stLine = self.LineFromPosition(stStart)
      stStart = self.PositionFromLine(stLine)
      stData = self.GetTextRange(stStart, stEnd)


      #print stStart, stEnd, stLine

      # start with default (revert to default, if text gets modify)
      self.StartStyling(stStart, 31)   # in this example, only style the text style bits
      self.SetStyling(len(stData), stc.STC_P_DEFAULT)

      # match gcodes
      mArray = self.reGCode.finditer(stData)

      for m in mArray:
         self.StartStyling(stStart+m.start(0), 31)   # in this example, only style the text style bits
         self.SetStyling(m.end(0)-m.start(0), stc.STC_P_OPERATOR)

      # match line number
      mArray = self.reLineNumber.finditer(stData)

      for m in mArray:
         self.StartStyling(stStart+m.start(0), 31)   # in this example, only style the text style bits
         self.SetStyling(m.end(0)-m.start(0), stc.STC_P_IDENTIFIER)

      # match paramters
      mArray = self.reParams.finditer(stData)

      for m in mArray:
         self.StartStyling(stStart+m.start(1), 31)   # in this example, only style the text style bits
         self.SetStyling(m.end(1)-m.start(1), stc.STC_P_WORD2)

      # match axis
      mArray = self.reAxis.finditer(stData)

      for m in mArray:
         self.StartStyling(stStart+m.start(1), 31)   # in this example, only style the text style bits
         self.SetStyling(m.end(1)-m.start(1), stc.STC_P_WORD)

      # match comments or skip code
      # *** must be last to catch any keywords or numbers in commnets
      for regex in self.reComments:
         mArray = regex.finditer(stData)

         for m in mArray:
            self.StartStyling(stStart+m.start(0), 31)   # in this example, only style the text style bits
            self.SetStyling(m.end(0)-m.start(0), stc.STC_P_COMMENTLINE)


   def UpdateUI(self, stateData):
      self.stateData = stateData

      if (self.stateData.swState == gc.gSTATE_IDLE or \
          self.stateData.swState == gc.gSTATE_BREAK):

         self.SetReadOnly(self.configReadOnly)
      else:
         # cannot update while we are on a non-IDLE state
         self.SetReadOnly(True)

   def UpdatePC(self, pc):
      if pc > -1:
         self.MarkerDeleteAll(self.markerPC)
         self.handlePC = self.MarkerAdd(pc, self.markerPC)

         if self.autoScroll:
            self.GotoLine(pc)

   def GoToPC(self):
      pc = self.MarkerLineFromHandle(self.handlePC)

      if self.configAutoScroll == 3:
         self.autoScroll = True

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
