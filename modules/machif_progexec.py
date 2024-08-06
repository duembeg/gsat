"""----------------------------------------------------------------------------
    machif_progexec.py

    Copyright (C) 2013 Wilhelm Duembeg

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
import threading
import time
import logging
import hashlib
import queue

import modules.config as gc
import modules.machif_config as mi


# -----------------------------------------------------------------------------
# regular expressions
# -----------------------------------------------------------------------------
gReAxis = re.compile(r'([XYZ])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

# comments example "( comment string )" or "; comment string"
gReGcodeComments = [re.compile(r'\(.*\)'), re.compile(r';.*')]

# message example "(MSG, CHANGE TOOL BIT: to drill size 0.81300 mm)"
gReGcodeMsg = re.compile(r'^\s*\(MSG,(.+)\)')


class MachIfExecuteThread(threading.Thread, gc.EventQueueIf):
    """  Threads that executes the gcode sending code to serial port. This
    thread allows the UI to continue being responsive to user input while this
    thread is busy executing program or waiting for serial events.
    Additionally it helps for user input not to disturb the rate and flow
    of data sent to the serial port.
    """

    def __init__(self, event_handler):
        """Init Worker Thread Class."""
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        self.okToPostEvents = True

        self.gcodeDataLines = []
        self.gcodeFileName = ""
        self.breakPointSet = set()
        self.initialProgramCounter = 0
        self.workingProgramCounter = 0
        self.lastWorkingProgramCounter = -1

        self.swState = gc.STATE_IDLE
        self.lastEventID = gc.EV_CMD_NULL

        self.serialWriteQueue = []

        self.machIfId = None
        self.machIfModule = None
        self.machIfState = None

        self.runTimeStart = 0
        self.runTimeElapse = 0

        self.do_init_script = False

        self.init_config()

        if event_handler is not None:
            self.add_event_listener(event_handler)

        self.logger = logging.getLogger()
        if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
            self.logger.info("init logging id:0x%x" % id(self))

        # init device module
        self.init_machine_if_module()

        # start thread
        self.start()

    def init_config(self, run_time_safe_only=False):
        """ Update configs that can be updated during run-time
        """
        if not run_time_safe_only:
            self.machIfId = mi.GetMachIfId(gc.CONFIG_DATA.get('/machine/Device', ""))

        self.filterGCodesEnable = gc.CONFIG_DATA.get('/machine/FilterGcodesEnable', False)
        self.filterGCodes = gc.CONFIG_DATA.get('/machine/FilterGcodes', "")
        filterGcodeList = self.filterGCodes.split(',')
        self.filterGCodesList = [x.strip() for x in filterGcodeList]
        self.dictProbeSettings = gc.CONFIG_DATA.get('/machine/Probe')

    def process_queue(self):
        """ Handle events coming from main UI
        """
        # process events from queue
        try:
            e = self._eventQueue.get_nowait()
        except queue.Empty:
            pass
        else:

            self.lastEventID = e.event_id

            if e.event_id == gc.EV_CMD_STEP:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_STEP")

                h1 = hashlib.md5(str(self.gcodeDataLines).encode('utf-8')).hexdigest()

                if 'gcodeFileName' in e.data:
                    self.gcodeFileName = e.data['gcodeFileName']

                if 'gcodeLines' in e.data:
                    self.gcodeDataLines = e.data['gcodeLines']

                if 'gcodePC' in e.data:
                    self.initialProgramCounter = e.data['gcodePC']
                    self.workingProgramCounter = self.initialProgramCounter
                else:
                    self.initialProgramCounter = self.workingProgramCounter
                    # self.workingProgramCounter = self.initialProgramCounter

                last_brk_pt_set = self.breakPointSet
                if 'breakPoints' in e.data:
                    self.breakPointSet = e.data['breakPoints']

                # if gcode lines change update listeners of new md5
                h2 = hashlib.md5(str(self.gcodeDataLines).encode('utf-8')).hexdigest()
                if h1 != h2:
                    self.notify_event_listeners(gc.EV_GCODE_MD5, h2)
                elif last_brk_pt_set != self.breakPointSet:
                    self.notify_event_listeners(gc.EV_BRK_PT_CHG)

                self.swState = gc.STATE_STEP

            elif e.event_id == gc.EV_CMD_RUN:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_RUN")

                h1 = hashlib.md5(str(self.gcodeDataLines).encode('utf-8')).hexdigest()

                if 'gcodeFileName' in e.data:
                    self.gcodeFileName = e.data['gcodeFileName']

                if 'gcodeLines' in e.data:
                    self.gcodeDataLines = e.data['gcodeLines']

                if 'gcodePC' in e.data:
                    self.initialProgramCounter = e.data['gcodePC']
                    self.workingProgramCounter = self.initialProgramCounter

                last_brk_pt_set = self.breakPointSet
                if 'breakPoints' in e.data:
                    self.breakPointSet = e.data['breakPoints']

                # init time only if we got new lines or previous state was
                # IDLE (if we stop or step operations)
                h2 = hashlib.md5(str(self.gcodeDataLines).encode('utf-8')).hexdigest()
                if h1 != h2 or self.swState == gc.STATE_IDLE:
                    self.runTimeStart = int(time.time())

                # if gcode lines change update listeners of new md5
                if h1 != h2:
                    self.notify_event_listeners(gc.EV_GCODE_MD5, h2)
                elif last_brk_pt_set != self.breakPointSet:
                    self.notify_event_listeners(gc.EV_BRK_PT_CHG)

                self.swState = gc.STATE_RUN

            elif e.event_id == gc.EV_CMD_PAUSE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_PAUSE")

                self.swState = gc.STATE_PAUSE

            elif e.event_id == gc.EV_CMD_STOP:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_STOP")

                force_update = False

                if self.swState != gc.STATE_IDLE:
                    force_update = True
                    self.swState = gc.STATE_IDLE

                # self.runTimeStart = 0

                if force_update:
                    self.notify_event_listeners(gc.EV_SW_STATE, self.swState)

            elif e.event_id == gc.EV_CMD_SEND:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_SEND {}".format(str(e.data).strip()))

                self.serialWriteQueue.append((e.data, False))

            elif e.event_id == gc.EV_CMD_SEND_W_ACK:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_SEND_W_ACK {}".format(e.data))

                self.serialWriteQueue.append((e.data, True))

            elif e.event_id == gc.EV_CMD_OK_TO_POST:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_OK_TO_POST")
                pass

            elif e.event_id == gc.EV_CMD_GET_STATUS:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_GET_STATUS")

                self.machIfModule.doGetStatus()

            elif e.event_id == gc.EV_CMD_GET_SYSTEM_INFO:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_GET_SYSTEM_INFO")

                self.machIfModule.doGetSystemInfo()

            elif e.event_id == gc.EV_CMD_CYCLE_START:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_CYCLE_START")

                # this command is usually use for resume after a machine stop
                # thus, queues most probably full send without checking if ok..
                self.machIfModule.doCycleStartResume()

            elif e.event_id == gc.EV_CMD_FEED_HOLD:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_FEED_HOLD")

                # this command is usually use for abort and machine stop
                # we can't afford to skip this action, send without checking
                # if ok...
                self.machIfModule.doFeedHold()

            elif e.event_id == gc.EV_CMD_QUEUE_FLUSH:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_QUEUE_FLUSH")

                self.machIfModule.doQueueFlush()

            elif e.event_id == gc.EV_CMD_RESET:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_RESET")

                self.machIfModule.doReset()

            elif e.event_id == gc.EV_CMD_CLEAR_ALARM:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_CLEAR_ALARM")

                self.machIfModule.doClearAlarm()

            elif e.event_id == gc.EV_CMD_MOVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_MOVE {}".format(e.data))

                self.machIfModule.doMove(e.data)

            elif e.event_id == gc.EV_CMD_MOVE_RELATIVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_MOVE_RELATIVE {}".format(e.data))

                self.machIfModule.doMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_RAPID_MOVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_RAPID_MOVE {}".format(e.data))

                self.machIfModule.doFastMove(e.data)

            elif e.event_id == gc.EV_CMD_RAPID_MOVE_RELATIVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_RAPID_MOVE_RELATIVE {}".format(e.data))

                self.machIfModule.doFastMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_JOG_MOVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_JOG_MOVE {}".format(e.data))

                self.machIfModule.doJogMove(e.data)

            elif e.event_id == gc.EV_CMD_JOG_MOVE_RELATIVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_JOG_MOVE_RELATIVE {}".format(e.data))

                self.machIfModule.doJogMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_JOG_RAPID_MOVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_JOG_RAPID_MOVE {}".format(e.data))

                self.machIfModule.doJogFastMove(e.data)

            elif e.event_id == gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info(
                        "EV_CMD_JOG_RAPID_MOVE_RELATIVE {}".format(e.data))

                self.machIfModule.doJogFastMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_JOG_STOP:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_JOG_STOP {}".format(e.data))

                self.machIfModule.doJogStop()

            elif e.event_id == gc.EV_CMD_SET_AXIS:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_SET_AXIS {}".format(e.data))

                self.machIfModule.doSetAxis(e.data)

            elif e.event_id == gc.EV_CMD_HOME:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_HOME")

                self.machIfModule.doHome(e.data)

            elif e.event_id == gc.EV_CMD_EXIT:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_EXIT")

                if self.machIfModule.isSerialPortOpen():
                    self.machIfModule.close()
                else:
                    self.endThread = True
                    self.swState = gc.STATE_IDLE

            elif e.event_id == gc.EV_HELLO:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_HELLO from 0x{:x}".format(id(e.sender)))

                listener = e.sender
                self.add_event_listener(listener)
                h = hashlib.md5(str(self.gcodeDataLines).encode('utf-8')).hexdigest()
                listener.add_event(gc.EV_GCODE_MD5, h)

            elif e.event_id == gc.EV_GOOD_BYE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_GOOD_BYE from 0x{:x}".format(id(e.sender)))

                self.remove_event_listener(e.sender)

            elif e.event_id == gc.EV_CMD_PROBE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_PROBE {}".format(e.data))

                self.machIfModule.doProbe(e.data)

            elif e.event_id == gc.EV_CMD_PROBE_HELPER:
                # This helper takes care of
                #   Running the probe command
                #   Setting probe offset
                #   Retract using settings saved settings
                # all the commands are sent to the machine interface, it is
                # expected that if a probe error happens the machine will
                # ignore the the set axis command anf the retract command
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_PROBE_HELPER {}".format(e.data))

                # expectation is a dictionary with a single key (the axis)
                # and a positive or negative value indicating direction,
                # the actual value is not important
                axis = list(e.data.keys())[0]
                direction = e.data[axis]

                feed_rate = self.dictProbeSettings[axis.upper()]['FeedRate']
                travel_limit = self.dictProbeSettings[axis.upper()]['TravelLimit']
                retract = self.dictProbeSettings[axis.upper()]['Retract']
                offset = self.dictProbeSettings[axis.upper()]['Offset']

                # depending on probe direction we need to update some values
                if direction > 0:
                    travel_limit = abs(travel_limit)
                    retract = -abs(retract)
                else:
                    travel_limit = -abs(travel_limit)
                    retract = abs(retract)

                probe = {axis: travel_limit, 'feed': feed_rate}
                self.machIfModule.doProbe(probe)

                set_axis = {axis: offset}
                self.machIfModule.doSetAxis(set_axis)

                if retract != 0:
                    retract_axis = {axis: retract}
                    self.machIfModule.doFastMoveRelative(retract_axis)

            elif e.event_id == gc.EV_CMD_UPDATE_CONFIG:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_UPDATE_CONFIG")

                self.init_config(run_time_safe_only=True)

            elif e.event_id == gc.EV_CMD_GET_SW_STATE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_GET_SW_STATE")

                self.notify_event_listeners(gc.EV_SW_STATE, self.swState)

            elif e.event_id == gc.EV_CMD_GET_GCODE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_GET_GCODE")

                listener = e.sender
                listener.add_event(gc.EV_GCODE, self.gcodeDataLines, self)

            elif e.event_id == gc.EV_CMD_GET_GCODE_MD5:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_GET_GCODE_MD5")

                h = hashlib.md5(str(self.gcodeDataLines).encode('utf-8')).hexdigest()
                # self.notify_event_listeners(gc.EV_GCODE_MD5, h)

                listener = e.sender
                listener.add_event(gc.EV_GCODE_MD5, h, self)

            elif e.event_id == gc.EV_CMD_GET_BRK_PT:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.info("EV_CMD_GET_BRK_PT")

                listener = e.sender
                listener.add_event(gc.EV_BRK_PT, self.breakPointSet)

            else:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC_EV):
                    self.logger.error("got unknown event!! [{}]".format(str(e.event_id)))

    """-------------------------------------------------------------------------
    programExecuteThread: General Functions
    -------------------------------------------------------------------------"""

    def init_machine_if_module(self):
        self.machIfModule = mi.GetMachIfModule(self.machIfId)

        if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
            msg = "init MachIf Module (%s)." % self.machIfModule.getName()
            self.logger.info(msg)

        self.machIfModule.init()

    def get_gcode_dict(self):
        gcodeDict = dict()
        gcodeDict['gcodeFileName'] = self.gcodeFileName
        gcodeDict['gcodeLines'] = self.gcodeDataLines
        gcodeDict['gcodePC'] = self.workingProgramCounter
        gcodeDict['breakPoints'] = self.breakPointSet
        return gcodeDict

    def serial_read(self):
        rxData = self.machIfModule.read()

        if 'event' in rxData:
            forwardEvent = True
            e = rxData['event']
            if e['id'] == gc.EV_ABORT:
                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

            if e['id'] == gc.EV_EXIT:
                self.endThread = True
                self.swState = gc.STATE_IDLE
                forwardEvent = False

            if forwardEvent:
                # notify listeners
                self.notify_event_listeners(e['id'], e['data'])

        else:
            rxData['pc'] = self.workingProgramCounter
            rxData['swstate'] = "{}".format(self.swState)

            rxDataKeys = rxData.keys()

            if set(['rx_data', 'sr']) & set(rxDataKeys):

                try:
                    rx_data = rxData['rx_data']

                    if len(rx_data):
                        if 'rx_data_info' in rxData:
                            rx_data_info = rxData['rx_data_info']
                            rx_data = "".join(
                                [rx_data.strip(), " ", rx_data_info])
                            rxData['rx_data'] = rx_data
                except KeyError:
                    pass

                    # notify listeners
                    # self.notifyEventListeners(gc.EV_DATA_IN, rx_data)

                if 'sr' in rxData:
                    if len(self.gcodeDataLines):
                        # at this point we haven't completed and added program counter
                        # we need to +1, also array starts at 0 and gcode page starts at 1
                        # nee another +1
                        gcode_lines_len = len(self.gcodeDataLines)
                        adj_prog_counter = self.workingProgramCounter + 2

                        if adj_prog_counter > gcode_lines_len:
                            adj_prog_counter = gcode_lines_len

                        prcnt = "{}/{} {:.2f}%".format(
                            adj_prog_counter, gcode_lines_len,
                            abs((float(adj_prog_counter)/float(gcode_lines_len) * 100)))
                        rxData['sr']['prcnt'] = prcnt

                    if 'stat' in rxData['sr']:
                        self.machIfState = rxData['sr']['stat']

                    if self.runTimeStart:
                        runTimeNow = int(time.time())
                        self.runTimeElapse = runTimeNow - self.runTimeStart
                        rxData['sr']['rtime'] = self.runTimeElapse

                        # if self.swState == gc.STATE_IDLE and self.machIfState in [
                        #     "Idle", "idle", "Stop", "stop", "End", "end"]:
                        #     self.runTimeStart = 0

                self.notify_event_listeners(gc.EV_DATA_STATUS, rxData)

            if 'tx_data' in rxData:
                tx_data = rxData['tx_data']

                if len(tx_data) > 0:

                    # notify listeners
                    self.notify_event_listeners(gc.EV_DATA_OUT, tx_data)

            # if 'sr' in rxData:
            #     # notify listeners
            #     self.notifyEventListeners(gc.EV_DATA_STATUS, rxData['sr'])

            if 'r' in rxData:
                if 'fb' in rxData['r']:
                    # notify listeners
                    self.notify_event_listeners(gc.EV_DATA_STATUS, rxData['r'])

                if 'init' in rxData['r']:
                    # notify listeners
                    self.notify_event_listeners(gc.EV_DEVICE_DETECTED, rxData['r'])
                    self.do_init_script = True

                if 'sys' in rxData['r']:
                    # notify listeners
                    self.notify_event_listeners(gc.EV_DATA_STATUS, rxData['r']['sys'])

                if 'f' in rxData:
                    if (rxData['f'][1] != 0 and gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC)):
                        msg = f"acknowledgement state ERROR[{rxData['f'][1]}]"
                        if 'rx_data' in rxData:
                            msg = "".join([msg, " ", rxData['rx_data'].strip()])

                        if 'rx_data_info' in rxData:
                            msg = "".join([msg, " ", rxData['rx_data_info'].strip()])

                        self.logger.info(msg)

        return rxData

    def serial_write(self, serial_data):
        bytesSent = 0

        lines = serial_data.splitlines(True)

        for line in lines:
            bytes_sent = self.machIfModule.write(line)

            # sent data to UI
            if bytes_sent > 0:
                # notify listeners
                self.notify_event_listeners(gc.EV_DATA_OUT, line)

            bytesSent = bytesSent + bytes_sent

        return bytesSent

    def tick(self):
        self.machIfModule.tick()
        self.process_queue()

        if self.do_init_script:
            # run user specified script
            self.run_device_init_script()

            # get device status
            self.add_event(gc.EV_CMD_GET_STATUS)

            self.do_init_script = False

    def wait_for_acknowledge(self):
        """ waits for a ack kind of response also check for errors
            and signal calling function
        """
        rc_error = False
        wait_for_acknowledge = True

        while (wait_for_acknowledge):
            rxDataDict = self.wait_for_response()

            if self.swState == gc.STATE_ABORT:
                wait_for_acknowledge = False

            if self.lastEventID == gc.EV_CMD_STOP:
                wait_for_acknowledge = False

            if self.endThread:
                wait_for_acknowledge = False

            if 'r' in rxDataDict:
                if 'f' in rxDataDict:
                    if rxDataDict['f'][1] == 0:
                        # if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                        #     self.logger.info("acknowledgement state OK")
                        pass
                    else:
                        # if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                        #     msg = "acknowledgement state ERROR[%d]" % \
                        #           rxDataDict['f'][1]
                        #     if 'rx_data' in rxDataDict:
                        #         msg = "".join([msg, " ",
                        #                        rxDataDict['rx_data'].strip()])

                        #     if 'rx_data_info' in rxDataDict:
                        #         msg = "".join([msg, " ",
                        #                        rxDataDict['rx_data_info'].strip()])

                        #     self.logger.info(msg)

                        self.swState = gc.STATE_IDLE
                        rc_error = True

                wait_for_acknowledge = False
                break

            if 'err' in rxDataDict:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                    self.logger.info("acknowledgement state ERROR")

                self.swState = gc.STATE_IDLE
                rc_error = True
                wait_for_acknowledge = False
                break

        return rc_error

    def wait_for_response(self):
        waitForResponse = True
        rxDataDict = {}

        while (waitForResponse):
            rxDataDict = self.serial_read()

            if self.swState == gc.STATE_ABORT:
                waitForResponse = False

            if 'rx_data' in rxDataDict:
                if len(rxDataDict['rx_data'].strip()) > 0:
                    waitForResponse = False

            self.tick()

            if self.endThread:
                waitForResponse = False

            if self.lastEventID == gc.EV_CMD_STOP:
                waitForResponse = False

            time.sleep(0.01)

        return rxDataDict

    def send_run_step_gcode(self, gcode_data):
        write_to_device = True
        rc_error = False
        gcode = gcode_data.strip()

        if len(gcode) > 0:
            gcode = "%s\n" % (gcode)

            if self.machIfModule.okToSend(gcode):
                # write data
                self.serial_write(gcode)

                ''' Wait for acknowledge might no longer needed, the
                machine IF object will track the device queue
                all will manage whether or not we can send more
                commands to the IF'''
                # wait for response
                rc_error = self.wait_for_acknowledge()
                # self.SerialRead()

            else:
                write_to_device = False
                self.serial_read()

        if write_to_device:
            if not rc_error:
                self.workingProgramCounter += 1

            # if we stop early make sure to update PC to main UI
            # if self.swState == gc.STATE_IDLE:
            #     # notify listeners
            #     self.notifyEventListeners(gc.EV_PC_UPDATE,
            #                               self.workingProgramCounter)

        return rc_error

    def process_run_sate(self):
        """ Process RUN state and update counters or end state
        """
        error = False

        # check if we are done with gcode
        if self.workingProgramCounter >= len(self.gcodeDataLines):
            if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                self.logger.info("reach last PC, moving to gc.STATE_IDLE")

            self.swState = gc.STATE_IDLE

            # notify listeners
            self.notify_event_listeners(gc.EV_RUN_END)
            self.notify_event_listeners(gc.EV_SW_STATE, self.swState)
            self.runTimeStart = 0
            return

        # update PC
        if self.lastWorkingProgramCounter != self.workingProgramCounter:
            #     # notify listeners
            #     self.notifyEventListeners(gc.EV_PC_UPDATE,
            #                               self.workingProgramCounter)
            self.lastWorkingProgramCounter = self.workingProgramCounter

        # check for break point hit
        if self.workingProgramCounter in self.breakPointSet and self.workingProgramCounter != self.initialProgramCounter:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                self.logger.info(
                    f"encounter breakpoint PC[{self.workingProgramCounter + 1}], moving to gc.STATE_BREAK")

            self.swState = gc.STATE_BREAK
            # notify listeners
            self.notify_event_listeners(gc.EV_BRK_PT_STOP)
            self.notify_event_listeners(gc.EV_SW_STATE, self.swState)
            return

        # get gcode line
        gcode = self.gcodeDataLines[self.workingProgramCounter]

        # check for msg line
        reMsgSearch = gReGcodeMsg.search(gcode)
        if (reMsgSearch is not None) and (self.workingProgramCounter != self.initialProgramCounter):
            if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                self.logger.info(
                    f"encounter MSG line PC[{self.workingProgramCounter}], moving to gc.STATE_BREAK, "
                    f"MSG[{reMsgSearch.group(1)}]")

            self.swState = gc.STATE_BREAK

            # notify listeners
            self.notify_event_listeners(gc.EV_GCODE_MSG, reMsgSearch.group(1))
            return

        # don't sent unnecessary data save the bits for speed
        for reComments in gReGcodeComments:
            gcode = reComments.sub("", gcode)

        if self.filterGCodesEnable:
            for filter in self.filterGCodesList:
                if filter in gcode:
                    gcode = ""
                    break

        # send g-code command
        error = self.send_run_step_gcode(gcode)

        # check for errors
        if error:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                self.logger.info("error event, moving to gc.STATE_BREAK")

            self.swState = gc.STATE_BREAK
            self.errorFlag = False

            # notify listeners
            self.notify_event_listeners(gc.EV_BRK_PT_STOP)
            self.notify_event_listeners(gc.EV_SW_STATE, self.swState)
            return

    def process_step_sate(self):
        """ Process STEP state and update counters or end state
        """
        error = False

        # check if we are done with gcode
        if self.workingProgramCounter >= len(self.gcodeDataLines):
            if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                self.logger.info("reach last PC, moving to gc.STATE_IDLE")

            self.swState = gc.STATE_IDLE

            # notify listeners
            self.notify_event_listeners(gc.EV_STEP_END)
            self.notify_event_listeners(gc.EV_SW_STATE, self.swState)
            return

        # update PC
        # self.notifyEventListeners(gc.EV_PC_UPDATE, self.workingProgramCounter)
        self.notify_event_listeners(gc.EV_DATA_STATUS, {'pc': self.workingProgramCounter})

        # end move to IDLE state
        if self.workingProgramCounter > self.initialProgramCounter:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                self.logger.info("finish STEP cmd, moving to gc.STATE_IDLE")

            self.swState = gc.STATE_IDLE

            # notify listeners
            self.notify_event_listeners(gc.EV_STEP_END)
            self.notify_event_listeners(gc.EV_SW_STATE, self.swState)
            return

        gcode = self.gcodeDataLines[self.workingProgramCounter]

        # don't sent unnecessary data save the bits for speed
        for reComments in gReGcodeComments:
            gcode = reComments.sub("", gcode)

        error = self.send_run_step_gcode(gcode)

        # check for error
        if error:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                self.logger.info("error event, moving to gc.STATE_IDLE")

            # notify listeners
            self.notify_event_listeners(gc.EV_STEP_END)
            self.notify_event_listeners(gc.EV_SW_STATE, self.swState)
            return

    def process_idle_sate(self):
        self.serial_read()

    def process_serial_write_queue(self):
        if self.serialWriteQueue:

            data = self.serialWriteQueue[0]

            if self.machIfModule.okToSend(data[0]):
                self.serialWriteQueue.pop(0)
                self.serial_write(data[0])

                if data[1]:
                    self.wait_for_acknowledge()

    def run_device_init_script(self):
        init_script_en = gc.CONFIG_DATA.get('/machine/InitScriptEnable')

        if init_script_en:
            # comments example "( comment string )" or "; comment string"
            re_gcode_comments = [re.compile(r'\(.*\)'), re.compile(r';.*')]

            # run init script
            init_script = str(gc.CONFIG_DATA.get('/machine/InitScript')).splitlines()

            if len(init_script) > 0:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                    self.logger.info("Queuing machine init script...")

                for init_line in init_script:

                    for re_comments in re_gcode_comments:
                        init_line = re_comments.sub("", init_line)

                    init_line = "".join([init_line, "\n"])

                    if len(init_line.strip()):
                        self.add_event(gc.EV_CMD_SEND, init_line)

                        if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                            self.logger.info(init_line.strip())

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread.
        self.endThread = False

        if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
            self.logger.info("thread start")

        # inti machine interface
        self.machIfModule.open()

        # initial report of GCode MD5
        h = hashlib.md5(str(self.gcodeDataLines).encode('utf-8')).hexdigest()
        self.notify_event_listeners(gc.EV_GCODE_MD5, h)

        while not self.endThread:

            # process bookkeeping input queue for new commands or actions
            self.tick()

            # process write queue from UI cmds
            self.process_serial_write_queue()

            # check if we need to exit now
            if self.endThread:
                break

            if self.swState == gc.STATE_RUN:
                self.process_run_sate()
            elif self.swState == gc.STATE_STEP:
                self.process_step_sate()
            elif self.swState == gc.STATE_IDLE or self.swState == gc.STATE_PAUSE:
                self.process_idle_sate()
            elif self.swState == gc.STATE_BREAK:
                self.process_idle_sate()
            elif self.swState == gc.STATE_ABORT:
                self.process_idle_sate()
                break
            else:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
                    msg = "unexpected state [%d], moving back to IDLE, swState->gc.STATE_IDLE " % (self.swState)
                    self.logger.info(msg)

                self.process_idle_sate()
                self.swState = gc.STATE_IDLE

            time.sleep(0.010)

        if gc.test_verbose_mask(gc.VERBOSE_MASK_MACHIF_EXEC):
            self.logger.info("thread exit")

        # notify listeners
        self.notify_event_listeners(gc.EV_EXIT)
