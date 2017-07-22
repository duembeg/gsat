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
class machIf_Base():
   def __init__(self, cmd_line_options, id, name, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
      self.id = id
      self.name = name
      self.inputBufferMaxSize = input_buffer_max_size
      self.inputBufferWatermark = float(self.inputBufferMaxSize) * input_buffer_watermark_prcnt
      self.inputBufferSize = input_buffer_init_val

      self.cmdLineOptions = cmd_line_options

      self.serialPortOpen = False
      self.serialTxRxThread = None
      self.serialTxRxInQueue = Queue.Queue()
      self.serialTxRxOutQueue = Queue.Queue()
      self.stateData = None

   def _Reset(self, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
      self.inputBufferMaxSize = input_buffer_max_size
      self.inputBufferWatermark = float(self.inputBufferMaxSize) * input_buffer_watermark_prcnt
      self.inputBufferSize = input_buffer_init_val


   def Close(self):
      if self.serialTxRxThread is not None:
         self.serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_EXIT, None))

   def Encode(self, data):
      return data

   def Decode(self, data):
      return data

   def GetCycleStartCmd (self):
      return "~"

   def GetId(self):
      return self.id

   def GetFeedHoldCmd (self):
      return "!"

   def GetInitCommCmd (self):
      return ""

   def GetName(self):
      return self.name

   def GetQueueFlushCmd (self):
      return ""

   def GetResetCmd (self):
      return "\x18"

   def GetSetAxisCmd (self):
      return ""

   def GetStatusCmd(self):
      return ""

   def GetStatus(self):
      if self.OkToSend(self.GetStatusCmd()):
         self.Write(self.GetStatusCmd())

   def Init(self, state_data):
      self.stateData = state_data

   def IsSerialPortOpen(self):
      return self.serialPortOpen

   def OkToSend(self, data):
      bufferHasRoom = True

      data = self.Encode(data, bookeeping=False)

      if (self.inputBufferSize + len(data)) > self.inputBufferWatermark:
         bufferHasRoom = False

      return bufferHasRoom

   def Open(self):
      if self.stateData is not None:
         # inti serial RX thread
         self.serialTxRxThread = st.serialPortThread(self, self.stateData, self.serialTxRxOutQueue,
         self.serialTxRxInQueue, self.cmdLineOptions)
         self.Write(self.GetInitCommCmd())

   def Read(self):
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
                  rxData = self.Decode(e.data)
                  rxData['raw_data'] = e.data

            #print gc.gStateData.machIfId
            #print gc.gStateData.machIfName

      return rxData
      
   def Reset(self):
      pass

   def Tick(self):
      pass

   def Write(self, txData, raw_write=False):
      bytesSent = 0

      if self.serialTxRxThread is not None:

         if not raw_write:
            txData = self.Encode(txData)

         self.serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_SER_TXDATA,
               txData))

         bytesSent = len(txData)

      return bytesSent
