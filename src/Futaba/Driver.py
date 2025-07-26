"""Driver for Futaba RC to USB adapters."""

import array
import atexit
import logging
import multiprocessing
import os
import sys
import typing
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np
import usb

from . import Util as utils
from . import Worker


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
        self.frontPipe, self.backPipe = multiprocessing.Pipe()
        atexit.register(self.stop)

    def __eq__(self, other: object) -> bool:
        """Compare one drivers interrupt endpoint address with the other.

        Args:
            other (FutabaDeviceDriver): The device to compare to

        Returns:
            bool: True if the devices have the same interrupt endpoint address

        """
        return self.endpoint == other.endpoint

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
        return self.config["frameSize"]

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
            string: The current state of the driver.

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

    def toDict(self) -> dict:
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

    def _loadConfig(self, productName: str) -> dict:
        """Load the device config.

        Load the device config and fall back to the default config file if one doesn't exist.

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

    def _loadCalibration(self, productName: str) -> dict:
        """Load the calibration file for the given product.

        Args:
            productName (str, optional): The name of the product to load the
            calibration for. Defaults to None.

        Returns:
            list of list: Each inner list will contain exactly 2 items, each of
            which are lists.

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
        list,  # device Channels
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
                self.config["frame_size"],
                [channel.toDict() for channel in self.deviceChannels],
                self.name,
                self.interruptEndpoint,
            ]
        )


@dataclass(frozen=True, slots=True)
class InputChannel:
    """Provides a class based representation of a single input channel."""

    eventName: str
    calibrationRange: typing.Iterable[int]

    isReversed: bool = False
    logger: object = field(default_factory=lambda: utils.newLogger("InputChannel"))
    valueMap: array.array = field(default_factory=lambda: [])
    calibration: "ChannelCalibration" = None

    def __post_init__(self) -> None:
        """Instantiate our ChannelCalibration object."""
        object.__setattr__(
            self,
            "calibration",
            ChannelCalibration(
                logger=self.logger,
                inputRange=self.calibrationRange,
                reverse=self.isReversed,
            ),
        )
        object.__setattr__(self, "valueMap", self.calibration.valueMap)

        self.logger.debug(f"-= InputChannel({self.eventName}) created =-")
        self.logger.debug(f"    direction: {'reversed' if self.isReversed else 'normal'}")

    def __eq__(self, other: object) -> bool:
        """Determine if the input channels are equal."""
        return self.eventName == other.eventName

    def __hash__(self) -> int:
        """Determine the objects hash."""
        return hash(self.toDict())

    def toDict(self) -> dict:
        """Generate a dictionary representation of this input channel."""
        return {"eventName": self.eventName, "valueMap": self.valueMap}


@dataclass(frozen=True, slots=True)
class ChannelCalibration:
    """Provides a class based representation of a single channels calibration.

    Args:
        logger (logging.Logger): The logger you want this class to use
        inputRange (iterable, optional): An iterable of length 3 where each item represents the low,
        middle, and high point respectively in increasing order.
        defaults to utils.DEFAULT_INPUT_RANGE
        outputRange (_type_, optional): An iterable of length 3 where each item represents the low,
        middle, and high point respectively in increasing order.
        defaults to utils.DEFAULT_OUTPUT_RANGE
        reverse (bool, optional): If reverse the calibrated values will be
        inserted into the resulting array backwards. This will reverse the
        direction of the input. Defaults to False.


    Why:
        - The range of values that is output on a given channel is different for
         each device manufactured.
        - To account for this difference, we use a process known as
        "calibrating" the device. Calibrating a device is simply the process of
        determining your devices unique range of values, and then mapping that
        range of values to a standardized range of values.
            - This requires a 1-d interpolation from the raw device values to
            the standardized output values. This must be done every single time
            we read data from the device (hundreds of times per second+).

    What:
        - Provide an interface that allows for on the fly interpolation of the
        devices input range to the standardized output range

    How:
        - Interpolate all possible input values ahead of time
        - Create an array with a length equal to that of the upper output limit
        - For each value in the input range, interpolate the value and store the
        interpolated_value at array[value]
        - To prevent out of bounds errors and ensure output continuity:
            - Fill all values below "min input value" with "min output value"
            - Fill all values above "max input value" with "max output value"

    Rationale:
        - Assume the following:
            - our calibration mapping array has already been generated and
            is stored in a variable named "calMap".
            - assume we have just read the raw input value from the device and
            stored it to a variable named "rawV".
        - Translating the raw value to the calibrated value is as simple as
        calMap[rawV]
        - Therefore, we are providing an interface with O(1) runtime at the
        cost of 16kb of memory on an 8 channel device.

    """

    inputRange: typing.Iterable = field(default_factory=lambda: utils.DEFAULT_INPUT_RANGE)
    outputRange: typing.Iterable = field(default_factory=lambda: utils.DEFAULT_OUTPUT_RANGE)

    logger: logging.logger = field(default_factory=lambda: utils.newLogger("ChannelCalibration"))
    reverse: bool = False
    valueMap: array.array = field(init=False, repr=False)
    valueMapSize: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Generate the calibration mapping array."""
        inputRange = tuple(self.inputRange)
        outputRange = tuple(self.outputRange)
        logger = self.logger
        reverse = self.reverse
        valueMap = self._generateValueMap(
            inputRange,
            outputRange,
            reverse,
        )

        object.__setattr__(self, "valueMap", valueMap)
        object.__setattr__(self, "inputRange", inputRange)
        object.__setattr__(self, "outputRange", outputRange)
        object.__setattr__(self, "valueMapSize", sys.getsizeof(valueMap) // 1024)  # kb

        logger.debug(f"-= Channel Calibration({inputRange}, {outputRange}) created! =-")
        logger.debug("    valueMap:")
        logger.debug(f"        elements: {len(valueMap)}")
        logger.debug(f"        unique values: {len(set(valueMap))}")
        logger.debug(f"        mem footprint: {self.valueMapSize} Kb")
        logger.debug(f"    isReversed: {reverse}")
        logger.debug(f"    inputRange: {inputRange[2] - inputRange[0]} total elements")
        logger.debug(f"        high: {inputRange[2]}")
        logger.debug(f"        med: {inputRange[1]}")
        logger.debug(f"        low: {inputRange[0]}")
        logger.debug(f"    outputRange: {outputRange[2] - outputRange[0]} total elements")
        logger.debug(f"        high: {outputRange[2]}")
        logger.debug(f"        med: {outputRange[1]}")
        logger.debug(f"        low: {outputRange[0]}")

    @staticmethod
    def _generateValueMap(
        inputRange: typing.Iterable[int],
        outputRange: typing.Iterable[int],
        reverse: bool = False,
    ) -> array.array[int]:
        """Generate a list of values that maps the input range to the output range.

        Args:
            inputRange (list, optional): This determines the size of the map.
            Defaults to utils.DEFAULT_INPUT_RANGE.
            outputRange (list, optional): This determines what values are generated in the map.
            Defaults to utils.DEFAULT_OUTPUT_RANGE.
            reverse (bool, optional): If set to true the map will be generated backwards. This will
            reverse the direction of the input

        Returns:
            array: An array of all possible output values which can be interpolated from the range
            of input values

        """
        # Guarantee that we are working with ints
        inputRange = tuple(map(int, inputRange))
        outputRange = tuple(map(int, outputRange))

        inputMin, inputMid, inputMax = inputRange
        outputMin, outputMid, outputMax = outputRange

        # Create a value map such that the index of the array represents
        # the input value, and the contents at that index is the output
        allPossibleInputValues = np.array([outputMin] * inputMax, int)

        arrayRange = range(inputMin, inputMax)
        if reverse:
            reversed(arrayRange)
        for i in arrayRange:
            allPossibleInputValues[i] = i

        return array.array(
            "i",  # int
            np.round(
                np.interp(
                    allPossibleInputValues,
                    inputRange,
                    outputRange,
                    left=outputMin,
                    right=outputMax,
                ),
                0,  # No decimals
            ).astype(int),
        )
