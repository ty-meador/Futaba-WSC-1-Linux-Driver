from enum import Enum
from multiprocessing.connection import Connection

import usb
from _typeshed import Incomplete

from . import DriverSubproc as DriverSubproc
from .__config__ import CALIBRATION_PATH as CALIBRATION_PATH
from .__config__ import CONFIG_PATH as CONFIG_PATH
from .__config__ import DEFAULT_CALIBRATION as DEFAULT_CALIBRATION
from .__config__ import DEFAULT_CONFIG as DEFAULT_CONFIG
from .__config__ import FUTABA_VENDOR_ID as FUTABA_VENDOR_ID
from .__config__ import DeviceConfig as DeviceConfig
from .InputChannel import InputChannel as InputChannel
from .IPC import WorkerControl as WorkerControl

class DriverState(Enum):
    RUNNING = ...
    STOPPED = ...
    SUSPENDED = ...
    INITIALIZING = ...

class FutabaDeviceDriver:
    def disableEcho(self) -> None: ...
    def enableEcho(self) -> None: ...
    state: Incomplete
    def getState(self) -> DriverState: ...
    subProc: Incomplete
    def start(self) -> DriverState: ...
    def stop(self) -> None: ...
    def suspend(self) -> None: ...
    def toggleEcho(self) -> None: ...
    endpoint: int | None
    logger: Incomplete
    workerCtl: WorkerControl
    channelEvents: tuple[str, ...]
    deadZone: int
    deviceUUID: str
    frameSize: int
    manufacturer: str
    name: str
    noiseFilter: int
    pipe: Connection
    product: str
    productID: int
    speed: int | None
    serialNumber: str
    deviceChannels: Incomplete
    def __init__(self, device: usb.core.Device) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    def __del__(self) -> None: ...
    @staticmethod
    def deviceIsSupported(coreDevice: usb.core.Device) -> bool: ...
