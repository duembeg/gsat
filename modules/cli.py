"""----------------------------------------------------------------------------
   cli.py
----------------------------------------------------------------------------"""

import os
import re
import wx
from wx.lib import scrolledpanel as scrolled
from wx.lib.agw import floatspin as fs

import modules.config as gc

"""----------------------------------------------------------------------------
   gcsCliSettingsPanel:
   CLI settings.
----------------------------------------------------------------------------"""
class gcsCliSettingsPanel(scrolled.ScrolledPanel):
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

      # Add cehck box
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.cb = wx.CheckBox(self, wx.ID_ANY, "Save Command History")
      self.cb.SetValue(self.configData.Get('/cli/SaveCmdHistory'))
      hBoxSizer.Add(self.cb, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)
      vBoxSizer.Add(hBoxSizer, flag=wx.TOP|wx.LEFT, border=20)

      # Add spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.sc = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.sc.SetRange(1,1000)
      self.sc.SetValue(self.configData.Get('/cli/CmdMaxHistory'))
      hBoxSizer.Add(self.sc, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Max Command History")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/cli/SaveCmdHistory', self.cb.GetValue())
      self.configData.Set('/cli/CmdMaxHistory', self.sc.GetValue())

"""----------------------------------------------------------------------------
   gcsCliPanel:
   Control to handle CLI (Command Line Interface)
----------------------------------------------------------------------------"""
class gcsCliPanel(wx.Panel):
   def __init__(self, parent, config_data, state_data, *args, **kwargs):
      wx.Panel.__init__(self, parent, *args, **kwargs)

      self.cliCommand = ""
      self.configData = config_data
      self.stateData = state_data

      self.InitConfig()
      self.InitUI()

   def InitConfig(self):
      self.cliSaveCmdHistory = self.configData.Get('/cli/SaveCmdHistory')
      self.cliCmdMaxHistory = self.configData.Get('/cli/CmdMaxHistory')
      self.cliCmdHistory = self.configData.Get('/cli/CmdHistory')

   def InitUI(self):
      sizer = wx.BoxSizer(wx.VERTICAL)
      self.comboBox = wx.ComboBox(self, style=wx.CB_DROPDOWN|wx.TE_PROCESS_ENTER)
      self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter, self.comboBox)
      sizer.Add(self.comboBox, 1, wx.EXPAND|wx.ALL, border=1)
      self.SetSizerAndFit(sizer)

   def UpdateUI(self, stateData):
      self.stateData = stateData
      if stateData.serialPortIsOpen and not stateData.swState == gc.gSTATE_RUN:
         self.comboBox.Enable()
      else:
         self.comboBox.Disable()

   def GetCommand(self):
      return self.cliCommand

   def OnEnter(self, e):
      cliCommand = self.comboBox.GetValue()

      if cliCommand != self.cliCommand:
         if self.comboBox.GetCount() > self.cliCmdMaxHistory:
            self.comboBox.Delete(0)

         self.cliCommand = cliCommand
         self.comboBox.Append(self.cliCommand)

      self.comboBox.SetValue("")
      e.Skip()

   def Load(self, configFile):
      # read cmd hsitory
      configData = self.cliCmdHistory
      if len(configData) > 0:
         cliCommandHistory = configData.split("|")
         for cmd in cliCommandHistory:
            cmd = cmd.strip()
            if len(cmd) > 0:
               self.comboBox.Append(cmd.strip())

         self.cliCommand = cliCommandHistory[len(cliCommandHistory) - 1]

   def Save(self, configFile):
      # write cmd history
      if self.cliSaveCmdHistory:
         cliCmdHistory = self.comboBox.GetItems()
         if len(cliCmdHistory) > 0:
            cliCmdHistory =  "|".join(cliCmdHistory)
            self.configData.Set('/cli/CmdHistory', cliCmdHistory)

   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.InitConfig()
