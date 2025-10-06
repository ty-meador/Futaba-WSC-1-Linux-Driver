"""Module for cralibation UI components."""

from .Window import Window, WindowCoords

MIN = -32768
MAX = 32767


## basic UI concept
# ST Left | ST Right
#
#       制 ███▌
# ──────人──────
#   ██ 速
#
# Brake | Throttle
##
class CalibrationUI(Window):
    """Draw the status UI element."""
    def __init__(self, windowCoords: WindowCoords, title: str):
        """Create a calibration feedback UI element."""
        super().__init__(windowCoords, title)
        self.barSegmentsRight = tuple(["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"])
        self.barSegmentsLeft = tuple(["▕", "🮇", "🮈", "▐", "🮉", "🮊", "🮋", "█"])
        self.steeringPos = 0
        self.throttlePos = 0
        self.knownChannels: dict[tuple[int, int], str] = {}
        self.throttleChannel = (3, 1)
        self.length = 80
        ##
        # WOAH! You found an easter egg!
        # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⣿⣿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⣤⠤⠀⠀⠤⣤⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⡆⠈⢠⣾⣷⡄⠁⢰⣿⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠠⠆⠈⠋⠀⠶⠄⠙⠋⠠⠶⠀⠙⠁⠰⠄⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⣴⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣦⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⡉⠹⣿⠏⠉⢿⡿⠉⠉⢿⡿⠉⠹⣿⠏⢉⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⢰⣿ ⠀   制 人 速     ⣿⡆⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⣿⣿⣦⣤⣼⣿⣤⣤⣾⣷⣤⣤⣿⣧⣤⣴⣿⣿⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠠⣤⣤⡤⠀⡀⠠⣤⣤⣤⣤⠄⢀⠀⢤⣤⣤⠄⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠹⠋⣤⣾⣿⣷⡌⠛⠛⢡⣾⣿⣷⣤⠙⠏⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠰⠶⣶⣶⣶⣶⣶⣶⣶⣶⠶⠆⠀⠀⠀⠀⠀⠀⠀⠀⠀
        # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠉⠉⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
        ##
        self.chi = " 制 "  # "control"
        self.hito = "──────人──────"  # "human/person" - the operator at the center of control
        self.haya = " 速 "  # "speed"

    def setBoth(self, steeringPos: int, throttlePos: int) -> None:
        """Update both the steering and throttle position in a single render.

        Args:
            steeringPos (int): The position of the steering
            throttlePos (int): The position of the throttle

        """
        self.steeringPos = steeringPos
        self.throttlePos = throttlePos
        self.render()

    def updateChannel(self, channel: tuple[int, int], calibV: int) -> None:
        """Update the UI display for the given channel.

        Args:
            channel (any): the channel to update
            calibV (int): the new value to use for the update
        """
        perc = calibV / MAX
        barLen = int(perc * self.length)

        if channel not in self.knownChannels:
            self.clear()

        self.knownChannels[channel] = self._generateAxisBar(
            self.haya if channel == self.throttleChannel else self.chi,
            self.length,
            -barLen if channel == self.throttleChannel else barLen,
        )

    def _render(self) -> None:
        vOffset = (self.height // 2) - (
            len(self.knownChannels) - 1  # Account for added hito decoration
        )
        controlChannels = filter(
            lambda channel: channel != self.throttleChannel, self.knownChannels
        )

        for channel in controlChannels:
            vOffset += 1
            self.window.addstr(
                self.contentY + vOffset,
                self.contentX,
                self.knownChannels[channel],
            )
        vOffset += 1
        self.window.addstr(
            self.contentY + vOffset,
            self.contentX,
            self._generateCenterLine(
                self.hito,  # The human operator
                self.length,
            ),
        )
        vOffset += 1
        if self.throttleChannel in self.knownChannels:
            self.window.addstr(
                self.contentY + vOffset,
                self.contentX,
                self.knownChannels[self.throttleChannel],
            )

    def _generateCenterLine(self, centerPiece: str, totalLength: int) -> str:
        """Generate the center line that aligns with other bars' centers.

        Args:
            centerPiece (str): The center piece content (e.g., "──────人──────")
            totalLength (int): Total width to match other bars

        Returns:
            str: Centered line of exactly totalLength characters

        """
        return self._positionAtCenter(totalLength, centerPiece)

    def _positionAtCenter(self, totalLength: int, content: str) -> str:
        """Center any content within the total length.

        This is the core centering function used by both bars and center line.
        """
        contentStart = (totalLength - len(content)) // 2
        leftPadding = " " * contentStart
        rightPadding = " " * (totalLength - contentStart - len(content))
        return leftPadding + content + rightPadding

    def _generateAxisBar(self, hito: str, totalLength: int, progress: int) -> str:
        """Generate a progress bar that grows outward from a centered segment.

        The center segment stays fixed at the center, and progress bars grow
        outward from it (left for negative progress, right for positive).
        """
        # Determine direction and progress
        isLeftSide = progress < 0
        absProgress = abs(progress)

        # Create the progress bar characters
        segments = self.barSegmentsLeft if isLeftSide else self.barSegmentsRight

        # Calculate bar characters
        stepsPerChar = len(segments)
        fullChars = absProgress // stepsPerChar
        remainder = absProgress % stepsPerChar

        # Build the bar
        fullBarChar = segments[-1]
        fullBars = fullBarChar * fullChars

        partialBar = "" if remainder == 0 else segments[remainder - 1]

        # Combine segments based on direction
        barChars = partialBar + fullBars if isLeftSide else fullBars + partialBar

        # Now position everything with center segment truly centered
        return self._positionBarAroundCenter(totalLength, hito, barChars, isLeftSide)

    def _positionBarAroundCenter(
        self,
        totalLength: int,
        hito: str,
        barChars: str,
        isLeftSide: bool,
    ) -> str:
        """Position the bar and center segment with center segment truly centered."""
        # Calculate where center segment should start to be truly centered
        centerSegmentStart = (totalLength - len(hito)) // 2

        # Calculate available space on each side
        leftSpace = centerSegmentStart
        rightSpace = totalLength - centerSegmentStart - len(hito)

        if isLeftSide:
            # Bar grows to the left of center segment
            if len(barChars) <= leftSpace:
                # Bar fits in available left space
                leftPadding = " " * (leftSpace - len(barChars))
                leftContent = leftPadding + barChars
            else:
                # Bar exceeds available space - truncate
                leftContent = barChars[-leftSpace:]
            rightContent = " " * rightSpace
        else:
            # Bar grows to the right of center segment
            leftContent = " " * leftSpace
            if len(barChars) <= rightSpace:
                # Bar fits in available right space
                rightPadding = " " * (rightSpace - len(barChars))
                rightContent = barChars + rightPadding
            else:
                # Bar exceeds available space - truncate
                rightContent = barChars[:rightSpace]

        return leftContent + hito + rightContent
