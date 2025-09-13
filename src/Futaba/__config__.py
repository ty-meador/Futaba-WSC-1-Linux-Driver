"""Contains atomic utility functions for the project."""

import json
import logging
import os
from pathlib import Path

import tomllib

# Project structure
PWD = Path(__file__).parent.resolve()
PROJECT_ROOT = PWD.parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

# Load project configuration
with open(PYPROJECT_PATH, "rb") as f:
    toml_data = tomllib.load(f)
PYPROJECT = toml_data

##
# If you have an aging device, these values may need to be increased.
##
# You may want to increase this value if:
# - You are experiencing "cross talk" between channels
# - A channel is drifting/hovering around a static input
DEFAULT_NOISE_FILTER: int = 0
# You may want to increase this value if:
# - Your inputs have any "joystick drift"
# - Leaving the neutral position is too sensitive
DEFAULT_DEADZONE: int = 0

DEFAULT_DEVICE_MIN_VAL: int = 608
DEFAULT_DEVICE_MID_VAL: int = 2048
DEFAULT_DEVICE_MAX_VAL: int = 3388
EVENT_MIN_VAL: int = -32768
EVENT_MID_VAL: int = 0
EVENT_MAX_VAL: int = 32767

DEFAULT_INPUT_RANGE: tuple[int, int, int] = tuple([
    DEFAULT_DEVICE_MIN_VAL,
    DEFAULT_DEVICE_MID_VAL,
    DEFAULT_DEVICE_MAX_VAL,
])

DEFAULT_OUTPUT_RANGE: tuple[int, int, int] = tuple([
    EVENT_MIN_VAL,
    EVENT_MID_VAL,
    EVENT_MAX_VAL,
])

FUTABA_VENDOR_ID: int = 4104  # 0x1008
HID_INTERFACE: hex = 0x3  # conincidence
INTERRUPT_ENDPOINT_ATTRIBUTE: hex = 0x3  # conincidence

LOGLEVEL: int = logging.DEBUG
DRIVER_PATH: Path = Path(__file__).resolve().parent
CONFIG_PATH: Path = DRIVER_PATH / "configs"
CALIBRATION_PATH: Path = DRIVER_PATH / "calibrations"
LOG_PATH: Path = DRIVER_PATH / "logs"

with open(CONFIG_PATH / "_default.json", encoding="utf-8") as f:
    DEFAULT_CONFIG: dict = json.load(f)

DEFAULT_CALIBRATION: list = [DEFAULT_INPUT_RANGE * len(DEFAULT_CONFIG["channel_events"])]

if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)
