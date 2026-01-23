# Type stubs for python-uinput
# python-uinput version: 0.11.2+
# This file is based on python-uinput API as of 2024
from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union

from typing_extensions import Self

# Exception classes
class UInputError(Exception): ...

# Device class
class Device:
    def __init__(
        self,
        events: List[Union[int, Tuple[int, int, int, int, int]]],
        name: str = "python-uinput",
        vendor: int = 0x1,
        product: int = 0x1,
        version: int = 0x1,
        bustype: int = 0x3,
        devnode: Optional[str] = None
    ) -> None: ...

    def emit(
        self,
        event: int,
        value: int,
        syn: bool = True
    ) -> None: ...

    def emit_click(self, button: int) -> None: ...
    def emit_combo(self, events: List[Tuple[int, int]]) -> None: ...

    def syn(self) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...

# Event type constants
EV_SYN: int
EV_KEY: int
EV_REL: int
EV_ABS: int
EV_MSC: int
EV_SW: int
EV_LED: int
EV_SND: int
EV_REP: int
EV_FF: int
EV_PWR: int
EV_FF_STATUS: int

# Synchronization events
SYN_REPORT: int
SYN_CONFIG: int
SYN_MT_REPORT: int
SYN_DROPPED: int

# Key events (buttons)
KEY_RESERVED: int
KEY_ESC: int
KEY_1: int
KEY_2: int
KEY_3: int
KEY_4: int
KEY_5: int
KEY_6: int
KEY_7: int
KEY_8: int
KEY_9: int
KEY_0: int
KEY_MINUS: int
KEY_EQUAL: int
KEY_BACKSPACE: int
KEY_TAB: int
KEY_Q: int
KEY_W: int
KEY_E: int
KEY_R: int
KEY_T: int
KEY_Y: int
KEY_U: int
KEY_I: int
KEY_O: int
KEY_P: int
KEY_LEFTBRACE: int
KEY_RIGHTBRACE: int
KEY_ENTER: int
KEY_LEFTCTRL: int
KEY_A: int
KEY_S: int
KEY_D: int
KEY_F: int
KEY_G: int
KEY_H: int
KEY_J: int
KEY_K: int
KEY_L: int
KEY_SEMICOLON: int
KEY_APOSTROPHE: int
KEY_GRAVE: int
KEY_LEFTSHIFT: int
KEY_BACKSLASH: int
KEY_Z: int
KEY_X: int
KEY_C: int
KEY_V: int
KEY_B: int
KEY_N: int
KEY_M: int
KEY_COMMA: int
KEY_DOT: int
KEY_SLASH: int
KEY_RIGHTSHIFT: int
KEY_KPASTERISK: int
KEY_LEFTALT: int
KEY_SPACE: int
KEY_CAPSLOCK: int
KEY_F1: int
KEY_F2: int
KEY_F3: int
KEY_F4: int
KEY_F5: int
KEY_F6: int
KEY_F7: int
KEY_F8: int
KEY_F9: int
KEY_F10: int
KEY_NUMLOCK: int
KEY_SCROLLLOCK: int
KEY_KP7: int
KEY_KP8: int
KEY_KP9: int
KEY_KPMINUS: int
KEY_KP4: int
KEY_KP5: int
KEY_KP6: int
KEY_KPPLUS: int
KEY_KP1: int
KEY_KP2: int
KEY_KP3: int
KEY_KP0: int
KEY_KPDOT: int
KEY_F11: int
KEY_F12: int
KEY_KPENTER: int
KEY_RIGHTCTRL: int
KEY_KPSLASH: int
KEY_SYSRQ: int
KEY_RIGHTALT: int
KEY_HOME: int
KEY_UP: int
KEY_PAGEUP: int
KEY_LEFT: int
KEY_RIGHT: int
KEY_END: int
KEY_DOWN: int
KEY_PAGEDOWN: int
KEY_INSERT: int
KEY_DELETE: int

# Mouse buttons
BTN_LEFT: int
BTN_RIGHT: int
BTN_MIDDLE: int
BTN_SIDE: int
BTN_EXTRA: int
BTN_FORWARD: int
BTN_BACK: int
BTN_TASK: int
BTN_TRIGGER: int
BTN_THUMB: int
BTN_THUMB2: int
BTN_TOP: int
BTN_TOP2: int
BTN_PINKIE: int
BTN_BASE: int
BTN_BASE2: int
BTN_BASE3: int
BTN_BASE4: int
BTN_BASE5: int
BTN_BASE6: int

# Gamepad buttons
BTN_A: int
BTN_B: int
BTN_C: int
BTN_X: int
BTN_Y: int
BTN_Z: int
BTN_TL: int
BTN_TR: int
BTN_TL2: int
BTN_TR2: int
BTN_SELECT: int
BTN_START: int
BTN_MODE: int
BTN_THUMBL: int
BTN_THUMBR: int

# Relative axes
REL_X: int
REL_Y: int
REL_Z: int
REL_RX: int
REL_RY: int
REL_RZ: int
REL_HWHEEL: int
REL_DIAL: int
REL_WHEEL: int
REL_MISC: int

# Absolute axes
ABS_X: int
ABS_Y: int
ABS_Z: int
ABS_RX: int
ABS_RY: int
ABS_RZ: int
ABS_THROTTLE: int
ABS_RUDDER: int
ABS_WHEEL: int
ABS_GAS: int
ABS_BRAKE: int
ABS_HAT0X: int
ABS_HAT0Y: int
ABS_HAT1X: int
ABS_HAT1Y: int
ABS_HAT2X: int
ABS_HAT2Y: int
ABS_HAT3X: int
ABS_HAT3Y: int
ABS_PRESSURE: int
ABS_DISTANCE: int
ABS_TILT_X: int
ABS_TILT_Y: int
ABS_TOOL_WIDTH: int
ABS_VOLUME: int
ABS_MISC: int

# Force feedback
FF_STATUS_STOPPED: int
FF_STATUS_PLAYING: int

# Miscellaneous events
MSC_SERIAL: int
MSC_PULSELED: int
MSC_GESTURE: int
MSC_RAW: int
MSC_SCAN: int

# Switch events
SW_LID: int
SW_TABLET_MODE: int
SW_HEADPHONE_INSERT: int
SW_RFKILL_ALL: int

# LED events
LED_NUML: int
LED_CAPSL: int
LED_SCROLLL: int

# Sound events
SND_CLICK: int
SND_BELL: int
SND_TONE: int

# Constants for device creation with tuples
# (event_code, min_value, max_value, fuzz, flat)
EventTuple = Tuple[int, int, int, int, int]
