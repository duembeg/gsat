"""----------------------------------------------------------------------------
    wnd_console_config.py

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
import re
import wx
from wx.lib import scrolledpanel as scrolled
from wx.lib import colourselect as csel

import images.icons as ico


def hex_to_rgb(hex_color):
    m = re.match(r'^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$', hex_color, re.IGNORECASE)
    if m:
        return (int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16))
    else:
        return (0, 0, 0)


class Factory():
    """
    Factory class to init config page

    """

    @staticmethod
    def GetIcon():
        return ico.imgCli.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatOutputSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Console")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatOutputSettingsPanel(scrolled.ScrolledPanel):
    """
    Output settings

    """

    def __init__(self, parent, config_data, key="console"):
        super(gsatOutputSettingsPanel, self).__init__(parent, style=wx.TAB_TRAVERSAL | wx.NO_BORDER)

        self.configData = config_data
        self.key = key

        self.InitUI()
        self.SetAutoLayout(True)
        self.SetupScrolling()

    def InitUI(self):
        vBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # Scrolling section
        text = wx.StaticText(self, label="Scrolling")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, 0, wx.ALL, border=5)

        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)

        spText = wx.StaticText(self, label="Auto Scroll")
        hBoxSizer.Add(spText, 0, flag=wx.ALIGN_CENTER_VERTICAL)

        asList = ["Never", "Always", "On Kill Focus"]

        self.asComboBox = wx.ComboBox(
            self, -1, value=asList[self.configData.get(f"/{self.key}/AutoScroll")],
            choices=asList, style=wx.CB_READONLY)
        hBoxSizer.Add(self.asComboBox, 0, flag=wx.ALL | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, wx.LEFT | wx.BOTTOM | wx.EXPAND | wx.ALIGN_LEFT, border=20)

        # General Controls
        text = wx.StaticText(self, label="General")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, 0, wx.ALL, border=5)

        self.fontSelect = wx.FontPickerCtrl(self, size=(300, -1))
        vBoxSizer.Add(self.fontSelect, 0, wx.LEFT | wx.ALIGN_LEFT, border=20)
        font = wx.Font(
            self.configData.get(f"/{self.key}/FontSize"), wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0,
            self.configData.get(f"/{self.key}/FontFace"))

        font_style_str = self.configData.get(f"/{self.key}/FontStyle")

        if "bold" in font_style_str:
            font.MakeBold()

        if "italic" in font_style_str:
            font.MakeItalic()

        self.fontSelect.SetSelectedFont(font)

        vBoxSizer.Add((10, 10), 0, wx.ALL, border=1)

        gBoxSizer = wx.GridSizer(1, 3, 0, 0)

        self.checkReadOnly = wx.CheckBox(self, label="ReadOnly")
        self.checkReadOnly.SetValue(self.configData.get(f"/{self.key}/ReadOnly"))
        gBoxSizer.Add(self.checkReadOnly, 0, wx.ALIGN_LEFT)

        self.checkLineNumbers = wx.CheckBox(self, label="Line Numbers")
        self.checkLineNumbers.SetValue(self.configData.get(f"/{self.key}/LineNumber"))
        gBoxSizer.Add(self.checkLineNumbers, 0, wx.ALIGN_LEFT)

        self.checkCaretLine = wx.CheckBox(self, label="Highlight Caret Line")
        self.checkCaretLine.SetValue(self.configData.get(f"/{self.key}/CaretLine"))
        gBoxSizer.Add(self.checkCaretLine, 0, wx.ALIGN_LEFT)

        vBoxSizer.Add(gBoxSizer, 0, wx.LEFT | wx.BOTTOM, border=20)

        # Colors
        text = wx.StaticText(self, label="Colors")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, 0, wx.ALL, border=5)

        vColorSizer = wx.BoxSizer(wx.VERTICAL)
        foregroundColorSizer = wx.GridSizer(1, 6, 0, 0)
        backgroundColorSizer = wx.GridSizer(1, 6, 0, 0)

        # Foreground
        text = wx.StaticText(self, label="Foreground")
        vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

        text = wx.StaticText(self, label="Window")
        foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.windowForeground = csel.ColourSelect(
            self, -1, "",
            hex_to_rgb(self.configData.get(f"/{self.key}/WindowForeground")))

        foregroundColorSizer.Add(self.windowForeground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Line Numbers")
        foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.lineNumbersForeground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get(f"/{self.key}/LineNumberForeground")))

        foregroundColorSizer.Add(self.lineNumbersForeground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Highlight Line")

        foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.caretLineForeground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get(f"/{self.key}/CaretLineForeground")))

        foregroundColorSizer.Add(self.caretLineForeground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        vColorSizer.Add(foregroundColorSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        # Background
        text = wx.StaticText(self, label="")
        vColorSizer.Add(text, 0, flag=wx.ALL, border=5)
        text = wx.StaticText(self, label="Background")
        vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

        text = wx.StaticText(self, label="Window")
        backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.windowBackground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get(f"/{self.key}/WindowBackground")))
        backgroundColorSizer.Add(self.windowBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Line Numbers")
        backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.lineNumbersBackground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get(f"/{self.key}/LineNumberBackground")))

        backgroundColorSizer.Add(self.lineNumbersBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Highlight Line")
        backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.caretLineBackground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get(f"/{self.key}/CaretLineBackground")))
        backgroundColorSizer.Add(self.caretLineBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        vColorSizer.Add(backgroundColorSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        vBoxSizer.Add(vColorSizer, 0, wx.LEFT | wx.BOTTOM | wx.ALIGN_LEFT, border=20)

        # CLI settings
        text = wx.StaticText(self, label="Command Line Interface")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, 0, wx.ALL, border=5)

        # Add check box
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cli_cb = wx.CheckBox(self, wx.ID_ANY, "Save Command History")
        self.cli_cb.SetValue(self.configData.get(f"/{self.key}/cli/SaveCmdHistory"))
        hBoxSizer.Add(self.cli_cb, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        vBoxSizer.Add(hBoxSizer, flag=wx.LEFT, border=20)

        # Add spin ctrl
        hBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cli_sc = wx.SpinCtrl(self, wx.ID_ANY, "")
        self.cli_sc.SetRange(1, 1000)
        self.cli_sc.SetValue(self.configData.get(f"/{self.key}/cli/CmdMaxHistory"))
        hBoxSizer.Add(self.cli_sc, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        st = wx.StaticText(self, wx.ID_ANY, "Max Command History")
        hBoxSizer.Add(st, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        # finish up
        self.SetSizerAndFit(vBoxSizer)

    def UpdateConfigData(self):
        asValue = self.asComboBox.GetSelection()
        if asValue > 0:
            self.configData.set(f"/{self.key}/AutoScroll", self.asComboBox.GetSelection())

        self.configData.set(f"/{self.key}/ReadOnly", self.checkReadOnly.GetValue())

        self.configData.set(
            f"/{self.key}/WindowForeground", self.windowForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
        self.configData.set(
            f"/{self.key}/WindowBackground", self.windowBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

        self.configData.set(f"/{self.key}/CaretLine", self.checkCaretLine.GetValue())
        self.configData.set(
            f"/{self.key}/CaretLineForeground", self.caretLineForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
        self.configData.set(
            f"/{self.key}/CaretLineBackground", self.caretLineBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

        self.configData.set(f"/{self.key}/LineNumber", self.checkLineNumbers.GetValue())
        self.configData.set(
            f"/{self.key}/LineNumberForeground",
            self.lineNumbersForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
        self.configData.set(
            f"/{self.key}/LineNumberBackground",
            self.lineNumbersBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

        font = self.fontSelect.GetSelectedFont()
        font_style_list = []
        font_style_str = ""

        if font.GetWeight() == wx.BOLD:
            font_style_list.append("bold")

        if font.GetStyle() == wx.ITALIC:
            font_style_list.append("italic")

        if len(font_style_list) == 0:
            font_style_str = "normal"
        else:
            font_style_str = ",".join(font_style_list)

        self.configData.set(f"/{self.key}/FontFace", font.GetFaceName())
        self.configData.set(f"/{self.key}/FontSize", font.GetPointSize())
        self.configData.set(f"/{self.key}/FontStyle", font_style_str)

        self.configData.set(f"/{self.key}/cli/SaveCmdHistory", self.cli_cb.GetValue())
        self.configData.set(f"/{self.key}/cli/CmdMaxHistory", self.cli_sc.GetValue())
