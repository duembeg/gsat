"""----------------------------------------------------------------------------
    remote_server.py

    Copyright (C) 2020 Wilhelm Duembeg

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
import queue
import pickle

import modules.config as gc
import modules.machif_progexec as mi_progexec

import modules.version_info as vinfo


class RemoteServerThread(threading.Thread, gc.EventQueueIf):
    """
    Threads to send and monitor network socket for new data.

    """

    def __init__(self, event_handler):
        """
        Init remote client class

        """
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        self.tcpPort = gc.CONFIG_DATA.get('/remote/TcpPort', 61801)
        self.udpPort = gc.CONFIG_DATA.get('/remote/UdpPort', 61802)
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
        self.useUdpBroadcast = gc.CONFIG_DATA.get('/remote/UdpBroadcast', False)

        self.rxBuffer = b""
        self.rxBufferLen = 0
        self.allMsgLenRecv = 0

        self.clientEventQueue = gc.EventQueueIf()

        self.swState = gc.STATE_RUN

        self.logger = logging.getLogger()

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            self.logger.info("init logging id:0x{:x} {}".format(id(self), self))

        if event_handler is not None:
            self.add_event_listener(event_handler)

        # start thread
        self.start()

    def process_queue(self):
        """
        Event handlers

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
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                        self.logger.info(f"EV_DATA_* {e.event_id} from 0x{id(e.sender):x} {e.sender}")

                    e.sender = id(self)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_SER_PORT_OPEN:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                        self.logger.info(f"EV_SER_PORT_OPEN from 0x{id(e.sender):x} {e.sender}")

                    self.serialPortIsOpen = True
                    e.sender = id(self)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_SER_PORT_CLOSE:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                        self.logger.info("EV_SER_PORT_CLOSE from 0x{:x} {}".format(id(e.sender), e.sender))

                    self.serialPortIsOpen = False
                    e.sender = id(self)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_CMD_EXIT:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                        self.logger.info("EV_CMD_EXIT from 0x{:x} {}".format(id(e.sender), e.sender))

                    self.machifProgExec = None

                elif e.event_id == gc.EV_ABORT:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                        self.logger.info("EV_ABORT from 0x{:x} {}".format(id(e.sender), e.sender))

                    if self.machifProgExec is not None:
                        self.machifProgExec.add_event(gc.EV_CMD_EXIT)

                    e.sender = id(self)
                    e.event_id = gc.EV_DATA_IN
                    e.data = "remote machifProgExec {}".format(e.data)
                    self.send_broadcast(e)

                elif e.event_id == gc.EV_DEVICE_DETECTED:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                        self.logger.info("EV_DEVICE_DETECTED from 0x{:x} {}".format(id(e.sender), e.sender))

                    self.deviceDetected = True

                    # This will be done by progexec thread where it belongs
                    # self.run_device_init_script()

                    e.sender = id(self)
                    self.send_broadcast(e)

                else:
                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                        self.logger.info("EV_[{}] from 0x{:x} {}".format(e.event_id, id(e.sender), e.sender))

                    e.sender = id(self)
                    self.send_broadcast(e)

            # local/non-machine messaging
            elif e.event_id == gc.EV_HELLO:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_HELLO from 0x{:x} {}".format(id(e.sender), e.sender))

                self.add_event_listener(e.sender)

            elif e.event_id == gc.EV_GOOD_BYE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_GOOD_BYE from 0x{:x} {}".format(id(e.sender), e.sender))

                self.remove_event_listener(e.sender)

            elif e.event_id == gc.EV_CMD_EXIT:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_EXIT from 0x{:x} {}".format(id(e.sender), e.sender))

                if self.machifProgExec is not None:
                    self.machifProgExec.add_event(gc.EV_CMD_EXIT)

                self.close()

                self.endThread = True

            else:
                self.logger.error(
                    "EV_?? got unknown event!! {} from 0x{:x} {}".format(e.event_id, id(e.sender), e.sender))

    def process_client_queue(self):
        """
        Process socket events

        """
        try:
            e = self.clientEventQueue._eventQueue.get_nowait()
        except queue.Empty:
            pass
        else:
            # this message came from clients
            if e.event_id == gc.EV_CMD_TXDATA:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_TXDATA from client{}".format(self.inputsAddr[e.sender]))

            elif e.event_id == gc.EV_CMD_OPEN:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_OPEN from client{}".format(self.inputsAddr[e.sender]))

                if self.machifProgExec is None:
                    self.machifProgExec = mi_progexec.MachIfExecuteThread(self)

            elif e.event_id == gc.EV_CMD_CLOSE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_CLOSE from client{}".format(self.inputsAddr[e.sender]))

                if self.machifProgExec is not None:
                    self.machifProgExec.add_event(gc.EV_CMD_EXIT)

            elif e.event_id == gc.EV_CMD_GET_CONFIG:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_GET_CONFIG from client{}".format(self.inputsAddr[e.sender]))

                port_list = self.get_serial_ports()
                gc.CONFIG_DATA.add('/temp/SerialPorts', port_list)
                gc.CONFIG_DATA.add('/temp/RemoteServer', True)
                self.send(e.sender,  gc.SimpleEvent(gc.EV_RMT_CONFIG_DATA, gc.CONFIG_DATA, id(self.socServer)))

            elif e.event_id == gc.EV_CMD_GET_GCODE:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_GET_GCODE from client{}".format(self.inputsAddr[e.sender]))

                if self.machifProgExec is not None:
                    gcode_dict = self.machifProgExec.get_gcode_dict()
                    self.send(e.sender, gc.SimpleEvent(gc.EV_GCODE, gcode_dict, id(self.socServer)))

            elif e.event_id == gc.EV_CMD_GET_BRK_PT:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_GET_BRK_PT from client{}".format(self.inputsAddr[e.sender]))

                if self.machifProgExec is not None:
                    gcode_dict = self.machifProgExec.get_gcode_dict()
                    self.send(e.sender, gc.SimpleEvent(gc.EV_BRK_PT, gcode_dict['breakPoints'], id(self.socServer)))

            elif e.event_id == gc.EV_CMD_UPDATE_CONFIG:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_UPDATE_CONFIG from client{}".format(self.inputsAddr[e.sender]))

                machine_device = gc.CONFIG_DATA.get('/machine/Device')
                machine_port = gc.CONFIG_DATA.get('/machine/Port')
                machine_baud = gc.CONFIG_DATA.get('/machine/Baud')

                tcp_port = gc.CONFIG_DATA.get('/remote/TcpPort')
                udp_port = gc.CONFIG_DATA.get('/remote/UdpPort')
                udp_broadcast = gc.CONFIG_DATA.get('/remote/UdpBroadcast')

                if e.data is not None:
                    gc.CONFIG_DATA = e.data
                    gc.CONFIG_DATA.save()

                if self.machifProgExec is not None:
                    self.machifProgExec.add_event(gc.EV_CMD_UPDATE_CONFIG)

                    # close serial port if settings changed
                    if (machine_device != gc.CONFIG_DATA.get('/machine/Device') or
                       machine_port != gc.CONFIG_DATA.get('/machine/Port') or
                       machine_baud != gc.CONFIG_DATA.get('/machine/Baud')):
                        self.machifProgExec.add_event(gc.EV_CMD_EXIT)

                # re start server if settings changed
                if (tcp_port != gc.CONFIG_DATA.get('/remote/TcpPort') or
                   udp_port != gc.CONFIG_DATA.get('/remote/UdpPort') or
                   udp_broadcast != gc.CONFIG_DATA.get('/remote/UdpBroadcast')):

                    self.tcpPort = gc.CONFIG_DATA.get('/remote/TcpPort')
                    self.udpPort = gc.CONFIG_DATA.get('/remote/UdpPort')
                    self.udpBroadcast = gc.CONFIG_DATA.get('/remote/UdpBroadcast')

                    msg = gc.SimpleEvent(gc.EV_RMT_GOOD_BYE, "** Server settings changing, restart...\n")
                    self.send_broadcast(msg)
                    self.close()
                    self.open()

            elif e.event_id == gc.EV_CMD_RMT_RESET:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_CMD_RMT_RESET from client{}".format(self.inputsAddr[e.sender]))

                os.system('sudo reboot')

            elif e.event_id == gc.EV_RMT_PING:
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                    self.logger.info("EV_RMT_PING from client{}".format(self.inputsAddr[e.sender]))

                self.send(e.sender, gc.SimpleEvent(gc.EV_RMT_PONG, 0, id(self.socServer)))

            else:
                # # if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                # self.logger.error(
                #     "EV_?? got unknown event!! {} from client{}".format(e.event_id, self.inputs_addr[e.sender]))

                if self.machifProgExec is not None:
                    e.sender = self
                    self.machifProgExec.add_event(e)

    def close(self):
        """
        Close serial port

        """
        if self.socServer is not None:

            while len(self.inputs):
                soc = self.inputs.pop()
                soc.close()

            self.socServer = None

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                self.logger.info("Close clients and server port")

            self.notify_event_listeners(gc.EV_RMT_PORT_CLOSE)

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
                ser_list = [f"{i.device}, {i.description}" for i in ser_list_info]

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
                        ser_list.append('COM'+str(i + 1))
                    except serial.SerialException as e:
                        pass
                    except OSError as e:
                        pass
            else:
                ser_list = glob.glob('/dev/ttyUSB*') + \
                    glob.glob('/dev/ttyACM*') + \
                    glob.glob('/dev/cu*')

            if not len(ser_list):
                ser_list = ['None']

        return ser_list

    def open(self):
        """
        Open serial port

        """
        exFlag = False
        exMsg = ""

        self.close()

        try:
            self.socServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Internet, TCP
            # self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Internet, UDP
            self.socServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socServer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # for TCP
            self.socServer.setblocking(0)
            self.socServer.bind(("", self.tcpPort))
            self.socServer.listen(5)  # only for TCP
            self.inputs.append(self.socServer)

            if self.useUdpBroadcast:
                self.socBroadcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socBroadcast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socBroadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        except socket.error as e:
            exMsg = "** socket.error exception: {}\n".format(str(e))
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

            self.logger.error(exMsg.strip())

            # sending directly to who created us
            self.notify_event_listeners(gc.EV_ABORT, exMsg)
        else:
            msg = "Server listening on {}{}\n".format(self.host, self.socServer.getsockname())
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
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

                # got the entire message decode
                if self.rxBufferLen <= 0:
                    data = pickle.loads(self.rxBuffer)

                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                        log_msg =  "Recv msg id:{} obj:0x{:x} len:{} from {} ".format(
                            data.event_id, id(data), len(self.rxBuffer), self.inputsAddr[soc])

                        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_HEXDUMP):
                            log_msg = log_msg + gc.verbose_hexdump("", self.rxBuffer)

                        elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_HEX):
                            log_msg = log_msg + gc.verbose_data_hex("", self.rxBuffer)

                        elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_STR):
                            log_msg = log_msg + gc.verbose_data_ascii("", self.rxBuffer)

                        self.logger.info(log_msg)

                    # init rxBuffer last
                    self.rxBuffer = b""

        except OSError as e:
            # This is normal on non blocking connections - when there are no incoming data error is going to be raised
            # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
            # We are going to check for both - if one of them - that's expected, means no incoming data, continue as
            # normal. If we got different error code - something happened
            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                exMsg = "** OSError exception: {}\n".format(str(e))
                exFlag = True

        except IOError as e:
            # This is normal on non blocking connections - when there are no incoming data error is going to be raised
            # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
            # We are going to check for both - if one of them - that's expected, means no incoming data, continue as
            # normal. If we got different error code - something happened
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

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                self.logger.error(exMsg.strip())

            # add data to queue
            # self.notifyEventListeners(gc.EV_ABORT, exMsg)
            # self.close()

        # return data
        return data

    def send(self, soc, data):
        exFlag = False
        exMsg = ""

        pickle_data = pickle.dumps(data, protocol=5)
        msg_len = len(pickle_data)
        msg = "{:{header_size}}".format(msg_len, header_size=gc.SOCK_HEADER_SIZE).encode('utf-8')
        msg += pickle_data
        data_len = len(msg)
        data_sent_len = 0

        while (not exFlag and data_sent_len < data_len):
            try:
                data_sent_len += soc.send(bytes(msg[data_sent_len:]))

            except OSError as e:
                # This is normal on non blocking connections - when there are no incoming data error is going to be
                # raised. Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
                # We are going to check for both - if one of them - that's expected, means no incoming data, continue
                # as normal. If we got different error code - something happened
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
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

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            log_msg = "Send msg id:{} obj:0x{:x} len:{} to {} ".format(
                data.event_id, id(data), msg_len, self.inputsAddr[soc])

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_HEXDUMP):
                log_msg = log_msg + gc.verbose_hexdump("->", pickle_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_HEX):
                log_msg = log_msg + gc.verbose_data_hex("->", pickle_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_STR):
                log_msg = log_msg + gc.verbose_data_ascii("->", pickle_data)

            self.logger.info(log_msg)

        if exFlag:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                self.logger.error(exMsg.strip())

            self.clean_up(soc)

    def send_to(self, data):
        exFlag = False
        exMsg = ""

        pickle_data = pickle.dumps(data, protocol=5)
        msg_len = len(pickle_data)
        msg = "{:{header_size}}".format(msg_len, header_size=gc.SOCK_HEADER_SIZE).encode('utf-8')
        msg += pickle_data

        try:
            self.socBroadcast.sendto(bytes(msg), ('255.255.255.255', self.udpPort))

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                log_msg = "Send broadcast msg id:{} obj:0x{:x} len:{} ".format(data.event_id, id(data), msg_len)

                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_HEXDUMP):
                    log_msg = log_msg + gc.verbose_hexdump("->", pickle_data)

                elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_HEX):
                    log_msg = log_msg + gc.verbose_data_hex("->", pickle_data)

                elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_STR):
                    log_msg = log_msg + gc.verbose_data_ascii("->", pickle_data)

                self.logger.info(log_msg)

        except OSError as e:
            exMsg = "** OSError exception: {}\n".format(str(e))
            exFlag = True

        except IOError as e:
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
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
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
                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                    self.logger.info("RemoteServerThread queuing machine init script...")

                for init_line in init_script:

                    for re_comments in re_gcode_comments:
                        init_line = re_comments.sub("", init_line)

                    init_line = "".join([init_line, "\n"])

                    if len(init_line.strip()):
                        if self.machifProgExec is not None:
                            self.machifProgExec.add_event(gc.EV_CMD_SEND, init_line)

                            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                                self.logger.info(init_line.strip())

    def run(self):
        """
        Run Worker Thread.

        """
        # This is the code executing in the new thread.
        self.endThread = False

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
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

                            msg = "Server stablish connection to client{}\n".format(self.inputsAddr[connection])
                            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                                self.logger.info(msg.strip())
                                self.logger.info("Server report [{}] connected client(s)".format(len(self.inputs)-1))

                            # notify local listeners
                            self.notify_event_listeners(gc.EV_RMT_HELLO, msg)

                            # send welcome message, only to new client
                            python_ver = sys.version.replace('\n', "")
                            sys_str = str(os.uname()).replace("posix.uname_result", "")
                            welcome_str = \
                                "==========================================\n"\
                                f"Welcome to gsat server {vinfo.__version__}, running on:\n"\
                                f"host: {self.host} port: {soc.getsockname()[1]}\n"\
                                f"python: {python_ver}\n"\
                                f"system: {sys_str}\n"\
                                "\n"

                            msg = gc.SimpleEvent(gc.EV_RMT_HELLO, welcome_str, id(self))

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
                                # self.eventPut(data)
                                self.clientEventQueue.add_event(data)

                            else:
                                if not self.rxBufferLen:
                                    # no data client disconnected, clean up
                                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                                        self.logger.info(
                                            "Connection reset by peer, client {}".format(self.inputsAddr[soc]))

                                    self.clean_up(soc)

                                    if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                                        self.logger.info(
                                            "Server report [{}] connected client(s)".format(len(self.inputs)-1))

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
                        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                            self.logger.info("Unknown exception from client {}".format(self.inputsAddr[soc]))

                        self.clean_up(soc)

                elif self.swState == gc.STATE_ABORT:
                    # do nothing, wait to be terminated
                    pass
                else:
                    exMsg = "unexpected state [%d], Aborting..." \
                            % (self.swState)

                    self.logger.error(exMsg.strip())

                    self.notify_event_listeners(gc.EV_ABORT, exMsg)
                    break
            else:
                message = "Remote port is close, terminating.\n"

                self.logger.error(message.strip())

                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # add data to queue
                self.notify_event_listeners(gc.EV_ABORT, message)
                break

            time.sleep(0.010)

        # exit thread
        self.close()
        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            self.logger.info("thread exit")

        self.notify_event_listeners(gc.EV_EXIT, "")
