"""Class representing a single Futaba USB adapater"""

import array
import atexit
import json
import os
import subprocess

import numpy as np
import uinput
import usb

from driver import utils

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

##
# Credit to https://github.com/shaozu/Futaba_T16IZ_Linux/blob/main/entry.py
# for this great starting point!
##
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

    def getDeviceList(self):
        """Returns an ordered list of devices

        Returns:
            tuple of string: Ordered list of available devices
        """
        return tuple(map(lambda device: device.name, self.futabaDevices))

    def getDeviceStatus(self, deviceIndex):
        """Get the status of the device at the given index

        Args:
            deviceIndex (int): The device that you want the status of

        Returns:
            string: "RUNNING" or "IDLE"
        """
        if self._deviceIsRunning(self.futabaDevices[deviceIndex]):
            return "RUNNING"
        return "IDLE"

    def __init__(self):
        atexit.register(self._stopAllDrivers)
        self.logger = utils.getLogger(self.__class__)
        self.startCmds = []
        self.futabaDevices = tuple(
            map(
                self._initializeCoreDevice,
                [
                    device
                    for device in usb.core.find(find_all=True)
                    if device.manufacturer.lower() == "futaba"
                ],
            )
        )
        if len(self.futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

    @staticmethod
    def _initializeCoreDevice(device):
        """Appends the properties required for this driver to the provided device

        Args:
            device (usb.core.Device): The device to modify

        Returns:
            usb.core.Device: The modified device
        """
        device.name = f"{device.manufacturer} {device.product} (bus-{device.bus}, port-{device.port_number})"
        device.subproc = None
        device.startCmd = (
            "python3",
            "driver/start",
            "--bus",
            str(device.bus),
            "--port",
            str(device.port_number),
            "--use-name",
            device.name,
        )
        return device

    @staticmethod
    def _deviceIsRunning(futabaDevice):
        """Function to determine if a given device is actively running

        Args:
            futabaDevice (core.usb.Device): The device to check

        Returns:
            bool: True if the device has a subprocess
        """
        return (
            hasattr(futabaDevice, "subproc")  # Has device been initialized?
            and futabaDevice.subproc is not None  # Is there a subproc attached to it?
            and futabaDevice.poll() is None  # Is the subproc alive?
        )

    def _getIdleDevices(self, futabaDevices=None):
        """Gets a list of devices that are not running

        Args:
            futabaDevices (array of usb.core.Device, optional): The devices to filter. Defaults to self.futabaDevices.

        Returns:
            list of usb.core.Device: Filtered list containing only devices that are not actively running
        """
        if futabaDevices is None:
            futabaDevices = self.futabaDevices
        return filter(not self._deviceIsRunning, futabaDevices)

    def _getRunningDevices(self, futabaDevices=None):
        """Returns a list of running futaba devices

        Args:
            futabaDevices (list of usb.core.Device, optional): List of devices to filter. Defaults to all found devices.

        Returns:
            _type_: _description_
        """
        if futabaDevices is None:
            futabaDevices = self.futabaDevices
        return filter(self._deviceIsRunning, futabaDevices)

    def _startDriver(self, futabaDevice):
        """start a single device"""
        return subprocess.Popen(
            futabaDevice.startCmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _startDrivers(self, futabaDevices):
        """Starts all Futaba devices provided

        Args:
            futabaDevices (list of usb.core.Device): A list of Futaba USB device handles

        Returns:
            list of subprocess: A list of subprocesses each of which is responsable for
            a single device driver
        """
        return [self._startDriver(device) for device in futabaDevices]

    def _startAllDrivers(self):
        """Starts a driver for all found futaba devices"""
        return self._startDrivers(self.futabaDevices)

    def _stopDriver(self, futabaDevice):
        """Stops a single device driver

        Args:
            futabaDevice (usb.core.Device): a futaba device
        """
        if self._deviceIsRunning(futabaDevice):
            # Ask nicely
            try:
                futabaDevice.subproc.terminate()
                futabaDevice.subproc.wait(timeout=5)
                futabaDevice.subproc = None
            except Exception as e:
                self.logger.error(e)

        if self._deviceIsRunning(futabaDevice):
            # Ask not so nicely
            try:
                futabaDevice.subproc.kill()
                futabaDevice.subproc.wait(timeout=5)
                futabaDevice.subproc = None
            except Exception as e:
                self.logger.error(e)
        return futabaDevice

    def _stopDrivers(self, futabaDevices):
        """Takes a list of futaba devices and stops any driver subprocesses that are attached to them

        Args:
            futabaDevices (list of usb.core.Device): List of Futaba devices
        """
        # blocks waiting for each subproc to end
        return map(self._stopDriver, filter(self._deviceIsRunning, futabaDevices))

    def _stopAllDrivers(self):
        """Stops all running drivers"""
        return self._stopDrivers(self.futabaDevices)


class Driver:
    """Provides a class based interface for a single Futaba USB device"""

    def __init__(self, bus=None, port=None, name=None):
        atexit.register(self.stop)
        self.runFlag = False
        self.logger = utils.getLogger("driver")
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

    def calculateValueMap(
        self,
        # These values appear to work well for at least the WSC-1 and T16IZ
        # making them the safest known values so far
        inputRange=None,
        outputRange=None,
    ):
        """Generate a list of values that maps the input range to the output range

        Args:
            inputRange (list, optional): This determines the size of the map. Defaults to [600, 3500].
            outputRange (list, optional): This determines what values are generated in the map. Defaults to [0, 32768].

        Returns:
            list: A list of all possible output values given the range of input values
        """
        if not hasattr(inputRange, "__len__") or len(inputRange) != 2:
            self.logger.error(
                "inputRange must be an array of length 2, using defaults instead"
            )
            inputRange = [600, 3500]
        if not hasattr(outputRange, "__len__") or len(outputRange) != 2:
            self.logger.error(
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
            "I",
            np.round(
                np.interp(
                    inputValues,
                    inputRange,
                    outputRange,
                ),
                0,
            ).astype(int),
        )
        # return np.round(np.interp(inputValues, inputRange, outputRange), 0).astype(int)

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

    def start(self):
        """Start the driver"""

        endpoint = self.interruptEndpoint

        logger = self.logger
        name = self.name

        usbHandle = self.usbHandle
        if usbHandle.is_kernel_driver_active(0):
            usbHandle.detach_kernel_driver(0)
        usbHandle.set_configuration()

        logger.info(f"Driver started: {endpoint} -> {name}")
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
