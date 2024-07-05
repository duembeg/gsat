gsat
====

gsat is a cross-platform GCODE debug/step and alignment tool for TinyG and Grbl like GCODE
interpreter. with features similar to software debugger. For example usage of breakpoints,
change program counter (position), stop and inspection/modification of machine variables, step,
run.

use case: The GCODE file is a drill program for a PCB, gsat will make it possible to set-up a
break point right before the tool plunge. At this point with the jogging controls it is possible
to lower the tool right before penetrating the surface to verify alignment is adequate. Once
this is verify and or adjusted, the program can continue.

Development Environment
---------------------
### gsat's dependencies are:
* [python 2.7](http://www.python.org/) or later.
* [pySerial](http://pyserial.sourceforge.net/).
* [wxPython 2.8](http://www.wxpython.org/) or later.
   * Note: Up to wxPython 3.0, 4.x and beyond has too many changes that makes code not backward compatible.

### Additional dependencies if enabling OpenCV
* [OpenCV](http://opencv.org/)
* [numpy](http://pypi.python.org/pypi/numpy/)

### Devices
* [grbl](https://github.com/grbl/grbl/wiki/) is a free, open source, high performance CNC milling controller that will run on a straight Arduino.
* [g2core](https://github.com/synthetos/g2/wiki/What-is-g2core) is a cross-platform ARM Port of the TinyG motion control system that runs on the Arduino Due and on Synthetos hardware.
* [TinyG](https://github.com/synthetos/TinyG/wiki/) is a 6 axis motion control system designed for high-performance on small to mid-sized machines.

### CNCs use for development
* [ShapeOko](http://www.shapeoko.com/) is a Open-Source desktop CNC machine.
* [Proxxon MF70](http://www.proxxon.com/en//micromot/27112.php?list) costume CNC conversion, there are multiple offerings.
* Other CNC machines that use the above devices.

### OSes:
* [Ubuntu 16.04, 18.04](http://www.ubuntu.com/)
   * Installing dependencies:
   ```
   sudo apt-get install python-wxgtk3.0 python-wxtools wx3.0-i18n python-pip python-serial
   ```
   * Optional dependencies for OpenCV
   ```
   sudo apt-get install python-numpy python-opencv
   ```

### Editors used for development.
* [Visual Studio Code] (https://code.visualstudio.com/)

Screen Shoots
------------
### Main window
####* Linux
![Main window, Linux](https://raw.githubusercontent.com/duembeg/gsat/1b337421251a26ed622ad3a76953097c447de375/images/screenshoot/main_window_linux.png "Main Window, Linux")

### Settings Dialog
![Settings Dialog](https://raw.githubusercontent.com/duembeg/gsat/1b337421251a26ed622ad3a76953097c447de375/images/screenshoot/settings_dialog.png "Settings Dialog")

Changelog
---------
### 1.7.0
* Remote Interface
   * All code necessary to run the machine is now GUI free and can run in a console.
   * All UI code can communicate via sockets to the machine interface.
      * This also allows for multiple UIs to communicate with a single machine interface.
   * Added new options "--server" when enabled the UI will use sockets to communicate to the machine interface, and other UIs can also attach to the running machine.
   * Added a new gsat-console.py app that will run in console mode (WIP) this is perfect tu run with --server option on a Raspberry PI or another computer close to the machine where a screen maybe not necessary.
   * Added a KivyMD APP that can compile into an android app and run in a phone or tablet and can communicate via sockets with the machine interface.


### 1.6.0
* Major rewrite for underlying "working threads" code
   * All machine interfaces are now separated in modules, each interface module can handle the specifics for that interface. For example encode/decode data, handle specific Jog, Hold, and Abort commands. Using Facade and Interface OOD patterns.
   * Better support for grbl (for example extra axes in stm32 grbl versions).
   * Better support for TinyG2 and g2core using JSON format to communicate with interface.
   * Removed any special knowledge of the UI, this way the underlying code can be used independently of UI.
   * Better handling of buffers per interface; for example slow down when buffer getting too full allowing specific interface to keep up.
* Many UI changes.
   * Updated icons and JOG panel, added hold and resume toolbar buttons. Added button for probing in JOG panel.
   * grbl and g2core when error are sent back, extra explanation of error code will be displayed.
   * Remove special interface knowledge making it easier to add other interfaces in the future (for example Marlin).
   * Fixed run timer, now it will stop when interface finishes and not immediately after sending last command to interface.
   * DRO can now add or remove axes, by default is X, Y, and Z, but can turn on/off X, Y, Z, A, B, and C.
   * Added JOG pendant support for numeric keypad like pendant. With interactive mode enable by default. In this mode a single click advances by step size, if key is held down the movement will be continuous until key is released.
* Many other bug fixes.

### 1.5.1
* Added Support for verbosity changes in TinyG2 latest master branch now known as g2core.
* Fixed bug on jogging UI; where an operation was selected without selecting an axis. This resulted on a serial write and wait for ack, since string was empty there will be no ack.


### 1.5.0
* Added support for [TinyG2](https://github.com/synthetos/g2/wiki).
* Added support for [Mac OS X Mavericks](https://www.apple.com/osx/) with working [OpenCV](http://opencv.org/).
* Added run time dialog at end of program run (configurable option).
* Added PAUSE state, tool-bar button and menu item, in pause state run time continues.
* Added machine setting for [Grbl](https://github.com/grbl/grbl/wiki/), [TinyG](https://github.com/synthetos/TinyG/wiki/), or [TinyG2](https://github.com/synthetos/g2/wiki/).
* Added machine setting for initialization script, useful to send setup commands after device connect detect.
* Added machine run time status.
* Added machine Auto Status request setting (mainly for Grbl not needed with TinyG(2)).
* Consolidated Link and Machine setting panels (require a one time reconfiguration of port and baud when upgrading from old version).
* Added jog settings to auto update from machine status.
* Added jog settings to auto request update from machine after jog set operation that don't normally generate verbose information, like set to zero or set to job values.
* Added jog custom button support for scripts.
* Removed second set of XYZ coordinates and enlarge the reminding for ease of view at a distance.
* Updated G-Code message dialog, it is now treated as entering PAUSE state (run time continues).
* Fixed bug with missing variable "serialBaud" not found when changing settings while serial port was open.
* Fixed bug with File->Open being enabled while RUN state was active.
* Fixed multiple UI issues with [Mac OS X](http://www.apple.com/osx/)
* Moved decode of status string processing to program exec thread, this will help UI from becoming temporarily unresponsive.


### 1.4.0
* Added support for [TinyG](https://github.com/synthetos/TinyG/wiki).
   * TODO: Create dedicated class/interfaces for TinyG and grbl, including settings dialog, status window, etc.
* Added support for [Mac OS X](http://www.apple.com/osx/), tested with [TinyG](https://github.com/synthetos/TinyG/wiki) and [Grbl](https://github.com/grbl/grbl/wiki/).
* Improved serial communication with dedicated serial RX thread.
* Improved serial exception handling.
* Updated G-Code message dialog, now one can continue from dialog.
* Added better acknowledge check for g-code commands.
* Added finer Jogging controls for each axis.
* Added link port, link baud, and percent of lines sent on status panel.

### 1.3.0
* Program/repo name change gcs to gsat (g-code step and alignment tool)
  to port your old config file just rename from .gcs to .gsat while gsat is not running.

### 1.2.0
* Added G-code message dialog (it is treated as break point, hit run after "ok" button)
* Added try/catch block for open serial port.
* Fix Save-As bug, document title was not updated.
* Fix make sure strings sent to pySerial are ascii and not Unicode.

### 1.1.0
* UI updates
   * Added Find and Goto Line controls to tool bar.
   * Added G-Code syntax highlighting.
   * Updated icons to more colorful versions.
   * Removed CLI panel, moved CLI into Jogging panel.
* Separated code into modules, for better maintainability and preparing for plug-in support.

### 1.0.0
* Initial Release
