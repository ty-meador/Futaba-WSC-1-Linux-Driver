import atexit

import usb
from textual import on
from textual.app import App
from textual.containers import Horizontal
from textual.events import Mount
from textual.widgets import Footer, Header, Pretty, SelectionList
from textual.widgets.selection_list import Selection

from driver.Futaba import FutabaDeviceManager

driverCmds = []


class DriverUI(App):
    """UI for managing the drivers built with textualize"""

    CSS_PATH = "styles/main.tcss"

    def __init__(self):
        super().__init__()

        self.dManager = FutabaDeviceManager()
        atexit.register(self.dManager.stopAllDrivers)
        self.futabaDevices = []
        self.startCmds = []
        self.selectionENUM = {}

        deviceIndex = 0
        for device in usb.core.find(find_all=True):
            if device.manufacturer.lower() != "futaba":
                continue
            selectionKey = str(deviceIndex)
            device.name = f"{device.manufacturer} {device.product} (bus-{device.bus}, port-{device.port_number})"

            device.subproc = None
            device.startCmd = (
                "python3",
                "driver/start",
                "--bus",
                str(device.bus),
                "--port",
                str(device.port_number),
                "--use-name",
                device.name,
            )
            device.listOption = Selection(device.name, selectionKey)
            device.enum = {
                f"{device.name}": selectionKey,
                f"{selectionKey}": device.name,
            }
            self.selectionENUM.update(device.enum)
            self.futabaDevices.append(device)
            deviceIndex = len(self.futabaDevices)

        if len(self.futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

    def compose(self):
        yield Header()
        with Horizontal():
            yield SelectionList(*[device.listOption for device in self.futabaDevices])
            yield Pretty([])
        yield Footer()

    def on_mount(self):  # noqa: C0103
        """on mount event callback"""
        self.query_one(
            SelectionList
        ).border_title = "Driver for Futaba R/C -> USB Receivers"
        self.query_one(Pretty).border_title = "Running Drivers"

    @on(Mount)
    @on(SelectionList.SelectedChanged)
    def update_selected_view(self):  # noqa: C0103
        """callback"""
        selected = self.query_one(SelectionList).selected
        prettier = []
        for enum in selected:
            deviceIndex = int(enum)
            name = self.selectionENUM[enum]
            device = self.futabaDevices[deviceIndex]
            if not hasattr(device, "subproc") or device.subproc is None:
                subproc = self.startDriver(device)
                device.subproc = subproc
            prettier.append(f"{name}")

        # Kill drivers for deselected devices
        deviceList = filter(
            lambda device: device.enum[device.name] not in selected,
            self.futabaDevices,
        )
        self.stopDrivers(deviceList)
        self.query_one(Pretty).update(prettier)
