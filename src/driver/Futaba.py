"""Class representing a single Futaba USB adapater"""

import atexit
import os

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

EVENT_MAX_VALUE = 32768
EVENT_MIN_VALUE = 0

DEFAULT_CALIBRATION = [
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
    [[704, 3392], [EVENT_MIN_VALUE, EVENT_MAX_VALUE]],
]

FUTABA_VENDOR_ID = 4101


class FutabaDeviceDriver:
    """Provides a class-based interface for the Futaba device at the address specified"""

    def start(self):
        """Start the driver"""

        if self.usbHandle.is_kernel_driver_active(0):
            self.usbHandle.detach_kernel_driver(0)
        self.usbHandle.set_configuration()

        self.logger.info(f"Driver started: {self.interruptEndpoint} -> {self.name}")
        try:
            self._eventLoop()  # Block indefinitely

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

    @staticmethod
    def getConfig(productName):
        """Loads the settings for this particular device and falls back
        to the default config file if one doesn't exist

        Returns:
            dict: A dictionary containing the driver settings
        """
        logger = utils.getLogger("FutabaDeviceDriver")
        config = None

        filePath = os.path.join(utils.CONFIG_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CONFIG_PATH, "default.json")

        logger.debug(f"loading {filePath}")
        config = utils.loadJsonFile(filePath)

        if config is None:
            logger.debug(f"device config not found, loading {defaultPath}")
            config = utils.loadJsonFile(defaultPath)
        if config is None:
            logger.debug("using hard-coded defaults")
            config = DEFAULT_CONFIG

        logger.debug(f"config={config}")
        return config

    @staticmethod
    def getCalibration(productName):
        """Loads the calibration file for the given product

        Args:
            productName (str, optional): The name of the product to load the calibration for. Defaults to None.

        Returns:
            list of list: Each inner list will contain exactly 2 items, each of which are lists.
        """
        logger = utils.getLogger("FutabaDeviceDriver")

        filePath = os.path.join(utils.CALIBRATION_PATH, f"{productName}.json")
        defaultPath = os.path.join(utils.CALIBRATION_PATH, "default.json")

        logger.debug(f"loading {filePath}")
        channelCalibrations = utils.loadJsonFile(filePath)

        if channelCalibrations is None:
            logger.debug(f"loading{defaultPath}")
            channelCalibrations = utils.loadJsonFile(defaultPath)
        if channelCalibrations is None:
            logger.debug("using hard-coded defaults")
            channelCalibrations = DEFAULT_CALIBRATION

        logger.debug(f"channelCalibrations={channelCalibrations}")
        return channelCalibrations

    @classmethod
    def _generateCalibrationMaps(cls, channelCalibrations):
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

    def _eventLoop(self):
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

    def __init__(self, bus=None, port=None, name=None):
        self.runFlag = False
        self.logger = utils.getLogger("driver")
        self.logger.debug("Attempting to instantiate FutabaDeviceDriver")
        self.usbHandle = None
        for device in usb.core.find(find_all=True):
            if int(device.bus) == int(bus) and int(device.port_number) == int(port):
                self.usbHandle = device

        if self.usbHandle is None:
            raise RuntimeError("Could not locate the specified device!")

        self.logger.debug("Attempting to find interrupt endpoint")
        self.interruptEndpoint = utils.getInterruptAddress(self.usbHandle)
        self.logger.debug("Attempting to load device configuration")
        self.config = self.getConfig(self.usbHandle.product)
        self.logger.debug("Attempting to load device calibration")
        self.calibratedChannelMaps = self._generateCalibrationMaps(
            self.getCalibration(self.usbHandle.product)
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
                lambda event: event + (0, EVENT_MAX_VALUE, 0, 0),
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
