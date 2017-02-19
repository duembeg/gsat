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
      
      self.serialPort = None
      self.serialTxRxThread = None
      self.serialTxRxInQueue = Queue.Queue()
      self.serialTxRxOutQueue = Queue.Queue()
      

   def Close(self):
      if self.serialTxRxThread is not None:
         self.serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_EXIT, None))

   def Encode(self, data):
      return data

   def Decode(self, data):
      return data

   def GetSetAxisCmd (self):
      return ""
      
   def GetId(self):
      return self.id
      
   def GetName(self):
      return self.name

   def GetStatus(self):
      return ""

   def Init(self, serial):
      self.serialPort = serial
      
   def InitComm(self):
      return ""

   def Open(self):
      # inti serial RX thread
      self.serialTxRxThread = st.serialPortThread(self, self.serialPort, self.serialTxRxOutQueue,
      self.serialTxRxInQueue, self.cmdLineOptions)
      self.Write(self.InitComm())

   def Read(self):
      rxData = {}
      
      if self.serialTxRxThread is not None:

         if not self.serialTxRxInQueue.empty():
            # get item from queue
            e = self.serialTxRxInQueue.get()

            if e.event_id == gc.gEV_ABORT:
               rxData['event'] = gc.gEV_ABORT

            elif e.event_id == gc.gEV_SER_RXDATA:

               if len(e.data) > 0:
                  rxData = self.Decode(e.data)
                  rxData['raw_data'] = e.data
      
      return rxData

   def Write(self, txData, raw_write=False):
      bytesSent = 0
      
      if self.serialTxRxThread is not None:
         
         if not raw_write:
            txData = self.Encode(txData)
               
         self.serialTxRxOutQueue.put(gc.threadEvent(gc.gEV_CMD_SEND, 
               txData))
         
         bytesSent = len(txData)
         
      return bytesSent
