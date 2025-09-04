"""User interface module."""

# Allow dangling imports for re-export purposes
# ruff: noqa: F401
import curses
from dataclasses import dataclass

from .Window import Window, WindowCoords


@dataclass
class MenuItem:
    """Represents a single entry in a menu window."""

    text: str = None
    value: any = None


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
        self.title = "( Which receiver is your transmitter paired to? )"
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
            productName = device["productName"]
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


class Menu(Window):
    """Draw a menu."""

    def __init__(
        self,
        windowCoords: WindowCoords,
        menuItems: list[MenuItem] = None,
        title: str = "( Choose an option )",
    ):
        """Create a generic menu.

        Args:
            windowCoords (WindowCoords): The information for where and how the window should be
            displayed
            menuItems ([], optional): List of strings, each represening one item.
            title (str, optional): The title for the window. Defaults to "( Choose an option )".
        """
        super().__init__(windowCoords)
        if menuItems is None:
            menuItems = []

        self.menuItems = menuItems
        self.title = title
        self.selected = 0

    def addItem(self, item):
        """Add an item to the main deviceList.

        Args:
            item (str): The item to add

        """
        self.menuItems.append(item)

    def getItem(self):
        """Get the item that is currently selected.

        Returns:
            str: The item that is currently selected

        """
        return self.menuItems[self.selected["value"]]

    def up(self):
        """Move the selection up one item."""
        if self.selected > 0:
            self.selected -= 1

    def down(self):
        """Move the selection down one item."""
        if self.selected < len(self.menuItems) - 1:
            self.selected += 1

    def _render(self):
        """Re-render the deviceList."""
        for i, item in enumerate(self.menuItems):
            xCoord = (self.width - len(item)) // 2
            yCoord = self.contentY + i + 1
            if i == self.selected:
                self.window.addstr(
                    yCoord,
                    xCoord,
                    item,
                    curses.A_REVERSE | curses.A_UNDERLINE,
                )
            else:
                self.window.addstr(
                    yCoord,
                    xCoord,
                    item,
                )
