"""Contains atomic utility functions for the project."""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from logging import handlers
from pathlib import Path

import usb

DEFAULT_LOG_HANDLER: logging.handlers.RotatingFileHandler = handlers.RotatingFileHandler(
    "logs.txt",
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)

##
# Futaba makes prescision electronics. However, if you have an aging device, these values may need
# to be increased.
##

# You may want to increase this value if:
# - You are experiencing "cross talk" between channels
# - A channel is drifting/hovering around a static input
DEFAULT_NOISE_FILTER: int = 0
# You may want to increase this value if:
# - Your inputs have any "joystick drift"
# - Leaving the neutral position is too sensitive
DEFAULT_DEADZONE: int = 0

##
# Credit to https://github.com/shaozu/Futaba_T16IZ_Linux/blob/main/entry.py
# for this great starting point!
##
DEFAULT_DEVICE_MIN_VAL: int = 704
DEFAULT_DEVICE_MID_VAL: int = 2048
DEFAULT_DEVICE_MAX_VAL: int = 3392
EVENT_MIN_VAL: int = -32768
EVENT_MID_VAL: int = 0
EVENT_MAX_VAL: int = 32767
DEFAULT_INPUT_RANGE: tuple[int, int, int] = tuple(
    [
        DEFAULT_DEVICE_MIN_VAL,
        DEFAULT_DEVICE_MID_VAL,
        DEFAULT_DEVICE_MAX_VAL,
    ]
)
DEFAULT_OUTPUT_RANGE: tuple[int, int, int] = tuple(
    [
        EVENT_MIN_VAL,
        EVENT_MID_VAL,
        EVENT_MAX_VAL,
    ]
)

FUTABA_VENDOR_ID: int = 4104  # 0x1008
HID_INTERFACE: hex = 0x3  # conincidence
INTERRUPT_ENDPOINT_ATTRIBUTE: hex = 0x3  # conincidence


DEFAULT_CONFIG: dict = {
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

DEFAULT_CALIBRATION: list = [DEFAULT_INPUT_RANGE * len(DEFAULT_CONFIG["channel_events"])]

PRODUCTS: dict = {
    "default": 999,
    "WSC-1": 10,
    "T16IZ": 11,
    10: "WSC-1",
    11: "T16IZ",
    999: "default",
}


LOGLEVEL: int = logging.DEBUG
DEFAULT_LOG_HANDLER.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
DEFAULT_LOGGER: logging.Logger = logging.getLogger("driver")
DEFAULT_LOGGER.setLevel(LOGLEVEL)
DEFAULT_LOGGER.addHandler(DEFAULT_LOG_HANDLER)

DRIVER_PATH: str = Path(__file__).resolve().parent  # Using resolve to get an absolute path.
CONFIG_PATH: str = os.path.join(DRIVER_PATH, "configs")
CALIBRATION_PATH: str = os.path.join(DRIVER_PATH, "calibrations")
LOG_PATH: str = os.path.join(DRIVER_PATH, "logs")
os.makedirs(LOG_PATH, exist_ok=True)


def findHIDInterface(coreDevice: usb.core.Device) -> usb.core.Interface | None:
    """Find the HID interface for the given device.

    Args:
        coreDevice (usb.core.Device): The device to search

    Returns:
        usb.core.Device.interface: The HID interface if one exists
        None: Returned when:
            - No device found with matching vendor ID and endpoint
            - Multiple devices found (ambiguous result)
            - Device access fails

    """
    for config in coreDevice:
        for interface in config:
            if interface.bInterfaceClass == HID_INTERFACE:
                return interface
    return None


def findInterruptEndpoint(coreDevice: usb.core.Device) -> int | None:
    """Find the USB interrupt endpoint for the given HID interface.

    Args:
        coreDevice (usb.core.Device): The core device to find the interrupt endpoint of.

    Returns:
        int: The address of the endpoint if one exists, None if none exist.

    """
    hidInterface = findHIDInterface(coreDevice)
    if hidInterface:
        for endpoint in hidInterface:
            if (
                usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN
                and endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
            ):
                return endpoint.bEndpointAddress
    return None


def getCoreDevice(endpoint: int) -> usb.core.Device | bool:
    """Get the core USB device handle that has the provided enpoint.

    Args:
        endpoint (int): The interrupt endpoint address as an integer.

    Returns:
        usb.core.Device: The core device handle that has the provided endpoint.
        False: Returned when:
            - The number of devices found is not exactly 1

    """
    results = [
        device
        for device in usb.core.find(find_all=True)
        if device.idVendor == FUTABA_VENDOR_ID and findInterruptEndpoint(device) == endpoint
    ]

    if len(results) != 1:
        return False
    return results[0]


def getCoreDeviceInfo(endpoint: int) -> dict | None:
    """Find the core device on the given bus and port.

    Args:
        endpoint (int): The endpoint address of the device you want info for

    Returns:
        usb.core.Device: The core device at the provided bus and port0

    """
    device = getCoreDevice(endpoint)
    return (
        {
            "productID": device.idProduct,
            "serialNumber": device.serial_number,
            "product": device.product,
            "manufacturer": device.manufacturer,
            "speed": device.speed,
            "interruptEndpoint": findInterruptEndpoint(device),
        }
        if device
        else None
    )


def getInterruptAddress(device: usb.core.Device) -> int:
    """Take in a device and returns is interrupt enpoint address.

    Args:
        device (usb.core.Device): The device that we want to emulate

    Raises:
        ValueError: Raised if the provided device is not an of type usb.core.device
        RuntimeError: Raised if the provided device does not have an endpoint

    Returns:
        int: The endpoint object used to capture frames from the physical device

    """
    if not isinstance(device, usb.core.Device):
        raise ValueError("Expected first param to be of type usb.core.Device")
    for config in device:
        for interface in config:
            for endpoint in interface:
                if (
                    usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN
                    and endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
                ):
                    return endpoint.bEndpointAddress
    raise RuntimeError("No interrupt endpoint found!")


def loadJsonFile(filePath: Path | str) -> dict:
    """Load a JSON file into a dictionary.

    Args:
        filePath (str): The path to the json file you want to load

    Returns:
        dict: The parsed json

    """
    parsedJson = None
    with open(filePath, encoding="utf-8") as jsonFile:
        parsedJson = json.load(jsonFile)
    return parsedJson


def newLogger(
    name: str,
    fileName: str | None = None,
    level: int | None = None,
) -> logging.Logger:
    """Generate a logger.

    Args:
        name (str, optional): The label to insert after the timestamp on each line in the logs.
        Defaults to "logs"
        fileName (str, optional): The name of the log file the logger will log to. Defaults to
        None
        level (loglevel, optional): The level the logger should output. Defaults to
        logging.WARNING.

    Returns:
        logger (logging.logger): The generated logger

    """
    if level is None:
        level = logging.INFO
    if fileName is None:
        fileName = re.sub(r"\W", "_", name) + ".txt"

    handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_PATH, fileName),
        maxBytes=5 * 1024 * 1024,  # 5 megabytes
        backupCount=5,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


@dataclass(frozen=True, slots=True)
class DeviceConfig:
    """Stores the configuration settings for a single device."""

    channelEvents: list[str] = field(default_factory=lambda: DEFAULT_CONFIG["channel_events"])
    deadZone: int = DEFAULT_DEADZONE
    frameSize: int = field(default_factory=lambda: DEFAULT_CONFIG["frame_size"])
    noiseFilter: int = DEFAULT_NOISE_FILTER
