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

   id = 0
   name = ""
   inputBufferMaxSize = 100
   inputBufferWatermark = 90 #float(self.inputBufferMaxSize) * 0.9
   inputBufferWatermarkPrcnt = 0.9
   inputBufferSize = 0
   inputBufferInitVal = 0
   cmdLineOptions = None
   serialPortOpen = False
   serialTxRxThread = None
   serialTxRxInQueue = None
   serialTxRxOutQueue = None
   stateData = None

   def __init__(self, cmd_line_options, id, name, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
      self.id = id
      self.name = name
      self.inputBufferMaxSize = input_buffer_max_size
      self.inputBufferWatermarkPrcnt = input_buffer_watermark_prcnt
      self.inputBufferWatermark = float(self.inputBufferMaxSize) * self.inputBufferWatermarkPrcnt
      self.inputBufferInitVal = input_buffer_init_val
      self.inputBufferSize = self.inputBufferInitVal

      self.cmdLineOptions = cmd_line_options

      self.serialPortOpen = False
      self.serialTxRxThread = None
      self.serialTxRxInQueue = Queue.Queue()
      self.serialTxRxOutQueue = Queue.Queue()
      self.stateData = None

   def _reset(self, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
      self.inputBufferMaxSize = input_buffer_max_size
      self.inputBufferWatermark = float(self.inputBufferMaxSize) * input_buffer_watermark_prcnt
      self.inputBufferSize = input_buffer_init_val

   def close(self):
      if self.serialTxRxThread is not None:
         self.serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_EXIT, None))

   @abstractmethod
   def decode(self, data):
      return data

   @abstractmethod
   def encode(self, data):
      return data

   @abstractmethod
   def factory(self, cmd_line_options):
      return None

   def getCycleStartCmd (self):
      return "~"

   def getId(self):
      return self.id

   def getFeedHoldCmd (self):
      return "!"

   def getInitCommCmd (self):
      return ""

   def getName(self):
      return self.name

   def getQueueFlushCmd (self):
      return ""

   def getProbeAxisCmd (self):
      return "G38.2"

   def getResetCmd (self):
      return "\x18"

   def getSetAxisCmd (self):
      return "G92"

   def getStatusCmd(self):
      return ""

   def getStatus(self):
      if self.okToSend(self.getStatusCmd()):
         self.write(self.getStatusCmd())

   def init(self, state_data):
      self.stateData = state_data

   def isSerialPortOpen(self):
      return self.serialPortOpen

   def okToSend(self, data):
      bufferHasRoom = True

      data = self.encode(data, bookeeping=False)

      if (self.inputBufferSize + len(data)) > self.inputBufferWatermark:
         bufferHasRoom = False

      return bufferHasRoom

   def open(self):
      if self.stateData is not None:
         # inti serial RX thread
         self.serialTxRxThread = st.SerialPortThread(self, self.stateData, self.serialTxRxOutQueue,
         self.serialTxRxInQueue, self.cmdLineOptions)
         self.write(self.getInitCommCmd())

   def read(self):
      rxData = {}

      if self.serialTxRxThread is not None:

         if not self.serialTxRxInQueue.empty():
            # get item from queue
            e = self.serialTxRxInQueue.get()

            if e.event_id in [gc.gEV_EXIT, gc.gEV_ABORT, gc.gEV_SER_PORT_OPEN,
               gc.gEV_SER_PORT_CLOSE]:
               rxData['event'] = {}
               rxData['event']['id'] = e.event_id
               rxData['event']['data'] = e.data

               if e.event_id == gc.gEV_SER_PORT_OPEN:
                  self.serialPortOpen = True

               elif e.event_id == gc.gEV_SER_PORT_CLOSE:
                  self.serialPortOpen = False

            elif e.event_id == gc.gEV_SER_RXDATA:

               if len(e.data) > 0:
                  rxData = self.decode(e.data)
                  rxData['raw_data'] = e.data

      return rxData

   def reset(self):
      pass

   def tick(self):
      pass

   def write(self, txData, raw_write=False):
      bytesSent = 0

      if self.serialTxRxThread is not None:

         if not raw_write:
            txData = self.encode(txData)

         # in current design there is only one thread writing, bypass queue
         # to improve jogging. This should be safe as there is only one thread
         # writing and one reading. If issues start happening go back to queuing
         # solution, UPDATE: there was no observable benefit.
         # self.serialTxRxThread.serialWrite(txData)

         self.serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_SER_TXDATA,
               txData))

         bytesSent = len(txData)

      return bytesSent
