"""----------------------------------------------------------------------------
   wnd_numeric_entry.py

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


class gsatNumericEntryDialog(wx.Dialog):
    """
    Dialog for numeric entry. The dialog has a caption and an entry field

    """
    def __init__(self, parent, title, caption, style=wx.DEFAULT_DIALOG_STYLE, size=(250, 150)):
        super().__init__(parent, title=title, style=style)
        self.caption = caption
        self.value = None
        self.InitUI()
        self.SetSize(size)
        self.Centre()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Add caption
        st = wx.StaticText(panel, label=self.caption)
        vbox.Add(st, flag=wx.ALL | wx.EXPAND, border=5)

        # Add numeric entry
        self.entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.entry.Bind(wx.EVT_TEXT, self.OnText)
        self.entry.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)
        vbox.Add(self.entry, flag=wx.ALL | wx.EXPAND, border=5)

        # Add OK and Cancel buttons
        buttons = wx.StdDialogButtonSizer()
        self.okButton = wx.Button(panel, wx.ID_OK)
        self.okButton.SetDefault()
        self.okButton.Disable()
        buttons.AddButton(self.okButton)
        buttons.AddButton(wx.Button(panel, wx.ID_CANCEL))
        buttons.Realize()
        vbox.Add(buttons, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)

        panel.SetSizer(vbox)

    def OnText(self, event):
        """Enable OK button only if valid number is entered"""
        try:
            float(self.entry.GetValue())
            self.okButton.Enable()
        except ValueError:
            self.okButton.Disable()

    def OnEnter(self, event):
        """Close dialog if valid number is entered"""
        if self.okButton.IsEnabled():
            self.EndModal(wx.ID_OK)

    def GetValue(self):
        """Return the numeric value"""
        return float(self.entry.GetValue())