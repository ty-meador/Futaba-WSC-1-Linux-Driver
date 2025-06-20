import atexit

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

    def __init__(self, debug=False):
        super().__init__()

        self.fdm = FutabaDeviceManager()
        atexit.register(self.fdm.stopAll)
        futabaDevices = self.fdm.getDeviceList()

        self.selectionList = [
            Selection(f"{device['name']}", i) for i, device in enumerate(futabaDevices)
        ]

        if len(futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

    def compose(self):
        yield Header()
        with Horizontal():
            yield SelectionList(*[option for option in self.selectionList])
            yield Pretty([])
        yield Footer()

    def on_mount(self):  # noqa: C0103
        """on mount event callback"""
        self.query_one(SelectionList).border_title = "Futaba Driver Manager"
        self.query_one(Pretty).border_title = "Running Drivers"

    @on(Mount)
    @on(SelectionList.SelectedChanged)
    def update_selected_view(self):  # noqa: C0103
        """callback"""
        selected = self.query_one(SelectionList).selected

        for idx in selected:
            self.fdm.start(idx)

        self.query_one(Pretty).update(
            list(filter(lambda d: d["state"] == "RUNNING", self.fdm.getDeviceList()))
        )
