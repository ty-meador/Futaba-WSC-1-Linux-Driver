"""User interface module."""

# Allow dangling imports for re-export purposes
# ruff: noqa: F401
import curses
from dataclasses import dataclass
import typing
from .Window import Window, WindowCoords


@dataclass(frozen=True)
class MenuItem:
    """Represents a single entry in a menu window."""

    text: str
    value: typing.Any


class Menu(Window):
    """Draw the main options."""
    def __init__(self, windowCoords: WindowCoords, options: list[MenuItem]):
        """Create a MainMenu window object.

        Args:
            windowCoords (WindowCoords): The coordinate metadata for the window you want to render
            options (iterable of str): The options items to display

        """
        super().__init__(windowCoords)
        self.options = options
        self.title = "( Which receiver is your transmitter paired to? )"
        self.selected = 0

    def addItem(self, item: MenuItem):
        """Add an item to the main options.

        Args:
            item (any): The item to add

        """
        self.options.append(item)

    def getItem(self):
        """Get the item that is currently selected.

        Returns:
            str: The item that is currently selected

        """
        return self.options[self.selected].value

    def up(self):
        """Move the selection up one item."""
        if self.selected > 0:
            self.selected -= 1

    def down(self):
        """Move the selection down one item."""
        if self.selected < len(self.options) - 1:
            self.selected += 1

    def _render(self):
        """Re-render the options."""
        for i, option in enumerate(self.options):
            xCoord = (self.width - len(option.text)) // 2
            yCoord = self.contentY + i + 1
            if i == self.selected:
                self.window.addstr(
                    yCoord,
                    xCoord,
                    option.text,
                    curses.A_REVERSE | curses.A_UNDERLINE,
                )
            else:
                self.window.addstr(
                    yCoord,
                    xCoord,
                    option.text,
                )
