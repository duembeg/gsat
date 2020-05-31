"""----------------------------------------------------------------------------
   wnd_cli.py

   Copyright (C) 2013-2020 Wilhelm Duembeg

   This file is part of gsat. gsat is a cross-platform GCODE debug/step for
   grbl like GCODE interpreters. With features similar to software debuggers.
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
from wx.lib import scrolledpanel as scrolled
from wx.lib.agw import floatspin as fs

import modules.config as gc
import modules.machif_config as mi

import images.icons as ico

class gsatCliPanel(wx.ScrolledWindow):
    """ Comand Line Interface (CLI) controls for the machine.
    """
    def __init__(self, parent, config_data, state_data, **args):
        wx.ScrolledWindow.__init__(self, parent, **args)

        self.mainWindow = parent

        self.configData = config_data
        self.stateData = state_data

        self.cliCommand = ""
        self.cliIndex = 0

        self.InitConfig()
        self.InitUI()
        width, height = self.GetSizeTuple()
        scroll_unit = 10
        self.SetScrollbars(scroll_unit, scroll_unit, width /
                           scroll_unit, height/scroll_unit)

        self.UpdateSettings(self.configData)
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

        # Add CLI
        self.cliComboBox = wx.combo.BitmapComboBox(
            self, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER | wx.WANTS_CHARS)
        self.cliComboBox.SetToolTip(wx.ToolTip("Command Line Interface (CLI)"))
        self.cliComboBox.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter)
        self.cliComboBox.Bind(wx.EVT_KEY_DOWN, self.OnCliKeyDown)

        vPanelBoxSizer.Add(self.cliComboBox, 0, wx.EXPAND | wx.ALL, border=1)

        # Finish up init UI
        self.SetSizer(vPanelBoxSizer)
        self.Layout()

        #self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)
        #self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        #self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def UpdateUI(self, stateData, statusData=None):
        self.stateData = stateData

        if stateData.serialPortIsOpen and not stateData.swState == gc.STATE_RUN:
            self.cliComboBox.Enable()
        else:
            self.cliComboBox.Disable()

    def GetCliCommand(self):
        return self.cliCommand

    def OnCliEnter(self, e):
        cliCommand = self.cliComboBox.GetValue()

        if cliCommand != self.cliCommand:
            if self.cliComboBox.GetCount() > self.cliCmdMaxHistory:
                self.cliComboBox.Delete(0)

            self.cliCommand = cliCommand
            self.cliComboBox.Append(self.cliCommand)

        self.cliComboBox.SetValue("")

        self.cliIndex = self.cliComboBox.GetCount()

        self.mainWindow.eventForward2Machif(
            gc.EV_CMD_SEND, "".join([self.cliCommand, "\n"]))

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
        # read cmd hsitory
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

    def OnKeyUp(self, e):
        print "key up event"
        e.skip()

    def OnKeyDown(self, e):
        print "key down event"
        e.skip()

