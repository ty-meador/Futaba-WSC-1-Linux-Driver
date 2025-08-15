"""Module for cralibation UI components."""
## UI basic concept
# ST Left | ST Right
#
#       TURN
#       制██▋
# ──────人──────
#     ██速
#     BURN
#
# Brake | Throttle
##

from .Window import Window


class CalibrationWidget(Window):
    """Draw the status UI element."""

    def __init__(self, windowCoords):
        """Create a calibration feedback UI element."""
        super().__init__(windowCoords)
        self.barSegmentsRight = tuple(["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"])
        self.barSegmentsLeft = tuple(["▕", "🮇", "🮈", "▐", "🮉", "🮊", "🮋", "█"])
        self.throttlePos = 0
        self.steeringPos = 0
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

    def setBoth(self, steeringPos, throttlePos):
        """Update both the steering and throttle position in a single render.

        Args:
            steeringPos (int): The position of the steering
            throttlePos (int): The position of the throttle

        """
        self.steeringPos = steeringPos
        self.throttlePos = throttlePos
        self.render()

    def setThrottlePos(self, value):
        """Set the throttle position.

        Args:
            value (int): The current steering position

        """
        self.throttlePos = value - 2048
        self.render()

    def setSteeringPos(self, value):
        """Set the steering position.

        Args:
            value (int): The current steering position

        """
        self.steeringPos = -2048
        self.render()

    def _render(self):
        self.window.addstr(
            self.contentY,
            self.contentX,
            self._generateAxisBar(
                self.chi,  # control/precision
                self.length,
                self.steeringPos,
            ),
        )
        self.window.addstr(
            self.contentY + 1,
            self.contentX,
            self._generateCenterLine(
                self.hito,  # The human operator
                80,
            ),
        )
        self.window.addstr(
            self.contentY + 2,
            self.contentX,
            self._generateAxisBar(
                self.haya,  # speed/velocity
                self.length,
                self.throttlePos,
            ),
        )

    def _generateCenterLine(self, centerPiece, totalLength):
        """Generate the center line that aligns with other bars' centers.

        Args:
            centerPiece (str): The center piece content (e.g., "──────人──────")
            totalLength (int): Total width to match other bars

        Returns:
            str: Centered line of exactly totalLength characters

        """
        return self._positionAtCenter(totalLength, centerPiece)

    def _positionAtCenter(self, totalLength, content):
        """Center any content within the total length.

        This is the core centering function used by both bars and center line.
        """
        contentStart = (totalLength - len(content)) // 2
        leftPadding = " " * contentStart
        rightPadding = " " * (totalLength - contentStart - len(content))
        return leftPadding + content + rightPadding

    def _generateAxisBar(self, hito, totalLength, progress):
        """Generate a progress bar that grows outward from a centered segment.

        The center segment stays fixed at the center, and progress bars grow
        outward from it (left for negative progress, right for positive).
        """
        # Determine direction and absolute progress
        isLeftSide = progress < 0
        absProgress = abs(progress)

        # Create the progress bar characters
        segments = self.barSegmentsLeft if isLeftSide else self.barSegmentsRight

        # Calculate bar characters using your original logic
        stepsPerChar = len(segments)
        fullChars = absProgress // stepsPerChar
        remainder = absProgress % stepsPerChar

        # Build the bar
        fullBarChar = segments[-1]  # "█"
        fullBars = fullBarChar * fullChars

        partialBar = "" if remainder == 0 else segments[remainder - 1]

        # Combine segments based on direction (your original logic)
        barChars = partialBar + fullBars if isLeftSide else fullBars + partialBar

        # Now position everything with center segment truly centered
        return self._positionBarAroundCenter(totalLength, hito, barChars, isLeftSide)

    def _positionBarAroundCenter(self, totalLength, hito, barChars, isLeftSide):
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
