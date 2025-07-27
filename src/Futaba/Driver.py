"""Driver for Futaba RC to USB adapters."""

import atexit
import multiprocessing
import os
from enum import Enum, auto
from typing import Any

import usb

from . import Util as utils
from . import Worker
from .InputChannel import InputChannel


class DriverState(Enum):
    """Stores the state of a single device."""

    RUNNING = auto()
    STOPPED = auto()
    SUSPENDED = auto()
    INITIALIZING = auto()


class FutabaDeviceDriver:
    """Provides a class based interface for a single Futaba USB device."""

    def __init__(self, device: usb.core.Device) -> None:
        """Create an object that drives a single device on it's own process.

        Args:
            device (usb.core.Device): The device you want to spawn a driver for

        Raises:
            TypeError: If device is not of type usb.core.Device

        """
        self.state = DriverState.INITIALIZING
        self.endpoint = utils.getInterruptAddress(device)
        self.deviceInfo = utils.getCoreDeviceInfo(self.endpoint)

        if self.endpoint is None:
            raise TypeError("Unable to find interrupt endpoint for device")

        self.logger = utils.newLogger(f"{self.deviceInfo['product']}_driver")
        self.subProc = None
        self.killswitch = multiprocessing.Event()
        self.runFlag = multiprocessing.Event()

        self.config = self._loadConfig(self.productName)
        self.deviceChannels = [
            InputChannel(eventName, calibration, False, logger=self.logger)
            for eventName, calibration in zip(
                self.config["channel_events"],
                self._loadCalibration(self.productName),
                strict=True,  # 1 event name and 1 calibration per channel
            )
        ]
        # self.frontPipe, self.backPipe = multiprocessing.Pipe()
        atexit.register(self.stop)

    def __eq__(self, other: object) -> bool:
        """Compare one drivers interrupt endpoint address with the other.

        Args:
            other (object): The device to compare to

        Returns:
            bool: True if the devices have the same interrupt endpoint address

        """
        return hasattr(other, "endpoint") and self.endpoint == other.endpoint

    def __hash__(self) -> int:
        """Generate a has for this object.

        Returns:
            hash: The hash.

        """
        return hash(self.toDict())

    def __str__(self) -> str:
        """Generate a string representation of this device driver."""
        return f"{self.name} Driver"

    def __del__(self) -> None:
        """Destructor."""
        self.stop()

    @staticmethod
    def deviceIsSupported(coreDevice: usb.core.Device) -> bool:
        """Determine if the device is compatable with this driver class.

        Determine if the following conditions are true for the provided device:
        - Provided device is a Futaba device
        - Device has a HID interface
        - HID interface has a suitable interrupt endpoint

        Args:
            coreDevice (usb.core.Device): The device to check

        Returns:
            bool: True if all conditions are met, false otherwise

        """
        if coreDevice.idVendor != utils.FUTABA_VENDOR_ID:
            return False

        hidInterface = utils.findHIDInterface(coreDevice)
        if hidInterface is None:
            return False

        endpoint = utils.findInterruptEndpoint(coreDevice)

        return endpoint is not None

    @property
    def frameSize(self) -> int:
        """The frame size is the number of bytes read from the USB device per cycle."""
        return self.config["frame_size"]

    @property
    def interruptEndpoint(self) -> int:
        """The interrupt endpoint for the device."""
        return int(self.deviceInfo["interruptEndpoint"])

    @property
    def manufacturer(self) -> str:
        """The manufacturer of the device."""
        return self.deviceInfo["manufacturer"]

    @property
    def model(self) -> str:
        """The product name/model of the device."""
        return self.name

    @property
    def name(self) -> str:
        """The name that the virtual device will show up as to the operating system."""
        return f"Futaba {self.deviceInfo['product']}({self.endpoint})"

    @property
    def productName(self) -> str:
        """The product name/model of the device."""
        return self.deviceInfo["product"]

    @property
    def productID(self) -> int:
        """The product ID is a unique number assigned to vendors by the governing body."""
        return self.deviceInfo["productID"]

    @property
    def serialNumber(self) -> str:
        """The serial number of the device."""
        return self.deviceInfo["serialNumber"]

    @property
    def speed(self) -> str:
        """USB generation speed supported by the device."""
        return self.deviceInfo["speed"]

    def getState(self) -> DriverState:
        """Get the current state of the driver.

        Returns:
            DriverState: The current state of the driver.

        """
        if self.subProc is not None and self.subProc.is_alive():
            if self.runFlag.is_set():
                self.state = DriverState.RUNNING
            else:
                self.state = DriverState.SUSPENDED
        else:
            self.state = DriverState.STOPPED
        return self.state

    def start(self) -> DriverState:
        """Start the driver if it is not running."""
        if self.getState() != DriverState.RUNNING:
            if self.killswitch.is_set():
                self.killswitch.clear()
                self.logger.debug("-> Killswitch cleared")
            if not self.runFlag.is_set():
                self.runFlag.set()
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
        if not self.killswitch.is_set():
            self.killswitch.set()
        if self.subProc is not None and self.subProc.is_alive():
            self.subProc.join()
        self.subProc = None

    def suspend(self) -> None:
        """Suspend the driver without killing the subprocess."""
        if self.runFlag.is_set():
            self.runFlag.clear()

    def toDict(self) -> dict[str, Any]:
        """Create a dictionary representation of this driver."""
        return dict(
            {
                "config": self.config,
                "deviceChannels": len(self.deviceChannels),
                "interruptEndpoint": self.interruptEndpoint,
                "product": self.productName,
                "productID": self.productID,
                "manufacturer": self.manufacturer,
                "name": self.name,
                "serialNumber": self.serialNumber,
                "speed": self.speed,
            }
        )

    def _loadConfig(self, productName: str) -> dict[str, Any]:
        """Load the device config.

        Load the device config and fall back to the default config file if one doesn't exist.

        Args:
            productName (str): The name of the product to load the config for.

        Returns:
            dict: A dictionary containing the driver settings

        """
        config = None

        filePath = os.path.join(utils.CONFIG_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CONFIG_PATH, "default.json")

        self.logger.debug(f"loading {filePath}")
        config = utils.loadJsonFile(filePath)

        if config is None:
            self.logger.debug(f"device config not found, loading {defaultPath}")
            config = utils.loadJsonFile(defaultPath)
        if config is None:
            self.logger.debug("using hard-coded defaults")
            config = utils.DEFAULT_CONFIG

        self.logger.debug(f"config={config}")
        return config

    def _loadCalibration(self, productName: str) -> list[list[int]]:
        """Load the calibration file for the given product.

        Args:
            productName (str): The name of the product to load the
            calibration for. Defaults to None.

        Returns:
            list of list: Each inner list will contain calibration data for a channel.

        """
        filePath = os.path.join(utils.CALIBRATION_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CALIBRATION_PATH, "default.json")

        # Load this products calibration file by default
        self.logger.debug(f"loading {filePath}")
        channelCalibrations = utils.loadJsonFile(filePath)
        # If that fails, load the default config file
        if channelCalibrations is None:
            self.logger.debug(f"loading{defaultPath}")
            channelCalibrations = utils.loadJsonFile(defaultPath)
        # If that fails, use the hard-coded values
        if channelCalibrations is None:
            self.logger.debug("using hard-coded defaults")
            channelCalibrations = utils.DEFAULT_CALIBRATION

        self.logger.debug(f"channelCalibrations={channelCalibrations}")
        return channelCalibrations

    def _toSubprocTuple(
        self,
    ) -> tuple[
        multiprocessing.Event,  # Killswitch
        multiprocessing.Event,  # runFlag
        int,  # frameSize
        list[dict[str, Any]],  # device Channels
        str,  # name
        int,  # interrupt endpoint
    ]:
        """Create a tuple that is compatable with the worker function.

        Returns:
            tuple: The tuple that you will pass to the worker function

        """
        return tuple(
            [
                self.killswitch,
                self.runFlag,
                self.frameSize,
                tuple([channel.toDict() for channel in self.deviceChannels]),
                self.name,
                self.interruptEndpoint,
            ]
        )
