"""----------------------------------------------------------------------------
   serial_trhead.py

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
import serial
import tty
import threading
import time
import logging

import modules.config as gc


def verbose_data_ascii(direction, data):
    return "[%03d] %s %s" % (len(data), direction, data.strip())


def verbose_data_hex(direction, data):
    return "[%03d] %s ASCII:%s HEX:%s" % (
        len(data),
        direction,
        data.strip(),
        ':'.join(x.encode('hex') for x in data)
    )


class SerialPortThread(threading.Thread, gc.EventQueueIf):
    """ Threads to send and monitor serial port for new data.
    """

    def __init__(self, event_handler, port_name, port_baud):
        """ Init serial class
        """
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        self.serialPort = None
        self.serialPortName = port_name
        self.serialPortBaud = port_baud

        self.rxBuffer = ""

        self.swState = gc.STATE_RUN

        self.logger = logging.getLogger()

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
            self.logger.info("init logging id:0x%x" % id(self))

        if event_handler is not None:
            self.addEventListener(event_handler)

        # start thread
        self.start()

    def processQueue(self):
        """ Event handlers
        """
        # process events from queue
        if not self._eventQueue.empty():
            # get item from queue
            e = self._eventQueue.get()

            if e.event_id == gc.EV_CMD_SER_TXDATA:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF_EV:
                    self.logger.info("EV_CMD_SER_TXDATA")

                self.serialWrite(e.data)

            elif e.event_id == gc.EV_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF_EV:
                    self.logger.info("EV_HELLO from 0x%x" % id(e.sender))

                self.addEventListener(e.sender)

            elif e.event_id == gc.EV_GOODBY:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF_EV:
                    self.logger.info("EV_GOODBY from 0x%x" % id(e.sender))

                self.removeEventListener(e.sender)

            elif e.event_id == gc.EV_CMD_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF_EV:
                    self.logger.info("EV_CMD_EXIT")

                self.serialClose()

                self.endThread = True

            else:
                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF_EV:
                self.logger.error("EV_?? got unknown event!! [%s]" %
                                  str(e.event_id))

    def serialClose(self):
        """ Close serial port
        """
        if self.serialPort is not None:
            if self.serialPort.isOpen():
                # self.serialPort.flushInput()
                self.serialPort.close()

                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
                    self.logger.info("close serial port")

                self.notifyEventListeners(gc.EV_SER_PORT_CLOSE, 0)

    def serialOpen(self):
        """ Open serial port
        """
        exFlag = False
        exMsg = ""

        self.serialClose()

        port = self.serialPortName
        baud = self.serialPortBaud

        if port != "None":
            portName = port
            if os.name == 'nt':
                portName = r"\\.\%s" % (str(port))

            try:
                self.serialPort = serial.Serial(port=portName,
                                                baudrate=baud,
                                                timeout=0.001,
                                                bytesize=serial.EIGHTBITS,
                                                parity=serial.PARITY_NONE,
                                                stopbits=serial.STOPBITS_ONE,
                                                xonxoff=False,
                                                rtscts=False,
                                                dsrdtr=False)

            except serial.SerialException, e:
                exMsg = "** PySerial exception: %s\n" % str(e)
                exFlag = True

            except OSError, e:
                exMsg = "** OSError exception: %s\n" % str(e)
                exFlag = True

            except IOError, e:
                exMsg = "** IOError exception: %s\n" % str(e)
                exFlag = True

            # except:
            #     e = sys.exc_info()[0]
            #     exMsg = "** Unexpected exception: %s\n" % str(e)
            #     exFlag = True

            if self.serialPort is not None:
                if self.serialPort.isOpen():
                    # change tty mode, this is strange and not doing it
                    # was causing issues reconnecting to GRBL if disconnected
                    # because exception, it was fine other wise.
                    # These two lines makes it so opening port again will
                    # connect successfully even after exception close
                    serial_fd = self.serialPort.fileno()
                    tty.setraw(serial_fd)

                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
                        msg = "open serial port [%s] at "\
                            "%s bps" % (portName, baud)
                        self.logger.info(msg)

                    # no exceptions report serial port open

                    # sending directly to who created us
                    self.notifyEventListeners(gc.EV_SER_PORT_OPEN, port)

        else:
            exMsg = "There is no valid serial port detected {%s}." % str(port)
            exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.STATE_ABORT

            # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
            self.logger.error(exMsg.strip())

            # sending directly to who created us
            self.notifyEventListeners(gc.EV_ABORT, exMsg)

    def serialRead(self):
        exFlag = False
        exMsg = ""
        serialData = ""

        try:
            inDataCnt = self.serialPort.inWaiting()

            while inDataCnt > 0 and not exFlag:

                # # read data from port
                # # Was running with performance issues using readline(), move
                # # to read() using "".join() as performance is much better
                # # then "+="
                # serialData = self.serialPort.readline()
                # self.rxBuffer += self.serialPort.read(inDataCnt)
                self.rxBuffer = "".join(
                    [self.rxBuffer, self.serialPort.read(inDataCnt)])

                while '\n' in self.rxBuffer:
                    serialData, self.rxBuffer = self.rxBuffer.split('\n', 1)

                    if serialData:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:

                            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF_HEX:
                                self.logger.info(verbose_data_hex("<-",
                                                 serialData))

                            elif (gc.VERBOSE_MASK &
                                  gc.VERBOSE_MASK_SERIALIF_STR):
                                self.logger.info(verbose_data_ascii("<-",
                                                 serialData))

                        self.notifyEventListeners(gc.EV_SER_RXDATA,
                                                  "%s\n" % serialData)

                        # attempt to reduce starvation on other threads
                        # when serial traffic is constant
                        time.sleep(0.01)

                inDataCnt = self.serialPort.inWaiting()

        except serial.SerialException, e:
            exMsg = "** PySerial exception: %s\n" % e.message
            exFlag = True

        except OSError, e:
            exMsg = "** OSError exception: %s\n" % str(e)
            exFlag = True

        except IOError, e:
            exMsg = "** IOError exception: %s\n" % str(e)
            exFlag = True

        # except:
        #     e = sys.exc_info()[0]
        #     exMsg = "** Unexpected exception: %s\n" % str(e)
        #     exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.STATE_ABORT

            # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
            self.logger.error(exMsg.strip())

            # add data to queue
            self.notifyEventListeners(gc.EV_ABORT, exMsg)
            self.serialClose()

    def serialWrite(self, serialData):
        exFlag = False
        exMsg = ""

        if len(serialData) == 0:
            return

        if self.serialPort.isOpen():

            try:
                # send command
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF_HEX:
                        self.logger.info(verbose_data_hex("->", serialData))

                    elif (gc.VERBOSE_MASK &
                          gc.VERBOSE_MASK_SERIALIF_STR):
                        self.logger.info(verbose_data_ascii("->", serialData))

                self.serialPort.write(serialData)

            except serial.SerialException, e:
                exMsg = "** PySerial exception: %s\n" % e.message
                exFlag = True

            except OSError, e:
                exMsg = "** OSError exception: %s\n" % str(e)
                exFlag = True

            except IOError, e:
                exMsg = "** IOError exception: %s\n" % str(e)
                exFlag = True

            # except:
            #     e = sys.exc_info()[0]
            #     exMsg = "** Unexpected excetion: %s\n" % str(e)
            #     exFlag = True

            if exFlag:
                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
                self.logger.error(exMsg.strip())

                # add data to queue
                self.notifyEventListeners(gc.EV_ABORT, exMsg)
                self.serialClose()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread.
        self.endThread = False

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
            self.logger.info("thread start")

        self.serialOpen()

        while (not self.endThread) and (self.serialPort is not None):

            # process input queue for new commands or actions
            self.processQueue()

            # check if we need to exit now
            if (self.endThread):
                break

            if self.serialPort.isOpen():
                if self.swState == gc.STATE_RUN:
                    self.serialRead()
                elif self.swState == gc.STATE_ABORT:
                    # do nothing, wait to be terminated
                    pass
                else:
                    exMsg = "unexpected state [%d], Aborting..." \
                            % (self.swState)

                    # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
                    self.logger.error(exMsg.strip())

                    self.notifyEventListeners(gc.EV_ABORT, exMsg)
                    break
            else:
                message = "serial port is close, terminating.\n"

                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
                self.logger.error(message.strip())

                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # add data to queue
                self.notifyEventListeners(gc.EV_ABORT, message)
                # wx.LogMessage(message)
                break

            time.sleep(0.01)

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_SERIALIF:
            self.logger.info("thread exit")

        self.notifyEventListeners(gc.EV_EXIT, "")
