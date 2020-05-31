"""----------------------------------------------------------------------------
   wnd_machine.py

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

import modules.config as gc
import modules.machif_config as mi


class gsatMachineStatusPanel(wx.ScrolledWindow):
    """ Status information about machine, controls to enable auto and manual
        refresh.
    """

    def __init__(self, parent, config_data, state_data, **args):
        wx.ScrolledWindow.__init__(self, parent, **args)

        self.mainWindow = parent

        self.configData = config_data
        self.stateData = state_data

        self.machineDataColor = wx.RED

        self.InitConfig()

        self.InitUI()

        #self.UpdateSettings()
        wx.CallAfter(self.UpdateSettings)

        width, height = self.GetSizeTuple()
        scroll_unit = 10
        self.SetScrollbars(scroll_unit, scroll_unit, width /
                           scroll_unit, height/scroll_unit)

    def InitConfig(self):
        self.configDroEnX = self.configData.get('/machine/AxisDroEnable/X')
        self.configDroEnY = self.configData.get('/machine/AxisDroEnable/Y')
        self.configDroEnZ = self.configData.get('/machine/AxisDroEnable/Z')
        self.configDroEnA = self.configData.get('/machine/AxisDroEnable/A')
        self.configDroEnB = self.configData.get('/machine/AxisDroEnable/B')
        self.configDroEnC = self.configData.get('/machine/AxisDroEnable/C')

    def UpdateSettings(self, config_data=None):
        if config_data is not None:
            self.configData = config_data

        self.InitConfig()

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

        self.sDroBoxSz.Layout()

        self.UpdateUI(self.stateData)

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

    def UpdateUI(self, stateData, statusData=None):
        self.stateData = stateData

        if statusData is not None:

            prcnt = statusData.get('prcnt')
            if prcnt is not None:
                self.prcntStatus.SetLabel(prcnt)

            rtime = statusData.get('rtime')
            if rtime is not None:
                self.runTimeStatus.SetLabel(rtime)

            if self.configDroEnX:
                x = statusData.get('posx')
                if x is not None:
                    self.xPos.SetValue("{:.3f}".format(x))

            if self.configDroEnY:
                y = statusData.get('posy')
                if y is not None:
                    self.yPos.SetValue("{:.3f}".format(y))

            if self.configDroEnZ:
                z = statusData.get('posz')
                if z is not None:
                    self.zPos.SetValue("{:.3f}".format(z))

            if self.configDroEnA:
                a = statusData.get('posa')
                if a is not None:
                    self.aPos.SetValue("{:.3f}".format(a))

            if self.configDroEnB:
                b = statusData.get('posb')
                if b is not None:
                    self.bPos.SetValue("{:.3f}".format(b))

            if self.configDroEnC:
                c = statusData.get('posc')
                if c is not None:
                    self.cPos.SetValue("{:.3f}".format(c))

            fr = statusData.get('vel')
            if fr is not None:
                self.frVal.SetValue("{:.2f}".format(fr))

            fv = statusData.get('fv')
            fb = statusData.get('fb')
            if (fb is not None) and (fv is not None):
                self.version.SetLabel("fb[%s] fv[%s]" % (str(fb), str(fv)))
            elif fb is not None:
                self.version.SetLabel(str(fb))

            ib = statusData.get('ib')
            if ib is not None:
                self.bufferStatus.SetLabel("%d/%d" % (ib[1], ib[0]))

        if stateData.serialPortIsOpen:
            # self.refreshButton.Enable()

            if statusData is not None:
                stat = statusData.get('stat')
                if stat is not None:
                    self.runStatus.SetLabel(stat)
        else:
            # self.refreshButton.Disable()
            self.version.SetLabel("uknown")
            self.runStatus.SetLabel("detach")
            self.bufferStatus.SetLabel("-/-")

        machIfId = mi.GetMachIfId(self.configData.get('/machine/Device'))
        self.machIfStatus.SetLabel(mi.GetMachIfName(machIfId))

        self.Update()

    def CreateStaticBox(self, label):
        staticBox = wx.StaticBox(self, -1, label)
        staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)

        # staticBoxSizer = wx.BoxSizer(wx.VERTICAL)
        return staticBoxSizer

    def CreateDroBox(self, sz):
        fGridSizer = wx.FlexGridSizer(7, 2)

        # set font properties
        font = wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.BOLD)

        self.droCtrlDict = dict()

        # X axis
        self.xPosSt = wx.StaticText(self, label="X")
        self.xPosSt.SetFont(font)
        self.xPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.xPos.SetValue(gc.ZERO_STRING)
        self.xPos.SetFont(font)
        fGridSizer.Add(self.xPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                    wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.xPos, 1, flag=wx.ALL |
                    wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # Y axis
        self.yPosSt = wx.StaticText(self, label="Y")
        self.yPosSt.SetFont(font)
        self.yPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.yPos.SetValue(gc.ZERO_STRING)
        self.yPos.SetFont(font)
        fGridSizer.Add(self.yPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                    wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.yPos, 1, flag=wx.ALL |
                    wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # Z axis
        self.zPosSt = wx.StaticText(self, label="Z")
        self.zPosSt.SetFont(font)
        self.zPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.zPos.SetValue(gc.ZERO_STRING)
        self.zPos.SetFont(font)
        fGridSizer.Add(self.zPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                    wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.zPos, 1, flag=wx.ALL |
                    wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # A axis
        self.aPosSt = wx.StaticText(self, label="A")
        self.aPosSt.SetFont(font)
        self.aPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.aPos.SetValue(gc.ZERO_STRING)
        self.aPos.SetFont(font)
        fGridSizer.Add(self.aPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                    wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.aPos, 1, flag=wx.ALL |
                    wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        self.bPosSt = wx.StaticText(self, label="B")
        self.bPosSt.SetFont(font)
        self.bPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.bPos.SetValue(gc.ZERO_STRING)
        self.bPos.SetFont(font)
        fGridSizer.Add(self.bPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                    wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.bPos, 1, flag=wx.ALL |
                    wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        self.cPosSt = wx.StaticText(self, label="C")
        self.cPosSt.SetFont(font)
        self.cPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.cPos.SetValue(gc.ZERO_STRING)
        self.cPos.SetFont(font)
        fGridSizer.Add(self.cPosSt, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                    wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.cPos, 1, flag=wx.ALL |
                    wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # Feed Rate
        st = wx.StaticText(self, label="FR")
        st.SetFont(font)
        self.frVal = wx.TextCtrl(
            self, wx.ID_ANY, "", style=wx.TE_READONLY | wx.TE_RIGHT)
        self.frVal.SetValue("{:.2f}".format(eval(gc.ZERO_STRING)))
        self.frVal.SetFont(font)
        fGridSizer.Add(st, 0, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                       wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.frVal, 1, flag=wx.ALL |
                       wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # finish init flex grid sizer
        fGridSizer.AddGrowableCol(1)

        sz.Add(fGridSizer, 0, flag=wx.EXPAND)

    def CreateStatusStaticBox(self, sz):
        flexGridSizer = wx.FlexGridSizer(7, 2, 1, 5)
        sz.Add(flexGridSizer, 1, flag=wx.LEFT | wx.EXPAND, border=10)

        # set font properties
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)

        # Add MachIf name
        st = wx.StaticText(self, label="Device name")
        st.SetFont(font)
        machIfId = mi.GetMachIfId(self.configData.get('/machine/Device'))
        self.machIfStatus = wx.StaticText(
            self, label=mi.GetMachIfName(machIfId))
        self.machIfStatus.SetForegroundColour(self.machineDataColor)
        self.machIfStatus.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.machIfStatus, 0, flag=wx.ALIGN_LEFT)

        # Add MachIf running status
        st = wx.StaticText(self, label="Device state")
        st.SetFont(font)
        self.runStatus = wx.StaticText(self, label="Idle")
        self.runStatus.SetForegroundColour(self.machineDataColor)
        self.runStatus.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.runStatus, 0, flag=wx.ALIGN_LEFT)

        # Add MachIf running status
        st = wx.StaticText(self, label="Device buffer")
        st.SetFont(font)
        self.bufferStatus = wx.StaticText(self, label="-/-")
        self.bufferStatus.SetForegroundColour(self.machineDataColor)
        self.bufferStatus.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.bufferStatus, 0, flag=wx.ALIGN_LEFT)

        # Add MachIF version
        st = wx.StaticText(self, label="Device version")
        st.SetFont(font)
        self.version = wx.StaticText(self, label="None")
        self.version.SetForegroundColour(self.machineDataColor)
        self.version.SetFont(font)
        flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
        flexGridSizer.Add(self.version, 0, flag=wx.ALIGN_LEFT)

        # Add Connected Status
        '''
      st = wx.StaticText(self, label="Device port")
      st.SetFont(font)
      self.machinePort = wx.StaticText(self, label="None")
      self.machinePort.SetForegroundColour(self.machineDataColor)
      self.machinePort.SetFont(font)
      flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
      flexGridSizer.Add(self.machinePort, 0, flag=wx.ALIGN_LEFT)

      st = wx.StaticText(self, label="Device baud")
      st.SetFont(font)
      self.machineBaud = wx.StaticText(self, label="None")
      self.machineBaud.SetForegroundColour(self.machineDataColor)
      self.machineBaud.SetFont(font)
      flexGridSizer.Add(st, 0, flag=wx.ALIGN_LEFT)
      flexGridSizer.Add(self.machineBaud, 0, flag=wx.ALIGN_LEFT)
      '''

        # Add Percent sent status
        st = wx.StaticText(self, label="PC in file pos")
        st.SetFont(font)
        self.prcntStatus = wx.StaticText(self, label="0.00%")
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

    def OnRefresh(self, e):
        self.mainWindow.GetMachineStatus()
