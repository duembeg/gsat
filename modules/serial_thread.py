"""----------------------------------------------------------------------------
   serial_trhead.py

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
import sys
import serial
import threading
import Queue
import time
import pdb
import wx

import modules.config as gc

"""----------------------------------------------------------------------------
   serialPortThread:
   Threads that monitor serial port for new data and sends events to
   main window.
----------------------------------------------------------------------------"""
class serialPortThread(threading.Thread):
   """Worker Thread Class."""
   def __init__(self, notify_window, serial, in_queue, out_queue, cmd_line_options):
      """Init Worker Thread Class."""
      threading.Thread.__init__(self)

      # init local variables
      self.notifyWindow = notify_window
      self.serPort = serial
      self.serialThreadInQueue = in_queue
      self.serialThreadOutQueue = out_queue
      self.cmdLineOptions = cmd_line_options

      self.rxBuffer = ""

      self.swState = gc.gSTATE_RUN

      # start thread
      self.start()

   """-------------------------------------------------------------------------
   serialPortThread: Main Window Event Handlers
   Handle events coming from main UI
   -------------------------------------------------------------------------"""
   def ProcessQueue(self):
      # process events from queue ---------------------------------------------
      if not self.serialThreadInQueue.empty():
         # get item from queue
         e = self.serialThreadInQueue.get()

         if e.event_id == gc.gEV_CMD_EXIT:
            if self.cmdLineOptions.vverbose:
               print "** serialPortThread got event gc.gEV_CMD_EXIT."
            self.endThread = True
         
         elif e.event_id == gc.gEV_CMD_SEND:
            if self.cmdLineOptions.vverbose:
               print "** serialPortThread got event gc.gEV_CMD_SEND."
            self.SerialWrite(e.data)

         else:
            if self.cmdLineOptions.vverbose:
               print "** serialPortThread got unknown event!! [%s]." % str(e.event_id)

   """-------------------------------------------------------------------------
   serialPortThread: General Functions
   -------------------------------------------------------------------------"""
   def SerialRead(self):
      exFlag = False
      exMsg = ""
      serialData = ""

      try:
         inDataCnt = self.serPort.inWaiting()

         while inDataCnt > 0 and not exFlag:

            # read data from port
            # Was running with performance issues using readline(), move to read()
            # Using "".join() as performance is much better then "+="
            #serialData = self.serPort.readline()
            #self.rxBuffer += self.serPort.read(inDataCnt)
            self.rxBuffer = "".join([self.rxBuffer, self.serPort.read(inDataCnt)])

            while '\n' in self.rxBuffer:
               serialData, self.rxBuffer = self.rxBuffer.split('\n', 1)

               if len(serialData) > 0:
                  #pdb.set_trace()

                  if self.cmdLineOptions.vverbose:
                     print "[%03d] <- ASCII:{%s} HEX:{%s}" % (len(serialData),
                        serialData.strip(), ':'.join(x.encode('hex') for x in serialData))
                  elif self.cmdLineOptions.verbose:
                     print "[%03d] <- %s" % (len(serialData), serialData.strip())

                  # add data to queue
                  self.serialThreadOutQueue.put(gc.threadEvent(gc.gEV_SER_RXDATA, "%s\n" % serialData))
                  
                  # attempt to reduce starvation on other threads
                  # when serial traffic is constant
                  time.sleep(0.01)

            inDataCnt = self.serPort.inWaiting()

      except serial.SerialException, e:
         exMsg = "** PySerial exception: %s\n" % e.message
         exFlag = True

      except OSError, e:
         exMsg = "** OSError exception: %s\n" % str(e)
         exFlag = True

      except IOError, e:
         exMsg = "** IOError exception: %s\n" % str(e)
         exFlag = True

      if exFlag:
         # make sure we stop processing any states...
         self.swState = gc.gSTATE_ABORT

         if self.cmdLineOptions.verbose:
            print exMsg.strip()

         # add data to queue
         self.serialThreadOutQueue.put(gc.threadEvent(gc.gEV_ABORT, exMsg))

   def SerialWrite(self, serialData):
      exFlag = False
      exMsg = ""

      if len(serialData) == 0:
         return
         
      if self.serPort.isOpen():

         try:
            # send command
            self.serPort.write(serialData)

            if self.cmdLineOptions.vverbose:
               print "[%03d] -> ASCII:{%s} HEX:{%s}" % (len(serialData),
                  serialData.strip(), ':'.join(x.encode('hex') for x in serialData))
            elif self.cmdLineOptions.verbose:
               print "[%03d] -> %s" % (len(serialData), serialData.strip())

         except serial.SerialException, e:
            exMsg = "** PySerial exception: %s\n" % e.message
            exFlag = True

         except OSError, e:
            exMsg = "** OSError exception: %s\n" % str(e)
            exFlag = True

         except IOError, e:
            exMsg = "** IOError exception: %s\n" % str(e)
            exFlag = True
            
         except:
            e = sys.exc_info()[0]
            exMsg = "** Unexpected excetion: %s\n" % str(e)
            exFlag = True

         if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.gSTATE_ABORT

            if self.cmdLineOptions.verbose:
               print exMsg.strip()
         
   def run(self):
      """Run Worker Thread."""
      # This is the code executing in the new thread.
      self.endThread = False

      if self.cmdLineOptions.vverbose:
         print "** serialPortThread start."

      while(self.endThread != True):
         #print "** serialPortThread running.... QO: %d, QI:%d" % \
         #   (self.serialThreadOutQueue.qsize(), self.serialThreadInQueue.qsize())

         # process input queue for new commands or actions
         self.ProcessQueue()

         # check if we need to exit now
         if self.endThread:
            break
         
         if self.serPort.isOpen():
            if self.swState == gc.gSTATE_RUN:
               self.SerialRead()
            elif self.swState == gc.gSTATE_ABORT:
               # do nothing, wait to be terminated
               pass
            else:
               if self.cmdLineOptions.verbose:
                  print "** serialPortThread unexpected state [%d], moving back to IDLE." \
                     ", swState->gc.gSTATE_IDLE " % (self.swState)

               self.ProcessIdleSate()
               self.swState = gc.gSTATE_IDLE
         else:
            message ="** Serial Port is close, serialPortThread terminating.\n"

            if self.cmdLineOptions.verbose:
               print message.strip()

            # make sure we stop processing any states...
            self.swState = gc.gSTATE_ABORT

            # add data to queue
            self.serialThreadOutQueue.put(gc.threadEvent(gc.gEV_ABORT, ""))
            wx.LogMessage(message)
            break

         time.sleep(0.01)

      if self.cmdLineOptions.vverbose:
         print "** serialPortThread exit."
