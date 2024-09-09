"""----------------------------------------------------------------------------
    wnd_console.py

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


class gsatStcStyledConsoleCtrl(stc.StyledTextCtrl):
    """
    gsatStcStyledConsoleCtrl:

    Text control to display data

    """

    def __init__(
            self, parent, config_data, state_data, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
            name=stc.STCNameStr):

        stc.StyledTextCtrl.__init__(self, parent, id, pos, size, style, name)

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

        if pos[0] > 0:
            self.GotoPos(pos[0])
            self.SetSelection(pos[0], pos[1])

    def FindNextText(self, text):
        begPos = self.GetCurrentPos()
        lastLine = self.GetLineCount()
        endPos = self.GetLineEndPosition(lastLine)
        pos = self.FindText(begPos, endPos, text)

        if pos[0] > 0:
            self.GotoPos(pos[0])
            self.SetSelection(pos[0], pos[1])

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


class gsatConsoleCtrl(wx.Window):
    """
    ConsoleCtrl:

    """

    def __init__(self, parent, config_data, state_data, cmd_line_options, **args):
        wx.Window.__init__(self, parent, **args)

        self.mainWindow = parent

        self.configData = config_data
        self.stateData = state_data
        self.cmdLineOptions = cmd_line_options

        self.InitConfig()
        self.InitUI()
        self.SetInitialSize()

        self.cliCommand = ""
        self.cliIndex = 0

        self.LoadCli()

    def InitConfig(self):
        # cli data
        self.cliSaveCmdHistory = self.configData.get('/cli/SaveCmdHistory')
        self.cliCmdMaxHistory = self.configData.get('/cli/CmdMaxHistory')
        self.cliCmdHistory = self.configData.get('/cli/CmdHistory')

    def UpdateSettings(self, config_data):
        self.configData = config_data
        self.InitConfig()

    def InitUI(self):
        vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # Add TerminalOutput
        self.outputText = gsatStcStyledConsoleCtrl(self, self.configData, self.stateData, style=wx.NO_BORDER)
        vPanelBoxSizer.Add(self.outputText, 1, wx.EXPAND | wx.ALL, border=0)

        # Add CLI
        self.cliComboBox = wx.adv.BitmapComboBox(self, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER | wx.WANTS_CHARS)
        self.cliComboBox.SetToolTip(wx.ToolTip("Command Line Interface (CLI)"))
        self.cliComboBox.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter)
        self.cliComboBox.Bind(wx.EVT_KEY_DOWN, self.OnCliKeyDown)
        vPanelBoxSizer.Add(self.cliComboBox, 0, wx.EXPAND | wx.ALL, border=0)

        # Finish up init UI
        self.SetSizer(vPanelBoxSizer)
        self.Layout()

    def AppendText(self, data):
        self.outputText.AppendText(data)

    def GetLoggingInterface(self):
        return self.outputText

    def OnCliEnter(self, e):
        if self.stateData.serialPortIsOpen and not (self.stateData.swState == gc.STATE_RUN):

            cliCommand = self.cliComboBox.GetValue()

            if cliCommand != self.cliCommand:
                if self.cliComboBox.GetCount() > self.cliCmdMaxHistory:
                    self.cliComboBox.Delete(0)

                self.cliCommand = cliCommand
                self.cliComboBox.Append(self.cliCommand)

            self.cliComboBox.SetValue("")

            self.cliIndex = self.cliComboBox.GetCount()

            self.mainWindow.eventForward2Machif(gc.EV_CMD_SEND, "".join([self.cliCommand, "\n"]))

        e.Skip()

    def OnCliKeyDown(self, e):
        keyCode = e.GetKeyCode()
        cliItems = self.cliComboBox.GetItems()

        if wx.WXK_UP == keyCode:
            if self.cliIndex > 0:
                self.cliIndex = self.cliIndex - 1
                self.cliComboBox.SetValue(cliItems[self.cliIndex])
        elif wx.WXK_DOWN == keyCode:
            if len(cliItems) > self.cliIndex + 1:
                self.cliIndex = self.cliIndex + 1
                self.cliComboBox.SetValue(cliItems[self.cliIndex])
        else:
            e.Skip()

    def LoadCli(self):
        # read cmd history
        configData = self.cliCmdHistory
        if len(configData) > 0:
            cliCommandHistory = configData.split("|")
            for cmd in cliCommandHistory:
                cmd = cmd.strip()
                if len(cmd) > 0:
                    self.cliComboBox.Append(cmd.strip())

            self.cliCommand = cliCommandHistory[len(cliCommandHistory) - 1]
            self.cliIndex = self.cliComboBox.GetCount()

    def SaveCli(self):
        # write cmd history
        if self.cliSaveCmdHistory:
            cliCmdHistory = self.cliComboBox.GetItems()
            if len(cliCmdHistory) > 0:
                cliCmdHistory = "|".join(cliCmdHistory)
                self.configData.set('/cli/CmdHistory', cliCmdHistory)
