from dataclasses import dataclass, field
from pathlib import Path

from _typeshed import Incomplete

PWD: Incomplete
PROJECT_ROOT: Incomplete
PYPROJECT_PATH: Incomplete
toml_data: Incomplete
PYPROJECT = toml_data
DEFAULT_NOISE_FILTER: int
DEFAULT_DEADZONE: int
DEFAULT_DEVICE_MIN_VAL: int
DEFAULT_DEVICE_MID_VAL: int
DEFAULT_DEVICE_MAX_VAL: int
EVENT_MIN_VAL: int
EVENT_MID_VAL: int
EVENT_MAX_VAL: int
DEFAULT_INPUT_RANGE: tuple[int, ...]
DEFAULT_OUTPUT_RANGE: tuple[int, ...]
FUTABA_VENDOR_ID: int
HID_INTERFACE: int
INTERRUPT_ENDPOINT_ATTRIBUTE: int
LOGLEVEL: int
DRIVER_PATH: Path
CONFIG_PATH: Path
CALIBRATION_PATH: Path
LOG_PATH: Path
DEFAULT_CONFIG: Incomplete
DEFAULT_CALIBRATION: list[tuple[int, ...]]

@dataclass(frozen=True, slots=True)
class DeviceConfig:
    channelEvents: tuple[str, ...] = field(default_factory=Incomplete)
    deadZone: int = ...
    frameSize: int = field(default_factory=Incomplete)
    noiseFilter: int = ...
