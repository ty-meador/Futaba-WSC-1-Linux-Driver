"""Utility functions for the project"""

import json
import logging
import os
from logging import handlers
from pathlib import Path

import usb

HANDLER = handlers.RotatingFileHandler(
    "logs.txt",
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)


def getProjectRoot():
    """
    Gets the project root directory, assuming this function is called
    from a file within the project, and that there's a 'pyproject.toml'
    file at the project root.
    """

    # Start from THIS file's directory
    currentFile = Path(
        __file__
    ).resolve()  # Using resolve to get an absolute path.
    # Go up directories until we find 'pyproject.toml'
    for parent in currentFile.parents:  # Iterate over every parent.
        if (parent / ".pylintrc").exists():  # Checks if file exists
            return parent
    raise FileNotFoundError("Project root (with .pylintrc) not found.")


ROOT_DIR = os.path.abspath(getProjectRoot() / "src")
CONFIG_PATH = os.path.join(ROOT_DIR, "driver", "configs")
CALIBRATION_PATH = os.path.join(ROOT_DIR, "driver", "calibrations")


def getLogger(
    name="logs",
    level=logging.DEBUG,
):
    """Generates a logger

    Args:
        name (str): _description_
        maxSize (int, optional): Max file size of log files. Defaults to
        5*1024*1024.
        backupCount (int, optional): Number of backup logs to keep in rotation.
        Defaults to 5
        level (loglevel, optional): The level the logger should output. Defaults
        to logging.WARNING.

    Returns:
        logger: The generated logger
    """
    handler = HANDLER
    handler.setFormatter(
        logging.Formatter(f"%(asctime)s - {name} %(levelname)s\t: %(message)s")
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
    logger = getLogger(name=f"loadJsonFile({filePath})")
    parsedJson = None

    try:
        logger.debug(f"> Looking for {filePath}")
        with open(filePath, encoding="utf-8") as jsonFile:
            parsedJson = json.load(jsonFile)
        logger.debug("--> loaded!")
    except FileNotFoundError:
        # parsedJson defaults to None
        logger.debug("--> not found, returning >None<")
    return parsedJson


def getInterruptAddress(device):
    """Take in a device and returns is interrupt enpoint address

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
