"""Driver and manager for Futaba RC to USB adapters."""

import array
import atexit
import multiprocessing
import os
import sys
from enum import Enum, auto

import numpy as np
import usb

from . import utils, worker
from .errors import DeviceNotFoundError


class DeviceState(Enum):
    """Stores the state of a single device."""

    RUNNING = auto()
    STOPPED = auto()
    INITIALIZING = auto()


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB device drivers."""

    def __init__(self, debugMode=False):
        """Create an object that manages Futaba drivers.

        Raises:
            RuntimeError: Raised if no Futaba USB devices are detected

        """
        if len(self.futabaDevices) == 0:
            raise DeviceNotFoundError

        self.logger = utils.newLogger("FutabaDeviceManager")
        atexit.register(self.stopAll)

    @property
    def futabaDevices(self):
        """A tuple of supported Futaba devices."""
        return tuple(
            [
                FutabaDeviceDriver(device)
                for device in usb.core.find(find_all=True)
                if FutabaDeviceDriver.deviceIsSupported(device)
            ]
        )

    def findDevice(self, endpoint=None):
        """Find the Futaba device that has the provided endpoint.

        Args:
            endpoint (int, optional): The endpoint of the device you are looking for. Defaults to
            None.

        Returns:
            usb.core.Device or None: Returns None if a device was not found. Otherwise returns the
            core device handle.

        """
        if endpoint is not None:
            return self._findDeviceByEndpoint(endpoint)
        return None

    def getDeviceStatus(self, deviceIndex):
        """Get the status of the device at the given index.

        Args:
            deviceIndex (int): The device that you want the status of

        Returns:
            string: "RUNNING" or "IDLE"

        """
        try:
            return self.futabaDevices[deviceIndex].getState()
        except Exception as e:
            self.logger.warning(e)
            return False

    def listDevices(self):
        """Get an ordered list of available devices.

        Returns:
            tuple of string: Ordered list of available devices

        """
        return [{"key": i, **device.toDict()} for i, device in enumerate(self.futabaDevices)]

    def start(self, deviceIndex):
        """Start the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to
            start. Defaults to [].

        """
        self.logger.debug(f"Attempting to start device at index[s] {deviceIndex}")
        if isinstance(deviceIndex, int):
            result = self.futabaDevices[deviceIndex].start()

            if result:
                self.logger.debug(f"-> {self.futabaDevices[deviceIndex]} started")
            else:
                raise RuntimeError(
                    f"Start requested failed for item at index {deviceIndex}",
                )
        elif hasattr("__iter__", deviceIndex):
            self.logger.debug("-> Iterable detected, attempting to start multiple...")
            for idx in deviceIndex:
                result = self.futabaDevices[idx].start()
                if result:
                    self.logger.debug(f"--> {self.futabaDevices[deviceIndex]} started")
                else:
                    raise RuntimeError(
                        f"Start requested failed for item at index {idx}",
                    )

        return self.listDevices()

    def stop(self, deviceIndex):
        """Stop the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to
            stop. Defaults to [].

        """
        try:
            if isinstance(deviceIndex, int):
                self.futabaDevices[deviceIndex].stop()
            elif hasattr("__iter__", deviceIndex):
                for idx in deviceIndex:
                    self.futabaDevices[idx].stop()
        except Exception as e:
            self.logger.warning(e)
        return self.listDevices()

    def stopAll(self):
        """Stop all running drivers."""
        try:
            for device in self.futabaDevices:
                device.stop()
        except Exception as e:
            self.logger.warning(e)
        return self.listDevices()

    @staticmethod
    def _deviceIsRunning(futabaDeviceDriver):
        """Determine if the provided driver is currently running or not.

        Args:
            futabaDeviceDriver (FutabaDeviceDriver): The device to check

        Returns:
            bool: True if the device has a subprocess

        """
        return futabaDeviceDriver.getState() == DeviceState.RUNNING

    def _findDeviceByEndpoint(self, endpoint):
        """Find which device has the given endpoint.

        Args:
            endpoint (int): The endpoint of the device to find.

        Returns:
            dict: A dictionary representation of the device with the given
            endpoint.

        """
        endpoint = int(endpoint)
        for device in self.listDevices():
            if device["interruptEndpoint"] == endpoint:
                return device
        return None


class FutabaDeviceDriver:
    """Provides a class based interface for a single Futaba USB device."""

    def __init__(self, device):
        """Create an object that drives a single device on it's own process.

        Args:
            device (usb.core.Device): The device you want to spawn a driver for

        Raises:
            TypeError: If device is not of type usb.core.Device

        """
        self.state = DeviceState.INITIALIZING
        self.endpoint = utils.getInterruptAddress(device)
        self.deviceInfo = utils.getCoreDeviceInfo(self.endpoint)

        if self.endpoint is None:
            raise TypeError("Unable to find interrupt endpoint for device")

        self.logger = utils.newLogger(f"{self.deviceInfo['product']}_driver")
        self.subProc = None
        self.killswitch = multiprocessing.Event()

        self.config = self._loadConfig(self.productName)
        self.deviceChannels = [
            InputChannel(self.logger, eventName, calibration, False)
            for eventName, calibration in zip(
                self.config["channel_events"],
                self._loadCalibration(self.productName),
                strict=True,  # 1 event name and 1 calibration per channel
            )
        ]
        self.front_pipe, self.back_pipe = multiprocessing.Pipe()
        atexit.register(self.stop)

    def __eq__(self, other):
        """Compare one drivers interrupt endpoint address with the other.

        Args:
            other (FutabaDeviceDriver): The device to compare to

        Returns:
            bool: True if the devices have the same interrupt endpoint address

        """
        return self.endpoint == other.endpoint

    def __hash__(self):
        """Generate a has for this object.

        Returns:
            hash: The hash.

        """
        return hash(self.toDict())

    def __str__(self):
        """Generate a string representation of this device driver."""
        return f"{self.name} Driver"

    def __del__(self):
        """Destructor."""
        self.stop()

    @staticmethod
    def deviceIsSupported(coreDevice):
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
    def frameSize(self):
        """The frame size is the number of bytes read from the USB device per cycle."""
        return self.config["frameSize"]

    @property
    def interruptEndpoint(self):
        """The interrupt endpoint for the device."""
        return int(self.deviceInfo["interruptEndpoint"])

    @property
    def manufacturer(self):
        """The manufacturer of the device."""
        return self.deviceInfo["manufacturer"]

    @property
    def model(self):
        """The product name/model of the device."""
        return self.name

    @property
    def name(self):
        """The name that the virtual device will show up as to the operating system."""
        return f"Futaba {self.deviceInfo['product']}({self.endpoint})"

    @property
    def productName(self):
        """The product name/model of the device."""
        return self.deviceInfo["product"]

    @property
    def productID(self):
        """The product ID is a unique number assigned to vendors by the governing body."""
        return self.deviceInfo["productID"]

    @property
    def serialNumber(self):
        """The serial number of the device."""
        return self.deviceInfo["serialNumber"]

    @property
    def speed(self):
        """USB generation speed supported by the device."""
        return self.deviceInfo["speed"]

    def getState(self):
        """Get the current state of the driver.

        Returns:
            string: The current state of the driver.

        """
        if self.subProc is not None and self.subProc.is_alive():
            self.state = DeviceState.RUNNING
        else:
            self.state = DeviceState.STOPPED
        return self.state

    def start(self):
        """Start the driver if it is not running."""
        if self.getState() != DeviceState.RUNNING:
            if self.killswitch.is_set():
                self.killswitch.clear()
                self.logger.debug("-> Killswitch cleared")

            self.subProc = multiprocessing.Process(
                name=f"{self.name} Driver",
                target=worker.run,
                args=self._toSubprocTuple(),
            )
            self.subProc.start()

        return self.getState()

    def stop(self):
        """Stop the driver."""
        if not self.killswitch.is_set():
            self.killswitch.set()
        if self.subProc is not None and self.subProc.is_alive():
            self.subProc.join()
        self.state = DeviceState.STOPPED

    def toDict(self):
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

    def _loadConfig(self, productName):
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

    def _loadCalibration(self, productName):
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

    def _toSubprocTuple(self):
        """Create a tuple that is compatable with the worker function.

        Returns:
            tuple: The tuple that you will pass to the worker function

        """
        return tuple(
            [
                self.killswitch,
                self.config["frame_size"],
                [channel.toDict() for channel in self.deviceChannels],
                self.name,
                self.interruptEndpoint,
            ]
        )


class InputChannel:
    """Provides a class based representation of a single input channel."""

    def __init__(self, logger, eventName, calibration, reverseInputs=False):
        """Create an InputChannel object.

        Args:
            logger (logging.Logger): The logger for the class to use
            eventName (str): Any valid uinput event
            calibration (ChannelCalibration): A calibration object used to
            calibrate this input channel
            reverseInputs (bool, optional): If true the value map will be
            generated in reverse to reverse the inputs. Defaults to False.

        """
        self.logger = logger
        self.eventName = eventName
        self.isReversed = reverseInputs
        self.calibration = ChannelCalibration(
            logger,
            inputRange=calibration[0],
            outputRange=calibration[1],
            reverse=self.isReversed,
        )
        self.valueMap = self.calibration.valueMap
        self.logger.debug(f"-= InputChannel({self.eventName}) created =-")
        self.logger.debug(f"    direction: {'reversed' if self.isReversed else 'normal'}")

    def __eq__(self, other):
        """Determine if the input channels are equal."""
        return self.eventName == other.eventName

    def __hash__(self):
        """Determine the objects hash."""
        return hash(self.toDict())

    def __str__(self):
        """Create a string representation of this IputChannel."""
        return self.eventName

    def toDict(self):
        """Generate a dictionary representation of this input channel."""
        return {"eventName": self.eventName, "valueMap": self.valueMap}


class ChannelCalibration:
    """Provides a class based representation of a single channels calibration.

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

    def __init__(
        self,
        logger,
        inputRange=None,
        outputRange=None,
        reverse=False,
    ):
        """Create a ChannelCalibration object.

        Args:
            logger (logging.Logger): The logger you want this class to use
            inputRange (iterable of length 2, optional): A list, tuple, or array
            where the first value is the lowest possible input value and the
            second value is the highest possible input value. Defaults to None.
            outputRange (_type_, optional): A list, tuple, or array where the
            first value is the lowest possible output value and the second value
            is the highest possible output value. Defaults to None.
            reverse (bool, optional): If reverse the calibrated values will be
            inserted into the resulting array backwards. This will reverse the
            direction of the input. Defaults to False.

        """
        if inputRange is None:
            inputRange = [
                utils.DEFAULT_DEVICE_MIN_VAL,
                utils.DEFAULT_DEVICE_MID_VAL,
                utils.DEFAULT_DEVICE_MAX_VAL,
            ]
        if outputRange is None:
            outputRange = [
                utils.EVENT_MIN_VAL,
                utils.EVENT_MID_VAL,
                utils.EVENT_MAX_VAL,
            ]
        self.logger = logger
        self.reverse = reverse
        self.inputRange = inputRange
        self.outputRange = outputRange
        self.valueMap = self._generateValueMap(inputRange, outputRange, self.reverse)

        self.logger.debug(f"-= Channel Calibration({inputRange}, {outputRange}) created! =-")
        self.logger.debug("    valueMap:")
        self.logger.debug(f"        elements: {len(self.valueMap)}")
        self.logger.debug(f"        unique values: {len(set(self.valueMap))}")
        self.logger.debug(f"        mem footprint: {self.memoryFootprint} Kb")
        self.logger.debug(f"    isReversed: {self.reverse}")
        self.logger.debug(f"    inputRange: {inputRange[2] - inputRange[0]} total elements")
        self.logger.debug(f"        high: {inputRange[2]}")
        self.logger.debug(f"        med: {inputRange[1]}")
        self.logger.debug(f"        low: {inputRange[0]}")
        self.logger.debug(f"    outputRange: {outputRange[2] - outputRange[0]} total elements")
        self.logger.debug(f"        high: {outputRange[2]}")
        self.logger.debug(f"        med: {outputRange[1]}")
        self.logger.debug(f"        low: {outputRange[0]}")

        def __str__(self):
            """Create a string representation of this calibration object."""
            return str(
                {
                    "reverse": self.reverse,
                    "inputRange": self.inputRange,
                    "outputRange": self.outputRange,
                    "valueMap": f"Generated {len(self.valueMap)} values "
                    f"consuming{self.memoryFootprint} Kilobytes of memory",
                },
            )

    @property
    def memoryFootprint(self):
        """Get the size in Kilobytes of the calibration map.

        Returns:
            int: The number of kilobytes that the calibration map occupyes in memory

        """
        return sys.getsizeof(self.valueMap) // 1024  # kb

    @staticmethod
    def _generateValueMap(inputRange, outputRange, reverse=False):
        """Generate a list of values that maps the input range to the output range.

        Args:
            inputRange (list, optional): This determines the size of the map.
            Defaults to [600, 3500].
            outputRange (list, optional): This determines what values are generated in the map.
            Defaults to [0, 32768].
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
