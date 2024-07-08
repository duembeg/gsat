"""----------------------------------------------------------------------------
   wnd_output_config.py

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
    m = re.match(r'^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$',
                 hex_color, re.IGNORECASE)
    return (int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16))


class Factory():
    """
    Factory class to init config page

    """

    @staticmethod
    def GetIcon():
        return ico.imgLog.GetBitmap()

    @staticmethod
    def AddPage(parent_wnd, config, page):
        ''' Function to create and inti settings page
        '''
        settings_page = gsatOutputSettingsPanel(parent_wnd, config)
        parent_wnd.AddPage(settings_page, "Output")
        parent_wnd.SetPageImage(page, page)

        return settings_page


class gsatOutputSettingsPanel(scrolled.ScrolledPanel):
    """
    Output settings

    """

    def __init__(self, parent, config_data, key="output"):
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
        hBoxSizer.Add(spText, 0)

        if self.key == 'code':
            asList = ["Never", "Always", "On Kill Focus", "On Goto PC"]
        else:
            asList = ["Never", "Always", "On Kill Focus"]

        self.asComboBox = wx.ComboBox(
            self, -1, value=asList[self.configData.get('/%s/AutoScroll' % self.key)],
            choices=asList, style=wx.CB_READONLY)
        hBoxSizer.Add(self.asComboBox, 0, flag=wx.ALL | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL, border=5)

        vBoxSizer.Add(hBoxSizer, 0, wx.LEFT | wx.EXPAND | wx.ALIGN_LEFT, border=20)

        # General Controls
        text = wx.StaticText(self, label="General")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, 0, wx.ALL, border=5)

        self.fontSelect = wx.FontPickerCtrl(self, size=(300, -1))
        vBoxSizer.Add(self.fontSelect, 0, wx.LEFT | wx.ALIGN_LEFT, border=20)
        font = wx.Font(
            self.configData.get('/%s/FontSize' % self.key), wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0,
            self.configData.get('/%s/FontFace' % self.key))

        font_style_str = self.configData.get('/%s/FontStyle' % self.key)

        if "bold" in font_style_str:
            font.MakeBold()

        if "italic" in font_style_str:
            font.MakeItalic()

        self.fontSelect.SetSelectedFont(font)

        vBoxSizer.Add((10, 10), 0, wx.ALL, border=1)

        gBoxSizer = wx.GridSizer(1, 3, 0, 0)

        self.checkReadOnly = wx.CheckBox(self, label="ReadOnly")
        self.checkReadOnly.SetValue(self.configData.get('/%s/ReadOnly' % self.key))
        gBoxSizer.Add(self.checkReadOnly, 0, wx.ALIGN_LEFT)

        self.checkLineNumbers = wx.CheckBox(self, label="Line Numbers")
        self.checkLineNumbers.SetValue(self.configData.get('/%s/LineNumber' % self.key))
        gBoxSizer.Add(self.checkLineNumbers, 0, wx.ALIGN_LEFT)

        self.checkCaretLine = wx.CheckBox(self, label="Highlight Caret Line")
        self.checkCaretLine.SetValue(self.configData.get('/%s/CaretLine' % self.key))
        gBoxSizer.Add(self.checkCaretLine, 0, wx.ALIGN_LEFT)

        vBoxSizer.Add(gBoxSizer, 0, wx.LEFT, border=20)

        # Colors
        text = wx.StaticText(self, label="Colors")
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        text.SetFont(font)
        vBoxSizer.Add(text, 0, wx.ALL, border=5)

        vColorSizer = wx.BoxSizer(wx.VERTICAL)
        foregroundColorSizer = wx.GridSizer(1, 6, 0, 0)
        backgroundColorSizer = wx.GridSizer(1, 6, 0, 0)
        syntaxColorSizer = wx.GridSizer(3, 6, 0, 0)

        # Foreground
        text = wx.StaticText(self, label="Foreground")
        vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

        text = wx.StaticText(self, label="Window")
        foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.windowForeground = csel.ColourSelect(
            self, -1, "",
            hex_to_rgb(self.configData.get('/%s/WindowForeground' % self.key)))

        foregroundColorSizer.Add(self.windowForeground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Line Numbers")
        foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.lineNumbersForeground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get('/%s/LineNumberForeground' % self.key)))

        foregroundColorSizer.Add(self.lineNumbersForeground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Highlight Line")

        foregroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.caretLineForeground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get('/%s/CaretLineForeground' % self.key)))

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
            self, -1, "", hex_to_rgb(self.configData.get('/%s/WindowBackground' % self.key)))
        backgroundColorSizer.Add(self.windowBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Line Numbers")
        backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.lineNumbersBackground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get('/%s/LineNumberBackground' % self.key)))

        backgroundColorSizer.Add(self.lineNumbersBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        text = wx.StaticText(self, label="Highlight Line")
        backgroundColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
        self.caretLineBackground = csel.ColourSelect(
            self, -1, "", hex_to_rgb(self.configData.get('/%s/CaretLineBackground' % self.key)))
        backgroundColorSizer.Add(self.caretLineBackground, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

        vColorSizer.Add(
            backgroundColorSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        if self.key == 'code':
            # Syntax highlighting
            text = wx.StaticText(self, label="")
            vColorSizer.Add(text, 0, flag=wx.ALL, border=5)
            text = wx.StaticText(self, label="Syntax highlighting")
            vColorSizer.Add(text, 0, flag=wx.ALL, border=5)

            text = wx.StaticText(self, label="G Code")
            syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.gCodeHighlight = csel.ColourSelect(
                self, -1, "", hex_to_rgb(self.configData.get('/%s/GCodeHighlight' % self.key)))
            syntaxColorSizer.Add(self.gCodeHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

            text = wx.StaticText(self, label="M Code")
            syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.gModeHighlight = csel.ColourSelect(
                self, -1, "", hex_to_rgb(self.configData.get('/%s/MCodeHighlight' % self.key)))
            syntaxColorSizer.Add(self.gModeHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

            text = wx.StaticText(self, label="Axis Codes")
            syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.axisHighlight = csel.ColourSelect(
                self, -1, "", hex_to_rgb(self.configData.get('/%s/AxisHighlight' % self.key)))

            syntaxColorSizer.Add(self.axisHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

            text = wx.StaticText(self, label="Parameters")
            syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.parametersHighlight = csel.ColourSelect(
                self, -1, "", hex_to_rgb(self.configData.get('/%s/ParametersHighlight' % self.key)))

            syntaxColorSizer.Add(self.parametersHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

            text = wx.StaticText(self, label="Parameters2")
            syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.parameters2Highlight = csel.ColourSelect(
                self, -1, "", hex_to_rgb(self.configData.get('/%s/Parameters2Highlight' % self.key)))

            syntaxColorSizer.Add(self.parameters2Highlight, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

            text = wx.StaticText(self, label="Comments")
            syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.commentsHighlight = csel.ColourSelect(
                self, -1, "", hex_to_rgb(self.configData.get('/%s/CommentsHighlight' % self.key)))

            syntaxColorSizer.Add(self.commentsHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

            text = wx.StaticText(self, label="G-Code Line #")
            syntaxColorSizer.Add(text, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.gCodeLineNumberHighlight = csel.ColourSelect(
                self, -1, "", hex_to_rgb(self.configData.get('/%s/GCodeLineNumberHighlight' % self.key)))

            syntaxColorSizer.Add(self.gCodeLineNumberHighlight, 0, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT)

            vColorSizer.Add(syntaxColorSizer, 0, flag=wx.LEFT | wx.EXPAND, border=20)

        vBoxSizer.Add(vColorSizer, 0, wx.LEFT | wx.ALIGN_LEFT, border=10)

        # finish up
        self.SetSizerAndFit(vBoxSizer)

    def UpdateConfigData(self):
        asValue = self.asComboBox.GetSelection()
        if asValue > 0:
            self.configData.set(f'/{self.key}/AutoScroll', self.asComboBox.GetSelection())

        self.configData.set(f'/{self.key}/ReadOnly', self.checkReadOnly.GetValue())

        self.configData.set(
            f'/{self.key}/WindowForeground', self.windowForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
        self.configData.set(
            f'/{self.key}/WindowBackground', self.windowBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

        self.configData.set(f'/{self.key}/CaretLine', self.checkCaretLine.GetValue())
        self.configData.set(
            f'/{self.key}/CaretLineForeground', self.caretLineForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
        self.configData.set(
            f'/{self.key}/CaretLineBackground', self.caretLineBackground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

        self.configData.set(f'/{self.key}/LineNumber', self.checkLineNumbers.GetValue())
        self.configData.set(
            f'/{self.key}/LineNumberForeground',
            self.lineNumbersForeground.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
        self.configData.set(
            f'/{self.key}/LineNumberBackground',
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

        self.configData.set(f'/{self.key}/FontFace', font.GetFaceName())
        self.configData.set(f'/{self.key}/FontSize', font.GetPointSize())
        self.configData.set(f'/{self.key}/FontStyle', font_style_str)

        if self.key == 'code':
            self.configData.set(
                f'/{self.key}/GCodeHighlight', self.gCodeHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

            self.configData.set(
                f'/{self.key}/MCodeHighlight', self.gModeHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

            self.configData.set(
                f'/{self.key}/AxisHighlight', self.axisHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

            self.configData.set(
                f'/{self.key}/ParametersHighlight',
                self.parametersHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

            self.configData.set(
                f'/{self.key}/Parameters2Highlight',
                self.parametersHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

            self.configData.set(
                f'/{self.key}/CommentsHighlight', self.commentsHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))

            self.configData.set(
                f'/{self.key}/GCodeLineNumberHighlight',
                self.gCodeLineNumberHighlight.GetColour().GetAsString(wx.C2S_HTML_SYNTAX))
