"""----------------------------------------------------------------------------
   link.py
----------------------------------------------------------------------------"""

import os
import re
import wx
from wx.lib import scrolledpanel as scrolled
from wx.lib.agw import floatspin as fs

import modules.config as gc

"""----------------------------------------------------------------------------
   gcsLinkSettingsPanel:
   Link settings.
----------------------------------------------------------------------------"""
class gcsLinkSettingsPanel(scrolled.ScrolledPanel):
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
      flexGridSizer = wx.FlexGridSizer(2,2)
      gridSizer = wx.GridSizer(1,3)

      vBoxSizer.Add(flexGridSizer, 0, flag=wx.LEFT|wx.TOP|wx.RIGHT, border=20)
      vBoxSizer.Add(gridSizer, 0, flag=wx.ALL, border=5)

      # get serial port list and baud rate speeds
      spList = self.configData.Get('/link/PortList')
      brList = self.configData.Get('/link/BaudList')

      # Add serial port controls
      spText = wx.StaticText(self, label="Serial Port:")
      flexGridSizer.Add(spText, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

      self.spComboBox = wx.ComboBox(self, -1, value=self.configData.Get('/link/Port'),
         choices=spList, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
      flexGridSizer.Add(self.spComboBox,
         flag=wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      # Add baud rate controls
      srText = wx.StaticText(self, label="Baud Rate:")
      flexGridSizer.Add(srText, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)

      self.sbrComboBox = wx.ComboBox(self, -1, value=self.configData.Get('/link/Baud'),
         choices=brList, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER)
      flexGridSizer.Add(self.sbrComboBox,
         flag=wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/link/Port', self.spComboBox.GetValue())
      self.configData.Set('/link/Baud', self.sbrComboBox.GetValue())
