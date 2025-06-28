"""Futaba driver package."""

import array
import atexit
import multiprocessing
import os
import sys

import numpy as np
import uinput
import usb

import driver


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB
    device drivers.
    """

    def __init__(self):
        """Create an object that manages Futaba drivers.

        Raises:
            RuntimeError: Raised if no Futaba USB devices are detected

        """
        atexit.register(self.stopAll)
        self.logger = driver.newLogger("FutabaDeviceManager")
        self.futabaDevices = tuple(
            [
                FutabaDeviceDriver(device)
                for device in usb.core.find(find_all=True)
                if FutabaDeviceDriver.deviceIsSupported(device)
            ]
        )

        if len(self.futabaDevices) == 0:
            raise RuntimeError("No Futaba USB device detected!")

    @classmethod
    def findDevice(
        cls,
        endpoint=None,
        # model=None,
        # bus=None,
        # port=None
    ):
        if endpoint is not None:
            return cls._findDeviceByEndpoint(endpoint)
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
        return tuple(
            [
                {
                    "endpoint": device.getEndpoint(),
                    "key": i,
                    "name": device.getName(),
                    "state": device.getState(),
                }
                for i, device in enumerate(self.futabaDevices)
            ]
        )

    def start(self, deviceIndex):
        """Start the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to start. Defaults to [].

        """
        self.logger.debug(
            f"Attempting to start device at index[s] {deviceIndex}"
        )
        if isinstance(deviceIndex, int):
            result = self.futabaDevices[deviceIndex].start()

            if result:
                self.logger.debug(
                    f"-> {self.futabaDevices[deviceIndex]} started"
                )
            else:
                raise RuntimeError(
                    f"Start requested failed for item at index {deviceIndex}",
                )
        elif hasattr("__iter__", deviceIndex):
            self.logger.debug(
                "-> Iterable detected, attempting to start multiple..."
            )
            for idx in deviceIndex:
                result = self.futabaDevices[idx].start()
                if result:
                    self.logger.debug(
                        f"--> {self.futabaDevices[deviceIndex]} started"
                    )
                else:
                    raise RuntimeError(
                        f"Start requested failed for item at index {idx}",
                    )

        return self.listDevices()

    def stop(self, deviceIndex):
        """Stop the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to stop. Defaults to [].

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
        return futabaDeviceDriver.getState() == "RUNNING"

    def _findDeviceByEndpoint(self, endpoint):
        """Find which device has the given endpoint

        Args:
            endpoint (int): The endpoint of the device to find

        Returns:
            _type_: _description_
        """
        for device in self.listDevices():
            if device.getEndpoint() == endpoint:
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
        self.state = "INITIALIZING"

        self.endpoint = driver.findInterruptEndpoint(device)
        deviceInfo = driver.getCoreDeviceInfo(self.endpoint)
        if self.endpoint is None:
            raise TypeError("Unable to find interrupt endpoint for device")
        self.name = f"Futaba {deviceInfo['product']}({self.endpoint})"

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
                strict=True,  # 1 config and 1 calibration per channel
            )
        ]
        atexit.register(self.stop)

    def __str__(self):
        """Generate a string representation of this driver."""
        return f"{self.name} Driver"

    def __eq__(self, other):
        return self.endpoint == other.endpoint

    def __lt__(self, other):
        return NotImplemented

    def __gt__(self, other):
        return NotImplemented

    def __repr__(self):
        """Generate a machine-readable representation of this driver."""
        return str(self.toDict())

    def getEndpoint(self):
        """Get the interrupt endpoint for this device

        Returns:
            int: The interrupt endpoint for this device
        """
        return self.endpoint

    def getName(self):
        """Get the name of the device this driver was initialized for."""
        return self.name

    def getState(self):
        """Get the current state of the driver.

        Returns:
            string: The current state of the driver

        """
        if self.subProc is not None and self.subProc.is_alive():
            self.state = "RUNNING"
        else:
            self.state = "IDLE"
        return self.state

    def start(self):
        """Start the driver if it is not running."""
        if self.getState() != "RUNNING":
            if self.killswitch.is_set():
                self.killswitch.clear()
                self.logger.debug("-> Killswitch cleared")
            self.subProc = multiprocessing.Process(
                name=f"{self.name} Driver",
                target=_workerProcess,
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
        self.state = "IDLE"

    def toDict(self):
        """Create a dictionary representation of this driver."""
        return {
            "config": self.config,
            "deviceChannels": tuple(
                [channel.toDict() for channel in self.deviceChannels],
            ),
            "endpointAddress": self.interruptEndpoint,
            "name": self.name,
        }

    @staticmethod
    def deviceIsSupported(coreDevice):
        """Determine if the following conditions are true for the provided device.

        - Provided device is a Futaba device
        - Device has a HID interface
        - HID interface has a suitable interrupt endpoint

        Args:
            coreDevice (usb.core.Device): The device to check

        Returns:
            bool: True if all conditions are met, false otherwise

        """
        if coreDevice.idVendor != driver.FUTABA_VENDOR_ID:
            return False

        hidInterface = driver.findHIDInterface(coreDevice)
        if hidInterface is None:
            return False

        endpoint = driver.findInterruptEndpoint(coreDevice)
        if endpoint is None:
            return False

        return True

    def _loadConfig(self, productName):
        """Load the settings for this particular device and falls back to the default config file if one doesn't exist.

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
        """Load the calibration file for the given product.

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

    def toDict(self):
        """Generate a dictionary representation of this input channel."""
        return {"eventName": self.eventName, "valueMap": self.valueMap}

    def __init__(self, eventName, calibration, reverseInputs=False):
        """Create an InputChannel object.

        Args:
            eventName (str): Any valid uinput event
            calibration (ChannelCalibration): A calibration object used to calibrate this input channel
            reverseInputs (bool, optional): If true the value map will be generated in reverse to reverse the inputs. Defaults to False.

        """
        self.eventName = eventName
        self.isReversed = reverseInputs
        self.calibration = ChannelCalibration(
            inputRange=calibration[0],
            outputRange=calibration[1],
            reverse=self.isReversed,
        )
        self.valueMap = self.calibration.getCalibratedValueMap()

    def __str__(self):
        """Create a string representation of this IputChannel."""
        return str(self.toDict())


class ChannelCalibration:
    """Provides a class based representation of a channel calibration.

    Why:
        - The range of values that is output on a given channel is different for each device manufactured.
        - To account for this difference, we use a process known as "calibrating" the device. Calibrating a device is simply the process of determining your devices unique range of values, and then mapping that range of values to a standardized range of values.
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
        """Get an array where each index of the array represents a possible device input and the value stored at that index is the calibrated output value.

        Returns:
            array.array of int: The integer array that maps a given index to the corresponding calibrated outpute valued stored at that index

        """
        return self.valueMap

    def __init__(
        self,
        inputRange=None,
        outputRange=None,
        reverse=False,
    ):
        """Create a ChannelCalibration object.

        Args:
            inputRange (iterable of length 2, optional): A list, tuple, or array where the first value is the lowest possible input value and the second value is the highest possible input value. Defaults to None.
            outputRange (_type_, optional): A list, tuple, or array where the first value is the lowest possible output value and the second value is the highest possible output value. Defaults to None.
            reverse (bool, optional): If reverse the calibrated values will be inserted into the resulting array backwards. This will reverse the direction of the input. Defaults to False.

        """
        if inputRange is None:
            inputRange = [
                driver.DEFAULT_DEVICE_MIN_VAL,
                driver.DEFAULT_DEVICE_MAX_VAL,
            ]
        if outputRange is None:
            outputRange = [driver.EVENT_MIN_VAL, driver.EVENT_MAX_VAL]

        self.reverse = reverse
        self.inputRange = inputRange
        self.outputRange = outputRange
        self.valueMap = self._generateValueMap(
            inputRange, outputRange, self.reverse
        )

    def __str__(self):
        """Create a string representation of this calibration object."""
        return str(
            {
                "reverse": self.reverse,
                "inputRange": self.inputRange,
                "outputRange": self.outputRange,
                "valueMap": f"Generated {len(self.valueMap)} values consuming {sys.getsizeof(self.valueMap)} bytes of memory",
            },
        )

    @staticmethod
    def _generateValueMap(inputRange, outputRange, reverse=False):
        """Generate a list of values that maps the input range to the output range.

        Args:
            inputRange (list, optional): This determines the size of the map. Defaults to [600, 3500].
            outputRange (list, optional): This determines what values are generated in the map. Defaults to [0, 32768].
            reverse (bool, optional): If set to true the map will be generated backwards. This will reverse the direction of the input

        Returns:
            list: A list of all possible output values given the range of input values

        """
        # Guarantee that we are working with ints
        inputRange = tuple(map(int, inputRange))
        outputRange = tuple(map(int, outputRange))

        lowerInput = inputRange[0]
        upperInput = inputRange[2]
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
                    left=outputRange[0],
                    right=outputRange[1],
                ),
                0,  # No decimals
            ).astype(int),
        )


##
# Disabled mccabe linting as this function is specifically meant to be the
# target of a separate process. As such the function is more complex and
# contains more statments that would otherwise be tolerated
##
def _workerProcess(
    killswitch, frameSize, deviceChannels, name, interruptEndpoint
):  # noqa: C901, PLR0915, PLR0912
    """Start a worker for the given device with the given settings.

    This is meant to be run in a seperate process via
    `multiprocessing.Process(target=_workerProcess,...)`

    Args:
        killswitch (multiprocessing.Event): This worker will run an infinite loop until this event is set
        frameSize (int): The number of bytes to request from the usb device at one time
        deviceChannels (tuple of dict): a tuple where each value contained is a calibrated value map for its corresponding channel
        name (str): The name the device will show up as
        interruptEndpoint (int): The usb interrupt endpoint of the device that you want to start a driver for

    NOTE main event loop optimization:
        we initialize a local version of everything that will be used inside
        the main event loop. By doing this, the interpreter:
        - Does not have to re-create variables each iteration
        - Does not have to interpret dots, subscripts, etc

    """
    channel = None
    coreDevice = None
    logger = driver.newLogger(f"{name}_subproc")
    logger.debug("Subprocess started")
    for _device in usb.core.find(find_all=True):
        if _device.idVendor != driver.FUTABA_VENDOR_ID:
            continue
        for _config in _device:
            for _interface in _config:
                for _endpoint in _interface:
                    if (
                        usb.util.endpoint_direction(_endpoint.bEndpointAddress)
                        == usb.util.ENDPOINT_IN
                        and _endpoint.bmAttributes
                        == driver.INTERRUPT_ENDPOINT_ATTRIBUTE
                        and _endpoint.bEndpointAddress == interruptEndpoint
                    ):
                        interruptEndpoint = _endpoint.bEndpointAddress
                        coreDevice = _device
                        logger.debug(
                            f"Device at endpoint {interruptEndpoint}: {coreDevice}",
                        )
                        break

    if coreDevice is None:
        raise TypeError(
            f"No Futaba device found at interrupt endpoint {interruptEndpoint}",
        )

    channelEventsMap = []
    channelValueMaps = []
    for channel in deviceChannels:
        channelEventsMap.append(getattr(uinput, channel["eventName"]))
        channelValueMaps.append(channel["valueMap"])
    channelEventsMap = tuple(channelEventsMap)
    channelValueMaps = tuple(channelValueMaps)

    logger.debug("maps created")

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple(
            [
                event + (0, driver.EVENT_MAX_VAL, 0, 0)
                for event in channelEventsMap
            ]
        ),
        name,
        vendor=driver.FUTABA_VENDOR_ID,
    )

    logger.debug("virtual device set up")

    # Create all variables outside the loop to avoid the overhead of
    # recreating them each iteration
    emit = virtualDevice.emit
    fromBytes = int.from_bytes
    maxInputVal = None
    rawData = None
    readDevice = coreDevice.read
    synchronize = virtualDevice.syn

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    logger.info(f"Driver started: {interruptEndpoint} -> {name}")
    # -- MAIN LOOP --
    while not killswitch.is_set():
        try:
            # - The transmitter may not send a new frame if the inputs remain static
            # - No reason to care about timeouts
            # - - Long timeout length = less timeouts
            # - - Less timeouts = fewer exceptions raised
            # - - Fewer exceptions raised = less overhead
            rawData = readDevice(interruptEndpoint, frameSize, timeout=250)
            channelData = []
            # rawValues = []
            for i in range(0, len(rawData), 2):
                channel = i // 2
                valueMap = channelValueMaps[channel]

                rawValue = int(
                    fromBytes(rawData[i : i + 2], byteorder="little")
                )
                # Avoid overflows and underflows
                # account for off-by-one
                maxInputVal = len(valueMap) - 1
                if rawValue > maxInputVal:
                    rawValue = maxInputVal
                # calibration map will always have an index 0, so we pull
                # the minimum value from that
                elif rawValue < 0:
                    rawValue = 0
                # Extract calibrated value from map
                # rawValues.append(rawValue)
                channelData.append(valueMap[rawValue])
            channelData.reverse()
            # logger.critical(rawValues)
            # Queue one event for each channel
            for data, event in zip(channelData, channelEventsMap, strict=False):
                # Queue one event for each channel
                emit(event, data, syn=False)

            # fire all queued events
            synchronize()
        except usb.core.USBTimeoutError:
            pass
        except Exception as e:
            logger.critical(e)
            raise e

    logger.debug("Releasing the USB interface...")
    try:
        usb.util.release_interface(coreDevice, 0)
    except Exception as e:
        logger.warning(
            "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)",
        )
        logger.warning(e)

    logger.debug("Reattaching the kernel driver...")
    try:
        coreDevice.attach_kernel_driver(0)
    except Exception as e:
        logger.warning(
            "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)",
        )
        logger.warning(e)

    logger.debug("Resetting device...")
    try:
        coreDevice.reset()
    except Exception as e:
        logger.warning(
            "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)",
        )
        logger.warning(e)
