"""----------------------------------------------------------------------------
   grbl_machif.py

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
import time
import datetime as dt

try:
    import simplejson as json
except ImportError:
    import json

import re

import modules.machif as mi

# -----------------------------------------------------------------------------
# regular expressions
# -----------------------------------------------------------------------------
# -------------
# Grbl

# grbl version, example "Grbl 0.8c ['$' for help]"
gReGrblVersion = re.compile(r'Grbl\s*(.*)\s*\[.*\]')

# status,
# quick re check to avoid multiple checks, speeds things up
gReMachineStatus = re.compile(r'pos', re.I)

# GRBL example "<Run,MPos:20.163,0.000,0.000,WPos:20.163,0.000,0.000>"
gReGRBLMachineStatus = re.compile(r'<(\w+)[,\|].*WPos:([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+)')

# grbl ack, example  "ok"
gReGRBLMachineAck = re.compile(r'^ok\s$')

# grbl error, example  "error:20", "error: Unsupported command"
gReGRBLMachineError = re.compile(r'^error:(.*)\s$')

# Numeric reperecentation of state, cehcking strings all the time is not
# fastest way...
GRBL_STATE_UKNOWN    = 1000
GRBL_STATE_IDLE      = 1010
GRBL_STATE_RUN       = 1020
GRBL_STATE_HOLD      = 1030
GRBL_STATE_JOG       = 1040
GRBL_STATE_ALRARM    = 1050
GRBL_STATE_DOOR      = 1060
GRBL_STATE_CHECK     = 1070
GRBL_STATE_HOME      = 1080
GRBL_STATE_SLEEP     = 1090
GRBL_STATE_STOP      = 1100

gGrblStateDict = {
   "Idle"   : GRBL_STATE_IDLE,
   "Run"    : GRBL_STATE_RUN,
   "Hold"   : GRBL_STATE_HOLD,
   "Jog"    : GRBL_STATE_JOG,
   "Alarm"  : GRBL_STATE_ALRARM,
   "Door"   : GRBL_STATE_DOOR,
   "Check"  : GRBL_STATE_CHECK,
   "Home"   : GRBL_STATE_HOME,
   "Sleep"  : GRBL_STATE_SLEEP,
   "Stop"   : GRBL_STATE_STOP
   }


"""----------------------------------------------------------------------------
   machIf_GRBL:

   Machine Interface GRBL class.

   ID = 1000
   Name = "GRBL"
   Input buffer max size = 127
   Input buffer init size = 0
   Input buffer watermark = 90%

   per GRBL 0.9 and 1.1 grbl input buffer is 127 bytes (buffer includes
   all characters including nulls and new line)

----------------------------------------------------------------------------"""
class machIf_GRBL(mi.machIf_Base):
   def __init__(self, cmd_line_options):
      mi.machIf_Base.__init__(self, cmd_line_options, 1000, "grbl", 127, 0, 0.90)

      self.inputBufferPart = list()

      self.getSatusCmd = '?'
      self.currentStatus = GRBL_STATE_UKNOWN
      self.autoStatusNextMicro = None
      self.machineAutoRefresh = False

   def Decode(self, data):
      dataDict = {}

      # GRBL status data
      # data is expected to be an array of strings as follows
      # statusData[0] : Machine state
      # statusData[1] : Machine X
      # statusData[2] : Machine Y
      # statusData[3] : Machine Z
      # statusData[4] : Work X
      # statusData[5] : Work Y
      # statusData[6] : Work Z

      status = gReGRBLMachineStatus.match(data)
      if status is not None:
         statusData = status.groups()
         sr = {}

         # remove the "?" used to get status notice no "\n"
         bufferPart = 1
         self.inputBufferSize = self.inputBufferSize - bufferPart

         sr['stat'] = statusData[0]
         sr['posx'] = float(statusData[1])
         sr['posy'] = float(statusData[2])
         sr['posz'] = float(statusData[3])

         dataDict['sr'] = sr

         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL re GRBL status match %s" % str(statusData)
            print "** machIf_GRBL str match from %s" % str(data.strip())
            print "** machIf_GRBL input buffer decode returned: %d, buffer size: %d, %.2f%% full" % \
               (bufferPart, self.inputBufferSize, \
               (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize)))

         # check on status change
         decodedStatus = gGrblStateDict.get(statusData[0], GRBL_STATE_UKNOWN)
         if self.currentStatus != decodedStatus:
            if decodedStatus in [GRBL_STATE_RUN, GRBL_STATE_JOG]:
               self.autoStatusNextMicro = dt.datetime.now() + dt.timedelta(microseconds= self.stateData.machineStatusAutoRefreshPeriod * 1000)

            self.currentStatus = decodedStatus

      ack = gReGRBLMachineAck.search(data)
      if ack is not None:
         bufferPart = 0

         if len(self.inputBufferPart) > 0:
            bufferPart = self.inputBufferPart.pop(0)

         self.inputBufferSize = self.inputBufferSize - bufferPart

         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL found acknowledgement [%s]" % data.strip()

         r = {}
         dataDict['r'] = r
         dataDict['f'] = [0,0,bufferPart]
         dataDict['ib'] = [self.inputBufferMaxSize, self.inputBufferSize]

         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL input buffer decode returned: %d, buffer size: %d, %.2f%% full" % \
               (bufferPart, self.inputBufferSize, \
               (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize)))

      error = gReGRBLMachineError.search(data)
      if error is not None:
         bufferPart = 0

         if len(self.inputBufferPart) > 0:
            bufferPart = self.inputBufferPart.pop(0)

         self.inputBufferSize = self.inputBufferSize - bufferPart

         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL found error [%s]" % data.strip()

         if 'r' not in dataDict:
            r = {}
            dataDict['r'] = r

         error_code = error.group(1).strip()
         if error_code.isdigit():
            error_code = int(error_code)
         else:
            error_code = -1

         dataDict['f'] = [0,error_code,bufferPart, error.group(1).strip()]
         dataDict['ib'] = [self.inputBufferMaxSize, self.inputBufferSize]

         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL input buffer decode returned: %d, buffer size: %d, %.2f%% full" % \
               (bufferPart, self.inputBufferSize, \
               (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize)))

      version = gReGrblVersion.match(data)
      if version is not None:
         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL found device version [%s]" % version.group(1).strip()

         if 'r' not in dataDict:
            r = {}
            dataDict['r'] = r

         dataDict['r']['fv'] = version.group(1)
         dataDict['f'] = [0,0,0]
         dataDict['ib'] = [self.inputBufferMaxSize, self.inputBufferSize]

      return dataDict

   def Encode(self, data, bookeeping=True):
      if len(data) == 0:
         return data

      data = data.encode('ascii')

      # handle special cases doe to status in cmd line and how GRBL
      # reports deals with this. if not careful we might get two status
      # from a single line but is not consistence on hos this works.
      # for this reason if we find "?" on the line will remove all but one
      # also add 1 to the buffer since the status will remove 1 and
      # the acknowledged will remove the length of the line. If this is
      # not done the "?" will be counted twice when removing from
      # input buffer usage.
      if data.find(self.getSatusCmd) != -1:
         data = data.replace(self.getSatusCmd, "")
         data = "".join([data, "?"])

         if bookeeping:
            self.inputBufferSize = self.inputBufferSize + 1

      if data == self.getSatusCmd and bookeeping:
         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL input buffer encode used: %d, buffer size: %d, %.2f%% full" % \
               (1, self.inputBufferSize, \
               (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize)))

      elif bookeeping:
         dataLen = len(data)
         self.inputBufferSize = self.inputBufferSize + dataLen

         self.inputBufferPart.append(dataLen)

         if self.cmdLineOptions.vverbose:
            print "** machIf_GRBL input buffer encode used: %d, buffer size: %d, %.2f%% full" % \
               (dataLen, self.inputBufferSize, \
               (100 * (float(self.inputBufferSize)/self.inputBufferMaxSize)))

      return data

   def Init(self, state_data):
      mi.machIf_Base.Init(self, state_data)
      self.machineAutoRefresh = self.stateData.machineStatusAutoRefresh

   def GetInitCommCmd(self):
      return ""

   def GetSetAxisCmd(self):
      return "G92"

   def GetStatusCmd(self):
      return self.getSatusCmd

   def Tick (self):
      # check if is time for autorefresh and send get status cmd and prepare next refresh time
      if (self.autoStatusNextMicro != None) and (self.currentStatus in [GRBL_STATE_RUN, GRBL_STATE_JOG]):
         tnow = dt.datetime.now()
         tnowMilli = tnow.second*1000 + tnow.microsecond/1000
         tdeltaMilli = self.autoStatusNextMicro.second*1000 +  self.autoStatusNextMicro.microsecond/1000
         if  long(tnowMilli - tdeltaMilli) >= 0:
            if self.OkToSend(self.getSatusCmd):
               mi.machIf_Base.Write(self, self.getSatusCmd)

            self.autoStatusNextMicro = dt.datetime.now() + dt.timedelta(microseconds = self.stateData.machineStatusAutoRefreshPeriod * 1000)

      elif self.autoStatusNextMicro != None and self.currentStatus not in [GRBL_STATE_RUN, GRBL_STATE_JOG]:
         self.autoStatusNextMicro = None

      if self.machineAutoRefresh != self.stateData.machineStatusAutoRefresh:
         # depending on current state do appropriate action
         if self.machineAutoRefresh == False:
            if self.OkToSend(self.getSatusCmd):
               mi.machIf_Base.Write(self, self.getSatusCmd)

            self.autoStatusNextMicro = dt.datetime.now() + dt.timedelta(microseconds = self.stateData.machineStatusAutoRefreshPeriod * 1000)
         else:
            self.autoStatusNextMicro = None

         # finally update local variable
         self.machineAutoRefresh = self.stateData.machineStatusAutoRefresh


   def Write(self, txData, raw_write=False):
      askForStatus = False
      bytesSent = 0

      # moving to active state get at least one status msg
      if self.currentStatus in [GRBL_STATE_IDLE, GRBL_STATE_STOP, GRBL_STATE_HOME, GRBL_STATE_SLEEP]:
         askForStatus = True

      bytesSent = mi.machIf_Base.Write(self, txData, raw_write)

      if askForStatus and self.machineAutoRefresh:
         if self.OkToSend(self.getSatusCmd):
            mi.machIf_Base.Write(self, self.getSatusCmd)

         self.autoStatusNextMicro = dt.datetime.now() + dt.timedelta(microseconds = self.stateData.machineStatusAutoRefreshPeriod * 1000)

      return bytesSent


