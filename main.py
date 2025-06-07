"""The main program - run with `sudo python3 main.py`"""

import subprocess
import time

import usb
from textual import on
from textual.app import App
from textual.containers import Horizontal
from textual.events import Mount
from textual.widgets import Footer, Header, Pretty, SelectionList
from textual.widgets.selection_list import Selection

import driver.utils as utils

driverCmds = []


class DriverUI(App):
    CSS_PATH = "ui/selection_list.tcss"

    def __init__(self):
        super().__init__()
        utils.configSanityCheck()
        self.futabaDevices = []
        self.options = []
        self.startCmds = []
        self.selectionENUM = {}
        self.subprocs = []

        for device in usb.core.find(find_all=True):
            if device.manufacturer.lower() != "futaba":
                continue
            name = f"{device.manufacturer} {device.product}"

            self.futabaDevices.append(device)
            self.startCmds.append(
                (
                    "python3",
                    "driver/start",
                    "--bus",
                    str(device.bus),
                    "--port",
                    str(device.port_number),
                )
            )
            nextValue = str(len(self.futabaDevices))
            self.options.append(Selection(name, nextValue))
            self.selectionENUM[name] = nextValue
            self.selectionENUM[nextValue] = name

        if len(self.futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

    def compose(self):
        yield Header()
        with Horizontal():
            yield SelectionList(*self.options)
            yield Pretty([])
        yield Footer()

    def on_mount(self):
        self.query_one(
            SelectionList
        ).border_title = "Driver for Futaba R/C -> USB Receivers"

    @on(Mount)
    @on(SelectionList.SelectedChanged)
    def update_selected_view(self):
        prettier = []
        selected = self.query_one(SelectionList).selected
        for num in selected:
            name = self.selectionENUM[str(num)]
            num = int(num)
            device = self.futabaDevices[num - 1]
            subprocs = self.startDrivers([device])
            for subproc in subprocs:
                self.subprocs.append(subproc)
                prettier.append(f"{name}({num}) -> running")
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


if __name__ == "__main__":
    DriverUI().run()
