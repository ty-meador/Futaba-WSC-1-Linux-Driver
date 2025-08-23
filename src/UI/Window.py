"""Class representation of a window."""

import curses
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowCoords:
    """Store all the necessary coordinate metadata for a single window."""

    x: int
    y: int
    width: int
    height: int


class Window:
    """Represents a single window."""

    def __init__(self, windowCoords, title=None):
        """Create and render a window."""
        curses.curs_set(0)
        self.window = curses.newwin(
            windowCoords.height,
            windowCoords.width,
            windowCoords.y,
            windowCoords.x,
        )
        self.yMax, self.xMax = self.window.getmaxyx()
        self.x = windowCoords.x
        self.y = windowCoords.y
        self.title = title
        self.contentX = 1  # Account for border
        self.contentY = 1  # Account for border
        self.width = windowCoords.width
        self.height = windowCoords.height
        self.window.clear()
        self.window.border()
        self.touchline = self.window.touchline
        self.touchwin = self.window.touchwin
        self.clear = self.window.clear
        self.border = self.window.border
        self.nodelay = self.window.nodelay

    def getch(self):
        """Block waiting for an input from the user."""
        return self.window.getch()

    def render(self):
        """Clear the window and redraw it."""
        self._render()
        self.window.border()
        if self.title:
            self.window.addstr(
                0,
                ((self.width - len(self.title)) // 2),
                self.title,
            )
        self.window.refresh()

    def _render(self):
        """Render the window."""
        raise TypeError("Window._render must be implemented by subclasses")
