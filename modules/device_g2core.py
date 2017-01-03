"""----------------------------------------------------------------------------
   device_tinyg.py

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

import modules.device_base as devbase

"""----------------------------------------------------------------------------
   gsatDevice_g2core:

   Device g2core class.

----------------------------------------------------------------------------"""
class gsatDevice_g2core(devbase.gsatDeviceBase):
   def __init__(self, cmd_line_options):
      devbase.gsatDeviceBase.__init__(self, cmd_line_options)

   def Encode(self, data):
      # for now do nothing...
      return data

   def Decode(self, data):
      dataDict = {}

      if data.startswith("{"):
         dataDict = json.loads(data)

         if 'r' in dataDict:
            r = dataDict['r']
            
            # get status response out to avoid digging out later
            if 'sr' in r:
               sr = r['sr']
               dataDict['sr'] = sr
               del r['sr']

         if 'sr' in dataDict:
            sr = dataDict['sr']

            if 'stat' in sr:
               status = sr['stat']

               if 0 == status:
                  sr['stat'] = 'Init'
               elif 1 == status:
                  sr['stat'] = 'Ready'
               elif 2 == status:
                  sr['stat'] = 'Alarm'
               elif 3 == status:
                  sr['stat'] = 'Stop'
               elif 4 == status:
                  sr['stat'] = 'End'
               elif 5 == status:
                  sr['stat'] = 'Run'
               elif 6 == status:
                  sr['stat'] = 'Hold'
               elif 7 == status:
                  sr['stat'] = 'Probe'
               elif 8 == status:
                  sr['stat'] = 'Run'
               elif 9 == status:
                  sr['stat'] = 'Home'

            # deal with old versions of g2core
            if 'mpox' in sr:
               sr['posx'] = sr['mpox']
            if 'mpoy' in sr:
               sr['posy'] = sr['mpoy']
            if 'mpoz' in sr:
               sr['posz'] = sr['mpoz']
            if 'mpoa' in sr:
               sr['posa'] = sr['mpoa']

      else:
         if self.cmdLineOptions.vverbose:
            print "** gsatDevice_g2core cannot decode data!! [%s]." % data

      return dataDict

   def GetSetAxisCmd (self):
      return "G28.3"
      
   def GetDeviceName(self):
      return "g2core"

   def GetStatus(self):
      return '{"sr":null}\n'

   def InitComm(self):
      return ''
