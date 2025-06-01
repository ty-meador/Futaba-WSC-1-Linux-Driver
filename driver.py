"""
https://github.com/pyusb/pyusb/blob/master/docs/tutorial.rst
"""

import asyncio
import json
import logging
import logging.handlers
import os
import time

import uinput
import usb


def generateLogger(
    name,
    maxSize=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
    level=logging.WARNING,
):
    """Generates a logger

    Args:
        name (str): _description_
        maxSize (int, optional): Max file size of log files. Defaults to 5*1024*1024.
        backupCount (int, optional): Number of backup logs to keep in rotation. Defaults to 5
        level (loglevel, optional): The level the logger should output. Defaults to logging.WARNING.

    Returns:
        logger: The generated logger
    """
    handler = logging.handlers.RotatingFileHandler(
        f"{name}.log", maxBytes=maxSize, backupCount=backupCount
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


class FutabaUsbDeviceDriver:
    def __init__(self):
        self.logger = generateLogger("driver")
        self.eventLoop = asyncio.get_event_loop()
        self.coroutines = []
        self.devices = []
        self.startQueue = []
        futabaDevices = []
        usbDevices = usb.core.find(find_all=True)

        # Ensure default config file exists
        if not os.path.exists("default_config.json"):
            self.generateDefaultConfigFile()
        else:  # Is the default file sane?
            try:
                with open("default_config.json", "r", encoding="utf-8") as cfgFile:
                    json.load(cfgFile)
            except Exception:
                # Delete the existing default config and regenerate it
                self.generateDefaultConfigFile(forceRegenerate=True)

        for device in usbDevices:
            if device.manufacturer.lower() == "futaba":
                futabaDevices.append(FutabaUsbDevice(device))

        if len(futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

        self.devices = futabaDevices

    def __str__(self):
        return f"Devices: {self.devices}"

    def __repr__(self):
        return f"Devices: {self.devices}"

    def _sanityChecks(self):
        # Ensure default config file exists
        if not os.path.exists("default_config.json"):
            self._generateDefaultConfigFile()
        else:  # Is the default file sane?
            try:
                with open("default_config.json", "r", encoding="utf-8") as cfgFile:
                    json.loads(cfgFile)
            except Exception:
                # Delete the existing default config and regenerate it
                self._generateDefaultConfigFile(forceRegenerate=True)

    def _generateDefaultConfigFile(self, forceRegenerate=False):
        """Regenerates the default config file

        Args:
            forceRegenerate (bool, optional): If true the existing configuration file will be deleted and a new one will be created using default values. Defaults to False.
        """
        fileName = "default_config.json"
        backupFileName = f"{fileName}.{time.time()}.BACKUP"

        self.logger.info("Attempting to generate the default config file...")
        if os.path.exists(fileName):
            self.logger.warning("Default config file already exists...")
            # Force regenerate will delete the existing file and generate a
            # new one from scratch
            if forceRegenerate is True:
                os.rename(fileName, backupFileName)
                self.logger.warning(
                    f"-> Force regnerating default config file: your config file was backed up to {backupFileName}"
                )
            else:  # file exists, not force regenerating - do nothing
                return

        # A dict with a 1:1 representation of the JSON file that will be generated...
        defaultConfig = {"frame_size": 16, "event_max_value": 32768}

        # ...told ya
        with open(fileName, "w", encoding="utf-8") as cfgFile:
            cfgFile.write(json.dumps(defaultConfig, indent=4))

    async def startAll(self):
        """_summary_"""
        for device in self.devices:
            self.startQueue.append(
                await self.eventLoop.run_in_executor(None, device.start)
            )

    async def stopAll(self):
        for device in self.devices:
            self.coroutines.append(device.stop())
        return asyncio.gather(self.coroutines)


class FutabaUsbDevice:
    """
    Example:
            DEVICE ID 1008:000a on Bus 001 Address 002 =================
                bLength                :   0x12 (18 bytes)
                bDescriptorType        :    0x1 Device
                bcdUSB                 :  0x200 USB 2.0
                bDeviceClass           :    0x0 Specified at interface
                bDeviceSubClass        :    0x0
                bDeviceProtocol        :    0x0
                bMaxPacketSize0        :   0x40 (64 bytes)
                idVendor               : 0x1008
                idProduct              : 0x000a
                bcdDevice              :  0x200 Device 2.0
                iManufacturer          :    0x1 Futaba
                iProduct               :    0x2 WSC-1
                iSerialNumber          :    0x3 000000000
                bNumConfigurations     :    0x1
                    CONFIGURATION 1: 500 mA ==================================
                    bLength              :    0x9 (9 bytes)
                    bDescriptorType      :    0x2 Configuration
                    wTotalLength         :   0x22 (34 bytes)
                    bNumInterfaces       :    0x1
                    bConfigurationValue  :    0x1
                    iConfiguration       :    0x0
                    bmAttributes         :   0x80 Bus Powered
                    bMaxPower            :   0xfa (500 mA)
                        INTERFACE 0: Human Interface Device ====================
                        bLength            :    0x9 (9 bytes)
                        bDescriptorType    :    0x4 Interface
                        bInterfaceNumber   :    0x0
                        bAlternateSetting  :    0x0
                        bNumEndpoints      :    0x1
                        bInterfaceClass    :    0x3 Human Interface Device
                        bInterfaceSubClass :    0x0
                        bInterfaceProtocol :    0x0
                        iInterface         :    0x0
                            ENDPOINT 0x87: Interrupt IN ==========================
                            bLength          :    0x7 (7 bytes)
                            bDescriptorType  :    0x5 Endpoint
                            bEndpointAddress :   0x87 IN
                            bmAttributes     :    0x3 Interrupt
                            wMaxPacketSize   :   0x40 (64 bytes)
                            bInterval        :    0x1

    """

    def __init__(self, device=None, defaultConfig="default_config.json"):
        if not isinstance(device, usb.core.Device):
            raise ValueError(
                "Invalid device object provided to the FutabaUsbDevice class"
            )

        self.state = "initializing"
        self.name = f"{device.manufacturer}-{device.product}"
        self.fsSafeName = self.name.replace(
            " ", "_"
        )  # name that is safe for the file system. Used for logs and config files
        self.logger = generateLogger(self.fsSafeName)
        self.usbHandle = device
        self.usbEndpoint = self.getInterruptEndpoint(device)
        self.config = self._loadConfig(defaultConfig=defaultConfig)
        self.frameSize = self.config["frame_size"]
        self.eventMaxValue = self.config["event_max_value"]
        self.eventList = [  # 8 channels
            uinput.ABS_X,
            uinput.ABS_Y,
            uinput.ABS_RX,
            uinput.ABS_RY,
            uinput.ABS_THROTTLE,
            uinput.ABS_RUDDER,
            uinput.ABS_TILT_X,
            uinput.ABS_TILT_Y,
        ]
        self.eventReverseFlag = [False] * len(
            self.eventList
        )  # Default to no reversed inputs

        self.logger.info(f"Found {self.name}")

        events = tuple(
            map(lambda event: event + (0, self.eventMaxValue, 0, 0), self.eventList)
        )

        self.virtualDevice = uinput.Device(
            events, f"Virtual {self.name}", vendor=self.usbHandle.idVendor
        )
        self.logger.info(f"Virtual {self.name} created")
        self.state = "ready"

    def __str__(self):
        return f"Virtual {self.name} driver"

    def __repr__(self):
        return f"name={self.name}, fsSafeName={self.fsSafeName} config={self.config}, eventList={self.eventList}"

    def _stdout(self, msg):
        """prints a message to stdout with an identifying banner

        Args:
            msg (str): The message to output
        """
        print(f"{self.name} -> {msg}")

    def _loadConfig(self, defaultConfig="default_config.json"):
        """Loads the settings for this particular device and falls back
        to the default config file if one doesn't exist

        Returns:
            dict: A dictionary containing the driver settings
        """

        config = None
        try:
            self.logger.debug("Attempting to load config file...")
            with open(f"{self.fsSafeName}.json", "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
            self.logger.debug(f"...{self.fsSafeName}.json loaded!")
        except FileNotFoundError:
            self.logger.debug(f"-> No config found for {self.fsSafeName}...")
            self.logger.debug("-> Loading default config...")
            with open(defaultConfig, "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
        finally:
            if config is None:
                raise FileNotFoundError(
                    f"Unable to load {self.fsSafeName}.json or default_config.json!"
                )
        return config

    def _loadDefaultConfig(self):
        config = None
        with open("default_config.json", "r", encoding="utf-8") as cfgFile:
            config = json.load(cfgFile)
        return config

    def getState(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        return self.state

    def getInterruptEndpoint(self, device):
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
            raise ValueError(
                "The device provided to getInterruptEndpoint is not of type usb.core.Device"
            )
        for config in device:
            for interface in config:
                for endpoint in interface:
                    if (
                        usb.util.endpoint_direction(endpoint.bEndpointAddress)
                        == usb.util.ENDPOINT_IN
                        and endpoint.bmAttributes == 0x3
                    ):
                        return endpoint.bEndpointAddress
        raise RuntimeError("No interrupt endpoint found!")

    def parseDataFrame(self, data):
        """Parses the provided data frame into an ordered list of channel data frames

        Args:
            data (dataFrame): A data frame from the physical device

        Returns:
            list: Ordered list of channel data frames
        """
        try:
            parsed = []
            for i in range(0, len(data), 2):
                # remap data from (min 704, center 2048, max 3392) -> (min 0, center 16384, max 32768)
                channelData = int.from_bytes(data[i : i + 2], byteorder="little")
                channelData = (channelData - 704) * 256 // 21
                parsed.append(channelData)
            parsed.reverse()
        except Exception as e:
            raise ValueError(f"Unable to parse data frame {data}") from e
        self.logger.debug(f"Parsed data frame >{parsed}<")
        return parsed

    def sendDataFrame(self, data):
        """Sends the provided list of data packets to our virutal device

        Args:
            data (list): A list where each index represents a single channel. Each item will be a data
            packet from the physical device
        """
        # Queue one event for each channel
        for i, event in enumerate(self.eventList):
            # for i in range(0, len(self.eventList)):
            channelData = data[i]
            # Reverse the input if necessary
            if self.eventReverseFlag[i]:
                channelData = self.eventMaxValue - data[i]
            # queue channel event
            self.virtualDevice.emit(event, channelData, syn=False)
        # Synchronize (fire all queued events)
        self.virtualDevice.syn()

    def start(self):
        """Start the driver"""
        try:
            self.logger.info(f"Attempting to start virtual {self.name}")
            if self.state != "ready":
                raise Exception(
                    "Attempted to start a FutabaUSBDevice before the driver was in the ready state"
                )

            self.logger.info("-> Detaching kernel driver...")
            if self.usbHandle.is_kernel_driver_active(0):
                self.usbHandle.detach_kernel_driver(0)

            self.logger.info("-> Using default configuration...")
            self.usbHandle.set_configuration()

            if self.usbEndpoint is None:
                self.logger.critical(
                    f"Unable to find usb endpoint using the handle >{self.usbHandle}<"
                )
                self.stop(1)

            self.logger.info(f"Driver started: {self.usbEndpoint} -> {self.name}")

            # Main loop
            while not killswitch.is_set():
                try:
                    # read HW frame
                    hwFrame = self.usbHandle.read(
                        self.usbEndpoint, self.frameSize, timeout=20
                    )
                    # Parse channel data from HW frame
                    channelData = self.parseDataFrame(hwFrame)
                    # Send channel data to virtual device
                    self.sendDataFrame(channelData)
                except usb.core.USBError as e:
                    expectedErrors = [
                        # dongle doesn't detect transmitter - Expected if the batteries die,
                        # it isn't paired to the dongle, isn't on, etc
                        110
                    ]

                    # kaboom?
                    if e.errno not in expectedErrors:
                        # Yes Rico, kaboom.
                        self.state = "critical-usb-error"
                        self.logger.critical(e)
                        raise e
        except usb.core.USBError as e:
            if e.errno == 13:  # Access denied - permissions issue
                self.state = "critical-insufficient-permissions"
                self.logger.critical("Insufficient permissions to hook USB interface")
                self._stdout("Drivers must be run as root")
                raise RuntimeError(
                    "Insufficient permissions to hook USB interface"
                ) from e
        finally:
            self.stop()
            self.logger.info("...Done!")

    def stop(self, exitCode=None):
        """Stop the driver"""
        try:
            self.logger.info("Releasing the USB interface...")
            usb.util.release_interface(self.usbHandle, 0)
        except Exception as e:
            self.logger.warning(
                "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            self.logger.warning(e)

        try:
            self.logger.info("Reattaching the kernel driver...")
            self.usbHandle.attach_kernel_driver(0)
        except Exception as e:
            self.logger.warning(
                "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)"
            )
            self.logger.warning(e)

        try:
            self.logger.info("Resetting device...")
            self.usbHandle.reset()
        except Exception as e:
            self.logger.warning(
                "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            self.logger.warning(e)

        if exitCode is not None:
            exit(exitCode)
