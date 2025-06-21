"""Class representing a single Futaba USB adapater"""

import array
import atexit
import json
import multiprocessing
import os

import numpy as np
import uinput
import usb

from driver import utils

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

##
# An array of length EVENT_MAX_VAL will be used
# to map the raw device inputs to values between EVENT_MIN_VAL
# and EVENT_MAX_VAL
##
EVENT_MAX_VAL = 32768
EVENT_MIN_VAL = 0

##
# Credit to https://github.com/shaozu/Futaba_T16IZ_Linux/blob/main/entry.py
# for this great starting point!
##
DEFAULT_CALIBRATION = [
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[704, 3392], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
]

FUTABA_VENDOR_ID = 4101

PRODUCTS = {
    "default": 999,
    "WSC-1": 10,
    "T16IZ": 11,
    10: "WSC-1",
    11: "T16IZ",
    999: "default",
}

multiprocessing.set_start_method("spawn")


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
        try:
            if isinstance(deviceIndex, int):
                self.futabaDevices[deviceIndex].start()
            elif hasattr("__iter__", deviceIndex):
                for idx in deviceIndex:
                    self.futabaDevices[idx].start()
        except Exception as e:
            self.logger.warning(e)
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
        self.logger = utils.getLogger("FutabaDeviceManager")
        self.futabaDevices = tuple(
            FutabaDeviceDriver(device)
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
        if self.subProc.is_alive():
            self.state = "RUNNING"
        else:
            self.state = "IDLE"
        return self.state

    def start(self):
        """Start the driver if it is not running"""

        if self.usbHandle.is_kernel_driver_active(0):
            self.usbHandle.detach_kernel_driver(0)
        self.usbHandle.set_configuration()

        try:
            self._eventLoop()

        except usb.core.USBError:
            # Don't raise exception, pass through to finally block
            pass
        finally:
            self.stop()

        return self.subProc.is_alive()

    def stop(self, exitCode=None):
        """Stop the driver if it is running

        Args:
            exitCode (int, optional): If provided the driver will exit with this code. Defaults to None.
        """
        self._setState("STOPPING")
        logger = self.logger

        try:
            logger.debug("Releasing the USB interface...")
            usb.util.release_interface(self.usbHandle, 0)
        except Exception as e:
            logger.warning(
                "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.warning(e)

        try:
            logger.debug("Reattaching the kernel driver...")
            self.usbHandle.attach_kernel_driver(0)
        except Exception as e:
            logger.warning(
                "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.warning(e)

        try:
            logger.debug("Resetting device...")
            self.usbHandle.reset()
        except Exception as e:
            logger.warning(
                "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.warning(e)

        if exitCode is not None:
            exit(exitCode)

        self._setState("IDLE")

    def _eventLoop(self):
        """The main event loop of the driver - INDEFINITELY BLOCKING OPERATION"""
        # Define variables before loop so we don't waste time creating
        # a new variable each iteration and the interpreter doesn't have
        # to evaluate dots, dict subscripts etc etc
        self.runFlag = True
        self._setState("RUNNING")
        logger = self.logger
        calibration = None
        calibrationMaps = self.channelMaps
        channel = None
        channelEvents = self.channelEvents
        emit = self.virtualDevice.emit
        endpoint = self.interruptEndpoint
        eventMaxVal = self.config["event_max_value"]
        frameSize = self.config["frame_size"]
        fromBytes = int.from_bytes
        logger = self.logger
        maxInputVal = None
        rawData = None
        readDevice = self.usbHandle.read
        reverseFlags = self.reverseFlags
        synchronize = self.virtualDevice.syn
        logger.info(f"Driver started: {endpoint} -> {self.name}")
        while self.runFlag:
            try:
                # - The transmitter may not send a new frame if the inputs remain static
                # - No reason to care about timeouts
                # - - Long timeout length = less timeouts
                # - - Less timeouts = fewer exceptions caught
                # - - Fewer exceptions caught = less overhead
                rawData = readDevice(
                    endpoint,
                    frameSize,
                    timeout=1000,
                )

                channelData = []
                for i in range(0, len(rawData), 2):
                    channel = i // 2
                    calibration = calibrationMaps[channel]

                    rawValue = int(fromBytes(rawData[i : i + 2], byteorder="little"))

                    # Avoid overflows and underflows
                    # account for off-by-one
                    maxInputVal = len(calibration) - 1
                    if rawValue > maxInputVal:
                        rawValue = maxInputVal
                    # calibration map will always have an index 0, so we pull
                    # the minimum value from that
                    elif rawValue < 0:
                        rawValue = 0
                    # Extract calibrated value from map
                    channelData.append(calibration[rawValue])
                channelData.reverse()

                for data, event, reverseFlag in zip(  # Queue one event for each channel
                    channelData, channelEvents, reverseFlags
                ):
                    if reverseFlag:
                        data = eventMaxVal - data
                    emit(event, data, syn=False)

                synchronize()  # fire all queued events
            except usb.core.USBError as e:
                # kaboom?
                if e.errno != 110:
                    # Yes Rico, kaboom.
                    logger.critical(e)
                    raise e

    def _setState(self, state):
        """Set the state of the Object

        Args:
            state (string): The new state of the Object
        """
        self.logger = utils.getLogger(f"{self.name} -= {state} =-")
        self.state = state

    def __init__(self, coreDevice):
        ##
        # Sanity checks
        ##
        if coreDevice.manufacturer.lower() != "futaba":
            raise RuntimeError("NOT A Futaba DEVICE!")
        self.name = f"Futaba {coreDevice.product}({coreDevice.bus},{coreDevice.port_numbers[0]})"

        ##
        # Global flags
        ##
        self.runFlag = False
        self.state = "INITIALIZING"

        ##
        # Handles to external objects
        ##
        self.usbHandle = coreDevice
        self.usbHandle.port = coreDevice.port_numbers[0]
        self.logger = self._getLogger(name=self.usbHandle.product, state=self.state)
        self.interruptEndpoint = self._findEndpoint(self.usbHandle)
        self.subProc = multiprocessing.Process(
            name=f"{self.name} Driver", target=self._eventLoop
        )

        # Configuration
        self.logger.debug("Attempting to load device configuration")
        self.config = self._loadConfig(self.usbHandle.product)

        ##
        # Calibration:
        # Each channel will have an array that maps the devices raw value to
        # a calibrated value
        ##
        self.logger.debug("Attempting to load device calibration")
        self.calibration = self._loadCalibration(self.usbHandle.product)
        self.channelMaps = self._generateChannelMaps(self.calibration)
        self.channelEvents = (
            tuple(  # Attribute names are stored directly in the config file as a string
                getattr(uinput, evtName) for evtName in self.config["channel_events"]
            )
        )
        # Default to no reversed inputs
        self.reverseFlags = [False] * len(self.channelEvents)

        # Create a virtual device using the events we just set up
        self.virtualDevice = uinput.Device(
            tuple([event + (0, EVENT_MAX_VAL, 0, 0) for event in self.channelEvents]),
            self.name,
            vendor=self.usbHandle.idVendor,
        )

        # Update logger, output some debug info
        self.logger = utils.getLogger(f"{self.name} -= IDLE =-")
        self.logger.debug("Userspace driver ready:")
        self.logger.debug(f"-> bus={self.usbHandle.bus}")
        self.logger.debug(f"-> channelEvents: {self.channelEvents}")
        self.logger.debug(f"-> config: {self.config}")
        self.logger.debug(f"-> interruptEndpoint: {self.interruptEndpoint}")
        self.logger.debug(f"-> name: {self.name}")
        self.logger.debug(f"-> port={self.usbHandle.port}")
        self.logger.debug(f"-> reverseFlags: {self.reverseFlags}")
        self.logger.debug(f"-> virtualDevice: {self.virtualDevice}")

        ##
        # External event registration
        ##
        atexit.register(self.stop)

    def __str__(self):
        return f"{self.name} driver"

    def __repr__(self):
        return str(self.usbHandle)

    @staticmethod
    def _calculateValueMap(inputRange=None, outputRange=None):
        """Generate a list of values that maps the input range to the output range

        Args:
            inputRange (list, optional): This determines the size of the map. Defaults to [600, 3500].
            outputRange (list, optional): This determines what values are generated in the map. Defaults to [0, 32768].

        Returns:
            list: A list of all possible output values given the range of input values
        """
        logger = utils.getLogger("FutabaDeviceDriver")
        if not hasattr(inputRange, "__len__") or len(inputRange) != 2:
            logger.error(
                "inputRange must be an array of length 2, using defaults instead"
            )
            inputRange = [600, 3500]
        if not hasattr(outputRange, "__len__") or len(outputRange) != 2:
            logger.error(
                "outputRange must be an array of length 2, using defaults instead"
            )
            outputRange = [0, 32768]

        if not isinstance(inputRange[0], int):
            raise TypeError(
                f"Expected inputRange[0] to be of type int, found {type(inputRange[0])}"
            )
        if not isinstance(inputRange[1], int):
            raise TypeError(
                f"Expected inputRange[1] to be of type int, found {type(inputRange[1])}"
            )
        if not isinstance(outputRange[0], int):
            raise TypeError(
                f"Expected outputRange[0] to be of type int, found {type(outputRange[0])}"
            )
        if not isinstance(outputRange[1], int):
            raise TypeError(
                f"Expected outputRange[1] to be of type int, found {type(inputRange[1])}"
            )

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
        for i in range(lowerInput, upperInput):
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

    @staticmethod
    def _findEndpoint(device):
        """Find the USB interrupt endpoint for the provided device

        Args:
            device (usb.core.Device): The device that we want to emulate

        Raises:
            ValueError: Raised if the provided device is not an of type usb.core.device
            RuntimeError: Raised if the provided device does not have an endpoint

        Returns:
            : The endpoint object used to capture frames from the physical device
        """
        if not isinstance(device, usb.core.Device):
            raise ValueError("Expected first param to be of type usb.core.Device")
        for config in device:
            for interface in config:
                for endpoint in interface:
                    if (
                        usb.util.endpoint_direction(endpoint.bEndpointAddress)
                        == usb.util.ENDPOINT_IN
                        # 0x3 indicates interrupt endpoint
                        and endpoint.bmAttributes == 0x3
                    ):
                        return endpoint.bEndpointAddress
        raise RuntimeError("No interrupt endpoint found!")

    @staticmethod
    def _loadJsonFile(filePath):
        """Generic function to load a JSON file into a dictionary

        Args:
            filePath (str): The path to the json file you want to load

        Returns:
            dict: The parsed json
        """
        logger = utils.getLogger("FutabaDeviceDriver")
        parsedJson = None

        try:
            logger.debug(f"> Looking for {filePath}")
            with open(filePath, "r", encoding="utf-8") as jsonFile:
                parsedJson = json.load(jsonFile)
            logger.debug("--> loaded!")
        except FileNotFoundError:
            # parsedJson defaults to None
            logger.debug("--> not found, returning >None<")

        return parsedJson

    @staticmethod
    def _getLogger(name="FutabaDeviceDriver", state="CLASS"):
        """Properly namespace the logger and return it

        Args:
            name (str, optional): The name used as a label in the log file. Defaults to "FutabaDeviceDriver".
            state (str, optional): Appended to the name in the log file inside of parenthesis. Defaults to "CLASS".

        Returns:
            logger.logger: The logger instantiated for this class
        """
        return utils.getLogger(f"{name} -= {state} =-")

    @classmethod
    def _generateChannelMaps(cls, channelCalibrations):
        """Use the channelCalibrations to generate a calibrated map for each channel

        Args:
            channelCalibrations (Array of Array): The first will contain exactly 2 values, the start and end of the spectrum of possible input values. The second will contain exactly 2 values, the start and end of the spectrum of possible output values. Defaults to self.channelCalibrations

        Returns:
            Array of Array of Array: The calibrated channel maps
        """

        calibratedChannels = []
        for channelCalibration in channelCalibrations:
            inputRange = channelCalibration[0]
            outputRange = channelCalibration[1]
            calibratedChannels.append(cls._calculateValueMap(inputRange, outputRange))
        return calibratedChannels

    @classmethod
    def _loadConfig(cls, productName):
        """Loads the settings for this particular device and falls back
        to the default config file if one doesn't exist

        Returns:
            dict: A dictionary containing the driver settings
        """
        logger = cls._getLogger(name=productName)
        config = None

        filePath = os.path.join(utils.CONFIG_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CONFIG_PATH, "default.json")

        logger.debug(f"loading {filePath}")
        config = cls._loadJsonFile(filePath)

        if config is None:
            logger.debug(f"device config not found, loading {defaultPath}")
            config = cls._loadJsonFile(defaultPath)
        if config is None:
            logger.debug("using hard-coded defaults")
            config = DEFAULT_CONFIG

        logger.debug(f"config={config}")
        return config

    @classmethod
    def _loadCalibration(cls, productName):
        """Loads the calibration file for the given product

        Args:
            productName (str, optional): The name of the product to load the calibration for. Defaults to None.

        Returns:
            list of list: Each inner list will contain exactly 2 items, each of which are lists.
        """
        logger = cls._getLogger(name=productName)

        filePath = os.path.join(utils.CALIBRATION_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CALIBRATION_PATH, "default.json")

        logger.debug(f"loading {filePath}")
        channelCalibrations = cls._loadJsonFile(filePath)

        if channelCalibrations is None:
            logger.debug(f"loading{defaultPath}")
            channelCalibrations = cls._loadJsonFile(defaultPath)
        if channelCalibrations is None:
            logger.debug("using hard-coded defaults")
            channelCalibrations = DEFAULT_CALIBRATION

        logger.debug(f"channelCalibrations={channelCalibrations}")
        return channelCalibrations
