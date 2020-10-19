"""----------------------------------------------------------------------------
   wnd_machine_config.py

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

import os
import wx
from wx.lib import scrolledpanel as scrolled
import wx.propgrid as wxpg

import modules.config as gc
import modules.machif_config as mi


class gsatMachineSettingsPanel(scrolled.ScrolledPanel):
    """ Machine panel settings
    """

    def __init__(self, parent, config_data, config_remote_data, **args):
        scrolled.ScrolledPanel.__init__(self, parent,
                                        style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data
        self.configRemoteData = config_remote_data
        self.lastSpecificProperty = ""

        if self.configRemoteData is not None:
            self.configData = self.configRemoteData

        self.InitConfig()
        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        # self.FitInside()

    def InitConfig(self):
        self.machIfName = self.configData.get('/machine/Device')
        self.machIfId = mi.GetMachIfId(self.machIfName)
        self.machIfConfig = self.configData.get('/machine/MachIfSpecific')

    def InitUI(self):
        vBoxSizerRoot = wx.BoxSizer(wx.VERTICAL)

        # Add device type select
        flexGridSizer = wx.FlexGridSizer(5, 2, 5, 5)
        flexGridSizer.AddGrowableCol(1)

        st = wx.StaticText(self, label="Device")
        self.deviceComboBox = wx.ComboBox(
            self, -1, value=mi.GetMachIfName(self.machIfId),
            choices=sorted(mi.MACHIF_LIST, key=str.lower),
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER | wx.CB_READONLY
        )
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.deviceComboBox, 1,
                          flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        self.Bind(
            wx.EVT_COMBOBOX, self.OnDeviceComboBoxSelect, self.deviceComboBox)

        # get serial port list and baud rate speeds
        brList = ['1200', '2400', '4800', '9600',
                  '19200', '38400', '57600', '115200']

        # Add serial port controls
        st = wx.StaticText(self, label="Serial Port")
        self.spComboBox = wx.ComboBox(
            self, -1, value=self.configData.get('/machine/Port'),
            choices=['None'], style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER
        )
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.spComboBox, 1, flag=wx.EXPAND |
                          wx.ALIGN_CENTER_VERTICAL)

        self.Bind(
            wx.EVT_COMBOBOX, self.OnSpComboBoxSelect, self.spComboBox)

        # Older version of wx (available in *12.04, 14.04) doesn't support
        # EVT_COMBOBOX_DROPDOWN
        try:
            self.Bind(wx.EVT_COMBOBOX_DROPDOWN, self.OnSpComboBoxDropDown)
        except:
            self.OnSpComboBoxDropDown(None)

        # Add baud rate controls
        st = wx.StaticText(self, label="Baud Rate")
        self.sbrComboBox = wx.ComboBox(
            self, -1, value=self.configData.get('/machine/Baud'),
            choices=brList, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER
        )
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.sbrComboBox, 1, flag=wx.EXPAND |
                          wx.ALIGN_CENTER_VERTICAL)

        # DRO Font
        st = wx.StaticText(self, label="DRO Font")
        self.fontSelect = wx.FontPickerCtrl(self, size=(300, -1))

        self.fontSelect.SetToolTip(
            wx.ToolTip("DRO Font updates after application restart"))

        font = wx.Font(self.configData.get('/machine/DRO/FontSize'),
                       wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0,
                       unicode(self.configData.get('/machine/DRO/FontFace')))

        font_style_str = self.configData.get('/machine/DRO/FontStyle')

        if "bold" in font_style_str:
            font.MakeBold()

        if "italic" in font_style_str:
            font.MakeItalic()

        self.fontSelect.SetSelectedFont(font)

        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(self.fontSelect, 1, flag=wx.EXPAND |
                          wx.ALIGN_CENTER_VERTICAL)

        # add DRO enable axes
        st = wx.StaticText(self, label="DRO Axes")
        hBoxSz = wx.BoxSizer(wx.HORIZONTAL)

        self.cbDroEnX = wx.CheckBox(self, wx.ID_ANY, "X")
        self.cbDroEnX.SetValue(self.configData.get('/machine/DRO/EnableX'))
        self.cbDroEnX.SetToolTip(wx.ToolTip("DRO Enable X axis"))

        self.cbDroEnY = wx.CheckBox(self, wx.ID_ANY, "Y")
        self.cbDroEnY.SetValue(self.configData.get('/machine/DRO/EnableY'))
        self.cbDroEnY.SetToolTip(wx.ToolTip("DRO Enable Y axis"))

        self.cbDroEnZ = wx.CheckBox(self, wx.ID_ANY, "Z")
        self.cbDroEnZ.SetValue(self.configData.get('/machine/DRO/EnableZ'))
        self.cbDroEnZ.SetToolTip(wx.ToolTip("DRO Enable Z axis"))

        self.cbDroEnA = wx.CheckBox(self, wx.ID_ANY, "A")
        self.cbDroEnA.SetValue(self.configData.get('/machine/DRO/EnableA'))
        self.cbDroEnA.SetToolTip(wx.ToolTip("DRO Enable A axis"))

        self.cbDroEnB = wx.CheckBox(self, wx.ID_ANY, "B")
        self.cbDroEnB.SetValue(self.configData.get('/machine/DRO/EnableB'))
        self.cbDroEnB.SetToolTip(wx.ToolTip("DRO Enable B axis"))

        self.cbDroEnC = wx.CheckBox(self, wx.ID_ANY, "C")
        self.cbDroEnC.SetValue(self.configData.get('/machine/DRO/EnableC'))
        self.cbDroEnC.SetToolTip(wx.ToolTip("DRO Enable C axis"))

        hBoxSz.Add(self.cbDroEnX, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        hBoxSz.Add(self.cbDroEnY, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        hBoxSz.Add(self.cbDroEnZ, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        hBoxSz.Add(self.cbDroEnA, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        hBoxSz.Add(self.cbDroEnB, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        hBoxSz.Add(self.cbDroEnC, 0, flag=wx.ALIGN_CENTER_VERTICAL)

        flexGridSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        flexGridSizer.Add(hBoxSz, 0, flag=wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        vBoxSizerRoot.Add(flexGridSizer, 0, flag=wx.EXPAND |
                          wx.TOP | wx.LEFT | wx.RIGHT, border=20)

        self.pg = wxpg.PropertyGrid(self, wx.ID_ANY)
        self.pg.SetExtraStyle(wxpg.PG_EX_HELP_AS_TOOLTIPS)
        self.pg.EnableScrolling(True, True)

        self.pg.Append(wxpg.PropertyCategory("General Settings"))

        prop = "Enable init script"
        self.cbInitScript = self.pg.Append(wxpg.BoolProperty(
            prop, value=self.configData.get('/machine/InitScriptEnable')))
        self.pg.SetPropertyAttribute(prop, "UseCheckbox", True)
        self.pg.SetPropertyHelpString(prop, "Enable initialization script")

        prop = "Enable filter G-codes"
        self.cbFilterGcodes = self.pg.Append(wxpg.BoolProperty(
            prop, value=self.configData.get('/machine/FilterGcodesEnable')))
        self.pg.SetPropertyAttribute(prop, "UseCheckbox", True)
        self.pg.SetPropertyHelpString(
            prop, "When enabled, skip filtered G-codes")

        prop = "Filter G-codes list"
        self.tcFilterGcodes = self.pg.Append(wxpg.StringProperty(
            prop, value=self.configData.get('/machine/FilterGcodes')))
        self.pg.SetPropertyHelpString(
            prop,
            "When enabled, If a line contains one of these G-codes it wil be "
            "skipped (',' separated)")

        self.CreateMachIfSpecificCtrls()

        vBoxSizerRoot.Add(
            self.pg, 1,
            flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, border=20)

        vBoxSizerRoot.AddSpacer(10, -1)

        # add edit control for init script
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        st = wx.StaticText(self, label="Init script")
        vBoxSizer.Add(st, 0, flag=wx.ALIGN_CENTER_VERTICAL)

        self.tcInitScript = wx.TextCtrl(
            self, wx.ID_ANY, "", style=wx.TE_MULTILINE)
        self.tcInitScript.SetValue(self.configData.get('/machine/InitScript'))
        self.tcInitScript.SetToolTip(wx.ToolTip(
            "This script is sent to device upon connect detect"))
        vBoxSizer.Add(self.tcInitScript, 1, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        vBoxSizerRoot.Add(
            vBoxSizer, 2, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=20)

        vBoxSizerRoot.AddSpacer(10, -1)

        self.SetSizer(vBoxSizerRoot)

    def CreateMachIfSpecificCtrls(self):
        ''' Add machif specific config
        '''
        self.machIfConfigCtrl = dict()
        self.machIfConfigDic = self.machIfConfig.get(self.machIfName, {})

        if len(self.machIfConfigDic):

            self.pg.Append(wxpg.PropertyCategory(
                "%s Specific Stettings" % self.machIfName))

            for i in sorted(self.machIfConfigDic.keys()):
                name = self.machIfConfigDic[i]['Name']
                value = self.machIfConfigDic[i]['Value']
                tooltip = self.machIfConfigDic[i].get('ToolTip', "")

                if type(value) == int:
                    cp = self.pg.Append(wxpg.IntProperty(name, value=value))
                    # pg.SetPropertyEditor(name,"SpinCtrl")
                elif type(value) == float:
                    cp = self.pg.Append(wxpg.FloatProperty(name, value=value))
                elif type(value) == bool:
                    cp = self.pg.Append(wxpg.BoolProperty(name, value=value))
                    self.pg.SetPropertyAttribute(name, "UseCheckbox", True)
                elif type(value) == str:
                    cp = self.pg.Append(wxpg.StringProperty(name, value=value))
                else:
                    cp = None
                    self.pg.Append(wxpg.StringProperty(
                        name,
                        value="type not supported: ToDo add type handling"))

                if len(tooltip):
                    self.pg.SetPropertyHelpString(name, tooltip)

                if cp is not None:
                    self.machIfConfigCtrl[i] = cp

        elif len(self.lastSpecificProperty):
            self.pg.DeleteProperty(self.lastSpecificProperty)

        self.lastSpecificProperty = "%s Specific Stettings" % self.machIfName

    def UpdateConfigData(self):
        self.machIfName = self.deviceComboBox.GetValue()
        self.configData.set('/machine/Device', self.machIfName)
        self.configData.set('/machine/Port', self.spComboBox.GetValue())
        self.configData.set('/machine/Baud', self.sbrComboBox.GetValue())

        font = self.fontSelect.GetSelectedFont()
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

        self.configData.set(
            '/machine/DRO/EnableX', self.cbDroEnX.GetValue())
        self.configData.set(
            '/machine/DRO/EnableY', self.cbDroEnY.GetValue())
        self.configData.set(
            '/machine/DRO/EnableZ', self.cbDroEnZ.GetValue())
        self.configData.set(
            '/machine/DRO/EnableA', self.cbDroEnA.GetValue())
        self.configData.set(
            '/machine/DRO/EnableB', self.cbDroEnB.GetValue())
        self.configData.set(
            '/machine/DRO/EnableC', self.cbDroEnC.GetValue())

        self.configData.set(
            '/machine/FilterGcodesEnable', self.cbFilterGcodes.GetValue())

        filterGcodeList = self.tcFilterGcodes.GetValue().split(',')
        filterGcodeList = [x.strip() for x in filterGcodeList]
        filterGcodeList = ",".join(filterGcodeList)
        self.configData.set(
            '/machine/FilterGcodes', filterGcodeList)

        self.configData.set(
            '/machine/InitScriptEnable', self.cbInitScript.GetValue())
        self.configData.set(
            '/machine/InitScript', self.tcInitScript.GetValue())

        if len(self.machIfConfigCtrl):
            for i in self.machIfConfigCtrl:
                value = self.machIfConfigCtrl[i].GetValue()
                self.configData.set(
                    '/machine/MachIfSpecific/%s/%s/Value' % (
                        self.machIfName, i), value)

    def OnDeviceComboBoxSelect(self, event):
        self.machIfName = self.deviceComboBox.GetValue()
        self.CreateMachIfSpecificCtrls()

    def OnSpComboBoxSelect(self, event):
        value = self.spComboBox.GetValue()
        port = value.split(",")[0]
        self.spComboBox.SetValue(port)

    def OnSpComboBoxDropDown(self, event):
        serList = ['None']
        portSearchFailSafe = False

        if self.configRemoteData is not None:
            serList = self.configRemoteData.get('/temp/SerialPorts')
        else:
            try:
                import glob
                import serial.tools.list_ports

                serListInfo = serial.tools.list_ports.comports()

                if len(serListInfo) > 0:
                    if type(serListInfo[0]) == tuple:
                        serList = ["%s, %s, %s" %
                                (i[0], i[1], i[2]) for i in serListInfo]
                    else:
                        serList = ["%s, %s" % (i.device, i.description)
                                for i in serListInfo]

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
                        except serial.SerialException, e:
                            pass
                        except OSError, e:
                            pass
                else:
                    serList = glob.glob('/dev/ttyUSB*') + \
                        glob.glob('/dev/ttyACM*') + \
                        glob.glob('/dev/cu*')

                if len(serList) < 1:
                    serList = ['None']

        self.spComboBox.SetItems(serList)

