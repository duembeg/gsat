KivyMD gsatrc
====

gsat remote control (gsatrc) is a kivyMD Application that can be compiled into an android app, and it provides CNC pendant like controls.

Development Environment
---------------------
### gsatrc's dependencies are:
* [python 3.8](http://www.python.org/) or later.
* [kivy 2.3.0](http://https://kivy.org/)
* [kivyMD 1.3.0](https://github.com/kivymd/)

### OSes:
* [Ubuntu 20.04, 22.04](http://www.ubuntu.com/)
   * Installing dependencies:
   ```
    sudo apt install -y python3 python3-pip python3-venv git
    sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   ```
* [Ubuntu 18.04](http://www.ubuntu.com/)
   * Special Installing dependencies:
   ```
   sudo apt install python3.8 python3-pip python3.8-venv git
   sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   ```
* Optional to install on an android device
   ```
    sudo apt-get install -y adb android-sdk-platform-tools-common && sudo cp /lib/udev/rules.d/51-android.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger
   ```
    * more details... [permissions and udev rules](https://stackoverflow.com/questions/53887322/adb-devices-no-permissions-user-in-plugdev-group-are-your-udev-rules-wrong)

### Editors used for development.
* [Visual Studio Code] (https://code.visualstudio.com/)

### Building:
* For detail instructions see [kivy packing-android](https://kivy.org/doc/stable/guide/packaging-android.html)

### Quick instructions:
1) create venv and activate venv (use python3.8 for 18.04)
    ```
    python3 -m venv .venv
    source .venv/bin/activate
    ```
2) Install pip dependecies
    ```
    pip install -U pip
    pip install kivy kivymd buildozer Cython==0.29.33 setuptools
    ```
3) Build android app, install and run on device
    ```
    cd kivy-rc
    buildozer android debug deploy run logcat
    ```

Screen Shoots
------------
### Main window
![Main window, Linux](https://raw.githubusercontent.com/duembeg/gsat/be6c091cbb511c2a3d35844af2329be6711e3321/images/screenshoot/gsatrc-main-window.png "Main Window, Linux")

Changelog
---------
### 1.0
* Many UI updates and bug fixes.
<br/>Notes: When running on Linux all works well. For Android the socket might become stale an a reconnect maybe necessary; next version the plan to solve this is websockets and FastAPI. In here I already try all the tricks including keep alive at socket level and even ping/pong at app level... Still Android will disconnect eventually.

### 0.1
* Initial beta release.
