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

# import os
# import re
import threading
import time

import wx

import modules.config as gc


class ScriptExecuteThread(threading.Thread, gc.EventQueueIf):
    """  Threads that executes the scripts that directly interface with
    machif_progexec.
    This thread allows the UI to continue being responsive to user input
    while this thread is busy executing program or waiting for serial
    events.
    """

    def __init__(self, event_handler, state_data, cmd_line_options):
        """Init Worker Thread Class."""
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        self.eventHandler = event_handler
        self.stateData = state_data
        self.cmdLineOptions = cmd_line_options
        self.okToPostEvents = True

        self.swState = gc.STATE_IDLE

        # start thread
        self.start()

    def processQueue(self):
        """ Handle events coming from main UI
        """
        # process events from queue
        if not self._eventQueue.empty():
            # get item from queue
            e = self._eventQueue.get()

            self.lastEventID = e.event_id

            if e.event_id == gc.EV_CMD_EXIT:
                if self.cmdLineOptions.vverbose:
                    print "** scriptExecuteThread got event gc.gEV_CMD_EXIT."

                self.endThread = True
                self.swState = gc.STATE_IDLE

            elif e.event_id == gc.EV_CMD_RUN:
                if self.cmdLineOptions.vverbose:
                    print "** scriptExecuteThread got event gc.gEV_CMD_RUN, "\
                        "swState->gc.gSTATE_RUN"
                self.swState = gc.STATE_RUN

            elif e.event_id == gc.EV_CMD_STOP:
                if self.cmdLineOptions.vverbose:
                    print "** scriptExecuteThread got event gc.gEV_CMD_STOP, "\
                        "swState->gc.gSTATE_IDLE"

                self.swState = gc.STATE_IDLE

            elif e.event_id == gc.EV_CMD_GET_STATUS:
                if self.cmdLineOptions.vverbose:
                    print "** scriptExecuteThread got event "\
                        "gc.gEV_CMD_GET_STATUS."

            else:
                if self.cmdLineOptions.vverbose:
                    print "** scriptExecuteThread got unknown event!!"\
                        " [%s]." % str(e.event_id)

    def tick(self):
        return

    def waitForReady(self):
        return

    def processRunSate(self):
        """ Process RUN state and update counters or end state
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
            print "** scriptExecuteThread start."

        # inti machine interface
        self.machIfModule.open()

        while (not self.endThread):

            # process bookeeping input queue for new commands or actions
            self.tick()

            # process write queue from UI cmds
            self.processSerialWriteQueue()

            # check if we need to exit now
            if self.endThread:
                break

            if self.swState == gc.STATE_RUN:
                self.processRunSate()
            elif self.swState == gc.STATE_IDLE:
                self.processIdleSate()
            elif self.swState == gc.STATE_ABORT:
                self.processIdleSate()
                break
            else:
                if self.cmdLineOptions.verbose:
                    print "** scriptExecuteThread unexpected state "\
                        "[%d], moving back to IDLE." \
                        ", swState->gc.gSTATE_IDLE " % (self.swState)

                self.processIdleSate()
                self.swState = gc.STATE_IDLE

            time.sleep(0.01)

        if self.cmdLineOptions.vverbose:
            print "** scriptExecuteThread exit."

        self.eventHandler.eveventPut(gc.EV_EXIT, "")
        #wx.PostEvent(self.notifyWindow, gc.ThreadQueueEvent(None))
