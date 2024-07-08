"""----------------------------------------------------------------------------
   wnd_editor.py

   Copyright (C) 2013 Wilhelm Duembeg

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
import re
import wx
from wx import stc as stc
import string

import modules.config as gc


def hex_to_rgb(hex_color):
    m = re.match(r'^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$',
                 hex_color, re.IGNORECASE)
    return (int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16))


class gsatStcStyledTextCtrl(stc.StyledTextCtrl):
    """
    gsatStcStyledTextCtrl:

    Text control to display data

    """

    def __init__(self, parent, config_data, state_data, id=wx.ID_ANY,
                 pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
                 name=stc.STCNameStr):

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
        self.configReadOnly = self.configData.get('/output/ReadOnly')
        self.configAutoScroll = self.configData.get('/output/AutoScroll')
        self.configWindowForeground = self.configData.get('/output/WindowForeground')
        self.configWindowBackground = self.configData.get('/output/WindowBackground')
        self.configLineNumber = self.configData.get('/output/LineNumber')
        self.configLineNumberForeground = self.configData.get('/output/LineNumberForeground')
        self.configLineNumberBackground = self.configData.get('/output/LineNumberBackground')
        self.configCaretLine = self.configData.get('/output/CaretLine')
        self.configCaretLineForeground = self.configData.get('/output/CaretLineForeground')
        self.configCaretLineBackground = self.configData.get('/output/CaretLineBackground')

        self.configFontFace = self.configData.get('/output/FontFace')
        self.configFontSize = self.configData.get('/output/FontSize')
        self.configFontStyle = self.configData.get('/output/FontStyle')

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
        if self.configFontFace == "System" or self.configFontSize == -1:
            sysFont = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
            sysFont.SetNativeFontInfoUserDesc("Monospace 11")
            self.configFontFace = sysFont.GetFaceName()
            self.configFontSize = sysFont.GetPointSize()
            self.configFontStyle = "normal"
            self.configData.set('/output/FontFace', self.configFontFace)
            self.configData.set('/output/FontSize', self.configFontSize)
            self.configData.set('/output/FontStyle', self.configFontStyle)

        '''
        # global default style
        if wx.Platform == '__WXMSW__':
            self.StyleSetSpec(
                stc.STC_STYLE_DEFAULT,
                "fore:%s,back:%s,bold,face:Courier New,size:%d" % (
                    self.configWindowForeground, self.configWindowBackground,
                    self.configFontSize))

        elif wx.Platform == '__WXMAC__':
            self.StyleSetSpec(
                stc.STC_STYLE_DEFAULT,
                "fore:%s,back:%s,bold,face:Monaco,size:%d" % (
                    self.configWindowForeground, self.configWindowBackground,
                    self.configFontSize))
        else:
            defsize = wx.SystemSettings.GetFont(
                wx.SYS_ANSI_FIXED_FONT).GetPointSize()
        '''
        self.StyleResetDefault()

        self.StyleSetSpec(
            stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,%s,face:%s,size:%d" % (
                self.configWindowForeground, self.configWindowBackground,
                self.configFontStyle, self.configFontFace, self.configFontSize))

        self.StyleClearAll()

        self.StyleSetSpec(
            stc.STC_STYLE_LINENUMBER, "fore:%s,back:%s" %
            (self.configLineNumberForeground, self.configLineNumberBackground))

        # margin 0 for line numbers
        if self.configLineNumber:
            self.SetMarginType(0, stc.STC_MARGIN_NUMBER)
            self.SetMarginWidth(0, 50)
        else:
            self.SetMarginType(0, stc.STC_MARGIN_SYMBOL)
            self.SetMarginWidth(0, 1)

        # define markers
        self.markerCaretLine = 2
        self.MarkerDefine(
            self.markerCaretLine, stc.STC_MARK_ROUNDRECT, self.configCaretLineForeground,
            self.configCaretLineBackground)

        # disable two other margins
        self.SetMarginMask(1, pow(2, 0))
        self.SetMarginMask(2, pow(2, 1))

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

    def AppendText(self, data):
        readOnly = self.GetReadOnly()
        self.SetReadOnly(False)

        try:
            stc.StyledTextCtrl.AppendText(self, data)

        except:
            # sometimes there are utf_8 exceptions specially when
            # recovering from bad connection

            # Clean up string to only printable chars and try again
            try:
                filtered_string = filter(lambda x: x in string.printable, data)
                stc.StyledTextCtrl.AppendText(self, filtered_string)
            except:
                pass

        self.SetReadOnly(readOnly)

        if self.autoScroll:
            wx.CallAfter(self.ScrollToEnd)

    def FindFirstText(self, text):
        lastLine = self.GetLineCount()
        endPos = self.GetLineEndPosition(lastLine)
        pos = self.FindText(0, endPos, text)

        if pos > 0:
            self.GotoPos(pos+len(text))
            self.SetSelection(pos, pos+len(text))

    def FindNextText(self, text):
        begPos = self.GetCurrentPos()
        lastLine = self.GetLineCount()
        endPos = self.GetLineEndPosition(lastLine)
        pos = self.FindText(begPos, endPos, text)

        if pos > 0:
            self.GotoPos(pos+len(text))
            self.SetSelection(pos, pos+len(text))

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
        # self.ScrollToLine(self.GetLineCount())


"""----------------------------------------------------------------------------
   gsatGcodeStcStyledTextCtrl:
   Text control to display GCODE
----------------------------------------------------------------------------"""


class gsatGcodeStcStyledTextCtrl(gsatStcStyledTextCtrl):
    def __init__(self, parent, config_data, state_data, id=wx.ID_ANY,
                 pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
                 name=stc.STCNameStr):

        gsatStcStyledTextCtrl.__init__(
            self, parent, config_data, state_data, id, pos, size, style, name)

        self.breakPoints = set()

        self.InitConfig()
        self.InitUI()

    def InitConfig(self):
        self.configReadOnly = self.configData.get('/code/ReadOnly')
        self.configAutoScroll = self.configData.get('/code/AutoScroll')
        self.configWindowForeground = self.configData.get('/code/WindowForeground')
        self.configWindowBackground = self.configData.get('/code/WindowBackground')
        self.configLineNumber = self.configData.get('/code/LineNumber')
        self.configLineNumberForeground = self.configData.get('/code/LineNumberForeground')
        self.configLineNumberBackground = self.configData.get('/code/LineNumberBackground')
        self.configCaretLine = self.configData.get('/code/CaretLine')
        self.configCaretLineForeground = self.configData.get('/code/CaretLineForeground')
        self.configCaretLineBackground = self.configData.get('/code/CaretLineBackground')
        self.configGCodeHighlight = self.configData.get('/code/GCodeHighlight')
        self.configMCodeHighlight = self.configData.get('/code/MCodeHighlight')
        self.configAxisHighlight = self.configData.get('/code/AxisHighlight')
        self.configParametersHighlight = self.configData.get('/code/ParametersHighlight')
        self.configParameters2Highlight = self.configData.get('/code/Parameters2Highlight')
        self.configGCodeLineNumberHighlight = self.configData.get('/code/GCodeLineNumberHighlight')
        self.configCommentsHighlight = self.configData.get('/code/CommentsHighlight')

        self.configFontFace = self.configData.get('/code/FontFace')
        self.configFontSize = self.configData.get('/code/FontSize')
        self.configFontStyle = self.configData.get('/code/FontStyle')

        self.SetReadOnly(self.configReadOnly)

        if (self.configAutoScroll == 1) or (self.configAutoScroll == 2) or (self.configAutoScroll == 3):
            self.autoScroll = True

    def InitUI(self):
        if self.configFontFace == "System" or self.configFontSize == -1:
            sysFont = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
            sysFont.SetNativeFontInfoUserDesc("Monospace bold 11")
            self.configFontFace = sysFont.GetFaceName()
            self.configFontSize = sysFont.GetPointSize()
            self.configFontStyle = "normal"
            self.configData.set('/code/FontFace', self.configFontFace)
            self.configData.set('/code/FontSize', self.configFontSize)
            self.configData.set('/code/FontStyle', self.configFontStyle)

        self.Bind(wx.stc.EVT_STC_MARGINCLICK, self.OnMarginClick)

        '''
        # global default style
        if wx.Platform == '__WXMSW__':
            self.StyleSetSpec(
                stc.STC_STYLE_DEFAULT,
                "fore:%s,back:%s,bold,face:Courier New,size:%d" % (
                    self.configWindowForeground, self.configWindowBackground,
                    self.configFontSize))

        elif wx.Platform == '__WXMAC__':
            self.StyleSetSpec(
                stc.STC_STYLE_DEFAULT,
                "fore:%s,back:%s,bold,face:Monaco,size:%d" % (
                    self.configWindowForeground, self.configWindowBackground,
                    self.configFontSize))
        else:
            defsize = wx.SystemSettings.GetFont(
                wx.SYS_ANSI_FIXED_FONT).GetPointSize()
        '''
        self.StyleResetDefault()

        self.StyleSetSpec(
            stc.STC_STYLE_DEFAULT, "fore:%s,back:%s,%s,face:%s,size:%d" % (
                self.configWindowForeground, self.configWindowBackground,
                self.configFontStyle, self.configFontFace, self.configFontSize))

        self.StyleClearAll()

        self.StyleSetSpec(
            stc.STC_STYLE_LINENUMBER, "fore:%s,back:%s,bold" % (
                self.configLineNumberForeground,
                self.configLineNumberBackground))

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
        self.SetMarginSensitive(1, True)

        # margin 2 for markers
        self.SetMarginType(2, stc.STC_MARGIN_SYMBOL)
        self.SetMarginWidth(2, 16)

        # define markers
        self.markerPC = 0
        self.markerBreakpoint = 1
        self.markerCaretLine = 2
        self.MarkerDefine(self.markerPC, stc.STC_MARK_ARROW, "BLACK", "GREEN")
        self.MarkerDefine(self.markerBreakpoint, stc.STC_MARK_CIRCLE, "BLACK", "RED")
        self.MarkerDefine(
            self.markerCaretLine, stc.STC_MARK_ROUNDRECT, self.configCaretLineForeground,
            self.configCaretLineBackground)

        self.SetMarginMask(1, pow(2, self.markerBreakpoint))
        self.SetMarginMask(2, pow(2, self.markerPC))

        self.SetLexer(stc.STC_LEX_CONTAINER)

        self.Bind(stc.EVT_STC_STYLENEEDED, self.onStyleNeeded)

        # g-code
        self.StyleSetSpec(stc.STC_P_OPERATOR, "fore:%s" % self.configGCodeHighlight)
        self.reGCode = re.compile(r'[G]\d+\.{0,1}\d*', re.IGNORECASE)

        # m-code
        self.StyleSetSpec(stc.STC_P_CLASSNAME, "fore:%s" % self.configMCodeHighlight)
        self.reMCode = re.compile(r'[M]\d+\.{0,1}\d*', re.IGNORECASE)

        # axis
        self.StyleSetSpec(stc.STC_P_WORD, "fore:%s" % self.configAxisHighlight)
        self.reAxis = re.compile(r'([ABCIJKUVWXYZ])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

        # parameters
        self.StyleSetSpec(stc.STC_P_WORD2, "fore:%s" % self.configParametersHighlight)
        self.reParams = re.compile(r'([DEFHLOPQRST])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

        # parameters 2
        self.StyleSetSpec(stc.STC_P_DEFNAME, "fore:%s" % self.configParameters2Highlight)
        self.reParams2 = re.compile(r'([EF])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

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

        # print stStart, stEnd, stLine

        # start with default (revert to default, if text gets modify)
        # in this example, only style the text style bits
        self.StartStyling(stStart)
        self.SetStyling(len(stData), stc.STC_P_DEFAULT)

        # match gcodes
        mArray = self.reGCode.finditer(stData)

        for m in mArray:
            # in this example, only style the text style bits
            self.StartStyling(stStart+m.start(0))
            self.SetStyling(m.end(0)-m.start(0), stc.STC_P_OPERATOR)

        # match mcodes
        mArray = self.reMCode.finditer(stData)

        for m in mArray:
            # in this example, only style the text style bits
            self.StartStyling(stStart+m.start(0))
            self.SetStyling(m.end(0)-m.start(0), stc.STC_P_CLASSNAME)

        # match line number
        mArray = self.reLineNumber.finditer(stData)

        for m in mArray:
            # in this example, only style the text style bits
            self.StartStyling(stStart+m.start(0))
            self.SetStyling(m.end(0)-m.start(0), stc.STC_P_IDENTIFIER)

        # match parameters
        mArray = self.reParams.finditer(stData)

        for m in mArray:
            # in this example, only style the text style bits
            self.StartStyling(stStart+m.start(1))
            self.SetStyling(m.end(1)-m.start(1), stc.STC_P_WORD2)

        mArray = self.reParams2.finditer(stData)

        for m in mArray:
            # in this example, only style the text style bits
            self.StartStyling(stStart+m.start(0))
            self.SetStyling(m.end(0)-m.start(0), stc.STC_P_DEFNAME)

        # match axis
        mArray = self.reAxis.finditer(stData)

        for m in mArray:
            # in this example, only style the text style bits
            self.StartStyling(stStart+m.start(1))
            self.SetStyling(m.end(1)-m.start(1), stc.STC_P_WORD)

        # match comments or skip code
        # *** must be last to catch any keywords or numbers in comments
        for regex in self.reComments:
            mArray = regex.finditer(stData)

            for m in mArray:
                # in this example, only style the text style bits
                self.StartStyling(stStart+m.start(0))
                self.SetStyling(m.end(0)-m.start(0), stc.STC_P_COMMENTLINE)

    def UpdateUI(self, stateData):
        self.stateData = stateData

        if (self.stateData.swState == gc.STATE_IDLE or
           self.stateData.swState == gc.STATE_BREAK or
           self.stateData.swState == gc.STATE_PAUSE):

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

    def GetBreakPoints(self):
        return self.breakPoints

    def DeleteAllBreakPoints(self):
        self.MarkerDeleteAll(self.markerBreakpoint)
        self.breakPoints = set()

    def UpdateBreakPoint(self, pc, enable):
        if enable:
            self.MarkerAdd(pc, self.markerBreakpoint)
            self.breakPoints.add(pc)
        else:
            self.MarkerDelete(pc, self.markerBreakpoint)
            self.breakPoints.remove(pc)

    def ToggleBreakPoint(self, pc):
        markerBits = self.MarkerGet(pc)
        if (markerBits & pow(2, self.markerBreakpoint)):
            self.MarkerDelete(pc, self.markerBreakpoint)
            self.breakPoints.remove(pc)
        else:
            self.MarkerAdd(pc, self.markerBreakpoint)
            self.breakPoints.add(pc)

    def OnMarginClick(self, evt):
        if evt.GetMargin() == self.markerBreakpoint:
            line_clicked = self.LineFromPosition(evt.GetPosition())
            self.ToggleBreakPoint(line_clicked)
