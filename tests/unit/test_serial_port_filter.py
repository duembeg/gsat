"""Machine serial list filter (path-shape; same rules local + remote)."""

from modules.pyside_workbench.settings_dialog import MachinePage


def test_windows_com_allowed():
    assert MachinePage._serial_device_allowed("COM3")
    assert MachinePage._serial_device_allowed("com12")


def test_linux_usb_acm_allowed():
    assert MachinePage._serial_device_allowed("/dev/ttyUSB0")
    assert MachinePage._serial_device_allowed("/dev/ttyACM1")


def test_macos_cu_allowed():
    assert MachinePage._serial_device_allowed("/dev/cu.usbmodem14201")
    assert MachinePage._serial_device_allowed("/dev/cu.usbserial-A")


def test_ttys_and_bluetooth_dropped():
    assert not MachinePage._serial_device_allowed("/dev/ttyS0")
    assert not MachinePage._serial_device_allowed("/dev/tty.Bluetooth-Incoming-Port")


def test_none_placeholder_kept():
    assert MachinePage._serial_device_allowed("None")
    assert MachinePage._serial_device_allowed("")


def test_port_device_only_strips_description():
    assert MachinePage._port_device_only("/dev/ttyUSB0, Fake CNC") == "/dev/ttyUSB0"
    assert MachinePage._port_device_only("COM7") == "COM7"
