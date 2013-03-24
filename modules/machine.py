"""----------------------------------------------------------------------------
   machine.py
----------------------------------------------------------------------------"""

import os
import re
import wx
from wx.lib import scrolledpanel as scrolled
from wx.lib.agw import floatspin as fs

import modules.config as gc

"""----------------------------------------------------------------------------
   gcsMachineSettingsPanel:
   Machine settings.
----------------------------------------------------------------------------"""
class gcsMachineSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, config_data, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = config_data

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # Add check box
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.cb = wx.CheckBox(self, wx.ID_ANY, "Auto Refresh")
      self.cb.SetValue(self.configData.Get('/machine/AutoRefresh'))
      self.cb.SetToolTip(
         wx.ToolTip("Send '?' Status request (experimental)"))
      hBoxSizer.Add(self.cb, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)
      vBoxSizer.Add(hBoxSizer, flag=wx.TOP|wx.LEFT, border=20)

      # Add spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      self.sc = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.sc.SetRange(1,1000000)
      self.sc.SetValue(self.configData.Get('/machine/AutoRefreshPeriod'))
      hBoxSizer.Add(self.sc, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Auto Refresh Period (milliseconds)")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/machine/AutoRefresh', self.cb.GetValue())
      self.configData.Set('/machine/AutoRefreshPeriod', self.sc.GetValue())

"""----------------------------------------------------------------------------
   gcsMachineStatusPanel:
   Status information about machine, controls to enable auto and manual
   refresh.
----------------------------------------------------------------------------"""
class gcsMachineStatusPanel(wx.ScrolledWindow):
   def __init__(self, parent, config_data, state_data, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent

      self.configData = config_data
      self.stateData = state_data

      self.machineDataColor = wx.RED

      self.InitUI()
      width,height = self.GetSize()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

   def InitUI(self):
      gridSizer = wx.GridSizer(2,2)

      # Add Static Boxes ------------------------------------------------------
      wBox, self.wX, self.wY, self.wZ = self.CreatePositionStaticBox("Work Position")
      mBox, self.mX, self.mY, self.mZ = self.CreatePositionStaticBox("Machine Position")
      sBox, self.sConncted, self.sState = self.CreateStatusStaticBox("Status")

      gridSizer.Add(wBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      gridSizer.Add(mBox, 0, flag=wx.ALL|wx.EXPAND, border=5)
      gridSizer.Add(sBox, 0, flag=wx.ALL|wx.EXPAND, border=5)

      # Add Buttons -----------------------------------------------------------
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)
      self.refreshButton = wx.Button(self, wx.ID_REFRESH)
      self.refreshButton.SetToolTip(
         wx.ToolTip("Refresh machine status"))
      self.Bind(wx.EVT_BUTTON, self.OnRefresh, self.refreshButton)
      vBoxSizer.Add(self.refreshButton, 0, flag=wx.TOP, border=5)
      self.refreshButton.Disable()

      gridSizer.Add(vBoxSizer, 0, flag=wx.EXPAND|wx.ALIGN_LEFT|wx.ALL, border=5)


      # Finish up init UI
      self.SetSizer(gridSizer)
      self.Layout()

   def UpdateUI(self, stateData, statusData=None):
      self.stateData = stateData
      # adata is expected to be an array of strings as follows
      # statusData[0] : Machine state
      # statusData[1] : Machine X
      # statusData[2] : Machine Y
      # statusData[3] : Machine Z
      # statusData[4] : Work X
      # statusData[5] : Work Y
      # statusData[6] : Work Z
      if statusData is not None:
         self.mX.SetLabel(statusData[1])
         self.mY.SetLabel(statusData[2])
         self.mZ.SetLabel(statusData[3])
         self.wX.SetLabel(statusData[4])
         self.wY.SetLabel(statusData[5])
         self.wZ.SetLabel(statusData[6])
         self.sState.SetLabel(statusData[0])
         #self.sSpindle.SetLabel("?")

      if stateData.serialPortIsOpen:
         self.refreshButton.Enable()
         self.sConncted.SetLabel("Yes")
      else:
         self.refreshButton.Disable()
         self.sConncted.SetLabel("No")

      self.Update()

   def CreateStaticBox(self, label):
      # Static box -------------------------------------------------
      staticBox = wx.StaticBox(self, -1, label)
      staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)

      return staticBoxSizer

   def CreatePositionStaticBox(self, label):
      # Position static box -------------------------------------------------
      positionBoxSizer = self.CreateStaticBox(label)
      flexGridSizer = wx.FlexGridSizer(3,2)
      positionBoxSizer.Add(flexGridSizer, 1, flag=wx.EXPAND)

      # Add X pos
      xText = wx.StaticText(self, label="X:")
      xPosition = wx.StaticText(self, label=gc.gZeroString)
      xPosition.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(xText, 0, flag=wx.ALIGN_RIGHT)
      flexGridSizer.Add(xPosition, 0, flag=wx.ALIGN_LEFT)

      # Add Y Pos
      yText = wx.StaticText(self, label="Y:")
      yPosition = wx.StaticText(self, label=gc.gZeroString)
      yPosition.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(yText, 0, flag=wx.ALIGN_RIGHT)
      flexGridSizer.Add(yPosition, 0, flag=wx.ALIGN_LEFT)

      # Add Z Pos
      zText = wx.StaticText(self, label="Z:")
      zPosition = wx.StaticText(self, label=gc.gZeroString)
      zPosition.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(zText, 0, flag=wx.ALIGN_RIGHT)
      flexGridSizer.Add(zPosition, 0, flag=wx.ALIGN_LEFT)

      return positionBoxSizer, xPosition, yPosition, zPosition

   def CreateStatusStaticBox(self, label):
      # Position static box -------------------------------------------------
      positionBoxSizer = self.CreateStaticBox(label)
      flexGridSizer = wx.FlexGridSizer(3,2)
      positionBoxSizer.Add(flexGridSizer, 1, flag=wx.EXPAND)

      # Add Connected Status
      connectedText = wx.StaticText(self, label="Connected:")
      connectedStatus = wx.StaticText(self, label="No")
      connectedStatus.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(connectedText, 0, flag=wx.ALIGN_LEFT)
      flexGridSizer.Add(connectedStatus, 0, flag=wx.ALIGN_LEFT)

      # Add Running Status
      runningText = wx.StaticText(self, label="State:")
      runningStatus = wx.StaticText(self, label="Idle")
      runningStatus.SetForegroundColour(self.machineDataColor)
      flexGridSizer.Add(runningText, 0, flag=wx.ALIGN_LEFT)
      flexGridSizer.Add(runningStatus, 0, flag=wx.ALIGN_LEFT)

      # Add Spindle Status
      #spindleText = wx.StaticText(self, label="Spindle:")
      #spindleStatus = wx.StaticText(self, label=gOffString)
      #spindleStatus.SetForegroundColour(self.machineDataColor)
      #flexGridSizer.Add(spindleText, 0, flag=wx.ALIGN_LEFT)
      #flexGridSizer.Add(spindleStatus, 0, flag=wx.ALIGN_LEFT)

      return positionBoxSizer, connectedStatus, runningStatus#, spindleStatus

   def OnRefresh(self, e):
      self.mainWindow.GetMachineStatus()

   def UpdateSettings(self, config_data):
      self.configData = config_data
      #self.InitConfig()
