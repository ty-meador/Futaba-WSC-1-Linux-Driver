"""Driver for Futaba RC USB devices."""

import atexit
import multiprocessing
import os
from enum import Enum
from enum import auto
from typing import Any

import usb

from . import Util as utils
from . import Worker
from .__config__ import CALIBRATION_PATH
from .__config__ import CONFIG_PATH
from .__config__ import DEFAULT_CALIBRATION
from .__config__ import DEFAULT_CONFIG
from .__config__ import FUTABA_VENDOR_ID
from .InputChannel import InputChannel
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
        if hasattr(self, "workerCtl") and hasattr(self.workerCtl, "killswitch") and not self.workerCtl.killswitch.is_set():
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

    def toDict(self) -> dict[str, Any]:
        """Create a dictionary representation of this driver."""
        return dict({
            "config": self.config,
            "deviceChannels": len(self.deviceChannels),
            "deviceUUID": self.deviceUUID,
            "interruptEndpoint": self.interruptEndpoint,
            "productName": self.productName,
            "productID": self.productID,
            "manufacturer": self.manufacturer,
            "name": self.name,
            "serialNumber": self.serialNumber,
            "speed": self.speed,
        })

    def toggleEcho(
        self,
    ):
        """Toggle echo on or off."""
        if self.workerCtl.echoFlag.is_set():
            self.workerCtl.echoFlag.clear()
        else:
            self.workerCtl.echoFlag.set()

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

    def _loadCalibration(self, productName: str, deviceUUID: str) -> list[list[int]]:
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
    ) -> tuple[
        WorkerControl,
        int,  # frameSize
        list[dict[str, Any]],  # device Channels
        str,  # name
        int,  # interrupt endpoint
    ]:
        """Create a tuple that is compatable with the worker function.

        Returns:
            tuple: The tuple that you will pass to the worker function

        """
        return tuple([
            self.workerCtl,
            utils.DeviceConfig(
                channelEvents=self.config["channel_events"],
                deadZone=self.config["dead_zone"],
                frameSize=self.config["frame_size"],
                noiseFilter=self.config["noise_filter"],
            ),
            tuple([channel.toDict() for channel in self.deviceChannels]),
            self.name,
            self.interruptEndpoint,
        ])

    def __init__(self, device: usb.core.Device) -> None:
        """Create an object that drives a single device on it's own process.

        Args:
            device (usb.core.Device): The device you want to spawn a driver for

        Raises:
            TypeError: If device is not of type usb.core.Device

        """
        ##
        # meta-stuff
        ##
        self.state = DriverState.INITIALIZING

        self.endpoint = utils.findInterruptEndpoint(device)
        if self.endpoint is None:
            raise TypeError("Unable to find interrupt endpoint for device")

        self.deviceInfo = ({
            "productID": device.idProduct,
            "serialNumber": device.serial_number,
            "product": device.product,
            "manufacturer": device.manufacturer,
            "speed": device.speed,
            "interruptEndpoint": self.endpoint,
        } if device else None)

        self.logger = utils.newLogger(f"{self.deviceInfo['product']}_driver")
        ##
        # Worker subproc stuff
        ##
        self.subProc = None
        self.frontPipe, self.backPipe = multiprocessing.Pipe()
        self.workerCtl = WorkerControl(pipe=self.backPipe)

        ##
        # Device stuff
        ##
        self.config = self._loadConfig(self.productName)
        self.deviceChannels = [
            InputChannel(eventName, calibration, False, logger=self.logger)
            for eventName, calibration in zip(
                self.config["channel_events"],
                self._loadCalibration(self.productName, self.deviceUUID),
                strict=True,  # 1 event name and 1 calibration per channel
            )
        ]

        atexit.register(self.stop)

    def __eq__(self, other: object) -> bool:
        """Compare instances based on what USB endpoint they are using.

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
        return f"{self.name} Driver({self.deviceUUID})"

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
        return (
            coreDevice.idVendor == FUTABA_VENDOR_ID
            and utils.findInterruptEndpoint(coreDevice) is not None
        )

    @property
    def deadZone(self) -> int:
        """The size of the dead zone for the device.

        Returns:
            int: The size of the dead zone for the device
        """
        return self.config["dead_zone"]

    @property
    def deviceUUID(self) -> str:
        """Get a deterministic UUID for this device."""
        return f"{self.productID:04X}-{self.serialNumber}"

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
    def noiseFilter(self) -> int:
        """The minimum input change necessary trigger an output change.

        Returns:
            int: The noise filter value.
        """
        return self.config["noise_filter"]

    @property
    def pipe(self) -> multiprocessing.Pipe:
        """A duple pipe providing real-time communication to the running driver."""
        return self.frontPipe

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
