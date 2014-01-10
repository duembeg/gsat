#!/usr/bin/env python
"""----------------------------------------------------------------------------
   gsat.py:

   Copyright (C) 2013-2014 Wilhelm Duembeg

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

import os
import sys
import wx
from optparse import OptionParser

import modules.mainwnd as mw


"""----------------------------------------------------------------------------
   get_cli_params
   Get and process command line parameters.
----------------------------------------------------------------------------"""
def get_cli_params():
   ''' define, retrieve and error check command line interface (cli) params
   '''

   usage = \
      "usage: %prog [options]"

   parser = OptionParser(usage=usage)
   #parser.add_option("-f", "--file", dest="filename",
   #   help="write report to FILE", metavar="FILE")

   parser.add_option("-v", "--verbose",
      dest="verbose", action="store_true", default=False,
      help="print extra information while processing input file.")

   parser.add_option("--vv", "--vverbose",
      dest="vverbose", action="store_true", default=False,
      help="print extra extra information while processing input file.")

   (options, args) = parser.parse_args()

   # check arguments sanity
   if options.vverbose:
      options.verbose = True

   if not wx.VERSION >= (2,7,0,0):
      print "** Required wxPython 2.7 or grater."
      options.error()
      error(1)

   return (options, args)

"""----------------------------------------------------------------------------
   main
----------------------------------------------------------------------------"""
if __name__ == '__main__':

   (cmd_line_options, cli_args) = get_cli_params()

   app = wx.App(0)
   mw.gsatMainWindow(None, title=__appname__, cmd_line_options=cmd_line_options)
   app.MainLoop()
