"""----------------------------------------------------------------------------
   machif.py

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

import re
from abc import ABCMeta, abstractmethod
import logging

try:
    import queue
except ImportError:
    import Queue as queue

import modules.config as gc
import modules.serial_thread as st


class MachIf_Base(gc.EventQueueIf):
    """ Machine interface base class to provide a unified API for specific
        devices (g2core, TinyG, grbl, etc).
    """
    __metaclass__ = ABCMeta

    reMachiePositionMode = re.compile(r'.*(G9[0|1]).*')

    def __init__(
        self, if_id, name, input_buffer_max_size,
        input_buffer_init_val, input_buffer_watermark_prcnt
    ):
        gc.EventQueueIf.__init__(self)

        self.id = if_id
        self.name = name
        self._inputBufferMaxSize = input_buffer_max_size
        self._inputBufferWatermarkPrcnt = input_buffer_watermark_prcnt
        self._inputBufferWatermark = float(self._inputBufferMaxSize) * self._inputBufferWatermarkPrcnt
        self._inputBufferInitVal = input_buffer_init_val
        self._inputBufferSize = self._inputBufferInitVal

        self.logger = logging.getLogger()
        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD:
            self.logger.info("init logging id:0x%x" % id(self))

        self._serialPortOpen = False
        self._serialTxRxThread = None
        self.serialName = None
        self.serialBaud = None

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
        self.cmdProbeAxis = 'G38.2'
        self.cmdReset = '\x18'
        self.cmdSetAxis = 'G92'
        self.cmdStatus = ''
        self.cmdSystemInfo = ''

    @abstractmethod
    def _init(self):
        pass

    def _move(self, move_code, dict_axis_coor, resert_pos_mode=True):
        """ Move to a coordinate in obsolete or relative position mode
        """
        machine_current_position_mode = self.machinePositionMode

        self._sendAxisCmd(move_code, dict_axis_coor)

        if machine_current_position_mode != self.machinePositionMode and\
           resert_pos_mode:
            self.add_event(gc.EV_TXDATA, "{}\n".format(machine_current_position_mode))
            self.write("".join([machine_current_position_mode, "\n"]))

    def _reset(
        self, input_buffer_max_size, input_buffer_init_val,
        input_buffer_watermark_prcnt
    ):
        self._inputBufferMaxSize = input_buffer_max_size
        self._inputBufferWatermark = float(self._inputBufferMaxSize) * input_buffer_watermark_prcnt
        self._inputBufferSize = input_buffer_init_val

    def _sendAxisCmd(self, code, dict_axis_coor):
        """ sends axis cmd
        """
        machine_code = code

        if 'x' in dict_axis_coor:
            machine_code = "".join([machine_code, " X", str(dict_axis_coor.get('x'))])

        if 'y' in dict_axis_coor:
            machine_code = "".join([machine_code, " Y", str(dict_axis_coor.get('y'))])

        if 'z' in dict_axis_coor:
            machine_code = "".join([machine_code, " Z", str(dict_axis_coor.get('z'))])

        if 'a' in dict_axis_coor:
            machine_code = "".join([machine_code, " A", str(dict_axis_coor.get('a'))])

        if 'b' in dict_axis_coor:
            machine_code = "".join([machine_code, " B", str(dict_axis_coor.get('b'))])

        if 'c' in dict_axis_coor:
            machine_code = "".join([machine_code, " C", str(dict_axis_coor.get('c'))])

        if 'feed' in dict_axis_coor:
            machine_code = "".join([machine_code, " F", str(dict_axis_coor.get('feed'))])

        self.add_event(gc.EV_TXDATA, "{}\n".format(machine_code))
        self.write("".join([machine_code, "\n"]))

    def close(self):
        if self._serialTxRxThread is not None:
            self._serialTxRxThread.add_event(gc.EV_CMD_EXIT, None)

    @abstractmethod
    def decode(self, data):
        return data

    # list if Actions fucntions "use to be neamed do<Something>

    def doClearAlarm(self):
        """ Clears alarm condition
        """
        self.add_event(gc.EV_TXDATA, "{}\n".format(self.cmdClearAlarm.strip()))
        self.write(self.cmdClearAlarm)
        self.write(self.getStatusCmd())

    def doCycleStartResume(self):
        """ send cycle resume command
        """
        self.add_event(gc.EV_TXDATA, "{}\n".format(self.cmdCycleStart.strip()))
        self.write(self.cmdCycleStart)

    def doFastMove(self, dict_axis_coor):
        """ Fast (rapid) move to a coordinate in obsolete position mode
        """
        if self.machinePositionMode == "G90":
            self._move("G00", dict_axis_coor)
        else:
            self._move("G90 G00", dict_axis_coor)

    def doFastMoveRelative(self, dict_axis_coor):
        """ Fast (rapid) move to a coordinate in relative position mode
        """
        if self.machinePositionMode == "G91":
            self._move("G00", dict_axis_coor)
        else:
            self._move("G91 G00", dict_axis_coor)

    def doFeedHold(self):
        """ send feed hold command
        """
        self.add_event(gc.EV_TXDATA, "%s\n" % self.cmdFeedHold.strip())
        self.write(self.cmdFeedHold)

    def doGetStatus(self):
        if self.okToSend(self.cmdStatus):
            self.add_event(gc.EV_TXDATA, "%s\n" % self.cmdStatus.strip())
            self.write(self.cmdStatus)

    def doGetSystemInfo(self):
        if self.okToSend(self.cmdSystemInfo):
            self.add_event(gc.EV_TXDATA, "%s\n" % self.cmdSystemInfo.strip())
            self.write(self.cmdSystemInfo)

    def doHome(self, dict_axis):
        self._sendAxisCmd(self.cmdHome, dict_axis)

    def doInitComm(self):
        self.write(self.cmdInitComm)

    def doJogFastMove(self, dict_axis_coor):
        self.doFastMove(dict_axis_coor)

    def doJogFastMoveRelative(self, dict_axis_coor):
        self.doFastMoveRelative(dict_axis_coor)

    def doJogMove(self, dict_axis_coor):
        self.doMove(dict_axis_coor)

    def doJogMoveRelative(self, dict_axis_coor):
        self.doMoveRelative(dict_axis_coor)

    def doJogStop(self):
        self.doFeedHold()
        self.doQueueFlush()

    def doMove(self, dict_axis_coor):
        """ Move to a coordinate in opsolute position mode
        """
        if self.machinePositionMode == "G90":
            self._move("G01", dict_axis_coor)
        else:
            self._move("G90 G01", dict_axis_coor)

    def doMoveRelative(self, dict_axis_coor):
        """ Move to a coordinate in relative position mode
        """
        if self.machinePositionMode == "G91":
            self._move("G01", dict_axis_coor)
        else:
            self._move("G91 G01", dict_axis_coor)

    def doProbe(self, dict_axis_coor):
        """ Probe toward work piace, coordinate and feed rate required
            Errors/Alarm if probe fails
        """
        self._sendAxisCmd(self.cmdProbeAxis, dict_axis_coor)

    def doQueueFlush(self):
        self.add_event(gc.EV_TXDATA, "%s\n" % self.cmdQueueFlush.strip())
        self.write(self.cmdQueueFlush)
        self._init()

    def doReset(self):
        self.write(self.cmdReset)
        self._init()

    def doSetAxis(self, dict_axis_coor):
        """ Set axis coordinates
        """
        self._sendAxisCmd(self.cmdSetAxis, dict_axis_coor)

    @abstractmethod
    def encode(self, data, bookeeping=True):
        """ encodes the data for the controller if needed
        """
        # check positioning mode change
        position_mode = self.reMachiePositionMode.match(data)
        if position_mode is not None:
            self.machinePositionMode = position_mode.group(1)

        return data

    @abstractmethod
    def factory(self):
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

    def getSystemInfoCmd(self):
        return self.cmdSystemInfo

    def init(self):
        self.serialName = gc.CONFIG_DATA.get('/machine/Port')
        self.serialBaud = gc.CONFIG_DATA.get('/machine/Baud')

    def isSerialPortOpen(self):
        return self._serialPortOpen

    def okToSend(self, data):

        bufferHasRoom = True

        # split lines
        lines = data.splitlines(True)

        for line in lines:
            data = self.encode(line, bookeeping=False)
            new_size = self._inputBufferSize + len(data)
            if new_size > self._inputBufferWatermark:
                bufferHasRoom = False
                break

        return bufferHasRoom

    def open(self):
        if self.serialName is not None and self.serialBaud is not None:

            # inti serial RX thread
            self._serialTxRxThread = st.SerialPortThread(self,
                                                         self.serialName,
                                                         self.serialBaud)

            if self._serialTxRxThread is not None:
                self._serialTxRxThread.add_event(gc.EV_HELLO, None, self)
                self.doInitComm()

    def read(self):
        """ Read and process data from txrx thread
        """
        dictData = {}

        if self._serialTxRxThread is not None:
            # process events from queue
            try:
                e = self._eventQueue.get_nowait()
            except queue.Empty:
                pass
            else:
                if e.event_id == gc.EV_RXDATA:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                        self.logger.info("EV_RXDATA")

                    if len(e.data) > 0:
                        dictData = self.decode(e.data)
                        dictData['rx_data'] = e.data

                elif e.event_id == gc.EV_TXDATA:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                        self.logger.info("EV_TXDATA")

                    if len(e.data) > 0:
                        dictData['tx_data'] = e.data

                elif e.event_id == gc.EV_HELLO:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                        self.logger.info("EV_HELLO from 0x%x" % id(e.sender))

                    self.add_event_listener(e.sender)

                elif e.event_id == gc.EV_GOOD_BYE:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                        self.logger.info("EV_GOOD_BYE from 0x%x" % id(e.sender))

                    self.remove_event_listener(e.sender)

                elif e.event_id in [gc.EV_EXIT, gc.EV_ABORT, gc.EV_SER_PORT_OPEN,
                                    gc.EV_SER_PORT_CLOSE]:
                    dictData['event'] = {}
                    dictData['event']['id'] = e.event_id
                    dictData['event']['data'] = e.data

                    if e.event_id == gc.EV_SER_PORT_OPEN:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                            self.logger.info("EV_SER_PORT_OPEN")

                        self._serialPortOpen = True

                    elif e.event_id == gc.EV_SER_PORT_CLOSE:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                            self.logger.info("EV_SER_PORT_CLOSE")

                        self._serialPortOpen = False

                    elif e.event_id == gc.EV_ABORT:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                            self.logger.info("EV_ABORT")

                    elif e.event_id == gc.EV_EXIT:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                            self.logger.info("EV_EXIT")
                else:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_MACHIF_MOD_EV:
                        self.logger.error("EV_?? got unknown event!! [%s]" %
                                        str(e.event_id))

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
                self._serialTxRxThread.add_event(gc.EV_CMD_TXDATA, txData)
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
                    self._serialTxRxThread.add_event(gc.EV_CMD_TXDATA, line)

                    bytesSent = bytesSent + len(line)

        return bytesSent
