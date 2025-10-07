"""Driver for Futaba RC USB devices."""

import atexit
from enum import auto, Enum
import multiprocessing
from multiprocessing.connection import Connection
import os
from typing import Any
import usb

from . import Util as utils
from . import Worker
from .__config__ import (
    CALIBRATION_PATH,
    CONFIG_PATH,
    DEFAULT_CALIBRATION,
    DEFAULT_CONFIG,
    FUTABA_VENDOR_ID,
    DeviceConfig,
)
from .InputChannel import InputChannel, ChannelDict
from .IPC import WorkerControl


class DriverState(Enum):
    """Stores the state of a single device."""

    RUNNING = auto()
    STOPPED = auto()
    SUSPENDED = auto()
    INITIALIZING = auto()


class FutabaDeviceDriver:
    """Provides a class based interface for a single Futaba USB device."""
    def disableEcho(self):
        """Disable input echoing."""
        if self.workerCtl.echoFlag.is_set():
            self.workerCtl.echoFlag.clear()

    def enableEcho(self):
        """Enable input echoing."""
        if not self.workerCtl.echoFlag.is_set():
            self.workerCtl.echoFlag.set()

    def getState(self) -> DriverState:
        """Get the current state of the driver.

        Returns:
            DriverState: The current state of the driver.

        """
        # Refresh state before returning it
        if self.subProc is not None and self.subProc.is_alive():
            if self.workerCtl.runFlag.is_set():
                self.state = DriverState.RUNNING
            else:
                self.state = DriverState.SUSPENDED
        else:
            self.state = DriverState.STOPPED
        return self.state

    def start(self) -> DriverState:
        """Start the driver if it is not running."""
        if self.getState() == DriverState.RUNNING:
            return self.getState()

        if self.workerCtl.killswitch.is_set():
            self.workerCtl.killswitch.clear()
            self.logger.debug("-> killswitch cleared")
        if not self.workerCtl.runFlag.is_set():
            self.workerCtl.runFlag.set()
            self.logger.debug("-> runFlag set")

        self.subProc = multiprocessing.Process(
            name=f"{self.name} Driver",
            target=Worker.run,
            args=self._toSubprocTuple(),
        )

        self.subProc.start()

        return self.getState()

    def stop(self) -> None:
        """Stop the driver and kill the subprocess."""
        # It's possible for the constructor to fail before one or any of these are instantiated
        if (
            hasattr(self, "workerCtl") and hasattr(self.workerCtl, "killswitch")
            and not self.workerCtl.killswitch.is_set()
        ):
            self.workerCtl.killswitch.set()
        # Give the worker up to 1 second to shut down gracefully
        if hasattr(self, "subProc") and self.subProc is not None and self.subProc.is_alive():
            self.subProc.join(timeout=1.0)
        # Force shutdown
        if hasattr(self, "subProc") and self.subProc is not None and self.subProc.is_alive():
            self.subProc.terminate()
            self.subProc.join()
        self.subProc = None

    def suspend(self) -> None:
        """Suspend the driver without killing the subprocess."""
        if self.workerCtl.runFlag.is_set():
            self.workerCtl.runFlag.clear()

    def toggleEcho(
        self,
    ):
        """Toggle echo on or off."""
        if self.workerCtl.echoFlag.is_set():
            self.disableEcho()
        else:
            self.enableEcho()

    def _loadConfig(self, productName: str) -> dict[str, Any]:
        """Load the device config.

        Load the device config and fall back to the default config file if one doesn't exist.

        Args:
            productName (str): The name of the product to load the config for.

        Returns:
            dict: A dictionary containing the driver settings

        """
        config = None

        filePath = os.path.join(CONFIG_PATH, f"_{productName}.json")
        defaultPath = os.path.join(CONFIG_PATH, "_default.json")

        self.logger.debug("loading %s", filePath)
        config = utils.parseJsonFile(filePath)

        if config is None:
            self.logger.debug("device config not found, loading %s", defaultPath)
            config = utils.parseJsonFile(defaultPath)
        if config is None:
            self.logger.debug("using hard-coded defaults")
            config = DEFAULT_CONFIG

        self.logger.debug("config=%s", config)
        return config

    def _loadCalibration(self, productName: str, deviceUUID: str) -> list[tuple[int, ...]]:
        """Load the calibration file for the given product.

        Args:
            productName (str): The name of the product to load the
            calibration for. Defaults to None.

        Returns:
            list of list: Each inner list will contain calibration data for a channel.

        """
        filePath = os.path.join(CALIBRATION_PATH, f"{productName}_{deviceUUID}.json")
        defaultProductPath = os.path.join(CALIBRATION_PATH, f"_{productName}.json")
        defaultPath = os.path.join(CALIBRATION_PATH, "_default.json")

        # Load custom calibration if it exists
        self.logger.debug("loading %s", filePath)
        channelCalibrations = utils.parseJsonFile(filePath)

        # If that fails, load the default calibration file for this product
        if channelCalibrations is None:
            self.logger.debug("loading %s", defaultProductPath)
            channelCalibrations = utils.parseJsonFile(defaultProductPath)

        # If that fails, load the global default config file
        if channelCalibrations is None:
            self.logger.debug("loading %s", defaultPath)
            channelCalibrations = utils.parseJsonFile(defaultPath)

        # If that fails, use the hard-coded values
        if channelCalibrations is None:
            self.logger.debug("using hard-coded defaults")
            channelCalibrations = DEFAULT_CALIBRATION

        self.logger.debug("channelCalibrations=%s", channelCalibrations)
        return channelCalibrations

    def _toSubprocTuple(
        self,
    ) -> tuple[WorkerControl, DeviceConfig, tuple[ChannelDict, ...], str, int | None]:
        """Create a tuple that is compatable with the worker function.

        Returns:
            tuple: The tuple that you will pass to the worker function

        """

        return (
            self.workerCtl,
            DeviceConfig(
                channelEvents=self.channelEvents,
                deadZone=self.deadZone,
                frameSize=self.frameSize,
                noiseFilter=self.noiseFilter,
            ),
            tuple([channel.toDict() for channel in self.deviceChannels]),
            self.name,
            self.endpoint,
        )

    def __init__(self, device: usb.core.Device) -> None:
        """Create an object that drives a single device on it's own process.

        Args:
            device (usb.core.usb.core.Device): The device you want to spawn a driver for

        Raises:
            TypeError: If device is not of type usb.core.usb.core.Device

        """
        ##
        # meta-stuff
        ##
        self.state: DriverState = DriverState.INITIALIZING
        self.endpoint: int | None = utils.findInterruptEndpoint(device)
        if self.endpoint is None:
            raise TypeError("Unable to find interrupt endpoint for device")

        self.logger = utils.newLogger(f"{device.product}_driver")
        ##
        # Worker subproc stuff
        ##
        self.subProc: multiprocessing.Process | None = None
        self._frontPipe, self._backPipe = multiprocessing.Pipe()
        self.workerCtl: WorkerControl = WorkerControl(pipe=self._backPipe)

        ##
        # Device stuff
        ##
        config = self._loadConfig(device.product)
        self.channelEvents: tuple[str, ...] = tuple(config["channel_events"])
        self.deadZone: int = config["dead_zone"]
        self.deviceUUID: str = f"{device.idProduct:04X}-{device.serial_number}"
        self.frameSize: int = config["frame_size"]
        self.manufacturer: str = device.manufacturer
        self.name: str = f"Futaba {device.product}({self.endpoint})"
        self.noiseFilter: int = config["noise_filter"]
        self.pipe: Connection = self._frontPipe
        self.product: str = device.product
        self.productID: int = device.idProduct
        self.speed: int | None = device.speed
        self.serialNumber: str = device.serial_number

        self.deviceChannels = (
            InputChannel(eventName, calibration, False, logger=self.logger)
            for eventName, calibration in zip(
                config["channel_events"],
                self._loadCalibration(self.product, self.deviceUUID),
                strict=True,  # 1 event name and 1 calibration per channel
            )
        )

        atexit.register(self.stop)

    def __eq__(self, other: object) -> bool:
        """Compare instances based on what USB endpoint they are using.

        Args:
            other (object): The device to compare to

        Returns:
            bool: True if the devices have the same interrupt endpoint address

        """
        return isinstance(other, FutabaDeviceDriver) and self.endpoint == other.endpoint

    def __hash__(self) -> int:
        """Generate a has for this object.

        Returns:
            hash: The hash.

        """
        return hash(self.endpoint)

    def __str__(self) -> str:
        """Generate a string representation of this device driver."""
        return f"{self.name} Driver({self.deviceUUID})"

    def __del__(self) -> None:
        """Destructor."""
        self.stop()

    @staticmethod
    def deviceIsSupported(coreDevice: usb.core.Device) -> bool:
        """Determine if the device is compatable with this driver class.

        Determine if the following conditions are true for the provided device:
        - Provided device is a Futaba device
        - usb.core.Device has a HID interface
        - HID interface has a suitable interrupt endpoint

        Args:
            coreDevice (usb.core.usb.core.Device): The device to check

        Returns:
            bool: True if all conditions are met, false otherwise

        """
        return (
            coreDevice.idVendor == FUTABA_VENDOR_ID
            and utils.findInterruptEndpoint(coreDevice) is not None
        )
