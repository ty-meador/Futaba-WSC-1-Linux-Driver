"""Contains atomic utility functions for the project."""

from dataclasses import dataclass, field
import json
import logging
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

DEFAULT_INPUT_RANGE: tuple[int, ...] = tuple([
    DEFAULT_DEVICE_MIN_VAL,
    DEFAULT_DEVICE_MID_VAL,
    DEFAULT_DEVICE_MAX_VAL,
])

DEFAULT_OUTPUT_RANGE: tuple[int, ...] = tuple([
    EVENT_MIN_VAL,
    EVENT_MID_VAL,
    EVENT_MAX_VAL,
])

FUTABA_VENDOR_ID: int = 4104  # 0x1008
HID_INTERFACE: int = 0x3  # conincidence
INTERRUPT_ENDPOINT_ATTRIBUTE: int = 0x3  # conincidence

LOGLEVEL: int = logging.DEBUG
DRIVER_PATH: Path = Path(__file__).resolve().parent
CONFIG_PATH: Path = DRIVER_PATH / "configs"
CALIBRATION_PATH: Path = DRIVER_PATH / "calibrations"
LOG_PATH: Path = DRIVER_PATH / "logs"

with open(CONFIG_PATH / "_default.json", encoding="utf-8") as f:
    DEFAULT_CONFIG = json.load(f)

DEFAULT_CALIBRATION: list[tuple[int, ...]] = [
    DEFAULT_INPUT_RANGE * len(DEFAULT_CONFIG["channel_events"])
]

if not LOG_PATH.exists():
    LOG_PATH.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class DeviceConfig:
    """Stores the configuration settings for a single device."""

    channelEvents: tuple[str, ...] = field(
        default_factory=lambda: tuple(DEFAULT_CONFIG["channel_events"])
    )
    deadZone: int = DEFAULT_DEADZONE
    frameSize: int = field(default_factory=lambda: DEFAULT_CONFIG["frame_size"])
    noiseFilter: int = DEFAULT_NOISE_FILTER
