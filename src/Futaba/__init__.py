"""Driver and manager for Futaba RC to USB adapters."""

import array
import atexit
import json
import logging
import multiprocessing
import os
import re
import sys
from logging import handlers
from pathlib import Path

import numpy as np
import uinput
import usb

ROOT_DIR = None
# Start from THIS file's directory
currentFile = Path(__file__).resolve()  # Using resolve to get an absolute path.
for parent in currentFile.parents:  # Iterate over every parent.
    if (parent / "LICENSE").exists():  # We expect the LICENSE file to be in the root of the project
        ROOT_DIR = os.path.abspath(parent)
        break

if ROOT_DIR is None:
    raise RuntimeError(
        "Unable to locate a file named 'LICENSE', therefore cannot determine the "
        "projects root directory"
    )

SRC_PATH = os.path.join(ROOT_DIR, "src")
LOG_PATH = os.path.join(ROOT_DIR, "logs")
os.makedirs(LOG_PATH, exist_ok=True)

DRIVER_PATH = os.path.join(SRC_PATH, "Futaba")
CONFIG_PATH = os.path.join(DRIVER_PATH, "configs")
CALIBRATION_PATH = os.path.join(DRIVER_PATH, "calibrations")
DEFAULT_DEVICE_MIN_VAL = 704
DEFAULT_DEVICE_MID_VAL = 2048
DEFAULT_DEVICE_MAX_VAL = 3392
EVENT_MIN_VAL = 0
EVENT_MID_VAL = 16384
EVENT_MAX_VAL = 32768
FUTABA_VENDOR_ID = 4104  # 0x1008
INTERRUPT_ENDPOINT_ATTRIBUTE = 0x3  # conincidence
HID_INTERFACE = 0x3  # conincidence
print(LOG_PATH)
##
# Credit to https://github.com/shaozu/Futaba_T16IZ_Linux/blob/main/entry.py
# for this great starting point!
##
DEFAULT_CONFIG = {
    "frame_size": 16,
    "channel_events": [
        "ABS_X",
        "ABS_Y",
        "ABS_RX",
        "ABS_RY",
        "ABS_THROTTLE",
        "ABS_RUDDER",
        "ABS_TILT_X",
        "ABS_TILT_Y",
    ],
}


DEFAULT_CALIBRATION = [
    [
        [DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MID_VAL, DEFAULT_DEVICE_MAX_VAL],
        [EVENT_MIN_VAL, EVENT_MID_VAL, EVENT_MAX_VAL],
    ]
    * len(DEFAULT_CONFIG["channel_events"])  # one calibration mapping per channel
]

PRODUCTS = {
    "default": 999,
    "WSC-1": 10,
    "T16IZ": 11,
    10: "WSC-1",
    11: "T16IZ",
    999: "default",
}


DEFAULT_LOG_HANDLER = handlers.RotatingFileHandler(
    "logs.txt",
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)


LOGLEVEL = logging.DEBUG
DEFAULT_LOG_HANDLER.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
DEFAULT_LOGGER = logging.getLogger("driver")
DEFAULT_LOGGER.setLevel(LOGLEVEL)
DEFAULT_LOGGER.addHandler(DEFAULT_LOG_HANDLER)


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB device drivers."""

    def __init__(self, debugMode=False):
        """Create an object that manages Futaba drivers.

        Raises:
            RuntimeError: Raised if no Futaba USB devices are detected

        """
        atexit.register(self.stopAll)
        self.logger = newLogger("FutabaDeviceManager")
        self.futabaDevices = tuple(
            [
                FutabaDeviceDriver(device)
                for device in usb.core.find(find_all=True)
                if FutabaDeviceDriver.deviceIsSupported(device)
            ]
        )

        if len(self.futabaDevices) == 0:
            raise RuntimeError("No Futaba USB device detected!")

    def findDevice(
        self,
        endpoint=None,
        # model=None,
        # bus=None,
        # port=None
    ):
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
        deviceList = []
        for i, device in enumerate(self.futabaDevices):
            _dict = device.toDict()
            deviceDict = {"key": i}
            for key in _dict:
                deviceDict[key] = _dict[key]
            deviceList.append(deviceDict)
        return deviceList

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
        return futabaDeviceDriver.getState() == "RUNNING"

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
        self.state = "INITIALIZING"

        self.endpoint = findInterruptEndpoint(device)
        deviceInfo = getCoreDeviceInfo(self.endpoint)
        if self.endpoint is None:
            raise TypeError("Unable to find interrupt endpoint for device")
        self.name = f"Futaba {deviceInfo['product']}({self.endpoint})"

        self.logger = newLogger(f"{deviceInfo['product']}_driver")
        self.productID = deviceInfo["productID"]
        self.serialNumber = deviceInfo["serialNumber"]
        self.product = deviceInfo["product"]
        self.manufacturer = deviceInfo["manufacturer"]
        self.speed = deviceInfo["speed"]
        self.interruptEndpoint = int(deviceInfo["interruptEndpoint"])
        self.subProc = None
        self.killswitch = multiprocessing.Event()
        self.config = self._loadConfig(self.product)
        self.deviceChannels = [
            InputChannel(eventName, calibration, False)
            for eventName, calibration in zip(
                self.config["channel_events"],
                self._loadCalibration(self.product),
                strict=True,  # 1 event name and 1 calibration per channel
            )
        ]
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

    def getEndpoint(self):
        """Get the interrupt endpoint for this device.

        Returns:
            int: The interrupt endpoint for this device.

        """
        return self.endpoint

    def getName(self):
        """Get the name of the device this driver was initialized for."""
        return self.name

    def getState(self):
        """Get the current state of the driver.

        Returns:
            string: The current state of the driver.

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
        return dict(
            {
                "config": self.config,
                "deviceChannels": tuple(
                    [channel.toDict() for channel in self.deviceChannels],
                ),
                "interruptEndpoint": self.interruptEndpoint,
                "product": self.product,
                "productID": self.productID,
                "manufacturer": self.manufacturer,
                "name": self.name,
                "serialNumber": self.serialNumber,
                "speed": self.speed,
            }
        )

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
        if coreDevice.idVendor != FUTABA_VENDOR_ID:
            return False

        hidInterface = findHIDInterface(coreDevice)
        if hidInterface is None:
            return False

        endpoint = findInterruptEndpoint(coreDevice)

        return endpoint is not None

    def _loadConfig(self, productName):
        """Load the device config.

        Load the device config and fall back to the default config file if one doesn't exist.

        Returns:
            dict: A dictionary containing the driver settings

        """
        config = None

        filePath = os.path.join(CONFIG_PATH, f"{productName}.json")
        defaultPath = os.path.join(CONFIG_PATH, "default.json")

        self.logger.debug(f"loading {filePath}")
        config = loadJsonFile(filePath)

        if config is None:
            self.logger.debug(f"device config not found, loading {defaultPath}")
            config = loadJsonFile(defaultPath)
        if config is None:
            self.logger.debug("using hard-coded defaults")
            config = DEFAULT_CONFIG

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
        filePath = os.path.join(CALIBRATION_PATH, f"{productName}.json")
        defaultPath = os.path.join(CALIBRATION_PATH, "default.json")

        # Load this products calibration file by default
        self.logger.debug(f"loading {filePath}")
        channelCalibrations = loadJsonFile(filePath)
        # If that fails, load the default config file
        if channelCalibrations is None:
            self.logger.debug(f"loading{defaultPath}")
            channelCalibrations = loadJsonFile(defaultPath)
        # If that fails, use the hard-coded values
        if channelCalibrations is None:
            self.logger.debug("using hard-coded defaults")
            channelCalibrations = DEFAULT_CALIBRATION

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
            calibration (ChannelCalibration): A calibration object used to
            calibrate this input channel
            reverseInputs (bool, optional): If true the value map will be
            generated in reverse to reverse the inputs. Defaults to False.

        """
        self.eventName = eventName
        self.isReversed = reverseInputs
        self.calibration = ChannelCalibration(
            inputRange=calibration[0],
            outputRange=calibration[1],
            reverse=self.isReversed,
        )
        self.valueMap = self.calibration.valueMap

    def __str__(self):
        """Create a string representation of this IputChannel."""
        return self.eventName


class ChannelCalibration:
    """Provides a class based representation of a channel calibration.

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
        inputRange=None,
        outputRange=None,
        reverse=False,
    ):
        """Create a ChannelCalibration object.

        Args:
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
                DEFAULT_DEVICE_MIN_VAL,
                DEFAULT_DEVICE_MAX_VAL,
            ]
        if outputRange is None:
            outputRange = [EVENT_MIN_VAL, EVENT_MAX_VAL]

        self.reverse = reverse
        self.inputRange = inputRange
        self.outputRange = outputRange
        self.valueMap = self._generateValueMap(inputRange, outputRange, self.reverse)

        def __str__(self):
            """Create a string representation of this calibration object."""
            return str(
                {
                    "reverse": self.reverse,
                    "inputRange": self.inputRange,
                    "outputRange": self.outputRange,
                    "valueMap": f"Generated {len(self.valueMap)} values "
                    f"consuming{sys.getsizeof(self.valueMap)} bytes of memory",
                },
            )

    @staticmethod
    def _generateValueMap(inputRange, outputRange, reverse=False):
        """Generate a list of values that maps the input range to the output range.

        Args:
            inputRange (list, optional): This determines the size of the map.
            Defaults to [600, 3500].
            outputRange (list, optional): This determines what values are
            generated in the map. Defaults to [0, 32768].
            reverse (bool, optional): If set to true the map will be generated
            backwards. This will reverse the direction of the input

        Returns:
            list: A list of all possible output values given the range of input
            values

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


def findHIDInterface(coreDevice):
    """Find the HID interface for the given device.

    Args:
        coreDevice (usb.core.Device): The device to search

    Returns:
        usb.core.Device.interface: The HID interface if one exists, none if
        none exist

    """
    for config in coreDevice:
        for interface in config:
            if interface.bInterfaceClass == HID_INTERFACE:
                return interface
    return None


def findInterruptEndpoint(coreDevice):
    """Find the USB interrupt endpoint for the given HID interface.

    Args:
        coreDevice (usb.core.Device): The core device to find the interrupt endpoint of.

    Returns:
        int: The address of the endpoint if one exists, None if none exist.

    """
    hidInterface = findHIDInterface(coreDevice)
    for endpoint in hidInterface:
        if (
            usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN
            and endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
        ):
            return endpoint.bEndpointAddress
    return None


def getCoreDevice(endpoint):
    """Get the core USB device handle that has the provided enpoint.

    Args:
        endpoint (int): The interrupt endpoint address as an integer.

    Returns:
        usb.core.Device: The core device handle that has the provided endpoint.

    """
    results = [
        device
        for device in usb.core.find(find_all=True)
        if device.idVendor == FUTABA_VENDOR_ID and findInterruptEndpoint(device) == endpoint
    ]

    if len(results) != 1:
        DEFAULT_LOGGER.critical(f"Expected to find exactly 1 result, found {len(results)}")
        return False

    DEFAULT_LOGGER.debug(f"-> Found {results[0]}")
    return results[0]


def getCoreDeviceInfo(endpoint):
    """Find the core device on the given bus and port.

    Args:
        endpoint (int): The endpoint address of the device you want info for

    Returns:
        usb.core.Device: The core device at the provided bus and port0

    """
    logger = DEFAULT_LOGGER
    logger.debug(f"looking for core device with an interrupt endpoint address of {endpoint}")
    device = getCoreDevice(endpoint)
    return {
        "productID": device.idProduct,
        "serialNumber": device.serial_number,
        "product": device.product,
        "manufacturer": device.manufacturer,
        "speed": device.speed,
        "interruptEndpoint": findInterruptEndpoint(device),
    }


def getInterruptAddress(device):
    """Take in a device and returns is interrupt enpoint address.

    Args:
        device (usb.core.Device): The device that we want to emulate

    Raises:
        ValueError: Raised if the provided device is not an of type usb.core.device
        RuntimeError: Raised if the provided device does not have an endpoint

    Returns:
        int: The endpoint object used to capture frames from the physical device

    """
    if not isinstance(device, usb.core.Device):
        raise ValueError("Expected first param to be of type usb.core.Device")
    for config in device:
        for interface in config:
            for endpoint in interface:
                if (
                    usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN
                    # 0x3 indicates interrupt endpoint
                    and endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
                ):
                    return endpoint.bEndpointAddress
    raise RuntimeError("No interrupt endpoint found!")


def loadJsonFile(filePath):
    """Load a JSON file into a dictionary.

    Args:
        filePath (str): The path to the json file you want to load

    Returns:
        dict: The parsed json

    """
    logger = newLogger(f"loadJsonFile({filePath})")
    parsedJson = None

    try:
        logger.debug(f"> Looking for {filePath}")
        with open(filePath, encoding="utf-8") as jsonFile:
            parsedJson = json.load(jsonFile)
        logger.debug("--> loaded!")
    except FileNotFoundError:
        # parsedJson defaults to None
        logger.debug("--> not found, returning >None<")
    return parsedJson


def newLogger(
    name="logs",
    fileName=None,
    level=LOGLEVEL,
):
    """Generate a logger.

    Args:
        name (str, optional): The label to insert after the timestamp on each line in the logs.
        Defaults to "logs"
        fileName (str, optional): The name of the log file the logger will log to. Defaults to
        None
        level (loglevel, optional): The level the logger should output. Defaults to
        logging.WARNING.

    Returns:
        logger: The generated logger

    """
    if fileName is None:
        fileName = re.sub(r"\W", "_", name) + ".txt"

    handler = handlers.RotatingFileHandler(
        os.path.join(LOG_PATH, fileName),
        maxBytes=5 * 1024 * 1024,  # 5 megabytes
        backupCount=5,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


##
# Disabled mccabe linting as this function is specifically meant to be the
# target of a separate process. As such the function is more complex and
# contains more statments that would otherwise be tolerated
##
def _workerProcess(killswitch, frameSize, deviceChannels, name, interruptEndpoint):  # noqa: C901, PLR0915, PLR0912
    """Start a worker for the given device with the given settings.

    This is meant to be run in a seperate process via
    `multiprocessing.Process(target=_workerProcess,...)`

    Args:
        killswitch (multiprocessing.Event): This worker will run an infinite loop until this event
        is set
        frameSize (int): The number of bytes to request from the usb device at one time
        deviceChannels (tuple of dict): a tuple where each value contained is a calibrated value map
        for its corresponding channel
        name (str): The name the device will show up as
        interruptEndpoint (int): The usb interrupt endpoint of the device that you want to start a
        driver for

    NOTE main event loop optimization:
        we initialize a local version of everything that will be used inside the main event loop.
        By doing this, the interpreter:
        - Does not have to re-create variables each iteration
        - Does not have to interpret dots, subscripts, etc

    """
    channel = None
    coreDevice = None
    logger = newLogger(f"{name}_subproc")
    logger.debug("Subprocess started")
    for _device in usb.core.find(find_all=True):
        if _device.idVendor != FUTABA_VENDOR_ID:
            continue
        for _config in _device:
            for _interface in _config:
                if _interface.bInterfaceClass != HID_INTERFACE:
                    continue
                for _endpoint in _interface:
                    if (
                        _endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
                        and usb.util.endpoint_direction(_endpoint.bEndpointAddress)
                        == usb.util.ENDPOINT_IN
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
        tuple([event + (0, EVENT_MAX_VAL, 0, 0) for event in channelEventsMap]),
        name,
        vendor=FUTABA_VENDOR_ID,
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
            # - The transmitter may not send a new frame if the inputs remain
            # static
            # - No reason to care about timeouts
            # - - Long timeout length = less timeouts
            # - - Less timeouts = fewer exceptions raised
            # - - Fewer exceptions raised = less overhead
            rawData = readDevice(interruptEndpoint, frameSize, timeout=250)
            channelData = []
            rawValues = []

            for i in range(0, len(rawData), 2):
                channel = i // 2
                valueMap = channelValueMaps[channel]

                rawValue = int(fromBytes(rawData[i : i + 2], byteorder="little"))
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
                rawValues.append(rawValue)
                channelData.append(valueMap[rawValue])
            channelData.reverse()

            # Queue one event for each channel
            for data, event in zip(channelData, channelEventsMap, strict=False):
                # Queue one event for each channel
                emit(event, data, syn=False)

            # fire all queued events
            synchronize()
        except usb.core.USBTimeoutError:
            pass
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.critical(e)
            raise e

    logger.debug("Releasing the USB interface...")
    try:
        usb.util.release_interface(coreDevice, 0)
    except Exception as e:
        logger.warning(f"Unable to release the USB interface, {e}")

    logger.debug("Reattaching the kernel ..")
    try:
        coreDevice.attach_kernel_driver(0)
    except Exception as e:
        logger.warning(f"Unable to reattach the kernel driver, {e}")

    logger.debug("Resetting device...")
    try:
        coreDevice.reset()
    except Exception as e:
        logger.warning(f"Unable to reset the USB interface, {e}")
