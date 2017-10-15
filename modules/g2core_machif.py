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
import re

try:
    import simplejson as json
except ImportError:
    import json

import modules.machif as mi


"""----------------------------------------------------------------------------
   MachIf_g2core:

   Machine Interface g2core class.

   ID = 1200
   Name = "g2core"
   input buffer max size = 255
   input buffer init size = 0
   input buffer watermark = 90%

   Init buffer to (1) when connecting it counts that as one char on response
   initial msg looks like
   {"r":{"fv":0.98,"fb":89.03,"hp":3,"hv":0,"id":"0213-2335-6343","msg":"SYSTEM READY"},"f":[1,0,1]}

   !!notice f[1,0,1]

----------------------------------------------------------------------------"""
class MachIf_g2core(mi.MachIf_Base):
   inputBufferMaxSize = 255
   inputBufferInitVal = 0
   inputBufferWatermarkPrcnt = 0.90

   # text mode re expressions
   reMachineAck = re.compile(r'.+ok>\s$')
   reMachinePos = re.compile(r'(\w)\s+position:\s+([+-]{0,1}\d+\.\d+)')
   reMachineVel = re.compile(r'Velocity:\s+(\d+\.\d+)')
   reMachineStat = re.compile(r'Machine state:\s+(\w+)')

   stat_dict ={
      0:'Init',
      1:'Ready',
      2:'Alarm',
      3:'Stop',
      4:'End',
      5:'Run',
      6:'Hold',
      7:'Probe',
      8:'Cycle',
      9:'Homeming',
      10:'Jog',
      11:'InterLock',
      12:'Shutdown',
      13:'Panic',
      }

   def __init__(self, cmd_line_options):
      super(MachIf_g2core, self).__init__(cmd_line_options, 1200,
         "g2core", self.inputBufferMaxSize, self.inputBufferInitVal,
         self.inputBufferWatermarkPrcnt)

      self.inputBufferPart = list()

   def decode(self, data):
      dataDict = {}

      try:
         dataDict = json.loads(data)

         if 'r' in dataDict:
            r = dataDict['r']

            # get status response out to avoid digging out later
            if 'sr' in r:
               sr = r['sr']
               dataDict['sr'] = sr

         if 'sr' in dataDict:
            sr = dataDict['sr']

            if 'stat' in sr:
               status = sr['stat']
               sr['stat'] = self.stat_dict.get(status,"Uknown")

            # deal with old versions of g2core
            if 'mpox' in sr:
               sr['posx'] = sr['mpox']
            if 'mpoy' in sr:
               sr['posy'] = sr['mpoy']
            if 'mpoz' in sr:
               sr['posz'] = sr['mpoz']
            if 'mpoa' in sr:
               sr['posa'] = sr['mpoa']

         dataDict['ib'] = [self.inputBufferMaxSize, self.inputBufferSize]

      except:
         ack = self.reMachineAck.match(data)
         pos = self.reMachinePos.match(data)
         vel = self.reMachineVel.match(data)
         stat = self.reMachineStat.match(data)

         if ack is not None:
            dataDict['r'] = {"f":[1,0,0]}
            dataDict['f'] = [1,0,0]
         elif pos is not None:
            if 'sr' not in dataDict:
               dataDict['sr'] = {}

            dataDict['sr']["".join(["pos", pos.group(1).lower()])] = float(pos.group(2))
         elif vel is not None:
            if 'sr' not in dataDict:
               dataDict['sr'] = {}

            dataDict['sr']['vel'] = float(vel.group(1))
         elif stat is not None:
            if 'sr' not in dataDict:
               dataDict['sr'] = {}

            dataDict['sr']['stat'] = stat.group(1)
         else:
            if self.cmdLineOptions.vverbose:
               print "** MachIf_g2core cannot decode data!! [%s]." % data

      if 'r' in dataDict:
         # checking for count in "f" response doesn't always work as expected and broke on edge branch
         # it was never specify that this was the functionality so abandoning that solution

         if len(self.inputBufferPart) > 0:
            bufferPart = self.inputBufferPart.pop(0)

            self.inputBufferSize = self.inputBufferSize - bufferPart

            if self.cmdLineOptions.vverbose:
               print "** MachIf_g2core input buffer decode returned: %d, buffer size: %d, %.2f%% full" % \
                  (bufferPart, self.inputBufferSize, \
                  (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize)))
         else:
            pass
            #print "hmmm this could be a problem"
            #print dataDict

      return dataDict

   def encode(self, data, bookeeping=True):
      data = data.encode('ascii')

      if data in [self.getCycleStartCmd(), self.getFeedHoldCmd()]:
         pass
      elif bookeeping:
         dataLen = len(data)
         self.inputBufferSize = self.inputBufferSize + dataLen

         self.inputBufferPart.append(dataLen)

         if self.cmdLineOptions.vverbose:
            print "** MachIf_g2core input buffer encode used: %d, buffer size: %d, %.2f%% full" % \
               (dataLen, self.inputBufferSize, \
               (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize)))

      return data

   def getQueueFlushCmd (self):
      return "%\n"

   def getSetAxisCmd (self):
      #return "G28.3"
      return "G92"

   def getStatusCmd(self):
      return '{"sr":null}\n'

   def reset(self):
      super(MachIf_g2core, self)._reset(self.inputBufferMaxSize,
         self.inputBufferInitVal, self.inputBufferWatermarkPrcnt)

      self.inputBufferPart = list()
