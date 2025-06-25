import json
import logging
import os
import re
from logging import handlers
from pathlib import Path

import uinput
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
FUTABA_VENDOR_ID = 4104
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
DEFAULT_LOG_HANDLER.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s")
)
DEFAULT_LOGGER = logging.getLogger("driver")
DEFAULT_LOGGER.setLevel(LOGLEVEL)
DEFAULT_LOGGER.addHandler(DEFAULT_LOG_HANDLER)


def findInterruptEndpoint(device):
    """Find the USB interrupt endpoint for the provided device

    Args:
        device (usb.core.Device): The device that we want to emulate

    Raises:
        ValueError: Raised if the provided device is not an of type usb.core.device
        RuntimeError: Raised if the provided device does not have an endpoint

    Returns:
        int: The interrupt endpoint address
    """
    logger = DEFAULT_LOGGER
    logger.debug("looking for endpoint for device provided")

    if not isinstance(device, usb.core.Device):
        err = (
            f"Expected first param to be of type usb.core.Device, found {type(device)}"
        )
        logger.critical(err)
        raise ValueError(err)

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


def getCoreDeviceInfo(endpoint):
    """Finds the core device on the given bus and port

    Args:
        bus (int): The bus of the device
        port (int): The port of the device

    Returns:
        usb.core.Device: The core device at the provided bus and port
    """

    logger = DEFAULT_LOGGER
    logger.debug(
        f"looking for core device with an interrupt endpoint address of {endpoint}"
    )
    results = [
        device
        for device in usb.core.find(find_all=True)
        if device.idVendor == FUTABA_VENDOR_ID
        and findInterruptEndpoint(device) == endpoint
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
    """Generates a logger

    Args:
        name (str): _description_
        maxSize (int, optional): Max file size of log files. Defaults to 5*1024*1024.
        backupCount (int, optional): Number of backup logs to keep in rotation. Defaults to 5
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
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s")
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def loadJsonFile(filePath):
    """Generic function to load a JSON file into a dictionary

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
