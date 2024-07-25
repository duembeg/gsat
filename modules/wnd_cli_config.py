"""----------------------------------------------------------------------------
   wnd_cli_config.py

   Copyright (C) 2013 Wilhelm Duembeg

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
import wx
from wx.lib import scrolledpanel as scrolled

import images.icons as ico


class Factory():
    """
    Factory class to init config page

    """

    @staticmethod
    def GetIcon():
        return ico.imgCli.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        """
        Function to create and inti settings page

        """
        settings_page = gsatCliSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Cli")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatCliSettingsPanel(scrolled.ScrolledPanel):
    """
    CLI settings

    """

    def __init__(self, parent, config_data, **args):
        super(gsatCliSettingsPanel, self).__init__(parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        self.stateData = None
        self.keyboardJoggingEnable = False
        # self.FitInside()

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # Add check box
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cb = wx.CheckBox(self, wx.ID_ANY, "Save Command History")
        self.cb.SetValue(self.configData.get('/cli/SaveCmdHistory'))
        hBoxSizer.Add(self.cb, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, flag=wx.TOP | wx.LEFT, border=20)

        # Add spin ctrl
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sc = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.sc.SetRange(1, 1000)
        self.sc.SetValue(self.configData.get('/cli/CmdMaxHistory'))
        hBoxSizer.Add(self.sc, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "Max Command History")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)
        self.SetSizer(vBoxSizer)

    def UpdateConfigData(self):
        self.configData.set('/cli/SaveCmdHistory', self.cb.GetValue())
        self.configData.set('/cli/CmdMaxHistory', self.sc.GetValue())
