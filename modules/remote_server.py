"""----------------------------------------------------------------------------
   remote_server.py

   Copyright (C) 2020-2020 Wilhelm Duembeg

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
import sys
import threading
import time
import logging
import socket
import select
import Queue
import pickle
import platform

import modules.config as gc

from modules.version_info import *


def verbose_data_ascii(direction, data):
    return "[%03d] %s %s" % (len(data), direction, data.strip())


def verbose_data_hex(direction, data):
    return "[%03d] %s ASCII:%s HEX:%s" % (
        len(data),
        direction,
        data.strip(),
        ':'.join(x.encode('hex') for x in data))


class RemoteServerThread(threading.Thread, gc.EventQueueIf):
    """ Threads to send and monitor network socket for new data.
    """

    def __init__(self, event_handler):
        """ Init remote client class
        """
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        # self.remotePort = None
        # self.remoteHost = None
        self.port = 61801
        self.host = "river"
        self.server = None
        self.inputs = []
        self.outputs = []
        self.messageQueues = {}
        self.broadcastQueue = Queue.Queue()

        self.rxBuffer = ""

        self.swState = gc.STATE_RUN

        self.logger = logging.getLogger()

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info("init logging id:0x{:x} {}".format(id(self), self))

        if event_handler is not None:
            self.addEventListener(event_handler)

        # start thread
        self.start()

    def process_queue(self):
        """ Event handlers
        """

        # process events from queue
        try:
            e = self._eventQueue.get_nowait()
        except Queue.Empty:
            pass
        else:
            if e.event_id == gc.EV_CMD_TXDATA:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_TXDATA")

                self.write(e.data)

            elif e.event_id == gc.EV_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_HELLO from 0x{:x} {}".format(id(e.sender), e.sender))

                self.addEventListener(e.sender)

            elif e.event_id == gc.EV_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_GOOD_BYE from 0x{:x} {}".format(id(e.sender), e.sender))

                self.removeEventListener(e.sender)

            elif e.event_id == gc.EV_CMD_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_EXIT")

                self.close()

                self.endThread = True

            else:
                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                self.logger.error(
                    "EV_?? got unknown event!! {} from 0x{:x} {}".format(e.event_id, id(e.sender), e.sender))

    def close(self):
        """ Close serial port
        """
        if self.server is not None:

            while len(self.inputs):
                soc = self.inputs.pop()
                soc.close()

            self.server = None

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info("close clients and server port")

            self.notifyEventListeners(gc.EV_SER_PORT_CLOSE, 0)

    def open(self):
        """ Open serial port
        """
        exFlag = False
        exMsg = ""

        self.close()

        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setblocking(0)
            self.server.bind((self.host, self.port))
            self.server.listen(5)
            self.inputs.append(self.server)

        except socket.error as e:
            exMsg = "** socket.error exception: {}\n".format(str(e))
            exFlag = True

        except OSError as e:
            exMsg = "** OSError exception: {}\n".format(str(e))
            exFlag = True

        except IOError as e:
            exMsg = "** IOError exception: {}\n".format(str(e))
            exFlag = True

        # except:
        #     e = sys.exc_info()[0]
        #     exMsg = "** Unexpected exception: {}\n".format(str(e))
        #     exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.STATE_ABORT

            # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.error(exMsg.strip())

            # sending directly to who created us
            self.notifyEventListeners(gc.EV_ABORT, exMsg)
        else:
            msg = "sever listening on {}:{}".format(self.host, self.port)
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info(msg)

            # sending directly to who created us
            self.notifyEventListeners(gc.EV_RMT_PORT_OPEN, msg)

    def read(self):
        exFlag = False
        exMsg = ""
        serialData = ""

        try:
            self.server.recv(10)

        except IOError as e:
            exMsg = "** IOError exception: {}\n".format(str(e))
            exFlag = True

        except:
            e = sys.exc_info()[0]
            exMsg = "** Unexpected exception: {}\n".format(str(e))
            exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.STATE_ABORT

            # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.error(exMsg.strip())

            # add data to queue
            self.notifyEventListeners(gc.EV_ABORT, exMsg)
            self.close()

        return

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
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:

                            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_HEX:
                                self.logger.info(verbose_data_hex("<-",
                                                 serialData))

                            elif (gc.VERBOSE_MASK &
                                  gc.VERBOSE_MASK_REMOTEIF_STR):
                                self.logger.info(verbose_data_ascii("<-",
                                                 serialData))

                        self.notifyEventListeners(gc.EV_RXDATA,
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

            # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.error(exMsg.strip())

            # add data to queue
            self.notifyEventListeners(gc.EV_ABORT, exMsg)
            self.close()

    def send(self, soc, data):
        exFlag = False
        exMsg = ""

        pickle_data = pickle.dumps(data)
        msg = "{:{header_size}}".format(len(pickle_data), header_size=gc.SOCK_HEADER_SIZE)
        msg += pickle_data

        try:
            soc.send(bytes(msg.encode('utf-8')))

        except socket.error as e:
            exMsg = "** socket.error exception: {}\n".format(str(e))
            exFlag = True

        except OSError as e:
            exMsg = "** OSError exception: {}\n".format(str(e))
            exFlag = True

        except IOError as e:
            exMsg = "** IOError exception: {}\n".format(str(e))
            exFlag = True

        # except:
        #     e = sys.exc_info()[0]
        #     exMsg = "** Unexpected exception: {}\n".format(str(e))
        #     exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            # self.swState = gc.STATE_ABORT

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(exMsg.strip())

            # add data to queue
            # self.notifyEventListeners(gc.EV_ABORT, exMsg)
            # self.close()


    def write(self, serialData):
        exFlag = False
        exMsg = ""

        if len(serialData) == 0:
            return

        if self.serialPort.isOpen():

            try:
                # send command
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_HEX:
                        self.logger.info(verbose_data_hex("->", serialData))

                    elif (gc.VERBOSE_MASK &
                          gc.VERBOSE_MASK_REMOTEIF_STR):
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
            #     exMsg = "** Unexpected exception: %s\n" % str(e)
            #     exFlag = True

            if exFlag:
                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(exMsg.strip())

                # add data to queue
                self.notifyEventListeners(gc.EV_ABORT, exMsg)
                self.close()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread.
        self.endThread = False

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info("thread start")

        self.open()

        while (not self.endThread) and self.inputs:

            # process input queue for new commands or actions
            self.process_queue()

            # check if we need to exit now
            if (self.endThread):
                break

            if len(self.inputs):
                if self.swState == gc.STATE_RUN:
                    readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs, 0.1)

                    for soc in readable:
                        if soc is self.server:
                            connection, client_address = soc.accept()
                            connection.setblocking(0)
                            self.inputs.append(connection)
                            self.messageQueues[connection] = Queue.Queue()

                            msg = "sever got connection from {}".format(connection.getpeername())
                            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                                self.logger.info(msg)

                            # notify local lisensers
                            self.notifyEventListeners(gc.EV_RMT_HELLO, msg)

                            # welcome message
                            self.messageQueues[connection].put(gc.SimpleEvent(
                                gc.EV_RMT_HELLO,
                                "Welcome to gsat server {}, on {}:{} [{}]".format(
                                    __version__, self.host, self.port, platform.processor()),
                                id(self)))

                            if connection not in self.outputs:
                                self.outputs.append(connection)
                        else:
                            data = soc.recv(1024)
                            if data:
                                # message_queues[s].put(data)
                                if soc not in self.outputs:
                                    self.outputs.append(soc)
                            else:
                                if soc in self.outputs:
                                    self.outputs.remove(soc)
                                self.inputs.remove(soc)
                                soc.close()
                                # del message_queues[s]

                    # Handle outputs
                    for soc in writable:
                        try:
                            msg = self.messageQueues[soc].get_nowait()
                        except Queue.Empty:
                            pass
                        else:
                            self.send(soc, msg)

                        try:
                            msg = self.broadcastQueue.get_nowait()
                        except Queue.Empty:
                            pass
                        else:
                            print >>sys.stderr, 'sending "%s" to %s' % (msg, soc.getpeername())
                            soc.send(msg)

                elif self.swState == gc.STATE_ABORT:
                    # do nothing, wait to be terminated
                    pass
                else:
                    exMsg = "unexpected state [%d], Aborting..." \
                            % (self.swState)

                    # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                    self.logger.error(exMsg.strip())

                    self.notifyEventListeners(gc.EV_ABORT, exMsg)
                    break
            else:
                message = "remote port is close, terminating.\n"

                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(message.strip())

                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # add data to queue
                self.notifyEventListeners(gc.EV_ABORT, message)
                break

        # exit thread
        self.close()
        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info("thread exit")

        self.notifyEventListeners(gc.EV_EXIT, "")
