"""----------------------------------------------------------------------------
   tinyg_machif.py

   Copyright (C) 2013-2018 Wilhelm Duembeg

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

import modules.config as gc
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

TINYG_STAT_CODE_2_STR_DICT = {
    0: "OK",
    1: "ERROR",
    2: "EAGAIN",
    3: "NOOP",
    4: "COMPLETE",
    5: "TERMINATE",
    6: "RESET",
    7: "EOL",
    8: "EOF",
    9: "FILE_NOT_OPEN",
    10: "FILE_SIZE_EXCEEDED",
    11: "NO_SUCH_DEVICE",
    12: "BUFFER_EMPTY",
    13: "BUFFER_FULL",
    14: "BUFFER_FULL_FATAL",
    15: "INITIALIZING",
    16: "ENTERING_BOOT_LOADER",
    17: "FUNCTION_IS_STUBBED",
    18: "Reserved",
    19: "Reserved",

    # Internal System Errors
    20: "INTERNAL_ERROR",
    21: "INTERNAL_RANGE_ERROR",
    22: "FLOATING_POINT_ERROR",
    23: "DIVIDE_BY_ZERO",
    24: "INVALID_ADDRESS",
    25: "READ_ONLY_ADDRESS",
    26: "INIT_FAIL",
    27: "ALARMED",
    28: "FAILED_TO_GET_PLANNER_BUFFER",
    29: "GENERIC_EXCEPTION_REPORT",
    30: "PREP_LINE_MOVE_TIME_IS_INFINITE",
    31: "PREP_LINE_MOVE_TIME_IS_NAN",
    32: "FLOAT_IS_INFINITE",
    33: "FLOAT_IS_NAN",
    34: "PERSISTENCE_ERROR",
    35: "BAD_STATUS_REPORT_SETTING",
    36: "Reserved",
    89: "Reserved",

    # Assertion Failures	Build down from     99: "until",
    90: "CONFIG_ASSERTION_FAILURE",
    91: "XIO_ASSERTION_FAILURE",
    92: "ENCODER_ASSERTION_FAILURE",
    93: "STEPPER_ASSERTION_FAILURE",
    94: "PLANNER_ASSERTION_FAILURE",
    95: "CANONICAL_MACHINE",
    96: "CONTROLLER_ASSERTION_FAILURE",
    97: "STACK_OVERFLOW",
    98: "MEMORY_FAULT",
    99: "GENERIC_ASSERTION_FAILURE",

    # Application and Data Input Errors -------------------------

    # Generic Data Input Errors
    100: "UNRECOGNIZED_NAME",
    101: "INVALID_OR_MALFORMED_COMMAND",
    102: "BAD_NUMBER_FORMAT",
    103: "BAD_UNSUPPORTED_TYPE",
    104: "PARAMETER_IS_READ_ONLY",
    105: "PARAMETER_CANNOT_BE_READ",
    106: "COMMAND_NOT_ACCEPTED",
    107: "INPUT_EXCEEDS_MAX_LENGTH",
    108: "INPUT_LESS_THAN_MIN_VALUE",
    109: "INPUT_EXCEEDS_MAX_VALUE",
    110: "INPUT_VALUE_RANGE_ERROR",
    111: "JSON_SYNTAX_ERROR",
    112: "JSON_TOO_MANY_PAIRS",
    113: "JSON_TOO_LONG",
    114: "Reserved",
    129: "Reserved",

    # GCODE Errors and Warnings	Most are from NIST
    130: "GCODE_GENERIC_INPUT_ERROR",
    131: "GCODE_COMMAND_UNSUPPORTED",
    132: "MCODE_COMMAND_UNSUPPORTED",
    133: "GCODE_MODAL_GROUP_VIOLATION",
    134: "GCODE_AXIS_IS_MISSING",
    135: "GCODE_AXIS_CANNOT_BE_PRESENT",
    136: "GCODE_AXIS_IS_INVALID",
    137: "GCODE_AXIS_IS_NOT_CONFIGURED",
    138: "GCODE_AXIS_NUMBER_IS_MISSING",
    139: "GCODE_AXIS_NUMBER_IS_INVALID",
    140: "GCODE_ACTIVE_PLANE_IS_MISSING",
    141: "GCODE_ACTIVE_PLANE_IS_INVALID",
    142: "GCODE_FEEDRATE_NOT_SPECIFIED",
    143: "GCODE_INVERSE_TIME_MODE",
    144: "GCODE_ROTARY_AXIS",
    145: "GCODE_G53_WITHOUT_G0_OR_G1",
    146: "REQUESTED_VELOCITY",
    147: "CUTTER_COMPENSATION",
    148: "PROGRAMMED_POINT",
    149: "SPINDLE_SPEED_BELOW_MINIMUM",
    150: "SPINDLE_SPEED_MAX_EXCEEDED",
    151: "S_WORD_IS_MISSING",
    152: "S_WORD_IS_INVALID",
    153: "SPINDLE_MUST_BE_OFF",
    154: "SPINDLE_MUST_BE_TURNING",
    155: "ARC_SPECIFICATION_ERROR",
    156: "ARC_AXIS_MISSING",
    157: "ARC_OFFSETS_MISSING",
    158: "ARC_RADIUS",
    159: "ARC_ENDPOINT",
    160: "P_WORD_IS_MISSING",
    161: "P_WORD_IS_INVALID",
    162: "P_WORD_IS_ZERO",
    163: "P_WORD_IS_NEGATIVE",
    164: "P_WORD_IS_NOT_AN_INTEGER",
    165: "P_WORD_IS_NOT_VALID_TOOL_NUMBER",
    166: "D_WORD_IS_MISSING",
    167: "D_WORD_IS_INVALID",
    168: "E_WORD_IS_MISSING",
    169: "E_WORD_IS_INVALID",
    170: "H_WORD_IS_MISSING",
    171: "H_WORD_IS_INVALID",
    172: "L_WORD_IS_MISSING",
    173: "L_WORD_IS_INVALID",
    174: "Q_WORD_IS_MISSING",
    175: "Q_WORD_IS_INVALID",
    176: "R_WORD_IS_MISSING",
    177: "R_WORD_IS_INVALID",
    178: "T_WORD_IS_MISSING",
    179: "T_WORD_IS_INVALID",
    180: "Reserved",
    199: "Reserved",

    # TinyG Errors and Warnings
    200: "GENERIC_ERROR",
    201: "MINIMUM_LENGTH_MOVE",
    202: "MINIMUM_TIME_MOVE",
    203: "MACHINE_ALARMED",
    204: "LIMIT_SWITCH_HIT",
    205: "PLANNER_FAILED_TO_CONVERGE",
    206: "Reserved",
    219: "Reserved",
    220: "SOFT_LIMIT_EXCEEDED",
    221: "SOFT_LIMIT_EXCEEDED_XMIN",
    222: "SOFT_LIMIT_EXCEEDED_XMAX",
    223: "SOFT_LIMIT_EXCEEDED_YMIN",
    224: "SOFT_LIMIT_EXCEEDED_YMAX",
    225: "SOFT_LIMIT_EXCEEDED_ZMIN",
    226: "SOFT_LIMIT_EXCEEDED_ZMAX",
    227: "SOFT_LIMIT_EXCEEDED_AMIN",
    228: "SOFT_LIMIT_EXCEEDED_AMAX",
    229: "SOFT_LIMIT_EXCEEDED_BMIN",
    230: "SOFT_LIMIT_EXCEEDED_BMAX",
    231: "SOFT_LIMIT_EXCEEDED_CMIN",
    232: "SOFT_LIMIT_EXCEEDED_CMAX",
    233: "Reserved",
    239: "Reserved",
    240: "HOMING_CYCLE_FAILED",
    241: "HOMING_ERROR_BAD_OR_NO_AXIS",
    242: "HOMING_ERROR_SWITCH_MISCONFIGURATION",
    243: "HOMING_ERROR_ZERO_SEARCH_VELOCITY",
    244: "HOMING_ERROR_ZERO_LATCH_VELOCITY",
    245: "HOMING_ERROR_TRAVEL_MIN_MAX_IDENTICAL",
    246: "HOMING_ERROR_NEGATIVE_LATCH_BACKOFF",
    247: "HOMING_ERROR_SEARCH_FAILED",
    248: "Reserved",
    249: "Reserved",
    250: "PROBE_CYCLE_FAILED",
    251: "PROBE_ENDPOINT",
    252: "JOGGING_CYCLE_FAILED",
}


class MachIf_TinyG(mi.MachIf_Base):
    """------------------------------------------------------------------------
    MachIf_TinyG:

    TinyG machine interface.

    ID = 1100
    Name = "TinyG"

    ------------------------------------------------------------------------"""

    """------------------------------------------------------------------------
    Notes:

    input buffer max size = 255
    input buffer init size = 0
    input buffer watermark = 90%

    Init buffer to (-1) when connecting it needs a initial '\n' that
    should not be counted
    ------------------------------------------------------------------------"""

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
        9: 'Homing',
        10: 'Jog',
        11: 'InterLock',
        12: 'Shutdown',
        13: 'Panic',
    }

    def __init__(self):
        super(MachIf_TinyG, self).__init__(ID, NAME, BUFFER_MAX_SIZE,
                                           BUFFER_INIT_VAL,
                                           BUFFER_WATERMARK_PRCNT)

        self._inputBufferPart = list()

        # list of commands
        self.cmdClearAlarm = '{"clear":true}\n'
        self.cmdInitComm = '{"sys":null}\n'
        self.cmdQueueFlushCmd = "%"
        self.cmdSetAxisCmd = "G28.3"
        self.cmdStatus = '{"sr":null}\n'
        self.cmdSystemInfo = '{"sys":null}\n'

    def _init(self):
        """ Init object variables, ala soft-reset in hw
        """
        super(MachIf_TinyG, self)._reset(BUFFER_MAX_SIZE,
                                         BUFFER_INIT_VAL,
                                         BUFFER_WATERMARK_PRCNT)

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

                    if 'fb' in sys and 'fv' in sys:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                            self.logger.info("found version fb[%s] "
                                             "fv[%s]" % (sys['fb'], sys['fv']))

                    if 'id' in sys:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                            self.logger.info("found device init string [%s]" %
                                             ("id:"+sys['id']))

                        dataDict['r']['init'] = "id:"+sys['id']

                if 'id' in r:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                        self.logger.info("found device init string [%s]" %
                                         ("id:"+r['id']))

                    dataDict['r']['init'] = "id:"+r['id']

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

                sr['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

            if 'f' in dataDict:
                stat_code = dataDict['f'][1]
                if stat_code > 0:
                    stat_str = '{"st":%d,"msg":"%s"}\n' % (
                        stat_code,
                        TINYG_STAT_CODE_2_STR_DICT.get(
                            stat_code, "Unknown"))
                    self.add_event(gc.EV_RXDATA, stat_str)

                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                        error_msg = "found error [%s]" % stat_str
                        self.logger.info(error_msg)

        except ValueError:
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

            if 'sr' not in dataDict:
                sr = dict()
                dataDict['sr'] = sr

            sr['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

            for pos in [posx, posy, posz, posa]:
                if pos is not None:
                    dataDict['sr'][pos.group(1)] = float(pos.group(2))
                    match = True

            if vel is not None:
                dataDict['sr']['vel'] = float(vel.group(1))
                match = True

            if stat is not None:
                dataDict['sr']['stat'] = self.stat_dict.get(
                    int(stat.group(1)), "Uknown")
                match = True

            if not match:
                pass
            #     if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
            #         self.logger.info("cannot decode data!! [%s]" %
            #                          data.strip())

        if 'r' in dataDict:
            # checking for count in "f" response doesn't always work as
            # expected and broke on edge branch it was never specify that
            # this was the functionality so abandoning that solution

            if self._inputBufferPart:
                bufferPart = self._inputBufferPart.pop(0)

                self._inputBufferSize = self._inputBufferSize - bufferPart

                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                    prcnt = float(self._inputBufferSize) / \
                            self._inputBufferMaxSize
                    self.logger.info("decode, input buffer free: %d,"
                                     "buffer size: %d, %.2f%% full" % (
                                         bufferPart,
                                         self._inputBufferSize,
                                         (100*prcnt)))
            else:
                pass
                # print "hmmm this could be a problem"
                # print dataDict

        if 'sr' in dataDict:
            sr = dataDict['sr']
        else:
            sr = {}
            dataDict['sr'] = sr

        sr['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

        return dataDict

    def encode(self, data, bookeeping=True):
        """ Encodes data properly to be sent to controller
        """
        data = data.encode('ascii')

        data = super(MachIf_TinyG, self).encode(data)

        if data in [self.getCycleStartCmd(), self.getFeedHoldCmd()]:
            pass
        elif bookeeping:
            dataLen = len(data)
            self._inputBufferSize = self._inputBufferSize + dataLen

            self._inputBufferPart.append(dataLen)

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                prcnt = float(self._inputBufferSize)/self._inputBufferMaxSize
                self.logger.info("encode, input buffer used: %d, buffer "
                                 "size: %d, %.2f%% full" % (
                                    dataLen,
                                    self._inputBufferSize,
                                    (100*prcnt)))
        return data

    def factory(self):
        return MachIf_TinyG()
