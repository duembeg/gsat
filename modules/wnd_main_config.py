"""----------------------------------------------------------------------------
   wnd_main_config.py

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
import sys
import glob
import serial
import re
import time
import shutil
import logging
import wx
import wx.combo
# from wx import stc as stc
# from wx.lib.mixins import listctrl as listmix
from wx.lib.agw import aui as aui
from wx.lib.agw import floatspin as fs
from wx.lib.agw import genericmessagedialog as gmd
# from wx.lib.agw import flatmenu as fm
from wx.lib.wordwrap import wordwrap
from wx.lib import scrolledpanel as scrolled

import modules.config as gc
import modules.machif_config as mi
import images.icons as ico

main_wnd_c = sys.modules[__name__]
import modules.wnd_gcode_config as gcode_c
import modules.wnd_output_config as output_c
import modules.wnd_machine_config as machine_c
import modules.wnd_jogging_config as jog_c
import modules.wnd_cli_config as cli_c
import modules.wnd_compvision_config as compvision_c
import modules.wnd_remote_config as remote_c


class Factory():
    """ Factory class to init config page
    """

    @staticmethod
    def GetIcon():
        return ico.imgGeneralSettings.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatGeneralSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "General")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatGeneralSettingsPanel(scrolled.ScrolledPanel):
    """ General panel settings
    """

    def __init__(self, parent, configData, **args):
        scrolled.ScrolledPanel.__init__(
            self, parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = configData

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        # self.FitInside()

    def InitUI(self):
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # run time dialog settings
        st = wx.StaticText(self, label="General")
        st.SetFont(font)
        vBoxSizer.Add(st, 0, wx.ALL, border=5)

        # Add file save backup check box
        self.cbDisplayRunTimeDialog = wx.CheckBox(
            self, wx.ID_ANY, "Display run time dialog at program end")
        self.cbDisplayRunTimeDialog.SetValue(
            self.configData.get('/mainApp/DisplayRunTimeDialog'))
        vBoxSizer.Add(self.cbDisplayRunTimeDialog, flag=wx.LEFT, border=25)

        # file settings
        st = wx.StaticText(self, label="Files")
        st.SetFont(font)
        vBoxSizer.Add(st, 0, wx.ALL, border=5)

        # Add file save backup check box
        self.cbBackupFile = wx.CheckBox(
            self, wx.ID_ANY, "Create a backup copy of file before saving")
        self.cbBackupFile.SetValue(self.configData.get('/mainApp/BackupFile'))
        vBoxSizer.Add(self.cbBackupFile, flag=wx.LEFT, border=25)

        # Add file history spin ctrl
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.scFileHistory = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.scFileHistory.SetRange(0, 100)
        self.scFileHistory.SetValue(
            self.configData.get('/mainApp/FileHistory/FilesMaxHistory'))
        hBoxSizer.Add(self.scFileHistory, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "Recent file history size")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        # tools settings
        st = wx.StaticText(self, label="Tools")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        st.SetFont(font)
        vBoxSizer.Add(st, 0, wx.ALL, border=5)

        # Add Inch to mm round digits spin ctrl
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.scIN2MMRound = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.scIN2MMRound.SetRange(0, 100)
        self.scIN2MMRound.SetValue(
            self.configData.get('/mainApp/RoundInch2mm'))
        hBoxSizer.Add(self.scIN2MMRound, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "Inch to mm round digits")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        # Add mm to Inch round digits spin ctrl
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.scMM2INRound = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.scMM2INRound.SetRange(0, 100)
        self.scMM2INRound.SetValue(
            self.configData.get('/mainApp/Roundmm2Inch'))
        hBoxSizer.Add(self.scMM2INRound, flag=wx.ALL |
                      wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "mm to Inch round digits")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        self.SetSizer(vBoxSizer)

    def UpdateConfigData(self):
        self.configData.set('/mainApp/DisplayRunTimeDialog',
                            self.cbDisplayRunTimeDialog.GetValue())
        self.configData.set('/mainApp/BackupFile',
                            self.cbBackupFile.GetValue())
        self.configData.set('/mainApp/FileHistory/FilesMaxHistory',
                            self.scFileHistory.GetValue())
        self.configData.set('/mainApp/RoundInch2mm',
                            self.scIN2MMRound.GetValue())
        self.configData.set('/mainApp/Roundmm2Inch',
                            self.scMM2INRound.GetValue())


class gsatSettingsDialog(wx.Dialog):
    """ Dialog to control program settings
    """

    def __init__(self, parent, config_data, config_remote_data=None, id=wx.ID_ANY, title="Settings",
                 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER):
        super(gsatSettingsDialog, self).__init__(parent, id, title, style=style)

        self.configRemoteData = config_remote_data

        if self.configRemoteData:
            self.configData = self.configRemoteData
        else:
            self.configData = config_data

        self.settings_pages = []

        self.InitUI()

    def InitUI(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # add pages
        if self.configRemoteData:
            mod_settings = [machine_c, remote_c]
        else:
            mod_settings = [main_wnd_c, gcode_c, output_c, cli_c, machine_c, jog_c, compvision_c, remote_c]

        # init note book
        self.imageList = wx.ImageList(16, 16)

        for m in mod_settings:
            self.imageList.Add(m.Factory.GetIcon())

        # for Windows and OS X, tabbed on the left don't work as well
        if sys.platform.startswith('linux'):
            self.noteBook = wx.Notebook(self, size=(700, 400), style=wx.BK_LEFT)
        else:
            self.noteBook = wx.Notebook(self, size=(700, 400))

        self.noteBook.AssignImageList(self.imageList)

        # add pages
        index = 0
        for m in mod_settings:
            self.settings_pages.append(m.Factory.AddPage(self.noteBook, self.configData, index))
            index = index + 1

        # self.noteBook.Layout()
        sizer.Add(self.noteBook, 1, wx.ALL | wx.EXPAND, 5)

        # buttons
        line = wx.StaticLine(self, -1, size=(20, -1), style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.GROW | wx.ALIGN_CENTER_VERTICAL |
                  wx.LEFT | wx.RIGHT | wx.TOP, border=5)

        btnsizer = wx.StdDialogButtonSizer()

        btn = wx.Button(self, wx.ID_OK)
        btnsizer.AddButton(btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btnsizer.AddButton(btn)

        btnsizer.Realize()

        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL |
                  wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizerAndFit(sizer)
        # self.SetAutoLayout(True)
        self.Layout()

    def UpdateConfigData(self):
        for page in self.settings_pages:
            page.UpdateConfigData()
