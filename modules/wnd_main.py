"""----------------------------------------------------------------------------
   wnd_main.py

   Copyright (C) 2013-2018 Wilhelm Duembeg

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
import modules.wnd_editor as ed
import modules.wnd_machine as mc
import modules.wnd_jogging as jog
import modules.wnd_compvision as compv
import modules.machif_progexec as mi_progexec

__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
    "GCODE Step and Alignment Tool (gsat) is a cross-platform GCODE "\
    "debug/step for grbl like GCODE interpreters. With features similar "\
    "to software debuggers. Features Such as breakpoint, change current "\
    "program counter, inspection and modification of variables."


# define authorship information
__authors__ = ['Wilhelm Duembeg']
__author__ = ','.join(__authors__)
__credits__ = []
__copyright__ = 'Copyright (c) 2013-2018'
__license__ = 'GPL v2, Copyright (c) 2013-2014'
__license_str__ = __license__ + '\nhttp://www.gnu.org/licenses/gpl-2.0.txt'

# maintenance information
__maintainer__ = 'Wilhelm Duembeg'
__email__ = 'duembeg.github@gmail.com'
__website__ = 'https://github.com/duembeg/gsat'

# define version information
__requires__ = ['pySerial', 'wxPython']
__version_info__ = (1, 6, 0)
__version__ = 'v%i.%i.%i beta' % __version_info__
__revision__ = __version__


"""----------------------------------------------------------------------------
   Globals:
----------------------------------------------------------------------------"""

# -----------------------------------------------------------------------------
# MENU & TOOL BAR IDs
# -----------------------------------------------------------------------------
gID_TOOLBAR_OPEN = wx.NewId()
gID_TOOLBAR_LINK_STATUS = wx.NewId()
gID_TOOLBAR_PROGRAM_STATUS = wx.NewId()
gID_MENU_MAIN_TOOLBAR = wx.NewId()
gID_MENU_SEARCH_TOOLBAR = wx.NewId()
gID_MENU_RUN_TOOLBAR = wx.NewId()
gID_MENU_STATUS_TOOLBAR = wx.NewId()
gID_MENU_OUTPUT_PANEL = wx.NewId()
gID_MENU_MACHINE_STATUS_PANEL = wx.NewId()
gID_MENU_MACHINE_JOGGING_PANEL = wx.NewId()
gID_MENU_CV2_PANEL = wx.NewId()
gID_MENU_LOAD_DEFAULT_LAYOUT = wx.NewId()
gID_MENU_SAVE_DEFAULT_LAYOUT = wx.NewId()
gID_MENU_RESET_DEFAULT_LAYOUT = wx.NewId()
gID_MENU_LOAD_LAYOUT = wx.NewId()
gID_MENU_SAVE_LAYOUT = wx.NewId()
gID_MENU_RUN = wx.NewId()
gID_MENU_PAUSE = wx.NewId()
gID_MENU_STEP = wx.NewId()
gID_MENU_STOP = wx.NewId()
gID_MENU_BREAK_TOGGLE = wx.NewId()
gID_MENU_BREAK_REMOVE_ALL = wx.NewId()
gID_MENU_SET_PC = wx.NewId()
gID_MENU_RESET_PC = wx.NewId()
gID_MENU_GOTO_PC = wx.NewId()
gID_MENU_MACHINE_REFRESH = wx.NewId()
gID_MENU_MACHINE_CYCLE_START = wx.NewId()
gID_MENU_MACHINE_FEED_HOLD = wx.NewId()
gID_MENU_MACHINE_QUEUE_FLUSH = wx.NewId()
gID_MENU_MACHINE_RESET = wx.NewId()
gID_MENU_MACHINE_CLEAR_ALARM = wx.NewId()
gID_MENU_ABORT = wx.NewId()
gID_MENU_IN2MM = wx.NewId()
gID_MENU_MM2IN = wx.NewId()
gID_MENU_G812G01 = wx.NewId()
gID_MENU_FIND = wx.NewId()
gID_MENU_GOTOLINE = wx.NewId()


gID_TIMER_MACHINE_REFRESH = wx.NewId()
gID_TIMER_RUN = wx.NewId()

# -----------------------------------------------------------------------------
# regular expressions
# -----------------------------------------------------------------------------
gReAxis = re.compile(r'([XYZ])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

idle_count = 0


class gsatLog(wx.PyLog):
    """ custom wxLog
    """

    def __init__(self, textCtrl, logTime=0):
        wx.PyLog.__init__(self)
        self.tc = textCtrl
        self.logTime = logTime

    def DoLogString(self, message, timeStamp):
        if self.tc:
            self.tc.AppendText(message + '\n')


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
            self.configData.get('/mainApp/FileHistory/MaxFiles'))
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

    def UpdatConfigData(self):
        self.configData.set('/mainApp/DisplayRunTimeDialog',
                            self.cbDisplayRunTimeDialog.GetValue())
        self.configData.set('/mainApp/BackupFile',
                            self.cbBackupFile.GetValue())
        self.configData.set('/mainApp/FileHistory/MaxFiles',
                            self.scFileHistory.GetValue())
        self.configData.set('/mainApp/RoundInch2mm',
                            self.scIN2MMRound.GetValue())
        self.configData.set('/mainApp/Roundmm2Inch',
                            self.scMM2INRound.GetValue())


class gsatSettingsDialog(wx.Dialog):
    """ Dialog to control program settings
    """

    def __init__(self, parent, configData, id=wx.ID_ANY, title="Settings",
                 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER):

        wx.Dialog.__init__(self, parent, id, title, style=style)

        self.configData = configData

        self.InitUI()

    def InitUI(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # init note book
        self.imageList = wx.ImageList(16, 16)
        self.imageList.Add(ico.imgGeneralSettings.GetBitmap())
        # self.imageList.Add(ico.imgPlugConnect.GetBitmap())
        self.imageList.Add(ico.imgProgram.GetBitmap())
        self.imageList.Add(ico.imgLog.GetBitmap())
        self.imageList.Add(ico.imgCli.GetBitmap())
        self.imageList.Add(ico.imgMachine.GetBitmap())
        self.imageList.Add(ico.imgMove.GetBitmap())
        self.imageList.Add(ico.imgEye.GetBitmap())

        # for Windows and OS X, tabbed on the left don't work as well
        if sys.platform.startswith('linux'):
            self.noteBook = wx.Notebook(
                self, size=(640, 400), style=wx.BK_LEFT)
        else:
            self.noteBook = wx.Notebook(self, size=(640, 400))

        self.noteBook.AssignImageList(self.imageList)

        # add pages
        self.AddGeneralPage(0)
        self.AddProgramPage(1)
        self.AddOutputPage(2)
        self.AddCliPage(3)
        self.AddMachinePage(4)
        self.AddJoggingPage(5)
        self.AddCV2Panel(6)

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

    def AddGeneralPage(self, page):
        self.generalPage = gsatGeneralSettingsPanel(
            self.noteBook, self.configData)
        self.noteBook.AddPage(self.generalPage, "General")
        self.noteBook.SetPageImage(page, page)

    def AddProgramPage(self, page):
        self.programPage = ed.gsatStyledTextCtrlSettingsPanel(
            self.noteBook, self.configData, "code")
        self.noteBook.AddPage(self.programPage, "Program")
        self.noteBook.SetPageImage(page, page)

    def AddOutputPage(self, page):
        self.outputPage = ed.gsatStyledTextCtrlSettingsPanel(
            self.noteBook, self.configData, "output")
        self.noteBook.AddPage(self.outputPage, "Output")
        self.noteBook.SetPageImage(page, page)

    def AddCliPage(self, page):
        self.cliPage = jog.gsatCliSettingsPanel(self.noteBook, self.configData)
        self.noteBook.AddPage(self.cliPage, "Cli")
        self.noteBook.SetPageImage(page, page)

    def AddMachinePage(self, page):
        self.machinePage = mc.gsatMachineSettingsPanel(
            self.noteBook, self.configData)
        self.noteBook.AddPage(self.machinePage, "Machine")
        self.noteBook.SetPageImage(page, page)

    def AddJoggingPage(self, page):
        self.jogPage = jog.gsatJoggingSettingsPanel(
            self.noteBook, self.configData)
        self.noteBook.AddPage(self.jogPage, "Jogging")
        self.noteBook.SetPageImage(page, page)

    def AddCV2Panel(self, page):
        self.CV2Page = compv.gsatCV2SettingsPanel(
            self.noteBook, self.configData)
        self.noteBook.AddPage(self.CV2Page, " OpenCV2")
        self.noteBook.SetPageImage(page, page)

    def UpdatConfigData(self):
        self.generalPage.UpdatConfigData()
        self.programPage.UpdatConfigData()
        self.outputPage.UpdatConfigData()
        self.cliPage.UpdatConfigData()
        self.machinePage.UpdatConfigData()
        self.jogPage.UpdatConfigData()
        self.CV2Page.UpdatConfigData()


class gsatMainWindow(wx.Frame, gc.EventQueueIf):
    """ Main Window Inits the UI and other panels, it also controls the worker
    threads and resources such as serial port.
    """

    def __init__(self, parent, wnd_id=wx.ID_ANY, title="",
                 cmd_line_options=None, pos=wx.DefaultPosition,
                 size=(800, 600), style=wx.DEFAULT_FRAME_STYLE):

        wx.Frame.__init__(self, parent, wnd_id, title, pos, size, style)
        gc.EventQueueIf.__init__(self)

        # init cmd line options
        self.cmdLineOptions = cmd_line_options

        self.SetIcon(ico.imgGCSBlack32x32.GetIcon())

        if sys.platform in 'darwin':
            # for Mac OS X to properly display icon in task bar
            self.tbicon = wx.TaskBarIcon(iconType=wx.TBI_DOCK)
            self.tbicon.SetIcon(ico.imgGCSBlack32x32.GetIcon(), __appname__)

        # register for thread events
        gc.reg_thread_queue_data_event(self, self.OnThreadEvent)

        # get app data obj
        self.stateData = gc.STATE_DATA

        # get app data obj
        self.configData = gc.CONFIG_DATA

        self.logger = logging.getLogger()
        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI:
            self.logger.info("init logging id:0x%x" % id(self))

        self.InitConfig()

        # init some variables
        self.machifProgExec = None
        self.runTimer = None
        self.runStartTime = 0
        self.runEndTime = 0
        self.eventInCount = 0
        self.eventHandleCount = 0

        # register for close events
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        # self.Bind(wx.EVT_IDLE, self.OnIdle)

        self.machinePort = ""
        self.machineBaud = 0
        self.machineAutoRefresh = False
        self.machineAutoRefreshPeriod = 200

        self.InitUI()
        self.Centre()
        self.Show()

    def InitConfig(self):
        self.displayRuntimeDialog = self.configData.get(
            '/mainApp/DisplayRunTimeDialog')
        self.saveBackupFile = self.configData.get('/mainApp/BackupFile')
        self.maxFileHistory = self.configData.get(
            '/mainApp/FileHistory/MaxFiles', 10)
        self.roundInch2mm = self.configData.get('/mainApp/RoundInch2mm')
        self.roundmm2Inch = self.configData.get('/mainApp/Roundmm2Inch')
        self.stateData.machIfId = mi.GetMachIfId(
            self.configData.get('/machine/Device'))
        self.stateData.machIfName = mi.GetMachIfName(self.stateData.machIfId)
        self.stateData.serialPort = self.configData.get('/machine/Port')
        self.stateData.serialPortBaud = self.configData.get('/machine/Baud')
        self.stateData.machineStatusAutoRefresh = self.configData.get(
            '/machine/AutoRefresh')
        self.stateData.machineStatusAutoRefreshPeriod = self.configData.get(
            '/machine/AutoRefreshPeriod')

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
            self.logger.info("Init config values...")
            self.logger.info("wxVersion:                %s" % wx.version())
            self.logger.info("displayRuntimeDialog:     %s" %
                             self.displayRuntimeDialog)
            self.logger.info("saveBackupFile:           %s" %
                             self.saveBackupFile)
            self.logger.info("maxFileHistory:           %s" %
                             self.maxFileHistory)
            self.logger.info("roundInch2mm:             %s" %
                             self.roundInch2mm)
            self.logger.info("roundmm2Inch:             %s" %
                             self.roundmm2Inch)
            self.logger.info("machIfName:               %s" %
                             self.stateData.machIfName)
            self.logger.info("machIfId:                 %s" %
                             self.stateData.machIfId)
            self.logger.info("machIfPort:               %s" %
                             self.stateData.serialPort)
            self.logger.info("machIfBaud:               %s" %
                             self.stateData.serialPortBaud)
            self.logger.info("machIfAutoRefresh:       %s" %
                             self.stateData.machineStatusAutoRefresh)
            self.logger.info("machineAutoRefreshPeriod: %s" %
                             self.stateData.machineStatusAutoRefreshPeriod)

    def InitUI(self):
        """ Init main UI """

        # init aui manager
        self.aui_mgr = aui.AuiManager()

        # notify AUI which frame to use
        self.aui_mgr.SetManagedWindow(self)

        # experiment with status bar
        self.statusbar = self.CreateStatusBar(1)
        self.statusbar.SetStatusText('')

        self.machineStatusPanel = mc.gsatMachineStatusPanel(
            self, self.configData, self.stateData,)
        self.CV2Panel = compv.gsatCV2Panel(
            self, self.configData, self.stateData, self.cmdLineOptions)
        self.machineJoggingPanel = jog.gsatJoggingPanel(
            self, self.configData, self.stateData)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter,
                  self.machineJoggingPanel.cliComboBox)

        # output Window
        self.outputText = ed.gsatStcStyledTextCtrl(
            self, self.configData, self.stateData, style=wx.NO_BORDER)
        wx.Log_SetActiveTarget(gsatLog(self.outputText))

        # for serious debugging
        # wx.Log_SetActiveTarget(wx.LogStderr())
        # wx.Log_SetTraceMask(wx.TraceMessages)

        # main gcode list control
        self.gcText = ed.gsatGcodeStcStyledTextCtrl(
            self, self.configData, self.stateData, style=wx.NO_BORDER)

        # add the panes to the manager
        self.aui_mgr.AddPane(
            self.gcText,
            aui.AuiPaneInfo().Name("GCODE_PANEL").CenterPane()
            .Caption("G-Code").CloseButton(True).MaximizeButton(True)
            .BestSize(600, 600))

        self.aui_mgr.AddPane(
            self.outputText,
            aui.AuiPaneInfo().Name("OUTPUT_PANEL").Bottom().Position(1)
            .Caption("Output").CloseButton(True).MaximizeButton(True)
            .BestSize(600, 200))

        self.aui_mgr.AddPane(
            self.CV2Panel,
            aui.AuiPaneInfo().Name("CV2_PANEL").Right().Row(1)
            .Caption("Computer Vision").CloseButton(True).MaximizeButton(True)
            .BestSize(640, 530).Hide().Layer(1))

        self.aui_mgr.AddPane(
            self.machineJoggingPanel,
            aui.AuiPaneInfo().Name("MACHINE_JOGGING_PANEL").Right().Row(1)
            .Caption("Machine Jogging").CloseButton(True).MaximizeButton(True)
            .BestSize(400, 600).Layer(1))

        self.aui_mgr.AddPane(
            self.machineStatusPanel,
            aui.AuiPaneInfo().Name("MACHINE_STATUS_PANEL").Right().Row(1)
            .Caption("Machine Status").CloseButton(True).MaximizeButton(True)
            .BestSize(360, 400).Layer(1))

        self.CreateMenu()
        self.CreateToolBar()

        # tell the manager to "commit" all the changes just made
        self.aui_mgr.SetAGWFlags(
            self.aui_mgr.GetAGWFlags() | aui.AUI_MGR_ALLOW_ACTIVE_PANE)

        # load default layout
        self.aui_mgr.SavePerspective()

        self.SaveLayoutData('/mainApp/Layout/Reset')

        self.LoadLayoutData('/mainApp/Layout/Default', False)

        # finish up
        self.aui_mgr.Update()
        wx.CallAfter(self.UpdateUI)
        self.SetPC(0)

        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)

    def CreateMenu(self):

        # Create the menubar
        # self.menuBar = FM.FlatMenuBar(self, wx.ID_ANY, 32, 5,
        #   options = FM_OPT_SHOW_TOOLBAR | FM_OPT_SHOW_CUSTOMIZE)
        # self.menuBar = fm.FlatMenuBar(self, wx.ID_ANY,
        #                               options=fm.FM_OPT_SHOW_TOOLBAR)
        self.menuBar = wx.MenuBar()

        # ---------------------------------------------------------------------
        # File menu
        fileMenu = wx.Menu()
        self.menuBar.Append(fileMenu, "&File")

        openItem = wx.MenuItem(fileMenu, wx.ID_OPEN, "&Open")
        openItem.SetBitmap(ico.imgOpen.GetBitmap())
        fileMenu.AppendItem(openItem)

        recentMenu = wx.Menu()
        fileMenu.AppendMenu(wx.ID_ANY, "&Recent Files", recentMenu)

        # load history
        self.fileHistory = wx.FileHistory(self.maxFileHistory)

        # load form config daat
        for i in list(reversed(range(1, self.maxFileHistory+1))):
            fn = self.configData.get("/mainApp/FileHistory/File%d" % (i))
            if fn is not None:
                self.fileHistory.AddFileToHistory(fn)

        self.fileHistory.UseMenu(recentMenu)
        self.fileHistory.AddFilesToMenu()

        saveItem = wx.MenuItem(fileMenu, wx.ID_SAVE, "&Save")
        if os.name != 'nt':
            saveItem.SetBitmap(ico.imgSave.GetBitmap())
        fileMenu.AppendItem(saveItem)

        saveAsItem = wx.MenuItem(fileMenu, wx.ID_SAVEAS, "Save &As")
        if os.name != 'nt':
            saveAsItem.SetBitmap(ico.imgSave.GetBitmap())
        fileMenu.AppendItem(saveAsItem)

        exitItem = wx.MenuItem(fileMenu, wx.ID_EXIT, "E&xit")
        exitItem.SetBitmap(ico.imgExit.GetBitmap())
        fileMenu.AppendItem(exitItem)

        # ---------------------------------------------------------------------
        # Edit menu
        # viewEdit = wx.Menu()
        # self.menuBar.Append(viewEdit,                   "&Edit")

        # viewEdit.Append(wx.ID_PREFERENCES,              "&Settings")

        # ---------------------------------------------------------------------
        # View menu
        viewMenu = wx.Menu()
        self.menuBar.Append(viewMenu, "&View")

        viewMenu.AppendCheckItem(gID_MENU_MAIN_TOOLBAR, "&Main Tool Bar")
        viewMenu.AppendCheckItem(gID_MENU_SEARCH_TOOLBAR, "&Search Tool Bar")
        viewMenu.AppendCheckItem(gID_MENU_RUN_TOOLBAR, "&Run Tool Bar")
        viewMenu.AppendCheckItem(gID_MENU_STATUS_TOOLBAR, "Status &Tool Bar")
        viewMenu.AppendSeparator()
        viewMenu.AppendCheckItem(gID_MENU_OUTPUT_PANEL, "&Output")
        viewMenu.AppendCheckItem(gID_MENU_MACHINE_STATUS_PANEL,
                                 "Machine &Status")
        viewMenu.AppendCheckItem(gID_MENU_MACHINE_JOGGING_PANEL,
                                 "Machine &Jogging")
        viewMenu.AppendCheckItem(gID_MENU_CV2_PANEL, "Computer &Vision")
        viewMenu.AppendSeparator()
        viewMenu.Append(gID_MENU_LOAD_DEFAULT_LAYOUT, "&Load Layout")
        viewMenu.Append(gID_MENU_SAVE_DEFAULT_LAYOUT, "S&ave Layout")
        viewMenu.Append(gID_MENU_RESET_DEFAULT_LAYOUT, "R&eset Layout")
        viewMenu.AppendSeparator()

        settingsItem = wx.MenuItem(viewMenu, wx.ID_PREFERENCES, "&Settings")
        settingsItem.SetBitmap(ico.imgSettings.GetBitmap())
        viewMenu.AppendItem(settingsItem)

        # ---------------------------------------------------------------------
        # Run menu
        runMenu = wx.Menu()
        self.menuBar.Append(runMenu, "&Run")

        runItem = wx.MenuItem(runMenu, gID_MENU_RUN, "&Run\tF5")
        if os.name != 'nt':
            runItem.SetBitmap(ico.imgPlay.GetBitmap())
        runMenu.AppendItem(runItem)

        pauseItem = wx.MenuItem(runMenu, gID_MENU_PAUSE, "Pa&use")
        if os.name != 'nt':
            pauseItem.SetBitmap(ico.imgPause.GetBitmap())
        runMenu.AppendItem(pauseItem)

        stepItem = wx.MenuItem(runMenu, gID_MENU_STEP, "S&tep")
        if os.name != 'nt':
            stepItem.SetBitmap(ico.imgStep.GetBitmap())
        runMenu.AppendItem(stepItem)

        stopItem = wx.MenuItem(runMenu, gID_MENU_STOP, "&Stop")
        if os.name != 'nt':
            stopItem.SetBitmap(ico.imgStop.GetBitmap())
        runMenu.AppendItem(stopItem)

        runMenu.AppendSeparator()
        breakItem = wx.MenuItem(runMenu, gID_MENU_BREAK_TOGGLE,
                                "Brea&kpoint Toggle\tF9")
        if os.name != 'nt':
            breakItem.SetBitmap(ico.imgBreak.GetBitmap())
        runMenu.AppendItem(breakItem)

        runMenu.Append(gID_MENU_BREAK_REMOVE_ALL, "Breakpoint &Remove All")

        runMenu.AppendSeparator()

        setPCItem = wx.MenuItem(runMenu, gID_MENU_SET_PC, "Set &PC")
        if os.name != 'nt':
            setPCItem.SetBitmap(ico.imgSetMapPin.GetBitmap())
        runMenu.AppendItem(setPCItem)

        resetPCItem = wx.MenuItem(runMenu, gID_MENU_RESET_PC, "&Reset PC")
        if os.name != 'nt':
            resetPCItem.SetBitmap(ico.imgResetMapPin.GetBitmap())
        runMenu.AppendItem(resetPCItem)

        gotoPCItem = wx.MenuItem(runMenu, gID_MENU_GOTO_PC, "&Goto PC")
        if os.name != 'nt':
            gotoPCItem.SetBitmap(ico.imgGotoMapPin.GetBitmap())
        runMenu.AppendItem(gotoPCItem)

        runMenu.AppendSeparator()

        machineRefresh = wx.MenuItem(
            runMenu, gID_MENU_MACHINE_REFRESH, "Machine &Refresh\tCtrl+R")
        if os.name != 'nt':
            machineRefresh.SetBitmap(ico.imgMachineRefresh.GetBitmap())
        runMenu.AppendItem(machineRefresh)

        machineCycleStart = wx.MenuItem(
            runMenu, gID_MENU_MACHINE_CYCLE_START, "Machine &Cycle Start")
        if os.name != 'nt':
            machineCycleStart.SetBitmap(ico.imgCycleStart.GetBitmap())
        runMenu.AppendItem(machineCycleStart)

        machineFeedHold = wx.MenuItem(
            runMenu, gID_MENU_MACHINE_FEED_HOLD, "Machine &Feed Hold")
        if os.name != 'nt':
            machineFeedHold.SetBitmap(ico.imgFeedHold.GetBitmap())
        runMenu.AppendItem(machineFeedHold)

        machineQueueFlush = wx.MenuItem(
            runMenu, gID_MENU_MACHINE_QUEUE_FLUSH, "Machine &Queue Flush")
        if os.name != 'nt':
            machineQueueFlush.SetBitmap(ico.imgQueueFlush.GetBitmap())
        runMenu.AppendItem(machineQueueFlush)

        machineReset = wx.MenuItem(
            runMenu, gID_MENU_MACHINE_RESET, "Machine Reset")
        if os.name != 'nt':
            machineReset.SetBitmap(ico.imgMachineReset.GetBitmap())
        runMenu.AppendItem(machineReset)

        machineClearAlarm = wx.MenuItem(
            runMenu, gID_MENU_MACHINE_CLEAR_ALARM, "Machine Clear Alarm")
        if os.name != 'nt':
            machineReset.SetBitmap(ico.imgClearAlarm.GetBitmap())
        runMenu.AppendItem(machineClearAlarm)

        runMenu.AppendSeparator()

        abortItem = wx.MenuItem(runMenu, gID_MENU_ABORT, "&Abort")
        if os.name != 'nt':
            abortItem.SetBitmap(ico.imgAbort.GetBitmap())
        runMenu.AppendItem(abortItem)

        # ---------------------------------------------------------------------
        # Tool menu
        toolMenu = wx.Menu()
        self.menuBar.Append(toolMenu, "&Tools")

        toolMenu.Append(gID_MENU_IN2MM, "&Inch to mm")
        toolMenu.Append(gID_MENU_MM2IN, "&mm to Inch")
        toolMenu.AppendSeparator()
        toolMenu.Append(gID_MENU_G812G01, "&G81 to G01")

        # ---------------------------------------------------------------------
        # Help menu
        helpMenu = wx.Menu()
        self.menuBar.Append(helpMenu, "&Help")

        aboutItem = wx.MenuItem(helpMenu, wx.ID_ABOUT, "&About", "About gsat")
        aboutItem.SetBitmap(ico.imgAbout.GetBitmap())
        helpMenu.AppendItem(aboutItem)

        # ---------------------------------------------------------------------
        # Bind events to handlers

        # ---------------------------------------------------------------------
        # File menu bind
        self.Bind(wx.EVT_MENU,        self.OnFileOpen,     id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU_RANGE,  self.OnFileHistory,
                  id=wx.ID_FILE1, id2=wx.ID_FILE9)
        self.Bind(wx.EVT_MENU,        self.OnFileSave,     id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU,        self.OnFileSaveAs,   id=wx.ID_SAVEAS)
        self.Bind(wx.EVT_MENU,        self.OnClose,        id=wx.ID_EXIT)
        self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN,
                  self.OnDropDownToolBarOpen,   id=gID_TOOLBAR_OPEN)

        self.Bind(wx.EVT_UPDATE_UI, self.OnFileOpenUpdate, id=wx.ID_OPEN)
        self.Bind(wx.EVT_UPDATE_UI, self.OnFileSaveUpdate, id=wx.ID_SAVE)
        self.Bind(wx.EVT_UPDATE_UI, self.OnFileSaveAsUpdate,
                  id=wx.ID_SAVEAS)

        # ---------------------------------------------------------------------
        # Search menu bind
        self.Bind(wx.EVT_MENU, self.OnFind,                id=gID_MENU_FIND)
        self.Bind(wx.EVT_MENU, self.OnGotoLine,
                  id=gID_MENU_GOTOLINE)

        # ---------------------------------------------------------------------
        # View menu bind
        self.Bind(wx.EVT_MENU, self.OnMainToolBar,
                  id=gID_MENU_MAIN_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnSearchToolBar,
                  id=gID_MENU_SEARCH_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnRunToolBar,
                  id=gID_MENU_RUN_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnStatusToolBar,
                  id=gID_MENU_STATUS_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnOutput,
                  id=gID_MENU_OUTPUT_PANEL)
        self.Bind(wx.EVT_MENU, self.OnMachineStatus,
                  id=gID_MENU_MACHINE_STATUS_PANEL)
        self.Bind(wx.EVT_MENU, self.OnMachineJogging,
                  id=gID_MENU_MACHINE_JOGGING_PANEL)
        self.Bind(wx.EVT_MENU, self.OnComputerVision,
                  id=gID_MENU_CV2_PANEL)
        self.Bind(wx.EVT_MENU, self.OnLoadDefaultLayout,
                  id=gID_MENU_LOAD_DEFAULT_LAYOUT)
        self.Bind(wx.EVT_MENU, self.OnSaveDefaultLayout,
                  id=gID_MENU_SAVE_DEFAULT_LAYOUT)
        self.Bind(wx.EVT_MENU, self.OnResetDefaultLayout,
                  id=gID_MENU_RESET_DEFAULT_LAYOUT)

        self.Bind(wx.EVT_UPDATE_UI, self.OnMainToolBarUpdate,
                  id=gID_MENU_MAIN_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnSearchToolBarUpdate,
                  id=gID_MENU_SEARCH_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnRunToolBarUpdate,
                  id=gID_MENU_RUN_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnStatusToolBarUpdate,
                  id=gID_MENU_STATUS_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnOutputUpdate,
                  id=gID_MENU_OUTPUT_PANEL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineStatusUpdate,
                  id=gID_MENU_MACHINE_STATUS_PANEL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineJoggingUpdate,
                  id=gID_MENU_MACHINE_JOGGING_PANEL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnComputerVisionUpdate,
                  id=gID_MENU_CV2_PANEL)

        self.Bind(wx.EVT_MENU, self.OnSettings,
                  id=wx.ID_PREFERENCES)

        # ---------------------------------------------------------------------
        # Run menu bind
        self.Bind(wx.EVT_MENU, self.OnRun, id=gID_MENU_RUN)
        self.Bind(wx.EVT_MENU, self.OnPause, id=gID_MENU_PAUSE)
        self.Bind(wx.EVT_MENU, self.OnStep, id=gID_MENU_STEP)
        self.Bind(wx.EVT_MENU, self.OnStop, id=gID_MENU_STOP)
        self.Bind(wx.EVT_MENU, self.OnBreakToggle,
                  id=gID_MENU_BREAK_TOGGLE)
        self.Bind(wx.EVT_MENU, self.OnBreakRemoveAll,
                  id=gID_MENU_BREAK_REMOVE_ALL)
        self.Bind(wx.EVT_MENU, self.OnSetPC, id=gID_MENU_SET_PC)
        self.Bind(wx.EVT_MENU, self.OnResetPC,
                  id=gID_MENU_RESET_PC)
        self.Bind(wx.EVT_MENU, self.OnGoToPC, id=gID_MENU_GOTO_PC)
        self.Bind(wx.EVT_MENU, self.OnMachineRefresh,
                  id=gID_MENU_MACHINE_REFRESH)
        self.Bind(wx.EVT_MENU, self.OnMachineCycleStart,
                  id=gID_MENU_MACHINE_CYCLE_START)
        self.Bind(wx.EVT_MENU, self.OnMachineFeedHold,
                  id=gID_MENU_MACHINE_FEED_HOLD)
        self.Bind(wx.EVT_MENU, self.OnMachineQueueFlush,
                  id=gID_MENU_MACHINE_QUEUE_FLUSH)
        self.Bind(wx.EVT_MENU, self.OnMachineReset,
                  id=gID_MENU_MACHINE_RESET)
        self.Bind(wx.EVT_MENU, self.OnMachineClearAlarm,
                  id=gID_MENU_MACHINE_CLEAR_ALARM)
        self.Bind(wx.EVT_MENU, self.OnAbort, id=gID_MENU_ABORT)

        self.Bind(wx.EVT_BUTTON, self.OnRun, id=gID_MENU_RUN)
        self.Bind(wx.EVT_BUTTON, self.OnPause, id=gID_MENU_PAUSE)
        self.Bind(wx.EVT_BUTTON, self.OnStep, id=gID_MENU_STEP)
        self.Bind(wx.EVT_BUTTON, self.OnStop, id=gID_MENU_STOP)
        self.Bind(wx.EVT_BUTTON, self.OnBreakToggle,
                  id=gID_MENU_BREAK_TOGGLE)
        self.Bind(wx.EVT_BUTTON, self.OnSetPC, id=gID_MENU_SET_PC)
        self.Bind(wx.EVT_BUTTON, self.OnResetPC,
                  id=gID_MENU_RESET_PC)
        self.Bind(wx.EVT_BUTTON, self.OnGoToPC, id=gID_MENU_GOTO_PC)
        self.Bind(wx.EVT_BUTTON, self.OnMachineRefresh,
                  id=gID_MENU_MACHINE_REFRESH)
        self.Bind(wx.EVT_BUTTON, self.OnMachineCycleStart,
                  id=gID_MENU_MACHINE_CYCLE_START)
        self.Bind(wx.EVT_BUTTON, self.OnMachineFeedHold,
                  id=gID_MENU_MACHINE_FEED_HOLD)
        self.Bind(wx.EVT_BUTTON, self.OnMachineQueueFlush,
                  id=gID_MENU_MACHINE_QUEUE_FLUSH)
        self.Bind(wx.EVT_BUTTON, self.OnMachineReset,
                  id=gID_MENU_MACHINE_RESET)
        self.Bind(wx.EVT_BUTTON, self.OnMachineClearAlarm,
                  id=gID_MENU_MACHINE_CLEAR_ALARM)
        self.Bind(wx.EVT_BUTTON, self.OnAbort, id=gID_MENU_ABORT)

        self.Bind(wx.EVT_UPDATE_UI, self.OnRunUpdate, id=gID_MENU_RUN)
        self.Bind(wx.EVT_UPDATE_UI, self.OnPauseUpdate, id=gID_MENU_PAUSE)
        self.Bind(wx.EVT_UPDATE_UI, self.OnStepUpdate, id=gID_MENU_STEP)
        self.Bind(wx.EVT_UPDATE_UI, self.OnStopUpdate, id=gID_MENU_STOP)
        self.Bind(wx.EVT_UPDATE_UI, self.OnBreakToggleUpdate,
                  id=gID_MENU_BREAK_TOGGLE)
        self.Bind(wx.EVT_UPDATE_UI, self.OnBreakRemoveAllUpdate,
                  id=gID_MENU_BREAK_REMOVE_ALL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnSetPCUpdate, id=gID_MENU_SET_PC)
        self.Bind(wx.EVT_UPDATE_UI, self.OnResetPCUpdate, id=gID_MENU_RESET_PC)
        self.Bind(wx.EVT_UPDATE_UI, self.OnGoToPCUpdate, id=gID_MENU_GOTO_PC)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineRefreshUpdate,
                  id=gID_MENU_MACHINE_REFRESH)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineCycleStartUpdate,
                  id=gID_MENU_MACHINE_CYCLE_START)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineFeedHoldUpdate,
                  id=gID_MENU_MACHINE_FEED_HOLD)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineQueueFlushUpdate,
                  id=gID_MENU_MACHINE_QUEUE_FLUSH)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineResetUpdate,
                  id=gID_MENU_MACHINE_RESET)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineClearAlarmUpdate,
                  id=gID_MENU_MACHINE_CLEAR_ALARM)
        self.Bind(wx.EVT_UPDATE_UI, self.OnAbortUpdate, id=gID_MENU_ABORT)

        # ---------------------------------------------------------------------
        # tools menu bind
        self.Bind(wx.EVT_MENU, self.OnInch2mm, id=gID_MENU_IN2MM)
        self.Bind(wx.EVT_MENU, self.Onmm2Inch, id=gID_MENU_MM2IN)
        self.Bind(wx.EVT_MENU, self.OnG812G01, id=gID_MENU_G812G01)

        self.Bind(wx.EVT_UPDATE_UI, self.OnInch2mmUpdate, id=gID_MENU_IN2MM)
        self.Bind(wx.EVT_UPDATE_UI, self.Onmm2InchUpdate, id=gID_MENU_MM2IN)
        self.Bind(wx.EVT_UPDATE_UI, self.OnG812G01Update, id=gID_MENU_G812G01)

        # ---------------------------------------------------------------------
        # Help menu bind
        self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)

        # ---------------------------------------------------------------------
        # Status tool bar
        self.Bind(wx.EVT_MENU, self.OnLinkStatus, id=gID_TOOLBAR_LINK_STATUS)

        # ---------------------------------------------------------------------
        # Create shortcut keys for menu
        acceleratorTable = wx.AcceleratorTable([
            # (wx.ACCEL_ALT,       ord('X'),         wx.ID_EXIT),
            # (wx.ACCEL_CTRL,      ord('H'),         helpID),
            # (wx.ACCEL_CTRL,      ord('F'),         findID),
            (wx.ACCEL_NORMAL,    wx.WXK_F5,        gID_MENU_RUN),
            (wx.ACCEL_NORMAL,    wx.WXK_F9,        gID_MENU_BREAK_TOGGLE),
        ])

        self.SetAcceleratorTable(acceleratorTable)

        # finish up...
        self.SetMenuBar(self.menuBar)

    def CreateToolBar(self):
        iconSize = (16, 16)

        # ---------------------------------------------------------------------
        # Main Tool Bar
        self.appToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition,
                                         wx.DefaultSize,
                                         agwStyle=aui.AUI_TB_GRIPPER |
                                         aui.AUI_TB_OVERFLOW |
                                         aui.AUI_TB_TEXT |
                                         aui.AUI_TB_HORZ_TEXT |
                                         # aui.AUI_TB_PLAIN_BACKGROUND
                                         aui.AUI_TB_DEFAULT_STYLE)

        self.appToolBar.SetToolBitmapSize(iconSize)

        self.appToolBar.AddSimpleTool(gID_TOOLBAR_OPEN, "Open",
                                      ico.imgOpen.GetBitmap(), "Open\tCtrl+O")

        self.appToolBar.AddSimpleTool(wx.ID_SAVE, "Save",
                                      ico.imgSave.GetBitmap(), "Save\tCtrl+S")
        self.appToolBar.SetToolDisabledBitmap(
            wx.ID_SAVE, ico.imgSaveDisabled.GetBitmap())

        self.appToolBar.AddSimpleTool(wx.ID_SAVEAS, "Save As",
                                      ico.imgSave.GetBitmap(),
                                      "Save As")
        self.appToolBar.SetToolDisabledBitmap(
            wx.ID_SAVEAS, ico.imgSaveDisabled.GetBitmap())

        self.appToolBar.SetToolDropDown(gID_TOOLBAR_OPEN, True)

        self.appToolBar.Realize()

        self.aui_mgr.AddPane(self.appToolBar,
                             aui.AuiPaneInfo().Name("MAIN_TOOLBAR")
                             .Caption("Main Tool Bar").ToolbarPane()
                             .Top().Gripper())

        # ---------------------------------------------------------------------
        # Search Tool Bar
        self.searchToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition,
                                            wx.DefaultSize,
                                            agwStyle=aui.AUI_TB_GRIPPER |
                                            aui.AUI_TB_OVERFLOW |
                                            aui.AUI_TB_TEXT |
                                            aui.AUI_TB_HORZ_TEXT |
                                            # aui.AUI_TB_PLAIN_BACKGROUND
                                            aui.AUI_TB_DEFAULT_STYLE)

        self.searchToolBarFind = wx.TextCtrl(self.searchToolBar,
                                             size=(100, -1),
                                             style=wx.TE_PROCESS_ENTER)
        self.searchToolBar.AddControl(self.searchToolBarFind)
        self.searchToolBar.SetToolTipString("Find Text")
        self.searchToolBar.AddSimpleTool(gID_MENU_FIND, "",
                                         ico.imgFind.GetBitmap(),
                                         "Find Next\tF3")
        self.Bind(wx.EVT_TEXT_ENTER, self.OnFind, self.searchToolBarFind)

        self.searchToolBarGotoLine = wx.TextCtrl(self.searchToolBar,
                                                 size=(50, -1),
                                                 style=wx.TE_PROCESS_ENTER)
        self.searchToolBar.AddControl(self.searchToolBarGotoLine)
        self.searchToolBar.SetToolTipString("Line Number")
        self.searchToolBar.AddSimpleTool(gID_MENU_GOTOLINE, "",
                                         ico.imgGotoLine.GetBitmap(),
                                         "Goto Line")
        self.Bind(wx.EVT_TEXT_ENTER, self.OnGotoLine,
                  self.searchToolBarGotoLine)

        self.searchToolBar.Realize()

        self.aui_mgr.AddPane(self.searchToolBar,
                             aui.AuiPaneInfo().Name("SEARCH_TOOLBAR")
                             .Caption("Search Tool Bar").ToolbarPane()
                             .Top().Gripper())

        # ---------------------------------------------------------------------
        # GCODE Tool Bar
        self.gcodeToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition,
                                           wx.DefaultSize,
                                           agwStyle=aui.AUI_TB_GRIPPER |
                                           aui.AUI_TB_OVERFLOW |
                                           # aui.AUI_TB_TEXT |
                                           # aui.AUI_TB_HORZ_TEXT |
                                           # aui.AUI_TB_PLAIN_BACKGROUND
                                           aui.AUI_TB_DEFAULT_STYLE)

        self.gcodeToolBar.SetToolBitmapSize(iconSize)

        self.gcodeToolBar.AddSimpleTool(gID_MENU_RUN, "Run",
                                        ico.imgPlay.GetBitmap(),
                                        "Run\tF5")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_RUN, ico.imgPlayDisabled.GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_PAUSE, "Pause",
                                        ico.imgPause.GetBitmap(),
                                        "Pause")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_PAUSE, ico.imgPauseDisabled.GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_STEP, "Step",
                                        ico.imgStep.GetBitmap(),
                                        "Step")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_STEP, ico.imgStepDisabled.GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_STOP, "Stop",
                                        ico.imgStop.GetBitmap(),
                                        "Stop")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_STOP, ico.imgStopDisabled.GetBitmap())

        self.gcodeToolBar.AddSeparator()

        self.gcodeToolBar.AddSimpleTool(gID_MENU_BREAK_TOGGLE, "Break Toggle",
                                        ico.imgBreak.GetBitmap(),
                                        "Breakpoint Toggle\tF9")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_BREAK_TOGGLE, ico.imgBreakDisabled.GetBitmap())

        self.gcodeToolBar.AddSeparator()

        self.gcodeToolBar.AddSimpleTool(gID_MENU_SET_PC, "Set PC",
                                        ico.imgSetMapPin.GetBitmap(),
                                        "Set Program Counter (PC) to current "
                                        "position")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_SET_PC, ico.imgSetMapPinDisabled.GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_RESET_PC, "Set PC",
                                        ico.imgResetMapPin.GetBitmap(),
                                        "Reset Program Counter (PC) to "
                                        "beginning of file")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_RESET_PC, ico.imgResetMapPinDisabled.GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_GOTO_PC, "Goto PC",
                                        ico.imgGotoMapPin.GetBitmap(),
                                        "Goto current Program Counter (PC)")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_GOTO_PC, ico.imgGotoMapPinDisabled.GetBitmap())

        self.gcodeToolBar.AddSeparator()

        self.gcodeToolBar.AddSimpleTool(gID_MENU_MACHINE_REFRESH,
                                        "Machine Refresh",
                                        ico.imgMachineRefresh.GetBitmap(),
                                        "Machine Refresh")
        self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_REFRESH,
                                                ico.imgMachineRefreshDisabled
                                                .GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_MACHINE_CYCLE_START,
                                        "Cycle Start",
                                        ico.imgCycleStart.GetBitmap(),
                                        "Machine Cycle Start")
        self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_CYCLE_START,
                                                ico.imgCycleStartDisabled
                                                .GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_MACHINE_FEED_HOLD,
                                        "Feed Hold",
                                        ico.imgFeedHold.GetBitmap(),
                                        "Machine Feed Hold")
        self.gcodeToolBar.SetToolDisabledBitmap(
            gID_MENU_MACHINE_FEED_HOLD, ico.imgFeedHoldDisabled.GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_MACHINE_QUEUE_FLUSH,
                                        "Queue Flush",
                                        ico.imgQueueFlush.GetBitmap(),
                                        "Machine Queue Flush")
        self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_QUEUE_FLUSH,
                                                ico.imgQueueFlushDisabled
                                                .GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_MACHINE_RESET, "Reset",
                                        ico.imgMachineReset.GetBitmap(),
                                        "Machine Reset")
        self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_RESET,
                                                ico.imgMachineResetDisabled
                                                .GetBitmap())

        self.gcodeToolBar.AddSimpleTool(gID_MENU_MACHINE_CLEAR_ALARM,
                                        "Clear Alarm",
                                        ico.imgClearAlarm.GetBitmap(),
                                        "Machine Clear Alarm")
        self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_CLEAR_ALARM,
                                                ico.imgClearAlarmDisabled
                                                .GetBitmap())
        self.gcodeToolBar.AddSeparator()

        self.gcodeToolBar.AddSimpleTool(gID_MENU_ABORT, "Abort",
                                        ico.imgAbort.GetBitmap(),
                                        "Abort")
        self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_ABORT,
                                                ico.imgAbortDisabled
                                                .GetBitmap())

        self.gcodeToolBar.Realize()

        self.aui_mgr.AddPane(self.gcodeToolBar,
                             aui.AuiPaneInfo().Name("GCODE_TOOLBAR")
                             .Caption("Program Tool Bar").ToolbarPane()
                             .Top().Gripper())

        # ---------------------------------------------------------------------
        # Status Tool Bar
        self.statusToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition,
                                            wx.DefaultSize,
                                            agwStyle=aui.AUI_TB_GRIPPER |
                                            aui.AUI_TB_OVERFLOW |
                                            # aui.AUI_TB_TEXT |
                                            aui.AUI_TB_HORZ_TEXT |
                                            # aui.AUI_TB_PLAIN_BACKGROUND
                                            aui.AUI_TB_DEFAULT_STYLE)

        self.statusToolBar.SetToolBitmapSize(iconSize)

        self.statusToolBar.AddSimpleTool(gID_TOOLBAR_LINK_STATUS, "123456789",
                                         ico.imgPlugDisconnect.GetBitmap(),
                                         "Open/Close Device port")
        self.statusToolBar.SetToolDisabledBitmap(gID_MENU_RUN,
                                                 ico.imgPlugDisconnect
                                                 .GetBitmap())

        self.statusToolBar.AddSimpleTool(gID_TOOLBAR_PROGRAM_STATUS, "123456",
                                         ico.imgProgram.GetBitmap(),
                                         "Program Status")
        self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_PROGRAM_STATUS,
                                                 ico.imgProgram.GetBitmap())

        self.statusToolBar.Realize()

        self.aui_mgr.AddPane(self.statusToolBar, aui.AuiPaneInfo()
                             .Name("STATUS_TOOLBAR")
                             .Caption("Status Tool Bar").ToolbarPane()
                             .Top().Gripper())

        # finish up
        self.appToolBar.Refresh()
        self.gcodeToolBar.Refresh()
        self.statusToolBar.Refresh()

    def UpdateUI(self):
        self.gcText.UpdateUI(self.stateData)
        self.machineStatusPanel.UpdateUI(self.stateData)
        self.machineJoggingPanel.UpdateUI(self.stateData)
        self.CV2Panel.UpdateUI(self.stateData)

        # Force update tool bar items
        self.OnAppToolBarForceUpdate()
        self.OnStatusToolBarForceUpdate()
        self.OnRunToolBarForceUpdate()

        self.aui_mgr.Update()

    """------------------------------------------------------------------------
   gsatMainWindow: UI Event Handlers
   -------------------------------------------------------------------------"""

    def OnAppToolBarForceUpdate(self):
        state = True
        if self.stateData.serialPortIsOpen and \
           (self.stateData.swState == gc.STATE_RUN or
                self.stateData.swState == gc.STATE_STEP):

            state = False

        self.appToolBar.EnableTool(gID_TOOLBAR_OPEN, state)
        self.appToolBar.Refresh()

    # -------------------------------------------------------------------------
    # File Menu Handlers
    # -------------------------------------------------------------------------
    def OnFileOpen(self, e):
        """ File Open """
        # get current file data
        currentPath = self.stateData.gcodeFileName
        (currentDir, currentFile) = os.path.split(currentPath)

        if len(currentDir) == 0:
            currentDir = os.getcwd()

        # init file dialog
        dlgFile = wx.FileDialog(
            self, message="Choose a file",
            defaultDir=currentDir,
            defaultFile=currentFile,
            wildcard=gc.FILE_WILDCARD,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlgFile.ShowModal() == wx.ID_OK:
            # got file, open and present progress
            self.stateData.gcodeFileName = dlgFile.GetPath()
            self.lineNumber = 0

            # save history
            self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)

            # update file history in config data
            historyCount = self.fileHistory.GetCount()

            if historyCount > 0:
                for index in range(historyCount):
                    self.configData.add(
                        '/mainApp/FileHistory/File%d' % (index+1),
                        self.fileHistory.GetHistoryFile(index)
                    )
                self.configData.save()

            self.OnDoFileOpen(e, self.stateData.gcodeFileName)

    def OnFileOpenUpdate(self, e):
        state = True
        if self.stateData.serialPortIsOpen and \
           (self.stateData.swState == gc.STATE_RUN or
                self.stateData.swState == gc.STATE_STEP):

            state = False

        e.Enable(state)
        self.appToolBar.EnableTool(gID_TOOLBAR_OPEN, state)

    def OnDropDownToolBarOpen(self, e):
        if not e.IsDropDownClicked():
            self.OnFileOpen(e)
        else:
            toolbBar = e.GetEventObject()
            toolbBar.SetToolSticky(e.GetId(), True)

            historyCount = self.fileHistory.GetCount()

            if historyCount > 0:
                # create the popup menu
                menuPopup = wx.Menu()

                for index in range(historyCount):
                    m = wx.MenuItem(menuPopup, wx.ID_FILE1+index,
                                    "&%d %s" %
                                    (index,
                                     self.fileHistory.GetHistoryFile(index)))

                    menuPopup.AppendItem(m)

                # line up our menu with the button
                rect = toolbBar.GetToolRect(e.GetId())
                pt = toolbBar.ClientToScreen(rect.GetBottomLeft())
                pt = self.ScreenToClient(pt)

                self.PopupMenu(menuPopup, pt)

            # make sure the button is "un-stuck"
            toolbBar.SetToolSticky(e.GetId(), False)

    def OnFileHistory(self, e):
        fileNumber = e.GetId() - wx.ID_FILE1
        self.stateData.gcodeFileName = self.fileHistory.GetHistoryFile(
            fileNumber)
        self.fileHistory.AddFileToHistory(
            self.stateData.gcodeFileName)  # move up the list

        # update file history in config data
        historyCount = self.fileHistory.GetCount()

        if historyCount > 0:
            for index in range(historyCount):
                self.configData.add(
                    '/mainApp/FileHistory/File%d' % (index+1),
                    self.fileHistory.GetHistoryFile(index)
                )
            self.configData.save()

        self.OnDoFileOpen(e, self.stateData.gcodeFileName)

    def OnDoFileOpen(self, e, fileName=None):
        if os.path.exists(fileName):
            self.stateData.gcodeFileName = fileName

            readOnly = self.gcText.GetReadOnly()
            self.gcText.SetReadOnly(False)
            self.gcText.LoadFile(self.stateData.gcodeFileName)
            self.gcText.SetReadOnly(readOnly)

            self.stateData.fileIsOpen = True
            self.SetTitle("%s - %s" % (os.path.basename(
                          self.stateData.gcodeFileName), __appname__))

            self.stateData.breakPoints = set()
            self.SetPC(0)
            self.gcText.GoToPC()
            self.UpdateUI()

            self.statusbar.SetStatusText(os.path.basename(fileName))
        else:
            dlg = wx.MessageDialog(self,
                                   "The file doesn't exits.\n"
                                   "File: %s\n\n"
                                   "Please check the path and try again." %
                                   fileName, "", wx.OK | wx.ICON_STOP)
            dlg.ShowModal()
            dlg.Destroy()

        # self.gcText.SetReadOnly(True)

    def OnFileSave(self, e):
        if not self.stateData.fileIsOpen:
            self.OnFileSaveAs(e)
        else:
            if self.saveBackupFile:
                shutil.copyfile(self.stateData.gcodeFileName,
                                self.stateData.gcodeFileName+"~")

            self.gcText.SaveFile(self.stateData.gcodeFileName)

    def OnFileSaveUpdate(self, e):
        e.Enable(self.gcText.GetModify())

    def OnFileSaveAs(self, e):
        # get current file data
        currentPath = self.stateData.gcodeFileName
        (currentDir, currentFile) = os.path.split(currentPath)

        if len(currentDir) == 0:
            currentDir = os.getcwd()

        # init file dialog
        dlgFile = wx.FileDialog(
            self, message="Create a file",
            defaultDir=currentDir,
            defaultFile=currentFile,
            wildcard=gc.FILE_WILDCARD,
            style=wx.SAVE
        )

        if dlgFile.ShowModal() == wx.ID_OK:
            # got file, open and present progress
            self.stateData.gcodeFileName = dlgFile.GetPath()
            self.lineNumber = 0

            # save history
            self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)

            # update file history in config data
            historyCount = self.fileHistory.GetCount()

            if historyCount > 0:
                for index in range(historyCount):
                    self.configData.add(
                        '/mainApp/FileHistory/File%d' % (index+1),
                        self.fileHistory.GetHistoryFile(index)
                    )
                self.configData.save()

            self.gcText.SaveFile(self.stateData.gcodeFileName)

            # update title
            self.SetTitle(
                "%s - %s" %
                (os.path.basename(self.stateData.gcodeFileName), __appname__))

            self.statusbar.SetStatusText(
                os.path.basename(self.stateData.gcodeFileName))

            self.UpdateUI()

    def OnFileSaveAsUpdate(self, e):
        e.Enable(self.stateData.fileIsOpen or self.gcText.GetModify())

    # -------------------------------------------------------------------------
    # Search Menu Handlers
    # -------------------------------------------------------------------------
    def OnFind(self, e):
        searcText = self.searchToolBarFind.GetValue()
        self.gcText.FindNextText(searcText)

    def OnGotoLine(self, e):
        gotoLine = self.searchToolBarGotoLine.GetValue()
        if len(gotoLine) > 0:
            gotoLine = int(gotoLine)-1
        else:
            gotoLine = 0

        self.gcText.SetFocus()
        self.gcText.GotoLine(gotoLine)

    # -------------------------------------------------------------------------
    # View Menu Handlers
    # -------------------------------------------------------------------------
    def OnViewMenu(self, e, pane):
        panelInfo = self.aui_mgr.GetPane(pane)

        if panelInfo.IsShown():
            panelInfo.Hide()
        else:
            panelInfo.Show()

        self.aui_mgr.Update()

    def OnViewMenuUpdate(self, e, pane):
        panelInfo = self.aui_mgr.GetPane(pane)
        if panelInfo.IsShown():
            e.Check(True)
        else:
            e.Check(False)
        # self.aui_mgr.Update()

    def OnViewMenuToolBar(self, e, toolBar):
        self.OnViewMenu(e, toolBar)

        panelInfo = self.aui_mgr.GetPane(toolBar)
        if panelInfo.IsShown() and panelInfo.IsDocked():
            toolBar.SetGripperVisible(True)
            self.aui_mgr.Update()

    def OnMainToolBar(self, e):
        self.OnViewMenuToolBar(e, self.appToolBar)

    def OnMainToolBarUpdate(self, e):
        self.OnViewMenuUpdate(e, self.appToolBar)

    def OnSearchToolBar(self, e):
        self.OnViewMenuToolBar(e, self.searchToolBar)

    def OnSearchToolBarUpdate(self, e):
        self.OnViewMenuUpdate(e, self.searchToolBar)

    def OnRunToolBar(self, e):
        self.OnViewMenuToolBar(e, self.gcodeToolBar)

    def OnRunToolBarUpdate(self, e):
        self.OnViewMenuUpdate(e, self.gcodeToolBar)

    def OnStatusToolBar(self, e):
        self.OnViewMenuToolBar(e, self.statusToolBar)

    def OnStatusToolBarUpdate(self, e):
        self.OnViewMenuUpdate(e, self.statusToolBar)

    def OnOutput(self, e):
        self.OnViewMenu(e, self.outputText)

    def OnOutputUpdate(self, e):
        self.OnViewMenuUpdate(e, self.outputText)

    def OnMachineStatus(self, e):
        self.OnViewMenu(e, self.machineStatusPanel)

    def OnMachineStatusUpdate(self, e):
        self.OnViewMenuUpdate(e, self.machineStatusPanel)

    def OnMachineJogging(self, e):
        self.OnViewMenu(e, self.machineJoggingPanel)

    def OnMachineJoggingUpdate(self, e):
        self.OnViewMenuUpdate(e, self.machineJoggingPanel)

    def OnComputerVision(self, e):
        self.OnViewMenu(e, self.CV2Panel)

    def OnComputerVisionUpdate(self, e):
        self.OnViewMenuUpdate(e, self.CV2Panel)

    def OnLoadDefaultLayout(self, e):
        self.LoadLayoutData('/mainApp/Layout/Default')
        self.aui_mgr.Update()

    def OnSaveDefaultLayout(self, e):
        self.SaveLayoutData('/mainApp/Layout/Default')

    def OnResetDefaultLayout(self, e):
        self.LoadLayoutData('/mainApp/Layout/Reset')
        self.SaveLayoutData('/mainApp/Layout/Default')

    def OnSettings(self, e):
        # do settings dialog
        dlg = gsatSettingsDialog(self, self.configData)

        result = dlg.ShowModal()

        if result == wx.ID_OK:
            dlg.UpdatConfigData()

            self.configData.save()

            self.InitConfig()

            self.gcText.UpdateSettings(self.configData)
            self.outputText.UpdateSettings(self.configData)
            self.machineStatusPanel.UpdateSettings(self.configData)
            self.machineJoggingPanel.UpdateSettings(self.configData)
            self.CV2Panel.UpdateSettings(self.configData)

            # re open serial port if open
            if (self.stateData.serialPortIsOpen and (self.stateData
               .serialPort != self.machinePort or self.stateData
               .serialPortBaud != self.machineBaud)):

                self.SerialClose()

        dlg.Destroy()

    # -------------------------------------------------------------------------
    # Run Menu/ToolBar Handlers
    # -------------------------------------------------------------------------
    def OnRunToolBarForceUpdate(self):
        self.OnRunUpdate()
        self.OnStepUpdate()
        self.OnStopUpdate()
        self.OnBreakToggleUpdate()
        self.OnSetPCUpdate()
        self.OnResetPCUpdate()
        self.OnGoToPCUpdate()
        self.OnMachineRefreshUpdate()
        self.OnMachineCycleStartUpdate()
        self.OnMachineFeedHoldUpdate()
        self.OnMachineQueueFlushUpdate()
        self.OnMachineResetUpdate()
        self.OnMachineClearAlarmUpdate()
        self.OnAbortUpdate()
        self.gcodeToolBar.Refresh()

    def OnRun(self, e=None):
        if self.machifProgExec is not None:
            rawText = self.gcText.GetText()
            self.stateData.gcodeFileLines = rawText.splitlines(True)

            self.machifProgExec.eventPut(
                gc.EV_CMD_RUN,
                [
                    self.stateData.gcodeFileLines,
                    self.stateData.programCounter,
                    self.stateData.breakPoints
                ]
            )

            if self.stateData.swState != gc.STATE_PAUSE and \
               self.stateData.swState != gc.STATE_BREAK:
                self.runStartTime = int(time.time())
                self.runEndTime = 0

            self.RunTimerStart()

            self.gcText.GoToPC()
            self.stateData.swState = gc.STATE_RUN
            self.UpdateUI()

    def OnRunHelper(self):
        state = False
        if self.stateData.serialPortIsOpen and \
           (self.stateData.swState == gc.STATE_IDLE or
            self.stateData.swState == gc.STATE_BREAK or
                self.stateData.swState == gc.STATE_PAUSE):

            state = True

        return state

    def OnRunUpdate(self, e=None):
        state = self.OnRunHelper()

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_RUN, state)

    def OnPause(self, e):
        self.Stop(gc.STATE_PAUSE)

    def OnPauseUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen and \
           self.stateData.swState != gc.STATE_IDLE and \
           self.stateData.swState != gc.STATE_PAUSE and \
           self.stateData.swState != gc.STATE_ABORT:

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_STOP, state)

    def OnStep(self, e):
        if self.machifProgExec is not None:
            rawText = self.gcText.GetText()
            self.stateData.gcodeFileLines = rawText.splitlines(True)

            self.machifProgExec.eventPut(
                gc.EV_CMD_STEP,
                [
                    self.stateData.gcodeFileLines,
                    self.stateData.programCounter,
                    self.stateData.breakPoints
                ]
            )
            self.stateData.swState = gc.STATE_STEP
            self.UpdateUI()

    def OnStepUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen and \
           (self.stateData.swState == gc.STATE_IDLE or
            self.stateData.swState == gc.STATE_BREAK or
                self.stateData.swState == gc.STATE_PAUSE):

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_STEP, state)

    def OnStop(self, e):
        self.Stop()

    def OnStopUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen and \
           self.stateData.swState != gc.STATE_IDLE:

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_STOP, state)

    def OnBreakToggle(self, e):
        pc = self.gcText.GetCurrentLine()
        enable = False

        if pc in self.stateData.breakPoints:
            self.stateData.breakPoints.remove(pc)
        else:
            self.stateData.breakPoints.add(pc)
            enable = True

        self.gcText.UpdateBreakPoint(pc, enable)

    def OnBreakToggleUpdate(self, e=None):
        state = False
        if (self.stateData.swState == gc.STATE_IDLE or
            self.stateData.swState == gc.STATE_BREAK or
                self.stateData.swState == gc.STATE_PAUSE):

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_BREAK_TOGGLE, state)

    def OnBreakRemoveAll(self, e):
        self.breakPoints = set()
        self.gcText.UpdateBreakPoint(-1, False)

    def OnBreakRemoveAllUpdate(self, e):
        if (self.stateData.swState == gc.STATE_IDLE or
            self.stateData.swState == gc.STATE_BREAK or
                self.stateData.swState == gc.STATE_PAUSE):

            e.Enable(True)
        else:
            e.Enable(False)

    def OnSetPC(self, e):
        self.SetPC()

    def OnSetPCUpdate(self, e=None):
        state = False
        if (self.stateData.swState == gc.STATE_IDLE or
            self.stateData.swState == gc.STATE_BREAK or
                self.stateData.swState == gc.STATE_PAUSE):

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_SET_PC, state)

    def OnResetPC(self, e):
        self.SetPC(0)

    def OnResetPCUpdate(self, e=None):
        state = False
        if (self.stateData.swState == gc.STATE_IDLE or
            self.stateData.swState == gc.STATE_BREAK or
                self.stateData.swState == gc.STATE_PAUSE):

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_RESET_PC, state)

    def OnGoToPC(self, e):
        self.gcText.GoToPC()

    def OnGoToPCUpdate(self, e=None):
        state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_GOTO_PC, state)

    def OnMachineRefresh(self, e):
        self.GetMachineStatus()

    def OnMachineRefreshUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_REFRESH, state)

    def OnMachineCycleStart(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_CYCLE_START)

            if (self.stateData.swState == gc.STATE_PAUSE):
                self.OnRun(e)

    def OnMachineCycleStartUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_CYCLE_START, state)

    def OnMachineFeedHold(self, e):
        if self.machifProgExec is not None:

            if (self.stateData.swState == gc.STATE_RUN):
                self.OnPause(e)

            self.machifProgExec.eventPut(gc.EV_CMD_FEED_HOLD)

    def OnMachineFeedHoldUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_FEED_HOLD, state)

    def OnMachineQueueFlush(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.put(gc.EV_CMD_QUEUE_FLUSH)

    def OnMachineQueueFlushUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_QUEUE_FLUSH, state)

    def OnMachineReset(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_RESET)

    def OnMachineResetUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_RESET, state)

    def OnMachineClearAlarm(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_CLEAR_ALARM)

    def OnMachineClearAlarmUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_CLEAR_ALARM, state)

    def OnAbort(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_FEED_HOLD)

        self.Stop()

        mim = mi.GetMachIfModule(self.stateData.machIfId)

        self.outputText.AppendText("*** ABORT!!! a feed-hold command (%s) has "
                                   " been sent to %s, you can\n"
                                   "    use cycle-restart command (%s) to "
                                   "continue.\n" %
                                   (mim.getFeedHoldCmd(), self.stateData
                                    .machIfName, mim.getCycleStartCmd()))

    def OnAbortUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_ABORT, state)

    # -------------------------------------------------------------------------
    # Tools Menu Handlers
    # -------------------------------------------------------------------------
    def OnToolUpdateIdle(self, e):
        state = False
        if (self.stateData.swState == gc.STATE_IDLE or
            self.stateData.swState == gc.STATE_BREAK or
                self.stateData.swState == gc.STATE_PAUSE):
            state = True

        e.Enable(state)

    def OnInch2mm(self, e):
        dlg = wx.MessageDialog(self,
                               "Your about to convert the current file from "
                               "inches to metric.\nThis is an experimental "
                               "feature, do you want to continue?",
                               "",
                               wx.OK | wx.CANCEL | wx.ICON_WARNING)

        if dlg.ShowModal() == wx.ID_OK:
            rawText = self.gcText.GetText()
            self.stateData.gcodeFileLines = rawText.splitlines(True)
            lines = self.ConvertInchAndmm(self.stateData.gcodeFileLines,
                                          in_to_mm=True,
                                          round_to=self.roundInch2mm)

            readOnly = self.gcText.GetReadOnly()
            self.gcText.SetReadOnly(False)
            self.gcText.SetText("".join(lines))
            self.gcText.SetReadOnly(readOnly)

        dlg.Destroy()

    def OnInch2mmUpdate(self, e):
        self.OnToolUpdateIdle(e)

    def Onmm2Inch(self, e):
        dlg = wx.MessageDialog(self,
                               "Your about to convert the current file from "
                               "metric to inches.\nThis is an experimental "
                               "feature, do you want to continue?",
                               "",
                               wx.OK | wx.CANCEL | wx.ICON_WARNING)

        if dlg.ShowModal() == wx.ID_OK:
            rawText = self.gcText.GetText()
            self.stateData.gcodeFileLines = rawText.splitlines(True)
            lines = self.ConvertInchAndmm(self.stateData.gcodeFileLines,
                                          in_to_mm=False,
                                          round_to=self.roundmm2Inch)

            readOnly = self.gcText.GetReadOnly()
            self.gcText.SetReadOnly(False)
            self.gcText.SetText("".join(lines))
            self.gcText.SetReadOnly(readOnly)

        dlg.Destroy()

    def Onmm2InchUpdate(self, e):
        self.OnToolUpdateIdle(e)

    def OnG812G01(self, e):
        dlg = wx.MessageDialog(self,
                               "Your about to convert the current file from "
                               "G81 to G01.\nThis is an experimental feature, "
                               "do you want to continue?",
                               "",
                               wx.OK | wx.CANCEL | wx.ICON_WARNING)

        if dlg.ShowModal() == wx.ID_OK:
            rawText = self.gcText.GetText()
            self.stateData.gcodeFileLines = rawText.splitlines(True)
            lines = self.ConvertG812G01(self.stateData.gcodeFileLines)

            readOnly = self.gcText.GetReadOnly()
            self.gcText.SetReadOnly(False)
            self.gcText.SetText("".join(lines))
            self.gcText.SetReadOnly(readOnly)

        dlg.Destroy()

    def OnG812G01Update(self, e):
        self.OnToolUpdateIdle(e)

    # -------------------------------------------------------------------------
    # Status Menu/ToolBar Handlers
    # -------------------------------------------------------------------------
    def OnStatusToolBarForceUpdate(self):
        # Link status
        if self.stateData.serialPortIsOpen:
            self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Close")
            self.statusToolBar.SetToolBitmap(
                gID_TOOLBAR_LINK_STATUS, ico.imgPlugConnect.GetBitmap())
            self.statusToolBar.SetToolDisabledBitmap(
                gID_TOOLBAR_LINK_STATUS, ico.imgPlugConnect.GetBitmap())
        else:
            self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Open")
            self.statusToolBar.SetToolBitmap(
                gID_TOOLBAR_LINK_STATUS, ico.imgPlugDisconnect.GetBitmap())
            self.statusToolBar.SetToolDisabledBitmap(
                gID_TOOLBAR_LINK_STATUS, ico.imgPlugDisconnect.GetBitmap())

        # Program status
        if self.stateData.swState == gc.STATE_IDLE:
            self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Idle")
        elif self.stateData.swState == gc.STATE_RUN:
            self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Run")
        elif self.stateData.swState == gc.STATE_PAUSE:
            self.statusToolBar.SetToolLabel(
                gID_TOOLBAR_PROGRAM_STATUS, "Pause")
        elif self.stateData.swState == gc.STATE_STEP:
            self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Step")
        elif self.stateData.swState == gc.STATE_BREAK:
            self.statusToolBar.SetToolLabel(
                gID_TOOLBAR_PROGRAM_STATUS, "Break")
        elif self.stateData.swState == gc.STATE_ABORT:
            self.statusToolBar.SetToolLabel(
                gID_TOOLBAR_PROGRAM_STATUS, "ABORT")

        self.statusToolBar.Refresh()

    def OnLinkStatus(self, e):
        if self.stateData.serialPortIsOpen:
            self.SerialClose()
        else:
            self.SerialOpen()

    # -------------------------------------------------------------------------
    # Help Menu Handlers
    # -------------------------------------------------------------------------
    def OnAbout(self, e):
        # First we create and fill the info object
        aboutDialog = wx.AboutDialogInfo()
        aboutDialog.Name = __appname__
        aboutDialog.Version = __version__
        # aboutDialog.Copyright = __copyright__
        if os.name == 'nt':
            aboutDialog.Description = wordwrap(
                __description__, 520, wx.ClientDC(self))
        else:
            aboutDialog.Description = __description__
        aboutDialog.WebSite = (__website__, "gsat home page")
        # aboutDialog.Developers = __authors__

        aboutDialog.SetLicense(__license_str__)

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(aboutDialog)

    # -------------------------------------------------------------------------
    # Other UI Handlers
    # -------------------------------------------------------------------------
    def OnCliEnter(self, e):
        cliCommand = self.machineJoggingPanel.GetCliCommand()

        if len(cliCommand) > 0:
            serialData = "%s\n" % (cliCommand)
            self.SerialWrite(serialData)

    def OnClose(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_EXIT)

        time.sleep(1)

        if self.stateData.serialPortIsOpen:
            self.SerialClose()

        self.machineJoggingPanel.SaveCli()
        self.configData.save()
        self.aui_mgr.UnInit()

        self.Destroy()
        e.Skip()

    def OnKeyPress(self, e):
        keyCode = e.GetKeyCode()

        if keyCode in self.machineJoggingPanel.numKeypadPendantKeys:
            self.machineJoggingPanel.OnKeyPress(e)
        else:
            e.Skip()

    """------------------------------------------------------------------------
   gsatMainWindow: General Functions
   ------------------------------------------------------------------------"""

    def RunTimerStart(self):
        if self.runTimer is not None:
            self.runTimer.Stop()
        else:
            t = self.runTimer = wx.Timer(self, gID_TIMER_RUN)
            self.Bind(wx.EVT_TIMER, self.OnRunTimerAction, t)

        self.runTimer.Start(1000)

    def RunTimerStop(self):
        if self.runTimer is not None:
            self.runTimer.Stop()

    def OnRunTimerAction(self, e):
        # calculate run time
        runTimeStr = "00:00:00"

        self.runEndTime = int(time.time())
        runTime = self.runEndTime - self.runStartTime
        hours, reminder = divmod(runTime, 3600)
        minutes, reminder = divmod(reminder, 60)
        seconds, mseconds = divmod(reminder, 1)
        runTimeStr = "%02d:%02d:%02d" % (hours, minutes, seconds)

        if (mseconds):
            pass

        if self.stateData.swState != gc.STATE_RUN and \
           self.stateData.swState != gc.STATE_PAUSE and \
           self.stateData.swState != gc.STATE_BREAK:
            self.RunTimerStop()

        self.machineStatusPanel.UpdateUI(
            self.stateData, dict({'rtime': runTimeStr}))

    def OnAutoRefreshTimerAction(self, e):
        if self.stateData.deviceDetected:
            # this is know to cause problems with Grbl 0.8c (maybe fixed in
            # 0.9), if too many request are sent Grbl behaves erratically,
            # this is really not require needed with TinyG(2) as its purpose
            # is to update status panel, and TinyG(2) already provides this
            # information at run time.
            self.GetMachineStatus()

    def GetSerialPortList(self):
        spList = []

        if os.name == 'nt':
            # Scan for available ports.
            for i in range(256):
                try:
                    # s = serial.Serial(i)
                    serial.Serial(i)
                    spList.append('COM'+str(i + 1))
                    # s.close()
                except serial.SerialException, e:
                    if e:
                        pass
                except OSError, e:
                    if e:
                        pass
        else:
            spList = glob.glob('/dev/ttyUSB*') + \
                glob.glob('/dev/ttyACM*') + glob.glob('/dev/cu*')

        if len(spList) < 1:
            spList = ['None']

        return spList

    def GetSerialBaudRateList(self):
        sbList = ['1200', '2400', '4800', '9600',
                  '19200', '38400', '57600', '115200']
        return sbList

    def SerialClose(self):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_EXIT)

    def SerialOpen(self):
        self.machinePort = self.stateData.serialPort
        self.machineBaud = self.stateData.serialPortBaud
        self.machineAutoRefresh = self.stateData.machineStatusAutoRefresh
        self.machineAutoRefreshPeriod = \
            self.stateData.machineStatusAutoRefreshPeriod

        self.machifProgExec = mi_progexec.MachIfExecuteThread(self)

        self.UpdateUI()

    def SerialWrite(self, serialData):
        if self.stateData.serialPortIsOpen:

            if self.machifProgExec is not None:
                self.machifProgExec.eventPut(gc.EV_CMD_SEND, serialData)
                # self.mainWndOutQueue.put(
                #     gc.SimpleEvent(gc.EV_CMD_SEND, serialData))
                # # self.mainWndOutQueue.join()

        elif self.cmdLineOptions.verbose:
            print "gsatMainWindow ERROR: attempt serial write with port "\
                "closed!!"

    def SerialWriteWaitForAck(self, serialData):
        if self.stateData.serialPortIsOpen:

            if self.machifProgExec is not None:
                self.machifProgExec.eventPut(gc.EV_CMD_SEND_W_ACK, serialData)

        elif self.cmdLineOptions.verbose:
            print "gsatMainWindow ERROR: attempt serial write with port "\
                "closed!!"

    def Stop(self, toState=gc.STATE_IDLE):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_STOP)

            self.stateData.swState = toState
            self.UpdateUI()

    def SetPC(self, pc=None):
        if pc is None:
            pc = self.gcText.GetCurrentLine()

        self.stateData.programCounter = pc
        self.gcText.UpdatePC(pc)

    def MachineStatusAutoRefresh(self, autoRefresh):
        self.stateData.machineStatusAutoRefresh = autoRefresh

        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(
                gc.EV_CMD_AUTO_STATUS, self.stateData.machineStatusAutoRefresh
            )

        if autoRefresh:
            self.GetMachineStatus()

    def GetMachineStatus(self):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(gc.EV_CMD_GET_STATUS)

        elif self.cmdLineOptions.verbose:
            print "gsatMainWindow ERROR: attempt GetMachineStatus without "\
                "progExecTread!!"

    def LoadLayoutData(self, key, update=True):
        dimesnionsData = layoutData = self.configData.get(
            "".join([key, "/Dimensions"]), "")
        if dimesnionsData:
            dimesnionsData = dimesnionsData.split("|")

            winPposition = eval(dimesnionsData[0])
            winSize = eval(dimesnionsData[1])
            winIsMaximized = eval(dimesnionsData[2])
            winIsIconized = eval(dimesnionsData[3])

            if winIsMaximized:
                self.Maximize(True)
            elif winIsIconized:
                self.Iconize(True)
            else:
                self.Maximize(False)
                self.Iconize(False)
                self.SetPosition(winPposition)
                self.SetSize(winSize)

        layoutData = self.configData.get("".join([key, "/Perspective"]), "")
        if layoutData:
            self.aui_mgr.LoadPerspective(layoutData, update)

    def SaveLayoutData(self, key):
        layoutData = self.aui_mgr.SavePerspective()

        winPposition = self.GetPosition()
        winSize = self.GetSize()
        winIsIconized = self.IsIconized()
        winIsMaximized = self.IsMaximized()

        dimensionsData = "|".join([
            str(winPposition),
            str(winSize),
            str(winIsMaximized),
            str(winIsIconized)
        ])

        self.configData.set("".join([key, "/Dimensions"]), dimensionsData)
        self.configData.set("".join([key, "/Perspective"]), layoutData)
        self.configData.save()

    def ConvertInchAndmm(self, lines, in_to_mm=True, round_to=-1):
        ret_lienes = []

        # itarate input lines
        for line in lines:

            # check for G20/G21 anc hange accordingly
            if in_to_mm:
                re_matches = re.findall(r"G20", line)
                if len(re_matches) > 0:
                    line = line.replace("G20", "G21")
                    # line = line.replace("INCHES", "MILLIMETERS")
            else:
                re_matches = re.findall(r"G21", line)
                if len(re_matches) > 0:
                    line = line.replace("G21", "G20")
                    # line = line.replace("MILLIMETERS", "INCHES")

            # check for G with units to convert code
            re_matches = re.findall(r"((X|Y|Z|R|F)([-+]?\d*\.\d*))", line)
            # re_matches = re.findall(r"((Z|R|F)([-+]?\d*\.\d*))", line)
            # import pdb;pdb.set_trace()
            if len(re_matches) > 0:
                # convert here
                # re_match item: string to (replace, literal, value)
                for match in re_matches:
                    current_val = float(match[2])
                    if in_to_mm:
                        convert_val = 25.4 * current_val
                    else:
                        convert_val = current_val / 25.4

                    if round_to > -1:
                        convert_val = round(convert_val, round_to)

                    current_str = match[0]
                    convert_str = match[1] + str(convert_val)

                    line = line.replace(current_str, convert_str)

            ret_lienes.append(line)

        return ret_lienes

    def ConvertG812G01(self, lines):
        ret_lienes = []
        state = 0
        R = 0
        Z = 0
        F = 0

        for line in lines:

            # check for empty lines
            if len(line.strip()) == 0:
                if state != 0:
                    state = 0

            # check for G code
            match = re.match(
                r"G81\s*R(\d*\.\d*)\s*Z([-+]?\d*\.\d*)\sF(\d*\.\d*)", line)
            if match is not None:
                state = 81
                R = match.group(1)
                Z = match.group(2)
                F = match.group(3)

            # in 81 state, convert G81 XY lines to G01
            if state == 81:
                match = re.match(r".*X([-+]?\d*\.\d*)\sY([-+]?\d*\.\d*)", line)
                if match is not None:
                    X = match.group(1)
                    Y = match.group(2)

                    line = \
                        "G00 X%s Y%s ( rapid move to drill zone. )\n" \
                        "G01 Z%s F%s ( plunge. )\n" \
                        "G00 Z%s ( retract )\n" % (X, Y, Z, F, R)

            ret_lienes.append(line)

        return ret_lienes

    def OnIdle(self, e):
        """ process idel time
        """
        pass
        # self.OnThreadEvent(e)

        # global idle_count
        # idle_count = idle_count+1
        # print "here on Idle %d" % idle_count

        # if not self._eventQueue.empty():
        #     e.RequestMore()

    def OnThreadEvent(self, e):
        """ program execution thread event handlers handle events
        """
        self.eventHandleCount = self.eventHandleCount + 1
        # process events from queue
        if not self._eventQueue.empty():
            # get item from queue
            te = self._eventQueue.get()

            if te.event_id == gc.EV_ABORT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_ABORT")

                self.outputText.AppendText(te.data)
                self.machifProgExec = None
                self.stateData.serialPortIsOpen = False
                self.stateData.deviceDetected = False
                self.stateData.swState = gc.STATE_IDLE
                self.UpdateUI()

            elif te.event_id == gc.EV_DATA_STATUS:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_STATUS")

                if 'stat' in te.data:
                    self.stateData.machineStatusString = te.data['stat']

                # TODO: this doens't belong here put in machif_proexec
                if 'init' in te.data:
                    # if self.cmdLineOptions.vverbose:
                    #     print "gsatMainWindow device detected via version " \
                    #         "string [%s]." % te.data['fb']
                    self.stateData.deviceDetected = True
                    self.GetMachineStatus()
                    self.RunDeviceInitScript()

                prcnt = "%.2f%%" % abs((float(
                    self.stateData.programCounter)/float(len(
                        self.stateData.gcodeFileLines)-1) * 100))
                te.data['prcnt'] = prcnt

                self.machineStatusPanel.UpdateUI(self.stateData, te.data)
                self.machineJoggingPanel.UpdateUI(self.stateData, te.data)

            elif te.event_id == gc.EV_DATA_IN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_IN")

                self.outputText.AppendText("%s" % te.data)

            elif te.event_id == gc.EV_DATA_OUT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_OUT")

                self.outputText.AppendText("> %s" % te.data)

                if te.data[-1:] != "\n":
                    self.outputText.AppendText("\n")

            elif te.event_id == gc.EV_PC_UPDATE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_PC_UPDATE [%s]." % str(te.data))

                self.SetPC(te.data)

            elif te.event_id == gc.EV_DEVICE_DETECTED:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DEVICE_DETECTED")

                self.stateData.deviceDetected = True

                # TODO: this doens't belong here put in machif_proexec
                self.GetMachineStatus()
                self.RunDeviceInitScript()

            elif te.event_id == gc.EV_RUN_END:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RUN_END")

                self.stateData.swState = gc.STATE_IDLE
                self.RunTimerStop()

                # calculate run time
                if self.runEndTime == 0:
                    self.runEndTime = int(time.time())

                runTime = self.runEndTime - self.runStartTime
                hours, reminder = divmod(runTime, 3600)
                minutes, reminder = divmod(reminder, 60)
                seconds, mseconds = divmod(reminder, 1)
                runTimeStr = "%02d:%02d:%02d" % (hours, minutes, seconds)
                runStartTimeStr = time.strftime(
                    "%a, %d %b %Y %H:%M:%S", time.localtime(self.runStartTime))
                runEndTimeStr = time.strftime(
                    "%a, %d %b %Y %H:%M:%S", time.localtime(self.runEndTime))

                if (mseconds):
                    pass

                self.machineStatusPanel.UpdateUI(
                    self.stateData, dict({'rtime': runTimeStr}))
                self.Refresh()
                self.UpdateUI()
                print self.stateData.programCounter

                # display run time dialog.
                if self.displayRuntimeDialog:
                    msgText = \
                        "Started:	%s\n"\
                        "Ended:	%s\n"\
                        "Run time:	%s" % (
                            runStartTimeStr, runEndTimeStr, runTimeStr)

                    if sys.platform in 'darwin':
                        # because dialog icons where not working correctly in
                        # Mac OS X
                        gmd.GenericMessageDialog(msgText, "G-Code Program",
                                                 gmd.GMD_DEFAULT, wx.OK |
                                                 wx.ICON_INFORMATION)
                    else:
                        wx.MessageBox(msgText, "G-Code Program",
                                      wx.OK | wx.ICON_INFORMATION)

                self.SetPC(0)
                self.machineStatusPanel.UpdateUI(
                    self.stateData, dict({'prcnt': "100.00%"}))
                self.Refresh()
                self.UpdateUI()

            elif te.event_id == gc.EV_STEP_END:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_STEP_END")

                self.stateData.swState = gc.STATE_IDLE
                self.UpdateUI()

            elif te.event_id == gc.EV_HIT_BRK_PT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HIT_BRK_PT")

                self.stateData.swState = gc.STATE_BREAK
                self.UpdateUI()

            elif te.event_id == gc.EV_HIT_MSG:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HIT_MSG [%s]" % te.data.strip())

                lastSwState = self.stateData.swState
                self.stateData.swState = gc.STATE_PAUSE
                self.UpdateUI()

                self.outputText.AppendText("** MSG: %s" % te.data.strip())

                if lastSwState == gc.STATE_RUN:
                    if sys.platform in 'darwin':
                        # because dialog icons where not working correctly in
                        # Mac OS X
                        dlg = gmd.GenericMessageDialog(
                            self, te.data.strip() +
                            "\n\nContinue program?", "G-Code Message",
                            wx.YES_NO | wx.YES_DEFAULT |
                            wx.ICON_INFORMATION)
                    else:
                        dlg = wx.MessageDialog(
                            self, te.data.strip() +
                            "\n\nContinue program?", "G-Code Message",
                            wx.YES_NO | wx.YES_DEFAULT |
                            wx.ICON_INFORMATION)
                else:
                    if sys.platform in 'darwin':
                        # because dialog icons where not working correctly in
                        # Mac OS X
                        dlg = gmd.GenericMessageDialog(
                            self, te.data.strip(),
                            "G-Code Message", wx.OK | wx.ICON_INFORMATION)
                    else:
                        dlg = wx.MessageDialog(
                            self, te.data.strip(),
                            "G-Code Message", wx.OK | wx.ICON_INFORMATION)

                result = dlg.ShowModal()
                dlg.Destroy()

                if result == wx.ID_YES:
                    self.OnRun()

            elif te.event_id == gc.EV_SER_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_OPEN")

                self.stateData.serialPortIsOpen = True
                self.UpdateUI()

            elif te.event_id == gc.EV_SER_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_CLOSE")

                self.stateData.serialPortIsOpen = False
                self.stateData.deviceDetected = False
                self.stateData.swState = gc.STATE_IDLE
                self.UpdateUI()

            elif te.event_id == gc.EV_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_EXIT")

                self.machifProgExec = None

            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.error("got UKNOWN event id[%d]" % te.event_id)

                self.stateData.swState = gc.STATE_IDLE
                self.UpdateUI()

        # # tell program exec thread that our queue is empty, ok to post more
        # # event
        # self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_OK_TO_POST, None))

        if not self._eventQueue.empty():
            pass  # timed post again

    def RunDeviceInitScript(self):
        initScriptEn = self.configData.get('/machine/InitScriptEnable')

        if initScriptEn:
            # comments example "( comment string )" or "; comment string"
            reGcodeComments = [re.compile(r'\(.*\)'), re.compile(r';.*')]

            # run init script
            initScript = str(self.configData.get(
                '/machine/InitScript')).splitlines()

            if len(initScript) > 0:
                if self.cmdLineOptions.verbose:
                    print "gsatMainWindow queuing machine init script..."

                self.outputText.AppendText("Queuing machine init script...\n")
                for initLine in initScript:

                    for reComments in reGcodeComments:
                        initLine = reComments.sub("", initLine)

                    initLine = "".join([initLine, "\n"])

                    if len(initLine.strip()) > 0:
                        self.SerialWrite(initLine)
                        # self.SerialWriteWaitForAck(initLine)
                        self.outputText.AppendText(initLine)

    def eventPut(self, id, data=None, sender=None):
        gc.EventQueueIf.eventPut(self, id, data, sender)
        self.eventInCount = self.eventInCount + 1
        wx.PostEvent(self, gc.ThreadQueueEvent(None))

    def eventForward2Machif(self, id, data=None, sender=None):
        if self.machifProgExec is not None:
            self.machifProgExec.eventPut(id, data, sender)
