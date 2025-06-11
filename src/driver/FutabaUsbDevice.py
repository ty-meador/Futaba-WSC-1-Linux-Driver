"""Class representing a single Futaba USB adapater"""

import atexit
import json
import os

import uinput
import usb
import utils


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

    def __init__(
        self,
        vendorID=None,
        productID=None,
        bus=None,
        port=None,
        name=None,
    ):
        self.state = "initializing"
        atexit.register(self.stop)

        if vendorID is None:
            vendorID = 4104  # Futaba
        if productID is None:
            productID = 10  # WSC-1
        if bus is None:
            raise TypeError("You must specify the bus of the device")
        if port is None:
            raise TypeError("You must specify the port of the device")

        devices = usb.core.find(
            find_all=True,
            idVendor=vendorID,
            idProduct=productID,
        )

        if devices is None:
            self.stop(1)

        self.usbHandle = None
        for device in devices:
            if int(device.bus) == int(bus) and int(device.port_number) == int(port):
                self.usbHandle = device

        if self.usbHandle is None:
            raise RuntimeError("Could not locate the specified device!")

        self.usbEndpoint = self.findEndpoint(self.usbHandle)
        self.name = name
        if self.name is None:
            self.name = f"{self.usbHandle.manufacturer}-{self.usbHandle.product}({self.usbEndpoint})"
        self.logName = self.name.replace(" ", "_").strip().upper()
        self.productName = self.usbHandle.product.strip().upper().replace(" ", "-")
        self.logger = utils.generateLogger(self.logName)
        self.config = self.loadConfig()
        self.calibration = self.loadCalibration()
        # self.smap = interp1d([595, 3510], [0, 32768])
        # self.tmap = interp1d([608, 3251], [0, 32768])
        self.tmap = lambda x: self.interpolate(x, 620, 3300)
        self.smap = lambda x: self.interpolate(x, 600, 3495)
        self.gmap = lambda x: x
        # self.gmap = lambda x: self.interpolate(x, 704, 3392)
        self.frameSize = self.config["frame_size"]
        self.eventMaxValue = self.config["event_max_value"]
        # 8 channels
        self.eventList = [
            uinput.ABS_X,
            uinput.ABS_Y,
            uinput.ABS_RX,
            uinput.ABS_RY,
            uinput.ABS_THROTTLE,
            uinput.ABS_RUDDER,
            uinput.ABS_TILT_X,
            uinput.ABS_TILT_Y,
        ]
        self.valueMaps = [
            self.gmap,
            self.gmap,
            self.gmap,
            self.gmap,
            self.gmap,
            self.gmap,
            self.tmap,
            self.smap,
        ]
        # Default to no reversed inputs
        self.eventReverseFlag = [False] * len(self.eventList)
        # self.channelCalibrations = [interp1d([], [])]

        self.logger.info(f"Found {self.name}")

        events = tuple(
            map(lambda event: event + (0, self.eventMaxValue, 0, 0), self.eventList)
        )

        self.virtualDevice = uinput.Device(
            events,
            self.name,
            vendor=self.usbHandle.idVendor,
        )
        self.logger.info(f"created on usb endpoint {self.usbEndpoint}")
        self.state = "ready"

    def __str__(self):
        return f"{self.name} driver"

    def __repr__(self):
        return self.usbHandle

    def interpolate(self, value, low, high):
        """Guarantees that the value falls between 0 and 32768 based on a provided hight and low calibration"""
        if value < low:
            return 0
        elif value > high:
            return 32768
        else:
            return int(((value - low) / (high - low)) * 32768)

    def loadConfig(self):
        """Loads the settings for this particular device and falls back
        to the default config file if one doesn't exist

        Returns:
            dict: A dictionary containing the driver settings
        """
        logger = self.logger
        productName = self.productName
        logger.debug("loading config")
        logger.debug("Setting up path to default config file...")
        defaultFileName = "default.json"
        defaultFilePath = os.path.join(utils.getConfigsPath(), defaultFileName)
        logger.debug("-> Done!")

        config = None
        try:
            configFileName = f"{productName}.json"
            configFilePath = os.path.join(utils.getConfigsPath(), configFileName)

            logger.debug("Attempting to load config file...")
            with open(configFilePath, "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
            logger.debug(f"...{configFileName} loaded!")
        except FileNotFoundError:
            logger.debug(f"-> {configFileName} not found, loading default config...")
            with open(defaultFilePath, "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
            logger.debug(f"-> {defaultFileName} loaded!")
        finally:
            if config is None:
                raise FileNotFoundError(
                    f"Unable to load {configFileName} or {defaultFileName}!"
                )
        return config

    def loadCalibration(self):
        """Loads the calibration file for this device"""
        calibration = None
        productName = self.productName
        calibrationFileName = f"{productName}.json"
        calibrationFilePath = os.path.join(
            utils.getCalibrationsPath(),
            calibrationFileName,
        )
        defaultFileName = "default.json"
        defaultFilePath = os.path.join(
            utils.getCalibrationsPath(),
            defaultFileName,
        )

        try:
            with open(calibrationFilePath, "r", encoding="utf-8") as calibFile:
                calibration = json.load(calibFile)
        except FileNotFoundError:
            with open(defaultFilePath, "r", encoding="utf-8") as calibFile:
                calibration = json.load(calibFile)
        finally:
            if calibration is None:
                raise FileNotFoundError(
                    f"Unable to load {calibrationFileName} or {defaultFileName}"
                )
        return calibration

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
            raise ValueError(
                "The device provided to _findEndpoint is not of type usb.core.Device"
            )
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

    def parseDataFrame(self, data):
        """Parses the provided data frame into an ordered list of channel data frames

        Args:
            data (dataFrame): A data frame from the physical device

        Returns:
            list: Ordered list of channel data frames
        """
        try:
            # remap data from (min 704, center 2048, max 3392) -> (min 0, center 16384, max 32768)
            channelData = [
                (
                    self.valueMaps[i // 2](
                        int.from_bytes(data[i : i + 2], byteorder="little")
                    )
                )
                for i in range(0, len(data), 2)
            ]
            channelData.reverse()
            self.logger.debug(channelData)
            return channelData
        except Exception as e:
            self.logger.debug(e)

    # def _parseDataFrame_DEBUG(self, data):
    #     _c = [
    #         int.from_bytes(data[i : i + 2], byteorder="little")
    #         for i in range(0, len(data), 2)
    #     ]
    #     # remap data from (min 704, center 2048, max 3392) -> (min 0, center 16384, max 32768)
    #     channelData = [
    #         (int.from_bytes(data[i : i + 2], byteorder="little") - 704) * 256 // 21
    #         for i in range(0, len(data), 2)
    #     ]
    #     self.logger.debug(f"s: {_c[7]}, t: {_c[6]}")
    #     channelData.reverse()
    #     return channelData

    def sendDataFrame(self, data):
        """Sends the provided list of data packets to our virutal device

        Args:
            data (list): A list where each index represents a single channel. Each item will be a data
            packet from the physical device
        """
        eventMaxVal = self.eventMaxValue
        eventList = self.eventList
        reverseFlags = self.eventReverseFlag
        vDevice = self.virtualDevice
        # Queue one event for each channel
        for _, (
            channelData,
            event,
            reverseFlag,
        ) in enumerate(
            zip(
                data,
                eventList,
                reverseFlags,
            )
        ):
            # Reverse the input if necessary
            if reverseFlag:
                channelData = eventMaxVal - channelData
            # queue channel event
            vDevice.emit(event, channelData, syn=False)
            # self.logger.debug(f"parsed events {channelData}")
        # Synchronize (fire all queued events)
        vDevice.syn()

    def start(self):
        """Start the driver"""
        try:
            if self.state != "ready":
                raise Exception(
                    "Attempted to start a FutabaUSBDevice before the driver was in the ready state"
                )

            usbHandle = self.usbHandle
            endpoint = self.usbEndpoint
            frameSize = self.frameSize
            parseDataFrame = self.parseDataFrame
            sendDataFrame = self.sendDataFrame
            logger = self.logger
            stop = self.stop
            name = self.name
            if usbHandle.is_kernel_driver_active(0):
                usbHandle.detach_kernel_driver(0)

            # self.logger.debug("-> Using default configuration...")
            usbHandle.set_configuration()

            if endpoint is None:
                logger.critical(
                    f"Unable to find usb endpoint using the handle >{usbHandle}<"
                )
                stop(1)

            logger.info(f"Driver started: {endpoint} -> {name}")

            while True:
                try:
                    # read frame from HW device
                    dataFrame = usbHandle.read(
                        endpoint,
                        frameSize,
                        timeout=1000,  # typically timeouts are caused by the transmitter not being connected to the dongle though an idle transmitter may also cause a timeout
                    )
                    # Parse channel data from HW frame
                    channelData = parseDataFrame(dataFrame)
                    # Send channel data to virtual device
                    sendDataFrame(channelData)
                except usb.core.USBError as e:
                    # expectedErrors = [
                    #     110  # Transmitter not connected to dongle
                    # ]
                    #
                    # if e.errno not in expectedErrors:

                    # kaboom?
                    if e.errno != 110:
                        # Yes Rico, kaboom.
                        self.state = "critical-usb-error"
                        logger.critical(e)
                        raise e
        except usb.core.USBError as e:
            if e.errno == 13:  # Access denied - permissions issue
                self.state = "critical-insufficient-permissions"
                logger.critical("Insufficient permissions to hook USB interface")
                # self.stdout("Drivers must be run as root")
                raise RuntimeError(
                    "Insufficient permissions to hook USB interface"
                ) from e
        finally:
            stop()

    def stop(self, exitCode=None):
        """Stop the driver"""
        logger = self.logger
        usbHandle = self.usbHandle

        try:
            logger.debug("Releasing the USB interface...")
            usb.util.release_interface(usbHandle, 0)
        except Exception as e:
            logger.warning(
                "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.error(e)

        try:
            logger.debug("Reattaching the kernel driver...")
            usbHandle.attach_kernel_driver(0)
        except Exception as e:
            logger.warning(
                "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.error(e)

        try:
            logger.debug("Resetting device...")
            usbHandle.reset()
        except Exception as e:
            logger.warning(
                "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.error(e)

        if exitCode is not None:
            exit(exitCode)
