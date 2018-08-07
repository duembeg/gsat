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
import Queue
from abc import ABCMeta, abstractmethod

import modules.config as gc
import modules.serial_thread as st


class MachIf_Base(object):
    """----------------------------------------------------------------------------
    machIf_Base:

    Machine interface base class to provide a unified API for specific devices
    (g2core, TinyG, grbl, etc).

    ----------------------------------------------------------------------------"""
    __metaclass__ = ABCMeta

    def __init__(self, cmd_line_options, if_id, name, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
        self.id = if_id
        self.name = name
        self._inputBufferMaxSize = input_buffer_max_size
        self._inputBufferWatermarkPrcnt = input_buffer_watermark_prcnt
        self._inputBufferWatermark = float(
            self._inputBufferMaxSize) * self._inputBufferWatermarkPrcnt
        self._inputBufferInitVal = input_buffer_init_val
        self._inputBufferSize = self._inputBufferInitVal

        self.cmdLineOptions = cmd_line_options

        self._serialPortOpen = False
        self._serialTxRxThread = None
        self._serialTxRxInQueue = Queue.Queue()
        self._serialTxRxOutQueue = Queue.Queue()
        self.stateData = None

        # machine
        self.machinePositionMode = "G90"
        self.machineStatus = -1

        # cmds
        self.cmdClearAlarm = ''
        self.cmdCycleStart = '~'
        self.cmdFeedHold = '!'
        self.cmdHome = 'G28.2'
        self.cmdInitComm = ''
        self.cmdQueueFlush = ''
        self.cmdProbeAxis = '"G38.2'
        self.cmdReset = '\x18'
        self.cmdSetAxis = 'G92'
        self.cmdStatus = ''

    @abstractmethod
    def _init(self):
        pass

    def _move(self, move_code, dictAxisCoor):
        """ Move to a coordinate in opsolute or relative position mode
        """
        machine_current_position_mode = self.machinePositionMode

        self._send_axis_cmd(move_code, dictAxisCoor)

        self._serialTxRxInQueue.put(
            gc.SimpleEvent(gc.EV_SER_TXDATA, "%s\n" % machine_current_position_mode)
        )

        self.write("".join([machine_current_position_mode,"\n"]))

    def _reset(self, input_buffer_max_size, input_buffer_init_val, input_buffer_watermark_prcnt):
        self._inputBufferMaxSize = input_buffer_max_size
        self._inputBufferWatermark = float(
            self._inputBufferMaxSize) * input_buffer_watermark_prcnt
        self._inputBufferSize = input_buffer_init_val

    def _send_axis_cmd(self, code, dictAxisCoor):
        """ sends axis cmd
        """
        machine_code = code

        if 'x' in dictAxisCoor:
            machine_code = "".join([
                machine_code, " X", str(dictAxisCoor.get('x'))
                ])

        if 'y' in dictAxisCoor:
            machine_code = "".join([
                machine_code, " Y", str(dictAxisCoor.get('y'))
                ])

        if 'z' in dictAxisCoor:
            machine_code = "".join([
                machine_code, " Z",str(dictAxisCoor.get('z'))
                ])

        if 'a' in dictAxisCoor:
            machine_code = "".join([
                machine_code, " A",str(dictAxisCoor.get('a'))
                ])

        if 'b' in dictAxisCoor:
            machine_code = "".join([
                machine_code, " B",str(dictAxisCoor.get('b'))
                ])

        if 'c' in dictAxisCoor:
            machine_code = "".join([
                machine_code, " C",str(dictAxisCoor.get('c'))
                ])

        if 'feed' in dictAxisCoor:
            machine_code = "".join([
                machine_code, " F",str(dictAxisCoor.get('feed'))
                ])

        self._serialTxRxInQueue.put(
            gc.SimpleEvent(gc.EV_SER_TXDATA, "%s\n" % machine_code)
        )

        self.write("".join([machine_code,"\n"]))

    def close(self):
        if self._serialTxRxThread is not None:
            self._serialTxRxOutQueue.put(gc.SimpleEvent(gc.EV_CMD_EXIT, None))

    @abstractmethod
    def decode(self, data):
        return data

    def doClearAlarm(self):
        """ Clears alarm condition
        """
        self._serialTxRxInQueue.put(gc.SimpleEvent(gc.EV_SER_TXDATA, self.cmdClearAlarm))
        self.write(self.cmdClearAlarm)
        self.write(self.getStatusCmd())

    def doCycleStartResume(self):
        """ send cycle resume command
        """
        self._serialTxRxInQueue.put(
            gc.SimpleEvent(gc.EV_SER_TXDATA, "%s\n" % self.cmdCycleStart)
        )

        self.write(self.cmdCycleStart)

    def doFastMove(self, dict_axis_coor):
        """ Fast (rapid) move to a coordinate in opsolute position mode
        """
        self._move("G90 G00", dict_axis_coor)


    def doFastMoveRelative(self, dict_axis_coor):
        """ Fast (rapid) move to a coordinate in relative position mode
        """
        self._move("G91 G00", dict_axis_coor)

    def doFeedHold(self):
        """ send feed hold command
        """
        self._serialTxRxInQueue.put(
            gc.SimpleEvent(gc.EV_SER_TXDATA, "%s\n" % self.cmdFeedHold)
        )

        self.write(self.cmdFeedHold)

    def doGetStatus(self):
        if self.okToSend(self.cmdStatus):
            self._serialTxRxInQueue.put(
                gc.SimpleEvent(gc.EV_SER_TXDATA, "%s\n" % self.cmdStatus)
            )

            self.write(self.cmdStatus)

    def doHome(self, dict_axis):
        self._send_axis_cmd(self.cmdHome, dict_axis)

    def doInitComm(self):
        self.write(self.cmdInitComm)

    def doMove(self, dict_axis_coor):
        """ Move to a coordinate in opsolute position mode
        """
        self._move("G90 G01", dict_axis_coor)

    def doMoveRelative(self, dict_axis_coor):
        """ Move to a coordinate in relative position mode
        """
        self._move("G91 G01", dict_axis_coor)

    def doQueueFlush(self):
        self.write(self.cmdQueueFlush)
        self._init()

    def doReset(self):
        self.write(self.cmdReset)
        self._init()

    def doSetAxis(self, dict_axis_coor):
        """ Set axis coordinates
        """
        self._send_axis_cmd(self.cmdSetAxis, dict_axis_coor)

    @abstractmethod
    def encode(self, data, bookeeping=True):
        return data

    @abstractmethod
    def factory(self, cmd_line_options):
        return None

    def getCycleStartCmd(self):
        return self.cmdCycleStart

    def getId(self):
        return self.id

    def getFeedHoldCmd(self):
        return self.cmdFeedHold

    def getInitCommCmd(self):
        return self.cmdInitComm

    def getName(self):
        return self.name

    def getQueueFlushCmd(self):
        return self.cmdQueueFlush

    def getProbeAxisCmd(self):
        return self.cmdProbeAxis

    def getResetCmd(self):
        return self.cmdReset

    def getSetAxisCmd(self):
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
            self.doInitComm()

    def read(self):
        """ Read and process data from txrx thread
        """
        dictData = {}

        if self._serialTxRxThread is not None:

            if not self._serialTxRxInQueue.empty():
                # get item from queue
                e = self._serialTxRxInQueue.get()

                if e.event_id in [gc.EV_EXIT, gc.EV_ABORT, gc.EV_SER_PORT_OPEN,
                                  gc.EV_SER_PORT_CLOSE]:
                    dictData['event'] = {}
                    dictData['event']['id'] = e.event_id
                    dictData['event']['data'] = e.data

                    if e.event_id == gc.EV_SER_PORT_OPEN:
                        self._serialPortOpen = True

                    elif e.event_id == gc.EV_SER_PORT_CLOSE:
                        self._serialPortOpen = False

                elif e.event_id == gc.EV_SER_RXDATA:

                    if len(e.data) > 0:
                        dictData = self.decode(e.data)
                        dictData['rx_data'] = e.data

                elif e.event_id == gc.EV_SER_TXDATA:

                    if len(e.data) > 0:
                        dictData['tx_data'] = e.data

        return dictData

    def tick(self):
        pass

    def write(self, txData, raw_write=False):
        """ process and write data to txrx thread
        """
        bytesSent = 0

        if self._serialTxRxThread is not None:

            if raw_write:
                # self._serialTxRxThread.serialWrite(txData)
                self._serialTxRxOutQueue.put(gc.SimpleEvent(gc.EV_CMD_SER_TXDATA,
                                                            txData))
            else:
                lines = txData.splitlines(True)

                for line in lines:
                    line = self.encode(line)

                    """ in current design there is only one thread writing, will
                    bypass queue to improve jogging. This should be safe as
                    there is only one thread writing and one reading. If
                    issues start happening go back to queuing solution,

                    *** UPDATE: there was no observable benefit nor issues
                    Leaving this here to revisit in future ."""
                    # self._serialTxRxThread.serialWrite(line)

                    self._serialTxRxOutQueue.put(gc.SimpleEvent(gc.EV_CMD_SER_TXDATA,
                                                                line))

                    bytesSent = bytesSent + len(line)

        return bytesSent
