"""Class representing a single Futaba USB adapater"""

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

FUTABA_VENDOR_ID = 4101


class FutabaUsbDevice:
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

    def __init__(self, bus=None, port=None, name=None):
        atexit.register(self.stop)
        self.logger = utils.generateLogger("driver")
        self.logger.debug("Attempting to instantiate FutabaUsbDevice:")

        self.usbHandle = None
        for device in usb.core.find(find_all=True):
            if int(device.bus) == int(bus) and int(device.port_number) == int(port):
                self.usbHandle = device

        if self.usbHandle is None:
            raise RuntimeError("Could not locate the specified device!")

        self.interruptEndpoint = self.findEndpoint(self.usbHandle)
        self.config = self.loadConfig()
        self.channelCalibrations = self.loadCalibration()
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
        self.logger.debug(f"-> channelCalibrations: {self.channelCalibrations}")
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

        configFileName = f"{productName}.json"
        configFilePath = os.path.join(utils.CONFIG_PATH, configFileName)
        logger.debug("loading config")
        defaultFileName = "default.json"
        defaultFilePath = os.path.join(utils.CONFIG_PATH, defaultFileName)

        try:
            logger.debug("-> Attempting to load config file...")
            with open(configFilePath, "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
            logger.debug(f"---> {configFileName} loaded!")
        except FileNotFoundError:
            logger.debug(f"---> {configFileName} not found, loading default config...")
            with open(defaultFilePath, "r", encoding="utf-8") as cfgFile:
                config = json.load(cfgFile)
            logger.debug(f"---> {defaultFileName} loaded!")
        finally:
            if config is None:
                raise FileNotFoundError(
                    f"Unable to load {configFileName} or {defaultFileName}!"
                )
        return config

    def loadCalibration(self, productName=None):
        """Loads the calibration file"""
        if productName is None:
            productName = self.usbHandle.product
        logger = self.logger
        channelCalibrations = None
        calibrationFileName = f"{productName}.json"
        calibrationFilePath = os.path.join(utils.CALIBRATION_PATH, calibrationFileName)

        try:
            with open(calibrationFilePath, "r", encoding="utf-8") as calibFile:
                channelCalibrations = json.load(calibFile)
        except FileNotFoundError:
            logger.warning(
                f"not calibration found for device {productName}, using default calibration"
            )

            defaultFileName = "default.json"
            defaultFilePath = os.path.join(
                utils.CALIBRATION_PATH,
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

    def start(self):
        """Start the driver"""
        try:
            channelCalibrations = self.channelCalibrations
            channelEvents = self.channelEvents
            emit = self.virtualDevice.emit
            endpoint = self.interruptEndpoint
            eventMaxVal = self.config["event_max_value"]
            frameSize = self.config["frame_size"]
            fromBytes = int.from_bytes
            interp = np.interp
            logger = self.logger
            name = self.name
            reverseFlags = self.eventReverseFlags
            stop = self.stop
            synchronize = self.virtualDevice.syn
            usbHandle = self.usbHandle

            if usbHandle.is_kernel_driver_active(0):
                usbHandle.detach_kernel_driver(0)
            usbHandle.set_configuration()

            logger.info(f"Driver started: {endpoint} -> {name}")

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
            # REGARDLESS OF THE STATE OF THE DEVICE
            while True:
                try:
                    rawData = usbHandle.read(
                        endpoint,
                        frameSize,
                        timeout=100,
                    )

                    channelsData = [
                        (
                            int(
                                interp(
                                    # Interpolate raw data based on calibration
                                    fromBytes(
                                        rawData[i : i + 2], byteorder="little"
                                    ),  # Value
                                    channelCalibrations[i // 2][0],  # input range
                                    channelCalibrations[i // 2][1],  # output range
                                )
                            )
                        )
                        for i in range(0, len(rawData), 2)
                    ]
                    channelsData.reverse()

                    # Queue one event for each channel
                    for channelData, channelEvent, reverseFlag in zip(
                        channelsData, channelEvents, reverseFlags
                    ):
                        if reverseFlag:
                            channelData = eventMaxVal - channelData
                        # queue channel event
                        emit(
                            channelEvent,
                            channelData,
                            syn=False,
                        )
                    # Synchronize (fire all queued events)
                    synchronize()
                except usb.core.USBError as e:
                    # kaboom?
                    if e.errno != 110:
                        # Yes Rico, kaboom.
                        logger.critical(e)
                        raise e
                    # Transmitter timeout - ignore
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
