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
    ):
        atexit.register(self.stop)
        self.state = "initializing"
        self.name = "FutabaUsbDevice - Initializing"
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

        self.usbEndpoint = self._getInterruptEndpoint(self.usbHandle)
        self.name = f"{self.usbHandle.manufacturer}-{self.usbHandle.product}({self.usbEndpoint})"
        self.configFile = ()
        self.logName = self.name.replace(" ", "-").strip().upper()
        self.logger = utils.generateLogger(self.logName)
        self.config = self._loadConfig()
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
        # Default to no reversed inputs
        self.eventReverseFlag = [False] * len(self.eventList)

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

    # def _stdout(self, msg):
    #     """prints a message to stdout with an identifying banner

    #     Args:
    #         msg (str): The message to output
    #     """
    #     print(f"{self.name} -> {msg}")

    def _loadConfig(self):
        """Loads the settings for this particular device and falls back
        to the default config file if one doesn't exist

        Returns:
            dict: A dictionary containing the driver settings
        """
        productName = self.usbHandle.product.strip().upper().replace(" ", "-")
        configFile = os.path.join(utils.getConfigsPath(), f"{productName}.json")

        config = None
        try:
            self.logger.debug("Attempting to load config file...")
            with open(configFile, "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
            self.logger.debug(f"...{configFile} loaded!")
        except FileNotFoundError:
            self.logger.debug(f"-> {configFile} not found, loading default config...")
            with open("default_config.json", "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
        finally:
            if config is None:
                raise FileNotFoundError(
                    f"Unable to load {configFile}.json or default_config.json!"
                )
        return config

    def _loadDefaultConfig(self):
        config = None
        with open("default_config.json", "r", encoding="utf-8") as cfgFile:
            config = json.load(cfgFile)
        return config

    def _getInterruptEndpoint(self, device):
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
                "The device provided to _getInterruptEndpoint is not of type usb.core.Device"
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

    def _parseDataFrame(self, data):
        """Parses the provided data frame into an ordered list of channel data frames

        Args:
            data (dataFrame): A data frame from the physical device

        Returns:
            list: Ordered list of channel data frames
        """
        self.logger.debug(f"Attempting to parse data frame {data}")
        try:
            channelData = [
                (  # remap data from (min 704, center 2048, max 3392) -> (min 0, center 16384, max 32768)
                    (int.from_bytes(data[i : i + 2], byteorder="little") - 704)
                    * 256
                    // 21
                )
                for i in range(0, len(data), 2)
            ]
            channelData.reverse()
        except Exception as e:
            raise ValueError(f"Unable to parse data frame {data}") from e
        self.logger.debug(f"Parsed data frame >{channelData}<")
        return channelData

    def _sendDataFrame(self, data):
        """Sends the provided list of data packets to our virutal device

        Args:
            data (list): A list where each index represents a single channel. Each item will be a data
            packet from the physical device
        """
        # Queue one event for each channel
        for _, (
            event,
            channelData,
            eventReverseFlag,
        ) in enumerate(
            zip(
                self.eventList,
                data,
                self.eventReverseFlag,
            )
        ):
            # Reverse the input if necessary
            if eventReverseFlag:
                channelData = self.eventMaxValue - channelData
            # queue channel event
            self.virtualDevice.emit(event, channelData, syn=False)
            self.logger.debug(f"parsed events {channelData}")
        # Synchronize (fire all queued events)
        self.virtualDevice.syn()

    def start(self):
        """Start the driver"""
        try:
            # self._stdout("Starting driver")
            self.logger.debug(f"Attempting to start virtual {self.name}")
            if self.state != "ready":
                raise Exception(
                    "Attempted to start a FutabaUSBDevice before the driver was in the ready state"
                )

            self.logger.debug("-> Detaching kernel driver...")
            if self.usbHandle.is_kernel_driver_active(0):
                self.usbHandle.detach_kernel_driver(0)

            self.logger.debug("-> Using default configuration...")
            self.usbHandle.set_configuration()

            if self.usbEndpoint is None:
                self.logger.critical(
                    f"Unable to find usb endpoint using the handle >{self.usbHandle}<"
                )
                self.stop(1)

            self.logger.info(f"Driver started: {self.usbEndpoint} -> {self.name}")

            # Main loop
            while True:
                try:
                    # read frame from HW device
                    dataFrame = self.usbHandle.read(
                        self.usbEndpoint,
                        self.frameSize,
                        timeout=20,
                    )
                    # Parse channel data from HW frame
                    channelData = self._parseDataFrame(dataFrame)
                    # Send channel data to virtual device
                    self._sendDataFrame(channelData)
                except usb.core.USBError as e:
                    expectedErrors = [
                        110  # Transmitter not connected to dongle
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
                # self._stdout("Drivers must be run as root")
                raise RuntimeError(
                    "Insufficient permissions to hook USB interface"
                ) from e
        finally:
            self.stop()

    def stop(self, exitCode=None):
        """Stop the driver"""
        # self._stdout("Stopping driver")
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
