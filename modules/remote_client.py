"""----------------------------------------------------------------------------
   remote_client.py

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
from os import tcsetpgrp
import sys
import threading
import time
import logging
import socket
import select

try:
    import queue
except ImportError:
    import Queue as queue

try:
    import cPickle as pickle
except:
    import pickle

import modules.config as gc

def verbose_data_ascii(direction, data):
    return "[%03d] %s %s" % (len(data), direction, data.strip())


def verbose_data_hex(direction, data):
    return "[%03d] %s ASCII:%s HEX:%s" % (
        len(data),
        direction,
        data.strip(),
        ':'.join(x.encode('hex') for x in data))


class RemoteClientThread(threading.Thread, gc.EventQueueIf):
    """ Threads to send and monitor network socket for new data.
    """

    def __init__(self, event_handler, host=None, tcp_port=None, udp_port=None):
        """ Init remote client class
        """
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        if host:
            self.host = host
        else:
            self.host = gc.CONFIG_DATA.get('/remote/Host', "")

        if host:
            self.tcpPort = tcp_port
        else:
            self.tcpPort = gc.CONFIG_DATA.get('/remote/TcpPort', 61801)

        if host:
            self.udpPort = udp_port
        else:
            self.udpPort = gc.CONFIG_DATA.get('/remote/UdpPort', 61802)

        # self.host = "river"
        self.socClient = None
        self.socBroadcast = None
        self.inputs = []
        self.inputsAddr = {}
        self.outputs = []
        self.messageQueues = {}
        self.useUdpBroadcast = gc.CONFIG_DATA.get('/remote/udpBroadcast', True)

        self.rxBuffer = b""
        self.rxBufferLen = 0
        self.allMsgLenRecv = 0

        self.swState = gc.STATE_RUN

        self.logger = logging.getLogger()

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info("init logging id:0x{:x} {}".format(id(self), self))

        if event_handler is not None:
            self.add_event_listener(event_handler)

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
            if e.event_id == gc.EV_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_HELLO from 0x{:x} {}".format(id(e.sender), e.sender))

                self.add_event_listener(e.sender)

            elif e.event_id == gc.EV_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_GOOD_BYE from 0x{:x} {}".format(id(e.sender), e.sender))

                self.remove_event_listener(e.sender)

            elif e.event_id == gc.EV_CMD_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                    self.logger.info("EV_CMD_EXIT")

                self.close()

                self.endThread = True

            else:
                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_EV:
                # self.logger.error("EV_?? got unknown event!! from 0x{:x} {}".format(id(e.sender), e.sender))

                # commands that we don't handle forward to server
                e.sender = id(e.sender)
                self.send(self.socClient, e)

    def get_hostname(self):
        """ Get server hot info
        """
        hostname = ""

        if self.socClient is not None:
            hostname = "{}{}".format(self.host, self.inputsAddr[self.socClient])

        return hostname

    def close(self):
        """ Close serial port
        """
        if self.socClient is not None:

            msg = "Close remote connection to {}{}\n".format(self.host, self.inputsAddr[self.socClient])

            while len(self.inputs):
                soc = self.inputs.pop()
                soc.close()

            self.socClient = None

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info(msg.strip())

            self.notify_event_listeners(gc.EV_RMT_PORT_CLOSE, msg)

        if self.socBroadcast is not None:
            self.socBroadcast.close()
            self.socBroadcast = None

    def open(self):
        """ Open serial port
        """
        exFlag = False
        exMsg = ""

        self.close()

        try:
            self.socClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Internet, TCP
            #self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Internet, UDP
            self.socClient.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # for TCP
            self.socClient.connect((self.host, self.tcpPort))
            self.inputs.append(self.socClient)
            self.inputsAddr[self.socClient] = self.socClient.getpeername()

            if self.useUdpBroadcast:
                self.socBroadcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) # UDP
                self.socBroadcast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                self.socBroadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                self.socBroadcast.bind(("", self.udpPort))

        except socket.error as e:
            exMsg = "** socket.error exception: socket:{}:{} err:{}\n".format(self.host, self.tcpPort, str(e))
            exFlag = True

        except OSError as e:
            exMsg = "** OSError exception: socket:{}:{} err:{}\n".format(self.host, self.tcpPort, str(e))
            exFlag = True

        except IOError as e:
            exMsg = "** IOError exception: socket:{}:{} err:{}\n".format(self.host, self.tcpPort, str(e))
            exFlag = True

        # except:
        #     e = sys.exc_info()[0]
        #     exMsg = "** Unexpected exception: socket:{}:{} err:{}\n".format(self.host, self.port, str(e))
        #     exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.STATE_ABORT
            self.socClient.close()
            self.socClient = None

            # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.error(exMsg.strip())

            # sending directly to who created us
            self.notify_event_listeners(gc.EV_ABORT, exMsg)
        else:
            msg = "Open remote connection to {}{}\n".format(self.host, self.inputsAddr[self.socClient])

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.info(msg.strip())

            # sending directly to who created us
            self.notify_event_listeners(gc.EV_RMT_PORT_OPEN, msg)

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

    def recv_from(self):
        exFlag = False
        exMsg = ""
        data = None

        try:
            data, from_data = self.socBroadcast.recvfrom(gc.SOCK_DATA_SIZE)
            msg_header = data[:gc.SOCK_HEADER_SIZE]

            if len(msg_header):
                msg_len = int(msg_header.decode('utf-8'))
                self.allMsgLenRecv += msg_len

            msg = data[gc.SOCK_HEADER_SIZE:]

            if len(msg):
                # got the entire mesage decode
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_HEX:
                    self.logger.info(verbose_data_hex("<-", msg))

                elif (gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF_STR):
                    self.logger.info(verbose_data_ascii("<-", msg))

                data = pickle.loads(msg)

                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                    self.logger.info(
                        "Recv msg len:{} data:{} from {}".format(len(msg), str(data), from_data))

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
        data_len = len(msg)
        data_sent_len = 0

        while (not exFlag and data_sent_len<data_len):

            try:
                data_sent_len += soc.send(bytes(msg[data_sent_len:]))

            except OSError as e:
                exMsg = "** OSError exception: {}\n".format(str(e))
                exFlag = True

            except IOError as e:
                # This is normal on non blocking connections - when there are no incoming data error is going to be
                # raised. Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
                # We are going to check for both - if one of them - that's expected, means no incoming data, continue
                # as normal. If we got different error code - something happened
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

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info(
                "Send msg len:{} data:{} to {}".format(msg_len, str(data), soc.getpeername()))

        if exFlag:
            # make sure we stop processing any states...
            # self.swState = gc.STATE_ABORT

            if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(exMsg.strip())

            # add data to queue
            # self.notifyEventListeners(gc.EV_ABORT, exMsg)
            # self.close()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread.
        self.endThread = False

        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info("thread start")

        self.open()

        while (not self.endThread): # and (self.serialPort is not None):

            # process input queue for new commands or actions
            self.process_queue()

            # check if we need to exit now
            if (self.endThread):
                break

            if len(self.inputs):
                if self.swState == gc.STATE_RUN:
                    readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs, 0)

                    for soc in readable:
                        data = self.recv(soc)
                        if data:
                            data.sender = self
                            self.notify_event_listeners(data)
                        else:
                            if not self.rxBufferLen:
                                msg = "Connection reset by peer, server {}{}\n".format(
                                    self.host, self.socClient.getpeername())

                                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                                    self.logger.info(msg.strip())

                                self.swState = gc.STATE_ABORT

                                self.notify_event_listeners(gc.EV_ABORT, msg)

                    if len(exceptional):
                        pass

                    if self.useUdpBroadcast:
                        udp_readable, udp_writable, udp_exceptional = select.select([self.socBroadcast], self.outputs, self.inputs, 0)

                        if len(udp_readable):
                            data = self.recv_from()
                            if data:
                                data.sender = self
                                self.notify_event_listeners(data)

                    # # Handle outputs
                    # for soc in writable:
                    #     try:
                    #         msg = self.messageQueues[soc].get_nowait()
                    #     except Queue.Empty:
                    #         pass
                    #     else:
                    #         print >>sys.stderr, 'sending "%s" to %s' % (msg, soc.getpeername())
                    #         self.send(msg)

                    # handle exceptions
                    for soc in exceptional:
                        msg = "Unknown exception from client{}\n".format(self.inputsAddr[soc])
                        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                            self.logger.info(msg.strip())

                        self.swState = gc.STATE_ABORT

                        self.notify_event_listeners(gc.EV_ABORT, msg)

                elif self.swState == gc.STATE_ABORT:
                    # do nothing, wait to be terminated
                    pass
                else:
                    exMsg = "Unexpected state [%d], Aborting..." \
                            % (self.swState)

                    # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                    self.logger.error(exMsg.strip())

                    self.notify_event_listeners(gc.EV_ABORT, exMsg)
                    break
            else:
                message = "Remote port is close, terminating.\n"

                # if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
                self.logger.error(message.strip())

                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # add data to queue
                self.notify_event_listeners(gc.EV_ABORT, message)
                break

        # exit thread
        self.close()
        if gc.VERBOSE_MASK & gc.VERBOSE_MASK_REMOTEIF:
            self.logger.info("thread exit")

        self.notify_event_listeners(gc.EV_EXIT, "")

