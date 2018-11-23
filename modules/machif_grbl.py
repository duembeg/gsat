"""----------------------------------------------------------------------------
   machif_grbl.py

   Copyright (C) 2013-2018 Wilhelm Duembeg

   This file is part of gsat. gsat is a cross-platform GCODE debug/step for
   grbl like GCODE interpreters. With features similar to software debuggers.
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

import datetime as dt
import re

import modules.config as gc
import modules.machif as mi

""" Global values for this module
"""
# Numeric reperecentation of state, cehcking strings all the time is not
# fastest way...
GRBL_STATE_UKNOWN = 1000
GRBL_STATE_IDLE = 1010
GRBL_STATE_RUN = 1020
GRBL_STATE_HOLD = 1030
GRBL_STATE_JOG = 1040
GRBL_STATE_ALRARM = 1050
GRBL_STATE_DOOR = 1060
GRBL_STATE_CHECK = 1070
GRBL_STATE_HOME = 1080
GRBL_STATE_SLEEP = 1090
GRBL_STATE_STOP = 1100

GRBL_ERROR_CODE_2_STR_DICT = {
    1: "GCODE words consist of a letter and a value. Letter was not found",
    2: "Numeric value format is not valid or missing an expected value",
    3: "grbl '$' system command was not recognized or supported",
    4: "Negative value received for an expected positive value",
    5: "Homing cycle is not enabled via settings",
    6: "Minimum step pulse time must be greater than 3 usec",
    7: "EEPROM read failed. Reset and restored to default values",
    8: "grbl '$' command cannot be used unless Grbl is IDLE. Ensures smooth "
       "operation during a job",
    9: "GCODE locked out during alarm or jog state",
    10: "Soft limits cannot be enabled without homing also enabled",
    11: "Max characters per line exceeded. Line was not processed and "
        "executed",
    12: "(Compile Option) grbl '$' setting value exceeds the maximum step "
        "rate supported",
    13: "Safety door detected as opened and door state initiated",
    14: "(grbl-Mega Only) Build info or startup line exceeded EEPROM line "
        "length limit",
    15: "Jog target exceeds machine travel. Command ignored",
    16: "Jog command with no '=' or contains prohibited GCODE",
    20: "Unsupported or invalid GCODE command found in block",
    21: "More than one GCODE command from same modal group found in block",
    22: "Feed rate has not yet been set or is undefined",
    23: "GCODE command in block requires an integer value",
    24: "Two GCODE commands that both require the use of the XYZ axis words "
        "were detected in the block",
    25: "A GCODE word was repeated in the block",
    26: "A GCODE command implicitly or explicitly requires XYZ axis words "
        "in the block, but none were detected",
    27: "N line number value is not within the valid range of 1 - 9,999,999",
    28: "A GCODE command was sent, but is missing some required P or L "
        "value words in the line",
    29: "grbl supports six work coordinate systems G54-G59. G59.1, G59.2, "
        "and G59.3 are not supported",
    30: "The G53 GCODE command requires either a G0 seek or G1 feed motion "
        "mode to be active. A different motion was active",
    31: "There are unused axis words in the block and G80 motion mode cancel "
        "is active",
    32: "A G2 or G3 arc was commanded but there are no XYZ axis words in the "
        "selected plane to trace the arc",
    33: "The motion command has an invalid target. G2, G3, and G38.2 "
        "generates this error, if the arc is impossible to generate or if "
        "the probe target is the current position",
    34: "A G2 or G3 arc, traced with the radius definition, had a "
        "mathematical error when computing the arc geometry. Try either "
        "breaking up the arc into semi-circles or quadrants, or redefine "
        "them with the arc offset definition",
    35: "A G2 or G3 arc, traced with the offset definition, is missing the "
        "IJK offset word in the selected plane to trace the arc",
    36: "There are unused, leftover GCODE words that aren't used by any "
        "command in the block",
    37: "The G43.1 dynamic tool length offset command cannot apply an "
        "offset to an axis other than its configured axis. The Grbl default "
        "axis is the Z-axis",
    38: "An invalid tool number sent to the parser"
}

GRBL_ALARM_CODE_2_STR_DICT = {
    1: "Hard limit triggered. Machine position is likely lost due to sudden "
       "and immediate halt. Re-homing is highly recommended",
    2: "GCODE motion target exceeds machine travel. Machine position safely "
       "retained. Alarm may be unlocked",
    3: "Reset while in motion. grbl cannot guarantee position. Lost steps "
       "are likely. Re-homing is highly recommended",
    4: "Probe fail. The probe is not in the expected initial state before "
       "starting probe cycle, where G38.2 and G38.3 is not triggered and "
       "G38.4 and G38.5 is triggered",
    5: "Probe fail. Probe did not contact the workpiece within the "
       "programmed travel for G38.2 and G38.4",
    6: "Homing fail. Reset during active homing cycle",
    7: "Homing fail. Safety door was opened during active homing cycle",
    8: "Homing fail. Cycle failed to clear limit switch when pulling off. "
       "Try increasing pull-off setting or check wiring",
    9: "Homing fail. Could not find limit switch within search distance. "
       "Defined as 1.5 * max_travel on search and 5 * pulloff on locate "
       "phases",
}

GRBL_HOLD_CODE_2_STR_DICT = {
    0: "Hold complete. Ready to resume",
    1: "Hold in-progress. Reset will throw an alarm",
}

GRBL_DOOR_CODE_2_STR_DICT = {
    0: "Door closed. Ready to resume",
    1: "Machine stopped. Door still ajar. Can't resume until closed",
    2: "Door opened. Hold (or parking retract) in-progress. Reset will "
       "throw an alarm",
    3: "Door closed and resuming. Restoring from park, if applicable. "
       "Reset will throw an alarm",
}

GRBL_CONFIG_2_STR_DICT = {
    0: "Step pulse, microseconds",
    1: "Step idle delay, milliseconds",
    2: "Step port invert, mask",
    3: "Direction port invert, mask",
    4: "Step enable invert, boolean",
    5: "Limit pins invert, boolean",
    6: "Probe pin invert, boolean",
    10: "Status report, mask",
    11: "Junction deviation, mm",
    12: "Arc tolerance, mm",
    13: "Report inches, boolean",
    20: "Soft limits, boolean",
    21: "Hard limits, boolean",
    22: "Homing cycle, boolean",
    23: "Homing dir invert, mask",
    24: "Homing feed, mm/min",
    25: "Homing seek, mm/min",
    26:	"Homing debounce, milliseconds",
    27: "Homing pull-off, mm",
    30: "Max spindle speed, RPM",
    31: "Min spindle speed, RPM",
    32: "Laser mode, boolean",
    100: "X steps/mm",
    101: "Y steps/mm",
    102: "Z steps/mm",
    110: "X Max rate, mm/min",
    111: "Y Max rate, mm/min",
    112: "Z Max rate, mm/min",
    120: "X Acceleration, mm/sec^2",
    121: "Y Acceleration, mm/sec^2",
    122: "Z Acceleration, mm/sec^2",
    130: "X Max travel, mm",
    131: "Y Max travel, mm",
    132: "Z Max travel, mm",
}

# This values are only use to initialize or reset base class.
# base class has internal variables tor track these
ID = 1000
NAME = "grbl"
BUFFER_MAX_SIZE = 127
BUFFER_INIT_VAL = 0
BUFFER_WATERMARK_PRCNT = 0.90


class MachIf_GRBL(mi.MachIf_Base):
    """-----------------------------------------------------------------------
    MachIf_GRBL:

    grbl machine interface

    ID = 1000
    Name = "grbl"

    -----------------------------------------------------------------------"""

    """-----------------------------------------------------------------------
    Notes:

    Input buffer max size = 127
    Input buffer init size = 0
    Input buffer watermark = 90%

    per GRBL 0.9 and 1.1 grbl input buffer is 127 bytes (buffer includes
    all characters including nulls and new line)

    To be able to track working position changet GRBL settigs to display work
    position as oppose to machine position from 1.1f use $10=0 to configure...

    -----------------------------------------------------------------------"""

    stat_dict = {
        "Idle": GRBL_STATE_IDLE,
        "Run": GRBL_STATE_RUN,
        "Hold": GRBL_STATE_HOLD,
        "Jog": GRBL_STATE_JOG,
        "Alarm": GRBL_STATE_ALRARM,
        "Door": GRBL_STATE_DOOR,
        "Check": GRBL_STATE_CHECK,
        "Home": GRBL_STATE_HOME,
        "Sleep": GRBL_STATE_SLEEP,
        "Stop": GRBL_STATE_STOP
    }

    # grbl version, example "[VER:x.x.x:]"
    reGrblVersion = re.compile(r'\[VER:(.*):\]')

    # grbl init, example "Grbl 0.8c ['$' for help]"
    reGrblInitStr = re.compile(r'(Grbl\s*(.*)\s*\[.*\])')

    # status,
    # quick re check to avoid multiple checks, speeds things up
    reGrblOneMachineStatus = re.compile(r'pos', re.I)

    # GRBL example
    #   "<Run,MPos:20.163,0.000,0.000,WPos:20.163,0.000,0.000>"
    #   "<Hold:29|WPos:20.163,0.000,20.000>"
    # self.reGrblMachineStatus = re.compile(
    #    r'<(\w+)[,\|].*WPos:([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+),'\
    #    '([+-]{0,1}\d+\.\d+)')
    reGrblMachineStatus = re.compile(
        r'<(\w+)[:]{0,1}[\d]*[,\|].*[W|M]Pos:([+-]{0,1}\d+\.\d+),'
        r'([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+)\|FS:(\d+),(\d+)')

    """
        To be able to track working position changet GRBL settigs to display
        work position as oppose to machine position from 1.1f use $10=0 to
        configure...
    """

    # grbl ack, example  "ok"
    reGrblMachineAck = re.compile(r'^ok\s$')

    # grbl error, example  "error:20", "error: Unsupported command"
    reGrblMachineError = re.compile(r'^error:(\d+)\s$')

    # grbl init, example "ALARM:x"
    reGrblAlarm = re.compile(r'ALARM:(\d+)')

    # grbl config settings
    reGrblConfig = re.compile(r'^\$(\d+)=\d+.*\s*')

    def __init__(self):
        super(MachIf_GRBL, self).__init__(ID, NAME,
                                          BUFFER_MAX_SIZE, BUFFER_INIT_VAL,
                                          BUFFER_WATERMARK_PRCNT)

        self._inputBufferPart = list()

        self.machineAutoRefresh = False
        self.machineAutoRefreshPeriod = 200
        self.machineStatus = GRBL_STATE_UKNOWN

        self.autoStatusNextMicro = None

        self.initStringDetectFlag = False

        # list of commads
        self.cmdClearAlarm = '$X\n'
        self.cmdHome = '$H\n'
        self.cmdInitComm = self.cmdReset

        # no way to clean quque, this will do soft reset
        # *stoping coolean and spindle with it.
        self.cmdQueueFlush = self.cmdReset

        self.cmdPostInit = '$I\n'
        self.cmdStatus = '?'

    def _init(self):
        """ Init object variables, ala soft-reset in hw
        """
        super(MachIf_GRBL, self)._reset(
            BUFFER_MAX_SIZE, BUFFER_INIT_VAL, BUFFER_WATERMARK_PRCNT
        )

        self._inputBufferPart = list()

    def decode(self, data):
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

        status = self.reGrblMachineStatus.match(data)
        if status is not None:
            statusData = status.groups()
            sr = {}

            # remove the "?" used to get status notice no "\n"
            bufferPart = 1

            if (self._inputBufferSize >= bufferPart):
                self._inputBufferSize = self._inputBufferSize - bufferPart
            else:
                bufferPart = 0

            sr['stat'] = statusData[0]
            sr['posx'] = float(statusData[1])
            sr['posy'] = float(statusData[2])
            sr['posz'] = float(statusData[3])
            sr['vel'] = float(statusData[4])

            dataDict['sr'] = sr

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                self.logger.info("status match %s" % str(statusData))
                prcnt = float(self._inputBufferSize)/self._inputBufferMaxSize
                self.logger.info("decode, input buffer free: %d, buffer size: "
                                 "%d, %.2f%% full" % (
                                        bufferPart,
                                        self._inputBufferSize,
                                        (100*prcnt)))

            # check on status change
            decodedStatus = self.stat_dict.get(
                statusData[0], GRBL_STATE_UKNOWN)

            if self.machineStatus != decodedStatus:
                if decodedStatus in [GRBL_STATE_RUN, GRBL_STATE_JOG]:
                    msec = self.machineAutoRefreshPeriod * 1000
                    self.autoStatusNextMicro = dt.datetime.now() + \
                        dt.timedelta(microseconds=msec)

                self.machineStatus = decodedStatus

            sr['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

        ack = self.reGrblMachineAck.search(data)
        if ack is not None:
            bufferPart = 0

            if len(self._inputBufferPart) > 0:
                bufferPart = self._inputBufferPart.pop(0)

            self._inputBufferSize = self._inputBufferSize - bufferPart

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                self.logger.info("founf acknowledge [%s]" % data.strip())

            r = {}
            dataDict['r'] = r
            dataDict['f'] = [0, 0, bufferPart]
            dataDict['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                prcnt = float(self._inputBufferSize)/self._inputBufferMaxSize
                self.logger.info("decode, input buffer free: %d, buffer size: "
                                 "%d, %.2f%% full" % (
                                        bufferPart,
                                        self._inputBufferSize,
                                        (100*prcnt)))

        alarm = self.reGrblAlarm.search(data)
        if alarm is not None:
            if 'sr' in dataDict:
                sr = dataDict.get('sr')
            else:
                sr = {}

            sr['stat'] = "Alarm"
            decodedStatus = self.stat_dict.get(sr['stat'], GRBL_STATE_UKNOWN)

            sr['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

            dataDict['sr'] = sr

            alarm_code = alarm.group(1).strip()
            if alarm_code.isdigit():
                alarm_code = int(alarm_code)
                alarm_str = "[MSG: %s]\n" % (
                    GRBL_ALARM_CODE_2_STR_DICT.get(alarm_code, "Uknown")
                )
                dataDict['rx_data_info'] = alarm_str
            else:
                error_code = -1

        error = self.reGrblMachineError.search(data)
        if error is not None:
            bufferPart = 0

            if len(self._inputBufferPart) > 0:
                bufferPart = self._inputBufferPart.pop(0)

            self._inputBufferSize = self._inputBufferSize - bufferPart

            if 'r' not in dataDict:
                r = {}
                dataDict['r'] = r

            error_code = error.group(1).strip()
            if error_code.isdigit():
                error_code = int(error_code)
                err_str = "[MSG: %s]\n" % (
                    GRBL_ERROR_CODE_2_STR_DICT.get(error_code, "Unknown")
                )

                dataDict['rx_data_info'] = err_str

            else:
                error_code = -1

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                error_msg = "found error [%s]" % data.strip()
                if 'rx_data_info' in dataDict:
                    error_msg = "found %s, %s" % (
                                data.strip(),
                                dataDict['rx_data_info'].strip())
                self.logger.info(error_msg)

            dataDict['f'] = [0, error_code, bufferPart, error_code]
            dataDict['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                prcnt = float(self._inputBufferSize)/self._inputBufferMaxSize
                self.logger.info("decode, input buffer free: %d, buffer size: "
                                 "%d, %.2f%% full" % (
                                        bufferPart,
                                        self._inputBufferSize,
                                        (100*prcnt)))

        version = self.reGrblVersion.match(data)
        if version is not None:
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                self.logger.info("found version [%s]" %
                                 version.group(1).strip())

            if 'r' not in dataDict:
                r = {}
                dataDict['r'] = r

            dataDict['r']['fb'] = version.group(1)
            dataDict['f'] = [0, 0, 0]
            dataDict['ib'] = [self._inputBufferMaxSize, self._inputBufferSize]

        initStr = self.reGrblInitStr.match(data)
        if initStr is not None:
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                self.logger.info("found device init string [%s]" %
                                 initStr.group(1).strip())

            self.initStringDetectFlag = True

            if 'r' not in dataDict:
                r = {}
                dataDict['r'] = r

            dataDict['r']['init'] = initStr.group(1).strip()

        config = self.reGrblConfig.match(data)
        if config is not None:
            data_len = len(data)
            fill = 20 - data_len
            dataDict['rx_data_info'] = "%s%s\n" % (
                ' '*fill,
                GRBL_CONFIG_2_STR_DICT.get(int(config.group(1)), "")
            )

        return dataDict

    def doHome(self, dict_axis):
        if 'x' in dict_axis and 'y' in dict_axis and 'z' in dict_axis:
            self.eventPut(gc.EV_SER_TXDATA, self.cmdHome)
            self.write(self.cmdHome)
            self.write(self.cmdStatus)
        else:
            msg = "!! grbl doesn't support single/partial axis homing."
            self.eventPut(gc.EV_SER_RXDATA, msg)

    def doInitComm(self):
        """ soft reset grbl to get it to talk to is hw version info
            not all arduino boards reset on connect.
        """
        self.write(self.cmdInitComm)
        self._init()

    def encode(self, data, bookeeping=True):
        """ Encodes data properly to be sent to controller
        """
        if len(data) == 0:
            return data

        data = data.encode('ascii')

        data = super(MachIf_GRBL, self).encode(data)

        # handle special cases due to status in cmd line and how GRBL
        # reports deals with this. if not careful we might get two status
        # from a single line but is not consistence on host this works.
        # for this reason if we find "?" on the line will remove all but one
        # also add 1 to the buffer since the status will remove 1 and
        # the acknowledged will remove the length of the line. If this is
        # not done the "?" will be counted twice when removing from
        # input buffer usage.
        if data.find(self.cmdStatus) != -1:
            # maybe more then one, replace all by ""
            data = data.replace(self.cmdStatus, "")
            data = "".join([data, self.cmdStatus])  # only allow one

            if bookeeping:
                self._inputBufferSize = self._inputBufferSize + 1

        if data == self.cmdStatus and bookeeping:
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
                prcnt = float(self._inputBufferSize)/self._inputBufferMaxSize
                self.logger.info("encode, input buffer used: %d, buffer "
                                 "size: %d, %.2f%% full" % (
                                    1,
                                    self._inputBufferSize,
                                    (100*prcnt)))

        elif data in [self.getCycleStartCmd(), self.getFeedHoldCmd()]:
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
        return MachIf_GRBL()

    def init(self):
        super(MachIf_GRBL, self).init()
        self.machineAutoRefresh = gc.CONFIG_DATA.get('/machine/AutoRefresh')
        self.machineAutoRefreshPeriod = gc.CONFIG_DATA.get(
            '/machine/AutoRefreshPeriod')

    def tick(self):
        # check if is time for auto-refresh and send get status cmd and
        # prepare next refresh time
        if self.autoStatusNextMicro is not None:
            if self.machineStatus in [GRBL_STATE_RUN, GRBL_STATE_JOG]:
                tnow = dt.datetime.now()
                tnowMilli = tnow.second*1000 + tnow.microsecond/1000
                tdeltaMilli = self.autoStatusNextMicro.second * \
                    1000 + self.autoStatusNextMicro.microsecond/1000
                if long(tnowMilli - tdeltaMilli) >= 0:
                    if self.okToSend(self.cmdStatus):
                        super(MachIf_GRBL, self).write(self.cmdStatus)

                    msec = self.machineAutoRefreshPeriod * 1000
                    self.autoStatusNextMicro = dt.datetime.now() + \
                        dt.timedelta(microseconds=msec)
            else:
                self.autoStatusNextMicro = None

        if self.machineAutoRefresh != gc.CONFIG_DATA.get(
                '/machine/AutoRefresh'):
            # depending on current state do appropriate action
            if not self.machineAutoRefresh:
                if self.okToSend(self.cmdStatus):
                    super(MachIf_GRBL, self).write(self.cmdStatus)

                msec = self.machineAutoRefreshPeriod * 1000
                self.autoStatusNextMicro = dt.datetime.now() + \
                    dt.timedelta(microseconds=msec)
            else:
                self.autoStatusNextMicro = None

            # finally update local variable
            self.machineAutoRefresh = gc.CONFIG_DATA.get(
                    '/machine/AutoRefresh')

        if self.machineAutoRefreshPeriod != \
           gc.CONFIG_DATA.get('/machine/AutoRefreshPeriod'):
            self.machineAutoRefreshPeriod = gc.CONFIG_DATA.get(
                '/machine/AutoRefreshPeriod')

        # check for init condition, take action, and reset init condition
        if (self.initStringDetectFlag):
            self.initStringDetectFlag = False
            self.write(self.cmdPostInit)
            self._init()

    def write(self, txData, raw_write=False):
        askForStatus = False
        bytesSent = 0

        # moving to active state get at least one status msg
        if self.machineStatus in [
            GRBL_STATE_IDLE, GRBL_STATE_STOP, GRBL_STATE_HOME,
            GRBL_STATE_SLEEP, GRBL_STATE_HOLD
        ]:
            askForStatus = True

        bytesSent = super(MachIf_GRBL, self).write(txData, raw_write)

        if askForStatus and self.machineAutoRefresh:
            if self.okToSend(self.cmdStatus):
                super(MachIf_GRBL, self).write(self.cmdStatus)

            msec = self.machineAutoRefreshPeriod * 1000
            self.autoStatusNextMicro = dt.datetime.now() + \
                dt.timedelta(microseconds=msec)

        return bytesSent
