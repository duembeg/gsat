"""----------------------------------------------------------------------------
   tinyg_machif.py

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


""" Global values for this module
"""
# This values are only use to initialize or reset base class.
# base class has internal variables tor track these
ID = 1100
NAME = "TinyG"
BUFFER_MAX_SIZE = 255
BUFFER_INIT_VAL = 0
BUFFER_WATERMARK_PRCNT = 0.90

class MachIf_TinyG(mi.MachIf_Base):
    """-------------------------------------------------------------------------
    MachIf_TinyG:

    TinyG machine interface.

    ID = 1100
    Name = "TinyG"

    -------------------------------------------------------------------------"""

    """-------------------------------------------------------------------------
    Notes:

    input buffer max size = 255
    input buffer init size = 0
    input buffer watermark = 90%

    Init buffer to (-1) when connecting it needs a initial '\n' that
    should not be counted
    -------------------------------------------------------------------------"""

    # text mode re expressions
    reMachineAck = re.compile(r'.+\s+ok>\s$')
    reMachineErr = re.compile(r'.+\s+err:\s$')
    reMachinePosX = re.compile(r'.*(posx):([+-]{0,1}\d+\.\d+)')
    reMachinePosY = re.compile(r'.*(posy):([+-]{0,1}\d+\.\d+)')
    reMachinePosZ = re.compile(r'.*(posz):([+-]{0,1}\d+\.\d+)')
    reMachinePosA = re.compile(r'.*(posa):([+-]{0,1}\d+\.\d+)')
    reMachineVel = re.compile(r'.*vel:(\d+\.\d+),{0,1}')
    reMachineStat = re.compile(r'.*stat:(\d+),{0,1}')

    stat_dict = {
        0: 'Init',
        1: 'Ready',
        2: 'Alarm',
        3: 'Stop',
        4: 'End',
        5: 'Run',
        6: 'Hold',
        7: 'Probe',
        8: 'Cycle',
        9: 'Homeming',
        10: 'Jog',
        11: 'InterLock',
        12: 'Shutdown',
        13: 'Panic',
    }

    def __init__(self, cmd_line_options):
        super(MachIf_TinyG, self).__init__(cmd_line_options, ID,
                                           NAME, BUFFER_MAX_SIZE, BUFFER_INIT_VAL,
                                           BUFFER_WATERMARK_PRCNT)

        self._inputBufferPart = list()

        # list of commands
        self.cmdInitComm = '\n{"sys":null}\n'
        self.cmdQueueFlushCmd = "%\n"
        self.cmdSetAxisCmd = "G28.3"
        self.cmdStatus = '{"sr":null}\n'

    def _init(self):
        """ Init object variables, ala soft-reset in hw
        """
        super(MachIf_TinyG, self)._reset(BUFFER_MAX_SIZE,
                                         BUFFER_INIT_VAL, BUFFER_WATERMARK_PRCNT)

        self._inputBufferPart = list()

    def decode(self, data):
        dataDict = {}

        try:
            dataDict = json.loads(data)

            if 'r' in dataDict:
                r = dataDict['r']

                # get footer response out to avoid digging out later
                if 'f' in r:
                    f = r['f']
                    dataDict['f'] = f

                # get status response out to avoid digging out later
                if 'sr' in r:
                    sr = r['sr']
                    dataDict['sr'] = sr

                # get version out to avoid digging out later
                if 'sys' in r:
                    sys = r['sys']

                    if 'fb' in sys:
                        r['fb'] = sys['fb']

                    if 'fv' in sys:
                        r['fv'] = sys['fv']

            if 'sr' in dataDict:
                sr = dataDict['sr']

                if 'stat' in sr:
                    status = sr['stat']
                    sr['stat'] = self.stat_dict.get(status, "Uknown")

                # deal with old versions of tinyG
                if 'mpox' in sr:
                    sr['posx'] = sr['mpox']
                if 'mpoy' in sr:
                    sr['posy'] = sr['mpoy']
                if 'mpoz' in sr:
                    sr['posz'] = sr['mpoz']
                if 'mpoa' in sr:
                    sr['posa'] = sr['mpoa']

            dataDict['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

        except:
            match = False
            ack = self.reMachineAck.match(data)
            posx = self.reMachinePosX.match(data)
            posy = self.reMachinePosY.match(data)
            posz = self.reMachinePosZ.match(data)
            posa = self.reMachinePosA.match(data)
            vel = self.reMachineVel.match(data)
            stat = self.reMachineStat.match(data)

            if ack is not None:
                dataDict['r'] = {"f": [1, 0, 0]}
                dataDict['f'] = [1, 0, 0]
                match = True

            for pos in [posx, posy, posz, posa]:
                if pos is not None:
                    if 'sr' not in dataDict:
                        dataDict['sr'] = {}

                    dataDict['sr'][pos.group(1)] = float(pos.group(2))
                    match = True

            if vel is not None:
                if 'sr' not in dataDict:
                    dataDict['sr'] = {}

                dataDict['sr']['vel'] = float(vel.group(1))
                match = True

            if stat is not None:
                if 'sr' not in dataDict:
                    dataDict['sr'] = {}

                dataDict['sr']['stat'] = self.stat_dict.get(
                    int(stat.group(1)), "Uknown")
                match = True

            if match == False:
                if self.cmdLineOptions.vverbose:
                    print "** MachIf_TinyG cannot decode data!! [%s]." % data

        if 'r' in dataDict:
            # checking for count in "f" response doesn't always work as expected and broke on edge branch
            # it was never specify that this was the functionality so abandoning that solution

            if len(self._inputBufferPart) > 0:
                bufferPart = self._inputBufferPart.pop(0)

                self._inputBufferSize = self._inputBufferSize - bufferPart

                if self.cmdLineOptions.vverbose:
                    print "** MachIf_TinyG input buffer decode returned: %d, buffer size: %d, %.2f%% full" % \
                        (bufferPart, self._inputBufferSize,
                         (100 * (float(self._inputBufferSize)/self._inputBufferMaxSize)))
            else:
                pass
                #print "hmmm this could be a problem"
                #print dataDict

        return dataDict

    def doClearAlarm(self):
        """ Clears alarm condition in grbl
        """
        self.write('{"clear":true}\n')
        self.write(self.getStatusCmd())

    def encode(self, data, bookeeping=True):
        """ Encodes data properly to be sent to controller
        """
        data = data.encode('ascii')

        if data in [self.getCycleStartCmd(), self.getFeedHoldCmd()]:
            pass
        elif bookeeping:
            dataLen = len(data)
            self._inputBufferSize = self._inputBufferSize + dataLen

            self._inputBufferPart.append(dataLen)

            if self.cmdLineOptions.vverbose:
                print "** MachIf_TinyG input buffer encode used: %d, buffer size: %d, %.2f%% full" % \
                    (dataLen, self._inputBufferSize,
                     (100 * (float(self._inputBufferSize)/self._inputBufferMaxSize)))

        return data

    def factory(self, cmd_line_options):
        return MachIf_TinyG(cmd_line_options)
