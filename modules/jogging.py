"""----------------------------------------------------------------------------
   jogging.py

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

import os
import re
import wx
from wx.lib import scrolledpanel as scrolled
from wx.lib.agw import floatspin as fs

import modules.config as gc


"""----------------------------------------------------------------------------
   gsatJoggingSettingsPanel:
   Machine settings.
----------------------------------------------------------------------------"""
class gsatJoggingSettingsPanel(scrolled.ScrolledPanel):
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

      text = wx.StaticText(self, label="General:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      # Add cehck box
      self.cb = wx.CheckBox(self, wx.ID_ANY, "XYZ Read Only Status")
      self.cb.SetValue(self.configData.Get('/jogging/XYZReadOnly'))
      self.cb.SetToolTip(
         wx.ToolTip("If disable the XYZ fields in jogging status are editable"))
      vBoxSizer.Add(self.cb, flag=wx.LEFT|wx.BOTTOM, border=20)

      # Custom controls
      text = wx.StaticText(self, label="Custom Controls:")
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vBoxSizer.Add(text, 0, wx.ALL, border=5)

      box1, c1CtrlArray = self.CreateCustomControlSettings(1)
      box2, c2CtrlArray = self.CreateCustomControlSettings(2)
      box3, c3CtrlArray = self.CreateCustomControlSettings(3)
      box4, c4CtrlArray = self.CreateCustomControlSettings(4)

      self.customCtrlArray = [c1CtrlArray, c2CtrlArray, c3CtrlArray, c4CtrlArray]

      vBoxSizer.Add(box1, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      vBoxSizer.Add(box2, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      vBoxSizer.Add(box3, 0, flag=wx.LEFT|wx.EXPAND, border=20)
      vBoxSizer.Add(box4, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      self.SetSizer(vBoxSizer)

   def CreateCustomControlSettings(self, cn):
      # Custom controls
      vCustomSizer = wx.BoxSizer(wx.VERTICAL)
      text = wx.StaticText(self, label="Custom Control %d:" % cn)
      font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
      text.SetFont(font)
      vCustomSizer.Add(text, 0, flag=wx.ALL, border=5)

      # Label
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      text = wx.StaticText(self, label="Label:")
      hBoxSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
      tcLabel = wx.TextCtrl(self, -1,
         self.configData.Get('/jogging/Custom%dLabel' % cn), size=(125, -1))
      hBoxSizer.Add(tcLabel, 0, flag=wx.ALIGN_CENTER_VERTICAL)

      vCustomSizer.Add(hBoxSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      # other controls
      gCustomSizer = wx.FlexGridSizer(3,3,0,0)

      text = wx.StaticText(self, label="X Settings:")
      gCustomSizer.Add(text, flag=wx.LEFT|wx.TOP|wx.ALIGN_BOTTOM, border=5)
      text = wx.StaticText(self, label="Y Settings:")
      gCustomSizer.Add(text, flag=wx.LEFT|wx.TOP|wx.ALIGN_BOTTOM, border=5)
      text = wx.StaticText(self, label="Z Settings:")
      gCustomSizer.Add(text, flag=wx.LEFT|wx.TOP|wx.ALIGN_BOTTOM, border=5)

      # check boxes
      cbXIsOffset = wx.CheckBox(self, wx.ID_ANY, "Is Offset")
      cbXIsOffset.SetValue(self.configData.Get('/jogging/Custom%dXIsOffset' % cn))
      cbXIsOffset.SetToolTip(wx.ToolTip("If set the value is treated as an offset"))
      gCustomSizer.Add(cbXIsOffset, flag=wx.ALL, border=5)

      cbYIsOffset = wx.CheckBox(self, wx.ID_ANY, "Is Offset")
      cbYIsOffset.SetValue(self.configData.Get('/jogging/Custom%dYIsOffset' % cn))
      cbYIsOffset.SetToolTip(wx.ToolTip("If set the value is treated as an offset"))
      gCustomSizer.Add(cbYIsOffset, flag=wx.ALL, border=5)

      cbZIsOffset = wx.CheckBox(self, wx.ID_ANY, "Is Offset")
      cbZIsOffset.SetValue(self.configData.Get('/jogging/Custom%dZIsOffset' % cn))
      cbZIsOffset.SetToolTip(wx.ToolTip("If set the value is treated as an offset"))
      gCustomSizer.Add(cbZIsOffset, flag=wx.ALL, border=5)

      # spin controls
      scXValue = fs.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      scXValue.SetFormat("%f")
      scXValue.SetDigits(4)
      scXValue.SetValue(self.configData.Get('/jogging/Custom%dXValue' % cn))
      gCustomSizer.Add(scXValue, flag=wx.ALL, border=5)

      scYValue = fs.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      scYValue.SetFormat("%f")
      scYValue.SetDigits(4)
      scYValue.SetValue(self.configData.Get('/jogging/Custom%dYValue' % cn))
      gCustomSizer.Add(scYValue,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)

      scZValue = fs.FloatSpin(self, -1,
         min_val=-100000, max_val=100000, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      scZValue.SetFormat("%f")
      scZValue.SetDigits(4)
      scZValue.SetValue(self.configData.Get('/jogging/Custom%dZValue' % cn))
      gCustomSizer.Add(scZValue,
         flag=wx.ALL|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, border=5)


      #st = wx.StaticText(self, wx.ID_ANY, "X")
      #hBoxSizer.Add(st, flag=wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)

      vCustomSizer.Add(gCustomSizer, 0, flag=wx.LEFT|wx.EXPAND, border=20)

      return vCustomSizer, [
         tcLabel,
         cbXIsOffset, cbYIsOffset, cbZIsOffset,
         scXValue   , scYValue   , scZValue
      ]

   def UpdatConfigData(self):
      self.configData.Set('/jogging/XYZReadOnly', self.cb.GetValue())

      for cn in range(4):
         cnp1 = cn+1
         self.configData.Set('/jogging/Custom%dLabel' % cnp1,
            self.customCtrlArray[cn][0].GetValue())

         self.configData.Set('/jogging/Custom%dXIsOffset' % cnp1,
            self.customCtrlArray[cn][1].GetValue())
         self.configData.Set('/jogging/Custom%dYIsOffset' % cnp1,
            self.customCtrlArray[cn][2].GetValue())
         self.configData.Set('/jogging/Custom%dZIsOffset' % cnp1,
            self.customCtrlArray[cn][3].GetValue())

         self.configData.Set('/jogging/Custom%dXValue' % cnp1,
            self.customCtrlArray[cn][4].GetValue())
         self.configData.Set('/jogging/Custom%dYValue' % cnp1,
            self.customCtrlArray[cn][5].GetValue())
         self.configData.Set('/jogging/Custom%dZValue' % cnp1,
            self.customCtrlArray[cn][6].GetValue())

"""----------------------------------------------------------------------------
   gsatCliSettingsPanel:
   CLI settings.
----------------------------------------------------------------------------"""
class gsatCliSettingsPanel(scrolled.ScrolledPanel):
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
   gsatJoggingPanel:
   Jog controls for the machine as well as custom user controls.
----------------------------------------------------------------------------"""
class gsatJoggingPanel(wx.ScrolledWindow):
   def __init__(self, parent, config_data, state_data, **args):
      wx.ScrolledWindow.__init__(self, parent, **args)

      self.mainWindow = parent

      self.configData = config_data
      self.stateData = state_data

      self.useMachineWorkPosition = False

      self.memoX = gc.gZeroString
      self.memoY = gc.gZeroString
      self.memoZ = gc.gZeroString

      self.cliCommand = ""
      self.cliIndex = 0

      self.InitConfig()
      self.InitUI()
      width,height = self.GetSizeTuple()
      scroll_unit = 10
      self.SetScrollbars(scroll_unit,scroll_unit, width/scroll_unit, height/scroll_unit)

      self.UpdateSettings(self.configData)
      #self.spinCtrl.SetFocus()
      self.LoadCli()

   def InitConfig(self):
      # jogging data
      self.configXYZReadOnly      = self.configData.Get('/jogging/XYZReadOnly')

      self.configCustom1Label     = self.configData.Get('/jogging/Custom1Label')
      self.configCustom1XIsOffset = self.configData.Get('/jogging/Custom1XIsOffset')
      self.configCustom1XValue    = self.configData.Get('/jogging/Custom1XValue')
      self.configCustom1YIsOffset = self.configData.Get('/jogging/Custom1YIsOffset')
      self.configCustom1YValue    = self.configData.Get('/jogging/Custom1YValue')
      self.configCustom1ZIsOffset = self.configData.Get('/jogging/Custom1ZIsOffset')
      self.configCustom1ZValue    = self.configData.Get('/jogging/Custom1ZValue')

      self.configCustom2Label     = self.configData.Get('/jogging/Custom2Label')
      self.configCustom2XIsOffset = self.configData.Get('/jogging/Custom2XIsOffset')
      self.configCustom2XValue    = self.configData.Get('/jogging/Custom2XValue')
      self.configCustom2YIsOffset = self.configData.Get('/jogging/Custom2YIsOffset')
      self.configCustom2YValue    = self.configData.Get('/jogging/Custom2YValue')
      self.configCustom2ZIsOffset = self.configData.Get('/jogging/Custom2ZIsOffset')
      self.configCustom2ZValue    = self.configData.Get('/jogging/Custom2ZValue')

      self.configCustom3Label     = self.configData.Get('/jogging/Custom3Label')
      self.configCustom3XIsOffset = self.configData.Get('/jogging/Custom3XIsOffset')
      self.configCustom3XValue    = self.configData.Get('/jogging/Custom3XValue')
      self.configCustom3YIsOffset = self.configData.Get('/jogging/Custom3YIsOffset')
      self.configCustom3YValue    = self.configData.Get('/jogging/Custom3YValue')
      self.configCustom3ZIsOffset = self.configData.Get('/jogging/Custom3ZIsOffset')
      self.configCustom3ZValue    = self.configData.Get('/jogging/Custom3ZValue')

      self.configCustom4Label     = self.configData.Get('/jogging/Custom4Label')
      self.configCustom4XIsOffset = self.configData.Get('/jogging/Custom4XIsOffset')
      self.configCustom4XValue    = self.configData.Get('/jogging/Custom4XValue')
      self.configCustom4YIsOffset = self.configData.Get('/jogging/Custom4YIsOffset')
      self.configCustom4YValue    = self.configData.Get('/jogging/Custom4YValue')
      self.configCustom4ZIsOffset = self.configData.Get('/jogging/Custom4ZIsOffset')
      self.configCustom4ZValue    = self.configData.Get('/jogging/Custom4ZValue')

      # cli data
      self.cliSaveCmdHistory      = self.configData.Get('/cli/SaveCmdHistory')
      self.cliCmdMaxHistory       = self.configData.Get('/cli/CmdMaxHistory')
      self.cliCmdHistory          = self.configData.Get('/cli/CmdHistory')


   def UpdateSettings(self, config_data):
      self.configData = config_data
      self.InitConfig()

      if self.configXYZReadOnly:
         self.jX.SetEditable(False)
         self.jX.SetBackgroundColour(gc.gReadOnlyBkColor)
         self.jY.SetEditable(False)
         self.jY.SetBackgroundColour(gc.gReadOnlyBkColor)
         self.jZ.SetEditable(False)
         self.jZ.SetBackgroundColour(gc.gReadOnlyBkColor)
      else:
         self.jX.SetEditable(True)
         self.jX.SetBackgroundColour(gc.gEdityBkColor)
         self.jY.SetEditable(True)
         self.jY.SetBackgroundColour(gc.gEdityBkColor)
         self.jZ.SetEditable(True)
         self.jZ.SetBackgroundColour(gc.gEdityBkColor)

      self.custom1Button.SetLabel(self.configCustom1Label)
      self.custom2Button.SetLabel(self.configCustom2Label)
      self.custom3Button.SetLabel(self.configCustom3Label)
      self.custom4Button.SetLabel(self.configCustom4Label)

   def InitUI(self):
      vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)
      hPanelBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      # Add CLI
      self.cliComboBox = wx.combo.BitmapComboBox(self, style=wx.CB_DROPDOWN|wx.TE_PROCESS_ENTER|wx.WANTS_CHARS)
      self.cliComboBox.SetToolTip(wx.ToolTip("Command Line Interface (CLI)"))
      self.cliComboBox.Bind(wx.EVT_TEXT_ENTER, self.OnCliEnter)
      #self.cliComboBox.Bind(wx.EVT_CHAR, self.OnCliChar)
      self.cliComboBox.Bind(wx.EVT_KEY_DOWN, self.OnCliKeyDown)
      #self.cliComboBox.Bind(wx.EVT_KEY_UP, self.OnCliKeyUp)
      vPanelBoxSizer.Add(self.cliComboBox, 0, wx.EXPAND|wx.ALL, border=1)


      # Add Controls ----------------------------------------------------------
      joggingControls = self.CreateJoggingControls()
      vPanelBoxSizer.Add(joggingControls, 0, flag=wx.ALL|wx.EXPAND, border=5)

      positionStatusControls = self.CreatePositionStatusControls()
      hPanelBoxSizer.Add(positionStatusControls, 0, flag=wx.EXPAND)

      gotoControls = self.CreateGotoControls()
      hPanelBoxSizer.Add(gotoControls, 0, flag=wx.LEFT|wx.EXPAND, border=10)

      utilControls = self.CreateUtilControls()
      hPanelBoxSizer.Add(utilControls, 0, flag=wx.LEFT|wx.EXPAND, border=10)

      vPanelBoxSizer.Add(hPanelBoxSizer, 1, flag=wx.ALL|wx.EXPAND, border=5)

      # Finish up init UI
      self.SetSizer(vPanelBoxSizer)
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
      if statusData is not None and self.useMachineWorkPosition:
         self.jX.SetValue(statusData[4])
         self.jY.SetValue(statusData[5])
         self.jZ.SetValue(statusData[6])

      if stateData.serialPortIsOpen and not stateData.swState == gc.gSTATE_RUN:
         self.resettoZeroPositionButton.Enable()
         self.resettoCurrentPositionButton.Enable()
         self.goZeroButton.Enable()
         self.goToCurrentPositionButton.Enable()
         self.goHomeButton.Enable()
         self.positiveXButton.Enable()
         self.negativeXButton.Enable()
         self.positiveYButton.Enable()
         self.negativeYButton.Enable()
         self.positiveZButton.Enable()
         self.negativeZButton.Enable()
         self.spindleOnButton.Enable()
         self.spindleOffButton.Enable()
         self.custom1Button.Enable()
         self.custom2Button.Enable()
         self.custom3Button.Enable()
         self.custom4Button.Enable()
         self.cliComboBox.Enable()
      else:
         self.resettoZeroPositionButton.Disable()
         self.resettoCurrentPositionButton.Disable()
         self.goZeroButton.Disable()
         self.goToCurrentPositionButton.Disable()
         self.goHomeButton.Disable()
         self.positiveXButton.Disable()
         self.negativeXButton.Disable()
         self.positiveYButton.Disable()
         self.negativeYButton.Disable()
         self.positiveZButton.Disable()
         self.negativeZButton.Disable()
         self.spindleOnButton.Disable()
         self.spindleOffButton.Disable()
         self.custom1Button.Disable()
         self.custom2Button.Disable()
         self.custom3Button.Disable()
         self.custom4Button.Disable()
         self.cliComboBox.Disable()


   def CreateJoggingControls(self):
      # Add Buttons -----------------------------------------------------------
      hButtonBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
      vYButtonBoxSizer = wx.BoxSizer(wx.VERTICAL)
      vZButtonBoxSizer = wx.BoxSizer(wx.VERTICAL)
      vOtherButtonBoxSizer = wx.BoxSizer(wx.VERTICAL)

      buttonSize = (50,50)

      self.negativeXButton = wx.Button(self, label="-X", size=buttonSize)
      self.negativeXButton.SetToolTip(
         wx.ToolTip("Move X axis on negative direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnXNeg, self.negativeXButton)
      hButtonBoxSizer.Add(self.negativeXButton, flag=wx.ALIGN_CENTER_VERTICAL)

      self.positiveYButton = wx.Button(self, label="+Y", size=buttonSize)
      self.positiveYButton.SetToolTip(
         wx.ToolTip("Move Y axis on positive direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnYPos, self.positiveYButton)
      vYButtonBoxSizer.Add(self.positiveYButton)

      self.negativeYButton = wx.Button(self, label="-Y", size=buttonSize)
      self.negativeYButton.SetToolTip(
         wx.ToolTip("Move Y axis on negative direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnYNeg, self.negativeYButton)
      vYButtonBoxSizer.Add(self.negativeYButton)
      hButtonBoxSizer.Add(vYButtonBoxSizer, flag=wx.ALIGN_CENTER_VERTICAL)

      self.positiveXButton = wx.Button(self, label="+X", size=buttonSize)
      self.positiveXButton.SetToolTip(
         wx.ToolTip("Move X axis on positive direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnXPos, self.positiveXButton)
      hButtonBoxSizer.Add(self.positiveXButton, flag=wx.ALIGN_CENTER_VERTICAL)

      spacerText = wx.StaticText(self, label="   ")
      hButtonBoxSizer.Add(spacerText, flag=wx.ALIGN_CENTER_VERTICAL)

      self.positiveZButton = wx.Button(self, label="+Z", size=buttonSize)
      self.positiveZButton.SetToolTip(
         wx.ToolTip("Move Z axis on positive direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnZPos, self.positiveZButton)
      vZButtonBoxSizer.Add(self.positiveZButton)

      self.negativeZButton = wx.Button(self, label="-Z", size=buttonSize)
      self.negativeZButton.SetToolTip(
         wx.ToolTip("Move Z axis on negative direction by step size"))
      self.Bind(wx.EVT_BUTTON, self.OnZNeg, self.negativeZButton)
      vZButtonBoxSizer.Add(self.negativeZButton)
      hButtonBoxSizer.Add(vZButtonBoxSizer, flag=wx.ALIGN_CENTER_VERTICAL)

      spacerText = wx.StaticText(self, label="     ")
      hButtonBoxSizer.Add(spacerText, flag=wx.ALIGN_CENTER_VERTICAL)

      self.spindleOnButton = wx.Button(self, label="SP ON", size=(60,50))
      self.spindleOnButton.SetToolTip(wx.ToolTip("Spindle ON"))
      self.Bind(wx.EVT_BUTTON, self.OnSpindleOn, self.spindleOnButton)
      vOtherButtonBoxSizer.Add(self.spindleOnButton)

      self.spindleOffButton = wx.Button(self, label="SP OFF", size=(60,50))
      self.spindleOffButton.SetToolTip(wx.ToolTip("Spindle OFF"))
      self.Bind(wx.EVT_BUTTON, self.OnSpindleOff, self.spindleOffButton)
      vOtherButtonBoxSizer.Add(self.spindleOffButton)

      hButtonBoxSizer.Add(vOtherButtonBoxSizer, flag=wx.ALIGN_BOTTOM)

      return hButtonBoxSizer

   def CreatePositionStatusControls(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      # add status controls
      spinText = wx.StaticText(self, -1, "Step Size:  ")
      vBoxSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      self.spinCtrl = fs.FloatSpin(self, -1,
         min_val=0, max_val=99999, increment=0.10, value=1.0,
         agwStyle=fs.FS_LEFT)
      self.spinCtrl.SetFormat("%f")
      self.spinCtrl.SetDigits(4)

      vBoxSizer.Add(self.spinCtrl, 0,
         flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, border=5)

      spinText = wx.StaticText(self, -1, "Jogging Status:  ")
      vBoxSizer.Add(spinText, 0, flag=wx.ALIGN_CENTER_VERTICAL)

      flexGridSizer = wx.FlexGridSizer(4,2)
      vBoxSizer.Add(flexGridSizer,0 , flag=wx.ALL|wx.EXPAND, border=5)

      # Add X pos
      xText = wx.StaticText(self, label="X:")
      self.jX = wx.TextCtrl(self, value=gc.gZeroString)
      flexGridSizer.Add(xText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jX, 1, flag=wx.EXPAND)

      # Add Y Pos
      yText = wx.StaticText(self, label="Y:")
      self.jY = wx.TextCtrl(self, value=gc.gZeroString)
      flexGridSizer.Add(yText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jY, 1, flag=wx.EXPAND)

      # Add Z Pos
      zText = wx.StaticText(self, label="Z:")
      self.jZ = wx.TextCtrl(self, value=gc.gZeroString)
      flexGridSizer.Add(zText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jZ, 1, flag=wx.EXPAND)

      # Add Spindle status
      spindleText = wx.StaticText(self, label="SP:")
      self.jSpindle = wx.TextCtrl(self, value=gc.gOffString, style=wx.TE_READONLY)
      self.jSpindle.SetBackgroundColour(gc.gReadOnlyBkColor)
      flexGridSizer.Add(spindleText, 0, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
      flexGridSizer.Add(self.jSpindle, 1, flag=wx.EXPAND)

      # Add Checkbox for sync with work position
      self.useWorkPosCheckBox = wx.CheckBox (self, label="Use Work Pos")
      self.useWorkPosCheckBox.SetToolTip(
         wx.ToolTip("Use Machine status to update Jogging position (experimental)"))
      self.Bind(wx.EVT_CHECKBOX, self.OnUseMachineWorkPosition, self.useWorkPosCheckBox)
      vBoxSizer.Add(self.useWorkPosCheckBox)

      return vBoxSizer

   def CreateGotoControls(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      spinText = wx.StaticText(self, -1, "")
      vBoxSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      # add Buttons
      self.resettoZeroPositionButton = wx.Button(self, label="Reset to Zero")
      self.resettoZeroPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToZeroPos, self.resettoZeroPositionButton)
      vBoxSizer.Add(self.resettoZeroPositionButton, flag=wx.TOP|wx.EXPAND, border=5)

      self.goZeroButton = wx.Button(self, label="Goto Zero")
      self.goZeroButton.SetToolTip(
         wx.ToolTip("Move to Machine Working position X0, Y0, Z0"))
      self.Bind(wx.EVT_BUTTON, self.OnGoZero, self.goZeroButton)
      vBoxSizer.Add(self.goZeroButton, flag=wx.EXPAND)

      self.resettoCurrentPositionButton = wx.Button(self, label="Reset to Jog")
      self.resettoCurrentPositionButton.SetToolTip(
         wx.ToolTip("Reset machine work position to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnResetToCurrentPos, self.resettoCurrentPositionButton)
      vBoxSizer.Add(self.resettoCurrentPositionButton, flag=wx.EXPAND)

      self.goToCurrentPositionButton = wx.Button(self, label="Goto Jog")
      self.goToCurrentPositionButton.SetToolTip(
         wx.ToolTip("Move to to current jogging values"))
      self.Bind(wx.EVT_BUTTON, self.OnGoPos, self.goToCurrentPositionButton)
      vBoxSizer.Add(self.goToCurrentPositionButton, flag=wx.EXPAND)

      self.goHomeButton = wx.Button(self, label="Goto Home")
      self.goHomeButton.SetToolTip(
         wx.ToolTip("Execute Machine Homing Cycle"))
      self.Bind(wx.EVT_BUTTON, self.OnGoHome, self.goHomeButton)
      vBoxSizer.Add(self.goHomeButton, flag=wx.EXPAND)


      return vBoxSizer

   def CreateUtilControls(self):
      vBoxSizer = wx.BoxSizer(wx.VERTICAL)

      spinText = wx.StaticText(self, -1, "")
      vBoxSizer.Add(spinText,0 , flag=wx.ALIGN_CENTER_VERTICAL)

      # add position stack
      hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

      self.pushStackButton = wx.Button(self, label="+", style=wx.BU_EXACTFIT)
      self.pushStackButton.SetToolTip(
         wx.ToolTip("Adds current jog position values to jog memory stack"))
      self.Bind(wx.EVT_BUTTON, self.OnPushStack, self.pushStackButton)
      hBoxSizer.Add(self.pushStackButton, 1, flag=wx.EXPAND)

      self.jogMemoryStackComboBox = wx.combo.BitmapComboBox(self, -1, value="", size=(10,-1),
         choices=[], style=wx.CB_READONLY|wx.CB_DROPDOWN)
      self.jogMemoryStackComboBox.SetToolTip(wx.ToolTip("jog memory stack"))
      self.Bind(wx.EVT_COMBOBOX, self.OnPopStack, self.jogMemoryStackComboBox)
      hBoxSizer.Add(self.jogMemoryStackComboBox, 1, flag=wx.EXPAND)

      vBoxSizer.Add(hBoxSizer, flag=wx.TOP|wx.EXPAND, border=5)

      # add custom buttons
      self.custom1Button = wx.Button(self, label=self.configCustom1Label)
      self.custom1Button.SetToolTip(wx.ToolTip("Move to pre-defined position (1)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom1Button, self.custom1Button)
      vBoxSizer.Add(self.custom1Button, flag=wx.EXPAND)

      self.custom2Button = wx.Button(self, label=self.configCustom2Label)
      self.custom2Button.SetToolTip(wx.ToolTip("Move to pre-defined position (2)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom2Button, self.custom2Button)
      vBoxSizer.Add(self.custom2Button, flag=wx.EXPAND)

      self.custom3Button = wx.Button(self, label=self.configCustom3Label)
      self.custom3Button.SetToolTip(wx.ToolTip("Move to pre-defined position (3)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom3Button, self.custom3Button)
      vBoxSizer.Add(self.custom3Button, flag=wx.EXPAND)

      self.custom4Button = wx.Button(self, label=self.configCustom4Label)
      self.custom4Button.SetToolTip(wx.ToolTip("Move to pre-defined position (4)"))
      self.Bind(wx.EVT_BUTTON, self.OnCustom4Button, self.custom4Button)
      vBoxSizer.Add(self.custom4Button, flag=wx.EXPAND)

      return vBoxSizer

   def AxisJog(self, staticControl, cmdString, opAdd):
      fAxisPos = float(staticControl.GetValue())

      if opAdd:
         fAxisPos += self.spinCtrl.GetValue()
      else:
         fAxisPos -= self.spinCtrl.GetValue()

      fAxisStrPos = gc.gNumberFormatString % (fAxisPos)
      staticControl.SetValue(fAxisStrPos)
      self.mainWindow.SerialWrite(cmdString.replace("<VAL>",fAxisStrPos))

   def OnXPos(self, e):
      self.AxisJog(self.jX, gc.gGRBL_CMD_JOG_X, opAdd=True)

   def OnXNeg(self, e):
      self.AxisJog(self.jX, gc.gGRBL_CMD_JOG_X, opAdd=False)

   def OnYPos(self, e):
      self.AxisJog(self.jY, gc.gGRBL_CMD_JOG_Y, opAdd=True)

   def OnYNeg(self, e):
      self.AxisJog(self.jY, gc.gGRBL_CMD_JOG_Y, opAdd=False)

   def OnZPos(self, e):
      self.AxisJog(self.jZ, gc.gGRBL_CMD_JOG_Z, opAdd=True)

   def OnZNeg(self, e):
      self.AxisJog(self.jZ, gc.gGRBL_CMD_JOG_Z, opAdd=False)

   def OnSpindleOn(self, e):
      self.jSpindle.SetValue(gc.gOnString)
      self.mainWindow.SerialWrite(gc.gGRBL_CMD_SPINDLE_ON)

   def OnSpindleOff(self, e):
      self.jSpindle.SetValue(gc.gOffString)
      self.mainWindow.SerialWrite(gc.gGRBL_CMD_SPINDLE_OFF)

   def OnUseMachineWorkPosition(self, e):
      self.useMachineWorkPosition = e.IsChecked()

   def OnResetToZeroPos(self, e):
      self.jX.SetValue(gc.gZeroString)
      self.jY.SetValue(gc.gZeroString)
      self.jZ.SetValue(gc.gZeroString)
      self.mainWindow.SerialWrite(gc.gGRBL_CMD_RESET_TO_ZERO_POS)

   def OnResetToCurrentPos(self, e):
      rstCmd = gc.gGRBL_CMD_RESET_TO_VAL_POS
      rstCmd = rstCmd.replace("<XVAL>", self.jX.GetValue())
      rstCmd = rstCmd.replace("<YVAL>", self.jY.GetValue())
      rstCmd = rstCmd.replace("<ZVAL>", self.jZ.GetValue())
      self.mainWindow.SerialWrite(rstCmd)

   def OnGoZero(self, e):
      self.jX.SetValue(gc.gZeroString)
      self.jY.SetValue(gc.gZeroString)
      self.jZ.SetValue(gc.gZeroString)
      self.mainWindow.SerialWrite(gc.gGRBL_CMD_GO_ZERO)

   def OnGoPos(self, e):
      goPosCmd = gc.gGRBL_CMD_GO_POS
      goPosCmd = goPosCmd.replace("<XVAL>", self.jX.GetValue())
      goPosCmd = goPosCmd.replace("<YVAL>", self.jY.GetValue())
      goPosCmd = goPosCmd.replace("<ZVAL>", self.jZ.GetValue())
      self.mainWindow.SerialWrite(goPosCmd)

   def OnGoHome(self, e):
      self.mainWindow.SerialWrite(gc.gGRBL_CMD_EXE_HOME_CYCLE)

   def OnPushStack(self, e):
      xVal = self.jX.GetValue()
      yVal = self.jY.GetValue()
      zVal = self.jZ.GetValue()

      self.jogMemoryStackComboBox.Append("X%s,Y%s,Z%s" % (xVal, yVal, zVal))

   def OnPopStack(self, e):
      strXYZ = self.jogMemoryStackComboBox.GetValue()
      self.jX.SetValue(re.search("X(\S+),Y", strXYZ).group(1))
      self.jY.SetValue(re.search("Y(\S+),Z", strXYZ).group(1))
      self.jZ.SetValue(re.search("Z(\S+)", strXYZ).group(1))

   def OnCustomButton(self, xo, xv, yo, yv, zo, zv):
      fXPos = float(self.jX.GetValue())
      fYPos = float(self.jY.GetValue())
      fZPos = float(self.jZ.GetValue())
      fXVal = float(xv)
      fYVal = float(yv)
      fZVal = float(zv)

      fXnp = fXVal
      if xo:
         fXnp = fXPos + fXVal

      fYnp = fYVal
      if yo:
         fYnp = fYPos + fYVal

      fZnp = fZVal
      if zo:
         fZnp = fZPos + fZVal

      self.jX.SetValue(str(fXnp))
      self.jY.SetValue(str(fYnp))
      self.jZ.SetValue(str(fZnp))

      goPosCmd = gc.gGRBL_CMD_GO_POS
      goPosCmd = goPosCmd.replace("<XVAL>", str(fXnp))
      goPosCmd = goPosCmd.replace("<YVAL>", str(fYnp))
      goPosCmd = goPosCmd.replace("<ZVAL>", str(fZnp))
      self.mainWindow.SerialWrite(goPosCmd)


   def OnCustom1Button(self, e):
      self.OnCustomButton(
         self.configCustom1XIsOffset, self.configCustom1XValue,
         self.configCustom1YIsOffset, self.configCustom1YValue,
         self.configCustom1ZIsOffset, self.configCustom1ZValue
      )

   def OnCustom2Button(self, e):
      self.OnCustomButton(
         self.configCustom2XIsOffset, self.configCustom2XValue,
         self.configCustom2YIsOffset, self.configCustom2YValue,
         self.configCustom2ZIsOffset, self.configCustom2ZValue
      )

   def OnCustom3Button(self, e):
      self.OnCustomButton(
         self.configCustom3XIsOffset, self.configCustom3XValue,
         self.configCustom3YIsOffset, self.configCustom3YValue,
         self.configCustom3ZIsOffset, self.configCustom3ZValue
      )

   def OnCustom4Button(self, e):
      self.OnCustomButton(
         self.configCustom4XIsOffset, self.configCustom4XValue,
         self.configCustom4YIsOffset, self.configCustom4YValue,
         self.configCustom4ZIsOffset, self.configCustom4ZValue
      )

   def OnRefresh(self, e):
      pass

   def GetCliCommand(self):
      return self.cliCommand

   def OnCliEnter(self, e):
      cliCommand = self.cliComboBox.GetValue()

      if cliCommand != self.cliCommand:
         if self.cliComboBox.GetCount() > self.cliCmdMaxHistory:
            self.cliComboBox.Delete(0)

         self.cliCommand = cliCommand
         self.cliComboBox.Append(self.cliCommand)

      self.cliComboBox.SetValue("")

      self.cliIndex = self.cliComboBox.GetCount()
      e.Skip()

   def OnCliKeyDown(self, e):
      keyCode = e.GetKeyCode()
      cliItems = self.cliComboBox.GetItems()

      if wx.WXK_UP == keyCode or wx.WXK_NUMPAD_UP == keyCode:
         if  self.cliIndex > 0:
            self.cliIndex = self.cliIndex - 1
            self.cliComboBox.SetValue(cliItems[self.cliIndex])
      elif wx.WXK_DOWN == keyCode or wx.WXK_NUMPAD_DOWN == keyCode:
         if  len(cliItems) > self.cliIndex + 1:
            self.cliIndex = self.cliIndex + 1
            self.cliComboBox.SetValue(cliItems[self.cliIndex])
      else:
         e.Skip()

   def LoadCli(self):
      # read cmd hsitory
      configData = self.cliCmdHistory
      if len(configData) > 0:
         cliCommandHistory = configData.split("|")
         for cmd in cliCommandHistory:
            cmd = cmd.strip()
            if len(cmd) > 0:
               self.cliComboBox.Append(cmd.strip())

         self.cliCommand = cliCommandHistory[len(cliCommandHistory) - 1]
         self.cliIndex = self.cliComboBox.GetCount()

   def SaveCli(self):
      # write cmd history
      if self.cliSaveCmdHistory:
         cliCmdHistory = self.cliComboBox.GetItems()
         if len(cliCmdHistory) > 0:
            cliCmdHistory =  "|".join(cliCmdHistory)
            self.configData.Set('/cli/CmdHistory', cliCmdHistory)
