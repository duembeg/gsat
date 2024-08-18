"""----------------------------------------------------------------------------
    remote_ws_server.py

    Copyright (C) 2024 Wilhelm Duembeg

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
import asyncio
import socketio
import uvicorn
import logging
import queue
import threading
import socket
import pickle

import modules.config as gc
import modules.machif_progexec as mi_progexec

import modules.version_info as vinfo


class RemoteServer(threading.Thread, gc.EventQueueIf):
    """
    Remote WebSocket GSAT Server

    """

    def __init__(self, event_handler):
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        self.port = gc.CONFIG_DATA.get('/remote/webSocketPort', 61803)
        self.api_token = gc.CONFIG_DATA.get('/remote/ApiToken', "")
        self.machif_prog_exec = None
        self.serial_port_is_open = False
        self.device_detected = False
        self.inputs_addr = {}
        self.clients = []
        self.server = None
        self.end_thread = False
        self.hostname = ""
        self.host_ip_address = ""
        self.server_id = ""

        self.swState = gc.STATE_RUN

        self.logger = logging.getLogger()

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            self.logger.info(f"init logging id:0x{id(self):x} {self}")

        if event_handler is not None:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                self.logger.info(f"Added event listener id:0x{id(event_handler):x} {event_handler}")

            self.add_event_listener(event_handler)

        # websocket init vars
        self.sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
        self.app = socketio.ASGIApp(self.sio)
        self.VALID_TOKENS = {self.api_token}

        self.sio.event(self.connect)
        self.sio.event(self.disconnect)
        self.sio.on('client_message', self.on_message)

        loop = asyncio.get_event_loop()
        loop.create_task(self.check_queue())

        # start thread
        self.start()

    async def connect(self, sid, environ, auth):
        if not self.hostname:
            self.hostname = socket.gethostname()
            self.host_ip_address = socket.gethostbyname(self.hostname)
            self.server_id = f"{self.hostname}({self.host_ip_address})"

        if auth and auth.get('token') in self.VALID_TOKENS:

            client_ip = environ['REMOTE_ADDR']
            self.inputs_addr[sid] = client_ip
            self.clients.append(sid)

            msg = f"Client connected with valid token: {sid}\n"
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
                self.logger.info(msg.strip())
                self.logger.info(f"Server report [{len(self.clients)}] connected client(s)")

            # notify local listeners
            self.notify_event_listeners(gc.EV_RMT_HELLO, msg)

            # send welcome message, only to new client
            python_ver = sys.version.replace('\n', "")
            sys_str = str(os.uname()).replace("posix.uname_result", "")
            welcome_str = \
                "==========================================\n"\
                f"Welcome to gsat server {vinfo.__version__}, running on:\n"\
                f"host: {self.hostname} port: {self.port}\n"\
                f"python: {python_ver}\n"\
                f"system: {sys_str}\n"\
                "\n"

            msg = gc.SimpleEvent(gc.EV_RMT_HELLO, welcome_str, self.server_id)

            await self.send(sid, msg)

            if self.serial_port_is_open:
                msg = gc.SimpleEvent(gc.EV_SER_PORT_OPEN, 0, self.server_id)
                await self.send(sid, msg)

        else:
            print(f"Client connection refused (invalid token): {sid}")
            return False  # Refuse the connection

    async def disconnect(self, sid):
        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            self.logger.info(f"Client disconnected: {sid}")
            self.clients.remove(sid)
            self.logger.info(f"Server report [{len(self.clients)}] connected client(s)")

    async def on_message(self, sid, rx_data):
        """
        Handle incoming messages from clients

        """

        if isinstance(rx_data, str):
            self.logger.info(f"Unknown msg type:{type(rx_data)} len:{len(rx_data)} from {sid}, data:{rx_data}")
            data = rx_data
        else:
            data = pickle.loads(rx_data)

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            if isinstance(data, gc.SimpleEvent):
                ev_str = gc.EV_2STR_DICT.get(data.event_id, "unknown")
                log_msg = f"Recv msg {ev_str}({data.event_id}) len:{len(rx_data)} from {sid} "
            else:
                log_msg = f"Unknown msg type:{type(data)} len:{len(rx_data)} from {sid}"

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_HEXDUMP):
                log_msg = log_msg + gc.verbose_hexdump("", rx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_HEX):
                log_msg = log_msg + gc.verbose_data_hex("", rx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_STR):
                log_msg = log_msg + gc.verbose_data_ascii("", rx_data)

            self.logger.info(log_msg)

        if isinstance(data, gc.SimpleEvent):
            data.sender = sid
            await self.process_client_message(data)

    async def check_queue(self):
        while True:
            await self.process_queue()
            await asyncio.sleep(0.01)

            if self.end_thread:
                break

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
        pass

    def close(self):
        pass

    async def send(self, connection, data):
        tx_data = pickle.dumps(data, protocol=5)
        await self.sio.emit('server_message', tx_data, to=connection)

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            ev_str = gc.EV_2STR_DICT.get(data.event_id, "unknown")
            log_msg = f"Send msg {ev_str}({data.event_id}) len:{len(tx_data)} to {connection} "

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_HEXDUMP):
                log_msg = log_msg + gc.verbose_hexdump("->", tx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_HEX):
                log_msg = log_msg + gc.verbose_data_hex("->", tx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_STR):
                log_msg = log_msg + gc.verbose_data_ascii("->", tx_data)

            self.logger.info(log_msg)

    async def send_broadcast(self, data):
        tx_data = pickle.dumps(data, protocol=5)
        await self.sio.emit('server_message', tx_data)

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            ev_str = gc.EV_2STR_DICT.get(data.event_id, "unknown")
            log_msg = f"Send msg {ev_str}({data.event_id}) len:{len(tx_data)} to all "

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_HEXDUMP):
                log_msg = log_msg + gc.verbose_hexdump("->", tx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_HEX):
                log_msg = log_msg + gc.verbose_data_hex("->", tx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_STR):
                log_msg = log_msg + gc.verbose_data_ascii("->", tx_data)

            self.logger.info(log_msg)

    def run(self):
        # uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="info")
        log_level = "error"
        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER):
            log_level = "info"

        if 'curses' in sys.modules:
            self.logger.info("Warning: curses module found, using log_config=None")
            config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level=log_level, log_config=None)
        else:
            config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level=log_level)

        self.server = uvicorn.Server(config)
        # self.server.run()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Schedule check_queue in the uvicorn server's event loop
        loop.create_task(self.check_queue())

        loop.run_until_complete(self.server.serve())

    async def process_queue(self):
        """
        Local event handlers

        """
        # process events from queue
        try:
            ev = self._eventQueue.get_nowait()
        except queue.Empty:
            pass
        else:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_EV):
                self.logger.info(f"{gc.EV_2STR_DICT.get(ev.event_id)}({ev.event_id}) from 0x{id(ev.sender):x} {ev.sender}")

            # this message came from progexec tread
            if ev.sender is self.machif_prog_exec:

                if ev.event_id in [gc.EV_DATA_STATUS, gc.EV_DATA_OUT, gc.EV_DATA_IN]:
                    # these are the most common events from prog exe, process first

                    ev.sender = self.server_id
                    # ev.sender = id(self)
                    await self.send_broadcast(ev)

                elif ev.event_id == gc.EV_SER_PORT_OPEN:
                    self.serial_port_is_open = True
                    ev.sender = self.server_id
                    # ev.sender = id(self)
                    await self.send_broadcast(ev)

                elif ev.event_id == gc.EV_SER_PORT_CLOSE:
                    self.serial_port_is_open = False
                    ev.sender = self.server_id
                    # ev.sender = id(self)
                    await self.send_broadcast(ev)

                elif ev.event_id == gc.EV_CMD_EXIT:
                    self.machif_prog_exec = None

                elif ev.event_id == gc.EV_ABORT:
                    if self.machif_prog_exec is not None:
                        self.machif_prog_exec.add_event(gc.EV_CMD_EXIT)

                    ev.sender = self.server_id
                    # ev.sender = id(self)
                    ev.event_id = gc.EV_DATA_IN
                    ev.data = "remote machifProgExec {}".format(ev.data)
                    await self.send_broadcast(ev)

                elif ev.event_id == gc.EV_DEVICE_DETECTED:
                    self.device_detected = True

                    # This will be done by progexec thread where it belongs
                    # self.run_device_init_script()

                    ev.sender = self.server_id
                    # ev.sender = id(self)
                    await self.send_broadcast(ev)

                else:
                    ev.sender = self.server_id
                    # ev.sender = id(self)
                    await self.send_broadcast(ev)

            # local/non-machine messaging
            elif ev.event_id == gc.EV_HELLO:
                self.add_event_listener(ev.sender)

            elif ev.event_id == gc.EV_GOOD_BYE:
                self.remove_event_listener(ev.sender)

            elif ev.event_id == gc.EV_CMD_EXIT:
                if self.machif_prog_exec is not None:
                    self.machif_prog_exec.add_event(gc.EV_CMD_EXIT)

                if self.server is not None:
                    self.server.should_exit = True

                self.close()

                self.end_thread = True

            else:
                self.logger.error(
                    "EV_?? got unknown event!! {} from 0x{:x} {}".format(ev.event_id, id(ev.sender), ev.sender))

    async def process_client_message(self, ev):
        """
        Process client events

        """

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_EV):
            ev_str = gc.EV_2STR_DICT.get(ev.event_id, "unknown")
            self.logger.info(f"{ev_str}({ev.event_id}) from client {ev.sender}")

        # this message came from clients
        if ev.event_id == gc.EV_CMD_TXDATA:
            pass

        elif ev.event_id == gc.EV_CMD_OPEN:
            if self.machif_prog_exec is None:
                self.machif_prog_exec = mi_progexec.MachIfExecuteThread(self)

        elif ev.event_id == gc.EV_CMD_CLOSE:
            if self.machif_prog_exec is not None:
                self.machif_prog_exec.add_event(gc.EV_CMD_EXIT)

        elif ev.event_id == gc.EV_CMD_GET_CONFIG:
            port_list = self.get_serial_ports()
            gc.CONFIG_DATA.add('/temp/SerialPorts', port_list)
            gc.CONFIG_DATA.add('/temp/RemoteServer', True)
            await self.send(ev.sender, gc.SimpleEvent(gc.EV_RMT_CONFIG_DATA, gc.CONFIG_DATA, self.server_id))
            gc.CONFIG_DATA.add('/temp/RemoteServer', False)

        elif ev.event_id == gc.EV_CMD_GET_GCODE:
            if self.machif_prog_exec is not None:
                gcode_dict = self.machif_prog_exec.get_gcode_dict()
                await self.send(ev.sender, gc.SimpleEvent(gc.EV_GCODE, gcode_dict, self.server_id))

        elif ev.event_id == gc.EV_CMD_GET_BRK_PT:
            if self.machif_prog_exec is not None:
                gcode_dict = self.machif_prog_exec.get_gcode_dict()
                await self.send(ev.sender, gc.SimpleEvent(gc.EV_BRK_PT, gcode_dict['breakPoints'], self.server_id))

        elif ev.event_id == gc.EV_CMD_UPDATE_CONFIG:
            machine_device = gc.CONFIG_DATA.get('/machine/Device', "")
            machine_port = gc.CONFIG_DATA.get('/machine/Port', "")
            machine_baud = gc.CONFIG_DATA.get('/machine/Baud')

            tcp_port = gc.CONFIG_DATA.get('/remote/TcpPort', 61801)

            if ev.data is not None:
                gc.CONFIG_DATA = ev.data
                gc.CONFIG_DATA.save()

            if self.machif_prog_exec is not None:
                self.machif_prog_exec.add_event(gc.EV_CMD_UPDATE_CONFIG)

                # close serial port if settings changed
                if (machine_device != gc.CONFIG_DATA.get('/machine/Device') or
                   machine_port != gc.CONFIG_DATA.get('/machine/Port') or
                   machine_baud != gc.CONFIG_DATA.get('/machine/Baud')):
                    self.machif_prog_exec.add_event(gc.EV_CMD_EXIT)

            # re start server if settings changed
            if tcp_port != gc.CONFIG_DATA.get('/remote/TcpPort', 61801):
                self.port = gc.CONFIG_DATA.get('/remote/TcpPort', 61801)

                # send message to all clients
                await self.send_broadcast(
                    gc.SimpleEvent(gc.EV_RMT_GOOD_BYE, "** Server settings changing, restart...\n", self.server_id))

                self.close()
                self.open()

        elif ev.event_id == gc.EV_CMD_RMT_RESET:
            pass
            # os.system('sudo reboot')

        elif ev.event_id == gc.EV_RMT_PING:
            await self.send(ev.sender, gc.SimpleEvent(gc.EV_RMT_PONG, 0, self.server_id))

        else:
            # # if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_SERVER_EV):
            # self.logger.error(
            #     "EV_?? got unknown event!! {} from client{}".format(e.event_id, self.inputs_addr[e.sender]))

            if self.machif_prog_exec is not None:
                ev.sender = self
                self.machif_prog_exec.add_event(ev)
