# gsat

gsat is a cross-platform GCODE debug/step and alignment tool for TinyG and Grbl-like GCODE interpreters. It features functionalities similar to software debuggers, such as breakpoints, program counter (position) changes, stopping, inspecting/modifying machine variables, stepping, and running.

## Use Case

For instance, if the GCODE file is a drill program for a PCB, gsat allows you to set a breakpoint right before the tool plunges. At this point, you can use jogging controls to lower the tool just before it penetrates the surface to verify alignment. Once verified or adjusted, the program can continue.

## Development Environment

### Dependencies

- **Python**: [Python 3.8](http://www.python.org/) or later
- **Serial Communication**: [pySerial](http://pyserial.sourceforge.net/)
- **GUI Library**: [wxPython 4.x](http://www.wxpython.org/) or later

### Optional Dependencies (for OpenCV)

- [OpenCV](http://opencv.org/)
- [numpy](http://pypi.python.org/pypi/numpy/)

### Supported Devices

- **grbl**: [Grbl](https://github.com/grbl/grbl/wiki/) - Open source, high-performance CNC milling controller for Arduino
- **g2core**: [g2core](https://github.com/synthetos/g2/wiki/What-is-g2core) - ARM Port of TinyG motion control system for Arduino Due and Synthetos hardware
- **TinyG**: [TinyG](https://github.com/synthetos/TinyG/wiki/) - 6-axis motion control system for small to mid-sized machines

### CNC Machines Used for Development

- **ShapeOko**: [ShapeOko](http://www.shapeoko.com/) - Open-source desktop CNC machine
- **Proxxon MF70**: [Proxxon MF70](http://www.proxxon.com/en//micromot/27112.php?list) - Custom CNC conversion
- Other CNC machines using the above devices

### Supported Operating Systems

#### Ubuntu 20.04, 22.04, 24.04

```bash
sudo apt install python3 python3-pip python3-venv git python3-dev
sudo apt install build-essential libgtk-3-dev
python3 -m pip install -U pip
python3 -m pip install pyserial
python3 -m pip install wxPython
```

*Optional dependencies for OpenCV*

```bash
python3 -m pip install numpy
python3 -m pip install opencv-python
```

#### Ubuntu 18.04

*Special installation for dependencies:*

```bash
sudo apt install python3.8 python3-pip python3.8-venv git python3.8-dev
sudo apt install build-essential libgtk-3-dev
python3.8 -m pip install -U pip
python3.8 -m pip install pyserial
python3.8 -m pip install wxPython
```

*Optional dependencies for OpenCV*

```bash
python3.8 -m pip install numpy
python3.8 -m pip install opencv-python
```

### Editors Used for Development

- [Visual Studio Code](https://code.visualstudio.com/)

## Screenshots

### Main Window (Linux)
![Main window, Linux](https://raw.githubusercontent.com/duembeg/gsat/1b337421251a26ed622ad3a76953097c447de375/images/screenshoot/main_window_linux.png "Main Window, Linux")

### Settings Dialog
![Settings Dialog](https://raw.githubusercontent.com/duembeg/gsat/1b337421251a26ed622ad3a76953097c447de375/images/screenshoot/settings_dialog.png "Settings Dialog")

## Changelog

### 1.7.5

- Python 3.x and wxPython 4.x Migration
  - Updated dependencies instructions
- Fix CV2 issues
- Update to UI for quality of life, DRO edits, and axis letters are now clickable
- Added `gsat-server.py` starts enough code to control the machine and server for remote UIs
- Moved probe settings to machine configuration. A UI can connect to multiple machines, making it illogical for the UI to have multiple settings for each machine. Remote UIs might not even have the ability to configure the machine itself.

### 1.7.0

- Remote Interface and Android Remote Pendant
  - All code necessary to run the machine is now GUI-free and can run in a console.
  - All UI code can communicate via sockets to the machine interface.
    - Allows multiple UIs to communicate with a single machine interface.
  - Added new options `--server` to enable the UI to use sockets to communicate with the machine interface. Other UIs can also attach to the running machine.
  - Added `gsat-console.py` app for console mode (WIP), ideal for running with the `--server` option on a Raspberry Pi or another computer without a screen.
  - Added a KivyMD app that can compile into an Android app and run on a phone or tablet, communicating via sockets with the machine interface.

### 1.6.0

- Major rewrite for underlying "working threads" code
  - Machine interfaces are now separated into modules, each handling specifics for the interface (e.g., encode/decode data, handle Jog, Hold, and Abort commands). Uses Facade and Interface OOD patterns.
  - Better support for grbl (e.g., extra axes in stm32 grbl versions).
  - Better support for TinyG2 and g2core using JSON format for communication.
  - Removed special knowledge of the UI, allowing underlying code to be used independently of UI.
  - Improved buffer handling per interface, slowing down when the buffer gets too full.
- Many UI changes
  - Updated icons and JOG panel, added hold and resume toolbar buttons, added probing button in JOG panel.
  - Grbl and g2core now provide extra explanations for error codes.
  - Removed special interface knowledge, making it easier to add new interfaces in the future (e.g., Marlin).
  - Fixed run timer, now stops when the interface finishes and not immediately after sending the last command.
  - DRO can now add/remove axes (default is X, Y, Z; can enable X, Y, Z, A, B, and C).
  - Added JOG pendant support for numeric keypad-like pendant, with interactive mode enabled by default (single click advances by step size, holding key results in continuous movement).
- Various bug fixes.

### 1.5.1

- Added support for verbosity changes in TinyG2 latest master branch, now known as g2core.
- Fixed bug in jogging UI where an operation was selected without selecting an axis, resulting in no serial write ack.

### 1.5.0

- Added support for [TinyG2](https://github.com/synthetos/g2/wiki).
- Added support for [Mac OS X Mavericks](https://www.apple.com/osx/) with working [OpenCV](http://opencv.org/).
- Added runtime dialog at the end of the program run (configurable option).
- Added PAUSE state, toolbar button, and menu item; in PAUSE state, run time continues.
- Added machine setting for [Grbl](https://github.com/grbl/grbl/wiki/), [TinyG](https://github.com/synthetos/TinyG/wiki/), or [TinyG2](https://github.com/synthetos/g2/wiki/).
- Added machine setting for initialization script, useful for sending setup commands after device connect detection.
- Added machine run time status.
- Added machine Auto Status request setting (mainly for Grbl, not needed with TinyG(2)).
- Consolidated Link and Machine setting panels (requires a one-time reconfiguration of port and baud when upgrading from old version).
- Added jog settings to auto-update from machine status.
- Added jog settings to auto-request updates from the machine after jog set operations that don't normally generate verbose information, like setting to zero or job values.
- Added jog custom button support for scripts.
- Removed second set of XYZ coordinates, enlarged the remaining for easier viewing from a distance.
- Updated G-Code message dialog; now treated as entering PAUSE state (run time continues).
- Fixed bug with missing variable "serialBaud" when changing settings while serial port was open.
- Fixed bug with File->Open being enabled during RUN state.
- Fixed multiple UI issues with [Mac OS X](http://www.apple.com/osx/).
- Moved decoding of status string processing to program exec thread, helping UI from becoming temporarily unresponsive.

### 1.4.0

- Added support for [TinyG](https://github.com/synthetos/TinyG/wiki).
  - TODO: Create dedicated classes/interfaces for TinyG and grbl, including settings dialog, status window, etc.
- Added support for [Mac OS X](http://www.apple.com/osx/), tested with [TinyG](https://github.com/synthetos/TinyG/wiki) and [Grbl](https://github.com/grbl/grbl/wiki/).
- Improved serial communication with a dedicated serial RX thread.
- Improved serial exception handling.
- Updated G-Code message dialog, allowing continuation from the dialog.
- Added better acknowledge check for G-code commands.
- Added finer Jogging controls for each axis.
- Added link port, link baud, and percentage of lines sent on the status panel.

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
