"""----------------------------------------------------------------------------
   wnd_compvision_config.py

   Copyright (C) 2013 Wilhelm Duembeg

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

import wx
from wx.lib import scrolledpanel as scrolled

import images.icons as ico


class Factory():
    """
    Factory class to init config page

    """

    @staticmethod
    def GetIcon():
        return ico.imgEye.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatCV2SettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "OpenCV2")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatCV2SettingsPanel(scrolled.ScrolledPanel):
    """
    CV2 settings

    """

    def __init__(self, parent, config_data, **args):
        super(gsatCV2SettingsPanel, self).__init__(parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()
        # self.FitInside()

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)
        flexGridSizer = wx.FlexGridSizer(7, 2, 0, 0)

        # Add enable check box
        # , style=wx.ALIGN_RIGHT)
        self.cbEnable = wx.CheckBox(self, wx.ID_ANY, "Enable CV2")
        self.cbEnable.SetValue(self.configData.get('/cv2/Enable'))
        flexGridSizer.Add(
            self.cbEnable, flag=wx.ALL | wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            border=5
        )

        st = wx.StaticText(self, wx.ID_ANY, "")
        flexGridSizer.Add(st, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        # Add crosshair check box
        # , style=wx.ALIGN_RIGHT)
        self.cbCrosshair = wx.CheckBox(self, wx.ID_ANY, "Enable Crosshair")
        self.cbCrosshair.SetValue(self.configData.get('/cv2/Crosshair'))
        flexGridSizer.Add(
            self.cbCrosshair, flag=wx.ALL | wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            border=5
        )

        st = wx.StaticText(self, wx.ID_ANY, "")
        flexGridSizer.Add(st, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        # Add spin ctrl for capture device
        self.scDevice = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.scDevice.SetRange(-1, 100)
        self.scDevice.SetValue(self.configData.get('/cv2/CaptureDevice'))
        flexGridSizer.Add(
            self.scDevice, flag=wx.ALL | wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            border=5
        )

        st = wx.StaticText(self, wx.ID_ANY, "CV2 Capture Device")
        flexGridSizer.Add(st, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        # Add spin ctrl for capture period
        self.scPeriod = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.scPeriod.SetRange(1, 1000000)
        self.scPeriod.SetValue(self.configData.get('/cv2/CapturePeriod'))
        self.scPeriod.SetToolTip(
            wx.ToolTip(
                "NOTE: UI may become unresponsive if this value is too "
                "short\nSuggested value 100ms or grater"
            )
        )

        flexGridSizer.Add(
            self.scPeriod, flag=wx.ALL | wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            border=5
        )

        st = wx.StaticText(
            self, wx.ID_ANY, "CV2 Capture Period (milliseconds)")
        flexGridSizer.Add(st, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        # Add spin ctrl for capture width
        self.scWidth = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.scWidth.SetRange(1, 10000)
        self.scWidth.SetValue(self.configData.get('/cv2/CaptureWidth'))
        flexGridSizer.Add(
            self.scWidth, flag=wx.ALL | wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            border=5
        )

        st = wx.StaticText(self, wx.ID_ANY, "CV2 Capture Width")
        flexGridSizer.Add(st, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        # Add spin ctrl for capture height
        self.scHeight = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.scHeight.SetRange(1, 10000)
        self.scHeight.SetValue(self.configData.get('/cv2/CaptureHeight'))
        flexGridSizer.Add(
            self.scHeight, flag=wx.ALL | wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            border=5
        )

        st = wx.StaticText(self, wx.ID_ANY, "CV2 Capture Height")
        flexGridSizer.Add(st, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        vBoxSizer.Add(flexGridSizer, 0, flag=wx.ALL | wx.EXPAND, border=20)
        self.SetSizer(vBoxSizer)

    def UpdateConfigData(self):
        self.configData.set('/cv2/Enable', self.cbEnable.GetValue())
        self.configData.set('/cv2/Crosshair', self.cbCrosshair.GetValue())
        self.configData.set('/cv2/CaptureDevice', self.scDevice.GetValue())
        self.configData.set('/cv2/CapturePeriod', self.scPeriod.GetValue())
        self.configData.set('/cv2/CaptureWidth', self.scWidth.GetValue())
        self.configData.set('/cv2/CaptureHeight', self.scHeight.GetValue())
