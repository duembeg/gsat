"""----------------------------------------------------------------------------
   g2core_machif.py

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

G2CORE_STAT_CODE_2_STR_DICT = {
    0: "OK",
    1: "ERROR",
    2: "EAGAIN",
    3: "NOOP",
    4: "COMPLETE",
    5: "SHUTDOWN",
    6: "PANIC",
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
    18: "ALARM",
    19: "NO_DISPLAY",

    # Internal errors and startup messages
    20: "INTERNAL_ERROR",
    21: "INTERNAL_RANGE_ERROR",
    22: "FLOATING_POINT_ERROR",
    23: "DIVIDE_BY_ZERO",
    24: "INVALID_ADDRESS",
    25: "READ_ONLY_ADDRESS",
    26: "INIT_FAILURE",
    27: "ERROR_27",
    28: "FAILED_TO_GET_PLANNER_BUFFER",
    29: "GENERIC_EXCEPTION_REPORT",

    30: "PREP_LINE_MOVE_TIME_IS_INFINITE",
    31: "PREP_LINE_MOVE_TIME_IS_NAN",
    32: "FLOAT_IS_INFINITE",
    33: "FLOAT_IS_NAN",
    34: "PERSISTENCE_ERROR",
    35: "BAD_STATUS_REPORT_SETTING",
    36: "FAILED_GET_PLANNER_BUFFER",

    # Assertion failures - build down from 99 until they meet the
    # system internal errors
    88: "BUFFER_FREE_ASSERTION_FAILURE",
    89: "STATE_MANAGEMENT_ASSERTION_FAILURE",
    90: "CONFIG_ASSERTION_FAILURE",
    91: "XIO_ASSERTION_FAILURE",
    92: "ENCODER_ASSERTION_FAILURE",
    93: "STEPPER_ASSERTION_FAILURE",
    94: "PLANNER_ASSERTION_FAILURE",
    95: "CANONICAL_MACHINE_ASSERTION_FAILURE",
    96: "CONTROLLER_ASSERTION_FAILURE",
    97: "STACK_OVERFLOW",
    98: "MEMORY_FAULT",
    99: "GENERIC_ASSERTION_FAILURE",

    # Application and data input errors

    # Generic data input errors
    100: "UNRECOGNIZED_NAME",
    101: "INVALID_OR_MALFORMED_COMMAND",
    102: "BAD_NUMBER_FORMAT",
    103: "UNSUPPORTED_TYPE",
    104: "PARAMETER_IS_READ_ONLY",
    105: "PARAMETER_CANNOT_BE_READ",
    106: "COMMAND_NOT_ACCEPTED",
    107: "INPUT_EXCEEDS_MAX_LENGTH",
    108: "INPUT_LESS_THAN_MIN_VALUE",
    109: "INPUT_EXCEEDS_MAX_VALUE",
    110: "INPUT_VALUE_RANGE_ERROR",

    111: "JSON_SYNTAX_ERROR",
    112: "JSON_TOO_MANY_PAIRS",
    113: "JSON_OUTPUT_TOO_LONG",
    114: "NESTED_TXT_CONTAINER",
    115: "MAX_DEPTH_EXCEEDED",
    116: "VALUE_TYPE_ERROR",

    # Gcode errors and warnings (Most originate from NIST - by concept,
    # not number)
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
    143: "GCODE_INVERSE_TIME_MODE_CANNOT_BE_USED",
    144: "GCODE_ROTARY_AXIS_CANNOT_BE_USED",
    145: "GCODE_G53_WITHOUT_G0_OR_G1",
    146: "REQUESTED_VELOCITY_EXCEEDS_LIMITS",
    147: "CUTTER_COMPENSATION_CANNOT_BE_ENABLED",
    148: "PROGRAMMED_POINT_SAME_AS_CURRENT_POINT",
    149: "SPINDLE_SPEED_BELOW_MINIMUM",

    150: "SPINDLE_SPEED_MAX_EXCEEDED",
    151: "SPINDLE_MUST_BE_OFF",
    152: "SPINDLE_MUST_BE_TURNING",
    153: "ARC_ERROR_RESERVED",
    154: "ARC_HAS_IMPOSSIBLE_CENTER_POINT",
    155: "ARC_SPECIFICATION_ERROR",
    156: "ARC_AXIS_MISSING_FOR_SELECTED_PLANE",
    157: "ARC_OFFSETS_MISSING_FOR_SELECTED_PLANE",
    158: "ARC_RADIUS_OUT_OF_TOLERANCE",
    159: "ARC_ENDPOINT_IS_STARTING_POINT",

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
    178: "S_WORD_IS_MISSING",
    179: "S_WORD_IS_INVALID",

    180: "T_WORD_IS_MISSING",
    181: "T_WORD_IS_INVALID",

    # g2core errors and warnings
    200: "GENERIC_ERROR",
    201: "MINIMUM_LENGTH_MOVE",
    202: "MINIMUM_TIME_MOVE",
    203: "LIMIT_SWITCH_HIT",
    204: "COMMAND_REJECTED_BY_ALARM",
    205: "COMMAND_REJECTED_BY_SHUTDOWN",
    206: "COMMAND_REJECTED_BY_PANIC",
    207: "KILL_JOB",
    208: "NO_GPIO",

    209: "TEMPERATURE_CONTROL_ERROR",

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
    233: "SOFT_LIMIT_EXCEEDED_ARC",

    240: "HOMING_CYCLE_FAILED",
    241: "HOMING_ERROR_BAD_OR_NO_AXIS",
    242: "HOMING_ERROR_ZERO_SEARCH_VELOCITY",
    243: "HOMING_ERROR_ZERO_LATCH_VELOCITY",
    244: "HOMING_ERROR_TRAVEL_MIN_MAX_IDENTICAL",
    245: "HOMING_ERROR_NEGATIVE_LATCH_BACKOFF",
    246: "HOMING_ERROR_HOMING_INPUT_MISCONFIGURED",
    247: "HOMING_ERROR_MUST_CLEAR_SWITCHES_BEFORE_HOMING",
    248: "ERROR_248",
    249: "ERROR_249",

    250: "PROBE_CYCLE_FAILED",
    251: "PROBE_TRAVEL_TOO_SMALL",
    252: "NO_PROBE_SWITCH_CONFIGURED",
    253: "MULTIPLE_PROBE_SWITCHES_CONFIGURED",
    254: "PROBE_SWITCH_ON_ABC_AXIS",

    255: "ERROR_255",
}

""" Global values for this module
"""
# This values are only use to initialize or reset base class.
# base class has internal variables tor track these
ID = 1200
NAME = "g2core"
BUFFER_MAX_SIZE = 255
BUFFER_INIT_VAL = 0
BUFFER_WATERMARK_PRCNT = 0.90


class MachIf_g2core(mi.MachIf_Base):
    """------------------------------------------------------------------------
    g2core machine interface

    ID = 1200
    Name = "g2core"

    ------------------------------------------------------------------------"""

    """------------------------------------------------------------------------
    Notes:

    input buffer max size = 255
    input buffer init size = 0
    input buffer watermark = 90%

    Init buffer to (1) when connecting it counts that as one char on response
    initial msg looks like
    {"r":{"fv":0.98,"fb":89.03,"hp":3,"hv":0,"id":"0213-2335-6343","msg":"SYSTEM READY"},"f":[1,0,1]}

    !!notice f[1,0,1]
    ------------------------------------------------------------------------"""

    # text mode re expressions
    reMachineAck = re.compile(r'.+ok>\s$')
    reMachinePos = re.compile(r'(\w)\s+position:\s+([+-]{0,1}\d+\.\d+)')
    reMachineVel = re.compile(r'Velocity:\s+(\d+\.\d+)')
    reMachineStat = re.compile(r'Machine state:\s+(\w+)')

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

    def __init__(self, cmd_line_options):
        super(MachIf_g2core, self).__init__(
            cmd_line_options, ID, NAME, BUFFER_MAX_SIZE, BUFFER_INIT_VAL,
            BUFFER_WATERMARK_PRCNT)

        self._inputBufferPart = list()

        # list of commads
        self.cmdClearAlarm = '{"clr":null}\n'
        self.cmdQueueFlush = '%\n'
        self.cmdStatus = '{"sr":null}\n'

    def _init(self):
        """ Init object variables, ala soft-reset in hw
        """
        super(MachIf_g2core, self)._reset(
            BUFFER_MAX_SIZE, BUFFER_INIT_VAL, BUFFER_WATERMARK_PRCNT
        )

        self._inputBufferPart = list()

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
                    sr['stat'] = self.stat_dict.get(status, "Uknown")

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
                stat_code = dataDict['f'][1]
                if stat_code > 0:
                    stat_str = '{"st":%d,"msg":"%s"}\n' % (
                        stat_code, G2CORE_STAT_CODE_2_STR_DICT.get(
                            stat_code, "Unknown"))
                    self.eventPut(gc.EV_SER_RXDATA, stat_str)

        except ValueError:
            ack = self.reMachineAck.match(data)
            pos = self.reMachinePos.match(data)
            vel = self.reMachineVel.match(data)
            stat = self.reMachineStat.match(data)

            if ack is not None:
                dataDict['r'] = {"f": [1, 0, 0]}
                dataDict['f'] = [1, 0, 0]
            else:
                if 'sr' not in dataDict:
                    dataDict['sr'] = {}

                if pos is not None:
                    dataDict['sr'][
                        "".join(["pos", pos.group(1).lower()])] = float(
                        pos.group(2))
                elif vel is not None:
                    dataDict['sr']['vel'] = float(vel.group(1))
                elif stat is not None:
                    dataDict['sr']['stat'] = stat.group(1)
                else:
                    if self.cmdLineOptions.vverbose:
                        print "** MachIf_g2core cannot decode data!! [%s]."\
                            % data

        if 'r' in dataDict:
            # checking for count in "f" response doesn't always work as
            # expected and broke on edge branch it was never specify that
            # this was the functionality so abandoning that solution

            if self._inputBufferPart:
                bufferPart = self._inputBufferPart.pop(0)

                self._inputBufferSize = self._inputBufferSize - bufferPart

                if self.cmdLineOptions.vverbose:
                    print "** MachIf_g2core input buffer decode returned: "\
                        "%d, buffer size: %d, %.2f%% full" % (
                            bufferPart, self._inputBufferSize, (
                                100 * (float(self._inputBufferSize)/self._inputBufferMaxSize)
                            )
                        )

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

        if data in [self.getCycleStartCmd(), self.getFeedHoldCmd()]:
            pass
        elif bookeeping:
            dataLen = len(data)
            self._inputBufferSize = self._inputBufferSize + dataLen

            self._inputBufferPart.append(dataLen)

            if self.cmdLineOptions.vverbose:
                print "** MachIf_g2core input buffer encode used: "\
                    "%d, buffer size: %d, %.2f%% full" % (
                        dataLen, self._inputBufferSize, (
                            100 * (float(self._inputBufferSize)/self._inputBufferMaxSize)
                        )
                    )

        return data

    def factory(self, cmd_line_options):
        return MachIf_g2core(cmd_line_options)
