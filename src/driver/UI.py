import atexit

from textual import on
from textual.app import App
from textual.containers import Horizontal
from textual.events import Mount
from textual.widgets import Button, Footer, Header, Pretty

import driver
from driver.Futaba import FutabaDeviceManager

driverCmds = []

PLAY_ICON = "⏵"
PAUSE_ICON = "⏸"
STOP_ICON = "⏹"


class DriverUI(App):
    """UI for managing the drivers built with textualize"""

    CSS_PATH = "styles/main.tcss"

    def __init__(self, debug=False):
        super().__init__()

        self.fdm = FutabaDeviceManager()

        atexit.register(self.fdm.stopAll)
        futabaDevices = self.fdm.listDevices()
        self.logger = driver.newLogger("text-ui")

        if len(futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

    def compose(self):
        yield Header()
        with Horizontal():
            for i, device in enumerate(self.fdm.listDevices()):
                yield Button(
                    label=f"{device['name']} "
                    f"{PLAY_ICON if device['state'] == 'IDLE' else STOP_ICON}",
                    variant="primary",
                    name=str(i),
                    id=f"BTN_{i}",
                )
            yield Pretty([])
        yield Footer()

    def on_mount(self):  # noqa: C0103
        """on mount event callback"""
        # self.query_one(SelectionList).border_title = "Futaba Driver Manager"
        self.query_one(Pretty).border_title = "Running Drivers"

    @on(Button.Pressed)
    def on_button_pressed(self, event):
        button = event.button
        idx = int(button.name)
        device = self.fdm.listDevices()[idx]

        result = self.fdm.start(device["key"])

        self.query_one(Pretty).update(result)

        if device["state"] == "IDLE":
            self.fdm.start(device["key"])
        elif device["state"] == "RUNNING":
            self.fdm.stop(device["key"])
        else:
            raise TypeError(f"Unknown driver state encountered: {device.state}")

        event.button.label = f"{device['name']} "
        f"{PLAY_ICON if device['state'] == 'RUNNING' else STOP_ICON}"

        self.query_one(Pretty).update(
            list(
                filter(
                    lambda d: d["state"] == "RUNNING", self.fdm.listDevices()
                )
            )
        )

    @on(Mount)
    def update_selected_view(self):  # noqa: C0103
        """callback"""

        self.query_one(Pretty).update(
            list(
                filter(
                    lambda d: d["state"] == "RUNNING", self.fdm.listDevices()
                )
            )
        )
