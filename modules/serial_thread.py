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
import re
import sys
import serial
import tty
import threading
import Queue
import time
import pdb
import wx

import modules.config as gc

class SerialPortThread(threading.Thread, gc.EventQueueIf):
    """ Threads to send and monitor serial port for new data.
    """

    def __init__(self, event_handler, state_data, cmd_line_options):
        """ Init serial class
        """
        threading.Thread.__init__(self)
        gc.EventQueueIf.__init__(self)

        # init local variables
        self.eventHandler = event_handler
        self.serPort = None
        self.stateData = state_data
        self.cmdLineOptions = cmd_line_options

        self.rxBuffer = ""

        self.swState = gc.STATE_RUN

        # start thread
        self.start()

    def processQueue(self):
        """ Event handlers
        """
        # process events from queue
        if not self._eventQueue.empty():
            # get item from queue
            e = self._eventQueue.get()

            if e.event_id == gc.EV_CMD_EXIT:
                if self.cmdLineOptions.vverbose:
                    print "** SerialPortThread got event gc.gEV_CMD_EXIT."

                self.serialClose()

                self.endThread = True

            elif e.event_id == gc.EV_CMD_SER_TXDATA:
                if self.cmdLineOptions.vverbose:
                    print "** SerialPortThread got event gc.gEV_CMD_SER_TXDATA."

                self.serialWrite(e.data)

            else:
                if self.cmdLineOptions.vverbose:
                    print "** SerialPortThread got unknown event!! [%s]." % str(
                        e.event_id)

    def serialClose(self):
        """ Close serial port
        """
        if self.serPort is not None:
            if self.serPort.isOpen():
                # self.serPort.flushInput()
                self.serPort.close()

                if self.cmdLineOptions.vverbose:
                    print "** SerialPortThread close serial port."

                self.eventHandler.eventPut(gc.EV_SER_PORT_CLOSE, 0)

    def serialOpen(self):
        """ Open serial port
        """
        exFlag = False
        exMsg = ""

        self.serialClose()

        port = self.stateData.serialPort
        baud = self.stateData.serialPortBaud

        #import pdb;pdb.set_trace()

        if port != "None":
            portName = port
            if os.name == 'nt':
                portName = r"\\.\%s" % (str(port))

            try:
                self.serPort = serial.Serial(port=portName,
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

            except:
                e = sys.exc_info()[0]
                exMsg = "** Unexpected exception: %s\n" % str(e)
                exFlag = True

            if self.serPort is not None:
                if self.serPort.isOpen():
                    # change tty mode, this is strange and not doing it
                    # was causing issues reconnecting to GRBL if disconnected
                    # because exception, it was fine other wise.
                    # These two lines makes it so opening port again will
                    # connect successfully even after exception close
                    serial_fd = self.serPort.fileno()
                    tty.setraw(serial_fd)

                    if self.cmdLineOptions.vverbose:
                        print "** SerialPortThread open serial port [%s] at %s bps." % (
                            portName, baud)

                    # no exceptions report serial port open
                    self.eventHandler.eventPut(gc.EV_SER_PORT_OPEN, port)

        else:
            exMsg = "There is no valid serial port detected {%s}." % str(port)
            exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.STATE_ABORT

            if self.cmdLineOptions.verbose:
                print exMsg.strip()

            # add data to queue
            self.eventHandler.eventPut(gc.EV_ABORT, exMsg)

    def serialRead(self):
        exFlag = False
        exMsg = ""
        serialData = ""

        try:
            inDataCnt = self.serPort.inWaiting()

            while inDataCnt > 0 and not exFlag:

                # read data from port
                # Was running with performance issues using readline(), move to read()
                # Using "".join() as performance is much better then "+="
                #serialData = self.serPort.readline()
                #self.rxBuffer += self.serPort.read(inDataCnt)
                self.rxBuffer = "".join(
                    [self.rxBuffer, self.serPort.read(inDataCnt)])

                while '\n' in self.rxBuffer:
                    serialData, self.rxBuffer = self.rxBuffer.split('\n', 1)

                    if serialData:

                        if self.cmdLineOptions.vverbose:
                            print "[%03d] <- ASCII:%s HEX:%s" % (len(serialData),
                                serialData.strip(), ':'.join(x.encode('hex') for x in serialData))
                        elif self.cmdLineOptions.verbose:
                            print "[%03d] <- %s" % (len(serialData),
                                serialData.strip())

                        # add data to queue
                        self.eventHandler.eventPut(gc.EV_SER_RXDATA,
                            "%s\n" % serialData)

                        # attempt to reduce starvation on other threads
                        # when serial traffic is constant
                        time.sleep(0.01)

                inDataCnt = self.serPort.inWaiting()

        except serial.SerialException, e:
            exMsg = "** PySerial exception: %s\n" % e.message
            exFlag = True

        except OSError, e:
            exMsg = "** OSError exception: %s\n" % str(e)
            exFlag = True

        except IOError, e:
            exMsg = "** IOError exception: %s\n" % str(e)
            exFlag = True

        except:
            e = sys.exc_info()[0]
            exMsg = "** Unexpected exception: %s\n" % str(e)
            exFlag = True

        if exFlag:
            # make sure we stop processing any states...
            self.swState = gc.STATE_ABORT

            if self.cmdLineOptions.verbose:
                print exMsg.strip()

            # add data to queue
            self.eventHandler.eventPut(gc.EV_ABORT, exMsg)
            self.serialClose()

    def serialWrite(self, serialData):
        exFlag = False
        exMsg = ""

        if len(serialData) == 0:
            return

        if self.serPort.isOpen():

            try:
                # send command
                self.serPort.write(serialData)

                if self.cmdLineOptions.vverbose:
                    print "[%03d] -> ASCII:%s HEX:%s" % (len(serialData),
                                                         serialData.strip(), ':'.join(x.encode('hex') for x in serialData))
                elif self.cmdLineOptions.verbose:
                    print "[%03d] -> %s" % (len(serialData),
                                            serialData.strip())

            except serial.SerialException, e:
                exMsg = "** PySerial exception: %s\n" % e.message
                exFlag = True

            except OSError, e:
                exMsg = "** OSError exception: %s\n" % str(e)
                exFlag = True

            except IOError, e:
                exMsg = "** IOError exception: %s\n" % str(e)
                exFlag = True

            except:
                e = sys.exc_info()[0]
                exMsg = "** Unexpected excetion: %s\n" % str(e)
                exFlag = True

            if exFlag:
                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                if self.cmdLineOptions.verbose:
                    print exMsg.strip()

                # add data to queue
                self.eventHandler.eventPut(gc.EV_ABORT, exMsg)
                self.serialClose()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread.
        self.endThread = False

        if self.cmdLineOptions.vverbose:
            print "** SerialPortThread start."

        self.serialOpen()

        while ((self.endThread != True) and (self.serPort is not None)):

            # process input queue for new commands or actions
            self.processQueue()

            # check if we need to exit now
            if self.endThread:
                break

            if self.serPort.isOpen():
                if self.swState == gc.STATE_RUN:
                    self.serialRead()
                elif self.swState == gc.STATE_ABORT:
                    # do nothing, wait to be terminated
                    pass
                else:
                    exMsg = "** SerialPortThread unexpected state [%d], Aborting..." % (
                        self.swState)
                    if self.cmdLineOptions.verbose:
                        print exMsg

                    self.eventHandler.eventPut(gc.EV_ABORT, exMsg)
                    break
            else:
                message = "** Serial Port is close, SerialPortThread terminating.\n"

                if self.cmdLineOptions.verbose:
                    print message.strip()

                # make sure we stop processing any states...
                self.swState = gc.STATE_ABORT

                # add data to queue
                self.eventHandler.eventPut(gc.EV_ABORT, "")
                wx.LogMessage(message)
                break

            time.sleep(0.01)

        if self.cmdLineOptions.vverbose:
            print "** SerialPortThread exit."

        self.eventHandler.eventPut(gc.EV_EXIT, "")
