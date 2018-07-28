"""----------------------------------------------------------------------------
   machif.py

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
import serial
import threading
import Queue
from abc import ABCMeta, abstractmethod

try:
    import simplejson as json
except ImportError:
    import json

import modules.config as gc
import modules.serial_thread as st

"""----------------------------------------------------------------------------
   machIf_Base:

   Machine interface base class to provide a unified API for specific devices
   (g2core, TinyG, grbl, etc).

----------------------------------------------------------------------------"""
class MachIf_Base(object):
   __metaclass__ = ABCMeta

   def __init__(self, cmd_line_options, id, name, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
      self.id = id
      self.name = name
      self._inputBufferMaxSize = input_buffer_max_size
      self._inputBufferWatermarkPrcnt = input_buffer_watermark_prcnt
      self._inputBufferWatermark = float(self._inputBufferMaxSize) * self._inputBufferWatermarkPrcnt
      self._inputBufferInitVal = input_buffer_init_val
      self._inputBufferSize = self._inputBufferInitVal

      self.cmdLineOptions = cmd_line_options

      self._serialPortOpen = False
      self._serialTxRxThread = None
      self._serialTxRxInQueue = Queue.Queue()
      self._serialTxRxOutQueue = Queue.Queue()
      self.stateData = None

      # cmds
      self.cmdCycleStart = '~'
      self.cmdFeedHold = '!'
      self.cmdInitComm = ''
      self.cmdQueueFlush = ''
      self.cmdProbeAxis = '"G38.2'
      self.cmdReset = '\x18'
      self.cmdSetAxis = 'G92'
      self.cmdStatus = ''

   @abstractmethod
   def _init(self):
      pass

   def _reset(self, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
      self._inputBufferMaxSize = input_buffer_max_size
      self._inputBufferWatermark = float(self._inputBufferMaxSize) * input_buffer_watermark_prcnt
      self._inputBufferSize = input_buffer_init_val

   def close(self):
      if self._serialTxRxThread is not None:
         self._serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_EXIT, None))

   @abstractmethod
   def decode(self, data):
      return data

   def doClearAlarm(self):
      pass

   def doCycleStartResume(self):
      self.write(self.getCycleStartCmd())

   def doFastMove(self, dirAxisCoor):
      pass

   def doFastMoveRelative(self, dirAxisCoor):
      pass

   def doFeedHold(self):
      self.write(self.getFeedHoldCmd())

   def doGetStatus(self):
      if self.okToSend(self.getStatusCmd()):
         self.write(self.getStatusCmd())

   def doMove(self, dirAxisCoor):
      pass

   def doMoveRelative(self, dirAxisCoor):
      pass

   def doReset(self):
      self.write(self.getResetCmd())
      self._init()

   def doQueueFlush(self):
      self.write(self.getQueueFlushCmd())
      self._init()

   @abstractmethod
   def encode(self, data, bookeeping=True):
      return data

   @abstractmethod
   def factory(self, cmd_line_options):
      return None

   def getCycleStartCmd (self):
      return self.cmdCycleStart

   def getId(self):
      return self.id

   def getFeedHoldCmd (self):
      return self.cmdFeedHold

   def getInitCommCmd (self):
      return self.cmdInitComm

   def getName(self):
      return self.name

   def getQueueFlushCmd (self):
      return self.cmdQueueFlush

   def getProbeAxisCmd (self):
      return self.cmdProbeAxis

   def getResetCmd (self):
      return self.cmdReset

   def getSetAxisCmd (self):
      return self.cmdSetAxis

   def getStatusCmd(self):
      return self.cmdStatus

   def init(self, state_data):
      self.stateData = state_data

   def isSerialPortOpen(self):
      return self._serialPortOpen

   def okToSend(self, data):

      bufferHasRoom = True

      # split lines
      lines = data.splitlines(True)

      for line in lines:
         data = self.encode(line, bookeeping=False)

         if (self._inputBufferSize + len(data)) > self._inputBufferWatermark:
            bufferHasRoom = False
            break

      return bufferHasRoom

   def open(self):
      if self.stateData is not None:
         # inti serial RX thread
         self._serialTxRxThread = st.SerialPortThread(self, self.stateData, self._serialTxRxOutQueue,
         self._serialTxRxInQueue, self.cmdLineOptions)
         self.write(self.getInitCommCmd())

   def read(self):
      rxData = {}

      if self._serialTxRxThread is not None:

         if not self._serialTxRxInQueue.empty():
            # get item from queue
            e = self._serialTxRxInQueue.get()

            if e.event_id in [gc.gEV_EXIT, gc.gEV_ABORT, gc.gEV_SER_PORT_OPEN,
               gc.gEV_SER_PORT_CLOSE]:
               rxData['event'] = {}
               rxData['event']['id'] = e.event_id
               rxData['event']['data'] = e.data

               if e.event_id == gc.gEV_SER_PORT_OPEN:
                  self._serialPortOpen = True

               elif e.event_id == gc.gEV_SER_PORT_CLOSE:
                  self._serialPortOpen = False

            elif e.event_id == gc.gEV_SER_RXDATA:

               if len(e.data) > 0:
                  rxData = self.decode(e.data)
                  rxData['raw_data'] = e.data

      return rxData

   def tick(self):
      pass

   def write(self, txData, raw_write=False):
      bytesSent = 0

      if self._serialTxRxThread is not None:

         if raw_write:
            # self._serialTxRxThread.serialWrite(txData)
            self._serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_SER_TXDATA,
                  txData))
         else:
            lines = txData.splitlines(True)

            for line in lines:
               line = self.encode(line)

               ''' in current design there is only one thread writing, will
                   bypass queue to improve jogging. This should be safe as
                   there is only one thread writing and one reading. If
                   issues start happening go back to queuing solution,

                   *** UPDATE: there was no observable benefit nor issues
                   Leaving this here to revisit in future .'''
               # self._serialTxRxThread.serialWrite(line)

               self._serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_SER_TXDATA,
                     line))

               bytesSent = bytesSent + len(line)

      return bytesSent
