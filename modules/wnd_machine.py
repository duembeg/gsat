"""----------------------------------------------------------------------------
   wnd_machine.py

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
import wx
from wx.lib import newevent as newev

import modules.config as gc
import modules.wnd_numeric_entry as ne


class gsatMachineStatusPanel(wx.ScrolledWindow):
    """
        Status information about machine, controls to enable auto and manual
        refresh.

    """

    def __init__(self, parent, config_data, state_data, cmd_line_options, **args):
        wx.ScrolledWindow.__init__(self, parent, **args)
        # scrolled.ScrolledPanel.__init__(self, parent, -1)

        self.mainWindow = parent

        self.configData = config_data
        self.configRemoteData = None
        self.stateData = state_data
        self.cmdLineOptions = cmd_line_options
        self.droObj2AxisDict = {}

        self.machineDataColor = wx.RED

        self.InitConfig()

        self.InitUI()

        self.SetInitialSize()

        # add custom events and handlers
        self.UpdateSettingsEvt, self.EVT_UPDATE_SETTINGS = newev.NewEvent()
        self.Bind(self.EVT_UPDATE_SETTINGS, self.UpdateSettingsHandler)

        self.UpdateSettings()

        width, height = self.GetSize()
        scroll_unit = 10
        self.SetScrollbars(
            scroll_unit, scroll_unit,
            int(width/scroll_unit), int(height/scroll_unit))

    def InitConfig(self):
        self.configDroEnX = self.configData.get('/machine/DRO/EnableX')
        self.configDroEnY = self.configData.get('/machine/DRO/EnableY')
        self.configDroEnZ = self.configData.get('/machine/DRO/EnableZ')
        self.configDroEnA = self.configData.get('/machine/DRO/EnableA')
        self.configDroEnB = self.configData.get('/machine/DRO/EnableB')
        self.configDroEnC = self.configData.get('/machine/DRO/EnableC')
        self.configDroFontFace = self.configData.get('/machine/DRO/FontFace')
        self.configDroFontSize = self.configData.get('/machine/DRO/FontSize')
        self.configDroFontStyle = self.configData.get('/machine/DRO/FontStyle')

    def test(self):
        print(self.GetClientSize())
        print(self.sDroBoxSz.ComputeFittingWindowSize(self))
        print(self.sDroBoxSz.ComputeFittingClientSize(self))

    def UpdateSettings(self, config_data=None, config_remote_data=None):

        if config_data is not None:
            self.configData = config_data

        self.configRemoteData = config_remote_data

        self.InitConfig()

        evt = self.UpdateSettingsEvt()
        wx.PostEvent(self, evt)

    def UpdateSettingsHandler(self, config_data=None):

        if self.configDroEnX:
            self.xPosSt.Show()
            self.xPos.Show()
        else:
            self.xPosSt.Hide()
            self.xPos.Hide()

        if self.configDroEnY:
            self.yPosSt.Show()
            self.yPos.Show()
        else:
            self.yPosSt.Hide()
            self.yPos.Hide()

        if self.configDroEnZ:
            self.zPosSt.Show()
            self.zPos.Show()
        else:
            self.zPosSt.Hide()
            self.zPos.Hide()

        if self.configDroEnA:
            self.aPosSt.Show()
            self.aPos.Show()
        else:
            self.aPosSt.Hide()
            self.aPos.Hide()

        if self.configDroEnB:
            self.bPosSt.Show()
            self.bPos.Show()
        else:
            self.bPosSt.Hide()
            self.bPos.Hide()

        if self.configDroEnC:
            self.cPosSt.Show()
            self.cPos.Show()
        else:
            self.cPosSt.Hide()
            self.cPos.Hide()

        self.UpdateUI(self.stateData)

        fontPos = wx.Font(
            self.configDroFontSize,
            wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0,
            self.configDroFontFace)

        font_style_str = self.configDroFontStyle

        if "bold" in font_style_str:
            fontPos.MakeBold()

        if "italic" in font_style_str:
            fontPos.MakeItalic()

        #self.xPos.SetFont(fontPos)
        #self.yPos.SetFont(fontPos)
        #self.zPos.SetFont(fontPos)
        #self.aPos.SetFont(fontPos)
        #self.bPos.SetFont(fontPos)
        #self.cPos.SetFont(fontPos)

        #self.sDroBoxSz.Fit(self)
        #self.sDroBoxSz.Layout()

        #self.sDroBoxSz.SetDimension((0, 0), self.GetClientSize())
        #self.sDroBoxSz.Layout()
        #self.SetAutoLayout(True)
        #self.Center()
        #self.InvalidateBestSize()
        #self.EnableScrolling(False, False)
        #self.SetVirtualSize(self.GetBestVirtualSize())
        self.Layout()
        #self.FitInside()
        #self.SetDimensions(-1, -1, size.width, size.height, wx.SIZE_USE_EXISTING)
        #self.Update()
        #self.sDroBoxSz.FitInside(self)
        #self.Layout()
        #print "bottom ---"
        #self.test()
        #self.SetBackgroundColour("blue")

    def InitUI(self):
        self.vRootBoxSz = wx.BoxSizer(wx.VERTICAL)

        # Add Static Boxes ----------------------------------------------------
        self.sDroBoxSz = self.CreateStaticBox("DRO")
        self.CreateDroBox(self.sDroBoxSz)

        self.sStatusBoxSz = self.CreateStaticBox("Status")
        self.CreateStatusStaticBox(self.sStatusBoxSz)

        self.vRootBoxSz.Add(self.sDroBoxSz, 0, flag=wx.ALL | wx.EXPAND, border=5)
        self.vRootBoxSz.Add(self.sStatusBoxSz, 0, flag=wx.ALL | wx.EXPAND, border=5)

        self.SetAutoLayout(True)
        self.SetSizerAndFit(self.vRootBoxSz)
        self.Layout()

        # Create menu with icons
        self.menu = wx.Menu()

        # Create icons (you'll need to replace these with actual icon files)
        icon1 = wx.ArtProvider.GetBitmap(wx.ART_NEW, wx.ART_MENU, (16, 16))
        icon2 = wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN, wx.ART_MENU, (16, 16))
        icon3 = wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE, wx.ART_MENU, (16, 16))

        # Add menu items with icons
        item1 = wx.MenuItem(self.menu, 1, "Home Axis")
        item1.SetBitmap(icon1)
        self.menu.Append(item1)

        item2 = wx.MenuItem(self.menu, 2, "Zero Axis")
        item2.SetBitmap(icon2)
        self.menu.Append(item2)

        item3 = wx.MenuItem(self.menu, 3, "Goto Zero")
        item3.SetBitmap(icon3)
        self.menu.Append(item3)

    def UpdateUI(self, stateData, statusData=None):
        self.stateData = stateData

        if statusData is not None:

            if 'prcnt' in statusData:
                if self.prcntStatus.GetLabel() != statusData['prcnt']:
                    self.prcntStatus.SetLabel(statusData['prcnt'])

            if 'rtime' in statusData:
                rtime = statusData['rtime']
                hours, reminder = divmod(rtime, 3600)
                minutes, reminder = divmod(reminder, 60)
                seconds, mseconds = divmod(reminder, 1)
                runTimeStr = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

                if self.runTimeStatus.GetLabel() != runTimeStr:
                    self.runTimeStatus.SetLabel(runTimeStr)

            def update_val(enable, key, ctrl, data):
                if enable and key in data:
                    val = "{:.3f}".format(data[key])
                    if ctrl.GetValue() != val:
                        ctrl.SetValue(val)

            update_val(self.configDroEnX, 'posx', self.xPos, statusData)
            update_val(self.configDroEnY, 'posy', self.yPos, statusData)
            update_val(self.configDroEnZ, 'posz', self.zPos, statusData)
            update_val(self.configDroEnA, 'posa', self.aPos, statusData)
            update_val(self.configDroEnB, 'posb', self.bPos, statusData)
            update_val(self.configDroEnC, 'posc', self.cPos, statusData)
            update_val(self.configDroEnC, 'posc', self.cPos, statusData)

            if 'vel' in statusData:
                fr = "{:.2f}".format(statusData['vel'])
                if self.frVal.GetValue() != fr:
                    self.frVal.SetValue(fr)

            fv = statusData.get('fv')
            fb = statusData.get('fb')
            if (fb is not None) and (fv is not None):
                self.version.SetLabel("fb[%s] fv[%s]" % (str(fb), str(fv)))
            elif fb is not None:
                self.version.SetLabel(str(fb))

            ib = statusData.get('ib')
            if ib is not None:
                self.bufferStatus.SetLabel("%d/%d" % (ib[1], ib[0]))

            if 'machif' in statusData:
                self.machIfStatus.SetLabel(statusData['machif'])

        if self.stateData.serialPortIsOpen:
            # self.refreshButton.Enable()

            if statusData is not None:
                stat = statusData.get('stat')
                if stat is not None:
                    self.runStatus.SetValue(stat)
        else:
            # self.refreshButton.Disable()
            self.version.SetLabel("")
            self.bufferStatus.SetLabel("")
            self.runStatus.SetValue("")
            self.machIfStatus.SetLabel("")

        self.Update()

    def CreateStaticBox(self, label):
        staticBox = wx.StaticBox(self, -1, label)
        staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)

        # staticBoxSizer = wx.BoxSizer(wx.VERTICAL)
        return staticBoxSizer

    def CreateDroBox(self, sz):
        fGridSizer = wx.FlexGridSizer(8,2,0,0)

        # set font properties
        if self.configDroFontFace == "System" or self.configDroFontSize == -1:
            font = wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.BOLD)
            self.configDroFontFace = font.GetFaceName()
            self.configDroFontSize = font.GetPointSize()
            self.configDroFontStyle = "bold"
            self.configData.set('/machine/DRO/FontFace', self.configDroFontFace)
            self.configData.set('/machine/DRO/FontSize', self.configDroFontSize)
            self.configData.set('/machine/DRO/FontStyle', self.configDroFontStyle)

        fontSt = wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        fontPos = wx.Font(self.configDroFontSize, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, self.configDroFontFace)
        font_style_str = self.configDroFontStyle

        if "bold" in font_style_str:
            fontPos.MakeBold()

        if "italic" in font_style_str:
            fontPos.MakeItalic()

        dc = wx.ClientDC(self)
        dc.SetFont(fontPos)
        height = dc.GetCharHeight()

        # X axis
        self.xPosSt = wx.StaticText(self, label="X")
        self.xPosSt.SetFont(fontSt)
        self.xPos = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.xPos.SetValue(gc.ZERO_STRING)
        self.xPos.SetFont(fontPos)
        fGridSizer.Add(self.xPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.xPos, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)
        self.droObj2AxisDict[self.xPos] = {'axis': 'X', 'last_value': 0, 'modified': False}
        self.droObj2AxisDict[self.xPosSt] = self.droObj2AxisDict[self.xPos]

        # Y axis
        self.yPosSt = wx.StaticText(self, label="Y")
        self.yPosSt.SetFont(fontSt)
        self.yPos = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.yPos.SetValue(gc.ZERO_STRING)
        self.yPos.SetFont(fontPos)
        fGridSizer.Add(self.yPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.yPos, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)
        self.droObj2AxisDict[self.yPos] = {'axis': 'Y', 'last_value': 0, 'modified': False}
        self.droObj2AxisDict[self.yPosSt] = self.droObj2AxisDict[self.yPos]

        # Z axis
        self.zPosSt = wx.StaticText(self, label="Z")
        self.zPosSt.SetFont(fontSt)
        self.zPos = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.zPos.SetValue(gc.ZERO_STRING)
        self.zPos.SetFont(fontPos)
        fGridSizer.Add(self.zPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.zPos, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)
        self.droObj2AxisDict[self.zPos] = {'axis': 'Z', 'last_value': 0, 'modified': False}
        self.droObj2AxisDict[self.zPosSt] = self.droObj2AxisDict[self.zPos]

        # A axis
        self.aPosSt = wx.StaticText(self, label="A")
        self.aPosSt.SetFont(fontSt)
        self.aPos = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.aPos.SetValue(gc.ZERO_STRING)
        self.aPos.SetFont(fontPos)
        fGridSizer.Add(self.aPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.aPos, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)
        self.droObj2AxisDict[self.aPos] = {'axis': 'A', 'last_value': 0, 'modified': False}
        self.droObj2AxisDict[self.aPosSt] = self.droObj2AxisDict[self.aPos]

        self.bPosSt = wx.StaticText(self, label="B")
        self.bPosSt.SetFont(fontSt)
        self.bPos = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.bPos.SetValue(gc.ZERO_STRING)
        self.bPos.SetFont(fontPos)
        fGridSizer.Add(self.bPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.bPos, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)
        self.droObj2AxisDict[self.bPos] = {'axis': 'B', 'last_value': 0, 'modified': False}
        self.droObj2AxisDict[self.bPosSt] = self.droObj2AxisDict[self.bPos]

        self.cPosSt = wx.StaticText(self, label="C")
        self.cPosSt.SetFont(fontSt)
        self.cPos = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.cPos.SetValue(gc.ZERO_STRING)
        self.cPos.SetFont(fontPos)
        fGridSizer.Add(self.cPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.cPos, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)
        self.droObj2AxisDict[self.cPos] = {'axis': 'C', 'last_value': 0, 'modified': False}
        self.droObj2AxisDict[self.cPosSt] = self.droObj2AxisDict[self.cPos]

        for textCtrl in self.droObj2AxisDict.keys():
            textCtrl.Bind(wx.EVT_LEFT_UP, self.OnDroLeftUp)

        # Feed Rate
        st = wx.StaticText(self, label="FR")
        st.SetFont(fontSt)
        self.frVal = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.frVal.SetValue("{:.2f}".format(eval(gc.ZERO_STRING)))
        self.frVal.SetFont(fontPos)
        fGridSizer.Add(st, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.frVal, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # Machine status
        st = wx.StaticText(self, label="ST")
        st.SetFont(fontSt)
        self.runStatus = wx.TextCtrl(self, wx.ID_ANY, "", size=(-1, height), style=wx.TE_READONLY | wx.TE_RIGHT)
        self.runStatus.SetValue("")
        self.runStatus.SetFont(fontPos)
        fGridSizer.Add(st, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.runStatus, 1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # finish init flex grid sizer
        fGridSizer.AddGrowableCol(1)

        sz.Add(fGridSizer, 0, flag=wx.EXPAND)
        self.Layout()

    def CreateStatusStaticBox(self, sz):
        flexGridSizer = wx.FlexGridSizer(7, 2, 1, 5)
        sz.Add(flexGridSizer, 1, flag=wx.LEFT | wx.EXPAND, border=10)

        # set font properties
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)

        # Add MachIf name
        #                               01234567890123456789
        st = wx.StaticText(self, label="Device name       ")
        st.SetFont(font)
        self.machIfStatus = wx.StaticText(self, label="")
        self.machIfStatus.SetForegroundColour(self.machineDataColor)
        self.machIfStatus.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.machIfStatus, 0, flag=wx.ALIGN_LEFT)

        # Add MachIf version
        st = wx.StaticText(self, label="Device version")
        st.SetFont(font)
        self.version = wx.StaticText(self, label="-")
        self.version.SetForegroundColour(self.machineDataColor)
        self.version.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.version, 0, flag=wx.ALIGN_LEFT)

        # Add MachIf buffer status
        #                               01234567890123456789
        st = wx.StaticText(self, label="Device buffer")
        st.SetFont(font)
        self.bufferStatus = wx.StaticText(self, label="-/-")
        self.bufferStatus.SetForegroundColour(self.machineDataColor)
        self.bufferStatus.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.bufferStatus, 0, flag=wx.ALIGN_LEFT)

        # Add Percent sent status
        #                               01234567890123456789
        st = wx.StaticText(self, label="PC loc in G-code")
        st.SetFont(font)
        self.prcntStatus = wx.StaticText(self, label="-/- (0.00%)")
        self.prcntStatus.SetForegroundColour(self.machineDataColor)
        self.prcntStatus.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.prcntStatus, 0, flag=wx.ALIGN_LEFT)

        # Add run time
        st = wx.StaticText(self, label="Run time")
        st.SetFont(font)
        self.runTimeStatus = wx.StaticText(self, label="00:00:00")
        self.runTimeStatus.SetForegroundColour(self.machineDataColor)
        self.runTimeStatus.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.runTimeStatus, 0, flag=wx.ALIGN_LEFT)

    def OnDroLeftUp(self, event):
        eventControl = event.GetEventObject()
        axis = None

        if self.stateData.serialPortIsOpen:
            if eventControl in self.droObj2AxisDict.keys():
                axis = self.droObj2AxisDict[eventControl].get('axis')
                if isinstance(eventControl, wx.TextCtrl):
                    with ne.gsatNumericEntryDialog(self, "Goto", f"Enter new value for {axis} axis") as dlg:
                        if dlg.ShowModal() == wx.ID_OK:
                            dictAxisCoor = {axis.lower(): dlg.GetValue()}
                            self.mainWindow.eventForward2Machif(gc.EV_CMD_MOVE, dictAxisCoor)
                elif isinstance(eventControl, wx.StaticText):
                    print(f"StaticText value is {eventControl.GetLabel()}")
                    pos = eventControl.GetPosition() + (0, eventControl.GetSize().height)
                    self.PopupMenu(self.menu, pos)

    def OnRefresh(self, e):
        self.mainWindow.GetMachineStatus()
