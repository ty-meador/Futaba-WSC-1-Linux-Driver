"""User interface module."""

# Allow dangling imports for re-export purposes
# ruff: noqa: F401
import curses

from .Window import Window, WindowCoords


class MainMenu(Window):
    """Draw the main deviceList."""

    def __init__(self, windowCoords, deviceList):
        """Create a MainMenu window object.

        Args:
            windowCoords (WindowCoords): The coordinate metadata for the window you want to render
            deviceList (iterable of str): The deviceList items to display

        """
        super().__init__(windowCoords)
        self.deviceList = deviceList
        self.title = "( Choose device to calibrate )"
        self.selected = 0

    def addItem(self, item):
        """Add an item to the main deviceList.

        Args:
            item (str): The item to add

        """
        self.deviceList.append(item)

    def getItem(self):
        """Get the item that is currently selected.

        Returns:
            str: The item that is currently selected

        """
        return self.deviceList[self.selected]

    def up(self):
        """Move the selection up one item."""
        if self.selected > 0:
            self.selected -= 1

    def down(self):
        """Move the selection down one item."""
        if self.selected < len(self.deviceList) - 1:
            self.selected += 1

    def _render(self):
        """Re-render the deviceList."""
        productName = None
        for i, device in enumerate(self.deviceList):
            productName = device["product"]
            xCoord = (self.width - len(productName)) // 2
            yCoord = self.contentY + i + 1
            if i == self.selected:
                self.window.addstr(
                    yCoord,
                    xCoord,
                    productName,
                    curses.A_REVERSE | curses.A_UNDERLINE,
                )
            else:
                self.window.addstr(
                    yCoord,
                    xCoord,
                    productName,
                )
