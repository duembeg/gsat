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
* [python 2.7] (http://www.python.org)
* [pySerial 2.5](http://pyserial.sourceforge.net/)
* [wxPython 2.8](http://www.wxpython.org/)

### Additional dependencies if enabling Computer Vision
* [OpenCV 2.4.1] (http://opencv.org/)
* [numpy 1.6.1] (http://pypi.python.org/pypi/numpy)

### Devices
* [TinyG] (https://github.com/synthetos/TinyG/wiki) is a 6 axis motion control system designed for high-performance on small to mid-sized machines.
* [Grbl 0.8c] (https://github.com/grbl/grbl/wiki) is a free, open source, high performance CNC milling controller that will run on a straight Arduino.
* [ShapeOko] (http://www.shapeoko.com/) is a Open-Source desktop CNC machine. 

### OSes:
* [Ubuntu 12.04, 12.10, 13.04, 13.10 (32/64)] (http://www.ubuntu.com/)
 * Installing dependencies:  
  ```
  sudo apt-get install python-wxgtk2.8 python-wxtools wx2.8-i18n python-pip  
  ```  
  ```
  sudo pip install pyserial
  ```  
 * Optional for OpenCV  
    ```
    sudo apt-get install python-numpy python-opencv
    ```
* Windows 7 (32/64)
 * for installation instructions, follow the links above to download and install each dependency.

### Editors
* [Geany] (http://www.geany.org/)
* [Notepad ++] (http://notepad-plus-plus.org/)

Screen Shoots
------------
![Main window, stop on a breakpoint](https://raw.github.com/duembeg/gsat/a21778ddb4d0f7021cd4e60c6118173e7cea1d6c/images/screenshoot/main_window.png "Main window, stop on a breakpoint")
![Settings Dialog](https://raw.github.com/duembeg/gsat/v1.1.0/images/screenshoot/settings_dialog.png "Settings Dialog")
![About Dialog](https://raw.github.com/duembeg/gsat/a21778ddb4d0f7021cd4e60c6118173e7cea1d6c/images/screenshoot/about_box.png "About Dialog")

Changelog
---------
1.4.0
* Added TinyG support (text mode),
   * TODO: Create dedicated class/interfaces for TinyG and grbl, including settings dialog, status window, etc.
* Improved serial communication with dedicated serial RX thread.
* Improved serial exception handling.
* Updated G-Code message dialog, now one can continue from dialog.
* Added better acknowledge check for g-code commands.
* Added finer Jogging controls for each axis.
* Added link port, link baud, and percent of lines sent on status panel.

1.3.0
* Program/repo name change gcs to gsat (g-code step and alignment tool)  
  to port your old config file just rename from .gcs to .gsat while gsat is not running.

1.2.0
* Added G-code message dialog (it is treated as break point, hit run after "ok" button)
* Added try/catch block for open serial port.
* Fix Save-As bug, document title was not updated.
* Fix make sure strings sent to pySerial are ascii and not Unicode.

1.1.0
* UI updates
   * Added Find and Goto Line controls to tool bar.
   * Added G-Code syntax highlighting.
   * Updated icons to more colorful versions.
   * Removed CLI panel, moved CLI into Jogging panel.
* Separated code into modules, for better maintainability and preparing for plug-in support.

1.0.0
* Initial Release
