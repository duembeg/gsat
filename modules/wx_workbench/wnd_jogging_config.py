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
        self.jogFeedRateSpinCtrl = wx.SpinCtrlDouble(
            self, -1, size=(-1, -1), min=0, max=99999,
            initial=self.configData.get('/jogging/JogFeedRate'), inc=100)

        self.jogFeedRateSpinCtrl.SetDigits(0)
        self.jogFeedRateSpinCtrl.SetToolTip(wx.ToolTip("Jog Feed Rate Default Settings"))

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
        self.spindleSpeedSpinCtrl = wx.SpinCtrlDouble(
            self, -1, size=(-1, -1), min=0, max=99999,
            initial=self.configData.get('/jogging/SpindleSpeed'), inc=100)
        self.spindleSpeedSpinCtrl.SetDigits(0)
        self.spindleSpeedSpinCtrl.SetToolTip(wx.ToolTip("Spindle Default Settings"))
        hBoxSizer.Add(self.spindleSpeedSpinCtrl, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "RPM")
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
        tcScript.SetToolTip(wx.ToolTip("This script is sent to device when custom button is pressed"))
        vBoxSizer.Add(tcScript, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.BOTTOM, border=10)

        vBoxSizerRoot.Add(vBoxSizer, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=20)

        return vBoxSizerRoot, {'name': cName, 'label': tcLabel, 'script': tcScript}

    def UpdateConfigData(self):
        self.configData.set("/jogging/NumKeypadPendant", self.cbNumKeypadPendant.GetValue())
        self.configData.set("/jogging/ZJogSafeMove", self.cbZJogSafeMove.GetValue())

        self.configData.set("/jogging/SpindleSpeed", self.spindleSpeedSpinCtrl.GetValue())

        self.configData.set("/jogging/JogRapid", self.cbJogRapid.GetValue())

        self.configData.set("/jogging/JogFeedRate", self.jogFeedRateSpinCtrl.GetValue())

        for custom_ctrl in self.customCtrlArray:
            self.configData.set(
                f"/jogging/CustomButtons/{custom_ctrl.get('name')}/Label", custom_ctrl.get('label').GetValue())
            self.configData.set(
                f"/jogging/CustomButtons/{custom_ctrl.get('name')}/Script", custom_ctrl.get('script').GetValue())
