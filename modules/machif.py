"""----------------------------------------------------------------------------
   machif.py

   Copyright (C) 2013-2017 Wilhelm Duembeg

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
try:
    import simplejson as json
except ImportError:
    import json


"""----------------------------------------------------------------------------
   machIf_Base:

   Machine interface base class to provide a unified API for specific devices
   (g2core, TinyG, grbl, etc).

----------------------------------------------------------------------------"""
class machIf_Base():
   def __init__(self, cmd_line_options, id, name, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
      self.cmdLineOptions = cmd_line_options
      self.id = id
      self.name = name
      self.inputBufferMaxSize = input_buffer_max_size
      self.inputBufferWatermark = float(self.inputBufferMaxSize) * input_buffer_watermark_prcnt
      self.inputBufferSize = input_buffer_init_val

   def Encode(self, data):
      return data

   def Decode(self, data):
      return data

   def GetSetAxisCmd (self):
      return ""
      
   def GetId(self):
      return self.id
      
   def GetName(self):
      return self.name

   def GetStatus(self):
      return ""

   def Init(self):
      pass
      
   def InitComm(self):
      return ""

   def Read(self, data):
      serialData = ""
      return serialData

   def Write(self, data, raw_write=False):
      return ""
