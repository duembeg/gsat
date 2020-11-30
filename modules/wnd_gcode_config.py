"""----------------------------------------------------------------------------
   wnd_gcode_config.py

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

import re
import wx
from wx import stc as stc
from wx.lib import scrolledpanel as scrolled
from wx.lib import colourselect as csel

import modules.wnd_output_config as outc

import images.icons as ico

class Factory():
    """ Factory class to init config page
    """

    @staticmethod
    def GetIcon():
        return ico.imgProgram.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatGcodeSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Program")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatGcodeSettingsPanel(outc.gsatOutputSettingsPanel):
    """ Program settings
    """

    def __init__(self, parent, config_data, key="code"):
        super(gsatGcodeSettingsPanel, self).__init__(parent, config_data, key)