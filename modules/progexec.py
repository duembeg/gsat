"""----------------------------------------------------------------------------
   progexec.py

   Copyright (C) 2013-2014 Wilhelm Duembeg

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

# -----------------------------------------------------------------------------
# regular expressions
# -----------------------------------------------------------------------------
gReAxis = re.compile(r'([XYZ])(\s*[-+]*\d+\.{0,1}\d*)', re.IGNORECASE)

# -------------
# Grbl

# grbl version, example "Grbl 0.8c ['$' for help]"
gReGrblVersion = re.compile(r'Grbl\s*(.*)\s*\[.*\]')

# status,
# quick re check to avoid multiple checks, speeds things up
gReMachineStatus = re.compile(r'pos', re.I)

# GRBL example "<Run,MPos:20.163,0.000,0.000,WPos:20.163,0.000,0.000>"
gReGRBLMachineStatus = re.compile(r'<(\w+)[,\|].*WPos:([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+),([+-]{0,1}\d+\.\d+)')

# -------------
#TinyG/TinyG2

# TinyG detect, example "tinyg [mm] ok>"
gReTinyGDetect = re.compile(r'tinyg\s+(.*)\s+ok>')

# tinyG example posx:12.000,posy:12.200,posz:10.000,vel:0.000,stat:3
gReTinyGVerbose = re.compile(r'(\w*):(-?\d+\.?\d*)')

# tinyG query response example:
#X position:          30.408 mm
#Y position:          20.701 mm
#Z position:          10.000 mm
#Machine state:       Stop
gReTinyGPosStatus = re.compile(r'(\w*)\s+position:\s+(-?\d+\.?\d*)\s+.*')
gReTinyGStateStatus = re.compile(r'(\w*)\s+state:\s+(\w*).*')

# tinyG query response example:
#X machine posn:      30.408 mm
#Y machine posn:      20.701 mm
#Z machine posn:      10.000 mm
#Machine state:       Stop
gReTinyG2PosStatus = re.compile(r'(\w*)\s+machine posn:\s+(-?\d+\.?\d*)\s+.*')

# -------------

# comments example "( comment string )" or "; comment string"
gReGcodeComments = [re.compile(r'\(.*\)'), re.compile(r';.*')]

# message example "(MSG, CHANGE TOOL BIT: to drill size 0.81300 mm)"
gReGcodeMsg = re.compile(r'^\s*\(MSG,(.+)\)')

# acknowledge
gReAcknowlege = [
   re.compile(r'^ok\s$'),     # grbl example  "ok"
   re.compile(r'\sok>\s$')    # tinyG example "tinyg [xxx] ok>"
]

gReErrorAck = [
   re.compile(r'^error:.*\s$'),     # grbl
   re.compile(r'^.*\serr\[\d*\].*$')    # tinyG "tinyg [mm] err[201]: Move < min length: G00 Z5.0000"
]

"""----------------------------------------------------------------------------
   gsatProgramExecuteThread:
   Threads that executes the gcode sending code to serial port. This thread
   allows the UI to continue being responsive to user input while this
   thread is busy executing program or waiting for serial events.
   Additionally it helps for user input not to disturb the rate and flow
   of data sent to the serial port.
----------------------------------------------------------------------------"""
class gsatProgramExecuteThread(threading.Thread):
   """Worker Thread Class."""
   def __init__(self, notify_window, serial, in_queue, out_queue, cmd_line_options, device_id, machine_auto_status=False):
      """Init Worker Thread Class."""
      threading.Thread.__init__(self)

      # init local variables
      self.notifyWindow = notify_window
      self.serPort = serial
      self.progExecInQueue = in_queue
      self.progExecOutQueue = out_queue
      self.progExecSerialRxInQueue = Queue.Queue()
      self.progExecSerialRxOutQueue = Queue.Queue()
      self.cmdLineOptions = cmd_line_options
      self.deviceID = device_id
      self.deviceDetected = False
      self.okToPostEvents = True

      self.gcodeDataLines = []
      self.breakPointSet = set()
      self.initialProgramCounter = 0
      self.workingCounterWorking = 0

      self.swState = gc.gSTATE_IDLE
      self.lastEventID = gc.gEV_CMD_NULL

      self.machineAutoStatus = machine_auto_status

      self.serialRxThread = None

      self.serialWriteQueue = []

      # start thread
      self.start()

   """-------------------------------------------------------------------------
   gsatProgramExecuteThread: Main Window Event Handlers
   Handle events coming from main UI
   -------------------------------------------------------------------------"""
   def ProcessQueue(self):
      # check output queue and notify UI if is not empty
      if not self.progExecOutQueue.empty():
         if self.okToPostEvents:
            self.okToPostEvents = False
            wx.PostEvent(self.notifyWindow, gc.threadQueueEvent(None))

      # process events from queue ---------------------------------------------
      if not self.progExecInQueue.empty():
         # get item from queue
         e = self.progExecInQueue.get()

         self.lastEventID = e.event_id

         if e.event_id == gc.gEV_CMD_EXIT:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_EXIT."
            self.endThread = True
            self.swState = gc.gSTATE_IDLE

            if self.serialRxThread is not None:
               self.progExecSerialRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_EXIT, None))

         elif e.event_id == gc.gEV_CMD_RUN:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_RUN, swState->gc.gSTATE_RUN"
            self.gcodeDataLines = e.data[0]
            self.initialProgramCounter = e.data[1]
            self.workingProgramCounter = self.initialProgramCounter
            self.breakPointSet =  e.data[2]
            self.swState = gc.gSTATE_RUN

         elif e.event_id == gc.gEV_CMD_STEP:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_STEP, swState->gc.gSTATE_STEP"
            self.gcodeDataLines = e.data[0]
            self.initialProgramCounter = e.data[1]
            self.workingProgramCounter = self.initialProgramCounter
            self.breakPointSet =  e.data[2]
            self.swState = gc.gSTATE_STEP

         elif e.event_id == gc.gEV_CMD_STOP:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_STOP, swState->gc.gSTATE_IDLE"

            self.swState = gc.gSTATE_IDLE

         elif e.event_id == gc.gEV_CMD_SEND:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_SEND."
            self.serialWriteQueue.append((e.data, False))

         elif e.event_id == gc.gEV_CMD_SEND_W_ACK:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_SEND_W_ACK."
            self.serialWriteQueue.append((e.data, True))

         elif e.event_id == gc.gEV_CMD_AUTO_STATUS:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_AUTO_STATUS."
            self.machineAutoStatus = e.data

         elif e.event_id == gc.gEV_CMD_OK_TO_POST:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got event gc.gEV_CMD_OK_TO_POST."
            self.okToPostEvents = True

         else:
            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread got unknown event!! [%s]." % str(e.event_id)

   """-------------------------------------------------------------------------
   gsatProgramExecuteThread: General Functions
   -------------------------------------------------------------------------"""
   def SerialWrite(self, serialData):
      exFlag = False
      exMsg = ""

      # sent data to UI
      self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DATA_OUT, serialData))

      try:
         # send command
         self.serPort.write(serialData.encode('ascii'))

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

      if exFlag:
         # make sure we stop processing any states...
         self.swState = gc.gSTATE_ABORT

         if self.cmdLineOptions.verbose:
            print exMsg.strip()

         # add data to queue and signal main window
         self.progExecOutQueue.put(gc.threadEvent(gc.gEV_ABORT, exMsg))
         wx.PostEvent(self.notifyWindow, gc.threadQueueEvent(None))


   def DecodeStatusData (self, serialData):

      # -----------------------------------------------------------------
      # Grbl
      if self.deviceID == gc.gDEV_GRBL:

         # GRBL status data
         rematch = gReGRBLMachineStatus.match(serialData)
         # data is expected to be an array of strings as follows
         # statusData[0] : Machine state
         # statusData[1] : Machine X
         # statusData[2] : Machine Y
         # statusData[3] : Machine Z
         # statusData[4] : Work X
         # statusData[5] : Work Y
         # statusData[6] : Work Z

         if rematch is not None:
            statusData = rematch.groups()
            machineStatus = dict()
            machineStatus['stat'] = statusData[0]
            machineStatus['posx'] = statusData[1]
            machineStatus['posy'] = statusData[2]
            machineStatus['posz'] = statusData[3]
            #machineStatus['wposx'] = statusData[4]
            #machineStatus['wposy'] = statusData[5]
            #machineStatus['wposz'] = statusData[6]

            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread re GRBL status match %s" % str(statusData)
               print "** gsatProgramExecuteThread str match from %s" % str(serialData.strip())

            self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DATA_STATUS, machineStatus))


         elif self.deviceDetected == False:
            rematch = gReGrblVersion.match(serialData)
            if rematch is not None:
               self.deviceDetected = True
               self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DEVICE_DETECTED, None))

      # -----------------------------------------------------------------
      # TinyG and TinyG2
      if self.deviceID == gc.gDEV_TINYG or self.deviceID == gc.gDEV_TINYG2:

         if self.deviceDetected == False:
            rematch = gReTinyGDetect.findall(serialData)
            if len(rematch) > 0:
               self.deviceDetected = True
               self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DEVICE_DETECTED, None))

         # tinyG verbose/status
         rematch = gReTinyGVerbose.findall(serialData)
         if len(rematch) > 0:

            if self.cmdLineOptions.vverbose:
               print "** gsatProgramExecuteThread re tinyG verbose match %s" % str(rematch)
               print "** gsatProgramExecuteThread str match from %s" % str(serialData)

            machineStatus = dict(rematch)

            status = machineStatus.get('stat')
            if status is not None:
               if '0' in status:
                  machineStatus['stat'] = 'Init'
               elif '1' in status:
                  machineStatus['stat'] = 'Ready'
               elif '2' in status:
                  machineStatus['stat'] = 'Alarm'
               elif '3' in status:
                  machineStatus['stat'] = 'Stop'
               elif '4' in status:
                  machineStatus['stat'] = 'End'
               elif '5' in status:
                  machineStatus['stat'] = 'Run'
               elif '6' in status:
                  machineStatus['stat'] = 'Hold'
               elif '7' in status:
                  machineStatus['stat'] = 'Probe'
               elif '8' in status:
                  machineStatus['stat'] = 'Run'
               elif '9' in status:
                  machineStatus['stat'] = 'Home'

            self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DATA_STATUS, machineStatus))

         else:
            rematch = []

            if self.deviceID == gc.gDEV_TINYG2:
               rematch = gReTinyG2PosStatus.findall(serialData)
               
               # newer version (g2core) moved to TinyG style
               if len(rematch) == 0:
                  rematch = gReTinyGPosStatus.findall(serialData)
                  
            elif self.deviceID == gc.gDEV_TINYG:
               rematch = gReTinyGPosStatus.findall(serialData)

            if len(rematch) > 0:
               if self.cmdLineOptions.vverbose:
                  print "** gsatProgramExecuteThread re tinyG status match %s" % str(rematch)
                  print "** gsatProgramExecuteThread str match from %s" % str(serialData)

               machineStatus = dict()

               if self.deviceID == gc.gDEV_TINYG2:
                  machineStatus["mpo%s" % rematch[0][0].lower()] = rematch[0][1]
               elif self.deviceID == gc.gDEV_TINYG:
                  machineStatus["pos%s" % rematch[0][0].lower()] = rematch[0][1]

               self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DATA_STATUS, machineStatus))

            else:
               rematch = gReTinyGStateStatus.findall(serialData)

               if len(rematch) > 0:
                  if self.cmdLineOptions.vverbose:
                     print "** gsatProgramExecuteThread re tinyG status match %s" % str(serialData)

                  machineStatus = dict()
                  machineStatus["stat"] = rematch[0][1]

                  self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DATA_STATUS, machineStatus))

   def SerialRead(self):
      serialData = ""

      if not self.progExecSerialRxInQueue.empty():
         # get item from queue
         e = self.progExecSerialRxInQueue.get()

         if e.event_id == gc.gEV_ABORT:
            # make sure we stop processing any states...
            self.swState = gc.gSTATE_ABORT

            # add data to queue and signal main window to consume
            self.progExecOutQueue.put(gc.threadEvent(gc.gEV_ABORT, e.data))
            wx.PostEvent(self.notifyWindow, gc.threadQueueEvent(None))

         elif e.event_id == gc.gEV_SER_RXDATA:

            if len(e.data) > 0:

               # add data to queue and signal main window to consume
               self.progExecOutQueue.put(gc.threadEvent(gc.gEV_DATA_IN, e.data))

               serialData = e.data

               self.DecodeStatusData(serialData)

      return serialData

   def WaitForAcknowledge(self):
      waitForAcknowlege = True

      while (waitForAcknowlege):
         rxData = self.WaitForResponse()

         if self.swState == gc.gSTATE_ABORT:
            waitForAcknowlege = False

         if self.lastEventID == gc.gEV_CMD_STOP:
            waitForAcknowlege = False

         if self.endThread:
            waitForAcknowlege = False

         for reAcknowlege in gReAcknowlege:
            ack = reAcknowlege.search(rxData)

            if ack is not None:
               if self.cmdLineOptions.vverbose:
                  print "** gsatProgramExecuteThread found acknowledgement"\
                     " [%s]" % rxData.strip()
               waitForAcknowlege = False
               break

         for reErrorAck in gReErrorAck:
            errAck = reErrorAck.search(rxData)

            if errAck is not None:
               if self.cmdLineOptions.vverbose:
                  print "** gsatProgramExecuteThread found error acknowledgement"\
                     " [%s]" % rxData.strip()
               waitForAcknowlege = False
               break

   def WaitForResponse(self):
      waitForResponse = True
      rxData = ""

      while (waitForResponse):
         rxData = self.SerialRead()

         if self.swState == gc.gSTATE_ABORT:
            waitForResponse = False

         if len(rxData.strip()) > 0:
            waitForResponse = False

         self.ProcessQueue()

         if self.endThread:
            waitForResponse = False

         if self.lastEventID == gc.gEV_CMD_STOP:
            waitForResponse = False

         time.sleep(0.01)

      return rxData


   def RunStepSendGcode(self, gcodeData):
      gcode = gcodeData.strip()

      if len(gcode) > 0:
         if self.machineAutoStatus:
            if self.deviceID == gc.gDEV_TINYG2 or self.deviceID == gc.gDEV_TINYG:
               gcode = "%s%s" % (gcode, gc.gTINYG_CMD_GET_STATUS)
            elif self.deviceID == gc.gDEV_GRBL:
               gcode = "%s%s" % (gcode, gc.gGRBL_CMD_GET_STATUS)
         else:
            gcode = "%s\n" % (gcode)

         # write data
         self.SerialWrite(gcode)


         # wait for response
         #responseData = self.WaitForResponse()
         self.WaitForAcknowledge()

      self.workingProgramCounter += 1

      # if we stop early make sure to update PC to main UI
      if self.swState == gc.gSTATE_IDLE:
         self.progExecOutQueue.put(gc.threadEvent(gc.gEV_PC_UPDATE, self.workingProgramCounter))


   def ProcessRunSate(self):
      # send data to serial port ----------------------------------------------

      # check if we are done with gcode
      if self.workingProgramCounter >= len(self.gcodeDataLines):
         self.swState = gc.gSTATE_IDLE
         self.progExecOutQueue.put(gc.threadEvent(gc.gEV_RUN_END, None))
         if self.cmdLineOptions.vverbose:
            print "** gsatProgramExecuteThread reach last PC, swState->gc.gSTATE_IDLE"
         return

      # update PC
      self.progExecOutQueue.put(gc.threadEvent(gc.gEV_PC_UPDATE, self.workingProgramCounter))

      # check for break point hit
      if (self.workingProgramCounter in self.breakPointSet) and \
         (self.workingProgramCounter != self.initialProgramCounter):
         self.swState = gc.gSTATE_BREAK
         self.progExecOutQueue.put(gc.threadEvent(gc.gEV_HIT_BRK_PT, None))
         if self.cmdLineOptions.vverbose:
            print "** gsatProgramExecuteThread encounter breakpoint PC[%s], swState->gc.gSTATE_BREAK" % \
               (self.workingProgramCounter)
         return

      # get gcode line
      gcode = self.gcodeDataLines[self.workingProgramCounter]

      # check for msg line
      reMsgSearch = gReGcodeMsg.search(gcode)
      if (reMsgSearch is not None) and \
         (self.workingProgramCounter != self.initialProgramCounter):
         self.swState = gc.gSTATE_BREAK
         self.progExecOutQueue.put(gc.threadEvent(gc.gEV_HIT_MSG, reMsgSearch.group(1)))
         if self.cmdLineOptions.vverbose:
            print "** gsatProgramExecuteThread encounter MSG line PC[%s], swState->gc.gSTATE_BREAK, MSG[%s]" % \
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
         self.swState = gc.gSTATE_IDLE
         self.progExecOutQueue.put(gc.threadEvent(gc.gEV_STEP_END, None))
         if self.cmdLineOptions.vverbose:
            print "** gsatProgramExecuteThread reach last PC, swState->gc.gSTATE_IDLE"
         return

      # update PC
      self.progExecOutQueue.put(gc.threadEvent(gc.gEV_PC_UPDATE, self.workingProgramCounter))

      # end IDLE state
      if self.workingProgramCounter > self.initialProgramCounter:
         self.swState = gc.gSTATE_IDLE
         self.progExecOutQueue.put(gc.threadEvent(gc.gEV_STEP_END, None))
         if self.cmdLineOptions.vverbose:
            print "** gsatProgramExecuteThread finish STEP cmd, swState->gc.gSTATE_IDLE"
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
         data = self.serialWriteQueue.pop(0)
         self.SerialWrite(data[0])

         if data[1]:
            self.WaitForAcknowledge()

   def run(self):
      """Run Worker Thread."""
      # This is the code executing in the new thread.
      self.endThread = False

      if self.cmdLineOptions.vverbose:
         print "** gsatProgramExecuteThread start."

      # inti serial RX thread
      self.serialRxThread = gsatSerialPortThread(self, self.serPort, self.progExecSerialRxOutQueue,
      self.progExecSerialRxInQueue, self.cmdLineOptions)

      # init communication with device (helps to force tinyG into txt mode
      if self.deviceID == gc.gDEV_TINYG2 or self.deviceID == gc.gDEV_TINYG:
         self.SerialWrite(gc.gTINYG_CMD_GET_STATUS)
      elif self.deviceID == gc.gDEV_GRBL:
         self.SerialWrite(gc.gGRBL_CMD_GET_STATUS)
         self.SerialWrite(gc.gGRBL_CMD_GET_STATUS)

      while(self.endThread != True):

         # process input queue for new commands or actions
         self.ProcessQueue()

         # process write queue from UI cmds
         self.ProcessSerialWriteQueue()

         # check if we need to exit now
         if self.endThread:
            break

         if self.serPort.isOpen():
            if self.swState == gc.gSTATE_RUN:
               self.ProcessRunSate()
            elif self.swState == gc.gSTATE_STEP:
               self.ProcessStepSate()
            elif self.swState == gc.gSTATE_IDLE:
               self.ProcessIdleSate()
            elif self.swState == gc.gSTATE_BREAK:
               self.ProcessIdleSate()
            elif self.swState == gc.gSTATE_ABORT:
               # do nothing, wait to be terminated
               pass
            else:
               if self.cmdLineOptions.verbose:
                  print "** gsatProgramExecuteThread unexpected state [%d], moving back to IDLE." \
                     ", swState->gc.gSTATE_IDLE " % (self.swState)

               self.ProcessIdleSate()
               self.swState = gc.gSTATE_IDLE
         else:
            message ="** Serial Port is close, gsatProgramExecuteThread terminating.\n"

            if self.cmdLineOptions.verbose:
               print message.strip()

            # make sure we stop processing any states...
            self.swState = gc.gSTATE_ABORT

            # add data to queue and signal main window to consume
            self.progExecOutQueue.put(gc.threadEvent(gc.gEV_ABORT, ""))
            wx.PostEvent(self.notifyWindow, gc.threadQueueEvent(None))
            wx.LogMessage(message)
            break

         time.sleep(0.02)

      if self.cmdLineOptions.vverbose:
         print "** gsatProgramExecuteThread exit."

"""----------------------------------------------------------------------------
   gsatSerialPortThread:
   Threads that monitor serial port for new data and sends events to
   main window.
----------------------------------------------------------------------------"""
class gsatSerialPortThread(threading.Thread):
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
   gsatSerialPortThread: Main Window Event Handlers
   Handle events coming from main UI
   -------------------------------------------------------------------------"""
   def ProcessQueue(self):
      # process events from queue ---------------------------------------------
      if not self.serialThreadInQueue.empty():
         # get item from queue
         e = self.serialThreadInQueue.get()

         if e.event_id == gc.gEV_CMD_EXIT:
            if self.cmdLineOptions.vverbose:
               print "** gsatSerialPortThread got event gc.gEV_CMD_EXIT."
            self.endThread = True

         else:
            if self.cmdLineOptions.vverbose:
               print "** gsatSerialPortThread got unknown event!! [%s]." % str(e.event_id)

   """-------------------------------------------------------------------------
   gsatSerialPortThread: General Functions
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

   def run(self):
      """Run Worker Thread."""
      # This is the code executing in the new thread.
      self.endThread = False

      if self.cmdLineOptions.vverbose:
         print "** gsatSerialPortThread start."

      while(self.endThread != True):

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
                  print "** gsatSerialPortThread unexpected state [%d], moving back to IDLE." \
                     ", swState->gc.gSTATE_IDLE " % (self.swState)

               self.ProcessIdleSate()
               self.swState = gc.gSTATE_IDLE
         else:
            message ="** Serial Port is close, gsatSerialPortThread terminating.\n"

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
         print "** gsatSerialPortThread exit."
