"""----------------------------------------------------------------------------
   mainwnd.py

   Copyright (C) 2013, 2014 Wilhelm Duembeg

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

__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
"GCODE Step and Alignment Tool (gsat) is a cross-platform GCODE debug/step for "\
"Grbl like GCODE interpreters. With features similar to software debuggers. Features "\
"Such as breakpoint, change current program counter, inspection and modification "\
"of variables."


# define authorship information
__authors__     = ['Wilhelm Duembeg']
__author__      = ','.join(__authors__)
__credits__     = []
__copyright__   = 'Copyright (c) 2013, 2014'
__license__     = 'GPL v2'
__license_str__ = __license__ + '\nhttp://www.gnu.org/licenses/gpl-2.0.txt'

# maintenance information
__maintainer__  = 'Wilhelm Duembeg'
__email__       = 'duembeg.github@gmail.com'

# define version information
__requires__        = ['pySerial', 'wxPython']
__version_info__    = (1, 3, 0)
__version__         = 'v%i.%02i.%02i' % __version_info__
__revision__        = __version__


"""----------------------------------------------------------------------------
   Dependencies:
----------------------------------------------------------------------------"""
import os
import sys
import glob
import serial
import re
import threading
import Queue
import time
import shutil
from optparse import OptionParser
import wx
import wx.combo
from wx import stc as stc
from wx.lib.mixins import listctrl as listmix
from wx.lib.agw import aui as aui
from wx.lib.agw import floatspin as fs
#from wx.lib.agw import flatmenu as fm
from wx.lib.wordwrap import wordwrap
from wx.lib import scrolledpanel as scrolled

import modules.config as gc
import images.icons as ico
import modules.editor as ed
import modules.link as link
import modules.machine as mc
import modules.jogging as jog
import modules.compvision as compv
import modules.progexec as progexec

"""----------------------------------------------------------------------------
   Globals:
----------------------------------------------------------------------------"""

# -----------------------------------------------------------------------------
# MENU & TOOL BAR IDs
# -----------------------------------------------------------------------------
gID_TOOLBAR_OPEN                 = wx.NewId()
gID_TOOLBAR_LINK_STATUS          = wx.NewId()
gID_TOOLBAR_PROGRAM_STATUS       = wx.NewId()
gID_TOOLBAR_MACHINE_STATUS       = wx.NewId()
gID_MENU_MAIN_TOOLBAR            = wx.NewId()
gID_MENU_SEARCH_TOOLBAR          = wx.NewId()
gID_MENU_RUN_TOOLBAR             = wx.NewId()
gID_MENU_STATUS_TOOLBAR          = wx.NewId()
gID_MENU_OUTPUT_PANEL            = wx.NewId()
gID_MENU_COMAMND_PANEL           = wx.NewId()
gID_MENU_MACHINE_STATUS_PANEL    = wx.NewId()
gID_MENU_MACHINE_JOGGING_PANEL   = wx.NewId()
gID_MENU_CV2_PANEL               = wx.NewId()
gID_MENU_LOAD_DEFAULT_LAYOUT     = wx.NewId()
gID_MENU_SAVE_DEFAULT_LAYOUT     = wx.NewId()
gID_MENU_RESET_DEFAULT_LAYOUT    = wx.NewId()
gID_MENU_LOAD_LAYOUT             = wx.NewId()
gID_MENU_SAVE_LAYOUT             = wx.NewId()
gID_MENU_RUN                     = wx.NewId()
gID_MENU_STEP                    = wx.NewId()
gID_MENU_STOP                    = wx.NewId()
gID_MENU_BREAK_TOGGLE            = wx.NewId()
gID_MENU_BREAK_REMOVE_ALL        = wx.NewId()
gID_MENU_SET_PC                  = wx.NewId()
gID_MENU_GOTO_PC                 = wx.NewId()
gID_MENU_ABORT                   = wx.NewId()
gID_MENU_IN2MM                   = wx.NewId()
gID_MENU_MM2IN                   = wx.NewId()
gID_MENU_G812G01                 = wx.NewId()
gID_MENU_FIND                    = wx.NewId()
gID_MENU_GOTOLINE                = wx.NewId()


gID_TIMER_MACHINE_REFRESH        = wx.NewId()

# -----------------------------------------------------------------------------
# regular expressions
# -----------------------------------------------------------------------------

# grbl version, example "Grbl 0.8c ['$' for help]"
gReGrblVersion = re.compile(r'Grbl\s*(.*)\s*\[.*\]')

# status, example "<Run,MPos:20.163,0.000,0.000,WPos:20.163,0.000,0.000>"
gReMachineStatus = re.compile(r'<(.*),MPos:(.*),(.*),(.*),WPos:(.*),(.*),(.*)>')

# comments example "( comment string )" or "; comment string"
#gReGcodeComments = [re.compile(r'\(.*\)'), re.compile(r';.*')]
#gReGcodeMsg = re.compile(r'^\s*\(MSG,(.+)\)')

"""----------------------------------------------------------------------------
   gsatLog:
   custom wxLog
----------------------------------------------------------------------------"""
class gsatLog(wx.PyLog):
    def __init__(self, textCtrl, logTime=0):
        wx.PyLog.__init__(self)
        self.tc = textCtrl
        self.logTime = logTime

    def DoLogString(self, message, timeStamp):
        #print message, timeStamp
        #if self.logTime:
        #    message = time.strftime("%X", time.localtime(timeStamp)) + \
        #              ": " + message
        if self.tc:
            self.tc.AppendText(message + '\n')

"""----------------------------------------------------------------------------
   gsatGeneralSettingsPanel:
   General settings panel.
----------------------------------------------------------------------------"""
class gsatGeneralSettingsPanel(scrolled.ScrolledPanel):
   def __init__(self, parent, configData, **args):
      scrolled.ScrolledPanel.__init__(self, parent,
         style=wx.TAB_TRAVERSAL|wx.NO_BORDER)

      self.configData = configData

      self.InitUI()
      self.SetAutoLayout(True)
      self.SetupScrolling()
      #self.FitInside()

   def InitUI(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # file settings
      text = wx.StaticText(self, label="Files:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      # Add file save backup check box
      self.cbBackupFile = wx.CheckBox(self, wx.ID_ANY, "Create a backup copy of file before saving")
      self.cbBackupFile.SetValue(self.configData.Get('/mainApp/BackupFile'))
      vBoxSizer.Add(self.cbBackupFile, flag=wx.LEFT, border=25)

      # Add file history spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      self.scFileHistory = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scFileHistory.SetRange(0,100)
      self.scFileHistory.SetValue(self.configData.Get('/mainApp/MaxFileHistory'))
      hBoxSizer.Add(self.scFileHistory, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Recent file history size")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      # tools settings
      text = wx.StaticText(self, label="Tools:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      # Add Inch to mm round digits spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.scIN2MMRound = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scIN2MMRound.SetRange(0,100)
      self.scIN2MMRound.SetValue(self.configData.Get('/mainApp/RoundInch2mm'))
      hBoxSizer.Add(self.scIN2MMRound, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "Inch to mm round digits")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      # Add mm to Inch round digits spin ctrl
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      self.scMM2INRound = wx.SpinCtrl(self, wx.ID_ANY, "")
      self.scMM2INRound.SetRange(0,100)
      self.scMM2INRound.SetValue(self.configData.Get('/mainApp/Roundmm2Inch'))
      hBoxSizer.Add(self.scMM2INRound, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      st = wx.StaticText(self, wx.ID_ANY, "mm to Inch round digits")
      hBoxSizer.Add(st, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)

      vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)


      self.SetSizer(vBoxSizer)

   def UpdatConfigData(self):
      self.configData.Set('/mainApp/BackupFile', self.cbBackupFile.GetValue())
      self.configData.Set('/mainApp/MaxFileHistory', self.scFileHistory.GetValue())
      self.configData.Set('/mainApp/RoundInch2mm', self.scIN2MMRound.GetValue())
      self.configData.Set('/mainApp/Roundmm2Inch', self.scMM2INRound.GetValue())


"""----------------------------------------------------------------------------
   gsatSettingsDialog:
   Dialog to control program settings
----------------------------------------------------------------------------"""
class gsatSettingsDialog(wx.Dialog):
   def __init__(self, parent, configData, id=wx.ID_ANY, title="Settings",
      style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER):

      wx.Dialog.__init__(self, parent, id, title, style=style)

      self.configData = configData

      self.InitUI()

   def InitUI(self):
      sizer = wx.BoxSizer(wx.VERTICAL)

      # init note book
      self.imageList = wx.ImageList(16, 16)
      self.imageList.Add(ico.imgGeneralSettings.GetBitmap())
      self.imageList.Add(ico.imgPlugConnect.GetBitmap())
      self.imageList.Add(ico.imgProgram.GetBitmap())
      self.imageList.Add(ico.imgLog.GetBitmap())
      self.imageList.Add(ico.imgCli.GetBitmap())
      self.imageList.Add(ico.imgMachine.GetBitmap())
      self.imageList.Add(ico.imgMove.GetBitmap())
      self.imageList.Add(ico.imgEye.GetBitmap())

      if os.name == 'nt':
         self.noteBook = wx.Notebook(self, size=(640,400))
      else:
         self.noteBook = wx.Notebook(self, size=(640,400), style=wx.BK_LEFT)

      self.noteBook.AssignImageList(self.imageList)

      # add pages
      self.AddGeneralPage(0)
      self.AddLinkPage(1)
      self.AddProgramPage(2)
      self.AddOutputPage(3)
      self.AddCliPage(4)
      self.AddMachinePage(5)
      self.AddJoggingPage(6)
      self.AddCV2Panel(7)

      #self.noteBook.Layout()
      sizer.Add(self.noteBook, 1, wx.ALL|wx.EXPAND, 5)

      # buttons
      line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
      sizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.TOP, border=5)

      btnsizer = wx.StdDialogButtonSizer()

      btn = wx.Button(self, wx.ID_OK)
      btnsizer.AddButton(btn)

      btn = wx.Button(self, wx.ID_CANCEL)
      btnsizer.AddButton(btn)

      btnsizer.Realize()

      sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5)

      self.SetSizerAndFit(sizer)
      #self.SetAutoLayout(True)

   def AddGeneralPage(self, page):
      self.generalPage = gsatGeneralSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.generalPage, "General")
      self.noteBook.SetPageImage(page, page)

   def AddLinkPage(self, page):
      self.linkPage = link.gsatLinkSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.linkPage, "Link")
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
      self.machinePage = mc.gsatMachineSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.machinePage, "Machine")
      self.noteBook.SetPageImage(page, page)

   def AddJoggingPage(self, page):
      self.jogPage = jog.gsatJoggingSettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.jogPage, "Jogging")
      self.noteBook.SetPageImage(page, page)

   def AddCV2Panel(self, page):
      self.CV2Page = compv.gsatCV2SettingsPanel(self.noteBook, self.configData)
      self.noteBook.AddPage(self.CV2Page, " OpenCV2")
      self.noteBook.SetPageImage(page, page)

   def UpdatConfigData(self):
      self.generalPage.UpdatConfigData()
      self.linkPage.UpdatConfigData()
      self.programPage.UpdatConfigData()
      self.outputPage.UpdatConfigData()
      self.cliPage.UpdatConfigData()
      self.machinePage.UpdatConfigData()
      self.jogPage.UpdatConfigData()
      self.CV2Page.UpdatConfigData()

"""----------------------------------------------------------------------------
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
   gsatMainWindow:
   Main Window Inits the UI and other panels, it also controls the worker
   threads and resources such as serial port.
-------------------------------------------------------------------------------
----------------------------------------------------------------------------"""
class gsatMainWindow(wx.Frame):

   def __init__(self, parent, id=wx.ID_ANY, title="", cmd_line_options=None,
      pos=wx.DefaultPosition, size=(800, 600), style=wx.DEFAULT_FRAME_STYLE):

      wx.Frame.__init__(self, parent, id, title, pos, size, style)

      # init config file
      self.configFile = wx.FileConfig("gsat", style=wx.CONFIG_USE_LOCAL_FILE)

      self.SetIcon(ico.imgGCSBlack32x32.GetIcon())

      # register for thread events
      gc.EVT_THREAD_QUEUE_EVENT(self, self.OnThreadEvent)

      # create serial obj
      self.serPort = serial.Serial()

      # create app data obj
      self.stateData = gc.gsatStateData()

      # create app data obj
      self.configData = gc.gsatConfigData()
      self.configData.Load(self.configFile)
      self.configData.Add('/link/PortList', self.GetSerialPortList())
      self.configData.Add('/link/BaudList', self.GetSerialBaudRateList())
      self.InitConfig()

      # init some variables
      self.progExecThread = None
      self.machineAutoRefreshTimer = None

      self.cmdLineOptions = cmd_line_options

      # thread communication queues
      self.mainWndInQueue = Queue.Queue()
      self.mainWndOutQueue = Queue.Queue()

      # register for close events
      self.Bind(wx.EVT_CLOSE, self.OnClose)

      self.InitUI()
      self.Centre()
      self.Show()

   def InitConfig(self):
      self.saveBackupFile = self.configData.Get('/mainApp/BackupFile')
      self.maxFileHistory = self.configData.Get('/mainApp/MaxFileHistory')
      self.roundInch2mm = self.configData.Get('/mainApp/RoundInch2mm')
      self.roundmm2Inch = self.configData.Get('/mainApp/Roundmm2Inch')
      self.linkPort = self.configData.Get('/link/Port')
      self.linkBaud = self.configData.Get('/link/Baud')
      self.machineAutoRefresh = self.configData.Get('/machine/AutoRefresh')
      self.machineAutoRefreshPeriod = self.configData.Get('/machine/AutoRefreshPeriod')

   def InitUI(self):
      """ Init main UI """

      # init aui manager
      self.aui_mgr = aui.AuiManager()

      # notify AUI which frame to use
      self.aui_mgr.SetManagedWindow(self)

      #self.connectionPanel = gsatConnectionPanel(self)
      self.machineStatusPanel = mc.gsatMachineStatusPanel(self, self.configData, self.stateData,)
      self.CV2Panel = compv.gsatCV2Panel(self, self.configData, self.stateData, self.cmdLineOptions)
      self.machineJoggingPanel = jog.gsatJoggingPanel(self, self.configData, self.stateData)
      self.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter, self.machineJoggingPanel.cliComboBox)

      # output Window
      self.outputText = ed.gsatStcStyledTextCtrl(self, self.configData, self.stateData, style=wx.NO_BORDER)
      wx.Log_SetActiveTarget(gsatLog(self.outputText))

      # for serious debugging
      #wx.Log_SetActiveTarget(wx.LogStderr())
      #wx.Log_SetTraceMask(wx.TraceMessages)

      # main gcode list control
      self.gcText = ed.gsatGcodeStcStyledTextCtrl(self, self.configData, self.stateData, style=wx.NO_BORDER)

      # add the panes to the manager
      self.aui_mgr.AddPane(self.gcText,
         aui.AuiPaneInfo().Name("GCODE_PANEL").CenterPane().Caption("G-Code")\
            .CloseButton(True).MaximizeButton(True).BestSize(600,600))


      self.aui_mgr.AddPane(self.outputText,
         aui.AuiPaneInfo().Name("OUTPUT_PANEL").Bottom().Position(1).Caption("Output")\
            .CloseButton(True).MaximizeButton(True).BestSize(600,200)
      )

      self.aui_mgr.AddPane(self.CV2Panel,
         aui.AuiPaneInfo().Name("CV2_PANEL").Right().Row(1).Caption("Computer Vision")\
            .CloseButton(True).MaximizeButton(True).BestSize(640,530).Hide().Layer(1)
      )

      self.aui_mgr.AddPane(self.machineJoggingPanel,
         aui.AuiPaneInfo().Name("MACHINE_JOGGING_PANEL").Right().Row(1).Caption("Machine Jogging")\
            .CloseButton(True).MaximizeButton(True).BestSize(360,380).Layer(1)
      )

      self.aui_mgr.AddPane(self.machineStatusPanel,
         aui.AuiPaneInfo().Name("MACHINE_STATUS_PANEL").Right().Row(1).Caption("Machine Status")\
            .CloseButton(True).MaximizeButton(True).BestSize(320,180).Layer(1)
      )


      self.CreateMenu()
      self.CreateToolBar()

      # tell the manager to "commit" all the changes just made
      self.aui_mgr.SetAGWFlags(self.aui_mgr.GetAGWFlags()|aui.AUI_MGR_ALLOW_ACTIVE_PANE )

      # load default layout
      perspectiveDefault = self.aui_mgr.SavePerspective()
      self.SaveLayoutData('/mainApp/ResetLayout')

      self.LoadLayoutData('/mainApp/DefaultLayout', False)

      # finish up
      self.aui_mgr.Update()
      wx.CallAfter(self.UpdateUI)
      self.SetPC(0)

   def CreateMenu(self):

      # Create the menubar
      #self.menuBar = FM.FlatMenuBar(self, wx.ID_ANY, 32, 5, options = FM_OPT_SHOW_TOOLBAR | FM_OPT_SHOW_CUSTOMIZE)
      #self.menuBar = fm.FlatMenuBar(self, wx.ID_ANY, options=fm.FM_OPT_SHOW_TOOLBAR)
      self.menuBar = wx.MenuBar()

      #------------------------------------------------------------------------
      # File menu
      fileMenu = wx.Menu()
      self.menuBar.Append(fileMenu,                            "&File")

      openItem = wx.MenuItem(fileMenu, wx.ID_OPEN,             "&Open")
      openItem.SetBitmap(ico.imgOpen.GetBitmap())
      fileMenu.AppendItem(openItem)

      recentMenu = wx.Menu()
      fileMenu.AppendMenu(wx.ID_ANY,                           "&Recent Files",
         recentMenu)

      # load history
      self.fileHistory = wx.FileHistory(self.maxFileHistory)
      self.fileHistory.Load(self.configFile)
      self.fileHistory.UseMenu(recentMenu)
      self.fileHistory.AddFilesToMenu()

      saveItem = wx.MenuItem(fileMenu, wx.ID_SAVE,             "&Save")
      if os.name != 'nt':
         saveItem.SetBitmap(ico.imgSave.GetBitmap())
      fileMenu.AppendItem(saveItem)

      saveAsItem = wx.MenuItem(fileMenu, wx.ID_SAVEAS,         "Save &As")
      if os.name != 'nt':
         saveAsItem.SetBitmap(ico.imgSave.GetBitmap())
      fileMenu.AppendItem(saveAsItem)

      exitItem = wx.MenuItem(fileMenu, wx.ID_EXIT,             "E&xit")
      exitItem.SetBitmap(ico.imgExit.GetBitmap())
      fileMenu.AppendItem(exitItem)

      #------------------------------------------------------------------------
      # Edit menu
      #viewEdit = wx.Menu()
      #self.menuBar.Append(viewEdit,                   "&Edit")

      #viewEdit.Append(wx.ID_PREFERENCES,              "&Settings")

      #------------------------------------------------------------------------
      # View menu
      viewMenu = wx.Menu()
      self.menuBar.Append(viewMenu,                            "&View")

      viewMenu.AppendCheckItem(gID_MENU_MAIN_TOOLBAR,          "&Main Tool Bar")
      viewMenu.AppendCheckItem(gID_MENU_SEARCH_TOOLBAR,        "&Search Tool Bar")
      viewMenu.AppendCheckItem(gID_MENU_RUN_TOOLBAR,           "&Run Tool Bar")
      viewMenu.AppendCheckItem(gID_MENU_STATUS_TOOLBAR,        "Status &Tool Bar")
      viewMenu.AppendSeparator()
      viewMenu.AppendCheckItem(gID_MENU_OUTPUT_PANEL,          "&Output")
      viewMenu.AppendCheckItem(gID_MENU_COMAMND_PANEL,         "&Command (CLI)")
      viewMenu.AppendCheckItem(gID_MENU_MACHINE_STATUS_PANEL,  "Machine &Status")
      viewMenu.AppendCheckItem(gID_MENU_MACHINE_JOGGING_PANEL, "Machine &Jogging")
      viewMenu.AppendCheckItem(gID_MENU_CV2_PANEL,             "Computer &Vision")
      viewMenu.AppendSeparator()
      viewMenu.Append(gID_MENU_LOAD_DEFAULT_LAYOUT,            "&Load Layout")
      viewMenu.Append(gID_MENU_SAVE_DEFAULT_LAYOUT,            "S&ave Layout")
      viewMenu.Append(gID_MENU_RESET_DEFAULT_LAYOUT,           "R&eset Layout")
      #viewMenu.Append(gID_MENU_LOAD_LAYOUT,                    "Loa&d Layout...")
      #viewMenu.Append(gID_MENU_SAVE_LAYOUT,                    "Sa&ve Layout...")
      viewMenu.AppendSeparator()

      settingsItem = wx.MenuItem(viewMenu, wx.ID_PREFERENCES,     "&Settings")
      settingsItem.SetBitmap(ico.imgSettings.GetBitmap())
      viewMenu.AppendItem(settingsItem)


      #------------------------------------------------------------------------
      # Run menu
      runMenu = wx.Menu()
      self.menuBar.Append(runMenu,                    "&Run")

      runItem = wx.MenuItem(runMenu, gID_MENU_RUN,    "&Run\tF5")
      if os.name != 'nt':
         runItem.SetBitmap(ico.imgPlay.GetBitmap())
      runMenu.AppendItem(runItem)

      stepItem = wx.MenuItem(runMenu, gID_MENU_STEP,  "S&tep")
      if os.name != 'nt':
         stepItem.SetBitmap(ico.imgStep.GetBitmap())
      runMenu.AppendItem(stepItem)

      stopItem = wx.MenuItem(runMenu, gID_MENU_STOP,  "&Stop")
      if os.name != 'nt':
         stopItem.SetBitmap(ico.imgStop.GetBitmap())
      runMenu.AppendItem(stopItem)

      runMenu.AppendSeparator()
      breakItem = wx.MenuItem(runMenu, gID_MENU_BREAK_TOGGLE,
                                                      "Brea&kpoint Toggle\tF9")
      if os.name != 'nt':
         breakItem.SetBitmap(ico.imgBreak.GetBitmap())
      runMenu.AppendItem(breakItem)

      runMenu.Append(gID_MENU_BREAK_REMOVE_ALL,       "Breakpoint &Remove All")
      runMenu.AppendSeparator()

      setPCItem = wx.MenuItem(runMenu, gID_MENU_SET_PC,"Set &PC")
      if os.name != 'nt':
         setPCItem.SetBitmap(ico.imgMapPin.GetBitmap())
      runMenu.AppendItem(setPCItem)

      gotoPCItem = wx.MenuItem(runMenu, gID_MENU_GOTO_PC,
                                                      "&Goto PC")
      if os.name != 'nt':
         gotoPCItem.SetBitmap(ico.imgGotoMapPin.GetBitmap())
      runMenu.AppendItem(gotoPCItem)

      runMenu.AppendSeparator()

      abortItem = wx.MenuItem(runMenu, gID_MENU_ABORT,"&Abort")
      if os.name != 'nt':
         abortItem.SetBitmap(ico.imgAbort.GetBitmap())
      runMenu.AppendItem(abortItem)

      #------------------------------------------------------------------------
      # Tool menu
      toolMenu = wx.Menu()
      self.menuBar.Append(toolMenu,                   "&Tools")

      toolMenu.Append(gID_MENU_IN2MM,                 "&Inch to mm")
      toolMenu.Append(gID_MENU_MM2IN,                 "&mm to Inch")
      toolMenu.AppendSeparator()
      toolMenu.Append(gID_MENU_G812G01,               "&G81 to G01")

      #------------------------------------------------------------------------
      # Help menu
      helpMenu = wx.Menu()
      self.menuBar.Append(helpMenu,                   "&Help")

      aboutItem = wx.MenuItem(helpMenu, wx.ID_ABOUT,  "&About", "About gsat")
      aboutItem.SetBitmap(ico.imgAbout.GetBitmap())
      helpMenu.AppendItem(aboutItem)


      #------------------------------------------------------------------------
      # Bind events to handlers

      #------------------------------------------------------------------------
      # File menu bind
      self.Bind(wx.EVT_MENU,        self.OnFileOpen,     id=wx.ID_OPEN)
      self.Bind(wx.EVT_MENU_RANGE,  self.OnFileHistory,  id=wx.ID_FILE1, id2=wx.ID_FILE9)
      self.Bind(wx.EVT_MENU,        self.OnFileSave,     id=wx.ID_SAVE)
      self.Bind(wx.EVT_MENU,        self.OnFileSaveAs,   id=wx.ID_SAVEAS)
      self.Bind(wx.EVT_MENU,        self.OnClose,        id=wx.ID_EXIT)
      self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN,
                           self.OnDropDownToolBarOpen,   id=gID_TOOLBAR_OPEN)

      self.Bind(wx.EVT_UPDATE_UI, self.OnFileSaveUpdate, id=wx.ID_SAVE)
      self.Bind(wx.EVT_UPDATE_UI, self.OnFileSaveAsUpdate,
                                                         id=wx.ID_SAVEAS)

      #------------------------------------------------------------------------
      # Search menu bind
      self.Bind(wx.EVT_MENU, self.OnFind,                id=gID_MENU_FIND)
      self.Bind(wx.EVT_MENU, self.OnGotoLine,            id=gID_MENU_GOTOLINE)

      #------------------------------------------------------------------------
      # View menu bind
      self.Bind(wx.EVT_MENU, self.OnMainToolBar,         id=gID_MENU_MAIN_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnSearchToolBar,       id=gID_MENU_SEARCH_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnRunToolBar,          id=gID_MENU_RUN_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnStatusToolBar,       id=gID_MENU_STATUS_TOOLBAR)
      self.Bind(wx.EVT_MENU, self.OnOutput,              id=gID_MENU_OUTPUT_PANEL)
      self.Bind(wx.EVT_MENU, self.OnMachineStatus,       id=gID_MENU_MACHINE_STATUS_PANEL)
      self.Bind(wx.EVT_MENU, self.OnMachineJogging,      id=gID_MENU_MACHINE_JOGGING_PANEL)
      self.Bind(wx.EVT_MENU, self.OnComputerVision,      id=gID_MENU_CV2_PANEL)
      self.Bind(wx.EVT_MENU, self.OnLoadDefaultLayout,   id=gID_MENU_LOAD_DEFAULT_LAYOUT)
      self.Bind(wx.EVT_MENU, self.OnSaveDefaultLayout,   id=gID_MENU_SAVE_DEFAULT_LAYOUT)
      self.Bind(wx.EVT_MENU, self.OnResetDefaultLayout,  id=gID_MENU_RESET_DEFAULT_LAYOUT)

      self.Bind(wx.EVT_UPDATE_UI, self.OnMainToolBarUpdate,
                                                         id=gID_MENU_MAIN_TOOLBAR)
      self.Bind(wx.EVT_UPDATE_UI, self.OnSearchToolBarUpdate,
                                                         id=gID_MENU_SEARCH_TOOLBAR)
      self.Bind(wx.EVT_UPDATE_UI, self.OnRunToolBarUpdate,
                                                         id=gID_MENU_RUN_TOOLBAR)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStatusToolBarUpdate,
                                                         id=gID_MENU_STATUS_TOOLBAR)
      self.Bind(wx.EVT_UPDATE_UI, self.OnOutputUpdate,   id=gID_MENU_OUTPUT_PANEL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnMachineStatusUpdate,
                                                         id=gID_MENU_MACHINE_STATUS_PANEL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnMachineJoggingUpdate,
                                                         id=gID_MENU_MACHINE_JOGGING_PANEL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnComputerVisionUpdate,
                                                         id=gID_MENU_CV2_PANEL)

      self.Bind(wx.EVT_MENU, self.OnSettings,            id=wx.ID_PREFERENCES)

      #------------------------------------------------------------------------
      # Run menu bind
      self.Bind(wx.EVT_MENU, self.OnRun,                 id=gID_MENU_RUN)
      self.Bind(wx.EVT_MENU, self.OnStep,                id=gID_MENU_STEP)
      self.Bind(wx.EVT_MENU, self.OnStop,                id=gID_MENU_STOP)
      self.Bind(wx.EVT_MENU, self.OnBreakToggle,         id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_MENU, self.OnBreakRemoveAll,      id=gID_MENU_BREAK_REMOVE_ALL)
      self.Bind(wx.EVT_MENU, self.OnSetPC,               id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_MENU, self.OnGoToPC,              id=gID_MENU_GOTO_PC)
      self.Bind(wx.EVT_MENU, self.OnAbort,               id=gID_MENU_ABORT)

      self.Bind(wx.EVT_BUTTON, self.OnRun,               id=gID_MENU_RUN)
      self.Bind(wx.EVT_BUTTON, self.OnStep,              id=gID_MENU_STEP)
      self.Bind(wx.EVT_BUTTON, self.OnStop,              id=gID_MENU_STOP)
      self.Bind(wx.EVT_BUTTON, self.OnBreakToggle,       id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_BUTTON, self.OnSetPC,             id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_BUTTON, self.OnGoToPC,            id=gID_MENU_GOTO_PC)
      self.Bind(wx.EVT_BUTTON, self.OnAbort,             id=gID_MENU_ABORT)

      self.Bind(wx.EVT_UPDATE_UI, self.OnRunUpdate,      id=gID_MENU_RUN)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStepUpdate,     id=gID_MENU_STEP)
      self.Bind(wx.EVT_UPDATE_UI, self.OnStopUpdate,     id=gID_MENU_STOP)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakToggleUpdate,
                                                         id=gID_MENU_BREAK_TOGGLE)
      self.Bind(wx.EVT_UPDATE_UI, self.OnBreakRemoveAllUpdate,
                                                         id=gID_MENU_BREAK_REMOVE_ALL)
      self.Bind(wx.EVT_UPDATE_UI, self.OnSetPCUpdate,    id=gID_MENU_SET_PC)
      self.Bind(wx.EVT_UPDATE_UI, self.OnGoToPCUpdate,   id=gID_MENU_GOTO_PC)
      self.Bind(wx.EVT_UPDATE_UI, self.OnAbortUpdate,    id=gID_MENU_ABORT)

      #------------------------------------------------------------------------
      # tools menu bind
      self.Bind(wx.EVT_MENU, self.OnInch2mm,             id=gID_MENU_IN2MM)
      self.Bind(wx.EVT_MENU, self.Onmm2Inch,             id=gID_MENU_MM2IN)
      self.Bind(wx.EVT_MENU, self.OnG812G01,             id=gID_MENU_G812G01)

      self.Bind(wx.EVT_UPDATE_UI, self.OnInch2mmUpdate,  id=gID_MENU_IN2MM)
      self.Bind(wx.EVT_UPDATE_UI, self.Onmm2InchUpdate,  id=gID_MENU_MM2IN)
      self.Bind(wx.EVT_UPDATE_UI, self.OnG812G01Update,  id=gID_MENU_G812G01)

      #------------------------------------------------------------------------
      # Help menu bind
      self.Bind(wx.EVT_MENU, self.OnAbout,               id=wx.ID_ABOUT)


      #------------------------------------------------------------------------
      # Status tool bar
      self.Bind(wx.EVT_MENU, self.OnLinkStatus,          id=gID_TOOLBAR_LINK_STATUS)
      self.Bind(wx.EVT_MENU, self.OnGetMachineStatus,    id=gID_TOOLBAR_MACHINE_STATUS)


      #------------------------------------------------------------------------
      # Create shortcut keys for menu
      acceleratorTable = wx.AcceleratorTable([
         #(wx.ACCEL_ALT,       ord('X'),         wx.ID_EXIT),
         #(wx.ACCEL_CTRL,      ord('H'),         helpID),
         #(wx.ACCEL_CTRL,      ord('F'),         findID),
         (wx.ACCEL_NORMAL,    wx.WXK_F5,        gID_MENU_RUN),
         (wx.ACCEL_NORMAL,    wx.WXK_F9,        gID_MENU_BREAK_TOGGLE),
      ])

      self.SetAcceleratorTable(acceleratorTable)

      # finish up...
      self.SetMenuBar(self.menuBar)

   def CreateToolBar(self):
      iconSize = (16, 16)

      #------------------------------------------------------------------------
      # Main Tool Bar
      self.appToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
         agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            aui.AUI_TB_TEXT |
            aui.AUI_TB_HORZ_TEXT |
            #aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE
         )


      self.appToolBar.SetToolBitmapSize(iconSize)

      self.appToolBar.AddSimpleTool(gID_TOOLBAR_OPEN, "Open", ico.imgOpen.GetBitmap(),
         "Open\tCtrl+O")

      self.appToolBar.AddSimpleTool(wx.ID_SAVE, "Save", ico.imgSave.GetBitmap(),
         "Save\tCtrl+S")
      self.appToolBar.SetToolDisabledBitmap(wx.ID_SAVE, ico.imgSaveDisabled.GetBitmap())

      self.appToolBar.AddSimpleTool(wx.ID_SAVEAS, "Save As", ico.imgSave.GetBitmap(),
         "Save As")
      self.appToolBar.SetToolDisabledBitmap(wx.ID_SAVEAS, ico.imgSaveDisabled.GetBitmap())

      self.appToolBar.SetToolDropDown(gID_TOOLBAR_OPEN, True)

      self.appToolBar.Realize()

      self.aui_mgr.AddPane(self.appToolBar,
         aui.AuiPaneInfo().Name("MAIN_TOOLBAR").Caption("Main Tool Bar").ToolbarPane().Top().Gripper())

      #------------------------------------------------------------------------
      # Search Tool Bar
      self.searchToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
         agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            aui.AUI_TB_TEXT |
            aui.AUI_TB_HORZ_TEXT |
            #aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE
         )

      self.searchToolBarFind = wx.TextCtrl(self.searchToolBar, size=(100,-1),
         style=wx.TE_PROCESS_ENTER)
      self.searchToolBar.AddControl(self.searchToolBarFind)
      self.searchToolBar.SetToolTipString("Find Text")
      self.searchToolBar.AddSimpleTool(gID_MENU_FIND, "", ico.imgFind.GetBitmap(),
         "Find Next\tF3")
      self.Bind(wx.EVT_TEXT_ENTER, self.OnFind, self.searchToolBarFind)

      self.searchToolBarGotoLine = wx.TextCtrl(self.searchToolBar, size=(50,-1),
         style=wx.TE_PROCESS_ENTER)
      self.searchToolBar.AddControl(self.searchToolBarGotoLine)
      self.searchToolBar.SetToolTipString("Line Number")
      self.searchToolBar.AddSimpleTool(gID_MENU_GOTOLINE, "", ico.imgGotoLine.GetBitmap(),
         "Goto Line")
      self.Bind(wx.EVT_TEXT_ENTER, self.OnGotoLine, self.searchToolBarGotoLine)

      self.searchToolBar.Realize()

      self.aui_mgr.AddPane(self.searchToolBar,
         aui.AuiPaneInfo().Name("SEARCH_TOOLBAR").Caption("Search Tool Bar").ToolbarPane().Top().Gripper())

      #------------------------------------------------------------------------
      # GCODE Tool Bar
      self.gcodeToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
         agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            #aui.AUI_TB_TEXT |
            #aui.AUI_TB_HORZ_TEXT |
            #aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE
      )

      self.gcodeToolBar.SetToolBitmapSize(iconSize)

      self.gcodeToolBar.AddSimpleTool(gID_MENU_RUN, "Run", ico.imgPlay.GetBitmap(),
         "Run\tF5")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_RUN, ico.imgPlayDisabled.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_STEP, "Step", ico.imgStep.GetBitmap(),
         "Step")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_STEP, ico.imgStepDisabled.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_STOP, "Stop", ico.imgStop.GetBitmap(),
         "Stop")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_STOP, ico.imgStopDisabled.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_BREAK_TOGGLE, "Break Toggle",
         ico.imgBreak.GetBitmap(), "Breakpoint Toggle\tF9")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_BREAK_TOGGLE, ico.imgBreakDisabled.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_SET_PC, "Set PC", ico.imgMapPin.GetBitmap(),
         "Set PC")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_SET_PC, ico.imgMapPinDisabled.GetBitmap())

      self.gcodeToolBar.AddSimpleTool(gID_MENU_GOTO_PC, "Goto PC", ico.imgGotoMapPin.GetBitmap(),
         "Goto PC")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_GOTO_PC, ico.imgGotoMapPinDisabled.GetBitmap())

      self.gcodeToolBar.AddSeparator()
      self.gcodeToolBar.AddSimpleTool(gID_MENU_ABORT, "Abort", ico.imgAbort.GetBitmap(),
         "Abort")
      self.gcodeToolBar.SetToolDisabledBitmap(gID_MENU_ABORT, ico.imgAbortDisabled.GetBitmap())

      self.gcodeToolBar.Realize()

      self.aui_mgr.AddPane(self.gcodeToolBar,
         aui.AuiPaneInfo().Name("GCODE_TOOLBAR").Caption("Program Tool Bar").ToolbarPane().Top().Gripper())

      #------------------------------------------------------------------------
      # Status Tool Bar
      self.statusToolBar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
         agwStyle=aui.AUI_TB_GRIPPER |
            aui.AUI_TB_OVERFLOW |
            #aui.AUI_TB_TEXT |
            aui.AUI_TB_HORZ_TEXT |
            #aui.AUI_TB_PLAIN_BACKGROUND
            aui.AUI_TB_DEFAULT_STYLE
      )

      self.statusToolBar.SetToolBitmapSize(iconSize)

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_LINK_STATUS, "123456789", ico.imgPlugDisconnect.GetBitmap(),
         "Link Status (link/unlink)")
      self.statusToolBar.SetToolDisabledBitmap(gID_MENU_RUN, ico.imgPlugDisconnect.GetBitmap())

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_PROGRAM_STATUS, "123456", ico.imgProgram.GetBitmap(),
         "Program Status")
      self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_PROGRAM_STATUS, ico.imgProgram.GetBitmap())

      self.statusToolBar.AddSimpleTool(gID_TOOLBAR_MACHINE_STATUS, "123456", ico.imgMachine.GetBitmap(),
         "Machine Status (refresh)")
      self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_MACHINE_STATUS, ico.imgMachineDisabled.GetBitmap())

      self.statusToolBar.Realize()

      self.aui_mgr.AddPane(self.statusToolBar,
         aui.AuiPaneInfo().Name("STATUS_TOOLBAR").Caption("Status Tool Bar").ToolbarPane().Top().Gripper())

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
      self.OnStatusToolBarForceUpdate()
      self.OnRunToolBarForceUpdate()

      self.aui_mgr.Update()

   """-------------------------------------------------------------------------
   gsatMainWindow: UI Event Handlers
   -------------------------------------------------------------------------"""

   #---------------------------------------------------------------------------
   # File Menu Handlers
   #---------------------------------------------------------------------------
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
         wildcard=gc.gWILDCARD,
         style=wx.OPEN | wx.FD_FILE_MUST_EXIST
         )

      if dlgFile.ShowModal() == wx.ID_OK:
         # got file, open and present progress
         self.stateData.gcodeFileName = dlgFile.GetPath()
         self.lineNumber = 0

         # save history
         self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)
         self.fileHistory.Save(self.configFile)
         self.configFile.Flush()

         self.OnDoFileOpen(e, self.stateData.gcodeFileName)

   def OnDropDownToolBarOpen(self, e):
      if not e.IsDropDownClicked():
         self.OnFileOpen(e)
      else:
         toolbBar = e.GetEventObject()
         toolbBar.SetToolSticky(e.GetId(), True)

         historyCount =  self.fileHistory.GetCount()

         if historyCount > 0:
            # create the popup menu
            menuPopup = wx.Menu()

            for index in range(historyCount):
               m = wx.MenuItem(menuPopup, wx.ID_FILE1+index,
                  "&%d %s" % (index,self.fileHistory.GetHistoryFile(index)))
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
      self.stateData.gcodeFileName = self.fileHistory.GetHistoryFile(fileNumber)
      self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)  # move up the list
      self.fileHistory.Save(self.configFile)
      self.configFile.Flush()

      self.OnDoFileOpen(e, self.stateData.gcodeFileName)

   def OnDoFileOpen(self, e, fileName=None):
      if os.path.exists(fileName):
         self.stateData.gcodeFileName = fileName

         readOnly = self.gcText.GetReadOnly()
         self.gcText.SetReadOnly(False)
         self.gcText.LoadFile(self.stateData.gcodeFileName)
         self.gcText.SetReadOnly(readOnly)

         self.stateData.fileIsOpen = True
         self.SetTitle("%s - %s" % (os.path.basename(self.stateData.gcodeFileName), __appname__))

         self.stateData.breakPoints = set()
         self.SetPC(0)
         self.gcText.GoToPC()
         self.UpdateUI()
      else:
         dlg = wx.MessageDialog(self,
            "The file doesn't exits.\n" \
            "File: %s\n\n" \
            "Please check the path and try again." % fileName, "",
            wx.OK|wx.ICON_STOP)
         result = dlg.ShowModal()
         dlg.Destroy()

      #self.gcText.SetReadOnly(True)

   def OnFileSave(self, e):
      if not self.stateData.fileIsOpen:
         self.OnFileSaveAs(e)
      else:
         if self.saveBackupFile:
            shutil.copyfile(self.stateData.gcodeFileName,self.stateData.gcodeFileName+"~")

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
         wildcard=gc.gWILDCARD,
         style=wx.SAVE
         )

      if dlgFile.ShowModal() == wx.ID_OK:
         # got file, open and present progress
         self.stateData.gcodeFileName = dlgFile.GetPath()
         self.lineNumber = 0

         # save history
         self.fileHistory.AddFileToHistory(self.stateData.gcodeFileName)
         self.fileHistory.Save(self.configFile)
         self.configFile.Flush()

         self.gcText.SaveFile(self.stateData.gcodeFileName)

         # update title
         self.SetTitle("%s - %s" % (os.path.basename(self.stateData.gcodeFileName), __appname__))

         self.UpdateUI()

   def OnFileSaveAsUpdate(self, e):
      e.Enable(self.stateData.fileIsOpen or self.gcText.GetModify())


   #---------------------------------------------------------------------------
   # Search Menu Handlers
   #---------------------------------------------------------------------------
   def OnFind(self, e):
      searcText = self.searchToolBarFind.GetValue()
      self.gcText.FindNextText(searcText)


   def OnGotoLine(self, e):
      gotoLine = self.searchToolBarGotoLine.GetValue()
      if len(gotoLine) > 0:
         gotoLine=int(gotoLine)-1
      else:
         gotoLine = 0

      self.gcText.SetFocus()
      self.gcText.GotoLine(gotoLine)


   #---------------------------------------------------------------------------
   # View Menu Handlers
   #---------------------------------------------------------------------------
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
      #self.aui_mgr.Update()

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
      self.LoadLayoutData('/mainApp/DefaultLayout')
      self.aui_mgr.Update()

   def OnSaveDefaultLayout(self, e):
      self.SaveLayoutData('/mainApp/DefaultLayout')

   def OnResetDefaultLayout(self, e):
      self.configFile.DeleteGroup('/mainApp/DefaultLayout')
      self.LoadLayoutData('/mainApp/ResetLayout')

   def OnSettings(self, e):
      # update serial port data
      self.configData.Add('/link/PortList', self.GetSerialPortList())
      self.configData.Add('/link/BaudList', self.GetSerialBaudRateList())

      # do settings dialog
      dlg = gsatSettingsDialog(self, self.configData)

      result = dlg.ShowModal()

      if result == wx.ID_OK:
         dlg.UpdatConfigData()

         self.InitConfig()

         # re open serial port if open
         if self.stateData.serialPortIsOpen and \
            (self.stateData.serialPort != self.linkPort or self.stateData.serialBaud != self.linkBaud):

            self.SerialClose()
            self.SerialOpen(self.linkPort, self.linkBaud)

         if self.stateData.machineStatusAutoRefresh != self.machineAutoRefresh or \
            self.stateData.machineStatusAutoRefreshPeriod != self.machineAutoRefreshPeriod:

            self.AutoRefreshTimerStop()
            self.AutoRefreshTimerStart()

         self.gcText.UpdateSettings(self.configData)
         self.outputText.UpdateSettings(self.configData)
         self.machineStatusPanel.UpdateSettings(self.configData)
         self.machineJoggingPanel.UpdateSettings(self.configData)
         self.CV2Panel.UpdateSettings(self.configData)

         # save config data to file now...
         self.configData.Save(self.configFile)

      dlg.Destroy()


   #---------------------------------------------------------------------------
   # Run Menu/ToolBar Handlers
   #---------------------------------------------------------------------------
   def OnRunToolBarForceUpdate(self):
      self.OnRunUpdate()
      self.OnStepUpdate()
      self.OnStopUpdate()
      self.OnBreakToggleUpdate()
      self.OnSetPCUpdate()
      self.OnGoToPCUpdate()
      self.OnAbortUpdate()
      self.gcodeToolBar.Refresh()

   def OnRun(self, e):
      if self.progExecThread is not None:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)

         self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_RUN,
            [self.stateData.gcodeFileLines, self.stateData.programCounter, self.stateData.breakPoints]))
         self.mainWndOutQueue.join()

         self.gcText.GoToPC()
         self.stateData.swState = gc.gSTATE_RUN
         self.UpdateUI()

   def OnRunUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen and \
         (self.stateData.swState == gc.gSTATE_IDLE or \
          self.stateData.swState == gc.gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_RUN, state)

   def OnStep(self, e):
      if self.progExecThread is not None:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)

         self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_STEP,
            [self.stateData.gcodeFileLines, self.stateData.programCounter, self.stateData.breakPoints]))
         self.mainWndOutQueue.join()

         self.stateData.swState = gc.gSTATE_STEP
         self.UpdateUI()

   def OnStepUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen and \
         (self.stateData.swState == gc.gSTATE_IDLE or \
          self.stateData.swState == gc.gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_STEP, state)

   def OnStop(self, e):
      self.Stop()

   def OnStopUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen and \
         self.stateData.swState != gc.gSTATE_IDLE and \
         self.stateData.swState != gc.gSTATE_BREAK:

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
      if (self.stateData.swState == gc.gSTATE_IDLE or \
          self.stateData.swState == gc.gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_BREAK_TOGGLE, state)

   def OnBreakRemoveAll(self, e):
      self.breakPoints = set()
      self.gcText.UpdateBreakPoint(-1, False)

   def OnBreakRemoveAllUpdate(self, e):
      if (self.stateData.swState == gc.gSTATE_IDLE or \
          self.stateData.swState == gc.gSTATE_BREAK):

         e.Enable(True)
      else:
         e.Enable(False)

   def OnSetPC(self, e):
      self.SetPC()

   def OnSetPCUpdate(self, e=None):
      state = False
      if (self.stateData.swState == gc.gSTATE_IDLE or \
          self.stateData.swState == gc.gSTATE_BREAK):

         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_SET_PC, state)

   def OnGoToPC(self, e):
      self.gcText.GoToPC()

   def OnGoToPCUpdate(self, e=None):
      state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_GOTO_PC, state)

   def OnAbort(self, e):
      self.serPort.write("!\n")
      self.Stop()
      self.outputText.AppendText("> !\n")
      self.outputText.AppendText(
         "*** ABORT!!! a feed-hold command (!) has been sent to Grbl, you can\n"\
         "    use cycle-restart command (~) to continue.\n"\
         "    \n"
         "    Note: If this is not desirable please reset Grbl, by closing and opening\n"\
         "    the serial link port.\n")

   def OnAbortUpdate(self, e=None):
      state = False
      if self.stateData.serialPortIsOpen:
         state = True

      if e is not None:
         e.Enable(state)

      self.gcodeToolBar.EnableTool(gID_MENU_ABORT, state)

   #---------------------------------------------------------------------------
   # Tools Menu Handlers
   #---------------------------------------------------------------------------
   def OnToolUpdateIdle(self, e):
      state = False
      if (self.stateData.swState == gc.gSTATE_IDLE or \
          self.stateData.swState == gc.gSTATE_BREAK):
         state = True

      e.Enable(state)

   def OnInch2mm(self, e):
      dlg = wx.MessageDialog(self,
         "Your about to convert the current file from inches to metric.\n"\
         "This is an experimental feature, do you want to continue?",
         "",
         wx.OK|wx.CANCEL|wx.ICON_WARNING)

      if dlg.ShowModal() == wx.ID_OK:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)
         lines = self.ConvertInchAndmm(
            self.stateData.gcodeFileLines, in_to_mm=True, round_to=self.roundInch2mm)

         readOnly = self.gcText.GetReadOnly()
         self.gcText.SetReadOnly(False)
         self.gcText.SetText("".join(lines))
         self.gcText.SetReadOnly(readOnly)

      dlg.Destroy()

   def OnInch2mmUpdate(self, e):
      self.OnToolUpdateIdle(e)

   def Onmm2Inch(self, e):
      dlg = wx.MessageDialog(self,
         "Your about to convert the current file from metric to inches.\n"\
         "This is an experimental feature, do you want to continue?",
         "",
         wx.OK|wx.CANCEL|wx.ICON_WARNING)

      if dlg.ShowModal() == wx.ID_OK:
         rawText = self.gcText.GetText()
         self.stateData.gcodeFileLines = rawText.splitlines(True)
         lines = self.ConvertInchAndmm(
            self.stateData.gcodeFileLines, in_to_mm=False, round_to=self.roundmm2Inch)

         readOnly = self.gcText.GetReadOnly()
         self.gcText.SetReadOnly(False)
         self.gcText.SetText("".join(lines))
         self.gcText.SetReadOnly(readOnly)

      dlg.Destroy()

   def Onmm2InchUpdate(self, e):
      self.OnToolUpdateIdle(e)

   def OnG812G01(self, e):
      dlg = wx.MessageDialog(self,
         "Your about to convert the current file from G81 to G01.\n"\
         "This is an experimental feature, do you want to continue?",
         "",
         wx.OK|wx.CANCEL|wx.ICON_WARNING)

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

   #---------------------------------------------------------------------------
   # Status Menu/ToolBar Handlers
   #---------------------------------------------------------------------------
   def OnStatusToolBarForceUpdate(self):
      # Link status
      if self.stateData.serialPortIsOpen:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Linked")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, ico.imgPlugConnect.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, ico.imgPlugConnect.GetBitmap())
      else:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_LINK_STATUS, "Unlinked")
         self.statusToolBar.SetToolBitmap(gID_TOOLBAR_LINK_STATUS, ico.imgPlugDisconnect.GetBitmap())
         self.statusToolBar.SetToolDisabledBitmap(gID_TOOLBAR_LINK_STATUS, ico.imgPlugDisconnect.GetBitmap())

      # Program status
      if self.stateData.swState == gc.gSTATE_IDLE:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Idle")
      elif self.stateData.swState == gc.gSTATE_RUN:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Run")
      elif self.stateData.swState == gc.gSTATE_STEP:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Step")
      elif self.stateData.swState == gc.gSTATE_BREAK:
         self.statusToolBar.SetToolLabel(gID_TOOLBAR_PROGRAM_STATUS, "Break")

      #Machine status
      self.statusToolBar.EnableTool(gID_TOOLBAR_MACHINE_STATUS, self.stateData.serialPortIsOpen)
      self.statusToolBar.SetToolLabel(gID_TOOLBAR_MACHINE_STATUS, self.stateData.machineStatusString)

      self.statusToolBar.Refresh()

   def OnLinkStatus(self, e):
      if self.stateData.serialPortIsOpen:
         self.SerialClose()
      else:
         self.SerialOpen(self.configData.Get('/link/Port'), self.configData.Get('/link/Baud'))

   def OnGetMachineStatus(self, e):
      self.GetMachineStatus()

   #---------------------------------------------------------------------------
   # Help Menu Handlers
   #---------------------------------------------------------------------------
   def OnAbout(self, e):
      # First we create and fill the info object
      aboutDialog = wx.AboutDialogInfo()
      aboutDialog.Name = __appname__
      aboutDialog.Version = __version__
      aboutDialog.Copyright = __copyright__
      if os.name == 'nt':
         aboutDialog.Description = wordwrap(__description__, 520, wx.ClientDC(self))
      else:
         aboutDialog.Description = __description__
      aboutDialog.WebSite = ("https://github.com/duembeg/gsat", "gsat home page")
      #aboutDialog.Developers = __authors__

      aboutDialog.License = __license_str__

      # Then we call wx.AboutBox giving it that info object
      wx.AboutBox(aboutDialog)

   #---------------------------------------------------------------------------
   # Other UI Handlers
   #---------------------------------------------------------------------------
   def OnCliEnter(self, e):
      cliCommand = self.machineJoggingPanel.GetCliCommand()

      if len(cliCommand) > 0:
         serialData = "%s\n" % (cliCommand)
         self.SerialWrite(serialData)

   def OnClose(self, e):
      if self.stateData.serialPortIsOpen:
         self.SerialClose()

      if self.progExecThread is not None:
         self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_EXIT, None))
         self.mainWndOutQueue.join()

      self.machineJoggingPanel.SaveCli()
      self.configData.Save(self.configFile)
      self.aui_mgr.UnInit()

      self.Destroy()
      e.Skip()

   """-------------------------------------------------------------------------
   gsatMainWindow: General Functions
   -------------------------------------------------------------------------"""
   def AutoRefreshTimerStart(self):
      self.stateData.machineStatusAutoRefresh = self.machineAutoRefresh
      self.stateData.machineStatusAutoRefreshPeriod = self.machineAutoRefreshPeriod

      if self.stateData.machineStatusAutoRefresh:
         if self.machineAutoRefreshTimer is not None:
            self.machineAutoRefreshTimer.Stop()
         else:
            t = self.machineAutoRefreshTimer = wx.Timer(self, gID_TIMER_MACHINE_REFRESH)
            self.Bind(wx.EVT_TIMER, self.OnAutoRefreshTimerAction, t)

         self.machineAutoRefreshTimer.Start(self.stateData.machineStatusAutoRefreshPeriod)

   def AutoRefreshTimerStop(self):
      if self.machineAutoRefreshTimer is not None:
         self.machineAutoRefreshTimer.Stop()

   def OnAutoRefreshTimerAction(self, e):
      if self.stateData.grblDetected and (self.stateData.swState == gc.gSTATE_IDLE or \
         self.stateData.swState == gc.gSTATE_BREAK):

         # only do this if we are in IDLE or BREAK, it will cause probelms
         # if status requets are sent randomly wile running program
         self.SerialWrite(gc.gGRBL_CMD_GET_STATUS)

   def GetSerialPortList(self):
      spList = []

      if os.name == 'nt':
         # Scan for available ports.
         for i in range(256):
            try:
               s = serial.Serial(i)
               spList.append('COM'+str(i + 1))
               #s.close()
            except serial.SerialException, e:
                pass
            except OSError, e:
               pass
      else:
         spList = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')

      if len(spList) < 1:
         spList = ['None']

      return spList

   def GetSerialBaudRateList(self):
      sbList = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
      return sbList

   def SerialOpen(self, port, baud):
      self.serPort.baudrate = baud

      if port != "None":
         portName = port
         if os.name == 'nt':
            portName=r"\\.\%s" % (str(port))

         self.serPort.port = portName
         self.serPort.timeout=1

         try:
            #import pdb;pdb.set_trace()
            self.serPort.open()

         except serial.SerialException, e:
            dlg = wx.MessageDialog(self, e.message,
               "pySerial exception", wx.OK|wx.ICON_STOP)
            result = dlg.ShowModal()
            dlg.Destroy()
            self.serPort.close()
         except OSError, e:
            dlg = wx.MessageDialog(self, str(e),
               "OSError exception", wx.OK|wx.ICON_STOP)
            result = dlg.ShowModal()
            dlg.Destroy()
            self.serPort.close()

         if self.serPort.isOpen():
            self.progExecThread = progexec.gsatProgramExecuteThread(self, self.serPort, self.mainWndOutQueue,
               self.mainWndInQueue, self.cmdLineOptions)

            self.stateData.serialPortIsOpen = True
            self.stateData.serialPort = port
            self.stateData.serialBaud = baud
            self.AutoRefreshTimerStart()
      else:
         dlg = wx.MessageDialog(self,
            "There is no valid serial port detected.\n" \
            "connect a valid serial device and try again.",
            "",
            wx.OK|wx.ICON_STOP)
         result = dlg.ShowModal()
         dlg.Destroy()

      self.UpdateUI()

   def SerialClose(self):
      if self.progExecThread is not None:
         self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_EXIT, None))
         self.mainWndOutQueue.join()
      self.progExecThread = None
      self.serPort.close()

      self.stateData.serialPortIsOpen = False
      self.stateData.grblDetected = False
      self.AutoRefreshTimerStop()
      self.UpdateUI()

   def SerialWrite(self, serialData):
      if self.stateData.serialPortIsOpen:

         if self.progExecThread is not None:
            self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_SEND, serialData))
            self.mainWndOutQueue.join()

      elif self.cmdLineOptions.verbose:
         print "gsatMainWindow ERROR: attempt serial write with port closed!!"

   def Stop(self):
      if self.progExecThread is not None:
         self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_STOP, None))
         self.mainWndOutQueue.join()

         self.stateData.swState = gc.gSTATE_IDLE
         self.UpdateUI()

   def SetPC(self, pc=None):
      if pc is None:
         pc = self.gcText.GetCurrentLine()

      self.stateData.programCounter = pc
      self.gcText.UpdatePC(pc)

   def MachineStatusAutoRefresh(self, autoRefresh):
      self.stateData.machineStatusAutoRefresh = autoRefresh

      if self.progExecThread is not None:
         self.mainWndOutQueue.put(gc.threadEvent(gc.gEV_CMD_AUTO_STATUS, self.stateData.machineStatusAutoRefresh))
         self.mainWndOutQueue.join()

      if autoRefresh:
         self.GetMachineStatus()

   def GetMachineStatus(self):
      if self.stateData.serialPortIsOpen:
         self.SerialWrite(gc.gGRBL_CMD_GET_STATUS)

   def LoadLayoutData(self, key, update=True):
      dimesnionsData = layoutData = self.configFile.Read(key+"/Dimensions")
      if len(dimesnionsData) > 0:
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

      layoutData = self.configFile.Read(key+"/Perspective")
      if len(layoutData) > 0:
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

      self.configFile.Write(key+"/Dimensions", dimensionsData)
      self.configFile.Write(key+"/Perspective", layoutData)

   def ConvertInchAndmm(self, lines, in_to_mm=True, round_to=-1):
      ret_lienes=[]

      # itarate input lines
      for line in lines:

         # check for G20/G21 anc hange accordingly
         if in_to_mm:
            re_matches = re.findall(r"G20", line)
            if len(re_matches) > 0:
               line = line.replace("G20", "G21")
               #line = line.replace("INCHES", "MILLIMETERS")
         else:
            re_matches = re.findall(r"G21", line)
            if len(re_matches) > 0:
               line = line.replace("G21", "G20")
               #line = line.replace("MILLIMETERS", "INCHES")

         # check for G with units to convert code
         re_matches = re.findall(r"((X|Y|Z|R|F)([-+]?\d*\.\d*))", line)
         #re_matches = re.findall(r"((Z|R|F)([-+]?\d*\.\d*))", line)
         #import pdb;pdb.set_trace()
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
      ret_lienes=[]
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
         match = re.match(r"G81\s*R(\d*\.\d*)\s*Z([-+]?\d*\.\d*)\sF(\d*\.\d*)", line)
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
                  "G00 Z%s ( retract )\n" % (X,Y,Z,F,R)

         ret_lienes.append(line)

      return ret_lienes

   """-------------------------------------------------------------------------
   gsatMainWindow: Serial Port Thread Event Handlers
   Handle events coming from serial port thread
   -------------------------------------------------------------------------"""
   def OnThreadEvent(self, e):
      while (not self.mainWndInQueue.empty()):
         # get dat from queue
         te = self.mainWndInQueue.get()

         if te.event_id == gc.gEV_ABORT:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_ABORT."
            self.outputText.AppendText(te.data)
            self.progExecThread = None
            self.SerialClose()

         elif te.event_id == gc.gEV_DATA_IN:
            teData = te.data

            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_DATA_IN."
            self.outputText.AppendText("%s" % teData)


            # -----------------------------------------------------------------
            # lest try to see if we have any other good data
            # -----------------------------------------------------------------

            # Grbl version, also useful to detect grbl connect
            rematch = gReGrblVersion.match(teData)
            if rematch is not None:
               if self.stateData.swState == gc.gSTATE_RUN:
                  # something went really bad we shouldn't see this while-in
                  # RUN state
                  self.Stop()
                  dlg = wx.MessageDialog(self,
                     "Detected Grbl reset string while-in RUN.\n" \
                     "Something went terribly wrong, STOPPING!!\n", "",
                     wx.OK|wx.ICON_STOP)
                  result = dlg.ShowModal()
                  dlg.Destroy()
               else:
                  self.stateData.grblDetected = True
                  if self.stateData.machineStatusAutoRefresh:
                     self.GetMachineStatus()
               self.UpdateUI()

            # Grbl status data
            rematch = gReMachineStatus.match(teData)
            if rematch is not None:
               statusData = rematch.groups()
               if self.cmdLineOptions.vverbose:
                  print "gsatMainWindow re.status.match %s" % str(statusData)
               self.stateData.machineStatusString = statusData[0]
               self.machineStatusPanel.UpdateUI(self.stateData, statusData)
               self.machineJoggingPanel.UpdateUI(self.stateData, statusData)
               self.UpdateUI()

         elif te.event_id == gc.gEV_DATA_OUT:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_DATA_OUT."
            self.outputText.AppendText("> %s" % te.data)

         elif te.event_id == gc.gEV_PC_UPDATE:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_PC_UPDATE [%s]." % str(te.data)
            self.SetPC(te.data)

         elif te.event_id == gc.gEV_RUN_END:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_RUN_END."
            self.stateData.swState = gc.gSTATE_IDLE
            self.Refresh()
            self.UpdateUI()
            self.SetPC(0)

         elif te.event_id == gc.gEV_STEP_END:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_STEP_END."
            self.stateData.swState = gc.gSTATE_IDLE
            self.UpdateUI()

         elif te.event_id == gc.gEV_HIT_BRK_PT:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_HIT_BRK_PT."
            self.stateData.swState = gc.gSTATE_BREAK
            self.UpdateUI()

         elif te.event_id == gc.gEV_HIT_MSG:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got event gc.gEV_HIT_MSG."
            self.stateData.swState = gc.gSTATE_BREAK
            self.UpdateUI()

            self.outputText.AppendText("** MSG: %s" % te.data.strip())

            dlg = wx.MessageDialog(self, te.data.strip(), "GCODE MSG",
               wx.OK|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()

         else:
            if self.cmdLineOptions.vverbose:
               print "gsatMainWindow got UKNOWN event id[%d]" % te.event_id
            self.stateData.swState = gc.gSTATE_IDLE
            self.UpdateUI()

         # item acknowledgment
         self.mainWndInQueue.task_done()

