"""Contains atomic utility functions for the project."""

import logging
import os
from logging import handlers
from pathlib import Path

DEFAULT_LOG_HANDLER: logging.handlers.RotatingFileHandler = handlers.RotatingFileHandler(
    "logs.txt",
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)

##
# Futaba makes prescision electronics. However, if you have an aging device, these values may need
# to be increased.
##

# You may want to increase this value if:
# - You are experiencing "cross talk" between channels
# - A channel is drifting/hovering around a static input
DEFAULT_NOISE_FILTER: int = 0
# You may want to increase this value if:
# - Your inputs have any "joystick drift"
# - Leaving the neutral position is too sensitive
DEFAULT_DEADZONE: int = 0

##
# Credit to https://github.com/shaozu/Futaba_T16IZ_Linux/blob/main/entry.py
# for this great starting point!
##
DEFAULT_DEVICE_MIN_VAL: int = 704
DEFAULT_DEVICE_MID_VAL: int = 2048
DEFAULT_DEVICE_MAX_VAL: int = 3392
EVENT_MIN_VAL: int = -32768
EVENT_MID_VAL: int = 0
EVENT_MAX_VAL: int = 32767
DEFAULT_INPUT_RANGE: tuple[int, int, int] = tuple(
    [
        DEFAULT_DEVICE_MIN_VAL,
        DEFAULT_DEVICE_MID_VAL,
        DEFAULT_DEVICE_MAX_VAL,
    ]
)
DEFAULT_OUTPUT_RANGE: tuple[int, int, int] = tuple(
    [
        EVENT_MIN_VAL,
        EVENT_MID_VAL,
        EVENT_MAX_VAL,
    ]
)

FUTABA_VENDOR_ID: int = 4104  # 0x1008
HID_INTERFACE: hex = 0x3  # conincidence
INTERRUPT_ENDPOINT_ATTRIBUTE: hex = 0x3  # conincidence


DEFAULT_CONFIG: dict = {
    "frame_size": 16,
    "channel_events": [
        "ABS_X",
        "ABS_Y",
        "ABS_RX",
        "ABS_RY",
        "ABS_THROTTLE",
        "ABS_RUDDER",
        "ABS_TILT_X",
        "ABS_TILT_Y",
    ],
}

DEFAULT_CALIBRATION: list = [DEFAULT_INPUT_RANGE * len(DEFAULT_CONFIG["channel_events"])]

PRODUCTS: dict = {
    "default": 1948,  # 🥚
    "WSC-1": 10,
    "T16IZ": 11,
    10: "WSC-1",
    11: "T16IZ",
    1948: "default",
}


LOGLEVEL: int = logging.DEBUG
DEFAULT_LOG_HANDLER.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
DEFAULT_LOGGER: logging.Logger = logging.getLogger("driver")
DEFAULT_LOGGER.setLevel(LOGLEVEL)
DEFAULT_LOGGER.addHandler(DEFAULT_LOG_HANDLER)

DRIVER_PATH: str = Path(__file__).resolve().parent  # Using resolve to get an absolute path.
CONFIG_PATH: str = os.path.join(DRIVER_PATH, "configs")
CALIBRATION_PATH: str = os.path.join(DRIVER_PATH, "calibrations")
LOG_PATH: str = os.path.join(DRIVER_PATH, "logs")
if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)
