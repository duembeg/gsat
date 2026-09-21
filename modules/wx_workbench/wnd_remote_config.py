"""----------------------------------------------------------------------------
    wnd_remote_config.py

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
import secrets
import string
import wx
from wx.lib import scrolledpanel as scrolled

import images.icons as ico
import modules.config as gc


class Factory():
    """
    Factory class to init config page

    """

    @staticmethod
    def GetIcon():
        return ico.imgRemote.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        """
        Function to create and inti settings page

        """
        settings_page = gsatRemoteSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Remote")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatRemoteSettingsPanel(scrolled.ScrolledPanel):
    """
    Remote settings

    """

    def __init__(self, parent, config_data, **args):
        super(gsatRemoteSettingsPanel, self).__init__(parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data
        self.remoteIndex = self.configData.get('/remotes/Index', 0)
        self.remoteInterface = self.configData.get(f'/remotes/remote{self.remoteIndex}/Interface', "websocket")

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        # self.FitInside()

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        # gridSizer = wx.FlexGridSizer(7, 2)
        gridSizer = wx.GridBagSizer(0, 0)

        row = 0

        if self.remoteInterface == "websocket":
            # add hostname
            if not self.configData.get('/temp/RemoteServer', False):
                st = wx.StaticText(self, wx.ID_ANY, "Host name")
                self.host = wx.TextCtrl(self, -1, self.configData.get(f'/remotes/remote{self.remoteIndex}/Host', ""))
                self.host.SetToolTip(wx.ToolTip("Host name or ip address"))
                gridSizer.Add(st, pos=(row, 0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
                gridSizer.Add(
                    self.host, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
                row += 1

            # add websocket port
            st = wx.StaticText(self, wx.ID_ANY, "WebSocket port")
            self.websocketPort = wx.TextCtrl(
                self, -1, str(self.configData.get(f'/remotes/remote{self.remoteIndex}/WebSocketPort', 61803)))
            self.websocketPort.SetToolTip(wx.ToolTip("WebSocket network port"))
            gridSizer.Add(st, pos=(row, 0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
            gridSizer.Add(self.websocketPort, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
            row += 1

            # Add api token
            st = wx.StaticText(self, wx.ID_ANY, "API token")
            self.apiToken = wx.TextCtrl(self, -1, self.configData.get(
                f'/remotes/remote{self.remoteIndex}/ApiToken', ""))
            self.apiToken.SetToolTip(wx.ToolTip("API token for server authentication"))
            button_size = self.apiToken.GetSize().height
            self.apiGenerate = wx.Button(self, label="G", size=(button_size, button_size))
            gridSizer.Add(st, pos=(row, 0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
            gridSizer.Add(self.apiToken, pos=(row, 1), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
            gridSizer.Add(self.apiGenerate, pos=(row, 2), flag=wx.ALIGN_CENTER_VERTICAL)

            # Bind the button click event
            self.apiGenerate.Bind(wx.EVT_BUTTON, self.OnApiGenerate)

            row += 1

            # Max Socket.IO / Engine.IO message size (large G-code Step/Run)
            # UI in MB; config stores bytes (1024-based MB).
            st = wx.StaticText(self, wx.ID_ANY, "Max message size (MB)")
            default_bytes = getattr(
                gc, "REMOTE_MAX_MESSAGE_BYTES_DEFAULT", 16 * 1024 * 1024)
            stored = self.configData.get(
                f'/remotes/remote{self.remoteIndex}/MaxMessageBytes',
                default_bytes)
            try:
                mb_val = gc.remote_message_bytes_to_mb(stored)
            except Exception:
                mb_val = float(getattr(gc, "REMOTE_MAX_MESSAGE_MB_DEFAULT", 16))
            if abs(mb_val - round(mb_val)) < 1e-9:
                mb_display = str(int(round(mb_val)))
            else:
                mb_display = f"{mb_val:g}"
            self.maxMessageMb = wx.TextCtrl(self, -1, mb_display)
            self.maxMessageMb.SetToolTip(wx.ToolTip(
                "Engine.IO / Socket.IO max message size in MB (default 16). "
                "gsat-server must use the same value; restart server after change. "
                "Allows first Step/Run of large G-code programs over WebSocket. "
                "Stored in config as bytes."))
            gridSizer.Add(st, pos=(row, 0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
            gridSizer.Add(
                self.maxMessageMb, pos=(row, 1), span=(1, 3),
                flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
            row += 1

            gridSizer.AddGrowableCol(1)

        else:
            # add hostname
            if not self.configData.get('/temp/RemoteServer', False):
                st = wx.StaticText(self, wx.ID_ANY, "Host name")
                self.host = wx.TextCtrl(self, -1, self.configData.get(f'/remotes/remote{self.remoteIndex}/Host', ""))
                self.host.SetToolTip(wx.ToolTip("Host name or ip address"))
                gridSizer.Add(st, pos=(row, 0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
                gridSizer.Add(self.host, pos=(row, 1), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
                row += 1

            # add TCP port
            st = wx.StaticText(self, wx.ID_ANY, "TCP port")
            self.tcpPort = wx.TextCtrl(self, -1, str(self.configData.get(
                f'/remotes/remote{self.remoteIndex}/TcpPort', "")))
            gridSizer.Add(st, pos=(row, 0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
            self.tcpPort.SetToolTip(wx.ToolTip("TCP network port"))
            gridSizer.Add(self.tcpPort, pos=(row, 1), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
            row += 1

            # add UDP port
            st = wx.StaticText(self, wx.ID_ANY, "UDP port")
            self.udpPort = wx.TextCtrl(self, -1, str(self.configData.get(
                f'/remotes/remote{self.remoteIndex}/UdpPort', "")))
            self.udpPort.SetToolTip(wx.ToolTip("UDP network port"))
            gridSizer.Add(st, pos=(row, 0), flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
            gridSizer.Add(self.udpPort, pos=(row, 1), flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
            row += 1

            # Add UDP broadcast check box
            self.udpBroadcast = wx.CheckBox(self, wx.ID_ANY, "Enable UDP broadcast              ")
            self.udpBroadcast.SetValue(self.configData.get(f'/remotes/remote{self.remoteIndex}/UdpBroadcast', False))
            self.udpBroadcast.SetToolTip(wx.ToolTip("Use UDP to broadcast high rate updates from server"))
            gridSizer.Add(self.udpBroadcast, pos=(row, 0), span=(1, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            row += 1

        # Add auto G-code request check box
        if not self.configData.get('/temp/RemoteServer', False):
            self.autoGcode = wx.CheckBox(self, wx.ID_ANY, "Auto G-code request")
            self.autoGcode.SetValue(self.configData.get(f'/remotes/remote{self.remoteIndex}/AutoGcodeRequest', False))
            self.autoGcode.SetToolTip(wx.ToolTip("Automatically ask for G-code from server upon connect"))
            gridSizer.Add(self.autoGcode, pos=(row, 0), span=(1, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            row += 1

        hBoxSizer.Add(gridSizer, 1, flag=wx.ALL | wx.EXPAND, border=20)

        st = wx.StaticText(self, -1, " ")
        hBoxSizer.Add(st, 1)

        vBoxSizer.Add(hBoxSizer, 1, flag=wx.ALL | wx.EXPAND, border=20)
        self.SetSizer(vBoxSizer)

    def OnApiGenerate(self, event):
        """
        Generate a secure API token of the specified length.

        """
        length = 16
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(length))

        self.apiToken.SetValue(token)

    def UpdateConfigData(self):
        if not self.configData.get('/temp/RemoteServer', False):
            self.configData.set(f'/remotes/remote{self.remoteIndex}/Host', self.host.GetValue())
            self.configData.set(f'/remotes/remote{self.remoteIndex}/AutoGcodeRequest', self.autoGcode.GetValue())
        if self.remoteInterface == "websocket":
            self.configData.set(
                f'/remotes/remote{self.remoteIndex}/WebSocketPort', int(self.websocketPort.GetValue().strip()))
            self.configData.set(f'/remotes/remote{self.remoteIndex}/ApiToken', self.apiToken.GetValue())
            max_b = gc.remote_message_mb_to_bytes(self.maxMessageMb.GetValue().strip())
            self.configData.set(
                f'/remotes/remote{self.remoteIndex}/MaxMessageBytes', max_b)
        elif self.remoteInterface == "socket":
            self.configData.set(f'/remotes/remote{self.remoteIndex}/TcpPort', int(self.tcpPort.GetValue().strip()))
            self.configData.set(f'/remotes/remote{self.remoteIndex}/UdpPort', int(self.udpPort.GetValue().strip()))
            self.configData.set(f'/remotes/remote{self.remoteIndex}/UdpBroadcast', self.udpBroadcast.GetValue())
        else:
            raise ValueError(f"Invalid remote interface: {self.remoteInterface}")
