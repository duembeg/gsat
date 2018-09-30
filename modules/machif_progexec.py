"""----------------------------------------------------------------------------
   machif_progexec.py

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
import threading
import time
import logging

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
        self.machIfId = mi.GetMachIfId(gc.CONFIG_DATA.get('/machine/Device'))
        self.okToPostEvents = True

        self.gcodeDataLines = []
        self.breakPointSet = set()
        self.initialProgramCounter = 0
        self.workingCounterWorking = 0
        self.lastWorkingCounterWorking = -1

        self.swState = gc.STATE_IDLE
        self.lastEventID = gc.EV_CMD_NULL

        self.machineAutoStatus = gc.CONFIG_DATA.get('/machine/AutoStatus')

        self.serialWriteQueue = []

        self.machIfModule = None

        if event_handler is not None:
            self.addEventListener(event_handler)

        self.logger = logging.getLogger()
        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
            self.logger.info("init logging id:0x%x" % id(self))

        # init device module
        self.initMachineIfModule()

        # start thread
        self.start()

    def processQueue(self):
        """ Handle events coming from main UI
        """
        # process events from queue
        if not self._eventQueue.empty():
            # get item from queue
            e = self._eventQueue.get()

        # check output queue and notify UI if is not empty
        # if not self.progExecOutQueue.empty():
        #     # if self.okToPostEvents:
        #     #   self.okToPostEvents = False
        #     #   wx.PostEvent(self.notifyWindow, gc.threadQueueEvent(None))
        #     wx.PostEvent(self.notifyWindow, gc.ThreadQueueEvent(None))

            self.lastEventID = e.event_id

            if e.event_id == gc.EV_CMD_STEP:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_STEP")

                self.gcodeDataLines = e.data[0]
                self.initialProgramCounter = e.data[1]
                self.workingProgramCounter = self.initialProgramCounter
                self.breakPointSet = e.data[2]
                self.swState = gc.STATE_STEP

            elif e.event_id == gc.EV_CMD_RUN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_RUN")

                self.gcodeDataLines = e.data[0]
                self.initialProgramCounter = e.data[1]
                self.workingProgramCounter = self.initialProgramCounter
                self.breakPointSet = e.data[2]
                self.swState = gc.STATE_RUN

            elif e.event_id == gc.EV_CMD_STOP:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_STOP")

                self.swState = gc.STATE_IDLE

            elif e.event_id == gc.EV_CMD_SEND:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_SEND %s" % e.data)

                self.serialWriteQueue.append((e.data, False))

            elif e.event_id == gc.EV_CMD_SEND_W_ACK:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_SEND_W_ACK %s" % e.data)

                self.serialWriteQueue.append((e.data, True))

            elif e.event_id == gc.EV_CMD_AUTO_STATUS:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_AUTO_STATUS")

                self.machineAutoStatus = e.data

            elif e.event_id == gc.EV_CMD_OK_TO_POST:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_OK_TO_POST")
                pass

            elif e.event_id == gc.EV_CMD_GET_STATUS:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_GET_STATUS")

                self.machIfModule.doGetStatus()

            elif e.event_id == gc.EV_CMD_CYCLE_START:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_CYCLE_START")

                # this command is usually use for resume after a machine stop
                # thus, queues most probably full send without checking if ok..
                self.machIfModule.doCycleStartResume()

            elif e.event_id == gc.EV_CMD_FEED_HOLD:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_FEED_HOLD")

                # this command is usually use for abort and machine stop
                # we can't afford to skip this action, send without checking
                # if ok...
                self.machIfModule.doFeedHold()

            elif e.event_id == gc.EV_CMD_QUEUE_FLUSH:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_QUEUE_FLUSH")

                self.machIfModule.doQueueFlush()

            elif e.event_id == gc.EV_CMD_RESET:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_RESET")

                self.machIfModule.doReset()

            elif e.event_id == gc.EV_CMD_CLEAR_ALARM:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_CLEAR_ALARM")

                self.machIfModule.doClearAlarm()

            elif e.event_id == gc.EV_CMD_MOVE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_MOVE %s" % e.data)

                self.machIfModule.doMove(e.data)

            elif e.event_id == gc.EV_CMD_MOVE_RELATIVE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_MOVE_RELATIVE %s" % e.data)

                self.machIfModule.doMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_RAPID_MOVE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_RAPID_MOVE %s" % e.data)

                self.machIfModule.doFastMove(e.data)

            elif e.event_id == gc.EV_CMD_RAPID_MOVE_RELATIVE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_RAPID_MOVE_RELATIVE %s" % e.data)

                self.machIfModule.doFastMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_SET_AXIS:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_SET_AXIS")

                self.machIfModule.doSetAxis(e.data)

            elif e.event_id == gc.EV_CMD_HOME:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_HOME")

                self.machIfModule.doHome(e.data)

            elif e.event_id == gc.EV_CMD_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_CMD_EXIT")

                if self.machIfModule.isSerialPortOpen():
                    self.machIfModule.close()
                else:
                    self.endThread = True
                    self.swState = gc.STATE_IDLE

            elif e.event_id == gc.EV_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_HELLO from 0x%x" % id(e.sender))

                self.addEventListener(e.sender)

            elif e.event_id == gc.EV_GOODBY:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.info("EV_GOODBY from 0x%x" % id(e.sender))

                self.removeEventListener(e.sender)

            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC_EV:
                    self.logger.error("got unknown event!! [%s]." %
                                      str(e.event_id))

    """-------------------------------------------------------------------------
   programExecuteThread: General Functions
   -------------------------------------------------------------------------"""

    def initMachineIfModule(self):
        self.machIfModule = mi.GetMachIfModule(self.machIfId)

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
            msg = "init MachIf Module (%s)." % self.machIfModule.getName()
            self.logger.info(msg)

        self.machIfModule.init()

    def serialRead(self):
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
                self.notifyEventListeners(e['id'], e['data'])

        else:
            if 'rx_data' in rxData:
                rx_data = rxData['rx_data']

                if len(rx_data) > 0:

                    if 'rx_data_info' in rxData:
                        rx_data_info = rxData['rx_data_info']
                        rx_data = "".join(
                            [rx_data.strip(), " ", rx_data_info]
                        )

                    # notify listeners
                    self.notifyEventListeners(gc.EV_DATA_IN, rx_data)

            if 'tx_data' in rxData:
                tx_data = rxData['tx_data']

                if len(tx_data) > 0:

                    # notify listeners
                    self.notifyEventListeners(gc.EV_DATA_OUT, tx_data)

            if 'sr' in rxData:
                # notify listeners
                self.notifyEventListeners(gc.EV_DATA_STATUS, rxData['sr'])

            if 'r' in rxData:
                if 'fb' in rxData['r']:
                    # notify listeners
                    self.notifyEventListeners(gc.EV_DATA_STATUS, rxData['r'])

                if 'init' in rxData['r']:
                    # notify listeners
                    self.notifyEventListeners(gc.EV_DATA_STATUS, rxData['r'])

                if 'f' in rxData:
                    if (rxData['f'][1] != 0 and
                       gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC):
                        msg = "acknowledgement state ERROR[%d]" % \
                                rxData['f'][1]
                        if 'rx_data' in rxData:
                            msg = "".join([msg, " ",
                                          rxData['rx_data'].strip()])

                        if 'rx_data_info' in rxData:
                            msg = "".join([msg, " ",
                                          rxData['rx_data_info'].strip()])

                        self.logger.info(msg)

        return rxData

    def serialWrite(self, serial_data):
        bytesSent = 0

        lines = serial_data.splitlines(True)

        for line in lines:
            bytes_sent = self.machIfModule.write(line)

            # sent data to UI
            if bytes_sent > 0:
                # notify listeners
                self.notifyEventListeners(gc.EV_DATA_OUT, line)

            bytesSent = bytesSent + bytes_sent

        return bytesSent

    def tick(self):
        self.machIfModule.tick()
        self.processQueue()

    def waitForAcknowledge(self):
        """ waits for a ack kind of response also check for errors
            and signal calling function
        """
        rc_error = False
        wait_for_acknowlege = True

        while (wait_for_acknowlege):
            rxDataDict = self.waitForResponse()

            if self.swState == gc.STATE_ABORT:
                wait_for_acknowlege = False

            if self.lastEventID == gc.EV_CMD_STOP:
                wait_for_acknowlege = False

            if self.endThread:
                wait_for_acknowlege = False

            if 'r' in rxDataDict:
                if 'f' in rxDataDict:
                    if rxDataDict['f'][1] == 0:
                        # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                        #     self.logger.info("acknowledgement state OK")
                        pass
                    else:
                        # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
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

                wait_for_acknowlege = False
                break

            if 'err' in rxDataDict:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                    self.logger.info("acknowledgement state ERROR")

                self.swState = gc.STATE_IDLE
                rc_error = True
                wait_for_acknowlege = False
                break

        return rc_error

    def waitForResponse(self):
        waitForResponse = True
        rxDataDict = {}

        while (waitForResponse):
            rxDataDict = self.serialRead()

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

    def sendRunStepGcode(self, gcode_data):
        write_to_device = True
        rc_error = False
        gcode = gcode_data.strip()

        if len(gcode) > 0:
            gcode = "%s\n" % (gcode)

            if self.machIfModule.okToSend(gcode):
                # write data
                self.serialWrite(gcode)

                ''' Wait for acknowledge might no longer needed, the
                machine IF object will track the device queue
                all will manage whether or not we can send more
                commands to the IF'''
                # wait for response
                rc_error = self.waitForAcknowledge()
                # self.SerialRead()

                # if self.machineAutoStatus:
                #     self.machIfModule.doGetStatus()
            else:
                write_to_device = False
                self.serialRead()

        if write_to_device:
            if not rc_error:
                self.workingProgramCounter += 1

            # if we stop early make sure to update PC to main UI
            if self.swState == gc.STATE_IDLE:
                # notify listeners
                self.notifyEventListeners(gc.EV_PC_UPDATE,
                                          self.workingProgramCounter)

        return rc_error

    def processRunSate(self):
        """ Process RUN state and update counters or end state
        """
        error = False

        # check if we are done with gcode
        if self.workingProgramCounter >= len(self.gcodeDataLines):
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                self.logger.info("reach last PC, moving to gc.STATE_IDLE")

            self.swState = gc.STATE_IDLE

            # notify listeners
            self.notifyEventListeners(gc.EV_RUN_END)
            return

        # update PC
        if self.lastWorkingCounterWorking != self.workingProgramCounter:
            # notify listeners
            self.notifyEventListeners(gc.EV_PC_UPDATE,
                                      self.workingProgramCounter)
            self.lastWorkingCounterWorking = self.workingProgramCounter

        # check for break point hit
        if (self.workingProgramCounter in self.breakPointSet and
           self.workingProgramCounter != self.initialProgramCounter):
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                self.logger.info("encounter breakpoint PC[%d], "
                                 "moving to gc.STATE_BREAK" %
                                 (self.workingProgramCounter + 1))

            self.swState = gc.STATE_BREAK
            # notify listeners
            self.notifyEventListeners(gc.EV_HIT_BRK_PT)
            return

        # get gcode line
        gcode = self.gcodeDataLines[self.workingProgramCounter]

        # check for msg line
        reMsgSearch = gReGcodeMsg.search(gcode)
        if (reMsgSearch is not None) and \
           (self.workingProgramCounter != self.initialProgramCounter):
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                self.logger.info("encounter MSG line PC[%s], "
                                 "moving to gc.STATE_BREAK, MSG[%s]" %
                                 (self.workingProgramCounter,
                                  reMsgSearch.group(1)))

            self.swState = gc.STATE_BREAK

            # notify listeners
            self.notifyEventListeners(gc.EV_HIT_MSG, reMsgSearch.group(1))
            return

        # don't sent unnecessary data save the bits for speed
        for reComments in gReGcodeComments:
            gcode = reComments.sub("", gcode)

        # send g-code command
        error = self.sendRunStepGcode(gcode)

        # check for erros
        if error:
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                self.logger.info("error event, moving to gc.STATE_BREAK")

            self.swState = gc.STATE_BREAK
            self.errorFlag = False

            # notify listeners
            self.notifyEventListeners(gc.EV_HIT_BRK_PT)
            return

    def processStepSate(self):
        """ Process STEP state and update counters or end state
        """
        error = False

        # check if we are done with gcode
        if self.workingProgramCounter >= len(self.gcodeDataLines):
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                self.logger.info("reach last PC, moving to gc.STATE_IDLE")

            self.swState = gc.STATE_IDLE

            # notify listeners
            self.notifyEventListeners(gc.EV_STEP_END)
            return

        # update PC
        self.notifyEventListeners(gc.EV_PC_UPDATE, self.workingProgramCounter)

        # end move to IDLE state
        if self.workingProgramCounter > self.initialProgramCounter:
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                self.logger.info("finish STEP cmd, moving to gc.STATE_IDLE")

            self.swState = gc.STATE_IDLE

            # notify listeners
            self.notifyEventListeners(gc.EV_STEP_END)
            return

        gcode = self.gcodeDataLines[self.workingProgramCounter]

        # don't sent unnecessary data save the bits for speed
        for reComments in gReGcodeComments:
            gcode = reComments.sub("", gcode)

        error = self.sendRunStepGcode(gcode)

        # check for error
        if error:
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                self.logger.info("error event, moving to gc.STATE_IDLE")

            # notify listeners
            self.notifyEventListeners(gc.EV_STEP_END)
            return

    def processIdleSate(self):
        self.serialRead()

    def processSerialWriteQueue(self):
        if self.serialWriteQueue:

            data = self.serialWriteQueue[0]

            if self.machIfModule.okToSend(data[0]):
                self.serialWriteQueue.pop(0)
                self.serialWrite(data[0])

                if data[1]:
                    self.waitForAcknowledge()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread.
        self.endThread = False

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
            self.logger.info("thread start")

        # inti machine interface
        self.machIfModule.open()

        while not self.endThread:

            # process bookeeping input queue for new commands or actions
            self.tick()

            # process write queue from UI cmds
            self.processSerialWriteQueue()

            # check if we need to exit now
            if self.endThread:
                break

            if self.swState == gc.STATE_RUN:
                self.processRunSate()
            elif self.swState == gc.STATE_STEP:
                self.processStepSate()
            elif self.swState == gc.STATE_IDLE:
                self.processIdleSate()
            elif self.swState == gc.STATE_BREAK:
                self.processIdleSate()
            elif self.swState == gc.STATE_ABORT:
                self.processIdleSate()
                break
            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
                    msg = "unexpected state [%d], moving back to IDLE, "\
                          "swState->gc.STATE_IDLE " % (self.swState)

                    self.logger.info(msg)

                self.processIdleSate()
                self.swState = gc.STATE_IDLE

            time.sleep(0.01)

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_EXEC:
            self.logger.info("thread exit")

        # notify listeners
        self.notifyEventListeners(gc.EV_EXIT)
