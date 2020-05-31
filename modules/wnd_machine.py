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

        self.InitUI()
        width, height = self.GetSize()
        scroll_unit = 10
        self.SetScrollbars(scroll_unit, scroll_unit, width /
                           scroll_unit, height/scroll_unit)

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # Add Static Boxes ----------------------------------------------------
        droBox = self.CreateDroBox()
        statusBox = self.CreateStatusStaticBox()

        vBoxSizer.Add(droBox, 0, flag=wx.ALL | wx.EXPAND, border=5)
        vBoxSizer.Add(statusBox, 0, flag=wx.ALL | wx.EXPAND, border=5)

        # # Add Buttons -------------------------------------------------------
        # self.refreshButton = wx.Button(self, wx.ID_REFRESH)
        # self.refreshButton.SetToolTip(
        #     wx.ToolTip("Refresh machine status"))
        # self.Bind(wx.EVT_BUTTON, self.OnRefresh, self.refreshButton)
        # self.refreshButton.Disable()

        # vBoxSizer.Add(self.refreshButton, 0, flag=wx.ALL, border=10)

        # Finish up init UI
        self.SetSizer(vBoxSizer)
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

            x = statusData.get('posx')
            if x is not None:
                self.xPos.SetValue("{:.3f}".format(x))

            y = statusData.get('posy')
            if y is not None:
                self.yPos.SetValue("{:.3f}".format(y))

            z = statusData.get('posz')
            if z is not None:
                self.zPos.SetValue("{:.3f}".format(z))

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
        '''
      self.machinePort.SetLabel(stateData.serialPort)
      self.machineBaud.SetLabel(stateData.serialPortBaud)
      '''

        self.Update()

    def CreateStaticBox(self, label):
        staticBox = wx.StaticBox(self, -1, label)
        staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)

        return staticBoxSizer

    def CreateDroBox(self):
        positionBoxSizer = self.CreateStaticBox("DRO")
        fGridSizer = wx.FlexGridSizer(4, 2)
        positionBoxSizer.Add(fGridSizer, 0, flag=wx.EXPAND)

        # set font properties
        font = wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.BOLD)

        # X axis
        st = wx.StaticText(self, label="X")
        st.SetFont(font)
        self.xPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.xPos.SetValue(gc.ZERO_STRING)
        self.xPos.SetFont(font)
        fGridSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                       wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.xPos, 1, flag=wx.ALL |
                       wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # Y axis
        st = wx.StaticText(self, label="Y")
        st.SetFont(font)
        self.yPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.yPos.SetValue(gc.ZERO_STRING)
        self.yPos.SetFont(font)
        fGridSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                       wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.yPos, 1, flag=wx.ALL |
                       wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # Z axis
        st = wx.StaticText(self, label="Z")
        st.SetFont(font)
        self.zPos = wx.TextCtrl(self, wx.ID_ANY, "",
                                style=wx.TE_READONLY | wx.TE_RIGHT)
        self.zPos.SetValue(gc.ZERO_STRING)
        self.zPos.SetFont(font)
        fGridSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                       wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.zPos, 1, flag=wx.ALL |
                       wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # Feed Rate
        st = wx.StaticText(self, label="FR")
        st.SetFont(font)
        self.frVal = wx.TextCtrl(
            self, wx.ID_ANY, "", style=wx.TE_READONLY | wx.TE_RIGHT)
        self.frVal.SetValue("{:.2f}".format(eval(gc.ZERO_STRING)))
        self.frVal.SetFont(font)
        fGridSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL |
                       wx.ALIGN_RIGHT, border=5)
        fGridSizer.Add(self.frVal, 1, flag=wx.ALL |
                       wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border=5)

        # finish init flex grid sizer
        fGridSizer.AddGrowableCol(1, 1)

        return positionBoxSizer

    def CreateStatusStaticBox(self):
        positionBoxSizer = self.CreateStaticBox("Status")
        flexGridSizer = wx.FlexGridSizer(7, 2, 1, 5)
        positionBoxSizer.Add(flexGridSizer, 1, flag=wx.EXPAND)

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

        return positionBoxSizer

    def OnRefresh(self, e):
        self.mainWindow.GetMachineStatus()

    def UpdateSettings(self, config_data):
        self.configData = config_data
        self.UpdateUI(self.stateData)
        # self.InitConfig()
