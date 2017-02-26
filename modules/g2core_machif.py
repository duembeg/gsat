"""----------------------------------------------------------------------------
   g2core_machif.py

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

import modules.machif as mi

"""----------------------------------------------------------------------------
   machIf_g2core:

   Machine Interface g2core class.

   ID = 1200
   Name = "g2core"
   input buffer max size = 255
   input buffer init size = 1
   input buffer watermark = 90%
   
   Init buffer to (1) when connecting it counts that as one char on response
   initial msg looks like
   {"r":{"fv":0.98,"fb":89.03,"hp":3,"hv":0,"id":"0213-2335-6343","msg":"SYSTEM READY"},"f":[1,0,1]}
   
   !!notice f[1,0,1]
   
----------------------------------------------------------------------------"""
class machIf_g2core(mi.machIf_Base):
   def __init__(self, cmd_line_options):
      mi.machIf_Base.__init__(self, cmd_line_options, 1200, "g2core", 255, 1, 0.90)

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
               #del r['sr']

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
               
         if 'f' in dataDict:
            f = dataDict['f']
            
            # remove buffer part freed from acked command
            bufferPart = f[2]
            self.inputBufferSize = self.inputBufferSize - bufferPart
            
            if self.cmdLineOptions.vverbose:
               print "** machIf_g2core input buffer decode returned: %d, buffer size: %d, %.2f%% full" % \
                  (bufferPart, self.inputBufferSize, \
                  (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize))) 
                  
         dataDict['ib'] = [self.inputBufferMaxSize, self.inputBufferSize]

      else:
         if self.cmdLineOptions.vverbose:
            print "** machIf_g2core cannot decode data!! [%s]." % data

      return dataDict

   def Encode(self, data, bookeeping=True):
      data = data.encode('ascii')
      
      if bookeeping:
         dataLen = len(data)
         self.inputBufferSize = self.inputBufferSize + dataLen
            
         if self.cmdLineOptions.vverbose:
            print "** machIf_g2core input buffer encode used: %d, buffer size: %d, %.2f%% full" % \
               (dataLen, self.inputBufferSize, \
               (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize))) 
         
      return data
      
   def GetSetAxisCmd (self):
      return "G28.3"
      
   def GetStatus(self):
      return '{"sr":null}\n'

   def InitComm(self):
      return ''

   def OkToSend(self, data):
      bufferHasRoom = True
      
      data = self.Encode(data, bookeeping=False)
      
      if (self.inputBufferSize + len(data)) > self.inputBufferWatermark:
         bufferHasRoom = False
         
      return bufferHasRoom