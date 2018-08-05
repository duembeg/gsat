"""----------------------------------------------------------------------------
   progexec_thread.py

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

import os
import re
import serial
import threading
import Queue
import time
import pdb

import wx

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

class MachIfExecuteThread(threading.Thread):
    """  Threads that executes the gcode sending code to serial port. This
    thread allows the UI to continue being responsive to user input while this
    thread is busy executing program or waiting for serial events.
    Additionally it helps for user input not to disturb the rate and flow
    of data sent to the serial port.
    """

    def __init__(self, notify_window, state_data, in_queue, out_queue, cmd_line_options, machif_id, machine_auto_status=False):
        """Init Worker Thread Class."""
        threading.Thread.__init__(self)

        # init local variables
        self.notifyWindow = notify_window
        self.stateData = state_data
        self.progExecInQueue = in_queue
        self.progExecOutQueue = out_queue
        self.cmdLineOptions = cmd_line_options
        self.machIfId = machif_id
        self.okToPostEvents = True

        self.gcodeDataLines = []
        self.breakPointSet = set()
        self.initialProgramCounter = 0
        self.workingCounterWorking = 0
        self.lastWorkingCounterWorking = -1

        self.swState = gc.STATE_IDLE
        self.lastEventID = gc.EV_CMD_NULL

        self.machineAutoStatus = machine_auto_status

        self.serialWriteQueue = []

        self.machIfModule = None

        # init device module
        self.InitMachineIfModule()

        # start thread
        self.start()

    """-------------------------------------------------------------------------
   programExecuteThread: Main Window Event Handlers
   Handle events coming from main UI
   -------------------------------------------------------------------------"""

    def ProcessQueue(self):
        # check output queue and notify UI if is not empty
        if not self.progExecOutQueue.empty():
            # if self.okToPostEvents:
            #   self.okToPostEvents = False
            #   wx.PostEvent(self.notifyWindow, gc.threadQueueEvent(None))
            wx.PostEvent(self.notifyWindow, gc.ThreadQueueEvent(None))

        # process events from queue ---------------------------------------------
        if not self.progExecInQueue.empty():
            # get item from queue
            e = self.progExecInQueue.get()

            self.lastEventID = e.event_id

            if e.event_id == gc.EV_CMD_EXIT:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_EXIT."

                if self.machIfModule.isSerialPortOpen():
                    self.machIfModule.close()
                else:
                    self.endThread = True
                    self.swState = gc.STATE_IDLE

            elif e.event_id == gc.EV_CMD_RUN:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_RUN, swState->gc.gSTATE_RUN"
                self.gcodeDataLines = e.data[0]
                self.initialProgramCounter = e.data[1]
                self.workingProgramCounter = self.initialProgramCounter
                self.breakPointSet = e.data[2]
                self.swState = gc.STATE_RUN

            elif e.event_id == gc.EV_CMD_STEP:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_STEP, swState->gc.gSTATE_STEP"
                self.gcodeDataLines = e.data[0]
                self.initialProgramCounter = e.data[1]
                self.workingProgramCounter = self.initialProgramCounter
                self.breakPointSet = e.data[2]
                self.swState = gc.STATE_STEP

            elif e.event_id == gc.EV_CMD_STOP:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_STOP, swState->gc.gSTATE_IDLE"

                self.swState = gc.STATE_IDLE

            elif e.event_id == gc.EV_CMD_SEND:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_SEND."
                self.serialWriteQueue.append((e.data, False))

            elif e.event_id == gc.EV_CMD_SEND_W_ACK:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_SEND_W_ACK."
                self.serialWriteQueue.append((e.data, True))

            elif e.event_id == gc.EV_CMD_AUTO_STATUS:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_AUTO_STATUS."
                self.machineAutoStatus = e.data

            elif e.event_id == gc.EV_CMD_OK_TO_POST:
                # if self.cmdLineOptions.vverbose:
                #   print "** programExecuteThread got event gc.gEV_CMD_OK_TO_POST."
                #self.okToPostEvents = True
                pass

            elif e.event_id == gc.EV_CMD_GET_STATUS:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_GET_STATUS."
                self.machIfModule.doGetStatus()

            elif e.event_id == gc.EV_CMD_CYCLE_START:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_CYCLE_START."

                # this command is usually use for resume after a machine stop
                # thus, queues most probably full send without checking if ok...
                self.machIfModule.doCycleStartResume()

            elif e.event_id == gc.EV_CMD_FEED_HOLD:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_FEED_HOLD."

                # this command is usually use for abort and machine stop
                # we can't afford to skip this action, send without checking if ok...
                self.machIfModule.doFeedHold()

            elif e.event_id == gc.EV_CMD_QUEUE_FLUSH:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_QUEUE_FLUSH."

                self.machIfModule.doQueueFlush()

            elif e.event_id == gc.EV_CMD_RESET:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_RESET."

                self.machIfModule.doReset()

            elif e.event_id == gc.EV_CMD_CLEAR_ALARM:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_CLEAR_ALARM."

                self.machIfModule.doClearAlarm()

            elif e.event_id == gc.EV_CMD_MOVE:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_MOVE."

                self.machIfModule.doMove(e.data)

            elif e.event_id == gc.EV_CMD_MOVE_RELATIVE:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_MOVE_RELATIVE."

                self.machIfModule.doMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_RAPID_MOVE:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_RAPID_MOVE."

                self.machIfModule.doFastMove(e.data)

            elif e.event_id == gc.EV_CMD_RAPID_MOVE_RELATIVE:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_RAPID_MOVE_RELATIVE."

                self.machIfModule.doFastMoveRelative(e.data)

            elif e.event_id == gc.EV_CMD_SET_AXIS:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_SET_AXIS."

                self.machIfModule.doSetAxis(e.data)

            elif e.event_id == gc.EV_CMD_HOME:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got event gc.gEV_CMD_HOME."

                self.machIfModule.doHome(e.data)

            else:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread got unknown event!! [%s]." % str(
                        e.event_id)

    """-------------------------------------------------------------------------
   programExecuteThread: General Functions
   -------------------------------------------------------------------------"""

    def InitMachineIfModule(self):
        self.machIfModule = mi.GetMachIfModule(self.machIfId)

        if self.cmdLineOptions.vverbose:
            print "** programExecuteThread Init MachIf Module (%s)." % self.machIfModule.getName(
            )

        self.machIfModule.init(self.stateData)

    def SerialRead(self):
        rxData = self.machIfModule.read()
        mainWndEvent = False

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
                # add data to queue and signal main window to consume
                self.progExecOutQueue.put(gc.SimpleEvent(e['id'], e['data']))
                mainWndEvent = True

        else:
            if 'rx_data' in rxData:
                rx_data = rxData['rx_data']

                if len(rx_data) > 0:

                    # add data to queue and signal main window to consume
                    self.progExecOutQueue.put(
                        gc.SimpleEvent(gc.EV_DATA_IN, rx_data))
                    mainWndEvent = True

            if 'tx_data' in rxData:
                tx_data = rxData['tx_data']

                if len(tx_data) > 0:

                    # add data to queue and signal main window to consume
                    self.progExecOutQueue.put(
                        gc.SimpleEvent(gc.EV_DATA_OUT, tx_data))
                    mainWndEvent = True

            if 'sr' in rxData:
                self.progExecOutQueue.put(gc.SimpleEvent(
                    gc.EV_DATA_STATUS, rxData['sr']))
                mainWndEvent = True

            if 'r' in rxData:
                if 'fb' in rxData['r']:
                    self.progExecOutQueue.put(gc.SimpleEvent(
                        gc.EV_DATA_STATUS, rxData['r']))
                    mainWndEvent = True

        if mainWndEvent:
            wx.PostEvent(self.notifyWindow, gc.ThreadQueueEvent(None))

        return rxData

    def SerialWrite(self, serialData):
        bytesSent = 0

        lines = serialData.splitlines(True)

        for line in lines:
            bytes_sent = self.machIfModule.write(line)

            # sent data to UI
            if bytes_sent > 0:
                self.progExecOutQueue.put(
                    gc.SimpleEvent(gc.EV_DATA_OUT, line))

            bytesSent = bytesSent + bytes_sent

        return bytesSent

    def Tick(self):
        self.machIfModule.tick()
        self.ProcessQueue()

    def WaitForAcknowledge(self):
        waitForAcknowlege = True

        while (waitForAcknowlege):
            rxDataDict = self.WaitForResponse()

            if self.swState == gc.STATE_ABORT:
                waitForAcknowlege = False

            if self.lastEventID == gc.EV_CMD_STOP:
                waitForAcknowlege = False

            if self.endThread:
                waitForAcknowlege = False

            if 'r' in rxDataDict:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread found acknowledgement"\
                        " [%s]" % str(rxDataDict['r']).strip()

                    if rxDataDict['f'][1] == 0:
                        print "** programExecuteThread acknowledgement OK %s" % str(
                            rxDataDict['f'])
                    else:
                        print "** programExecuteThread acknowledgement ERROR %s" % str(
                            rxDataDict['f'])

                waitForAcknowlege = False
                break

            if 'err' in rxDataDict:
                if self.cmdLineOptions.vverbose:
                    print "** programExecuteThread found error acknowledgement"\
                        " [%s]" % str(rxDataDict['r']).strip()
                waitForAcknowlege = False
                break

    def WaitForResponse(self):
        waitForResponse = True
        rxDataDict = {}

        while (waitForResponse):
            rxDataDict = self.SerialRead()

            if self.swState == gc.STATE_ABORT:
                waitForResponse = False

            if 'rx_data' in rxDataDict:
                if len(rxDataDict['rx_data'].strip()) > 0:
                    waitForResponse = False

            self.Tick()

            if self.endThread:
                waitForResponse = False

            if self.lastEventID == gc.EV_CMD_STOP:
                waitForResponse = False

            time.sleep(0.01)

        return rxDataDict

    def RunStepSendGcode(self, gcodeData):
        writeToDevice = True

        gcode = gcodeData.strip()

        if len(gcode) > 0:
            gcode = "%s\n" % (gcode)

            if self.machIfModule.okToSend(gcode):
                # write data
                self.SerialWrite(gcode)

                ''' Wait for acknowledge might no longer needed, the
                machine IF object will track the device queue
                all will manage whether or not we can send more
                commands to the IF'''
                # wait for response
                self.WaitForAcknowledge()
                # self.SerialRead()

                if self.machineAutoStatus:
                    self.machIfModule.doGetStatus()
            else:
                writeToDevice = False
                self.SerialRead()

        if writeToDevice:
            self.workingProgramCounter += 1

            # if we stop early make sure to update PC to main UI
            if self.swState == gc.STATE_IDLE:
                self.progExecOutQueue.put(gc.SimpleEvent(
                    gc.EV_PC_UPDATE, self.workingProgramCounter))

    def ProcessRunSate(self):
        # send data to serial port ----------------------------------------------

        # check if we are done with gcode
        if self.workingProgramCounter >= len(self.gcodeDataLines):
            self.swState = gc.STATE_IDLE
            self.progExecOutQueue.put(gc.SimpleEvent(gc.EV_RUN_END, None))
            if self.cmdLineOptions.vverbose:
                print "** programExecuteThread reach last PC, swState->gc.gSTATE_IDLE"
            return

        # update PC
        if self.lastWorkingCounterWorking != self.workingProgramCounter:
            self.progExecOutQueue.put(gc.SimpleEvent(
                gc.EV_PC_UPDATE, self.workingProgramCounter))
            self.lastWorkingCounterWorking = self.workingProgramCounter

        # check for break point hit
        if (self.workingProgramCounter in self.breakPointSet) and \
           (self.workingProgramCounter != self.initialProgramCounter):
            self.swState = gc.STATE_BREAK
            self.progExecOutQueue.put(gc.SimpleEvent(gc.EV_HIT_BRK_PT, None))
            if self.cmdLineOptions.vverbose:
                print "** programExecuteThread encounter breakpoint PC[%s], swState->gc.gSTATE_BREAK" % \
                    (self.workingProgramCounter)
            return

        # get gcode line
        gcode = self.gcodeDataLines[self.workingProgramCounter]

        # check for msg line
        reMsgSearch = gReGcodeMsg.search(gcode)
        if (reMsgSearch is not None) and \
           (self.workingProgramCounter != self.initialProgramCounter):
            self.swState = gc.STATE_BREAK
            self.progExecOutQueue.put(gc.SimpleEvent(
                gc.EV_HIT_MSG, reMsgSearch.group(1)))
            if self.cmdLineOptions.vverbose:
                print "** programExecuteThread encounter MSG line PC[%s], swState->gc.gSTATE_BREAK, MSG[%s]" % \
                    (self.workingProgramCounter, reMsgSearch.group(1))
            return

        # don't sent unnecessary data save the bits for speed
        for reComments in gReGcodeComments:
            gcode = reComments.sub("", gcode)

        # send g-code command
        self.RunStepSendGcode(gcode)

    def ProcessStepSate(self):
        # send data to serial port ----------------------------------------------

        # check if we are done with gcode
        if self.workingProgramCounter >= len(self.gcodeDataLines):
            self.swState = gc.STATE_IDLE
            self.progExecOutQueue.put(gc.SimpleEvent(gc.EV_STEP_END, None))
            if self.cmdLineOptions.vverbose:
                print "** programExecuteThread reach last PC, swState->gc.gSTATE_IDLE"
            return

        # update PC
        self.progExecOutQueue.put(gc.SimpleEvent(
            gc.EV_PC_UPDATE, self.workingProgramCounter))

        # end IDLE state
        if self.workingProgramCounter > self.initialProgramCounter:
            self.swState = gc.STATE_IDLE
            self.progExecOutQueue.put(gc.SimpleEvent(gc.EV_STEP_END, None))
            if self.cmdLineOptions.vverbose:
                print "** programExecuteThread finish STEP cmd, swState->gc.gSTATE_IDLE"
            return

        gcode = self.gcodeDataLines[self.workingProgramCounter]

        # don't sent unnecessary data save the bits for speed
        for reComments in gReGcodeComments:
            gcode = reComments.sub("", gcode)

        self.RunStepSendGcode(gcode)

    def ProcessIdleSate(self):
        self.SerialRead()

    def ProcessSerialWriteQueue(self):
        if len(self.serialWriteQueue) > 0:

            data = self.serialWriteQueue[0]

            if self.machIfModule.okToSend(data[0]):
                self.serialWriteQueue.pop(0)
                self.SerialWrite(data[0])

                if data[1]:
                    self.WaitForAcknowledge()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread.
        self.endThread = False

        if self.cmdLineOptions.vverbose:
            print "** programExecuteThread start."

        # inti machine interface
        self.machIfModule.open()

        while(self.endThread != True):

            # process bookeeping input queue for new commands or actions
            self.Tick()

            # process write queue from UI cmds
            self.ProcessSerialWriteQueue()

            # check if we need to exit now
            if self.endThread:
                break

            if self.swState == gc.STATE_RUN:
                self.ProcessRunSate()
            elif self.swState == gc.STATE_STEP:
                self.ProcessStepSate()
            elif self.swState == gc.STATE_IDLE:
                self.ProcessIdleSate()
            elif self.swState == gc.STATE_BREAK:
                self.ProcessIdleSate()
            elif self.swState == gc.STATE_ABORT:
                self.ProcessIdleSate()
                break
            else:
                if self.cmdLineOptions.verbose:
                    print "** programExecuteThread unexpected state [%d], moving back to IDLE." \
                        ", swState->gc.gSTATE_IDLE " % (self.swState)

                self.ProcessIdleSate()
                self.swState = gc.STATE_IDLE

            time.sleep(0.01)

        if self.cmdLineOptions.vverbose:
            print "** programExecuteThread exit."

        self.progExecOutQueue.put(gc.SimpleEvent(gc.EV_EXIT, ""))
        wx.PostEvent(self.notifyWindow, gc.ThreadQueueEvent(None))
