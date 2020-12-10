"""----------------------------------------------------------------------------
   wnd_remote_config.py

   Copyright (C) 2013-2020 Wilhelm Duembeg

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

import wx
from wx.lib import scrolledpanel as scrolled

import images.icons as ico

class Factory():
    """ Factory class to init config page
    """

    @staticmethod
    def GetIcon():
        return ico.imgRemote.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatRemoteSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Remote")
        parent_wnd.SetPageImage(page, page)

        return settings_page

class gsatRemoteSettingsPanel(scrolled.ScrolledPanel):
    """ Remote settings
    """

    def __init__(self, parent, config_data, **args):
        super(gsatRemoteSettingsPanel, self).__init__(parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        # self.FitInside()

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)
        #gridSizer = wx.FlexGridSizer(7, 2)
        gridSizer = wx.GridBagSizer()

        row = 0
        # add hostname
        if not self.configData.get('/temp/RemoteServer', False):
            st = wx.StaticText(self, wx.ID_ANY, "Host name")
            self.host = wx.TextCtrl(self, -1, self.configData.get('/remote/Host', ""))
            self.host.SetToolTip(wx.ToolTip("Host name or ip address"))
            gridSizer.Add(st, pos=(row,0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
            gridSizer.Add(self.host, pos=(row,1), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
            row += 1

        # add TCP port
        st = wx.StaticText(self, wx.ID_ANY, "TCP port")
        self.tcpPort = wx.TextCtrl(self, -1, str(self.configData.get('/remote/TcpPort', "")))
        gridSizer.Add(st, pos=(row,0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        self.tcpPort.SetToolTip(wx.ToolTip("TCP network port"))
        gridSizer.Add(self.tcpPort, pos=(row,1), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        row += 1

        # add UDP port
        st = wx.StaticText(self, wx.ID_ANY, "UDP port")
        self.udpPort = wx.TextCtrl(self, -1, str(self.configData.get('/remote/UdpPort', "")))
        self.udpPort.SetToolTip(wx.ToolTip("UDP network port"))
        gridSizer.Add(st, pos=(row,0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self.udpPort, pos=(row,1), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        row += 1

        # Add UDP broadcast check box
        self.udpBroadcast = wx.CheckBox(self, wx.ID_ANY, "Enable UDP broadcast              ")
        self.udpBroadcast.SetValue(self.configData.get('/remote/UdpBroadcast', False))
        self.udpBroadcast.SetToolTip(wx.ToolTip("Use UDP to broadcast high rate updates from server"))
        gridSizer.Add(self.udpBroadcast, pos=(row,0), span=(1,2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        row += 1

        # Add UDP broadcast check box
        if not self.configData.get('/temp/RemoteServer', False):
            self.autoGcode = wx.CheckBox(self, wx.ID_ANY, "Auto G-code request")
            self.autoGcode.SetValue(self.configData.get('/remote/AutoGcodeRequest', False))
            self.autoGcode.SetToolTip(wx.ToolTip("Automatically ask for G-code from server upon connect"))
            gridSizer.Add(self.autoGcode, pos=(row,0), span=(1,2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            row += 1

        vBoxSizer.Add(gridSizer, 0, flag=wx.ALL | wx.EXPAND, border=20)
        self.SetSizer(vBoxSizer)

    def UpdateConfigData(self):
        if not self.configData.get('/temp/RemoteServer', False):
            self.configData.set('/remote/Host', self.host.GetValue())
            self.configData.set('/remote/AutoGcodeRequest', self.autoGcode.GetValue())
        self.configData.set('/remote/TcpPort', int(self.tcpPort.GetValue().strip()))
        self.configData.set('/remote/UdpPort', int(self.udpPort.GetValue().strip()))
        self.configData.set('/remote/UdpBroadcast', self.udpBroadcast.GetValue())



