"""----------------------------------------------------------------------------
    remote_ws_client.py

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
import asyncio
import socketio
import threading
import logging
import socket
import queue
import pickle
import socketio.exceptions

from datetime import datetime

import modules.config as gc


class RemoteClient(threading.Thread, gc.EventQueueIf):
    """
    Threads to send and monitor network socket for new data.

    """

    def __init__(self, event_handler, host="", port=None, api_token=None, keep_alive=False):
        """
        Init remote client class

        """
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        self.remote_index = gc.CONFIG_DATA.get('/remotes/Index', 0)

        if host:
            self.host = host
        else:
            self.host = gc.CONFIG_DATA.get(f'/remotes/remote{self.remote_index}/Host', "")

        if port:
            self.port = port
        else:
            self.port = gc.CONFIG_DATA.get(f'/remotes/remote{self.remote_index}/WebSocketPort', 61803)

        if api_token:
            self.api_token = api_token
        else:
            self.api_token = gc.CONFIG_DATA.get(f'/remotes/remote{self.remote_index}/ApiToken', "")

        self.swState = gc.STATE_RUN

        self.logger = logging.getLogger()

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
            self.logger.info(f"init logging id:0x{id(self):x} {self}")

        if event_handler is not None:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
                self.logger.info(f"Added event listener id:0x{id(event_handler):x} {event_handler}")

            self.add_event_listener(event_handler)

        self.connected = False  # Connection status flag
        self.keep_alive = keep_alive

        # socket io init
        # self.sio = socketio.AsyncClient(logger=True, engineio_logger=True)
        self.sio = socketio.AsyncClient(reconnection=True, reconnection_attempts=5, reconnection_delay=5)

        if self.keep_alive:
            self.sio.eio.ping_interval = 20
            self.sio.eio.ping_timeout = 30

        self.exit_event = asyncio.Event()
        self.url = f"ws://{self.host}:{self.port}"

        self.sio.event(self.connect)
        self.sio.event(self.connect_error)
        self.sio.event(self.disconnect)
        self.sio.on('server_message', self.on_message)

        # start thread
        self.start()

    class ExitSignal(Exception):
        pass

    def close(self):
        """
        Close remote connection

        """
        if self.connected:
            # Get the current time and format it
            now = datetime.now()
            formatted_time = now.strftime('%Y%m%d:%I:%M%p')

            msg = f"Close remote connection to {self.url} at {formatted_time}\n"

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
                self.logger.info(msg.strip())

            self.notify_event_listeners(gc.EV_RMT_PORT_CLOSE, msg)
            self.exit_event.set()
            self.connected = False

    async def connect(self):
        # Get the current time and format it
        now = datetime.now()
        formatted_time = now.strftime('%Y%m%d:%I:%M%p')

        msg = f"Connected to {self.url} at {formatted_time}\n"
        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
            self.logger.info(msg.strip())

        # await self.sio.emit('client_message', 'Python client connected: Hello Wold')
        self.connected = True

        # Resolve the hostname to an IP address
        try:
            self.server_ip = socket.gethostbyname(self.host)
        except socket.gaierror:
            self.server_ip = ""

        # sending directly to who created us
        self.notify_event_listeners(gc.EV_RMT_PORT_OPEN, msg)

    async def connect_error(self, data):
        error_msg = f"Failed to connect, {data}\n"
        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
            self.logger.error(error_msg.strip())

        self.notify_event_listeners(gc.EV_ABORT, error_msg)
        self.exit_event.set()

        self.close()

    async def disconnect(self):
        self.close()

    def get_hostname(self):
        """
        Get server host info

        """
        hostname = ""

        if self.connected:
            hostname = f"{self.host}:{self.server_ip}"

        return hostname

    async def on_message(self, rx_data):

        if isinstance(rx_data, str):
            print(f"Received message: {rx_data}")
            data = rx_data
        else:
            data = pickle.loads(rx_data)

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
            if isinstance(data, gc.SimpleEvent):
                ev_str = gc.EV_2STR_DICT.get(data.event_id, "unknown")
                log_msg = f"Recv msg {ev_str}({data.event_id}) len:{len(rx_data)} from {self.sio.sid} "
            else:
                log_msg = f"Unknown msg type:{type(data)} len:{len(rx_data)} from {self.sio.sid} "

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT_HEXDUMP):
                log_msg = log_msg + gc.verbose_hexdump("", rx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT_HEX):
                log_msg = log_msg + gc.verbose_data_hex("", rx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT_STR):
                log_msg = log_msg + gc.verbose_data_ascii("", rx_data)

            self.logger.info(log_msg)

        if isinstance(data, gc.SimpleEvent):
            data.sender = self
            self.notify_event_listeners(data)

    async def send_messages(self):
        while not self.exit_event.is_set():
            message = await asyncio.get_event_loop().run_in_executor(None, input, "Enter message (or 'exit' to quit): ")
            if message.lower() == 'exit':
                self.exit_event.set()
                return  # Exit the function immediately
            await self.sio.emit('chat_message', message)

    async def wait_for_exit(self):
        await self.exit_event.wait()
        raise self.ExitSignal("Exit requested")

    async def run_loop(self):
        try:
            # await self.sio.connect(self.url, auth={'token': self.api_token})
            await self.sio.connect(self.url, auth={'token': self.api_token})
            # await self.sio.connect('http://localhost:8000', auth={'token': API_TOKEN})

            await asyncio.gather(
                self.sio.wait(),
                self.process_queue_loop(),
                self.wait_for_exit()
            )
        except self.ExitSignal:
            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
                self.logger.info("Exit signal received")
        except socketio.exceptions.ConnectionError as e:
            self.logger.error(f"Failed to connect: {e}")
            # Notify UI listeners (wx / PySide) so connect failures clear state
            self.notify_event_listeners(
                gc.EV_ABORT, f"Failed to connect: {e}\n")
        finally:
            if self.sio.connected:
                await self.sio.disconnect()

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
                self.logger.info("Disconnected and shutting down.")

    async def process_queue_loop(self):
        while not self.exit_event.is_set():
            await self.process_queue()
            await asyncio.sleep(0.01)

    async def process_queue(self):
        """
        Event handlers

        """
        # process events from queue
        try:
            e = self._eventQueue.get_nowait()
        except queue.Empty:
            pass
        else:
            if e.event_id in [gc.EV_HELLO, gc.EV_GOOD_BYE, gc.EV_CMD_EXIT]:

                if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT_EV):
                    self.logger.info(f"{gc.EV_2STR_DICT.get(e.event_id)} from 0x{id(e.sender):x} {e.sender}")

                if e.event_id == gc.EV_HELLO:
                    self.add_event_listener(e.sender)

                elif e.event_id == gc.EV_GOOD_BYE:
                    self.remove_event_listener(e.sender)

                elif e.event_id == gc.EV_CMD_EXIT:
                    self.close()

            else:
                # if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_EV):
                # self.logger.error("EV_?? got unknown event!! from 0x{:x} {}".format(id(e.sender), e.sender))

                # commands that we don't handle forward to server
                e.sender = id(e.sender)
                await self.send(e)

    async def send(self, data):
        """
        Send data to remote server

        """
        tx_data = pickle.dumps(data)

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
            if isinstance(data, gc.SimpleEvent):
                ev_str = gc.EV_2STR_DICT.get(data.event_id, "unknown")
                log_msg = f"Send msg {ev_str}({data.event_id}) len:{len(tx_data)} to {self.sio.sid} "
            else:
                log_msg = f"Unknown msg type:{type(data)} to {self.sio.sid} "

            if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT_HEXDUMP):
                log_msg = log_msg + gc.verbose_hexdump("", tx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT_HEX):
                log_msg = log_msg + gc.verbose_data_hex("", tx_data)

            elif gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT_STR):
                log_msg = log_msg + gc.verbose_data_ascii("", tx_data)

            self.logger.info(log_msg)

        # send the entire message encode
        await self.sio.emit('client_message', tx_data)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.run_loop())

        if gc.test_verbose_mask(gc.VERBOSE_MASK_REMOTEIF_CLIENT):
            self.logger.info(f"Thread exit id:0x{id(self):x} {self}")

        self.notify_event_listeners(gc.EV_EXIT, "")
