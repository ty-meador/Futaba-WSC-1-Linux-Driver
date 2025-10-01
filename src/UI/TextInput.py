import curses

from .Window import Window, WindowCoords


class TextInput(Window):
    def __init__(self, windowCoords: WindowCoords):
        """Init."""
        super().__init__(windowCoords)
        self.value = None

    def getValue(self):
        """Get input from the user and return it as a string."""
        self.render()
        self.value = str(self.window.getstr(self.contentX, self.contentY).decode(encoding="utf-8"))
        return self.value

    def _render(self) -> None:
        curses.echo()
