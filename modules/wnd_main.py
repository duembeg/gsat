"""----------------------------------------------------------------------------
   wnd_main.py

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
import hashlib
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

try:
    import queue
except ImportError:
    import Queue as queue

import modules.config as gc
import modules.machif_config as mi
import images.icons as ico

import modules.wnd_main_config as mwc
import modules.wnd_editor as ed
import modules.wnd_machine as mc
import modules.wnd_jogging as jog
import modules.wnd_cli as cli
import modules.wnd_compvision as compv
import modules.machif_progexec as mi_progexec
import modules.remote_client as remote_client

from modules.version_info import *

'''
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
__copyright__ = 'Copyright (c) 2013-2020'
__license__ = 'GPL v2, Copyright (c) 2013-2020'
__license_str__ = __license__ + '\nhttp://www.gnu.org/licenses/gpl-2.0.txt'

# maintenance information
__maintainer__ = 'Wilhelm Duembeg'
__email__ = 'duembeg.github@gmail.com'
__website__ = 'https://github.com/duembeg/gsat'

# define version information
__requires__ = ['pySerial', 'wxPython']
__version_info__ = (1, 6, 0)
__version__ = 'v%i.%i.%i' % __version_info__
__revision__ = __version__
'''

"""----------------------------------------------------------------------------
   Globals:
----------------------------------------------------------------------------"""

# -----------------------------------------------------------------------------
# MENU & TOOL BAR IDs
# -----------------------------------------------------------------------------
gID_TOOLBAR_OPEN = wx.NewId()
gID_TOOLBAR_SETTINGS = wx.NewId()
gID_MENU_MAIN_TOOLBAR = wx.NewId()
gID_MENU_SEARCH_TOOLBAR = wx.NewId()
gID_MENU_PROGRAM_TOOLBAR = wx.NewId()
gID_MENU_MACHINE_TOOLBAR = wx.NewId()
gID_MENU_REMOTE_TOOLBAR = wx.NewId()
gID_MENU_OUTPUT_PANEL = wx.NewId()
gID_MENU_CLI_PANEL = wx.NewId()
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
gID_MENU_MACHINE_CONNECT = wx.NewId()
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
gID_MENU_REMOTE_CONNECT = wx.NewId()
gID_MENU_REMOTE_GET_GCODE = wx.NewId()
gID_MENU_REMOTE_SETTINGS = wx.NewId()


gID_TIMER_MACHINE_REFRESH = wx.NewId()
gID_TIMER_RUN = wx.NewId()

# -----------------------------------------------------------------------------
# regular expressions
# -----------------------------------------------------------------------------
gReAxis = re.compile(r'([XYZ])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

idle_count = 0

class ThreadQueueEvent(wx.PyEvent):
    """ Simple event to carry arbitrary data.
    """

    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(gc.EVT_THREAD_QUEQUE_EVENT_ID)
        self.data = data

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


class gsatMainWindow(wx.Frame, gc.EventQueueIf):
    """ Main Window Inits the UI and other panels.
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
        self.configRemoteData = None
        self.stateData.machineStatusString = "None"

        self.logger = logging.getLogger()
        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_ALL:
            self.logger.info("init logging id:0x%x" % id(self))

        self.InitConfig()

        # init some variables
        self.machifProgExec = None
        self.machifProgExecGcodeMd5 = 0
        self.remoteClient = None
        self.progexecRunTime = 0
        self.runEndWaitingForMachIfIdle = False
        self.eventInCount = 0
        self.eventHandleCount = 0

        # register for close events
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        # self.Bind(wx.EVT_IDLE, self.OnIdle)

        self.InitUI()
        self.Centre()
        self.Show()

    def InitConfig(self):
        self.displayRuntimeDialog = self.configData.get(
            '/mainApp/DisplayRunTimeDialog')
        self.saveBackupFile = self.configData.get('/mainApp/BackupFile')
        self.maxFileHistory = self.configData.get(
            '/mainApp/FileHistory/FilesMaxHistory', 10)
        self.roundInch2mm = self.configData.get('/mainApp/RoundInch2mm')
        self.roundmm2Inch = self.configData.get('/mainApp/Roundmm2Inch')
        self.stateData.machIfId = mi.GetMachIfId(
            self.configData.get('/machine/Device'))
        self.stateData.machIfName = mi.GetMachIfName(self.stateData.machIfId)

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
            self.logger.info("Init config values...")
            self.logger.info("Pyhon Version:            %s" % sys.version)
            self.logger.info("wx Version:               %s" % wx.version())
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

    def InitUI(self):
        """ Init main UI """

        # init aui manager
        self.aui_mgr = aui.AuiManager()

        # notify AUI which frame to use
        self.aui_mgr.SetManagedWindow(self)

        # experiment with status bar
        self.statusbar = self.CreateStatusBar(4)
        self.statusbar.SetStatusWidths([-1, 350, 150, 100])
        self.statusbar.SetStatusText('')

        self.machineStatusPanel = mc.gsatMachineStatusPanel(
            self, self.configData, self.stateData, self.cmdLineOptions)
        self.CV2Panel = compv.gsatCV2Panel(
            self, self.configData, self.stateData, self.cmdLineOptions)
        self.machineJoggingPanel = jog.gsatJoggingPanel(
            self, self.configData, self.stateData, self.cmdLineOptions)
        # self.machineJoggingPanel = jog.gsatJoggingObsoletePanel(
        #     self, self.configData, self.stateData, self.cmdLineOptions)
        # self.cliPanel = cli.gsatCliPanel(
        #    self, self.configData, self.stateData)

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

        # self.aui_mgr.AddPane(
        #     self.cliPanel,
        #     aui.AuiPaneInfo().Name("CLI_PANEL").Bottom().Row(1)
        #     .Caption("CLI").CloseButton(True).MaximizeButton(True)
        #     .BestSize(600, 40))

        self.aui_mgr.AddPane(
            self.outputText,
            aui.AuiPaneInfo().Name("OUTPUT_PANEL").Bottom().Row(1)
            .Caption("Output").CloseButton(True).MaximizeButton(True)
            .BestSize(600, 200))

        self.aui_mgr.AddPane(
            self.CV2Panel,
            aui.AuiPaneInfo().Name("CV2_PANEL").Right().Row(1)
            .Caption("Computer Vision").CloseButton(True).MaximizeButton(True)
            .BestSize(640, 530).Hide().Layer(1))

        self.aui_mgr.AddPane(
            self.machineStatusPanel,
            aui.AuiPaneInfo().Name("MACHINE_STATUS_PANEL").Right().Row(1)
            .Caption("Machine Status").CloseButton(True).MaximizeButton(True)
            .BestSize(360, 400).Layer(1))

        self.aui_mgr.AddPane(
            self.machineJoggingPanel,
            aui.AuiPaneInfo().Name("MACHINE_JOGGING_PANEL").Right().Row(1)
            .Caption("Machine Jogging").CloseButton(True).MaximizeButton(True)
            .BestSize(400, 600).Layer(1))

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
        self.machineStatusPanel.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)
        self.machineJoggingPanel.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)
        self.CV2Panel.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)
        self.outputText.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)
        self.gcText.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPress)

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
        viewMenu.AppendCheckItem(gID_MENU_PROGRAM_TOOLBAR, "&Program Tool Bar")
        viewMenu.AppendCheckItem(gID_MENU_MACHINE_TOOLBAR, "M&achine Tool Bar")
        viewMenu.AppendCheckItem(gID_MENU_REMOTE_TOOLBAR, "&Remote Tool Bar")
        viewMenu.AppendSeparator()
        viewMenu.AppendCheckItem(gID_MENU_OUTPUT_PANEL, "&Output")
        # viewMenu.AppendCheckItem(gID_MENU_CLI_PANEL, "&CLI")
        viewMenu.AppendCheckItem(gID_MENU_MACHINE_STATUS_PANEL, "Machine &Status")
        viewMenu.AppendCheckItem(gID_MENU_MACHINE_JOGGING_PANEL, "Machine &Jogging")
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

        # ---------------------------------------------------------------------
        # Machine menu
        machineMenu = wx.Menu()
        self.menuBar.Append(machineMenu, "&Machine")

        machineMenu.AppendCheckItem(gID_MENU_MACHINE_CONNECT, "&Connect")

        machineRefresh = wx.MenuItem(machineMenu, gID_MENU_MACHINE_REFRESH, "Machine &Refresh\tCtrl+R")
        if os.name != 'nt':
            machineRefresh.SetBitmap(ico.imgMachineRefresh.GetBitmap())
        machineMenu.AppendItem(machineRefresh)

        machineCycleStart = wx.MenuItem(machineMenu, gID_MENU_MACHINE_CYCLE_START, "Machine &Cycle Start")
        if os.name != 'nt':
            machineCycleStart.SetBitmap(ico.imgCycleStart.GetBitmap())
        machineMenu.AppendItem(machineCycleStart)

        machineFeedHold = wx.MenuItem(machineMenu, gID_MENU_MACHINE_FEED_HOLD, "Machine &Feed Hold")
        if os.name != 'nt':
            machineFeedHold.SetBitmap(ico.imgFeedHold.GetBitmap())
        machineMenu.AppendItem(machineFeedHold)

        machineQueueFlush = wx.MenuItem(machineMenu, gID_MENU_MACHINE_QUEUE_FLUSH, "Machine &Queue Flush")
        if os.name != 'nt':
            machineQueueFlush.SetBitmap(ico.imgQueueFlush.GetBitmap())
        machineMenu.AppendItem(machineQueueFlush)

        machineReset = wx.MenuItem(machineMenu, gID_MENU_MACHINE_RESET, "Machine Reset")
        if os.name != 'nt':
            machineReset.SetBitmap(ico.imgMachineReset.GetBitmap())
        machineMenu.AppendItem(machineReset)

        machineClearAlarm = wx.MenuItem(machineMenu, gID_MENU_MACHINE_CLEAR_ALARM, "Machine Clear Alarm")
        if os.name != 'nt':
            machineReset.SetBitmap(ico.imgClearAlarm.GetBitmap())
        machineMenu.AppendItem(machineClearAlarm)

        machineMenu.AppendSeparator()

        abortItem = wx.MenuItem(machineMenu, gID_MENU_ABORT, "&Abort")
        if os.name != 'nt':
            abortItem.SetBitmap(ico.imgAbort.GetBitmap())
        machineMenu.AppendItem(abortItem)

        # ---------------------------------------------------------------------
        # Remote menu
        remoteMenu = wx.Menu()
        self.menuBar.Append(remoteMenu, "R&emote")

        remoteMenu.AppendCheckItem(gID_MENU_REMOTE_CONNECT, "&Connect")
        remoteMenu.Append(gID_MENU_REMOTE_GET_GCODE, "&Get G-code")
        remoteMenu.Append(gID_MENU_REMOTE_SETTINGS, "&Settings")

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
        self.Bind(wx.EVT_MENU, self.OnMainToolBar, id=gID_MENU_MAIN_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnSearchToolBar, id=gID_MENU_SEARCH_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnProgramToolBar, id=gID_MENU_PROGRAM_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnMachineToolBar, id=gID_MENU_MACHINE_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnRemoteToolBar, id=gID_MENU_REMOTE_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnOutput, id=gID_MENU_OUTPUT_PANEL)
        # self.Bind(wx.EVT_MENU, self.OnCli, id=gID_MENU_CLI_PANEL)
        self.Bind(wx.EVT_MENU, self.OnMachineStatus, id=gID_MENU_MACHINE_STATUS_PANEL)
        self.Bind(wx.EVT_MENU, self.OnMachineJogging, id=gID_MENU_MACHINE_JOGGING_PANEL)
        self.Bind(wx.EVT_MENU, self.OnComputerVision, id=gID_MENU_CV2_PANEL)
        self.Bind(wx.EVT_MENU, self.OnLoadDefaultLayout, id=gID_MENU_LOAD_DEFAULT_LAYOUT)
        self.Bind(wx.EVT_MENU, self.OnSaveDefaultLayout, id=gID_MENU_SAVE_DEFAULT_LAYOUT)
        self.Bind(wx.EVT_MENU, self.OnResetDefaultLayout, id=gID_MENU_RESET_DEFAULT_LAYOUT)

        self.Bind(wx.EVT_UPDATE_UI, self.OnMainToolBarUpdate, id=gID_MENU_MAIN_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnSearchToolBarUpdate, id=gID_MENU_SEARCH_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnProgramToolBarUpdate, id=gID_MENU_PROGRAM_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineToolBarUpdate, id=gID_MENU_MACHINE_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnRemoteToolBarUpdate, id=gID_MENU_REMOTE_TOOLBAR)
        self.Bind(wx.EVT_UPDATE_UI, self.OnOutputUpdate, id=gID_MENU_OUTPUT_PANEL)
        # self.Bind(wx.EVT_UPDATE_UI, self.OnCliUpdate, id=gID_MENU_CLI_PANEL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineStatusUpdate, id=gID_MENU_MACHINE_STATUS_PANEL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineJoggingUpdate, id=gID_MENU_MACHINE_JOGGING_PANEL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnComputerVisionUpdate, id=gID_MENU_CV2_PANEL)

        self.Bind(wx.EVT_MENU, self.OnSettings, id=wx.ID_PREFERENCES)

        # ---------------------------------------------------------------------
        # Run menu bind
        self.Bind(wx.EVT_MENU, self.OnRun, id=gID_MENU_RUN)
        self.Bind(wx.EVT_MENU, self.OnPause, id=gID_MENU_PAUSE)
        self.Bind(wx.EVT_MENU, self.OnStep, id=gID_MENU_STEP)
        self.Bind(wx.EVT_MENU, self.OnStop, id=gID_MENU_STOP)
        self.Bind(wx.EVT_MENU, self.OnBreakToggle, id=gID_MENU_BREAK_TOGGLE)
        self.Bind(wx.EVT_MENU, self.OnBreakRemoveAll, id=gID_MENU_BREAK_REMOVE_ALL)
        self.Bind(wx.EVT_MENU, self.OnSetPC, id=gID_MENU_SET_PC)
        self.Bind(wx.EVT_MENU, self.OnResetPC, id=gID_MENU_RESET_PC)
        self.Bind(wx.EVT_MENU, self.OnGoToPC, id=gID_MENU_GOTO_PC)

        self.Bind(wx.EVT_BUTTON, self.OnRun, id=gID_MENU_RUN)
        self.Bind(wx.EVT_BUTTON, self.OnPause, id=gID_MENU_PAUSE)
        self.Bind(wx.EVT_BUTTON, self.OnStep, id=gID_MENU_STEP)
        self.Bind(wx.EVT_BUTTON, self.OnStop, id=gID_MENU_STOP)
        self.Bind(wx.EVT_BUTTON, self.OnBreakToggle, id=gID_MENU_BREAK_TOGGLE)
        self.Bind(wx.EVT_BUTTON, self.OnSetPC, id=gID_MENU_SET_PC)
        self.Bind(wx.EVT_BUTTON, self.OnResetPC, id=gID_MENU_RESET_PC)
        self.Bind(wx.EVT_BUTTON, self.OnGoToPC, id=gID_MENU_GOTO_PC)

        self.Bind(wx.EVT_UPDATE_UI, self.OnRunUpdate, id=gID_MENU_RUN)
        self.Bind(wx.EVT_UPDATE_UI, self.OnPauseUpdate, id=gID_MENU_PAUSE)
        self.Bind(wx.EVT_UPDATE_UI, self.OnStepUpdate, id=gID_MENU_STEP)
        self.Bind(wx.EVT_UPDATE_UI, self.OnStopUpdate, id=gID_MENU_STOP)
        self.Bind(wx.EVT_UPDATE_UI, self.OnBreakToggleUpdate, id=gID_MENU_BREAK_TOGGLE)
        self.Bind(wx.EVT_UPDATE_UI, self.OnBreakRemoveAllUpdate, id=gID_MENU_BREAK_REMOVE_ALL)
        self.Bind(wx.EVT_UPDATE_UI, self.OnSetPCUpdate, id=gID_MENU_SET_PC)
        self.Bind(wx.EVT_UPDATE_UI, self.OnResetPCUpdate, id=gID_MENU_RESET_PC)
        self.Bind(wx.EVT_UPDATE_UI, self.OnGoToPCUpdate, id=gID_MENU_GOTO_PC)

        # ---------------------------------------------------------------------
        # Machine menu bind
        self.Bind(wx.EVT_MENU, self.OnMachineConnect, id=gID_MENU_MACHINE_CONNECT)
        self.Bind(wx.EVT_MENU, self.OnMachineRefresh, id=gID_MENU_MACHINE_REFRESH)
        self.Bind(wx.EVT_MENU, self.OnMachineCycleStart, id=gID_MENU_MACHINE_CYCLE_START)
        self.Bind(wx.EVT_MENU, self.OnMachineFeedHold, id=gID_MENU_MACHINE_FEED_HOLD)
        self.Bind(wx.EVT_MENU, self.OnMachineQueueFlush, id=gID_MENU_MACHINE_QUEUE_FLUSH)
        self.Bind(wx.EVT_MENU, self.OnMachineReset, id=gID_MENU_MACHINE_RESET)
        self.Bind(wx.EVT_MENU, self.OnMachineClearAlarm, id=gID_MENU_MACHINE_CLEAR_ALARM)
        self.Bind(wx.EVT_MENU, self.OnAbort, id=gID_MENU_ABORT)

        self.Bind(wx.EVT_BUTTON, self.OnMachineConnect, id=gID_MENU_MACHINE_CONNECT)
        self.Bind(wx.EVT_BUTTON, self.OnMachineRefresh, id=gID_MENU_MACHINE_REFRESH)
        self.Bind(wx.EVT_BUTTON, self.OnMachineCycleStart, id=gID_MENU_MACHINE_CYCLE_START)
        self.Bind(wx.EVT_BUTTON, self.OnMachineFeedHold, id=gID_MENU_MACHINE_FEED_HOLD)
        self.Bind(wx.EVT_BUTTON, self.OnMachineQueueFlush, id=gID_MENU_MACHINE_QUEUE_FLUSH)
        self.Bind(wx.EVT_BUTTON, self.OnMachineReset, id=gID_MENU_MACHINE_RESET)
        self.Bind(wx.EVT_BUTTON, self.OnMachineClearAlarm, id=gID_MENU_MACHINE_CLEAR_ALARM)
        self.Bind(wx.EVT_BUTTON, self.OnAbort, id=gID_MENU_ABORT)

        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineConnectUpdate, id=gID_MENU_MACHINE_CONNECT)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineRefreshUpdate, id=gID_MENU_MACHINE_REFRESH)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineCycleStartUpdate, id=gID_MENU_MACHINE_CYCLE_START)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineFeedHoldUpdate, id=gID_MENU_MACHINE_FEED_HOLD)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineQueueFlushUpdate, id=gID_MENU_MACHINE_QUEUE_FLUSH)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineResetUpdate, id=gID_MENU_MACHINE_RESET)
        self.Bind(wx.EVT_UPDATE_UI, self.OnMachineClearAlarmUpdate, id=gID_MENU_MACHINE_CLEAR_ALARM)
        self.Bind(wx.EVT_UPDATE_UI, self.OnAbortUpdate, id=gID_MENU_ABORT)

        # ---------------------------------------------------------------------
        # remote menu bind
        self.Bind(wx.EVT_MENU, self.OnRemoteConnect, id=gID_MENU_REMOTE_CONNECT)
        self.Bind(wx.EVT_MENU, self.OnRemoteGetGcode, id=gID_MENU_REMOTE_GET_GCODE)
        self.Bind(wx.EVT_MENU, self.OnRemoteSettings, id=gID_MENU_REMOTE_SETTINGS)

        self.Bind(wx.EVT_UPDATE_UI, self.OnRemoteConnectUpdate, id=gID_MENU_REMOTE_CONNECT)
        self.Bind(wx.EVT_UPDATE_UI, self.OnRemoteGetGcodeUpdate, id=gID_MENU_REMOTE_GET_GCODE)
        self.Bind(wx.EVT_UPDATE_UI, self.OnRemoteSettingsUpdate, id=gID_MENU_REMOTE_SETTINGS)

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
        self.Bind(wx.EVT_MENU, self.OnSettings, id=gID_TOOLBAR_SETTINGS)

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
        self.appToolBar.SetToolDisabledBitmap(wx.ID_SAVE, ico.imgSaveDisabled.GetBitmap())

        self.appToolBar.AddSimpleTool(wx.ID_SAVEAS, "Save As", ico.imgSave.GetBitmap(), "Save As")
        self.appToolBar.SetToolDisabledBitmap(wx.ID_SAVEAS, ico.imgSaveDisabled.GetBitmap())

        self.appToolBar.AddSimpleTool(gID_TOOLBAR_SETTINGS, "Settings", ico.imgSettings.GetBitmap(), "Settings")
        self.appToolBar.SetToolDisabledBitmap(gID_TOOLBAR_SETTINGS, ico.imgSettings.GetBitmap())


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

        self.gcodeToolBar.Realize()

        self.aui_mgr.AddPane(self.gcodeToolBar,
                             aui.AuiPaneInfo().Name("GCODE_TOOLBAR")
                             .Caption("Program Tool Bar").ToolbarPane()
                             .Top().Gripper())

        # ---------------------------------------------------------------------
        # Machine Tool Bar
        self.machineToolBar = aui.AuiToolBar(
            self, -1, wx.DefaultPosition, wx.DefaultSize,
            agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            # aui.AUI_TB_TEXT |
            # aui.AUI_TB_HORZ_TEXT |
            # aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE)

        self.machineToolBar.SetToolBitmapSize(iconSize)

        self.machineToolBar.AddSimpleTool(
            gID_MENU_MACHINE_CONNECT, "Machine Connect", ico.imgPlugDisconnect.GetBitmap(), "Machine Connect")
        self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_CONNECT, ico.imgPlugDisconnect.GetBitmap())

        self.machineToolBar.AddSimpleTool(
            gID_MENU_MACHINE_REFRESH, "Machine Refresh", ico.imgMachineRefresh.GetBitmap(), "Machine Refresh")
        self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_REFRESH, ico.imgMachineRefreshDisabled.GetBitmap())

        self.machineToolBar.AddSimpleTool(
            gID_MENU_MACHINE_CYCLE_START, "Cycle Start", ico.imgCycleStart.GetBitmap(), "Machine Cycle Start")
        self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_CYCLE_START, ico.imgCycleStartDisabled.GetBitmap())

        self.machineToolBar.AddSimpleTool(
            gID_MENU_MACHINE_FEED_HOLD, "Feed Hold", ico.imgFeedHold.GetBitmap(), "Machine Feed Hold")
        self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_FEED_HOLD, ico.imgFeedHoldDisabled.GetBitmap())

        self.machineToolBar.AddSimpleTool(
            gID_MENU_MACHINE_QUEUE_FLUSH, "Queue Flush", ico.imgQueueFlush.GetBitmap(), "Machine Queue Flush")
        self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_QUEUE_FLUSH, ico.imgQueueFlushDisabled.GetBitmap())

        self.machineToolBar.AddSimpleTool(
            gID_MENU_MACHINE_RESET, "Reset", ico.imgMachineReset.GetBitmap(), "Machine Reset")
        self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_RESET, ico.imgMachineResetDisabled.GetBitmap())

        self.machineToolBar.AddSimpleTool(
            gID_MENU_MACHINE_CLEAR_ALARM, "Clear Alarm",ico.imgClearAlarm.GetBitmap(), "Machine Clear Alarm")
        self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_CLEAR_ALARM, ico.imgClearAlarmDisabled.GetBitmap())

        self.machineToolBar.AddSeparator()

        self.machineToolBar.AddSimpleTool(
            gID_MENU_ABORT, "Abort", ico.imgAbort.GetBitmap(), "Abort")
        self.machineToolBar.SetToolDisabledBitmap(gID_MENU_ABORT, ico.imgAbortDisabled.GetBitmap())

        self.machineToolBar.Realize()

        self.aui_mgr.AddPane(self.machineToolBar,
                             aui.AuiPaneInfo().Name("MACHINE_TOOLBAR")
                             .Caption("Machine Tool Bar").ToolbarPane()
                             .Top().Gripper())

        # ---------------------------------------------------------------------
        # Remote Tool Bar
        self.remoteToolBar = aui.AuiToolBar(
            self, -1, wx.DefaultPosition, wx.DefaultSize,
            agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            # aui.AUI_TB_TEXT |
            #aui.AUI_TB_HORZ_TEXT |
            # aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE)

        self.remoteToolBar.SetToolBitmapSize(iconSize)

        self.remoteToolBar.AddSimpleTool(
            gID_MENU_REMOTE_CONNECT, "Remote", ico.imgRemote.GetBitmap(), "Connect to remote server")
        self.remoteToolBar.SetToolDisabledBitmap(gID_MENU_REMOTE_CONNECT, ico.imgRemote.GetBitmap())

        self.remoteToolBar.AddSimpleTool(
            gID_MENU_REMOTE_GET_GCODE, "Remote Get G-code", ico.imgRemoteGcode.GetBitmap(), "Get G-code from remote server")
        self.remoteToolBar.SetToolDisabledBitmap(gID_MENU_REMOTE_GET_GCODE, ico.imgRemoteGcodeDisabled.GetBitmap())

        self.remoteToolBar.AddSimpleTool(
            gID_MENU_REMOTE_SETTINGS, "Remore Settings", ico.imgRemoteSettings.GetBitmap(), "Settings on remote server")
        self.remoteToolBar.SetToolDisabledBitmap(gID_MENU_REMOTE_SETTINGS, ico.imgRemoteSettingsDisabled.GetBitmap())

        self.remoteToolBar.Realize()

        self.aui_mgr.AddPane(
            self.remoteToolBar, aui.AuiPaneInfo().Name("REMOTE_TOOLBAR")
            .Caption("Remote Tool Bar").ToolbarPane().Top().Gripper())

        # finish up
        self.appToolBar.Refresh()
        self.gcodeToolBar.Refresh()
        self.machineToolBar.Refresh()

    def UpdateUI(self):
        self.gcText.UpdateUI(self.stateData)
        # self.cliPanel.UpdateUI(self.stateData)
        self.machineStatusPanel.UpdateUI(self.stateData)
        self.machineJoggingPanel.UpdateUI(self.stateData)
        self.CV2Panel.UpdateUI(self.stateData)

        # Force update tool bar items
        self.OnAppToolBarForceUpdate()
        self.OnStatusToolBarForceUpdate()
        self.OnRunToolBarForceUpdate()

        # Program status
        if self.stateData.swState == gc.STATE_IDLE:
            self.statusbar.SetStatusText("SWST: Idle", 3)
        elif self.stateData.swState == gc.STATE_RUN:
            self.statusbar.SetStatusText("SWST: Run", 3)
        elif self.stateData.swState == gc.STATE_PAUSE:
            self.statusbar.SetStatusText("SWST: Pause", 3)
        elif self.stateData.swState == gc.STATE_STEP:
            self.statusbar.SetStatusText("SWST: Step", 3)
        elif self.stateData.swState == gc.STATE_BREAK:
            self.statusbar.SetStatusText("SWST: Break", 3)
        elif self.stateData.swState == gc.STATE_ABORT:
            self.statusbar.SetStatusText("SWST: ABORT", 3)

        # machif status
        if self.remoteClient:
            self.statusbar.SetStatusText("Remote: {}".format(self.remoteClient.get_hostname()), 1)
        else:
            self.statusbar.SetStatusText("", 1)

        if self.stateData.serialPortIsOpen:
            self.statusbar.SetStatusText("Device: Connected", 2)
        else:
            self.statusbar.SetStatusText("Device: Disconnected", 2)

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
            self.SetTitle("{} - {}".format(os.path.basename(self.stateData.gcodeFileName), __appname__))

            self.gcText.DeleteAllBreakPoints()
            self.SetPC(0)
            self.gcText.GoToPC()
            self.UpdateUI()

            self.statusbar.SetStatusText(os.path.basename(self.stateData.gcodeFileName))
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

            self.statusbar.SetStatusText(os.path.basename(self.stateData.gcodeFileName))

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

    def OnProgramToolBar(self, e):
        self.OnViewMenuToolBar(e, self.gcodeToolBar)

    def OnProgramToolBarUpdate(self, e):
        self.OnViewMenuUpdate(e, self.gcodeToolBar)

    def OnMachineToolBar(self, e):
        self.OnViewMenuToolBar(e, self.machineToolBar)

    def OnMachineToolBarUpdate(self, e):
        self.OnViewMenuUpdate(e, self.machineToolBar)

    def OnRemoteToolBar(self, e):
        self.OnViewMenuToolBar(e, self.remoteToolBar)

    def OnRemoteToolBarUpdate(self, e):
        self.OnViewMenuUpdate(e, self.remoteToolBar)

    def OnOutput(self, e):
        self.OnViewMenu(e, self.outputText)

    def OnOutputUpdate(self, e):
        self.OnViewMenuUpdate(e, self.outputText)

    # def OnCli(self, e):
    #     self.OnViewMenu(e, self.cliPanel)

    # def OnCliUpdate(self, e):
    #     self.OnViewMenuUpdate(e, self.cliPanel)

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
        # save port settings
        machine_port = self.configData.get('/machine/Port')
        machine_baud = self.configData.get('/machine/Baud')

        # do settings dialog
        dlg = mwc.gsatSettingsDialog(self, self.configData)

        result = dlg.ShowModal()

        if result == wx.ID_OK:
            dlg.UpdateConfigData()

            self.configData.save()

            self.InitConfig()

            self.gcText.UpdateSettings(self.configData)
            self.outputText.UpdateSettings(self.configData)
            # self.cliPanel(self.configData)
            self.machineStatusPanel.UpdateSettings(self.configData)
            self.machineJoggingPanel.UpdateSettings(self.configData)
            self.CV2Panel.UpdateSettings(self.configData)

            if self.machifProgExec is not None and self.remoteClient is None:
                self.machifProgExec.add_event(gc.EV_CMD_UPDATE_CONFIG)

            # re open serial port if open
            if self.stateData.serialPortIsOpen and (
                machine_port != self.configData.get('/machine/Port') or
                machine_baud != self.configData.get('/machine/Baud')):
                self.SerialClose()

        # refresh UIs after settings updates
        self.UpdateUI()

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
        # self.OnStatusToolBarForceUpdate()
        self.OnMachineConnectUpdate()
        self.OnMachineRefreshUpdate()
        self.OnMachineCycleStartUpdate()
        self.OnMachineFeedHoldUpdate()
        self.OnMachineQueueFlushUpdate()
        self.OnMachineResetUpdate()
        self.OnMachineClearAlarmUpdate()
        self.OnAbortUpdate()
        self.gcodeToolBar.Refresh()
        self.machineToolBar.Refresh()

    def OnRun(self, e=None):
        if self.machifProgExec is not None:
            rawText = self.gcText.GetText()
            self.stateData.gcodeFileLines = rawText.splitlines(True)

            runDict = dict()

            if len(self.stateData.gcodeFileLines):
                if len(self.stateData.gcodeFileName):
                    runDict['gcodeFileName'] = self.stateData.gcodeFileName

                h = hashlib.md5(str(self.stateData.gcodeFileLines)).hexdigest()
                if self.machifProgExecGcodeMd5 != h:
                    runDict['gcodeLines'] = self.stateData.gcodeFileLines

                runDict['gcodePC'] = self.stateData.programCounter
                runDict['breakPoints'] = self.gcText.GetBreakPoints()

            self.machifProgExec.add_event(gc.EV_CMD_RUN, runDict, self)

            self.gcText.GoToPC()

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
        #self.Stop(gc.STATE_PAUSE)
        self.machifProgExec.add_event(gc.EV_CMD_PAUSE, None, self)
        # self.stateData.swState = gc.STATE_PAUSE
        # self.UpdateUI()

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

            runDict = dict()

            if len(self.stateData.gcodeFileLines):
                if len(self.stateData.gcodeFileName):
                    runDict['gcodeFileName'] = self.stateData.gcodeFileName

                h = hashlib.md5(str(self.stateData.gcodeFileLines)).hexdigest()
                if self.machifProgExecGcodeMd5 != h:
                    runDict['gcodeLines'] = self.stateData.gcodeFileLines

                runDict['gcodePC'] = self.stateData.programCounter
                runDict['breakPoints'] = self.gcText.GetBreakPoints()

            self.machifProgExec.add_event(gc.EV_CMD_STEP, runDict, self)

            # self.stateData.swState = gc.STATE_STEP
            # self.UpdateUI()

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
        # if self.stateData.serialPortIsOpen:

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_STOP, state)

    def OnBreakToggle(self, e):
        pc = self.gcText.GetCurrentLine()
        enable = False

        break_points = self.gcText.GetBreakPoints()

        if pc in break_points:
            self.gcText.UpdateBreakPoint(pc, False)
        else:
            self.gcText.UpdateBreakPoint(pc, True)

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
        self.gcText.DeleteAllBreakPoints()

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

    # -------------------------------------------------------------------------
    # Machine Menu Handlers
    # -------------------------------------------------------------------------
    def OnMachineConnect(self, e):
        if self.stateData.serialPortIsOpen:
            self.SerialClose()
        else:
            self.SerialOpen()

    def OnMachineConnectUpdate(self, e=None):
        if e is not None:
            if self.machifProgExec is None:
                e.Check(False)
            else:
                e.Check(True)

        # self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_CONNECT, state)

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
            self.machifProgExec.add_event(gc.EV_CMD_CYCLE_START)

            # if (self.stateData.swState == gc.STATE_PAUSE):
            #     self.OnRun(e)

    def OnMachineCycleStartUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_CYCLE_START, state)

    def OnMachineFeedHold(self, e):
        if self.machifProgExec is not None:

            # if (self.stateData.swState == gc.STATE_RUN):
            #     self.OnPause(e)

            self.machifProgExec.add_event(gc.EV_CMD_FEED_HOLD)

    def OnMachineFeedHoldUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_FEED_HOLD, state)

    def OnMachineQueueFlush(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.add_event(gc.EV_CMD_QUEUE_FLUSH)

    def OnMachineQueueFlushUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:
            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_QUEUE_FLUSH, state)

    def OnMachineReset(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.add_event(gc.EV_CMD_RESET)

    def OnMachineResetUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_RESET, state)

    def OnMachineClearAlarm(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.add_event(gc.EV_CMD_CLEAR_ALARM)

    def OnMachineClearAlarmUpdate(self, e=None):
        state = False
        if self.stateData.serialPortIsOpen:

            state = True

        if e is not None:
            e.Enable(state)

        self.gcodeToolBar.EnableTool(gID_MENU_MACHINE_CLEAR_ALARM, state)

    def OnAbort(self, e):
        if self.machifProgExec is not None:
            self.machifProgExec.add_event(gc.EV_CMD_FEED_HOLD)

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
    # Remote Menu Handlers
    # -------------------------------------------------------------------------
    def OnRemoteConnect(self, e):
        if self.remoteClient is None:
            self.RemoteOpen()
        else:
            self.RemoteClose()

    def OnRemoteConnectUpdate(self, e):
        if self.remoteClient is None:
            e.Check(False)
        else:
            e.Check(True)

    def OnRemoteGetGcode(self, e):
        if self.remoteClient is not None:
            self.remoteClient.add_event(gc.EV_CMD_GET_GCODE)

    def OnRemoteGetGcodeUpdate(self, e):
        if self.remoteClient is None:
            e.Enable(False)
        else:
            e.Enable(True)

    def OnRemoteSettings(self, e):
        if self.remoteClient is not None:
            # save port settings
            machine_port = self.configRemoteData.get('/machine/Port')
            machine_baud = self.configRemoteData.get('/machine/Baud')

            # do settings dialog
            dlg = mwc.gsatSettingsDialog(self, self.configData, self.configRemoteData, title="Remote Settings")

            result = dlg.ShowModal()

            if result == wx.ID_OK:
                dlg.UpdateConfigData()

                self.remoteClient.add_event(gc.EV_CMD_UPDATE_CONFIG, self.configRemoteData)

            # refresh UIs after settings updates
            self.UpdateUI()

            dlg.Destroy()

    def OnRemoteSettingsUpdate(self, e):
        if self.remoteClient is None:
            e.Enable(False)
        else:
            e.Enable(True)

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
                               "inches to millimeter.\nThis is an experimental "
                               "feature, do you want to continue?",
                               "inch to millimeter",
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
                               "millimeter to inches.\nThis is an experimental "
                               "feature, do you want to continue?",
                               "millimeter to inch",
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
            self.machineToolBar.SetToolBitmap(gID_MENU_MACHINE_CONNECT, ico.imgPlugConnect.GetBitmap())
            self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_CONNECT, ico.imgPlugConnect.GetBitmap())
        else:
            self.machineToolBar.SetToolBitmap(gID_MENU_MACHINE_CONNECT, ico.imgPlugDisconnect.GetBitmap())
            self.machineToolBar.SetToolDisabledBitmap(gID_MENU_MACHINE_CONNECT, ico.imgPlugDisconnect.GetBitmap())


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
    def OnClose(self, e):

        self.machineJoggingPanel.SaveCli()

        self.configData.save()

        if self.remoteClient is not None:
            self.RemoteClose()
        elif self.machifProgExec is not None:
            self.SerialClose()

        time.sleep(1)

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
                except serial.SerialException as e:
                    if e:
                        pass
                except OSError as e:
                    if e:
                        pass
        else:
            spList = glob.glob('/dev/ttyUSB*') + \
                glob.glob('/dev/ttyACM*') + glob.glob('/dev/cu*')

        if len(spList) < 1:
            spList = ['None']

        return spList

    def GetSerialBaudRateList(self):
        sbList = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200', '230400']
        return sbList

    def SerialClose(self):
        if self.machifProgExec is not None:
            if self.remoteClient is None:
                self.machifProgExec.add_event(gc.EV_CMD_EXIT)
            else:
                self.machifProgExec.add_event(gc.EV_CMD_CLOSE)

            self.stateData.serialPortIsOpen = False
            self.UpdateUI()

    def SerialOpen(self):
        if self.remoteClient is None:
            self.machifProgExec = mi_progexec.MachIfExecuteThread(self)
        else:
            self.machifProgExec.add_event(gc.EV_CMD_OPEN)

        self.UpdateUI()

    def SerialWrite(self, serialData):
        if self.stateData.serialPortIsOpen:

            if self.machifProgExec is not None:
                self.machifProgExec.add_event(gc.EV_CMD_SEND, serialData)
                # self.mainWndOutQueue.put(
                #     gc.SimpleEvent(gc.EV_CMD_SEND, serialData))
                # # self.mainWndOutQueue.join()

        elif self.cmdLineOptions.verbose:
            print ("gsatMainWindow ERROR: attempt serial write with port closed!!")

    def SerialWriteWaitForAck(self, serialData):
        if self.stateData.serialPortIsOpen:

            if self.machifProgExec is not None:
                self.machifProgExec.add_event(gc.EV_CMD_SEND_W_ACK, serialData)

        elif self.cmdLineOptions.verbose:
            print ("gsatMainWindow ERROR: attempt serial write with port closed!!")

    def RemoteOpen(self):
        if self.remoteClient is None:
            if self.machifProgExec is not None:
                self.SerialClose()

            self.remoteClient = remote_client.RemoteClientThread(self)
            self.machifProgExec = self.remoteClient

    def RemoteClose(self):
        if self.remoteClient is not None:
            self.remoteClient.add_event(gc.EV_CMD_EXIT)

    def Stop(self, toState=gc.STATE_IDLE):
        if self.machifProgExec is not None:
            self.machifProgExec.add_event(gc.EV_CMD_STOP)

            # self.stateData.swState = toState
            # self.UpdateUI()

    def SetPC(self, pc=None):
        if pc is None:
            pc = self.gcText.GetCurrentLine()

        self.stateData.programCounter = pc
        self.gcText.UpdatePC(pc)

    def GetMachineStatus(self):
        if self.machifProgExec is not None:
            self.machifProgExec.add_event(gc.EV_CMD_GET_STATUS)

        elif self.cmdLineOptions.verbose:
            print ("gsatMainWindow ERROR: attempt GetMachineStatus without progExecTread!!")

    def LoadLayoutData(self, key, update=True):
        dimensionsData = layoutData = self.configData.get(
            "".join([key, "/Dimensions"]), "")
        if dimensionsData:
            dimensionsData = dimensionsData.split("|")

            winPosition = eval(dimensionsData[0])
            winSize = eval(dimensionsData[1])
            winIsMaximized = eval(dimensionsData[2])
            winIsIconized = eval(dimensionsData[3])

            if winIsMaximized:
                self.Maximize(True)
            elif winIsIconized:
                self.Iconize(True)
            else:
                self.Maximize(False)
                self.Iconize(False)
                self.SetPosition(winPosition)
                self.SetSize(winSize)

        layoutData = self.configData.get("".join([key, "/Perspective"]), "")
        if layoutData:
            self.aui_mgr.LoadPerspective(layoutData, update)

    def SaveLayoutData(self, key):
        layoutData = self.aui_mgr.SavePerspective()

        winPosition = self.GetPosition()
        winSize = self.GetSize()
        winIsIconized = self.IsIconized()
        winIsMaximized = self.IsMaximized()

        dimensionsData = "|".join([
            str(winPosition),
            str(winSize),
            str(winIsMaximized),
            str(winIsIconized)
        ])

        self.configData.set("".join([key, "/Dimensions"]), dimensionsData)
        self.configData.set("".join([key, "/Perspective"]), layoutData)

        self.configData.save()

    def ConvertInchAndmm(self, lines, in_to_mm=True, round_to=-1):
        ret_lienes = []

        # iterate input lines
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
        try:
            te = self._eventQueue.get_nowait()
        except queue.Empty:
            pass

        else:
            if te.event_id == gc.EV_DATA_STATUS:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_STATUS")

                if 'sr' in te.data:
                    sr = te.data['sr']

                    if 'rtime' in sr:
                        self.progexecRunTime = sr['rtime']

                    if 'stat' in sr:
                        self.stateData.machineStatusString = sr['stat']

                    self.machineStatusPanel.UpdateUI(self.stateData, sr)
                    self.machineJoggingPanel.UpdateUI(self.stateData, sr)

                if 'rx_data' in te.data:
                    self.outputText.AppendText("{}".format(te.data['rx_data']))

                if 'pc' in te.data:
                    if self.stateData.programCounter != te.data['pc']:
                        self.SetPC(te.data['pc'])

                if 'swstate' in te.data:
                    if self.stateData.swState != int(te.data['swstate']):
                        self.stateData.swState = int(te.data['swstate'])
                        self.UpdateUI()

                if 'fv' in te.data or 'fb' in te.data:
                    self.machineStatusPanel.UpdateUI(self.stateData, te.data)

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
                    self.logger.info("EV_PC_UPDATE [%s]" % str(te.data))

                self.SetPC(te.data)

            elif te.event_id == gc.EV_RUN_END:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RUN_END")

                # self.stateData.swState = gc.STATE_IDLE
                self.runEndWaitingForMachIfIdle = True
                self.UpdateUI()

            elif te.event_id == gc.EV_STEP_END:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_STEP_END")

                # self.stateData.swState = gc.STATE_IDLE
                self.UpdateUI()

            elif te.event_id == gc.EV_BRK_PT_STOP:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HIT_BRK_PT")

                # self.stateData.swState = gc.STATE_BREAK
                # self.UpdateUI()

            elif te.event_id == gc.EV_GCODE_MSG:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HIT_MSG [%s]" % te.data.strip())

                lastSwState = self.stateData.swState
                # self.stateData.swState = gc.STATE_PAUSE
                # self.UpdateUI()

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
                    self.logger.info("EV_SER_PORT_OPEN from 0x{:x} {}".format(id(te.sender), te.sender))

                self.stateData.serialPortIsOpen = True

                if self.remoteClient is not None:
                    self.remoteClient.add_event(gc.EV_CMD_GET_STATUS)

                self.UpdateUI()

            elif te.event_id == gc.EV_SER_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_CLOSE from 0x{:x} {}".format(id(te.sender), te.sender))

                self.stateData.serialPortIsOpen = False
                self.stateData.deviceDetected = False
                # self.stateData.swState = gc.STATE_IDLE
                self.UpdateUI()

            elif te.event_id == gc.EV_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_EXIT from 0x{:x} {}".format(id(te.sender), te.sender))

                if id(te.sender) == id(self.remoteClient):
                    self.remoteClient = None
                    self.configRemoteData = None

                    self.machineStatusPanel.UpdateSettings(self.configData, self.configRemoteData)

                if id(te.sender) == id(self.machifProgExec):
                    self.machifProgExec = None

                self.UpdateUI()

            elif te.event_id == gc.EV_DEVICE_DETECTED:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DEVICE_DETECTED")

                self.stateData.deviceDetected = True

                # TODO: this doesn't belong here put in machif_proexec
                self.GetMachineStatus()

                if self.remoteClient is None:
                    self.RunDeviceInitScript()

            elif te.event_id == gc.EV_ABORT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_ABORT from 0x{:x} {}".format(id(te.sender), te.sender))

                self.outputText.AppendText(te.data)

                if te.sender is self.remoteClient:
                    self.RemoteClose()
                    self.remoteClient = None
                    self.configRemoteData = None
                    self.stateData.serialPortIsOpen = False
                elif te.sender is self.machifProgExec:
                    self.SerialClose()
                    self.machifProgExec = None
                    self.stateData.serialPortIsOpen = False

                self.stateData.deviceDetected = False
                self.stateData.swState = gc.STATE_IDLE

                self.machineStatusPanel.UpdateSettings(self.configData, self.configRemoteData)
                self.UpdateUI()

            elif te.event_id == gc.EV_RMT_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_OPEN from 0x{:x} {}".format(id(te.sender), te.sender))

                self.outputText.AppendText(te.data)

                if self.remoteClient is not None:
                    self.remoteClient.add_event(gc.EV_CMD_GET_CONFIG)

                if self.machifProgExec is not None:
                    self.machifProgExec.add_event(gc.EV_CMD_GET_SYSTEM_INFO)
                    self.machifProgExec.add_event(gc.EV_CMD_GET_SW_STATE)

                    if self.configData.get('/remote/AutoGcodeRequest', False):
                        self.machifProgExec.add_event(gc.EV_CMD_GET_GCODE)

                self.UpdateUI()

            elif te.event_id == gc.EV_RMT_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_CLOSE from 0x{:x} {}".format(id(te.sender), te.sender))

                self.outputText.AppendText(te.data)
                self.stateData.serialPortIsOpen = False
                self.stateData.deviceDetected = False
                self.stateData.swState = gc.STATE_IDLE
                self.configRemoteData = None

                self.machineStatusPanel.UpdateSettings(self.configData, self.configRemoteData)
                self.UpdateUI()

            elif  te.event_id == gc.EV_RMT_CONFIG_DATA:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_CONFIG_DATA from 0x{:x} {}".format(id(te.sender), te.sender))

                self.configRemoteData = te.data
                self.machineStatusPanel.UpdateSettings(self.configData, self.configRemoteData)

            elif te.event_id == gc.EV_RMT_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_HELLO from 0x{:x} {}".format(id(te.sender), te.sender))

                self.outputText.AppendText(te.data)

            elif te.event_id == gc.EV_RMT_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_GOOD_BYE from 0x{:x} {}".format(id(te.sender), te.sender))

                self.outputText.AppendText(te.data)

            elif te.event_id == gc.EV_SW_STATE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SW_STATE")

                self.stateData.swState = te.data
                self.UpdateUI()

            elif te.event_id == gc.EV_GCODE_MD5:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GCODE_MD5")

                self.machifProgExecGcodeMd5 = te.data

                h = hashlib.md5(str([])).hexdigest()
                if h != te.data and self.machifProgExec is not None:
                    h = hashlib.md5(str(self.stateData.gcodeFileLines)).hexdigest()
                    if h != te.data:
                        self.machifProgExec.add_event(gc.EV_CMD_GET_GCODE)

            elif te.event_id == gc.EV_GCODE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GCODE")

                # only if there is gcode we should do do something
                if te.data.get('gcodeLines', []):
                    user_response = wx.ID_YES

                    if self.gcText.GetModify():
                        title = "Get Remote G-code"
                        prompt = "Current G-code has been modified, save before overide?"
                        if sys.platform in 'darwin':
                            # because dialog icons where not working correctly in
                            # Mac OS X
                            dlg = gmd.GenericMessageDialog(
                                self, prompt, title,
                                wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_QUESTION)
                        else:
                            dlg = wx.MessageDialog(
                                self, prompt, title,
                                wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_QUESTION)


                        user_response = dlg.ShowModal()
                        if user_response == wx.ID_YES:
                            self.OnFileSaveAs(None)

                        dlg.Destroy()

                    if user_response == wx.ID_CANCEL:
                        # cancel G-code update from remote server
                        pass
                    else:
                        if 'gcodeFileName' in te.data:
                            self.stateData.gcodeFileName = te.data['gcodeFileName']
                        else:
                            self.stateData.gcodeFileName = ""

                        self.SetTitle("{} - {}".format(os.path.basename(self.stateData.gcodeFileName), __appname__))
                        self.statusbar.SetStatusText(os.path.basename(self.stateData.gcodeFileName))
                        self.stateData.fileIsOpen = False

                        if 'gcodeLines' in te.data:
                            readOnly = self.gcText.GetReadOnly()
                            self.gcText.SetReadOnly(False)
                            self.gcText.ClearAll()
                            self.gcText.AddText("".join(te.data['gcodeLines']))
                            self.gcText.SetReadOnly(readOnly)
                            self.gcText.DiscardEdits()
                        else:
                            readOnly = self.gcText.GetReadOnly()
                            self.gcText.SetReadOnly(False)
                            self.gcText.ClearAll()
                            self.gcText.SetReadOnly(readOnly)
                            self.gcText.DiscardEdits()

                        rawText = self.gcText.GetText()
                        self.stateData.gcodeFileLines = rawText.splitlines(True)
                        h = hashlib.md5(str(self.stateData.gcodeFileLines)).hexdigest()
                        self.machifProgExecGcodeMd5 = h

                        if 'gcodePC' in te.data:
                            self.SetPC(te.data['gcodePC'])
                        else:
                            self.SetPC(0)

                        if 'breakPoints' in te.data:
                            break_points = te.data['breakPoints']
                            self.gcText.DeleteAllBreakPoints()
                            for bp in break_points:
                                self.gcText.UpdateBreakPoint(bp, True)
                        else:
                            self.gcText.DeleteAllBreakPoints()

                        self.gcText.GoToPC()
                        self.UpdateUI()

            elif te.event_id == gc.EV_BRK_PT_CHG:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_BRK_PT_CHG")

                if self.machifProgExec is not None:
                    self.machifProgExec.add_event(gc.EV_CMD_GET_BRK_PT)

            elif te.event_id == gc.EV_BRK_PT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_BRK_PT")

                break_points = te.data

                if self.gcText.GetBreakPoints() != break_points:
                    self.gcText.DeleteAllBreakPoints()
                    for bp in break_points:
                        self.gcText.UpdateBreakPoint(bp, True)

            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.error(
                        "got UNKNOWN event id[{}] from 0x{:x} {}".format(te.event_id, id(te.sender), te.sender))

                # self.stateData.swState = gc.STATE_IDLE
                self.UpdateUI()

        # deal with delay between sw-run-end and machif-end
        # definition: software send all gcode lines ot machif, but machine
        # still executing on them. UI should be re-anabled, any new command
        # will be queued behind already proccessed ones
        if self.runEndWaitingForMachIfIdle:
            if self.stateData.machineStatusString in [
               "Idle", "idle", "Stop", "stop", "End", "end"]:
                self.runEndWaitingForMachIfIdle = False
                # self.RunTimerStop()

                # calculate run time
                runStartTime = time.time() - self.progexecRunTime
                runTime = self.progexecRunTime

                hours, reminder = divmod(runTime, 3600)
                minutes, reminder = divmod(reminder, 60)
                seconds, mseconds = divmod(reminder, 1)
                runTimeStr = "%02d:%02d:%02d" % (hours, minutes, seconds)
                runStartTimeStr = time.strftime(
                    "%a, %d %b %Y %H:%M:%S", time.localtime(runStartTime))
                runEndTimeStr = time.strftime(
                    "%a, %d %b %Y %H:%M:%S", time.localtime(runStartTime + runTime))

                self.Refresh()
                self.UpdateUI()

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
                    print ("gsatMainWindow queuing machine init script...")

                self.outputText.AppendText("Queuing machine init script...\n")
                for initLine in initScript:

                    for reComments in reGcodeComments:
                        initLine = reComments.sub("", initLine)

                    initLine = "".join([initLine, "\n"])

                    if len(initLine.strip()) > 0:
                        self.SerialWrite(initLine)
                        # self.SerialWriteWaitForAck(initLine)
                        self.outputText.AppendText(initLine)

    def add_event(self, id, data=None, sender=None):
        gc.EventQueueIf.add_event(self, id, data, sender)
        self.eventInCount = self.eventInCount + 1
        wx.PostEvent(self, ThreadQueueEvent(None))

    def eventForward2Machif(self, id, data=None, sender=None):
        if self.machifProgExec is not None:
            self.machifProgExec.add_event(id, data, sender)
