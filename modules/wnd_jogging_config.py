"""----------------------------------------------------------------------------
   wnd_jogging_config.py

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
from wx.lib.agw import floatspin as fs


import images.icons as ico


class Factory():
    """
    Factory class to init config page

    """

    @staticmethod
    def GetIcon():
        return ico.imgMove.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatJoggingSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Jogging")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatJoggingSettingsPanel(scrolled.ScrolledPanel):
    """ Jog settings
    """
    def __init__(self, parent, config_data, **args):
        super(gsatJoggingSettingsPanel, self).__init__(parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        # self.FitInside()

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        text = wx.StaticText(self, label="General")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, flag=wx.ALL, border=5)

        # Add readonly check box
        self.cbXYZReadOnly = wx.CheckBox(
            self, wx.ID_ANY, "XYZ Read Only Status")
        self.cbXYZReadOnly.SetValue(
            self.configData.get('/jogging/XYZReadOnly'))
        self.cbXYZReadOnly.SetToolTip(
            wx.ToolTip("If enabled the XYZ fields in jogging status become "
                       "read only"))
        vBoxSizer.Add(self.cbXYZReadOnly, flag=wx.LEFT, border=20)

        # Add update from machine pos check box
        self.cbAutoMPOS = wx.CheckBox(
            self, wx.ID_ANY, "Auto update from machine position")
        self.cbAutoMPOS.SetValue(self.configData.get('/jogging/AutoMPOS'))
        self.cbAutoMPOS.SetToolTip(
            wx.ToolTip(
                "Use Machine position to auto update Jogging position, "
                "jogging operation use these values to operate. The JOG "
                "current position need to be in sync with machine position "
                "before starting any jog operation. Results maybe undesirable "
                "otherwise"))
        vBoxSizer.Add(self.cbAutoMPOS, flag=wx.LEFT, border=20)

        # Add request status after jogging set operation check box
        self.cbReqUpdateOnJogSetOp = wx.CheckBox(self, wx.ID_ANY, "Request update after JOG set operation")
        self.cbReqUpdateOnJogSetOp.SetValue(self.configData.get('/jogging/ReqUpdateOnJogSetOp'))
        self.cbReqUpdateOnJogSetOp.SetToolTip(wx.ToolTip(
            "If enable after each JOG set operation (ie set to ZERO) a machine update request will be sent to device"))
        vBoxSizer.Add(self.cbReqUpdateOnJogSetOp, flag=wx.LEFT, border=20)

        # Add num keypad as pendant check box
        self.cbNumKeypadPendant = wx.CheckBox(self, wx.ID_ANY, "Numeric Keypad as cnc pendant")
        self.cbNumKeypadPendant.SetValue(self.configData.get('/jogging/NumKeypadPendant'))
        self.cbNumKeypadPendant.SetToolTip(wx.ToolTip(""))
        vBoxSizer.Add(self.cbNumKeypadPendant, flag=wx.LEFT, border=20)

        # Add perform Z operation last check box
        self.cbZJogSafeMove = wx.CheckBox(self, wx.ID_ANY, "Z jog safe move")
        self.cbZJogSafeMove.SetValue(self.configData.get('/jogging/ZJogSafeMove'))
        self.cbZJogSafeMove.SetToolTip(wx.ToolTip(
            "when enabled, if Z_destination is grater Z_current, Z axis moves first, and vise-versa"))
        vBoxSizer.Add(self.cbZJogSafeMove, flag=wx.LEFT, border=20)

        # Add interactive jog
        self.cbJogInteractive = wx.CheckBox(self, wx.ID_ANY, "Interactive Jog")
        self.cbJogInteractive.SetValue(self.configData.get('/jogging/JogInteractive'))
        self.cbJogInteractive.SetToolTip(wx.ToolTip("Enables interactive jog positioning"))
        vBoxSizer.Add(self.cbJogInteractive, flag=wx.LEFT, border=20)

        # Add rapid jog
        self.cbJogRapid = wx.CheckBox(self, wx.ID_ANY, "Rapid Jog")
        self.cbJogRapid.SetValue(self.configData.get('/jogging/JogRapid'))
        self.cbJogRapid.SetToolTip(wx.ToolTip("Enables rapid jog positioning, otherwise feedrate"))
        vBoxSizer.Add(self.cbJogRapid, flag=wx.LEFT, border=20)

        vBoxSizer.AddSpacer(20)

        # Jog feed rate
        text = wx.StaticText(self, label="Jog Feed Rate Default Settings")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, flag=wx.ALL, border=5)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.jogFeedRateSpinCtrl = fs.FloatSpin(
            self, -1, min_val=0, max_val=999999, increment=100, value=self.configData.get('/jogging/JogFeedRate'),
            size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.jogFeedRateSpinCtrl.SetFormat("%f")
        self.jogFeedRateSpinCtrl.SetDigits(0)
        self.jogFeedRateSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.jogFeedRateSpinCtrl, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "units/min")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        vBoxSizer.AddSpacer(20)

        # Spindle
        text = wx.StaticText(self, label="Spindle Default Settings")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, flag=wx.ALL, border=5)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.spindleSpeedSpinCtrl = fs.FloatSpin(
            self, -1, min_val=0, max_val=99999, increment=100, value=self.configData.get('/jogging/SpindleSpeed'),
            size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.spindleSpeedSpinCtrl.SetFormat("%f")
        self.spindleSpeedSpinCtrl.SetDigits(0)
        self.spindleSpeedSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.spindleSpeedSpinCtrl, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "RPM")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        vBoxSizer.AddSpacer(20)

        # Z probe
        text = wx.StaticText(self, label="Z Probe Default Settings")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, flag=wx.ALL, border=5)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.probeZDistanceSpinCtrl = fs.FloatSpin(
            self, -1, min_val=-9999, max_val=9999, increment=0.1, value=self.configData.get('/jogging/ProbeDistance'),
            size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.probeZDistanceSpinCtrl.SetFormat("%f")
        self.probeZDistanceSpinCtrl.SetDigits(6)
        self.probeZDistanceSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.probeZDistanceSpinCtrl, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        st = wx.StaticText(self, wx.ID_ANY, "Probe Z height")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.probeZMaxDistanceSpinCtrl = fs.FloatSpin(
            self, -1, min_val=-9999, max_val=9999, increment=0.1,
            value=self.configData.get('/jogging/ProbeMaxDistance'), size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.probeZMaxDistanceSpinCtrl.SetFormat("%f")
        self.probeZMaxDistanceSpinCtrl.SetDigits(6)
        self.probeZMaxDistanceSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.probeZMaxDistanceSpinCtrl, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        st = wx.StaticText(self, wx.ID_ANY, "Probe Z max travel")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.probeZFeedRateSpinCtrl = fs.FloatSpin(
            self, -1, min_val=-0, max_val=99999, increment=0.1, value=self.configData.get('/jogging/ProbeFeedRate'),
            size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.probeZFeedRateSpinCtrl.SetFormat("%f")
        self.probeZFeedRateSpinCtrl.SetDigits(6)
        self.probeZFeedRateSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.probeZFeedRateSpinCtrl, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        st = wx.StaticText(self, wx.ID_ANY, "Probe Z feed rate")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        vBoxSizer.AddSpacer(20)

        # Custom controls
        text = wx.StaticText(self, label="Custom Controls")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, flag=wx.ALL, border=5)

        self.customButtonsDict = self.configData.get('/jogging/CustomButtons')
        self.customCtrlArray = list()

        for customButtonName in sorted(self.customButtonsDict.keys()):
            box, ctrl = self.CreateCustomControlSettings(
                customButtonName, self.customButtonsDict[customButtonName])
            self.customCtrlArray.append(ctrl)
            vBoxSizer.Add(box, proportion=1, flag=wx.LEFT | wx.EXPAND, border=20)

        self.SetSizer(vBoxSizer)

    def CreateCustomControlSettings(self, cName, cDict):
        # Custom controls
        vBoxSizerRoot = wx.BoxSizer(wx.VERTICAL)

        text = wx.StaticText(self, label="Custom Control %s" % cName.replace("Custom", ""))

        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizerRoot.Add(text, flag=wx.ALL, border=5)

        # Label
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(self, label="Label")
        hBoxSizer.Add(text, flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT | wx.BOTTOM, border=5)
        tcLabel = wx.TextCtrl(self, -1, cDict["Label"], size=(125, -1))
        hBoxSizer.Add(tcLabel, flag=wx.ALIGN_CENTER_VERTICAL)

        vBoxSizerRoot.Add(hBoxSizer, flag=wx.LEFT, border=20)

        # add edit control for script
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        text = wx.StaticText(self, wx.ID_ANY, "Script")
        vBoxSizer.Add(text)

        tcScript = wx.TextCtrl(self, wx.ID_ANY, "", style=wx.TE_MULTILINE)
        tcScript.SetValue(cDict["Script"])
        tcScript.SetToolTip(wx.ToolTip(
            "This script is sent to device when custom button is pressed"))
        vBoxSizer.Add(tcScript, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.BOTTOM, border=10)

        vBoxSizerRoot.Add(vBoxSizer, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=20)

        return vBoxSizerRoot, [cName, tcLabel, tcScript]

    def UpdateConfigData(self):
        self.configData.set('/jogging/XYZReadOnly', self.cbXYZReadOnly.GetValue())
        self.configData.set('/jogging/AutoMPOS', self.cbAutoMPOS.GetValue())
        self.configData.set('/jogging/ReqUpdateOnJogSetOp', self.cbReqUpdateOnJogSetOp.GetValue())
        self.configData.set('/jogging/NumKeypadPendant', self.cbNumKeypadPendant.GetValue())
        self.configData.set('/jogging/ZJogSafeMove', self.cbZJogSafeMove.GetValue())

        self.configData.set('/jogging/SpindleSpeed', self.spindleSpeedSpinCtrl.GetValue())

        self.configData.set('/jogging/ProbeDistance', self.probeZDistanceSpinCtrl.GetValue())
        self.configData.set('/jogging/ProbeMaxDistance', self.probeZMaxDistanceSpinCtrl.GetValue())
        self.configData.set('/jogging/ProbeFeedRate', self.probeZFeedRateSpinCtrl.GetValue())

        self.configData.set('/jogging/JogInteractive', self.cbJogInteractive.GetValue())

        self.configData.set('/jogging/JogRapid', self.cbJogRapid.GetValue())

        self.configData.set('/jogging/JogFeedRate', self.jogFeedRateSpinCtrl.GetValue())

        for i in self.customCtrlArray:
            self.configData.set('/jogging/CustomButtons/%s/Label' % i[0], i[1].GetValue())
            self.configData.set('/jogging/CustomButtons/%s/Script' % i[0], i[2].GetValue())
