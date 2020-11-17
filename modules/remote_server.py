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
import errno
import re

try:
    import queue
except ImportError:
    import Queue as queue

try:
    import cPickle as pickle
except:
    import pickle

import modules.config as gc
import modules.machif_progexec as mi_progexec

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
        self.tcpPort = 61801
        self.udpPort = 61802
        self.host = socket.gethostname()
        self.socServer = None
        self.socBroadcast = None
        self.inputs = []
        self.inputsAddr = {}
        self.outputs = []
        self.messageQueues = {}
        self.broadcastQueue = queue.Queue()
        self.machifProgExec = None
        self.serialPortIsOpen = False
        self.deviceDetected = False
        self.useUdpBroadcast = True

        self.rxBuffer = b""
        self.rxBufferLen = 0
        self.allMsgLenRecv = 0

        self.clientEventQueue = gc.EventQueueIf()

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
        except queue.Empty:
            pass
        else:
            # this message came from progexec tread
            if e.sender is self.machifProgExec:

                if e.event_id in [gc.EV_DATA_STATUS, gc.EV_DATA_OUT, gc.EV_DATA_IN]:
                    # these are the most common events from prog exe, process first
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                        self.logger.info("EV_DATA_* {} from 0x{:x} {}".format(e.event_id, id(e.sender), e.sender))

                    e.sender = id(self)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_SER_PORT_OPEN:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                        self.logger.info("EV_SER_PORT_OPEN from 0x{:x} {}".format(id(e.sender), e.sender))

                    self.serialPortIsOpen = True
                    e.sender = id(self)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_SER_PORT_CLOSE:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                        self.logger.info("EV_SER_PORT_CLOSE from 0x{:x} {}".format(id(e.sender), e.sender))

                    self.serialPortIsOpen = False
                    e.sender = id(self)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_CMD_EXIT:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                        self.logger.info("EV_CMD_EXIT from 0x{:x} {}".format(id(e.sender), e.sender))

                    self.machifProgExec = None

                elif e.event_id == gc.EV_ABORT:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                        self.logger.info("EV_ABORT from 0x{:x} {}".format(id(e.sender), e.sender))

                    if self.machifProgExec is not None:
                        self.machifProgExec.eventPut(gc.EV_CMD_EXIT)

                    e.sender = id(self)
                    e.event_id = gc.EV_DATA_IN
                    e.data = "remote machifProgExec {}".format(e.data)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_DEVICE_DETECTED:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                        self.logger.info("EV_DEVICE_DETECTED from 0x{:x} {}".format(id(e.sender), e.sender))

                    self.deviceDetected = True

                    self.run_device_init_script()

                    e.sender = id(self)
                    self.send_broadcast(e)


                else:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                        self.logger.info("EV_[{}] from 0x{:x} {}".format(e.event_id, id(e.sender), e.sender))

                    e.sender = id(self)
                    self.send_broadcast(e)

            # local/non-machine messageing
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
                    self.logger.info("EV_CMD_EXIT from 0x{:x} {}".format(id(e.sender), e.sender))

                if self.machifProgExec is not None:
                    self.machifProgExec.eventPut(gc.EV_CMD_EXIT)

                self.close()

                self.endThread = True

            else:
                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                self.logger.error(
                    "EV_?? got unknown event!! {} from 0x{:x} {}".format(e.event_id, id(e.sender), e.sender))


    def process_client_queue(self):
        # process socket events
        try:
            e = self.clientEventQueue._eventQueue.get_nowait()
        except queue.Empty:
            pass
        else:
            # this message came from clients
            if e.event_id == gc.EV_CMD_TXDATA:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_TXDATA from client{}".format(self.inputsAddr[e.sender]))

            elif e.event_id == gc.EV_CMD_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_OPEN from client{}".format(self.inputsAddr[e.sender]))

                if self.machifProgExec is None:
                    self.machifProgExec = mi_progexec.MachIfExecuteThread(self)

            elif e.event_id == gc.EV_CMD_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_CLOSE from client{}".format(self.inputsAddr[e.sender]))

                if self.machifProgExec is not None:
                    self.machifProgExec.eventPut(gc.EV_CMD_EXIT)

            elif e.event_id == gc.EV_CMD_GET_CONFIG:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_GET_CONFIG from client{}".format(self.inputsAddr[e.sender]))

                port_list = self.get_serial_ports()
                gc.CONFIG_DATA.add('/temp/SerialPorts', port_list)
                self.send(e.sender,  gc.SimpleEvent(gc.EV_RMT_CONFIG_DATA, gc.CONFIG_DATA, id(self.socServer)))

            elif e.event_id == gc.EV_CMD_GET_GCODE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_GET_GCODE from client{}".format(self.inputsAddr[e.sender]))

                #port_list = self.get_serial_ports()
                #gc.CONFIG_DATA.add('/temp/SerialPorts', port_list)
                #self.send(e.sender,  gc.SimpleEvent(gc.EV_RMT_CONFIG_DATA, gc.CONFIG_DATA, id(self.server)))

            elif e.event_id == gc.EV_CMD_UPDATE_CONFIG:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_UPDATE_CONFIG from client{}".format(self.inputsAddr[e.sender]))

                gc.CONFIG_DATA = e.data
                gc.CONFIG_DATA.save()

                if self.machifProgExec is not None:
                    self.machifProgExec.eventPut(gc.EV_CMD_UPDATE_CONFIG)

            else:
                # # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                # self.logger.error(
                #     "EV_?? got unknown event!! {} from client{}".format(e.event_id, self.inputs_addr[e.sender]))

                if self.machifProgExec is not None:
                    e.sender = self
                    self.machifProgExec.eventPut(e)

    def close(self):
        """ Close serial port
        """
        if self.socServer is not None:

            while len(self.inputs):
                soc = self.inputs.pop()
                soc.close()

            self.socServer = None

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info("Close clients and server port")

            self.notifyEventListeners(gc.EV_RMT_PORT_CLOSE)

        if self.socBroadcast is not None:
            self.socBroadcast.close()
            self.socBroadcast = None

    def get_serial_ports(self):
        ser_list = []
        port_search_fail_safe = False

        try:
            import glob
            import serial.tools.list_ports

            ser_list_info = serial.tools.list_ports.comports()

            if len(ser_list_info) > 0:
                if type(ser_list_info[0]) == tuple:
                    ser_list = ["%s, %s, %s" %
                               (i[0], i[1], i[2]) for i in ser_list_info]
                else:
                    ser_list = ["%s, %s" % (i.device, i.description)
                               for i in ser_list_info]

                ser_list.sort()

        except ImportError:
            port_search_fail_safe = True

        if port_search_fail_safe:
            ser_list = []

            if os.name == 'nt':
                # Scan for available ports.
                for i in range(256):
                    try:
                        serial.Serial(i)
                        serList.append('COM'+str(i + 1))
                    except serial.SerialException, e:
                        pass
                    except OSError, e:
                        pass
            else:
                ser_list = glob.glob('/dev/ttyUSB*') + \
                    glob.glob('/dev/ttyACM*') + \
                    glob.glob('/dev/cu*')

            if not len(ser_list):
                ser_list = ['None']

        return ser_list

    def open(self):
        """ Open serial port
        """
        exFlag = False
        exMsg = ""

        self.close()

        try:
            self.socServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Internet, TCP
            #self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Internet, UDP
            self.socServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socServer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # for TCP
            self.socServer.setblocking(0)
            self.socServer.bind(("", self.tcpPort))
            self.socServer.listen(5) # only for TCP
            self.inputs.append(self.socServer)

            if self.useUdpBroadcast:
                self.socBroadcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socBroadcast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socBroadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

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
            msg = "Sever listening on {}{}\n".format(self.host, self.socServer.getsockname())
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info(msg.strip())

            # sending directly to who created us
            self.notifyEventListeners(gc.EV_RMT_PORT_OPEN, msg)

    def recv(self, soc):
        exFlag = False
        exMsg = ""
        data = None

        try:
            if not len(self.rxBuffer):
                msg_header = soc.recv(gc.SOCK_HEADER_SIZE)
                msg_len = 0

                if len(msg_header):
                    msg_len = int(msg_header.decode('utf-8'))
                    self.rxBufferLen = msg_len
                    self.allMsgLenRecv += msg_len

            msg = b""
            if self.rxBufferLen > gc.SOCK_DATA_SIZE:
                msg = soc.recv(gc.SOCK_DATA_SIZE)
            else:
                msg = soc.recv(self.rxBufferLen)

            if len(msg):
                self.rxBufferLen -= len(msg)
                self.rxBuffer += msg

                # got the entire mesage decode
                if self.rxBufferLen <= 0:
                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_HEX:
                        self.logger.info(verbose_data_hex("<-", self.rxBuffer))

                    elif (gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_STR):
                        self.logger.info(verbose_data_ascii("<-", self.rxBuffer))

                    data = pickle.loads(self.rxBuffer)

                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                        self.logger.info(
                            "Recv msg len:{} data:{} from {}".format(len(self.rxBuffer), str(data), soc.getpeername()))

                    # init rxBuffer last
                    self.rxBuffer = b""

        except OSError as e:
            exMsg = "** OSError exception: {}\n".format(str(e))
            exFlag = True

        except IOError as e:
            # This is normal on non blocking connections - when there are no incoming data error is going to be raised
            # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
            # We are going to check for both - if one of them - that's expected, means no incoming data, continue as normal
            # If we got different error code - something happened
            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                exMsg = "** IOError exception: {}\n".format(str(e))
                exFlag = True

        except socket.error as e:
            exMsg = "** socket.error exception: {}\n".format(str(e))
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

        # return data
        return data

    def send(self, soc, data):
        exFlag = False
        exMsg = ""

        pickle_data = pickle.dumps(data)
        msg_len = len(pickle_data)
        msg = "{:{header_size}}".format(msg_len, header_size=gc.SOCK_HEADER_SIZE).encode('utf-8')
        msg += pickle_data

        try:
            soc.send(bytes(msg))

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info(
                    "Send msg len:{} data:{} to {}".format(msg_len, str(data), soc.getpeername()))

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
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(exMsg.strip())

            self.clean_up(soc)

    def send_to(self, data):
        exFlag = False
        exMsg = ""

        pickle_data = pickle.dumps(data)
        msg_len = len(pickle_data)
        msg = "{:{header_size}}".format(msg_len, header_size=gc.SOCK_HEADER_SIZE).encode('utf-8')
        msg += pickle_data

        try:
            self.socBroadcast.sendto(bytes(msg), ('255.255.255.255', self.udpPort))

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info(
                    "Send broadcast msg len:{} data:{}".format(msg_len, str(data)))

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
            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(exMsg.strip())


    def send_broadcast(self, data):
        if self.useUdpBroadcast:
            self.send_to(data)
        else:
            for soc in self.inputs:
                if soc is not self.socServer:
                    self.send(soc, data)

    def clean_up(self, soc):
        if soc in self.outputs:
            self.outputs.remove(soc)

        self.inputs.remove(soc)

        if soc in self.outputs:
            self.outputs.remove(soc)

        del self.inputsAddr[soc]
        del self.messageQueues[soc]
        soc.close()

    def run_device_init_script(self):
        init_script_en = gc.CONFIG_DATA.get('/machine/InitScriptEnable')

        if init_script_en:
            # comments example "( comment string )" or "; comment string"
            re_gcode_comments = [re.compile(r'\(.*\)'), re.compile(r';.*')]

            # run init script
            init_script = str(gc.CONFIG_DATA.get('/machine/InitScript')).splitlines()

            if len(init_script) > 0:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                    self.logger.info("RemoteServerThread queuing machine init script...")

                for init_line in init_script:

                    for re_comments in re_gcode_comments:
                        init_line = re_comments.sub("", init_line)

                    init_line = "".join([init_line, "\n"])

                    if len(init_line.strip()):
                        if self.machifProgExec is not None:
                            self.machifProgExec.eventPut(gc.EV_CMD_SEND, init_line)

                            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                                self.logger.info(init_line.strip())

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
            self.process_client_queue()

            # check if we need to exit now
            if (self.endThread):
                break

            if len(self.inputs):
                if self.swState == gc.STATE_RUN:
                    readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs, 0)

                    for soc in readable:
                        if soc is self.socServer:
                            # register new client
                            connection, client_address = soc.accept()
                            connection.setblocking(0)
                            self.inputs.append(connection)
                            self.inputsAddr[connection] = client_address
                            self.messageQueues[connection] = queue.Queue()

                            msg = "Sever stablish connection to client{}\n".format(self.inputsAddr[connection])
                            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                                self.logger.info(msg.strip())

                            # notify local lisensers
                            self.notifyEventListeners(gc.EV_RMT_HELLO, msg)

                            # send welcome message, only to new client
                            msg = gc.SimpleEvent(gc.EV_RMT_HELLO, "Welcome to gsat server {}, on {}{} {}\n".format(
                                    __version__, self.host, self.socServer.getsockname(),
                                    os.uname()), id(self))

                            self.send(connection, msg)

                            if self.serialPortIsOpen:
                                msg = gc.SimpleEvent(gc.EV_SER_PORT_OPEN, 0, id(self))
                                self.send(connection, msg)
                        else:
                            # read data from client
                            data = self.recv(soc)

                            if data:
                                # add data to self queue to handle
                                data.sender = soc
                                #self.eventPut(data)
                                self.clientEventQueue.eventPut(data)

                            else:
                                if not self.rxBufferLen:
                                    # no data client disconnected, clean up
                                    if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                                        self.logger.info(
                                            "Connection reset by peer, client{}".format(self.inputsAddr[soc]))

                                    self.clean_up(soc)

                    # # Handle outputs
                    # for soc in writable:
                    #     try:
                    #         msg = self.messageQueues[soc].get_nowait()
                    #     except Queue.Empty:
                    #         pass
                    #     else:
                    #         self.send(soc, msg)

                    #     try:
                    #         msg = self.broadcastQueue.get_nowait()
                    #     except Queue.Empty:
                    #         pass
                    #     else:
                    #         self.send(soc, msg)

                    # handle exceptions
                    for soc in exceptional:
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                            self.logger.info("Unknown exception from client{}".format(self.inputsAddr[soc]))

                        self.clean_up(soc)

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
                message = "Remote port is close, terminating.\n"

                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(message.strip())

                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # add data to queue
                self.notifyEventListeners(gc.EV_ABORT, message)
                break

            time.sleep(0.010)

        # exit thread
        self.close()
        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info("thread exit")

        self.notifyEventListeners(gc.EV_EXIT, "")

