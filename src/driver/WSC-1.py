"""Class for the WSC-1 USB receiver

Raises:
    FileNotFoundError: Raised when calibrations/WSC-1.json does not exist
    FileNotFoundError: Raised when configs/WSC-1.json does not exist

Returns:
    FutabaUsbDevice: _description_
"""

import uinput
from FutabaUsbDevice import FutabaUsbDevice


class WSC_1(FutabaUsbDevice):
    """Class for WSC-1 USB adapter"""

    def __init__(self):
        super().__init__(
            productID=10,
            productName="WSC-1",
            channelEvents=[
                uinput.ABS_X,
                uinput.ABS_Y,
                uinput.ABS_RX,
                uinput.ABS_RY,
                uinput.ABS_THROTTLE,
                uinput.ABS_RUDDER,
                uinput.ABS_TILT_X,
                uinput.ABS_TILT_Y,
            ],
        )
