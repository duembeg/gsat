"""----------------------------------------------------------------------------
    wnd_machine_config.py

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
import os
import wx
from wx.lib import scrolledpanel as scrolled
import wx.propgrid as pg

import modules.machif_config as mi
import images.icons as ico


class Factory():
    """
    Factory class to init config page

    """

    @staticmethod
    def GetIcon():
        return ico.imgMachine.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatMachineSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Machine")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatMachineSettingsPanel(scrolled.ScrolledPanel):
    """
    Machine settings

    """

    def __init__(self, parent, config_data, **args):
        super(gsatMachineSettingsPanel, self).__init__(parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data

        self.InitConfig()
        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        self.FitInside()

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnLateInit, self.timer)
        self.timer.Start(500, wx.TIMER_ONE_SHOT)

    def InitConfig(self):
        self.axisList = ['X', 'Y', 'Z', 'A', 'B', 'C']
        self.machIfName = self.configData.get('/machine/Device')
        self.machIfId = mi.GetMachIfId(self.machIfName)
        self.machIfConfig = self.configData.get('/machine/MachIfSpecific', {})
        self.machIfProbe = self.configData.get('/machine/Probe', {})

    def InitUI(self):
        vBoxSizerRoot = wx.BoxSizer(wx.VERTICAL)
        hBoxSizerRoot = wx.BoxSizer(wx.HORIZONTAL)

        # Add device type select
        flexGridSizer = wx.FlexGridSizer(5, 2, 5, 5)
        # flexGridSizer.AddGrowableCol(1)

        st = wx.StaticText(self, label="Device")
        self.deviceComboBox = wx.ComboBox(
            self, -1, value=mi.GetMachIfName(self.machIfId),
            choices=sorted(mi.MACHIF_LIST, key=str.lower),
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER | wx.CB_READONLY
        )
        flexGridSizer.Add(st, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.deviceComboBox, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        self.Bind(wx.EVT_COMBOBOX, self.OnDeviceComboBoxSelect, self.deviceComboBox)

        # get serial port list and baud rate speeds
        brList = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200', '230400']

        # Add serial port controls
        st = wx.StaticText(self, label="Serial Port")
        self.spComboBox = wx.ComboBox(
            self, -1, value=self.configData.get('/machine/Port'),
            choices=self.GetListOfSerialPorts(), style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
        flexGridSizer.Add(st, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.spComboBox, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        self.Bind(wx.EVT_COMBOBOX, self.OnSpComboBoxSelect, self.spComboBox)

        # Older version of wx (available in *12.04, 14.04) doesn't support
        # EVT_COMBOBOX_DROPDOWN
        try:
            self.Bind(wx.EVT_COMBOBOX_DROPDOWN, self.OnSpComboBoxDropDown, self.spComboBox)
        except:
            self.OnSpComboBoxDropDown(None)

        # Add baud rate controls
        st = wx.StaticText(self, label="Baud Rate")
        self.sbrComboBox = wx.ComboBox(
            self, -1, value=self.configData.get('/machine/Baud'), choices=brList,
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER
        )
        flexGridSizer.Add(st, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.sbrComboBox, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        hBoxSizerRoot.Add(flexGridSizer, proportion=0, flag=wx.TOP | wx.LEFT | wx.RIGHT | wx.EXPAND, border=20)

        self.pg = pg.PropertyGrid(self, wx.ID_ANY, style=wx.propgrid.PG_BOLD_MODIFIED | wx.propgrid.PG_TOOLTIPS)
        self.pg.SetExtraStyle(pg.PG_EX_HELP_AS_TOOLTIPS)
        self.pg.EnableScrolling(True, True)

        # add machif specific settings
        self.CreateMachIfSpecificCtrls()

        # add DRO settings
        self.CreateMachIfDROCtrls()

        # add general settings
        self.CreateMachIfGeneralCtrls()

        # add probe settings
        self.CreateMachIfProbeCtrls()

        hBoxSizerRoot.Add(self.pg, proportion=2, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, border=20)
        vBoxSizerRoot.Add(hBoxSizerRoot, 1, flag=wx.EXPAND)

        vBoxSizerRoot.AddSpacer(10)

        # add edit control for init script
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        st = wx.StaticText(self, label="Init script")
        vBoxSizer.Add(st, 0)

        self.tcInitScript = wx.TextCtrl(self, wx.ID_ANY, "", style=wx.TE_MULTILINE)
        self.tcInitScript.SetValue(self.configData.get('/machine/InitScript'))
        self.tcInitScript.SetToolTip(wx.ToolTip("This script is sent to device upon connect detect"))
        vBoxSizer.Add(self.tcInitScript, 1, flag=wx.ALL | wx.EXPAND)

        vBoxSizerRoot.Add(vBoxSizer, 1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=20)

        vBoxSizerRoot.AddSpacer(10)

        self.pg.Bind(pg.EVT_PG_CHANGED, self.OnPropertyChanged)

        self.UpdateUI()
        self.SetSizer(vBoxSizerRoot)

    def CreateMachIfDROCtrls(self):
        """
        Add DRO specific config

        """
        # add DRO font and enable axes
        self.pg.Append(pg.PropertyCategory("DRO Settings"))

        font = wx.Font(
            self.configData.get('/machine/DRO/FontSize'), wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0,
            self.configData.get('/machine/DRO/FontFace'))
        font_style_str = self.configData.get('/machine/DRO/FontStyle')

        if "bold" in font_style_str:
            font.MakeBold()
        if "italic" in font_style_str:
            font.MakeItalic()

        prop = "Font"
        self.fontDroProp = self.pg.Append(pg.FontProperty(prop, value=font))
        self.pg.SetPropertyHelpString(prop, "Font used in DRO axis display, requires application restart")

        self.dictDroCbEnableAxis = {}

        for axis in self.axisList:
            prop = f"Enable {axis} axis"
            self.dictDroCbEnableAxis[axis] = self.pg.Append(
                pg.BoolProperty(prop, value=self.configData.get(f'/machine/DRO/Enable{axis}')))
            self.pg.SetPropertyAttribute(prop, "UseCheckbox", True)
            self.pg.SetPropertyHelpString(prop, f"Enable {axis} axis in DRO Panel")

    def CreateMachIfGeneralCtrls(self):
        self.pg.Append(pg.PropertyCategory("General Settings"))

        prop = "Enable init script"
        self.cbInitScript = self.pg.Append(pg.BoolProperty(
            prop, value=self.configData.get('/machine/InitScriptEnable')))
        self.pg.SetPropertyAttribute(prop, "UseCheckbox", True)
        self.pg.SetPropertyHelpString(prop, "Enable initialization script")

        prop = "Enable filter G-codes"
        self.cbFilterGcodes = self.pg.Append(pg.BoolProperty(
            prop, value=self.configData.get('/machine/FilterGcodesEnable')))
        self.pg.SetPropertyAttribute(prop, "UseCheckbox", True)
        self.pg.SetPropertyHelpString(prop, "When enabled, skip filtered G-codes")

        prop = "Filter G-codes list"
        self.tcFilterGcodes = self.pg.Append(
            pg.StringProperty(prop, value=self.configData.get('/machine/FilterGcodes')))
        self.pg.SetPropertyHelpString(
            prop, "When enabled, If a line contains one of these G-codes it wil be skipped (',' separated)")

    def CreateMachIfSpecificCtrls(self):
        """
        Add machif specific config

        """

        self.dictMachineIfProp = {}

        for machine in self.machIfConfig:

            if self.machIfConfig[machine]:
                prop_cat = self.pg.Append(pg.PropertyCategory(f"{machine} Specific Settings"))
                self.dictMachineIfProp[machine] = {}
                self.dictMachineIfProp[machine]['prop_cat'] = prop_cat
                self.dictMachineIfProp[machine]['prop'] = []

            for prop in self.machIfConfig[machine]:
                name = self.machIfConfig[machine][prop]['Name']
                value = self.machIfConfig[machine][prop]['Value']
                tooltip = self.machIfConfig[machine][prop].get('ToolTip', "")

                self.dictMachineIfProp[machine]['prop'].append(prop)

                if isinstance(value, int):
                    self.pg.AppendIn(prop_cat, pg.IntProperty(name, f"{machine}_{prop}", value=value))
                    # pg.SetPropertyEditor(name,"SpinCtrl")
                elif isinstance(value, float):
                    self.pg.AppendIn(prop_cat, pg.FloatProperty(name, f"{machine}_{prop}", value=value))
                elif isinstance(value, bool):
                    self.pg.AppendIn(prop_cat, pg.BoolProperty(name, f"{machine}_{prop}", value=value))
                    self.pg.SetPropertyAttribute(name, "UseCheckbox", True)
                elif isinstance(value, str):
                    self.pg.AppendIn(prop_cat, pg.StringProperty(name, f"{machine}_{prop}", value=value))
                else:
                    self.pg.Append(pg.StringProperty(
                        name, f"{machine}_{prop}", value="type not supported: TODO: add type handling"))

                if len(tooltip):
                    self.pg.SetPropertyHelpString(f"{machine}_{prop}", tooltip)

                self.pg.Grid.FitColumns()

    def CreateMachIfProbeCtrls(self):
        self.probe_cat = self.pg.Append(pg.PropertyCategory("Probe Settings"))

        self.dictProbeProp = {}

        for axis in self.axisList:
            prob_cat = self.pg.AppendIn(self.probe_cat, pg.PropertyCategory(f"{axis} Probe"))

            self.pg.AppendIn(prob_cat, pg.FloatProperty(
                "Offset", f"{axis}O", value=self.machIfProbe.get(axis, {}).get('Offset', 0)))
            self.pg.SetPropertyHelpString(
                f"{axis}O", "Specifies the value of the axis after the probe triggers")

            self.pg.AppendIn(prob_cat, pg.IntProperty(
                "Feed Rate", f"{axis}FR", value=self.machIfProbe.get(axis, {}).get('FeedRate', 0)))
            self.pg.SetPropertyHelpString(
                f"{axis}FR", "Speed at which the probe moves when it is seeking the surface or edge")

            self.pg.AppendIn(prob_cat, pg.FloatProperty(
                "Travel Limit", f"{axis}TL", value=self.machIfProbe.get(axis, {}).get('TravelLimit', 0)))
            self.pg.SetPropertyHelpString(
                f"{axis}TL", "Defines the maximum distance the probe can travel before it stops and gives up")

            self.pg.AppendIn(prob_cat, pg.FloatProperty(
                "Retract Distance", f"{axis}RD", value=self.machIfProbe.get(axis, {}).get('Retract', 0)))
            self.pg.SetPropertyHelpString(
                f"{axis}RD", "Distance the probe will retract after touching the surface or edge")

            self.dictProbeProp[axis] = prob_cat

    def UpdateUI(self):
        """
        Update UI with config data

        """
        for machine in self.dictMachineIfProp:
            if self.machIfName == machine:
                self.pg.HideProperty(self.dictMachineIfProp[machine]['prop_cat'], hide=False)
            else:
                self.pg.HideProperty(self.dictMachineIfProp[machine]['prop_cat'], hide=True)

        for axis in self.axisList:
            if self.dictDroCbEnableAxis[axis].GetValue():
                self.pg.HideProperty(self.dictProbeProp[axis], hide=False)
            else:
                self.pg.HideProperty(self.dictProbeProp[axis], hide=True)

        self.pg.Grid.FitColumns()

    def UpdateConfigData(self):
        self.machIfName = self.deviceComboBox.GetValue()
        self.configData.set('/machine/Device', self.machIfName)
        self.configData.set('/machine/Port', self.spComboBox.GetValue())
        self.configData.set('/machine/Baud', self.sbrComboBox.GetValue())

        # save DRO settings
        font = self.fontDroProp.GetValue()
        font_style_list = []
        font_style_str = ""

        if font.GetWeight() == wx.BOLD:
            font_style_list.append("bold")

        if font.GetStyle() == wx.ITALIC:
            font_style_list.append("italic")

        if len(font_style_list) == 0:
            font_style_str = "normal"
        else:
            font_style_str = ",".join(font_style_list)

        self.configData.set('/machine/DRO/FontFace', font.GetFaceName())
        self.configData.set('/machine/DRO/FontSize', font.GetPointSize())
        self.configData.set('/machine/DRO/FontStyle', font_style_str)

        for axis in self.axisList:
            self.configData.set(f'/machine/DRO/Enable{axis}', self.dictDroCbEnableAxis[axis].GetValue())

        # save general settings
        self.configData.set('/machine/FilterGcodesEnable', self.cbFilterGcodes.GetValue())

        filterGcodeList = self.tcFilterGcodes.GetValue().split(',')
        filterGcodeList = [x.strip() for x in filterGcodeList]
        filterGcodeList = ",".join(filterGcodeList)
        self.configData.set('/machine/FilterGcodes', filterGcodeList)

        self.configData.set('/machine/InitScriptEnable', self.cbInitScript.GetValue())
        self.configData.set('/machine/InitScript', self.tcInitScript.GetValue())

        # save machine specific settings
        for machine in self.dictMachineIfProp:
            for prop in self.dictMachineIfProp[machine].get('prop', []):
                value = self.pg.GetPropertyByName(f"{machine}_{prop}").GetValue()
                self.configData.set(f'/machine/MachIfSpecific/{machine}/{prop}/Value', value)
                # print(f"Set {machine}_{prop} to {value}")

        # save probe settings
        for axis in self.axisList:
            self.configData.set(f'/machine/Probe/{axis}/Offset', self.pg.GetPropertyByName(f"{axis}O").GetValue())
            self.configData.set(f'/machine/Probe/{axis}/FeedRate', self.pg.GetPropertyByName(f"{axis}FR").GetValue())
            self.configData.set(f'/machine/Probe/{axis}/TravelLimit', self.pg.GetPropertyByName(f"{axis}TL").GetValue())
            self.configData.set(f'/machine/Probe/{axis}/Retract', self.pg.GetPropertyByName(f"{axis}RD").GetValue())

    def OnDeviceComboBoxSelect(self, event):
        self.machIfName = self.deviceComboBox.GetValue()
        self.UpdateUI()

    def OnLateInit(self, event):
        # We need to do this to updated width of pull down list
        # if we do it too early the pull down will have the full
        # size of port + description
        serList = self.GetListOfSerialPorts(description=True)
        value = self.spComboBox.GetValue()
        self.spComboBox.SetItems(serList)
        self.spComboBox.SetValue(value)  # restore value

    def OnPropertyChanged(self, event):
        # property = event.GetProperty()
        # print(f"Property {property.GetName()} changed")
        self.UpdateUI()

    def OnSpComboBoxSelect(self, event):
        value = self.spComboBox.GetValue()
        port = value.split(",")[0]
        self.spComboBox.SetValue(port)

    def OnSpComboBoxDropDown(self, event):
        serList = self.GetListOfSerialPorts(description=True)
        value = self.spComboBox.GetValue()
        self.spComboBox.SetItems(serList)
        self.spComboBox.SetValue(value)  # restore value

    def GetListOfSerialPorts(self, description=False):
        portSearchFailSafe = False

        serList = self.configData.get('/temp/SerialPorts')

        if not serList:
            serList = ['None']

            try:
                import glob
                import serial.tools.list_ports

                serListInfo = serial.tools.list_ports.comports()

                if len(serListInfo) > 0:
                    if os.name != 'nt':
                        for ser in serListInfo:
                            if "USB" in ser.device or "ACM" in ser.device or "cu" in ser.device:
                                if description:
                                    serList.append(f"{ser.device}, {ser.description}")
                                else:
                                    serList.append(ser.device)
                    else:
                        if description:
                            serList = [f"{i.device}, {i.description}" for i in serListInfo]
                        else:
                            serList = [i.device for i in serListInfo]

                serList.sort()

            except ImportError:
                portSearchFailSafe = True

            if portSearchFailSafe:
                serList = []

                if os.name == 'nt':
                    # Scan for available ports.
                    for i in range(256):
                        try:
                            serial.Serial(i)
                            serList.append('COM'+str(i + 1))
                        except serial.SerialException:
                            pass
                        except OSError:
                            pass
                else:
                    serList = glob.glob('/dev/ttyUSB*') + \
                        glob.glob('/dev/ttyACM*') + \
                        glob.glob('/dev/cu*')

                if len(serList) < 1:
                    serList = ['None']

        return serList
