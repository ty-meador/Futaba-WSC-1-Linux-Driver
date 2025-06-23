"""Class representing a single Futaba USB adapater"""

import array
import atexit
import multiprocessing
import os
import sys

import numpy as np
import usb

import driver


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB device drivers"""

    def listDevices(self):
        """Returns an ordered list of devices

        Returns:
            tuple of string: Ordered list of available devices
        """
        return tuple(
            {"name": device.getName(), "state": device.getState(), "key": i}
            for i, device in enumerate(self.futabaDevices)
        )

    def getDeviceStatus(self, deviceIndex):
        """Get the status of the device at the given index

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

    def start(self, deviceIndex):
        """Start the devices at the given indexes

        Args:
            deviceIndexes (list of int, optional): The devices you want to start. Defaults to [].
        """

        self.logger.debug(f"Attempting to start device at index[s] {deviceIndex}")
        if isinstance(deviceIndex, int):
            result = self.futabaDevices[deviceIndex].start()

            if result:
                self.logger.debug(f"-> {self.futabaDevices[deviceIndex]} started")
            else:
                raise RuntimeError(
                    f"Start requested failed for item at index {deviceIndex}"
                )
        elif hasattr("__iter__", deviceIndex):
            self.logger.debug("-> Iterable detected, attempting to start multiple...")
            for idx in deviceIndex:
                result = self.futabaDevices[idx].start()
                if result:
                    self.logger.debug(f"--> {self.futabaDevices[deviceIndex]} started")
                else:
                    raise RuntimeError(
                        f"Start requested failed for item at index {idx}"
                    )

        return self.listDevices()

    def stop(self, deviceIndex):
        """Stop the devices at the given indexes

        Args:
            deviceIndexes (list of int, optional): The devices you want to stop. Defaults to [].
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
        """Stops all running drivers"""
        try:
            for device in self.futabaDevices:
                device.stop()
        except Exception as e:
            self.logger.warning(e)
        return self.listDevices()

    def __init__(self):
        atexit.register(self.stopAll)
        self.logger = driver.newLogger("FutabaDeviceManager")
        self.futabaDevices = tuple(
            FutabaDeviceDriver(device.bus, device.port_numbers[0])
            for device in usb.core.find(find_all=True)
            if device.manufacturer.lower() == "futaba"
        )
        self.deviceList = tuple()
        if len(self.futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

    @staticmethod
    def _deviceIsRunning(futabaDeviceDriver):
        """Function to determine if a given device is actively running

        Args:
            futabaDeviceDriver (FutabaDeviceDriver): The device to check

        Returns:
            bool: True if the device has a subprocess
        """
        return futabaDeviceDriver.getState() == "RUNNING"


class FutabaDeviceDriver:
    """Provides a class based interface for a single Futaba USB device"""

    def getName(self):
        """Gets the name of the device this driver was initialized for"""
        return self.name

    def getState(self):
        """Gets the current state of the driver

        Returns:
            string: The current state of the driver
        """
        if self.subProc is not None and self.subProc.is_alive():
            self.state = "RUNNING"
        else:
            self.state = "IDLE"
        return self.state

    def start(self):
        """Start the driver if it is not running"""
        if self.getState() != "RUNNING":
            if self.killswitch.is_set():
                self.killswitch.clear()
                self.logger.debug("-> Killswitch cleared")
            self.subProc = multiprocessing.Process(
                name=f"{self.name} Driver",
                target=driver.eventDispatchWorker,
                args=self._toSubprocTuple(),
            )
            self.subProc.start()
        return self.getState()

    def stop(self):
        """Stop the driver"""
        if not self.killswitch.is_set():
            self.killswitch.set()
        if self.subProc is not None and self.subProc.is_alive():
            self.subProc.join()
        self.state = "IDLE"

    def toDict(self):
        """Returns a dictionary representation of the driverf object"""

        return {
            "config": self.config,
            "deviceChannels": tuple(
                [channel.toDict() for channel in self.deviceChannels]
            ),
            "endpointAddress": self.interruptEndpoint,
            "name": self.name,
        }

    def __init__(self, bus, port, name=None):
        deviceInfo = driver.getCoreDeviceInfo(bus, port)

        if not deviceInfo:
            raise RuntimeError(f"No device found at bus {bus}, port {port}")

        if deviceInfo["manufacturer"].lower() != "futaba":
            raise TypeError(
                f"The device at bus {bus}, port {port} does not appear to be aFutaba device"
            )

        self.state = "INITIALIZING"
        self.bus = bus
        self.port = port

        self.name = name
        if self.name is None:
            self.name = f"Futaba {deviceInfo['product']}({bus},{port})"

        self.logger = driver.newLogger(f"{deviceInfo['product']}_driver")
        self.productID = deviceInfo["productID"]
        self.serialNumber = deviceInfo["serialNumber"]
        self.product = deviceInfo["product"]
        self.manufacturer = deviceInfo["manufacturer"]
        self.speed = deviceInfo["speed"]
        self.interruptEndpoint = deviceInfo["interruptEndpoint"]
        self.subProc = None
        self.killswitch = multiprocessing.Event()
        self.config = self._loadConfig(self.product)
        self.deviceChannels = [
            InputChannel(eventName, calibration, False)
            for eventName, calibration in zip(
                self.config["channel_events"],
                self._loadCalibration(self.product),
            )
        ]
        # self.logger.debug(self.toDict())
        atexit.register(self.stop)

    def __str__(self):
        return f"{self.name} Driver"

    def __repr__(self):
        return str(self.toDict())

    def _loadConfig(self, productName):
        """Loads the settings for this particular device and falls back
        to the default config file if one doesn't exist

        Returns:
            dict: A dictionary containing the driver settings
        """
        config = None

        filePath = os.path.join(driver.CONFIG_PATH, f"{productName}.json")
        defaultPath = os.path.join(driver.CONFIG_PATH, "default.json")

        self.logger.debug(f"loading {filePath}")
        config = driver.loadJsonFile(filePath)

        if config is None:
            self.logger.debug(f"device config not found, loading {defaultPath}")
            config = driver.loadJsonFile(defaultPath)
        if config is None:
            self.logger.debug("using hard-coded defaults")
            config = driver.DEFAULT_CONFIG

        self.logger.debug(f"config={config}")
        return config

    def _loadCalibration(self, productName):
        """Loads the calibration file for the given product

        Args:
            productName (str, optional): The name of the product to load the calibration for. Defaults to None.

        Returns:
            list of list: Each inner list will contain exactly 2 items, each of which are lists.
        """

        filePath = os.path.join(driver.CALIBRATION_PATH, f"{productName}.json")
        defaultPath = os.path.join(driver.CALIBRATION_PATH, "default.json")

        self.logger.debug(f"loading {filePath}")
        channelCalibrations = driver.loadJsonFile(filePath)

        if channelCalibrations is None:
            self.logger.debug(f"loading{defaultPath}")
            channelCalibrations = driver.loadJsonFile(defaultPath)
        if channelCalibrations is None:
            self.logger.debug("using hard-coded defaults")
            channelCalibrations = driver.DEFAULT_CALIBRATION

        self.logger.debug(f"channelCalibrations={channelCalibrations}")
        return channelCalibrations

    def _toSubprocTuple(self):
        return (
            self.killswitch,
            self.config["frame_size"],
            list(map(lambda channel: channel.toDict(), self.deviceChannels)),
            self.name,
            self.interruptEndpoint,
        )


class InputChannel:
    """Provides a class based representation of a single input channel"""

    def toDict(self):
        """Returns a dictionary representation of this input channel"""
        return {"eventName": self.eventName, "valueMap": self.valueMap}

    def __init__(self, eventName, calibration, reverseInputs=False):
        self.eventName = eventName
        self.isReversed = reverseInputs
        self.calibration = ChannelCalibration(
            inputRange=calibration[0],
            outputRange=calibration[1],
            reverse=self.isReversed,
        )
        self.valueMap = self.calibration.getCalibratedValueMap()

    def __str__(self):
        return str(self.toDict())


class ChannelCalibration:
    """Provides a class based representation of a channel calibration.

    Why:
        - The range of values that is output on a given channel is different
        for each device manufactured.
        - To account for this difference, we use a process known as
        "calibrating" the device. Calibrating a device is simply the process
        of determining your devices unique range of values, and then mapping
        that range of values to a standardized range of values.
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
        - Translating the raw value to the calibrated value is as simple as calMap[rawV]
        - Therefore, we are providing an interface with O(1) runtime at the
        cost of 16kb of memory on an 8 channel device.
    """

    def getCalibratedValueMap(self):
        """Returns the calibrated value mapping

        Returns:
            array.array of int: The integer array that maps a given index to
            the corresponding calibrated outpute valued stored at that index
        """
        return self.valueMap

    def __init__(
        self,
        inputRange=None,
        outputRange=None,
        reverse=False,
    ):
        if inputRange is None:
            inputRange = [driver.DEFAULT_DEVICE_MIN_VAL, driver.DEFAULT_DEVICE_MAX_VAL]
        if outputRange is None:
            outputRange = [driver.EVENT_MIN_VAL, driver.EVENT_MAX_VAL]

        self.reverse = reverse
        self.inputRange = inputRange
        self.outputRange = outputRange
        self.valueMap = self._generateValueMap(inputRange, outputRange, self.reverse)

    def __str__(self):
        return str(
            {
                "reverse": self.reverse,
                "inputRange": self.inputRange,
                "outputRange": self.outputRange,
                "valueMap": f"Generated {len(self.valueMap)} values consuming {sys.getsizeof(self.valueMap)} bytes of memory",
            }
        )

    @staticmethod
    def _generateValueMap(inputRange, outputRange, reverse=False):
        """Generate a list of values that maps the input range to the output range

        Args:
            inputRange (list, optional): This determines the size of the map. Defaults to [600, 3500].
            outputRange (list, optional): This determines what values are generated in the map. Defaults to [0, 32768].

        Returns:
            list: A list of all possible output values given the range of input values
        """

        # Guarantee that we are working with ints
        inputRange[0] = int(inputRange[0])
        inputRange[1] = int(inputRange[1])
        outputRange[0] = int(outputRange[0])
        outputRange[1] = int(outputRange[1])

        lowerInput = inputRange[0]
        upperInput = inputRange[1]
        lowerOutput = outputRange[0]

        # Create a value map such that the index of the array represents
        # the input value, and the contents at that index is the output
        inputValues = np.array([lowerOutput] * upperInput, int)

        arrayRange = range(lowerInput, upperInput)
        if reverse:
            reversed(arrayRange)

        for i in arrayRange:
            inputValues[i] = i

        return array.array(
            "I",  # int
            np.round(
                np.interp(
                    inputValues,
                    inputRange,
                    outputRange,
                ),
                0,  # No decimals
            ).astype(int),
        )
