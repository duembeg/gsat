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

### Additional dependencies if enabling OpenCV
* [OpenCV](http://opencv.org/)
* [numpy](http://pypi.python.org/pypi/numpy/)

### Devices
* [TinyG](https://github.com/synthetos/TinyG/wiki/) is a 6 axis motion control system designed for high-performance on small to mid-sized machines.
* [TinyG2](https://github.com/synthetos/g2/wiki/) is a cross-platform ARM Port of the TinyG motion control system that runs on the Arduino Due and on Synthetos hardware.
* [Grbl](https://github.com/grbl/grbl/wiki/) is a free, open source, high performance CNC milling controller that will run on a straight Arduino.

### CNCs use for development
* [ShapeOko](http://www.shapeoko.com/) is a Open-Source desktop CNC machine.
* [Proxxon MF70](http://www.proxxon.com/en//micromot/27112.php?list) costume CNC conversion, there are multiple offerings.
* Other CNC machines that use the above devices.

### OSes:
* [Ubuntu 12.04, 12.10, 13.04, 13.10, 14.04](http://www.ubuntu.com/)
   * Installing dependencies:
   ```
   sudo apt-get install python-wxgtk2.8 python-wxtools wx2.8-i18n python-pip
   sudo pip install pyserial
   ```
   * Optional dependecies for OpenCV
   ```
   sudo apt-get install python-numpy python-opencv
   ```

* [Mac OS X](http://www.apple.com/osx/)
   * Install python following the instructions at [python-guide.org](http://docs.python-guide.org/en/latest/starting/install/osx/)
      * After installing python install pySerial
      ```
      pip install pyserial
      ```
   * Install wxPython following the instructions at [wxPython](http://www.wxpython.org/)
   * Optional dependecies for OpenCV
   ```
   brew install numpy
   brew tap homebrew/science
   brew install opencv
   ```

* [Windows 7](http://windows.microsoft.com/)
   * Install python following the instructions at [python.org](https://www.python.org/)
   * install pip following instructions at [pip.pypa.io](https://pip.pypa.io/en/latest/installing.html)
      * After installing pip install pySerial
      ```
      pip install pyserial
      ```
   * Install wxPython following the instructions at [wxPython](http://www.wxpython.org/)
   * Optional dependencies for [OpenCV](http://opencv.org/)
      * Install OpenCV follow instructions at [OpenCV windows install](http://docs.opencv.org/trunk/doc/py_tutorials/py_setup/py_setup_in_windows/py_setup_in_windows.html)

### Editors used for development.
* [Geany] (http://www.geany.org/)
* [Notepad ++] (http://notepad-plus-plus.org/)

Screen Shoots
------------
### Main window, stop on a breakpoint
![Main window, stop on a breakpoint](https://raw.github.com/duembeg/gsat/e07a7dc340ce89724829ca0b7d68cef213c7719a/images/screenshoot/main_window.png "Main Window, stop on a MSG")

### Settings Dialog
![Settings Dialog](https://raw.github.com/duembeg/gsat/e07a7dc340ce89724829ca0b7d68cef213c7719a/images/screenshoot/settings_dialog.png "Settings Dialog")

### About Dialog
![About Dialog](https://raw.github.com/duembeg/gsat/a21778ddb4d0f7021cd4e60c6118173e7cea1d6c/images/screenshoot/about_box.png "About Dialog")

Changelog
---------
### 1.5.0
* Added support for [TinyG2](https://github.com/synthetos/g2/wiki).
* Added support for [Mac OS X Mavericks](https://www.apple.com/osx/) with working [OpenCV](http://opencv.org/).
* Added PAUSE state, tool-bar button and menu item, in pause state run time continues.
* Added machine setting for [Grbl](https://github.com/grbl/grbl/wiki/), [TinyG](https://github.com/synthetos/TinyG/wiki/), or [TinyG2](https://github.com/synthetos/g2/wiki/).
* Added machine setting for initialization script, useful to send setup commands after device connect detect.
* Added machine runt time status.
* Added machine Auto Status request setting (mainly for Grbl not needed with TinyG(2)).
* Consolidated Link and Machine setting panels, this means that port and baud will have to be re-set after first upgrade to this version.
* Added jog settings to auto update from machine status.
* Added jog settings to auto request update from machine after jog set operation that don't normally generate verbose information, like set to zero or set to job values.
* Removed second set of XYZ coordinates and enlarge the reminding for ease of view at a distance.
* Updated G-Code message dialog, it is now treated as entering PAUSE state.
* Fixed bug with missing variable "serialBaud" not found when changing settings while serial port was open.
* Fixed multiple UI issues with [Mac OS X](http://www.apple.com/osx/)


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
