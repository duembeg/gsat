"""----------------------------------------------------------------------------
   wnd_jogging.py

   Copyright (C) 2013-2018 Wilhelm Duembeg

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

import time


class gsatJoggingSettingsPanel(scrolled.ScrolledPanel):
    """ Jog panel settings
    """
    def __init__(self, parent, config_data, **args):
        scrolled.ScrolledPanel.__init__(
            self, parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER
        )

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
            wx.ToolTip("If enabled the XYZ fields in jogging status become read only"))
        vBoxSizer.Add(self.cbXYZReadOnly, flag=wx.LEFT, border=20)

        # Add update from machine pos check box
        self.cbAutoMPOS = wx.CheckBox(
            self, wx.ID_ANY, "Auto update from machine position")
        self.cbAutoMPOS.SetValue(self.configData.get('/jogging/AutoMPOS'))
        self.cbAutoMPOS.SetToolTip(
            wx.ToolTip("Use Machine position to auto update Jogging position, "
                       "jogging operation use these values to operate. The JOG current "
                       "position need to be in sync with machine position before "
                       "starting any jog operation. Results maybe undesirable otherwise"))
        vBoxSizer.Add(self.cbAutoMPOS, flag=wx.LEFT, border=20)

        # Add request status after jogging set operation check box
        self.cbReqUpdateOnJogSetOp = wx.CheckBox(
            self, wx.ID_ANY, "Request update after JOG set operation")
        self.cbReqUpdateOnJogSetOp.SetValue(
            self.configData.get('/jogging/ReqUpdateOnJogSetOp'))
        self.cbReqUpdateOnJogSetOp.SetToolTip(
            wx.ToolTip("If enable after each JOG set operation (ie set to ZERO) a machine update request will be sent to device"))
        vBoxSizer.Add(self.cbReqUpdateOnJogSetOp, flag=wx.LEFT, border=20)

        # Add num keypad as pendant check box
        self.cbNumKeypadPendant = wx.CheckBox(
            self, wx.ID_ANY, "Numeric Keypad as cnc pendant")
        self.cbNumKeypadPendant.SetValue(
            self.configData.get('/jogging/NumKeypadPendant'))
        self.cbNumKeypadPendant.SetToolTip(
            wx.ToolTip(""))
        vBoxSizer.Add(self.cbNumKeypadPendant, flag=wx.LEFT, border=20)

        # Add perform Z operation last check box
        self.cbZJogSafeMove = wx.CheckBox(self, wx.ID_ANY, "Z jog safe move")
        self.cbZJogSafeMove.SetValue(
            self.configData.get('/jogging/ZJogSafeMove'))
        self.cbZJogSafeMove.SetToolTip(
            wx.ToolTip("when enabled, if Z_destination is grater Z_current, Z axis moves first, and vise-versa"))
        vBoxSizer.Add(self.cbZJogSafeMove, flag=wx.LEFT, border=20)

        # Add interactive jog
        self.cbJogInteractive = wx.CheckBox(
            self, wx.ID_ANY, "Interactive Jog")
        self.cbJogInteractive.SetValue(
            self.configData.get('/jogging/JogInteractive'))
        self.cbJogInteractive.SetToolTip(
            wx.ToolTip("Enables interactive jog positioning"))
        vBoxSizer.Add(self.cbJogInteractive, flag=wx.LEFT, border=20)

        # Add rapid jog
        self.cbJogRapid = wx.CheckBox(
            self, wx.ID_ANY, "Rapid Jog")
        self.cbJogRapid.SetValue(
            self.configData.get('/jogging/JogRapid'))
        self.cbJogRapid.SetToolTip(
            wx.ToolTip("Enables rapid jog positioning, otherwise feedrate"))
        vBoxSizer.Add(self.cbJogRapid, flag=wx.LEFT, border=20)

        vBoxSizer.AddSpacer(20)

        # Jog feed rate
        text = wx.StaticText(self, label="Jog Feed Rate Default Settings")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, flag=wx.ALL, border=5)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.jogFeedRateSpinCtrl = fs.FloatSpin(
            self, -1, min_val=0, max_val=999999, increment=100,
            value=self.configData.get('/jogging/JogFeedRate'),
            size=(-1, -1), agwStyle=fs.FS_LEFT
        )
        self.jogFeedRateSpinCtrl.SetFormat("%f")
        self.jogFeedRateSpinCtrl.SetDigits(0)
        self.jogFeedRateSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.jogFeedRateSpinCtrl, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)

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
        self.spindleSpeedSpinCtrl = fs.FloatSpin(self, -1,
                                                 min_val=0, max_val=99999, increment=100,
                                                 value=self.configData.get(
                                                     '/jogging/SpindleSpeed'),
                                                 size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.spindleSpeedSpinCtrl.SetFormat("%f")
        self.spindleSpeedSpinCtrl.SetDigits(0)
        self.spindleSpeedSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.spindleSpeedSpinCtrl, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)

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
        self.probeZDistanceSpinCtrl = fs.FloatSpin(self, -1,
                                                   min_val=-99999, max_val=99999, increment=0.1,
                                                   value=self.configData.get(
                                                       '/jogging/ProbeDistance'),
                                                   size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.probeZDistanceSpinCtrl.SetFormat("%f")
        self.probeZDistanceSpinCtrl.SetDigits(6)
        self.probeZDistanceSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.probeZDistanceSpinCtrl, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)
        st = wx.StaticText(self, wx.ID_ANY, "Probe Z height")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.probeZMaxDistanceSpinCtrl = fs.FloatSpin(self, -1,
                                                      min_val=-99999, max_val=99999, increment=0.1,
                                                      value=self.configData.get(
                                                          '/jogging/ProbeMaxDistance'),
                                                      size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.probeZMaxDistanceSpinCtrl.SetFormat("%f")
        self.probeZMaxDistanceSpinCtrl.SetDigits(6)
        self.probeZMaxDistanceSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.probeZMaxDistanceSpinCtrl,
                      flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        st = wx.StaticText(self, wx.ID_ANY, "Probe Z max travel")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.probeZFeedRateSpinCtrl = fs.FloatSpin(self, -1,
                                                   min_val=-0, max_val=99999, increment=0.1,
                                                   value=self.configData.get(
                                                       '/jogging/ProbeFeedRate'),
                                                   size=(-1, -1), agwStyle=fs.FS_LEFT)
        self.probeZFeedRateSpinCtrl.SetFormat("%f")
        self.probeZFeedRateSpinCtrl.SetDigits(6)
        self.probeZFeedRateSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        hBoxSizer.Add(self.probeZFeedRateSpinCtrl, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)
        st = wx.StaticText(self, wx.ID_ANY, "Probe Z feed rate")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        vBoxSizer.AddSpacer(20)

        # Custom controls
        text = wx.StaticText(self, label="Custom Controls")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, flag=wx.ALL, border=5)

        box1, c1CtrlArray = self.CreateCustomControlSettings(1)
        box2, c2CtrlArray = self.CreateCustomControlSettings(2)
        box3, c3CtrlArray = self.CreateCustomControlSettings(3)
        box4, c4CtrlArray = self.CreateCustomControlSettings(4)

        self.customCtrlArray = [c1CtrlArray,
                                c2CtrlArray, c3CtrlArray, c4CtrlArray]

        vBoxSizer.Add(box1, proportion=1, flag=wx.LEFT | wx.EXPAND, border=20)
        vBoxSizer.Add(box2, proportion=1, flag=wx.LEFT | wx.EXPAND, border=20)
        vBoxSizer.Add(box3, proportion=1, flag=wx.LEFT | wx.EXPAND, border=20)
        vBoxSizer.Add(box4, proportion=1, flag=wx.LEFT | wx.EXPAND, border=20)

        self.SetSizer(vBoxSizer)

    def CreateCustomControlSettings(self, cn):
        # Custom controls
        vBoxSizerRoot = wx.BoxSizer(wx.VERTICAL)
        text = wx.StaticText(self, label="Custom Control %d" % cn)
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizerRoot.Add(text, flag=wx.ALL, border=5)

        # Label
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(self, label="Label")
        hBoxSizer.Add(text, flag=wx.ALIGN_CENTER_VERTICAL |
                      wx.TOP | wx.RIGHT | wx.BOTTOM, border=5)
        tcLabel = wx.TextCtrl(self, -1,
                              self.configData.get('/jogging/Custom%dLabel' % cn), size=(125, -1))
        hBoxSizer.Add(tcLabel, flag=wx.ALIGN_CENTER_VERTICAL)

        vBoxSizerRoot.Add(hBoxSizer, flag=wx.LEFT, border=20)

        # add edit control for script
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        text = wx.StaticText(self, wx.ID_ANY, "Script")
        vBoxSizer.Add(text, flag=wx.ALIGN_CENTER_VERTICAL)

        tcScript = wx.TextCtrl(self, wx.ID_ANY, "", style=wx.TE_MULTILINE)
        tcScript.SetValue(self.configData.get('/jogging/Custom%dScript' % cn))
        tcScript.SetToolTip(wx.ToolTip(
            "This script is sent to device when custom button is pressed"))
        vBoxSizer.Add(tcScript, proportion=1, flag=wx.EXPAND |
                      wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.BOTTOM, border=10)

        vBoxSizerRoot.Add(vBoxSizer, proportion=1,
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=20)

        return vBoxSizerRoot, [tcLabel, tcScript]

    def UpdateConfigData(self):
        self.configData.set('/jogging/XYZReadOnly',
                            self.cbXYZReadOnly.GetValue())
        self.configData.set('/jogging/AutoMPOS', self.cbAutoMPOS.GetValue())
        self.configData.set('/jogging/ReqUpdateOnJogSetOp',
                            self.cbReqUpdateOnJogSetOp.GetValue())
        self.configData.set('/jogging/NumKeypadPendant',
                            self.cbNumKeypadPendant.GetValue())
        self.configData.set('/jogging/ZJogSafeMove',
                            self.cbZJogSafeMove.GetValue())

        self.configData.set('/jogging/SpindleSpeed',
                            self.spindleSpeedSpinCtrl.GetValue())

        self.configData.set('/jogging/ProbeDistance',
                            self.probeZDistanceSpinCtrl.GetValue())
        self.configData.set('/jogging/ProbeMaxDistance',
                            self.probeZMaxDistanceSpinCtrl.GetValue())
        self.configData.set('/jogging/ProbeFeedRate',
                            self.probeZFeedRateSpinCtrl.GetValue())

        self.configData.set('/jogging/JogInteractive',
                            self.cbJogInteractive.GetValue())

        self.configData.set('/jogging/JogRapid',
                            self.cbJogRapid.GetValue())

        self.configData.set('/jogging/JogFeedRate',
                            self.jogFeedRateSpinCtrl.GetValue())

        for cn in range(4):
            cnp1 = cn+1
            self.configData.set('/jogging/Custom%dLabel' % cnp1,
                                self.customCtrlArray[cn][0].GetValue())

            self.configData.set('/jogging/Custom%dScript' % cnp1,
                                self.customCtrlArray[cn][1].GetValue())


class gsatCliSettingsPanel(scrolled.ScrolledPanel):
    """-------------------------------------------------------------------------
    gsatCliSettingsPanel:
    CLI settings.
    -------------------------------------------------------------------------"""

    def __init__(self, parent, config_data, **args):
        scrolled.ScrolledPanel.__init__(self, parent,
                                        style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        self.stateData = None
        self.keybaordJoggingEnable = False
        # self.FitInside()

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # Add cehck box
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


class gsatJoggingPanel(wx.ScrolledWindow):
    """ Jog controls for the machine as well as custom user controls.
    """
    def __init__(self, parent, config_data, state_data, **args):
        wx.ScrolledWindow.__init__(self, parent, **args)

        self.mainWindow = parent

        self.configData = config_data
        self.stateData = state_data
        self.machStat = "None"
        self.machPosX = 0
        self.machPosY = 0
        self.machPosZ = 0
        self.machPosA = 0
        self.machPosB = 0
        self.machPosC = 0

        self.memoX = gc.ZERO_STRING
        self.memoY = gc.ZERO_STRING
        self.memoZ = gc.ZERO_STRING

        self.cliCommand = ""
        self.cliIndex = 0

        self.InitConfig()
        self.InitUI()
        width, height = self.GetSizeTuple()
        scroll_unit = 10
        self.SetScrollbars(scroll_unit, scroll_unit, width /
                           scroll_unit, height/scroll_unit)

        self.UpdateSettings(self.configData)
        # self.allCheckBox.SetValue(True)
        # self.spinCtrl.SetFocus()
        self.LoadCli()

        self.SavedJogPos = None

        self.keyCache = None
        self.jogInteractiveState = False

        self.numKeypadPendantKeys = [
            wx.WXK_NUMPAD_UP,
            wx.WXK_NUMPAD_DOWN,
            wx.WXK_NUMPAD_LEFT,
            wx.WXK_NUMPAD_RIGHT,
            wx.WXK_NUMPAD_HOME,
            wx.WXK_NUMPAD_PAGEUP,
            wx.WXK_NUMPAD_PAGEDOWN,
            wx.WXK_NUMPAD_END,
            wx.WXK_NUMPAD_BEGIN,
            wx.WXK_NUMPAD_INSERT,
            wx.WXK_NUMPAD_DELETE,
            wx.WXK_NUMPAD_DIVIDE,
            wx.WXK_NUMPAD_MULTIPLY,
            wx.WXK_NUMPAD_SUBTRACT,
            wx.WXK_NUMPAD_ADD,
            wx.WXK_NUMPAD_ENTER,
            wx.WXK_NUMPAD0,
            wx.WXK_NUMPAD1,
            wx.WXK_NUMPAD2,
            wx.WXK_NUMPAD3,
            wx.WXK_NUMPAD4,
            wx.WXK_NUMPAD5,
            wx.WXK_NUMPAD6,
            wx.WXK_NUMPAD7,
            wx.WXK_NUMPAD8,
            wx.WXK_NUMPAD9
        ]

    def InitConfig(self):
        # jogging data
        self.configXYZReadOnly = self.configData.get('/jogging/XYZReadOnly')
        self.configAutoMPOS = self.configData.get('/jogging/AutoMPOS')
        self.configReqUpdateOnJogSetOp = self.configData.get(
            '/jogging/ReqUpdateOnJogSetOp')
        self.configNumKeypadPendant = self.configData.get(
            '/jogging/NumKeypadPendant')
        self.configZJogSafeMove = self.configData.get(
            '/jogging/ZJogSafeMove')

        self.configSpindleSpeed = self.configData.get('/jogging/SpindleSpeed')

        self.configProbeDistance = self.configData.get(
            '/jogging/ProbeDistance')
        self.configProbeMaxDistance = self.configData.get(
            '/jogging/ProbeMaxDistance')
        self.configProbeFeedRate = self.configData.get(
            '/jogging/ProbeFeedRate')

        self.configCustom1Label = self.configData.get('/jogging/Custom1Label')
        self.configCustom1Script = self.configData.get(
            '/jogging/Custom1Script')

        self.configCustom2Label = self.configData.get('/jogging/Custom2Label')
        self.configCustom2Script = self.configData.get(
            '/jogging/Custom2Script')

        self.configCustom3Label = self.configData.get('/jogging/Custom3Label')
        self.configCustom3Script = self.configData.get(
            '/jogging/Custom3Script')

        self.configCustom4Label = self.configData.get('/jogging/Custom4Label')
        self.configCustom4Script = self.configData.get(
            '/jogging/Custom4Script')

        self.configJogFeedRate = self.configData.get('/jogging/JogFeedRate')
        self.configJogInteractive = self.configData.get(
            '/jogging/JogInteractive')
        self.configJogRapid = self.configData.get('/jogging/JogRapid')

        # cli data
        self.cliSaveCmdHistory = self.configData.get('/cli/SaveCmdHistory')
        self.cliCmdMaxHistory = self.configData.get('/cli/CmdMaxHistory')
        self.cliCmdHistory = self.configData.get('/cli/CmdHistory')

    def UpdateSettings(self, config_data):
        self.configData = config_data
        self.InitConfig()

        if self.configXYZReadOnly:
            self.jX.SetEditable(False)
            self.jX.SetBackgroundColour(gc.READ_ONLY_BK_COLOR)
            self.jY.SetEditable(False)
            self.jY.SetBackgroundColour(gc.READ_ONLY_BK_COLOR)
            self.jZ.SetEditable(False)
            self.jZ.SetBackgroundColour(gc.READ_ONLY_BK_COLOR)
        else:
            self.jX.SetEditable(True)
            self.jX.SetBackgroundColour(gc.EDIT_BK_COLOR)
            self.jY.SetEditable(True)
            self.jY.SetBackgroundColour(gc.EDIT_BK_COLOR)
            self.jZ.SetEditable(True)
            self.jZ.SetBackgroundColour(gc.EDIT_BK_COLOR)

        self.useWorkPosCheckBox.SetValue(self.configAutoMPOS)
        self.numKeypadPendantCheckBox.SetValue(self.configNumKeypadPendant)
        self.zJogMovesLastCheckBox.SetValue(self.configZJogSafeMove)

        self.spindleSpeedSpinCtrl.SetValue(self.configSpindleSpeed)

        self.rapidJogCheckBox.SetValue(self.configJogRapid)

        self.custom1Button.SetLabel(self.configCustom1Label)
        self.custom2Button.SetLabel(self.configCustom2Label)
        self.custom3Button.SetLabel(self.configCustom3Label)
        self.custom4Button.SetLabel(self.configCustom4Label)

    def InitUI(self):
        vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)
        hPanelBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        # Add CLI
        self.cliComboBox = wx.combo.BitmapComboBox(
            self, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER | wx.WANTS_CHARS)
        self.cliComboBox.SetToolTip(wx.ToolTip("Command Line Interface (CLI)"))
        self.cliComboBox.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter)
        self.cliComboBox.Bind(wx.EVT_KEY_DOWN, self.OnCliKeyDown)
        vPanelBoxSizer.Add(self.cliComboBox, 0, wx.EXPAND | wx.ALL, border=1)

        # Add Controls ----------------------------------------------------------
        joggingControls = self.CreateJoggingControls()
        vPanelBoxSizer.Add(joggingControls, 0, flag=wx.ALL |
                           wx.EXPAND, border=5)

        positionStatusControls = self.CreatePositionStatusControls()
        hPanelBoxSizer.Add(positionStatusControls, 0, flag=wx.EXPAND)

        gotoResetControls = self.CreateGotoAndResetControls()
        hPanelBoxSizer.Add(gotoResetControls, 0,
                           flag=wx.LEFT | wx.EXPAND, border=10)

        vPanelBoxSizer.Add(hPanelBoxSizer, 0, flag=wx.ALL |
                           wx.EXPAND, border=5)

        utilControls = self.CreateUtilControls()
        vPanelBoxSizer.Add(utilControls, 0, flag=wx.ALL | wx.EXPAND, border=5)

        # Finish up init UI
        self.SetSizer(vPanelBoxSizer)
        self.Layout()

        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)
        self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.jX.Bind(wx.EVT_TEXT_PASTE, self.onJogEditPaste)
        self.jY.Bind(wx.EVT_TEXT_PASTE, self.onJogEditPaste)
        self.jZ.Bind(wx.EVT_TEXT_PASTE, self.onJogEditPaste)

        # keyboard timer for interactive fucntion
        self.keyTimer = wx.Timer(self, id=-1)
        #self.keyTimerEvent = wx.TimerEvent(self.keyTimer.GetId())
        self.Bind(wx.EVT_TIMER, self.OnKeyTimer, self.keyTimer)

    def UpdateUI(self, stateData, statusData=None):
        self.stateData = stateData

        if statusData is not None:
            x = statusData.get('posx')
            if x is not None:
                self.machPosX = x
                if self.configAutoMPOS:
                    self.jX.SetValue("{:.3f}".format(x))

            y = statusData.get('posy')
            if y is not None:
                self.machPosY = y
                if self.configAutoMPOS:
                    self.jY.SetValue("{:.3f}".format(y))

            z = statusData.get('posz')
            if z is not None:
                self.machPosZ = z
                if self.configAutoMPOS:
                    self.jZ.SetValue("{:.3f}".format(z))

            a = statusData.get('posa')
            if z is not None:
                self.machPosA = a

            b = statusData.get('posb')
            if z is not None:
                self.machPosB = b

            c = statusData.get('posc')
            if z is not None:
                self.machPosC = c

            stat = statusData.get('stat')
            if stat is not None:
                self.machStat = stat

        if stateData.serialPortIsOpen and not stateData.swState == gc.STATE_RUN:
            self.keybaordJoggingEnable = True
            self.resetToZeroButton.Enable()
            self.resetToJogButton.Enable()
            self.gotoToZeroButton.Enable()
            self.gotoToJogButton.Enable()
            self.gotoToHomeButton.Enable()
            self.positiveXButton.Enable()
            self.negativeXButton.Enable()
            self.positiveYButton.Enable()
            self.negativeYButton.Enable()
            self.positiveZButton.Enable()
            self.negativeZButton.Enable()
            self.spindleCWOnButton.Enable()
            self.spindleCCWOnButton.Enable()
            self.spindleOffButton.Enable()
            self.coolantOnButton.Enable()
            self.coolantOffButton.Enable()
            self.custom1Button.Enable()
            self.custom2Button.Enable()
            self.custom3Button.Enable()
            self.custom4Button.Enable()
            self.cliComboBox.Enable()
            self.homeXButton.Enable()
            self.homeYButton.Enable()
            self.homeZButton.Enable()
            self.homeButton.Enable()
            self.SetToZeroButton.Enable()
            self.SetToZeroXYButton.Enable()
            self.SetToZeroZButton.Enable()
            self.GoToZeroXYButton.Enable()
            self.probeZButton.Enable()

            if self.SavedJogPos is None:
                self.restorePositionButton.Disable()
            else:
                self.restorePositionButton.Enable()

        else:
            self.keybaordJoggingEnable = False
            self.resetToZeroButton.Disable()
            self.resetToJogButton.Disable()
            self.gotoToZeroButton.Disable()
            self.gotoToJogButton.Disable()
            self.gotoToHomeButton.Disable()
            self.positiveXButton.Disable()
            self.negativeXButton.Disable()
            self.positiveYButton.Disable()
            self.negativeYButton.Disable()
            self.positiveZButton.Disable()
            self.negativeZButton.Disable()
            self.spindleCWOnButton.Disable()
            self.spindleCCWOnButton.Disable()
            self.spindleOffButton.Disable()
            self.coolantOnButton.Disable()
            self.coolantOffButton.Disable()
            self.custom1Button.Disable()
            self.custom2Button.Disable()
            self.custom3Button.Disable()
            self.custom4Button.Disable()
            self.cliComboBox.Disable()
            self.homeXButton.Disable()
            self.homeYButton.Disable()
            self.homeZButton.Disable()
            self.homeButton.Disable()
            self.SetToZeroButton.Disable()
            self.SetToZeroXYButton.Disable()
            self.SetToZeroZButton.Disable()
            self.GoToZeroXYButton.Disable()
            self.probeZButton.Disable()

            self.restorePositionButton.Disable()

    def CreateJoggingControls(self):
        # Add Buttons -----------------------------------------------------------
        gbzJoggingGridSizer = wx.GridBagSizer(0, 0)
        gbStepSizeGridSizer = wx.GridBagSizer(0, 0)
        gbJogSpindleGridSizer = wx.GridBagSizer(0, 0)

        buttonSize = (52, 52)
        #buttonSizeLong = (52, 75)
        #buttonSizeWideLong = (60, 75)

        # X axis buttons
        self.positiveXButton = wx.BitmapButton(self, -1, ico.imgPosX.GetBitmap(),
                                               size=buttonSize, style=wx.BORDER_NONE)
        self.positiveXButton.SetToolTip(
            wx.ToolTip("Move X axis on positive direction by step size"))
        self.Bind(wx.EVT_BUTTON, self.OnXPos, self.positiveXButton)
        gbzJoggingGridSizer.Add(self.positiveXButton, pos=(1, 2))

        self.negativeXButton = wx.BitmapButton(self, -1, ico.imgNegX.GetBitmap(),
                                               size=buttonSize, style=wx.BORDER_NONE)
        self.negativeXButton.SetToolTip(
            wx.ToolTip("Move X axis on negative direction by step size"))
        self.Bind(wx.EVT_BUTTON, self.OnXNeg, self.negativeXButton)
        gbzJoggingGridSizer.Add(self.negativeXButton, pos=(1, 0))

        # Y axis buttons
        self.positiveYButton = wx.BitmapButton(self, -1, ico.imgPosY.GetBitmap(),
                                               size=buttonSize, style=wx.BORDER_NONE)
        self.positiveYButton.SetToolTip(
            wx.ToolTip("Move Y axis on positive direction by step size"))
        self.Bind(wx.EVT_BUTTON, self.OnYPos, self.positiveYButton)
        gbzJoggingGridSizer.Add(self.positiveYButton, pos=(0, 1))

        self.negativeYButton = wx.BitmapButton(self, -1, ico.imgNegY.GetBitmap(),
                                               size=buttonSize, style=wx.BORDER_NONE)
        self.negativeYButton.SetToolTip(
            wx.ToolTip("Move Y axis on negative direction by step size"))
        self.Bind(wx.EVT_BUTTON, self.OnYNeg, self.negativeYButton)
        gbzJoggingGridSizer.Add(self.negativeYButton, pos=(2, 1))

        # Z axis buttons
        self.positiveZButton = wx.BitmapButton(self, -1, ico.imgPosZ.GetBitmap(),
                                               size=buttonSize, style=wx.BORDER_NONE)
        self.positiveZButton.SetToolTip(
            wx.ToolTip("Move Z axis on positive direction by step size"))
        self.Bind(wx.EVT_BUTTON, self.OnZPos, self.positiveZButton)
        gbzJoggingGridSizer.Add(self.positiveZButton, pos=(0, 3))

        self.negativeZButton = wx.BitmapButton(self, -1, ico.imgNegZ.GetBitmap(),
                                               size=buttonSize, style=wx.BORDER_NONE)
        self.negativeZButton.SetToolTip(
            wx.ToolTip("Move Z axis on negative direction by step size"))
        self.Bind(wx.EVT_BUTTON, self.OnZNeg, self.negativeZButton)
        gbzJoggingGridSizer.Add(self.negativeZButton, pos=(2, 3))

        # Spindle buttons
        self.spindleCWOnButton = wx.BitmapButton(self, -1, ico.imgSpindleCWOn.GetBitmap(),
                                                 size=buttonSize, style=wx.BORDER_NONE)
        self.spindleCWOnButton.SetToolTip(wx.ToolTip("Spindle CW ON"))
        self.Bind(wx.EVT_BUTTON, self.OnSpindleCWOn, self.spindleCWOnButton)
        gbzJoggingGridSizer.Add(self.spindleCWOnButton, pos=(2, 4))

        self.spindleCCWOnButton = wx.BitmapButton(self, -1, ico.imgSpindleCCWOn.GetBitmap(),
                                                  size=buttonSize, style=wx.BORDER_NONE)
        self.spindleCCWOnButton.SetToolTip(wx.ToolTip("Spindle CCW ON"))
        self.Bind(wx.EVT_BUTTON, self.OnSpindleCCWOn, self.spindleCCWOnButton)
        gbzJoggingGridSizer.Add(self.spindleCCWOnButton, pos=(2, 5))

        self.spindleOffButton = wx.BitmapButton(self, -1, ico.imgSpindleOff.GetBitmap(),
                                                size=buttonSize, style=wx.BORDER_NONE)
        self.spindleOffButton.SetToolTip(wx.ToolTip("Spindle OFF"))
        self.Bind(wx.EVT_BUTTON, self.OnSpindleOff, self.spindleOffButton)
        gbzJoggingGridSizer.Add(self.spindleOffButton, pos=(2, 6))

        # Coolant Buttons
        self.coolantOnButton = wx.BitmapButton(self, -1, ico.imgCoolantOn.GetBitmap(),
                                               size=buttonSize, style=wx.BORDER_NONE)
        self.coolantOnButton.SetToolTip(wx.ToolTip("Coolant ON"))
        self.Bind(wx.EVT_BUTTON, self.OnCoolantOn, self.coolantOnButton)
        gbzJoggingGridSizer.Add(self.coolantOnButton, pos=(1, 4))

        self.coolantOffButton = wx.BitmapButton(self, -1, ico.imgCoolantOff.GetBitmap(),
                                                size=buttonSize, style=wx.BORDER_NONE)
        self.coolantOffButton.SetToolTip(wx.ToolTip("Coolant OFF"))
        self.Bind(wx.EVT_BUTTON, self.OnCoolantOff, self.coolantOffButton)
        gbzJoggingGridSizer.Add(self.coolantOffButton, pos=(1, 5))

        # Home Buttons
        self.homeButton = wx.BitmapButton(self, -1, ico.imgHomeXYZ.GetBitmap(),
                                          size=buttonSize, style=wx.BORDER_NONE)
        self.homeButton.SetToolTip(wx.ToolTip("Home XYZ axis"))
        self.Bind(wx.EVT_BUTTON, self.OnHome, self.homeButton)
        gbzJoggingGridSizer.Add(self.homeButton, pos=(0, 0))

        self.homeXButton = wx.BitmapButton(self, -1, ico.imgHomeX.GetBitmap(),
                                           size=buttonSize, style=wx.BORDER_NONE)
        self.homeXButton.SetToolTip(wx.ToolTip("Home X axis"))
        self.Bind(wx.EVT_BUTTON, self.OnHomeX, self.homeXButton)
        gbzJoggingGridSizer.Add(self.homeXButton, pos=(0, 2))

        self.homeYButton = wx.BitmapButton(self, -1, ico.imgHomeY.GetBitmap(),
                                           size=buttonSize, style=wx.BORDER_NONE)
        self.homeYButton.SetToolTip(wx.ToolTip("Home Y axis"))
        self.Bind(wx.EVT_BUTTON, self.OnHomeY, self.homeYButton)
        gbzJoggingGridSizer.Add(self.homeYButton, pos=(2, 2))

        self.homeZButton = wx.BitmapButton(self, -1, ico.imgHomeZ.GetBitmap(),
                                           size=buttonSize, style=wx.BORDER_NONE)
        self.homeZButton.SetToolTip(wx.ToolTip("Home Z axis"))
        self.Bind(wx.EVT_BUTTON, self.OnHomeZ, self.homeZButton)
        gbzJoggingGridSizer.Add(self.homeZButton, pos=(1, 3))


        # self.homeXYButton = wx.BitmapButton(self, -1, ico.imgHomeXY.GetBitmap(),
        #   size=buttonSize, style=wx.BORDER_NONE)
        #self.homeXYButton.SetToolTip(wx.ToolTip("Home XY axis"))
        #self.Bind(wx.EVT_BUTTON, self.OnHomeXY, self.homeXYButton)
        #gbzJoggingGridSizer.Add(self.homeXYButton, pos=(1,1))

        '''
        # add interactive jog check box controls
        self.interactiveJogCheckBox = wx.CheckBox(self, label='Interactive/Step size')
        self.interactiveJogCheckBox.SetValue(self.configJogInteractive)
        self.interactiveJogCheckBox.SetToolTip(
            wx.ToolTip("Enables interactive jog positioning, otherwise step size"))
        self.Bind(wx.EVT_CHECKBOX, self.OnJogInteractive, self.interactiveJogCheckBox)

        gbStepSizeGridSizer.Add(self.interactiveJogCheckBox, pos=(
            0, 0), span=(1, 5), flag=wx.TOP, border=5)
        '''

        # add step size controls
        stepButtonSize = (46, -1)

        spinText = wx.StaticText(self, -1, "Step size")
        gbStepSizeGridSizer.Add(spinText, pos=(
            0, 0), span=(1, 5), flag=wx.TOP, border=5)

        self.stepSpinCtrl = fs.FloatSpin(self, -1,
                                         min_val=0, max_val=99999, increment=0.10, value=1.0,
                                         size=(stepButtonSize[0]*3, -1), agwStyle=fs.FS_LEFT)

        self.stepSpinCtrl.SetFormat("%f")
        self.stepSpinCtrl.SetDigits(3)
        self.stepSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        gbStepSizeGridSizer.Add(self.stepSpinCtrl, pos=(
            1, 0), span=(1, 3), flag=wx.ALIGN_CENTER_VERTICAL)

        self.stepSize0p05 = wx.Button(self, label="0.05", size=stepButtonSize)
        self.stepSize0p05.SetToolTip(wx.ToolTip("Set step size to 0.05"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize0p05)
        gbStepSizeGridSizer.Add(self.stepSize0p05, pos=(1, 3))

        self.stepSize0p1 = wx.Button(self, label="0.1", size=stepButtonSize)
        self.stepSize0p1.SetToolTip(wx.ToolTip("Set step size to 0.1"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize0p1)
        gbStepSizeGridSizer.Add(self.stepSize0p1, pos=(2, 0))

        self.stepSize0p5 = wx.Button(self, label="0.5", size=stepButtonSize)
        self.stepSize0p5.SetToolTip(wx.ToolTip("Set step size to 0.5"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize0p5)
        gbStepSizeGridSizer.Add(self.stepSize0p5, pos=(2, 1))

        self.stepSize1 = wx.Button(self, label="1", size=stepButtonSize)
        self.stepSize1.SetToolTip(wx.ToolTip("Set step size to 1"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize1)
        gbStepSizeGridSizer.Add(self.stepSize1, pos=(2, 2))

        self.stepSize5 = wx.Button(self, label="5", size=stepButtonSize)
        self.stepSize5.SetToolTip(wx.ToolTip("Set step size to 5"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize5)
        gbStepSizeGridSizer.Add(self.stepSize5, pos=(2, 3))

        self.stepSize10 = wx.Button(self, label="10", size=stepButtonSize)
        self.stepSize10.SetToolTip(wx.ToolTip("Set step size to 10"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize10)
        gbStepSizeGridSizer.Add(self.stepSize10, pos=(3, 0))

        self.stepSize20 = wx.Button(self, label="20", size=stepButtonSize)
        self.stepSize20.SetToolTip(wx.ToolTip("Set step size to 20"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize20)
        gbStepSizeGridSizer.Add(self.stepSize20, pos=(3, 1))

        self.stepSize50 = wx.Button(self, label="50", size=stepButtonSize)
        self.stepSize50.SetToolTip(wx.ToolTip("Set step size to 50"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize50)
        gbStepSizeGridSizer.Add(self.stepSize50, pos=(3, 2))

        self.stepSize100 = wx.Button(self, label="100", size=stepButtonSize)
        self.stepSize100.SetToolTip(wx.ToolTip("Set step size to 100"))
        self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize100)
        gbStepSizeGridSizer.Add(self.stepSize100, pos=(3, 3))

        #self.stepSize200 = wx.Button(self, label="200", size=stepButtonSize)
        #self.stepSize200.SetToolTip(wx.ToolTip("Set step size to 200"))
        #self.Bind(wx.EVT_BUTTON, self.OnSetStepSize, self.stepSize200)
        #gbStepSizeGridSizer.Add(self.stepSize200, pos=(3, 3))

        gbzJoggingGridSizer.Add(gbStepSizeGridSizer, pos=(3, 0), span=(4, 4))


        # add rapid jog check box controls
        self.rapidJogCheckBox = wx.CheckBox(self, label='Rapid')
        self.rapidJogCheckBox.SetValue(self.configJogRapid)
        self.rapidJogCheckBox.SetToolTip(
            wx.ToolTip("Enables rapid jog positioning, otherwise feedrate"))
        self.Bind(wx.EVT_CHECKBOX, self.OnJogRapid, self.rapidJogCheckBox)

        gbJogSpindleGridSizer.Add(self.rapidJogCheckBox, pos=(
            0, 0), span=(1, 2), flag=wx.TOP, border=5)

        self.feedRateSpinCtrl = fs.FloatSpin(self, -1,
            min_val=0, max_val=999999, increment=100, value=self.configJogFeedRate,
            size=(stepButtonSize[0]*3, -1), agwStyle=fs.FS_LEFT)

        self.feedRateSpinCtrl.SetFormat("%f")
        self.feedRateSpinCtrl.SetDigits(0)
        self.feedRateSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        gbJogSpindleGridSizer.Add(self.feedRateSpinCtrl, pos=(
            1, 0), span=(1, 3), flag=wx.ALIGN_CENTER_VERTICAL)

        # add spindle speed controls
        spinText = wx.StaticText(self, -1, "Spindle (rpm)")
        gbJogSpindleGridSizer.Add(spinText, pos=(
            2, 0), span=(1, 2), flag=wx.TOP, border=5)

        self.spindleSpeedSpinCtrl = fs.FloatSpin(self, -1,
            min_val=0, max_val=99999, increment=100, value=self.configSpindleSpeed,
            size=(stepButtonSize[0]*3, -1), agwStyle=fs.FS_LEFT)
        self.spindleSpeedSpinCtrl.SetFormat("%f")
        self.spindleSpeedSpinCtrl.SetDigits(0)
        self.spindleSpeedSpinCtrl.SetToolTip(wx.ToolTip(
            "Shift + mouse wheel = 2 * increment\n"
            "Ctrl + mouse wheel = 10 * increment\n"
            "Alt + mouse wheel = 100 * increment"))
        gbJogSpindleGridSizer.Add(self.spindleSpeedSpinCtrl, pos=(
            3, 0), span=(1, 3), flag=wx.ALIGN_CENTER_VERTICAL)

        gbzJoggingGridSizer.Add(gbJogSpindleGridSizer,
                                pos=(3, 4), span=(2, 3))

        # add Zero and go to Zero buttons
        self.SetToZeroButton = wx.BitmapButton(self, -1, ico.imgSetToZero.GetBitmap(),
            size=buttonSize, style=wx.BORDER_NONE)
        self.SetToZeroButton.SetToolTip(wx.ToolTip("Set all axis to zero"))
        self.Bind(wx.EVT_BUTTON, self.OnSetToZero, self.SetToZeroButton)
        gbzJoggingGridSizer.Add(self.SetToZeroButton, pos=(0, 4))

        self.SetToZeroXYButton = wx.BitmapButton(self, -1, ico.imgSetToZeroXY.GetBitmap(),
            size=buttonSize, style=wx.BORDER_NONE)
        self.SetToZeroXYButton.SetToolTip(
            wx.ToolTip("Set X and Y axis to zero"))
        self.Bind(wx.EVT_BUTTON, self.OnSetToZeroXY, self.SetToZeroXYButton)
        gbzJoggingGridSizer.Add(self.SetToZeroXYButton, pos=(0, 5))

        self.SetToZeroZButton = wx.BitmapButton(self, -1, ico.imgSetToZeroZ.GetBitmap(),
            size=buttonSize, style=wx.BORDER_NONE)
        self.SetToZeroZButton.SetToolTip(wx.ToolTip("Set Z axis to zero"))
        self.Bind(wx.EVT_BUTTON, self.OnSetToZeroZ, self.SetToZeroZButton)
        gbzJoggingGridSizer.Add(self.SetToZeroZButton, pos=(0, 6))

        self.GoToZeroXYButton = wx.BitmapButton(self, -1, ico.imgGoToZeroXY.GetBitmap(),
            size=buttonSize, style=wx.BORDER_NONE)
        self.GoToZeroXYButton.SetToolTip(wx.ToolTip("Move XY axis to zero"))
        self.Bind(wx.EVT_BUTTON, self.OnGoToZeroXY, self.GoToZeroXYButton)
        gbzJoggingGridSizer.Add(self.GoToZeroXYButton, pos=(1, 1))

        # Probe buttons
        self.probeZButton = wx.BitmapButton(self, -1, ico.imgProbeZ.GetBitmap(),
                                            size=buttonSize, style=wx.BORDER_NONE)
        self.probeZButton.SetToolTip(wx.ToolTip("Probe Z"))
        self.Bind(wx.EVT_BUTTON, self.OnProbeZ, self.probeZButton)
        gbzJoggingGridSizer.Add(self.probeZButton, pos=(1, 6))

        return gbzJoggingGridSizer

    def CreatePositionStatusControls(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # add status controls
        spinText = wx.StaticText(self, -1, "Jog status  ")
        vBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL)

        flexGridSizer = wx.FlexGridSizer(5, 2, 1, 3)
        vBoxSizer.Add(flexGridSizer, 0, flag=wx.ALL | wx.EXPAND, border=5)

        # Add X pos
        st = wx.StaticText(self, label="X")
        self.jX = wx.TextCtrl(self, value=gc.ZERO_STRING)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.jX, 1, flag=wx.EXPAND)

        # Add Y Pos
        st = wx.StaticText(self, label="Y")
        self.jY = wx.TextCtrl(self, value=gc.ZERO_STRING)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.jY, 1, flag=wx.EXPAND)

        # Add Z Pos
        st = wx.StaticText(self, label="Z")
        self.jZ = wx.TextCtrl(self, value=gc.ZERO_STRING)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.jZ, 1, flag=wx.EXPAND)

        # Add Spindle status
        st = wx.StaticText(self, label="SP")
        self.jSpindle = wx.TextCtrl(
            self, value=gc.OFF_STRING, style=wx.TE_READONLY)
        self.jSpindle.SetBackgroundColour(gc.READ_ONLY_BK_COLOR)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.jSpindle, 1, flag=wx.EXPAND)

        st = wx.StaticText(self, label="CO")
        self.jCoolant = wx.TextCtrl(
            self, value=gc.OFF_STRING, style=wx.TE_READONLY)
        self.jCoolant.SetBackgroundColour(gc.READ_ONLY_BK_COLOR)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.jCoolant, 1, flag=wx.EXPAND)

        # Add check box for sync with work position
        self.useWorkPosCheckBox = wx.CheckBox(self, label="Auto MPOS")
        self.useWorkPosCheckBox.SetValue(self.configAutoMPOS)
        self.useWorkPosCheckBox.SetToolTip(
            wx.ToolTip("Use Machine position to update Jogging position, "
                       "jogging operation use these values to operate"))
        self.Bind(wx.EVT_CHECKBOX, self.OnUseMachineWorkPosition,
                  self.useWorkPosCheckBox)
        vBoxSizer.Add(self.useWorkPosCheckBox)

        # Add check box for numeric keypad pendant
        self.numKeypadPendantCheckBox = wx.CheckBox(
            self, label="NumKeypad pen")
        self.numKeypadPendantCheckBox.SetValue(self.configNumKeypadPendant)
        self.numKeypadPendantCheckBox.SetToolTip(
            wx.ToolTip("Enables numeric keypad as pendant"))
        self.Bind(wx.EVT_CHECKBOX, self.OnNumKeypadPendant,
                  self.numKeypadPendantCheckBox)
        vBoxSizer.Add(self.numKeypadPendantCheckBox)

        # Add check box for Z moves last
        self.zJogMovesLastCheckBox = wx.CheckBox(self, label="Z jog safe move")
        self.zJogMovesLastCheckBox.SetValue(self.configZJogSafeMove)
        self.zJogMovesLastCheckBox.SetToolTip(
            wx.ToolTip("when enabled, if Z_destination is grater Z_current, Z axis moves first, and vise-versa"))
        self.Bind(wx.EVT_CHECKBOX, self.OnZJogSafeMove,
                  self.zJogMovesLastCheckBox)
        vBoxSizer.Add(self.zJogMovesLastCheckBox)

        return vBoxSizer

    def CreateGotoAndResetControls(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # Add radio buttons
        spinText = wx.StaticText(self, -1, "Select axis (f)")
        vBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL)

        vRadioBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.xCheckBox = wx.CheckBox(self, label='X')
        vRadioBoxSizer.Add(self.xCheckBox, flag=wx.LEFT | wx.EXPAND, border=5)
        self.Bind(wx.EVT_CHECKBOX, self.OnXCheckBox, self.xCheckBox)

        self.yCheckBox = wx.CheckBox(self, label='Y')
        vRadioBoxSizer.Add(self.yCheckBox, flag=wx.LEFT | wx.EXPAND, border=5)
        self.Bind(wx.EVT_CHECKBOX, self.OnYCheckBox, self.yCheckBox)

        self.zCheckBox = wx.CheckBox(self, label='Z')
        vRadioBoxSizer.Add(self.zCheckBox, flag=wx.LEFT | wx.EXPAND, border=5)
        self.Bind(wx.EVT_CHECKBOX, self.OnZCheckBox, self.zCheckBox)

        self.allCheckBox = wx.CheckBox(self, label='All')
        vRadioBoxSizer.Add(self.allCheckBox, flag=wx.LEFT |
                           wx.EXPAND, border=5)
        self.Bind(wx.EVT_CHECKBOX, self.OnAllCheckBox, self.allCheckBox)

        vBoxSizer.Add(vRadioBoxSizer, 0,
                      flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER)

        # Add Buttons
        spinText = wx.StaticText(self, -1, "Operation on (f)")
        vBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL |
                      wx.TOP | wx.EXPAND, border=5)

        # Add reset and move to zero(0) buttons
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.resetToZeroButton = wx.Button(self, label="f = 0")
        self.resetToZeroButton.SetToolTip(wx.ToolTip("Set f axis to zero(0)"))
        self.Bind(wx.EVT_BUTTON, self.OnResetToZero, self.resetToZeroButton)
        hBoxSizer.Add(self.resetToZeroButton, flag=wx.TOP |
                      wx.EXPAND)  # , border=5)

        self.gotoToZeroButton = wx.Button(self, label="f -> 0")
        self.gotoToZeroButton.SetToolTip(wx.ToolTip("Move f axis to zero(0)"))
        self.Bind(wx.EVT_BUTTON, self.OnGoToZero, self.gotoToZeroButton)
        hBoxSizer.Add(self.gotoToZeroButton, flag=wx.TOP |
                      wx.EXPAND)  # , border=5)

        vBoxSizer.Add(hBoxSizer, flag=wx.TOP | wx.EXPAND, border=5)

        # Add reset and move to jog buttons
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.resetToJogButton = wx.Button(self, label="f = Jog(f)")
        self.resetToJogButton.SetToolTip(
            wx.ToolTip("Set f axis to Jog(f) current value"))
        self.Bind(wx.EVT_BUTTON, self.OnResetToJogVal, self.resetToJogButton)
        hBoxSizer.Add(self.resetToJogButton, flag=wx.TOP |
                      wx.EXPAND)  # , border=5)

        self.gotoToJogButton = wx.Button(self, label="f -> Jog(f)")
        self.gotoToJogButton.SetToolTip(wx.ToolTip(
            "Move f axis to Jog(f) current value"))
        self.Bind(wx.EVT_BUTTON, self.OnGoToJogVal, self.gotoToJogButton)
        hBoxSizer.Add(self.gotoToJogButton, flag=wx.TOP |
                      wx.EXPAND)  # , border=5)

        vBoxSizer.Add(hBoxSizer, flag=wx.TOP | wx.EXPAND)  # , border=5)

        # Add move home buttons
        self.gotoToHomeButton = wx.Button(self, label="f -> Home")
        self.gotoToHomeButton.SetToolTip(wx.ToolTip("Move f axis HOME"))
        self.Bind(wx.EVT_BUTTON, self.OnGoHome, self.gotoToHomeButton)
        vBoxSizer.Add(self.gotoToHomeButton, flag=wx.TOP |
                      wx.EXPAND)  # , border=5)

        # Jog memory functions
        spinText = wx.StaticText(self, -1, "Jog memory")
        vBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL |
                      wx.TOP | wx.BOTTOM | wx.EXPAND, border=5)

        # add save and restore position buttons
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.savePositionButton = wx.Button(self, label="SAV POS")
        self.savePositionButton.SetToolTip(
            wx.ToolTip("Save current jog position"))
        self.Bind(wx.EVT_BUTTON, self.OnSaveJogPosition,
                  self.savePositionButton)
        hBoxSizer.Add(self.savePositionButton, flag=wx.TOP |
                      wx.EXPAND)  # , border=5)

        self.restorePositionButton = wx.Button(self, label="RES POS")
        self.restorePositionButton.SetToolTip(
            wx.ToolTip("Move axises to saved position"))
        self.Bind(wx.EVT_BUTTON, self.OnRestoreJogPosition,
                  self.restorePositionButton)
        hBoxSizer.Add(self.restorePositionButton,
                      flag=wx.TOP | wx.EXPAND)  # , border=5)

        vBoxSizer.Add(hBoxSizer, flag=wx.EXPAND)

        # add jog position memory stack
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.pushStackButton = wx.Button(self, label="+", size=(30, -1))
        self.pushStackButton.SetToolTip(
            wx.ToolTip("Adds current jog position values to jog memory stack"))
        self.Bind(wx.EVT_BUTTON, self.OnPushStack, self.pushStackButton)
        hBoxSizer.Add(self.pushStackButton, flag=wx.ALIGN_CENTER_VERTICAL)

        self.jogMemoryStackComboBox = wx.combo.BitmapComboBox(self, -1, value="", size=(10, -1),
                                                              choices=[], style=wx.CB_READONLY | wx.CB_DROPDOWN | wx.TAB_TRAVERSAL)
        self.jogMemoryStackComboBox.SetToolTip(wx.ToolTip("jog memory stack"))
        self.Bind(wx.EVT_COMBOBOX, self.OnPopStack,
                  self.jogMemoryStackComboBox)
        hBoxSizer.Add(self.jogMemoryStackComboBox, 3,
                      flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        vBoxSizer.Add(hBoxSizer, flag=wx.EXPAND)

        return vBoxSizer

    def CreateUtilControls(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        spinText = wx.StaticText(self, -1, "Custom buttons")
        vBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL)

        # add custom buttons
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.custom1Button = wx.Button(self, label=self.configCustom1Label)
        self.custom1Button.SetToolTip(
            wx.ToolTip("Move to pre-defined position (1)"))
        self.Bind(wx.EVT_BUTTON, self.OnCustom1Button, self.custom1Button)
        hBoxSizer.Add(self.custom1Button, flag=wx.TOP | wx.EXPAND, border=5)

        self.custom2Button = wx.Button(self, label=self.configCustom2Label)
        self.custom2Button.SetToolTip(
            wx.ToolTip("Move to pre-defined position (2)"))
        self.Bind(wx.EVT_BUTTON, self.OnCustom2Button, self.custom2Button)
        hBoxSizer.Add(self.custom2Button, flag=wx.TOP | wx.EXPAND, border=5)

        self.custom3Button = wx.Button(self, label=self.configCustom3Label)
        self.custom3Button.SetToolTip(
            wx.ToolTip("Move to pre-defined position (3)"))
        self.Bind(wx.EVT_BUTTON, self.OnCustom3Button, self.custom3Button)
        hBoxSizer.Add(self.custom3Button, flag=wx.TOP | wx.EXPAND, border=5)

        self.custom4Button = wx.Button(self, label=self.configCustom4Label)
        self.custom4Button.SetToolTip(
            wx.ToolTip("Move to pre-defined position (4)"))
        self.Bind(wx.EVT_BUTTON, self.OnCustom4Button, self.custom4Button)
        hBoxSizer.Add(self.custom4Button, flag=wx.TOP | wx.EXPAND, border=5)

        vBoxSizer.Add(hBoxSizer, flag=wx.EXPAND)

        return vBoxSizer

    def AxisJog(self, staticControl, axis, opAdd):
        """ Jog given axis, by selected step
        """
        dictAxisCoor = {}

        fAxisPos = self.stepSpinCtrl.GetValue()

        if self.configJogInteractive and self.jogInteractiveState:
            # make this a very large number, we will jog will be
            # cancel when user lets go of key
            fAxisPos = 10000

        if opAdd:
            pass
        else:
            fAxisPos = -1 * fAxisPos

        fAxisStrPos = gc.NUMBER_FORMAT_STRING % (fAxisPos)

        dictAxisCoor[str(axis).lower()] = fAxisStrPos

        if self.configJogRapid:
            gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE
        else:
            gc_cmd = gc.EV_CMD_JOG_MOVE_RELATIVE
            dictAxisCoor['feed'] = self.feedRateSpinCtrl.GetValue()

        self.mainWindow.eventForward2Machif(gc_cmd, dictAxisCoor)

    def OnAllCheckBox(self, evt):
        self.xCheckBox.SetValue(evt.IsChecked())
        self.yCheckBox.SetValue(evt.IsChecked())
        self.zCheckBox.SetValue(evt.IsChecked())

    def OnXCheckBox(self, evt):
        if evt.IsChecked() and self.yCheckBox.IsChecked() and self.zCheckBox.IsChecked():
            self.allCheckBox.SetValue(True)
        else:
            self.allCheckBox.SetValue(False)

    def OnYCheckBox(self, evt):
        if evt.IsChecked() and self.xCheckBox.IsChecked() and self.zCheckBox.IsChecked():
            self.allCheckBox.SetValue(True)
        else:
            self.allCheckBox.SetValue(False)

    def OnZCheckBox(self, evt):
        if evt.IsChecked() and self.xCheckBox.IsChecked() and self.yCheckBox.IsChecked():
            self.allCheckBox.SetValue(True)
        else:
            self.allCheckBox.SetValue(False)

    def OnXPos(self, e):
        self.AxisJog(self.jX, "X", opAdd=True)

    def OnXNeg(self, e):
        self.AxisJog(self.jX, "X", opAdd=False)

    def OnYPos(self, e):
        self.AxisJog(self.jY, "Y", opAdd=True)

    def OnYNeg(self, e):
        self.AxisJog(self.jY, "Y", opAdd=False)

    def OnZPos(self, e):
        self.AxisJog(self.jZ, "Z", opAdd=True)

    def OnZNeg(self, e):
        self.AxisJog(self.jZ, "Z", opAdd=False)

    def OnSpindleCWOn(self, e):
        self.jSpindle.SetValue(gc.ON_STRING)
        speed = self.spindleSpeedSpinCtrl.GetValue()
        spped_cmd = "".join([gc.DEVICE_CMD_SPINDLE_CW_ON,
                             " S", "%d" % round(speed), "\n"])
        self.mainWindow.SerialWrite(spped_cmd)

    def OnSpindleCCWOn(self, e):
        self.jSpindle.SetValue(gc.ON_STRING)
        speed = self.spindleSpeedSpinCtrl.GetValue()
        spped_cmd = "".join([gc.DEVICE_CMD_SPINDLE_CCW_ON,
                             " S", "%d" % round(speed), "\n"])
        self.mainWindow.SerialWrite(spped_cmd)

    def OnSpindleOff(self, e):
        self.jSpindle.SetValue(gc.OFF_STRING)
        self.mainWindow.SerialWrite(
            "".join([gc.DEVICE_CMD_SPINDLE_OFF, "\n"]))

    def OnCoolantOn(self, e):
        self.jCoolant.SetValue(gc.ON_STRING)
        self.mainWindow.SerialWrite(
            "".join([gc.DEVICE_CMD_COOLANT_ON, "\n"]))

    def OnCoolantOff(self, e):
        self.jCoolant.SetValue(gc.OFF_STRING)
        self.mainWindow.SerialWrite(
            "".join([gc.DEVICE_CMD_COOLANT_OFF, "\n"]))

    def OnProbeZ(self, e):
        mim = mi.GetMachIfModule(self.stateData.machIfId)

        self.mainWindow.SerialWrite(
            "".join([
                mim.getProbeAxisCmd(),
                " Z%f" % self.configProbeMaxDistance,
                " F%f" % self.configProbeFeedRate,
                "\n"]))

        self.mainWindow.SerialWrite(
            "".join([
                mim.getSetAxisCmd(),
                " Z%f" % self.configProbeDistance,
                "\n"]))

    def OnHomeX(self, e):
        """ Home X axis
        """
        dictAxisCoor = {'x':0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_HOME, dictAxisCoor)

    def OnHomeY(self, e):
        """ Home Y axis
        """
        dictAxisCoor = {'y':0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_HOME, dictAxisCoor)

    def OnHomeZ(self, e):
        """ Home Z axis
        """
        dictAxisCoor = {'z':0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_HOME, dictAxisCoor)

    def OnHomeXY(self, e):
        """ Home X and Y axis
        """
        dictAxisCoor = {'x': 0, 'y': 0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_HOME, dictAxisCoor)

    def OnHome(self, e):
        """ Home machine
        """
        dictAxisCoor = {'x': 0, 'y': 0, 'z': 0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_HOME, dictAxisCoor)

    def OnSetToZero(self, e):
        """ Sets axis X, Y and Z to 0
        """
        dictAxisCoor = {'x': 0, 'y': 0, 'z': 0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_SET_AXIS, dictAxisCoor)

    def OnSetToZeroXY(self, e):
        """ Sets axis X and Y to 0
        """
        dictAxisCoor = {'x': 0, 'y': 0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_SET_AXIS, dictAxisCoor)

    def OnSetToZeroZ(self, e):
        """ Sets axis Z to 0
        """
        dictAxisCoor = {'z': 0}
        self.mainWindow.eventForward2Machif(gc.EV_CMD_SET_AXIS, dictAxisCoor)

    def OnGoToZeroXY(self, e):
        """ Jogs axis X and Y to 0
        """
        dictAxisCoor = {'x': 0, 'y': 0}

        if self.configJogRapid:
            gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
        else:
            gc_cmd = gc.EV_CMD_JOG_MOVE
            dictAxisCoor['feed'] = self.feedRateSpinCtrl.GetValue()

        self.mainWindow.eventForward2Machif(gc_cmd, dictAxisCoor)

    def OnSetStepSize(self, e):
        buttonById = self.FindWindowById(e.GetId())
        self.stepSpinCtrl.SetValue(float(buttonById.GetLabel()))
        # self.stepSpinCtrl.SetValue(buttonById.GetLabel())

    def OnUseMachineWorkPosition(self, e):
        self.configAutoMPOS = e.IsChecked()

    '''
    def OnJogInteractive(self, e):
        self.configJogInteractive = e.IsChecked()
    '''

    def OnJogRapid(self, e):
        self.configJogRapid = e.IsChecked()

    def OnNumKeypadPendant(self, e):
        self.configNumKeypadPendant = e.IsChecked()

    def OnZJogSafeMove(self, e):
        self.configZJogSafeMove = e.IsChecked()

    def OnJogCmd(self, xval, yval, zval, machif_cmd):
        """ Utility function, for jog commands
        """
        dictAxisCoor = {}

        if self.xCheckBox.GetValue() or self.allCheckBox.GetValue():
            dictAxisCoor['x'] = xval

        if self.yCheckBox.GetValue() or self.allCheckBox.GetValue():
            dictAxisCoor['y'] = yval

        if self.zCheckBox.GetValue() or self.allCheckBox.GetValue():
            dictAxisCoor['z'] = zval

        if gc.EV_CMD_JOG_MOVE == machif_cmd or \
            gc.EV_CMD_JOG_MOVE_RELATIVE == machif_cmd:
            dictAxisCoor['feed'] = self.feedRateSpinCtrl.GetValue()

        if self.configZJogSafeMove and 'z' in dictAxisCoor and \
            (gc.EV_CMD_JOG_MOVE == machif_cmd or \
            gc.EV_CMD_JOG_RAPID_MOVE == machif_cmd or \
            gc.EV_CMD_JOG_MOVE_RELATIVE == machif_cmd or \
            gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE == machif_cmd):
            # figure out where we going and if we need to move
            # z axis first or last... basic assumptions...
            # if relative move a -z move means move Z last
            # if relative move a +z move means move Z first
            # if move, compare machine Z to new Z destination
            #    if Z < machine Z, move Z last
            #    if Z > machine Z, move Z first
            move_z_last = False

            if gc.EV_CMD_JOG_MOVE_RELATIVE == machif_cmd or \
            gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE == machif_cmd:
                if float(dictAxisCoor['z']) < 1:
                    move_z_last = True
                elif float(dictAxisCoor['z']) > 1:
                    move_z_last = False

            elif gc.EV_CMD_JOG_MOVE == machif_cmd or \
            gc.EV_CMD_JOG_RAPID_MOVE == machif_cmd:
                if float(dictAxisCoor['z']) < self.machPosZ:
                    move_z_last = True
                elif float(dictAxisCoor['z']) > self.machPosZ:
                    move_z_last = False

            dictZ = {'z': dictAxisCoor['z']}
            if 'feed' in dictAxisCoor:
                dictZ['feed'] = dictAxisCoor['feed']

            dictXY = {}
            if 'x' in dictAxisCoor:
                dictXY['x'] = dictAxisCoor['x']

                if 'feed' in dictAxisCoor:
                    dictXY['feed'] = dictAxisCoor['feed']

            if 'y' in dictAxisCoor:
                dictXY['y'] = dictAxisCoor['y']
                if 'feed' in dictAxisCoor:
                    dictXY['feed'] = dictAxisCoor['feed']

            if move_z_last:
                if dictXY.keys():
                    self.mainWindow.eventForward2Machif(machif_cmd, dictXY)

                self.mainWindow.eventForward2Machif(machif_cmd, dictZ)

            else:
                self.mainWindow.eventForward2Machif(machif_cmd, dictZ)

                if dictXY.keys():
                    self.mainWindow.eventForward2Machif(machif_cmd, dictXY)

        else:
            if 'x' in dictAxisCoor or 'y' in dictAxisCoor or  \
                'z' in dictAxisCoor or 'a' in dictAxisCoor or \
                'b' in dictAxisCoor or 'c' in dictAxisCoor:
                self.mainWindow.eventForward2Machif(machif_cmd, dictAxisCoor)

    def OnResetToZero(self, e):
        """ Reset machine selected axis to zero position
        """
        self.OnJogCmd(
            gc.ZERO_STRING, gc.ZERO_STRING, gc.ZERO_STRING, gc.EV_CMD_SET_AXIS
        )

        if self.configReqUpdateOnJogSetOp:
            self.mainWindow.GetMachineStatus()

    def OnGoToZero(self, e):
        """ Jogs machine selected axis to zero position
        """
        if self.configJogRapid:
            gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
        else:
            gc_cmd = gc.EV_CMD_JOG_MOVE

        self.OnJogCmd(gc.ZERO_STRING, gc.ZERO_STRING, gc.ZERO_STRING, gc_cmd)

    def OnResetToJogVal(self, e):
        """ Reset machine selected axis to user input job values
        """
        self.OnJogCmd(
            self.jX.GetValue(), self.jY.GetValue(), self.jZ.GetValue(),
            gc.EV_CMD_SET_AXIS
        )

        if self.configReqUpdateOnJogSetOp:
            self.mainWindow.GetMachineStatus()

    def OnGoToJogVal(self, e):
        """ Jogs machine selected axis to user input job values
        """
        if self.configJogRapid:
            gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
        else:
            gc_cmd = gc.EV_CMD_JOG_MOVE

        self.OnJogCmd(
            self.jX.GetValue(), self.jY.GetValue(), self.jZ.GetValue(),
            gc_cmd
        )

    def OnGoHome(self, e):
        """ Needs work not all controls can home each axis
            for example example grbl
        """
        self.OnJogCmd(gc.ZERO_STRING, gc.ZERO_STRING, gc.ZERO_STRING,
                      gc.EV_CMD_HOME)

    def OnSaveJogPosition(self, e):
        xVal = self.jX.GetValue()
        yVal = self.jY.GetValue()
        zVal = self.jZ.GetValue()

        self.SavedJogPos = (xVal, yVal, zVal)

        if self.stateData is not None:
            if self.stateData.serialPortIsOpen and not self.stateData.swState == gc.STATE_RUN:
                self.restorePositionButton.Enable()

    def OnRestoreJogPosition(self, e):
        if self.configJogRapid:
            gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
        else:
            gc_cmd = gc.EV_CMD_JOG_MOVE

        self.OnJogCmd(self.SavedJogPos[0], self.SavedJogPos[1],
            self.SavedJogPos[2], gc_cmd
        )

    def OnPushStack(self, e):
        xVal = self.jX.GetValue()
        yVal = self.jY.GetValue()
        zVal = self.jZ.GetValue()

        self.jogMemoryStackComboBox.Append("X%s,Y%s,Z%s" % (xVal, yVal, zVal))

    def OnPopStack(self, e):
        strXYZ = self.jogMemoryStackComboBox.GetValue()
        self.jX.SetValue(re.search("X(\S+),Y", strXYZ).group(1))
        self.jY.SetValue(re.search("Y(\S+),Z", strXYZ).group(1))
        self.jZ.SetValue(re.search("Z(\S+)", strXYZ).group(1))

    def OnCustomButton(self, script):
        scriptLines = script.splitlines()

        if len(scriptLines) > 0:
            for scriptLine in scriptLines:
                scriptLine = "".join([scriptLine, "\n"])
                self.mainWindow.SerialWrite(scriptLine)

    def OnCustom1Button(self, e):
        self.OnCustomButton(self.configCustom1Script)

    def OnCustom2Button(self, e):
        self.OnCustomButton(self.configCustom2Script)

    def OnCustom3Button(self, e):
        self.OnCustomButton(self.configCustom3Script)

    def OnCustom4Button(self, e):
        self.OnCustomButton(self.configCustom4Script)

    def OnRefresh(self, e):
        pass

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
        elif keyCode in self.numKeypadPendantKeys:
            self.OnKeyPress(e)
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

    def OnKeyTimer(self, e):
        # print "Got Timer"
        # print "expire", int(round(time.time() * 1000))
        self.keyCache = None

        if self.jogInteractiveState:
            gc_cmd = gc.EV_CMD_JOG_STOP
            self.mainWindow.eventForward2Machif(gc_cmd)
            self.jogInteractiveState = False

    def OnKeyPress(self, e):
        '''
        http://docs.wxwidgets.org/3.1/defs_8h.html#a41c4609211685cff198618963ec8f77d
        #print wx.WXK_NUMLOCK
        #print wx.WXK_SCROLL
        #print wx.WXK_NUMPAD_BEGIN (5 on keypad when num lock is off)
        '''
        if not self.configNumKeypadPendant:
            e.Skip()
            return

        #evObj = e.GetEventObject()

        # if (not self.keybaordJoggingEnable) or (self.cliComboBox == evObj):
        # if evObj in [self.cliComboBox, self.stepSpinCtrl.GetTextCtrl(),
        #   self.spindleSpeedSpinCtrl.GetTextCtrl(), self.jX, self.jY, self.jZ]:
        #   e.Skip()
        if False:
            pass
        else:

            key = e.GetKeyCode()

            # print dir(e)
            # print e.GetModifiers()

            if self.configJogInteractive:
                if self.keyCache is None:
                    self.keyTimer.Start(milliseconds = 100, oneShot = True)
                    self.keyCache = key
                elif self.keyCache == key and not self.jogInteractiveState:
                    self.keyTimer.Start(milliseconds = 100, oneShot = True)
                    self.jogInteractiveState = True
                elif self.keyCache == key and self.jogInteractiveState:
                    self.keyTimer.Start(milliseconds = 100, oneShot = True)
                    return
                else:
                    print "Oops!! key change too fast, not sure what to do"
                    self.keyTimer.Start(milliseconds = 1, oneShot = True)

            if (key == wx.WXK_NUMPAD_UP):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.positiveYButton.GetId())
                self.positiveYButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnYPos(e)

            elif (key == wx.WXK_NUMPAD_DOWN):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.negativeYButton.GetId())
                self.negativeYButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnYNeg(e)

            elif (key == wx.WXK_NUMPAD_LEFT):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.negativeXButton.GetId())
                self.negativeXButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnXNeg(e)

            elif (key == wx.WXK_NUMPAD_RIGHT):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.positiveXButton.GetId())
                self.positiveXButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnXPos(e)

            elif (key == wx.WXK_NUMPAD_HOME):
                #evt = wx.PyCommandEvent(wx.EVT_BUTTON.typeId, self.homeButton.GetId())
                # self.homeButton.SetFocus()
                #wx.PostEvent(self, evt)
                # self.OnHome(e)
                # pass
                self.mainWindow.OnMachineCycleStart(e)

            elif (key == wx.WXK_NUMPAD_PAGEUP):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.positiveZButton.GetId())
                self.positiveZButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnZPos(e)

            elif (key == wx.WXK_NUMPAD_PAGEDOWN):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.negativeZButton.GetId())
                self.negativeZButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnZNeg(e)

            elif (key == wx.WXK_NUMPAD_END):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.SetToZeroXYButton.GetId())
                self.SetToZeroXYButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnSetToZeroXY(e)

            elif (key == wx.WXK_NUMPAD_BEGIN):  # number "5" on keypad when not in numlock
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.GoToZeroXYButton.GetId())
                self.GoToZeroXYButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnGoToZeroXY(e)

            elif (key == wx.WXK_NUMPAD_INSERT):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.SetToZeroButton.GetId())
                self.SetToZeroButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnSetToZero(e)

            elif (key == wx.WXK_NUMPAD_DELETE):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.SetToZeroZButton.GetId())
                self.SetToZeroZButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnSetToZero(e)

            elif (key == wx.WXK_NUMPAD_DIVIDE):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.homeButton.GetId())
                self.homeButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnHome(e)

            elif (key == wx.WXK_NUMPAD_MULTIPLY):
                canRun = self.mainWindow.OnRunHelper()

                if canRun:
                    self.mainWindow.OnRun()

            elif (key == wx.WXK_NUMPAD_SUBTRACT):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.homeZButton.GetId())
                self.homeZButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnSetToZero(e)

            elif (key == wx.WXK_NUMPAD_ADD):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.probeZButton.GetId())
                self.probeZButton.SetFocus()
                wx.PostEvent(self, evt)
                # self.OnSetToZero(e)

            elif (key == wx.WXK_NUMPAD_ENTER):
                self.mainWindow.OnMachineFeedHold(e)

            elif (key == wx.WXK_NUMPAD_DECIMAL):
                self.mainWindow.OnMachineCycleStart(e)
                pass

            elif (key == wx.WXK_NUMPAD0):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize0p05.GetId())
                self.stepSize0p05.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD1):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize0p1.GetId())
                self.stepSize0p1.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD2):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize0p5.GetId())
                self.stepSize0p5.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD3):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize1.GetId())
                self.stepSize1.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD4):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize5.GetId())
                self.stepSize5.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD5):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize10.GetId())
                self.stepSize10.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD6):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize20.GetId())
                self.stepSize20.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD7):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize50.GetId())
                self.stepSize50.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD8):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize100.GetId())
                self.stepSize100.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMPAD9):
                evt = wx.PyCommandEvent(
                    wx.EVT_BUTTON.typeId, self.stepSize200.GetId())
                self.stepSize200.SetFocus()
                wx.PostEvent(self, evt)

            elif (key == wx.WXK_NUMLOCK):
                #print "NUMLOCK Key Pressed"
                pass

            else:
                pass
                #print key

                e.Skip()

    def onJogEditPaste(self, e):
        if not wx.TheClipboard.IsOpened():
            if wx.TheClipboard.Open():
                if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_TEXT)):
                    data = wx.TextDataObject()
                    wx.TheClipboard.GetData(data)
                    data = data.GetText()

                    reVal = re.search(
                        r'X\s*([+-]{0,1}\d+\.\d+)', data, re.I | re.M)
                    if reVal is not None:
                        self.jX.SetValue(reVal.group(1))

                    reVal = re.search(
                        r'Y\s*([+-]{0,1}\d+\.\d+)', data, re.I | re.M)
                    if reVal is not None:
                        self.jY.SetValue(reVal.group(1))

                    reVal = re.search(
                        r'Z\s*([+-]{0,1}\d+\.\d+)', data, re.I | re.M)
                    if reVal is not None:
                        self.jZ.SetValue(reVal.group(1))

                wx.TheClipboard.Close()
