"""The main program - run with `sudo python3 main.py`"""

import atexit
import subprocess

import usb
from textual import on
from textual.app import App
from textual.containers import Horizontal
from textual.events import Mount
from textual.widgets import Footer, Header, Pretty, SelectionList
from textual.widgets.selection_list import Selection

from driver import utils

driverCmds = []


class DriverUI(App):
    """UI for managing the drivers built with textualize"""

    CSS_PATH = "main.tcss"

    def __init__(self):
        super().__init__()
        self.futabaDevices = []
        atexit.register(self.stopAllDrivers)
        self.logger = utils.generateLogger()
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
            )
            device.selectItem = Selection(device.name, selectionKey)
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
        sList = []
        for device in self.futabaDevices:
            sList.append(device.selectItem)
        yield Header()
        with Horizontal():
            yield SelectionList(*sList)
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
            lambda device: device.enum[device.name] not in selected, self.futabaDevices
        )
        self.stopDrivers(deviceList)
        self.query_one(Pretty).update(prettier)

    def startDriver(self, futabaDevice):
        """start a single device"""
        return self.startDrivers([futabaDevice])[0]

    def startDrivers(self, futabaDevices):
        """Starts all Futaba devices provided

        Args:
            futabaDevices (list of usb.core.Device): A list of Futaba USB device handles

        Returns:
            list of subprocess: A list of subprocesses each of which is responsable for
            a single device driver
        """
        subprocs = []
        try:
            for device in futabaDevices:
                driverCmd = [
                    "python3",
                    "driver/start",
                    "--bus",
                    str(device.bus),
                    "--port",
                    str(device.port_number),
                ]
                subprocs.append(subprocess.Popen(driverCmd))
        except Exception as e:
            raise e
            # raise RuntimeError("Unable to start device drivers!") from e
        return subprocs

    def startAllDrivers(self):
        """Starts a driver for all found futaba devices"""
        return self.startDrivers(self.futabaDevices)

    def stopDriver(self, futabaDevice):
        """Stops a single device driver

        Args:
            futabaDevice (usb.core.Device): a futaba device
        """
        self.stopDriver([futabaDevice])

    def stopDrivers(self, futabaDevices):
        """Takes a list of futaba devices and stops any driver subprocesses that are attached to them

        Args:
            futabaDevices (list of usb.core.Device): List of Futaba devices
        """
        deviceList = filter(
            lambda device: hasattr(device, "subproc") and device.subproc is not None,
            futabaDevices,
        )

        # Request graceful termination of all subprocs
        for device in deviceList:
            try:
                device.subproc.terminate()
                device.subproc.wait()
                device.subproc = None
            except Exception as e:
                self.logger.warning(e)

    def stopAllDrivers(self):
        """Stops all running drivers"""
        return self.stopDrivers(self.futabaDevices)


if __name__ == "__main__":
    DriverUI().run()
