"""The main program - run with `sudo python3 main.py`"""

import atexit
import subprocess
import time

import usb
from textual import on
from textual.app import App
from textual.containers import Horizontal
from textual.events import Mount
from textual.widgets import Footer, Header, Pretty, SelectionList
from textual.widgets.selection_list import Selection

driverCmds = []


class DriverUI(App):
    """UI for managing the drivers built with textualize"""

    CSS_PATH = "selection_list.tcss"

    def __init__(self):
        super().__init__()
        self.futabaDevices = []
        atexit.register(self.stopAllDrivers)
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

    def on_mount(self):
        """on mount event callback"""
        self.query_one(
            SelectionList
        ).border_title = "Driver for Futaba R/C -> USB Receivers"
        self.query_one(Pretty).border_title = "Running Drivers"

    @on(Mount)
    @on(SelectionList.SelectedChanged)
    def update_selected_view(self):
        """callback"""
        selected = self.query_one(SelectionList).selected
        prettier = []
        for enum in selected:
            deviceIndex = int(enum)
            name = self.selectionENUM[enum]
            device = self.futabaDevices[deviceIndex]
            if device.subproc is None:
                subproc = self.startDriver(device)
                device.subproc = subproc
            prettier.append(f"{name}")

        # Kill drivers for deselected devices
        for device in self.futabaDevices:
            if device.enum[device.name] not in selected and device.subproc is not None:
                device.subproc.terminate()
                device.subproc.wait()
                device.subproc = None

        self.query_one(Pretty).update(prettier)

    def findFutabaDevices(self):
        """Finds all Futaba USB devices that are currently connected

        Returns:
            list of usb.core.Device: A list of Futaba usb device handles
        """
        devices = []
        for device in usb.core.find(find_all=True):
            if device.manufacturer.lower() == "futaba":
                devices.append(device)
        return devices

    def monitorDrivers(self, subprocs):
        """A blocking function that infinitely monitors the provided subprocesses until they all exit

        Args:
            subprocs (list of subprocess): A list of subprocesses
        """
        running = len(subprocs)
        while running > 0:
            running = 0
            stopped = 0
            time.sleep(1)
            for subproc in subprocs:
                if subproc.poll() is None:
                    running += 1
                else:
                    stopped += 1

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

    def stopAllDrivers(self):
        """Cleanup function to stop any running drivers"""
        deviceList = filter(
            lambda device: (hasattr(device, "subproc") and device.subproc is not None),
            self.futabaDevices,
        )

        for device in deviceList:
            # First send terminate signal to all running subprocs
            try:
                device.subproc.terminate()
            except Exception:
                pass

        for device in deviceList:
            # Next check each subproc and wait for it if it hasn't yet finished terminating
            try:
                device.subproc.wait()
                device.subproc = None
            except Exception:
                pass


if __name__ == "__main__":
    DriverUI().run()
