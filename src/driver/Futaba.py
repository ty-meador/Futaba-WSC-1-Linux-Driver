"""Class representing a single Futaba USB adapater"""

import atexit
import json
import multiprocessing
import os

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
        if (
            self.subProc is not None
            and isinstance(self.subProc, multiprocessing.Process)
            and self.subProc.is_alive()
        ):
            self.state = "RUNNING"
        else:
            self.state = "IDLE"
        return self.state

    def start(self):
        """Start the driver if it is not running"""

        try:
            self.subProc = multiprocessing.Process(
                name=f"{self.name} Driver",
                target=_EVENTLOOP,
                args=(self.killswitch,),
                kwargs=self.toDict(),
            )
            self.subProc.start()

        except usb.core.USBError:
            # Don't raise exception, pass through to finally block
            pass
        finally:
            self.stop()

        return self.subProc.is_alive()

    def stop(self):
        """Stop the driver"""
        self.killswitch.set()
        self.subProc.join()
        self._setState("IDLE")

    def toDict(self):
        """Returns a dictionary representation of the driverf object"""
        return {
            "calibration": self.calibration,
            "channelEvents": self.channelEvents,
            "config": self.config,
            "endpointAddress": self.interruptEndpoint,
            "name": self.name,
            "reverseFlags": self.reverseFlags,
        }

    def _setState(self, state):
        """Set the state of the Object

        Args:
            state (string): The new state of the Object
        """
        self.logger = utils.getLogger(f"{self.name} -= {state} =-")
        self.state = state

    def __init__(self, coreDevice):
        if coreDevice.manufacturer.lower() != "futaba":
            raise RuntimeError("NOT A Futaba DEVICE!")
        self.name = f"Futaba {coreDevice.product}({coreDevice.bus},{coreDevice.port_numbers[0]})"
        self.state = "INITIALIZING"
        self.logger = self._getLogger(name=coreDevice.product, state=self.state)
        self.interruptEndpoint = self._findEndpoint(coreDevice)
        self.subProc = None
        self.killswitch = multiprocessing.Event()
        self.logger.debug("Attempting to load device configuration")
        self.config = self._loadConfig(coreDevice.product)

        # Each channel will have an array that maps the devices raw value to
        # a calibrated value
        self.logger.debug("Attempting to load device calibration")
        self.calibration = self._loadCalibration(coreDevice.product)
        self.channelMaps = self._generateChannelMaps(self.calibration)
        # Attribute names are stored directly in the config file as a string
        self.channelEvents = tuple(
            getattr(uinput, evtName) for evtName in self.config["channel_events"]
        )
        # Default to no reversed inputs
        self.reverseFlags = [False] * len(self.channelEvents)
        self.logger = utils.getLogger(f"{self.name} -= IDLE =-")
        self.logger.debug(self.toDict())
        atexit.register(self.stop)

    def __str__(self):
        return f"{self.name} Driver"

    def __repr__(self):
        return str(self.toDict())

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
            calibratedChannels.append(utils.generateValueMap(inputRange, outputRange))
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


def _EVENTLOOP(
    killswitch,
    calibrationMaps=None,
    channelEvents=None,
    config=None,
    bus=None,
    port=None,
    name=None,
    reverseFlags=None,
):
    """The target function for the drivers subprocess"""
    # Define variables before loop so we don't waste time creating
    # a new variable each iteration and the interpreter doesn't have
    # to evaluate dots, dict subscripts etc etc
    if (
        bus is None
        or calibrationMaps is None
        or channelEvents is None
        or config is None
        or name is None
        or port is None
        or reverseFlags is None
    ):
        raise TypeError("All parameters are required")

    logger = utils.getLogger(name)
    calibration = None
    channel = None
    usbHandle = None
    endpointAddress = None

    logger = utils.getLogger(f"{name}(SUBPROC)")
    logger.DEBUG(
        f"Subprocess started, searching for device {name} on bus {bus}, port {port}"
    )

    coreDevice = [
        device
        for device in usb.core.find(find_all=True)
        if int(device.port_number) == int(port) and int(device.bus_) == int(bus)
    ][0]

    logger.DEBUG(
        f"--> device found ({coreDevice}), searching for interrupt endpoint address"
    )
    for _config in coreDevice:
        for _interface in _config:
            for _endpoint in _interface:
                if (
                    usb.util.endpoint_direction(_endpoint.bEndpointAddress)
                    == usb.util.ENDPOINT_IN
                    and _endpoint.bmAttributes == 0x3
                ):
                    endpointAddress = _endpoint.bEndpointAddress
                    logger.DEBUG(f"----> address found ({endpointAddress})")
                    break
    if coreDevice is None:
        raise TypeError(
            f"Unable to locate A device with an interrupt endpoint at {endpointAddress}"
        )

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple([event + (0, EVENT_MAX_VAL, 0, 0) for event in channelEvents]),
        name,
        vendor=FUTABA_VENDOR_ID,
    )

    # Create all variables outside the loop to avoid the overhead of
    # recreating them each iteration
    emit = virtualDevice.emit
    frameSize = config["frame_size"]
    fromBytes = int.from_bytes

    maxInputVal = None
    rawData = None
    readDevice = coreDevice.read
    synchronize = virtualDevice.syn
    logger.info(f"Driver started: {endpointAddress} -> {name}")

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    while not killswitch.is_set():
        try:
            # - The transmitter may not send a new frame if the inputs remain static
            # - No reason to care about timeouts
            # - - Long timeout length = less timeouts
            # - - Less timeouts = fewer exceptions caught
            # - - Fewer exceptions caught = less overhead
            rawData = readDevice(endpointAddress, frameSize, timeout=1000)

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

            # Queue one event for each channel
            for (
                data,
                event,
                reverseFlag,
            ) in zip(
                channelData,
                channelEvents,
                reverseFlags,
            ):
                if reverseFlag:
                    data = EVENT_MAX_VAL - data
                # Queue one event for each channel
                emit(event, data, syn=False)
            # fire all queued events
            synchronize()
        except usb.core.USBError as e:
            # kaboom?
            if e.errno != 110:
                # Yes Rico, kaboom.
                logger.critical(e)
                raise e
        finally:
            try:
                logger.debug("Releasing the USB interface...")
                usb.util.release_interface(coreDevice, 0)
            except Exception as e:
                logger.warning(
                    "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)"
                )
                logger.warning(e)

            try:
                logger.debug("Reattaching the kernel driver...")
                coreDevice.attach_kernel_driver(0)
            except Exception as e:
                logger.warning(
                    "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)"
                )
                logger.warning(e)

            try:
                logger.debug("Resetting device...")
                coreDevice.reset()
            except Exception as e:
                logger.warning(
                    "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)"
                )
                logger.warning(e)
