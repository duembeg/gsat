"""----------------------------------------------------------------------------
   script_progexec.py

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

class ScriptExecuteThread(threading.Thread):
    """  Threads that executes the scripts that directly interface with
    machif_progexec.
    This thread allows the UI to continue being responsive to user input
    while this thread is busy executing program or waiting for serial
    events.
    """

    def __init__(self, notify_window, state_data, in_queue, out_queue, cmd_line_options):
        """Init Worker Thread Class."""
        threading.Thread.__init__(self)

        # init local variables
        self.notifyWindow = notify_window
        self.stateData = state_data
        self.scriptExecInQueue = in_queue
        self.progExecOutQueue = out_queue
        self.cmdLineOptions = cmd_line_options
        self.okToPostEvents = True

        self.gcodeDataLines = []
        self.breakPointSet = set()
        self.initialProgramCounter = 0
        self.workingCounterWorking = 0
        self.lastWorkingCounterWorking = -1

        self.swState = gc.STATE_IDLE
        self.lastEventID = gc.EV_CMD_NULL

        self.serialWriteQueue = []

        self.machIfModule = None

        # init device module
        self.initMachineIfModule()

        # start thread
        self.start()

    def processQueue(self):
        """ Handle events coming from main UI
        """
        # check output queue and notify UI if is not empty
        if not self.progExecOutQueue.empty():
            # if self.okToPostEvents:
            #   self.okToPostEvents = False
            #   wx.PostEvent(self.notifyWindow, gc.threadQueueEvent(None))
            wx.PostEvent(self.notifyWindow, gc.ThreadQueueEvent(None))

        # process events from queue ---------------------------------------------
        if not self.scriptExecInQueue.empty():
            # get item from queue
            e = self.scriptExecInQueue.get()

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

    def tick(self):
        return

    def waitForReady(self):
        return

    def processRunSate(self):
        """ Process RUN state and update counters or end state
        """
        return

    def processStepSate(self):
        """ Process STEP state and update counters or end state
        """
        return

    def processIdleSate(self):
        self.serialRead()

    def processSerialWriteQueue(self):
        pass

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
                if self.cmdLineOptions.verbose:
                    print "** programExecuteThread unexpected state [%d], moving back to IDLE." \
                        ", swState->gc.gSTATE_IDLE " % (self.swState)

                self.processIdleSate()
                self.swState = gc.STATE_IDLE

            time.sleep(0.01)

        if self.cmdLineOptions.vverbose:
            print "** programExecuteThread exit."

        self.progExecOutQueue.put(gc.SimpleEvent(gc.EV_EXIT, ""))
        wx.PostEvent(self.notifyWindow, gc.ThreadQueueEvent(None))
