"""Driver and manager for Futaba RC to USB adapters."""

import json
import logging
import os
import re
from logging import handlers
from pathlib import Path

import usb

##
# Credit to https://github.com/shaozu/Futaba_T16IZ_Linux/blob/main/entry.py
# for this great starting point!
##
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

EVENT_MAX_VAL = 32768
EVENT_MIN_VAL = 0
DEFAULT_DEVICE_MIN_VAL = 704
DEFAULT_DEVICE_MAX_VAL = 3392
DEFAULT_CALIBRATION = [
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]]
    * len(DEFAULT_CONFIG["channel_events"])  # one calibration mapping per channel
]
FUTABA_VENDOR_ID = 4104  # 0x1008
PRODUCTS = {
    "default": 999,
    "WSC-1": 10,
    "T16IZ": 11,
    10: "WSC-1",
    11: "T16IZ",
    999: "default",
}

CALIBRATION_PATH = None
CONFIG_PATH = None
LOG_PATH = None
SRC_PATH = None

for parent in Path(__file__).resolve().parents:
    if (parent / ".pylintrc").exists():
        PARENT = os.path.abspath(parent)
        SRC_PATH = os.path.join(PARENT, "src")
        LOG_PATH = os.path.join(PARENT, "logs")
        DRIVER_PATH = os.path.join(SRC_PATH, "driver")
        CONFIG_PATH = os.path.join(DRIVER_PATH, "configs")
        CALIBRATION_PATH = os.path.join(DRIVER_PATH, "calibrations")
        os.makedirs(LOG_PATH, exist_ok=True)
        break

LOGLEVEL = logging.WARNING
DEFAULT_LOG_HANDLER = handlers.RotatingFileHandler(
    os.path.join(LOG_PATH, "driver.txt"),
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)
DEFAULT_LOG_HANDLER.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
DEFAULT_LOGGER = logging.getLogger("driver")
DEFAULT_LOGGER.setLevel(LOGLEVEL)
DEFAULT_LOGGER.addHandler(DEFAULT_LOG_HANDLER)

# These being the same value is a coincidence, they need to be sperate variables in case this chanes or is expanded upon
INTERRUPT_ENDPOINT_ATTRIBUTE = 0x3
HID_INTERFACE = 0x3


def findHIDInterface(coreDevice):
    """Find the HID interface for the given device.

    Args:
        coreDevice (usb.core.Device): The device to search

    Returns:
        usb.core.Device.interface: The HID interface if one exists, none if
        none exist

    """
    for config in coreDevice:
        for interface in config:
            if interface.bInterfaceClass == HID_INTERFACE:
                return interface
    return None


def findInterruptEndpoint(coreDevice):
    """Find the USB interrupt endpoint for the given HID interface.

    Args:
        hidInterface (usb.core.Device.intercface): The HID interface to search

    Returns:
        int: The address of the endpoint if one exists, None if none exist

    """
    hidInterface = findHIDInterface(coreDevice)
    for endpoint in hidInterface:
        if (
            usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN
            and endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
        ):
            return endpoint.bEndpointAddress
    return None


def getCoreDeviceInfo(endpoint):
    """Find the core device on the given bus and port.

    Args:
        endpoint (int): The endpoint address of the device you want info for

    Returns:
        usb.core.Device: The core device at the provided bus and port0

    """
    logger = DEFAULT_LOGGER
    logger.debug(f"looking for core device with an interrupt endpoint address of {endpoint}")
    results = [
        device
        for device in usb.core.find(find_all=True)
        if device.idVendor == FUTABA_VENDOR_ID and findInterruptEndpoint(device) == endpoint
    ]

    if len(results) != 1:
        logger.debug(f"Expected to find exactly 1 result, found {len(results)}")
        return False

    device = results[0]
    logger.debug(f"-> Found {results[0]}")
    return {
        "productID": device.idProduct,
        "serialNumber": device.serial_number,
        "product": device.product,
        "manufacturer": device.manufacturer,
        "speed": device.speed,
        "interruptEndpoint": findInterruptEndpoint(device),
    }


def newLogger(
    name="logs",
    fileName=None,
    level=LOGLEVEL,
):
    """Generate a logger.

    Args:
        name (str): The label to insert after the timestamp on each line in the logs
        fileName (str): The name of the log file the logger will log to
        level (loglevel, optional): The level the logger should output. Defaults to logging.WARNING.

    Returns:
        logger: The generated logger

    """
    if fileName is None:
        fileName = re.sub(r"\W", "_", name) + ".txt"

    handler = handlers.RotatingFileHandler(
        os.path.join(LOG_PATH, fileName),
        maxBytes=5 * 1024 * 1024,  # 5 megabytes
        backupCount=5,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def loadJsonFile(filePath):
    """Load a json file into a dictionary.

    Args:
        filePath (str): The path to the json file you want to load

    Returns:
        dict: The parsed json

    """
    logger = DEFAULT_LOGGER
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
