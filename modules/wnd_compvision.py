"""----------------------------------------------------------------------------
   wnd_compvision.py

   Copyright (C) 2013 Wilhelm Duembeg

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
import threading
import time
import queue
import wx
from wx.lib import scrolledpanel as scrolled

import modules.config as gc

# --------------------------------------------------------------------------
# Thread/ComputerVisionWindow communication events
# --------------------------------------------------------------------------
EV_CMD_CV_EXIT = 1000
EV_CMD_CV_IMAGE = 3000

ID_CV2_GOTO_CAM = wx.NewId()
ID_CV2_GOTO_TOOL = wx.NewId()
ID_CV2_CAPTURE_TIMER = wx.NewId()


class gsatCV2Panel(wx.ScrolledWindow):
    """
    Camera sensor panel

    """
    def __init__(
        self, parent, config_data, state_data, cmd_line_options,
        **args
    ):

        wx.ScrolledWindow.__init__(self, parent, **args)

        self.capture = False
        self.mainWindow = parent
        self.configData = config_data
        self.stateData = state_data
        self.captureTimer = None
        self.cmdLineOptions = cmd_line_options
        self.settingsChanged = True
        self.scrollUnit = 10

        # thread communication queues
        self.cvw2tQueue = queue.Queue()
        self.t2cvwQueue = queue.Queue()

        self.visionThread = None
        self.captureTimer = wx.Timer(self, ID_CV2_CAPTURE_TIMER)
        self.bmp = None

        self.InitConfig()
        self.InitUI()

        # register for events
        self.Bind(wx.EVT_TIMER, self.OnCaptureTimer, id=ID_CV2_CAPTURE_TIMER)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_SHOW, self.OnShow)

        # register for thread events
        gc.reg_thread_queue_data_event(self, self.OnThreadEvent)

    def InitConfig(self):
        self.cv2Enable = self.configData.get('/cv2/Enable')
        self.cv2Crosshair = self.configData.get('/cv2/Crosshair')
        self.cv2CaptureDevice = self.configData.get('/cv2/CaptureDevice')
        self.cv2CapturePeriod = self.configData.get('/cv2/CapturePeriod')
        self.cv2CaptureWidth = self.configData.get('/cv2/CaptureWidth')
        self.cv2CaptureHeight = self.configData.get('/cv2/CaptureHeight')

    def InitUI(self):
        vPanelBoxSizer = wx.BoxSizer(wx.VERTICAL)

        # capture panel
        scSizer = wx.BoxSizer(wx.VERTICAL)
        self.scrollPanel = scrolled.ScrolledPanel(self, -1)
        self.capturePanel = wx.BitmapButton(
            self.scrollPanel, -1, style=wx.NO_BORDER)
        scSizer.Add(self.capturePanel)
        self.scrollPanel.SetSizer(scSizer)
        self.scrollPanel.SetAutoLayout(True)

        # self.capturePanel.Bind(wx.EVT_MOTION, self.OnCapturePanelMouse)
        # self.capturePanel.Enable(False)

        vPanelBoxSizer.Add(self.scrollPanel, 1, wx.EXPAND)

        # buttons
        line = wx.StaticLine(self, -1, size=(20, -1), style=wx.LI_HORIZONTAL)
        vPanelBoxSizer.Add(
            line, 0, wx.GROW | wx.LEFT | wx.RIGHT | wx.TOP, border=5)

        btnsizer = wx.StdDialogButtonSizer()

        self.centerScrollButton = wx.Button(self, label="Center")
        self.centerScrollButton.SetToolTip(wx.ToolTip("Center scroll bars"))
        self.Bind(wx.EVT_BUTTON, self.OnCenterScroll, self.centerScrollButton)
        btnsizer.Add(self.centerScrollButton)

        self.captureButton = wx.ToggleButton(self, label="Capture")
        self.captureButton.SetToolTip(
            wx.ToolTip("Toggle video capture on/off"))
        self.Bind(wx.EVT_TOGGLEBUTTON, self.OnCapture, self.captureButton)
        self.Bind(wx.EVT_UPDATE_UI, self.OnCaptureUpdate, self.captureButton)
        btnsizer.Add(self.captureButton)

        btnsizer.Realize()

        vPanelBoxSizer.Add(btnsizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        # Finish up init UI
        self.SetSizer(vPanelBoxSizer)
        self.SetAutoLayout(True)
        width, height = self.GetSize()
        self.SetScrollbars(self.scrollUnit, self.scrollUnit, int(width/self.scrollUnit), int(height/self.scrollUnit))

    def UpdateSettings(self, config_data):
        self.configData = config_data
        self.settingsChanged = True

        self.InitConfig()

        if self.capture and self.IsShown():
            self.StopCapture()
            self.StartCapture()

    def UpdateUI(self, stateData, statusData=None):
        self.stateData = stateData

    def UpdateCapturePanel(self):

        if self.settingsChanged:
            self.settingsChanged = False

            self.scrollPanel.GetSizer().Layout()

            width, height = self.capturePanel.GetSize()

            self.scrollPanel.SetScrollbars(
                self.scrollUnit, self.scrollUnit, int(width/self.scrollUnit), int(height/self.scrollUnit))

            self.scrollPanel.GetSizer().Layout()

            self.CenterScroll()
            self.Refresh()

    def OnCapture(self, w):
        if self.capture:
            self.StopCapture()
        else:
            self.StartCapture()

    def OnCaptureUpdate(self, e):
        e.Enable(self.cv2Enable)

        if self.capture:
            self.captureButton.SetValue(True)
        else:
            self.captureButton.SetValue(False)

    def OnCaptureTimer(self, e):
        self.ProcessThreadQueue()

    def OnCenterScroll(self, e):
        self.CenterScroll()

    def OnDestroy(self, e):
        self.StopCapture()
        e.Skip()

    def OnShow(self, e):
        if self.capture and not e.GetShow():
            self.StopCapture()
        e.Skip()

    def OnThreadEvent(self, e):
        self.ProcessThreadQueue()

    def CenterScroll(self):
        x, y = self.capturePanel.GetClientSize()
        sx, sy = self.scrollPanel.GetSize()
        sux, suy = self.scrollPanel.GetScrollPixelsPerUnit()

        try:
            self.scrollPanel.Scroll((x-sx)/2/sux, (y-sy)/2/suy)

        except:
            pass

    def ProcessThreadQueue(self):
        if self.cmdLineOptions.vverbose:
            print("** gsatCV2Panel ProcessThreadQueue.")

        goitem = False

        while (not self.t2cvwQueue.empty()):
            te = self.t2cvwQueue.get()
            goitem = True

            if te.event_id == EV_CMD_CV_IMAGE:
                if self.cmdLineOptions.vverbose:
                    print("** gsatCV2Panel got event gEV_CMD_CV_IMAGE.")

                image = te.data

                if image is not None:
                    height, width, x = image.shape
                    self.bmp = wx.Bitmap.FromBuffer(width, height, image)
                    self.capturePanel.SetBitmapLabel(self.bmp)
                    # self.capturePanel.SetBitmapDisabled(self.bmp)

                    if self.settingsChanged:
                        wx.CallAfter(self.UpdateCapturePanel)

        # acknowledge thread
        if goitem:
            self.t2cvwQueue.task_done()

    def StartCapture(self):
        if self.cmdLineOptions.vverbose:
            print("** gsatCV2Panel StartCapture.")

        if not self.capture:

            self.capture = True

            if self.visionThread is None and self.cv2Enable:
                self.visionThread = gsatComputerVisionThread(
                    self, self.cvw2tQueue, self.t2cvwQueue, self.configData,
                    self.cmdLineOptions
                )

            if self.captureTimer is not None and self.cv2Enable:
                self.captureTimer.Start(self.cv2CapturePeriod)

    def StopCapture(self):

        if self.capture:
            if self.cmdLineOptions.vverbose:
                print("** gsatCV2Panel StopCapture.")

            self.capture = False

            if self.captureTimer is not None:
                self.captureTimer.Stop()

            if self.visionThread is not None:
                self.cvw2tQueue.put(gc.SimpleEvent(EV_CMD_CV_EXIT, None))

                goitem = False
                while (not self.t2cvwQueue.empty()):
                    # te = self.t2cvwQueue.get()
                    self.t2cvwQueue.get()
                    goitem = True

                # make sure to unlock thread
                if goitem:
                    self.t2cvwQueue.task_done()

                # self.cvw2tQueue.join()
                self.visionThread = None


class gsatComputerVisionThread(threading.Thread):
    """
    Threads that capture and processes vide frames.

    """

    def __init__(
        self, notify_window, in_queue, out_queue, config_data,
        cmd_line_options
    ):

        threading.Thread.__init__(self)

        # init local variables
        self.notifyWindow = notify_window
        self.cvw2tQueue = in_queue
        self.t2cvwQueue = out_queue
        self.cmdLineOptions = cmd_line_options
        self.configData = config_data

        if self.cmdLineOptions.vverbose:
            print("gsatComputerVisionThread ALIVE.")

        self.InitConfig()

        # start thread
        self.start()

    def InitConfig(self):
        self.cv2Enable = self.configData.get('/cv2/Enable')
        self.cv2Crosshair = self.configData.get('/cv2/Crosshair')
        self.cv2CaptureDevice = self.configData.get('/cv2/CaptureDevice')
        self.cv2CapturePeriod = self.configData.get('/cv2/CapturePeriod')
        self.cv2CaptureWidth = self.configData.get('/cv2/CaptureWidth')
        self.cv2CaptureHeight = self.configData.get('/cv2/CaptureHeight')

    """------------------------------------------------------------------------
   gsatcomputerVisionThread: Main Window Event Handlers
   Handle events coming from main UI
   ------------------------------------------------------------------------"""

    def ProcessQueue(self):
        # process events from queue
        if not self.cvw2tQueue.empty():
            # get item from queue
            e = self.cvw2tQueue.get()

            if e.event_id == EV_CMD_CV_EXIT:
                if self.cmdLineOptions.vverbose:
                    print("** gsatcomputerVisionThread got event gEV_CMD_EXIT.")
                self.endThread = True

            # item acknowledge
            self.cvw2tQueue.task_done()

    """------------------------------------------------------------------------
   gsatcomputerVisionThread: General Functions
   -------------------------------------------------------------------------"""

    def CaptureFrame(self):
        retval, frame = self.captureDevice.read()

        if self.cmdLineOptions.vverbose:
            print("** gsatcomputerVisionThread Capture Frame.")

        # cv.ShowImage("Window",frame)
        if frame is not None:
            # offset = (0, 0)
            # width = self.cv2CaptureWidth
            # height = self.cv2CaptureHeight

            if self.cv2Crosshair:
                height, width = frame.shape[:2]
                widthHalf = int(width/2)
                heightHalf = int(height/2)
                self.cv2.line(frame, (widthHalf, 0), (widthHalf, height), 255)
                self.cv2.line(frame, (0, heightHalf), (width, heightHalf), 255)
                self.cv2.circle(frame, (widthHalf, heightHalf), 66, 255)
                self.cv2.circle(frame, (widthHalf, heightHalf), 22, 255)

            # offset = (0, 0)

            # color...
            frame = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)

            # # important cannot call any wx. UI functions from this thread
            # # bad things will happen
            # sizePanel = self.capturePanel.GetClientSize()
            # image = self.cv.CreateImage(sizePanel, frame.depth,
            #   frame.nChannels
            # )

            # self.cv.Resize(frame, image, self.cv.CV_INTER_NN)
            # self.cv.Resize(frame, image, self.cv.CV_INTER_LINEAR)
            # image = frame

            return frame

    def run(self):
        """
        Worker Thread.
        This is the code executing in the new thread context.
        """
        import cv2 as cv2

        self.cv2 = cv2

        # set up camera
        self.captureDevice = cv2.VideoCapture(self.cv2CaptureDevice)

        # let camera hardware settle
        time.sleep(1)

        # init sensor frame size
        try:
            # OpenCV 3
            self.captureDevice.set(self.cv2.CAP_PROP_FRAME_WIDTH, self.cv2CaptureWidth)
            self.captureDevice.set(self.cv2.CAP_PROP_FRAME_HEIGHT, self.cv2CaptureHeight)
        except AttributeError:
            # OpenCV 2
            self.captureDevice.set(self.cv2.cv.CV_CAP_PROP_FRAME_WIDTH, self.cv2CaptureWidth)
            self.captureDevice.set(self.cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, self.cv2CaptureHeight)

        # init before work loop
        self.endThread = False

        if self.cmdLineOptions.vverbose:
            print("** gsatcomputerVisionThread start.")

        while (not self.endThread):

            # capture frame
            frame = self.CaptureFrame()

            # send frame to window, and wait...
            self.t2cvwQueue.put(gc.SimpleEvent(EV_CMD_CV_IMAGE, frame))
            self.t2cvwQueue.join()

            # sleep for a period
            time.sleep(self.cv2CapturePeriod/1000)

            # process input queue for new commands or actions
            self.ProcessQueue()

            # self.cv2.imshow('frame', frame)

            # check if we need to exit now
            if self.endThread:
                break

        self.captureDevice.release()

        if self.cmdLineOptions.vverbose:
            print("** gsatcomputerVisionThread exit.")
