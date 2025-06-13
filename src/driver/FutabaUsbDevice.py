"""Class representing a single Futaba USB adapater"""

import atexit
import json
import os

import numpy as np
import uinput
import usb
import utils

FUTABA_VENDOR_ID = 4101
WSC_1_PRODUCT_ID = 10


class FutabaUsbDevice(usb.core.Device):
    """
    Example:
            # What a Futaba device looks like in LSPCI
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
        channelEvents=None,
        channelCalibrations=None,
        productName=None,
        config=None,
    ):
        atexit.register(self.stop)
        self.logger = utils.generateLogger("driver")

        if bus is None:
            raise TypeError("You must specify the bus of the device")
        if port is None:
            raise TypeError("You must specify the port of the device")
        if vendorID is None:
            vendorID = FUTABA_VENDOR_ID
        if productID is None:
            productID = WSC_1_PRODUCT_ID
        if productName is None:
            productName = "WSC-1"
        if channelEvents is None:
            channelEvents = [
                uinput.ABS_X,
                uinput.ABS_Y,
                uinput.ABS_RX,
                uinput.ABS_RY,
                uinput.ABS_THROTTLE,
                uinput.ABS_RUDDER,
                uinput.ABS_TILT_X,
                uinput.ABS_TILT_Y,
            ]
        if config is None:
            config = self.loadConfig(productName=productName)
        if channelCalibrations is None:
            channelCalibrations = self.loadCalibration(productName=productName)

        devices = usb.core.find(find_all=True)

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
        self.productName = productName
        self.config = config
        self.channelCalibrations = channelCalibrations
        self.frameSize = self.config["frame_size"]
        self.eventMaxValue = self.config["event_max_value"]
        self.channelEvents = channelEvents
        # Default to no reversed inputs
        self.eventReverseFlag = [False] * len(self.channelEvents)

        self.logger.info(f"Found {self.name}")

        events = tuple(
            map(lambda event: event + (0, self.eventMaxValue, 0, 0), self.channelEvents)
        )

        self.virtualDevice = uinput.Device(
            events,
            self.name,
            vendor=self.usbHandle.idVendor,
        )
        self.logger.info(f"created on usb endpoint {self.usbEndpoint}")

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
            productName = self.productName

        configFileName = f"{productName}.json"
        configFilePath = os.path.join(utils.getConfigsPath(), configFileName)
        logger.debug("loading config")
        defaultFileName = "default.json"
        defaultFilePath = os.path.join(utils.getConfigsPath(), defaultFileName)
        logger.debug("-> Done!")

        try:
            logger.debug("Attempting to load config file...")
            with open(configFilePath, "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
            logger.debug(f"-> {configFileName} loaded!")
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

    def loadCalibration(self, productName=None):
        """Loads the calibration file"""
        if productName is None:
            productName = self.productName
        logger = self.logger
        channelCalibrations = None
        calibrationFileName = f"{productName}.json"
        calibrationFilePath = os.path.join(
            utils.getCalibrationsPath(), calibrationFileName
        )

        try:
            with open(calibrationFilePath, "r", encoding="utf-8") as calibFile:
                channelCalibrations = json.load(calibFile)
        except FileNotFoundError:
            logger.warning(
                f"not calibration found for device {productName}, using default calibration"
            )

            defaultFileName = "default.json"
            defaultFilePath = os.path.join(
                utils.getCalibrationsPath(),
                defaultFileName,
            )
            with open(defaultFilePath, "r", encoding="utf-8") as calibFile:
                channelCalibrations = json.load(calibFile)
        finally:
            pass

        return channelCalibrations

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

    def parseDataFrame(self, data, channelCalibrations):
        """Parses the provided data frame into an ordered list of channel data frames

        Args:
            data (dataFrame): A data frame from the physical device

        Returns:
            list: Ordered list of channel data frames
        """
        channelData = [
            (
                int(
                    np.interp(
                        # Interpolate raw data based on calibration
                        int.from_bytes(data[i : i + 2], byteorder="little"),  # Value
                        channelCalibrations[i // 2][0],  # input range
                        channelCalibrations[i // 2][1],  # output range
                    )
                )
            )
            for i in range(0, len(data), 2)
        ]
        channelData.reverse()
        return channelData

    def sendDataFrame(self, data):
        """Sends the provided list of data packets to our virutal device

        Args:
            data (list): A list where each index represents a single channel. Each item will be a data
            packet from the physical device
        """
        eventMaxVal = self.eventMaxValue
        channelEvents = self.channelEvents
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
                channelEvents,
                reverseFlags,
            )
        ):
            channelData = eventMaxVal - channelData if reverseFlag else channelData
            # queue channel event
            vDevice.emit(event, channelData, syn=False)
        # Synchronize (fire all queued events)
        vDevice.syn()

    def start(self):
        """Start the driver"""
        try:
            usbHandle = self.usbHandle
            endpoint = self.usbEndpoint
            frameSize = self.frameSize
            parseDataFrame = self.parseDataFrame
            sendDataFrame = self.sendDataFrame
            logger = self.logger
            stop = self.stop
            name = self.name
            channelCalibrations = self.channelCalibrations
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
                        # R/C transmitters/receivers are based on 2.4Ghz spread
                        # specktrum technology, similar to that used in WiFi.
                        # Unlike WiFi however, The signal is used for real-time
                        # communication with a remotely operated vehicle. As such,
                        # Manufacturers are behooved to minimize latency. They
                        # do this through a combination of highly effecient
                        # (usually proprietary) protocols, and (more
                        # importantly) **by only providing new frames when
                        # necessary**
                        #
                        # Therefore, we don't care about timeouts. The long
                        # timeout length here is actually meant to be a
                        # performance OPTIMIZATION. The transmitter will not
                        # send a new frame if the inputs have not moved -
                        # REGARDLESS OF THE STATE OF THE DEVICE OR VEHICLE
                        timeout=1000,
                    )
                    # Parse channel data from HW frame
                    channelData = parseDataFrame(dataFrame, channelCalibrations)
                    # Send channel data to virtual device
                    sendDataFrame(channelData)
                except usb.core.USBError as e:
                    # kaboom?
                    if e.errno != 110:  # Transmitter timeout - ignore
                        # Yes Rico, kaboom.
                        logger.critical(e)
                        raise e
        except usb.core.USBError as e:
            # Access denied - permissions issue
            if e.errno == 13:
                logger.critical("Insufficient permissions to hook USB interface")
                logger.critical("DRIVER MUST BE RUN WITH SUDO!")
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
            logger.warning(e)

        try:
            logger.debug("Reattaching the kernel driver...")
            usbHandle.attach_kernel_driver(0)
        except Exception as e:
            logger.warning(
                "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.warning(e)

        try:
            logger.debug("Resetting device...")
            usbHandle.reset()
        except Exception as e:
            logger.warning(
                "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)"
            )
            logger.warning(e)

        if exitCode is not None:
            exit(exitCode)


class WSC_1(FutabaUsbDevice):
    """Class for WSC-1 USB adapter"""

    def __init__(
        self,
        bus=None,
        port=None,
        name=None,
    ):
        super().__init__(
            bus=bus,
            port=port,
            name=name,
            productID=10,
            productName="WSC-1",
            channelEvents=[
                uinput.ABS_X,
                uinput.ABS_Y,
                uinput.ABS_RX,
                uinput.ABS_RY,
                uinput.ABS_THROTTLE,
                uinput.ABS_RUDDER,
                uinput.ABS_TILT_X,
                uinput.ABS_TILT_Y,
            ],
        )


class T16IZ(FutabaUsbDevice):
    "Class for T16IZ USB device"

    def __init__(
        self,
        bus=None,
        port=None,
        name=None,
    ):
        super().__init__(
            bus=bus,
            port=port,
            name=name,
            productID=11,
            productName="T16IZ",
            channelEvents=[
                uinput.ABS_X,
                uinput.ABS_Y,
                uinput.ABS_RX,
                uinput.ABS_RY,
                uinput.ABS_THROTTLE,
                uinput.ABS_RUDDER,
                uinput.ABS_TILT_X,
                uinput.ABS_TILT_Y,
            ],
        )
