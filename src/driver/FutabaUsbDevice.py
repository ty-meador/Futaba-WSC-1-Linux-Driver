"""Class representing a single Futaba USB adapater"""

import array
import atexit
import json
import os

import numpy as np
import uinput
import usb
import utils

PRODUCTS = {
    "default": 999,
    "WSC-1": 10,
    "T16IZ": 11,
    10: "WSC-1",
    11: "T16IZ",
    999: "default",
}

DEFAULT_CONFIG = {
    "frame_size": 16,
    "event_max_value": 32768,
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
    [[704, 3392], [0, 32768]],
    [[704, 3392], [0, 32768]],
    [[704, 3392], [0, 32768]],
    [[704, 3392], [0, 32768]],
    [[704, 3392], [0, 32768]],
    [[704, 3392], [0, 32768]],
    [[704, 3392], [0, 32768]],
    [[704, 3392], [0, 32768]],
]

FUTABA_VENDOR_ID = 4101


class FutabaUsbDevice:
    """Provides a class-based interface for the Futaba device at the address specified"""

    def __init__(self, bus=None, port=None, name=None):
        self.runFlag = False
        self.logger = utils.getLogger("driver")
        self.logger.debug("Attempting to instantiate FutabaUsbDevice")
        self.usbHandle = None
        for device in usb.core.find(find_all=True):
            if int(device.bus) == int(bus) and int(device.port_number) == int(port):
                self.usbHandle = device

        if self.usbHandle is None:
            raise RuntimeError("Could not locate the specified device!")

        self.logger.debug("Attempting to find interrupt endpoint")
        self.interruptEndpoint = self.findEndpoint(self.usbHandle)
        self.logger.debug("Attempting to load device configuration")
        self.config = self.loadConfig()
        self.logger.debug("Attempting to load device calibration")
        self.calibratedChannelMaps = self.generateCalibrationMaps(
            self.loadCalibration()
        )

        self.name = name
        if self.name is None:
            self.name = f"{self.usbHandle.manufacturer}-{self.usbHandle.product}({self.interruptEndpoint})"

        self.channelEvents = []
        for evtName in self.config["channel_events"]:
            self.channelEvents.append(getattr(uinput, evtName))

        # Default to no reversed inputs
        self.eventReverseFlags = [False] * len(self.channelEvents)

        events = tuple(
            map(
                lambda event: event + (0, self.config["event_max_value"], 0, 0),
                self.channelEvents,
            )
        )

        self.virtualDevice = uinput.Device(
            events,
            self.name,
            vendor=self.usbHandle.idVendor,
        )

        self.logger.debug("Virtual driver started:")
        self.logger.debug(f"-> bus={bus}")
        self.logger.debug(f"-> channelEvents: {self.channelEvents}")
        self.logger.debug(f"-> config: {self.config}")
        self.logger.debug(f"-> interruptEndpoint: {self.interruptEndpoint}")
        self.logger.debug(f"-> name: {self.name}")
        self.logger.debug(f"-> port={port}")
        self.logger.debug(f"-> reverseFlags: {self.eventReverseFlags}")
        self.logger.debug(f"-> virtualDevice: {self.virtualDevice}")
        atexit.register(self.stop)

    def __str__(self):
        return f"{self.name} driver"

    def __repr__(self):
        return str(self.usbHandle)

    def loadConfig(self, productName=None):
        """Loads the settings for this particular device and falls back
        to the default config file if one doesn't exist

        Returns:
            dict: A dictionary containing the driver settings
        """
        logger = self.logger
        config = None

        if productName is None:
            productName = self.usbHandle.product

        filePath = os.path.join(utils.CONFIG_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CONFIG_PATH, "default.json")

        logger.debug(f"loading {filePath}")
        config = self.loadJsonFile(filePath)

        if config is None:
            logger.debug(f"device config not found, loading {defaultPath}")
            config = self.loadJsonFile(defaultPath)
        if config is None:
            logger.debug("using hard-coded defaults")
            config = DEFAULT_CONFIG

        logger.debug(f"config={config}")
        return config

    def loadCalibration(self, productName=None):
        """Loads the calibration file for the given product

        Args:
            productName (str, optional): The name of the product to load the calibration for. Defaults to None.

        Returns:
            list of list: Each inner list will contain exactly 2 items, each of which are lists.
        """
        logger = self.logger
        if productName is None:
            productName = self.usbHandle.product

        filePath = os.path.join(utils.CALIBRATION_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CALIBRATION_PATH, "default.json")

        logger.debug(f"loading {filePath}")
        channelCalibrations = self.loadJsonFile(filePath)

        if channelCalibrations is None:
            logger.debug(f"loading{defaultPath}")
            channelCalibrations = self.loadJsonFile(defaultPath)
        if channelCalibrations is None:
            logger.debug("using hard-coded defaults")
            channelCalibrations = DEFAULT_CALIBRATION

        logger.debug(f"channelCalibrations={channelCalibrations}")
        return channelCalibrations

    def loadJsonFile(self, filePath):
        """Generic function to load a JSON file into a dictionary

        Args:
            filePath (str): The path to the json file you want to load

        Returns:
            dict: The parsed json
        """
        logger = self.logger
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

    def findEndpoint(self, device):
        """_summary_

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

    def generateCalibrationMaps(self, channelCalibrations):
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
            calibratedChannels.append(self.calculateValueMap(inputRange, outputRange))
        return calibratedChannels

    def calculateValueMap(self, inputRange, outputRange):
        """Generate a list of values that maps the input range to the output range

        Args:
            inputRange (list, optional): This determines the size of the map. Defaults to [600, 3500].
            outputRange (list, optional): This determines what values are generated in the map. Defaults to [0, 32768].

        Returns:
            list: A list of all possible output values given the range of input values
        """
        if not hasattr(inputRange, "__len__") or len(inputRange) != 2:
            raise TypeError(
                "inputRange must be an array of length 2, using defaults instead"
            )
        if not hasattr(outputRange, "__len__") or len(outputRange) != 2:
            raise TypeError(
                "outputRange must be an array of length 2, using defaults instead"
            )
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
            "I",
            np.round(
                np.interp(
                    inputValues,
                    inputRange,
                    outputRange,
                ),
                0,  # Round to the nearest int
            ).astype(int),
        )

    def eventLoop(self):
        """The main event loop of the driver - INDEFINITELY BLOCKING OPERATION"""
        # Define variables before loop so we don't waste time creating
        # a new variable each iteration and the interpreter doesn't have
        # to evaluate dots, dict subscripts etc etc
        self.runFlag = True
        calibration = None
        calibrationMaps = self.calibratedChannelMaps
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
        reverseFlags = self.eventReverseFlags
        synchronize = self.virtualDevice.syn

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
                    maxInputVal = len(calibration) - 1
                    if rawValue > maxInputVal:
                        rawValue = maxInputVal
                    elif rawValue < 0:
                        rawValue = 0
                    # Extract calibrated value from map
                    channelData.append(calibration[rawValue])
                channelData.reverse()

                # Queue one event for each channel
                for data, event, reverseFlag in zip(
                    channelData, channelEvents, reverseFlags
                ):
                    if reverseFlag:
                        data = eventMaxVal - data
                    emit(event, data, syn=False)

                # fire all queued events
                synchronize()
            except usb.core.USBError as e:
                # kaboom?
                if e.errno != 110:
                    # Yes Rico, kaboom.
                    logger.critical(e)
                    raise e

    def start(self):
        """Start the driver"""

        if self.usbHandle.is_kernel_driver_active(0):
            self.usbHandle.detach_kernel_driver(0)
        self.usbHandle.set_configuration()

        self.logger.info(f"Driver started: {self.interruptEndpoint} -> {self.name}")
        try:
            self.eventLoop()  # Block indefinitely

        except usb.core.USBError:
            pass
        finally:
            self.stop()

    def stop(self, exitCode=None):
        """Stop the driver if it is running

        Args:
            exitCode (int, optional): If provided the driver will exit with this code. Defaults to None.
        """
        self.runFlag = False

        try:
            self.logger.debug("Releasing the USB interface...")
            usb.util.release_interface(self.usbHandle, 0)
        except Exception as e:
            self.logger.warning(
                "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            self.logger.warning(e)

        try:
            self.logger.debug("Reattaching the kernel driver...")
            self.usbHandle.attach_kernel_driver(0)
        except Exception as e:
            self.logger.warning(
                "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)"
            )
            self.logger.warning(e)

        try:
            self.logger.debug("Resetting device...")
            self.usbHandle.reset()
        except Exception as e:
            self.logger.warning(
                "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            self.logger.warning(e)

        if exitCode is not None:
            exit(exitCode)
