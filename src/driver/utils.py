"""Utility functions for the project"""

import array
import json
import logging
import os
from logging import handlers
from pathlib import Path

import numpy as np
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
    currentFile = Path(__file__).resolve()  # Using resolve to get an absolute path.
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
        maxSize (int, optional): Max file size of log files. Defaults to 5*1024*1024.
        backupCount (int, optional): Number of backup logs to keep in rotation. Defaults to 5
        level (loglevel, optional): The level the logger should output. Defaults to logging.WARNING.

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
        with open(filePath, "r", encoding="utf-8") as jsonFile:
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


def generateValueMap(inputRange, outputRange):
    """Generate a list of values that maps the input range to the output range

    Args:
        inputRange (list, optional): This determines the size of the map. Defaults to [600, 3500].
        outputRange (list, optional): This determines what values are generated in the map. Defaults to [0, 32768].

    Returns:
        list: A list of all possible output values given the range of input values
    """
    if not hasattr(inputRange, "__len__") or len(inputRange) != 2:
        raise TypeError(
            "inputRange must be an array of length 2, using defaults instead"
        )
    if not hasattr(outputRange, "__len__") or len(outputRange) != 2:
        raise TypeError(
            "outputRange must be an array of length 2, using defaults instead"
        )
    if not isinstance(inputRange[0], int):
        raise TypeError(
            f"Expected inputRange[0] to be of type int, found {type(inputRange[0])}"
        )
    if not isinstance(inputRange[1], int):
        raise TypeError(
            f"Expected inputRange[1] to be of type int, found {type(inputRange[1])}"
        )
    if not isinstance(outputRange[0], int):
        raise TypeError(
            f"Expected outputRange[0] to be of type int, found {type(outputRange[0])}"
        )
    if not isinstance(outputRange[1], int):
        raise TypeError(
            f"Expected outputRange[1] to be of type int, found {type(inputRange[1])}"
        )

    # Guarantee that we are working with ints
    inputRange[0] = int(inputRange[0])
    inputRange[1] = int(inputRange[1])
    outputRange[0] = int(outputRange[0])
    outputRange[1] = int(outputRange[1])

    lowerInput = inputRange[0]
    upperInput = inputRange[1]
    lowerOutput = outputRange[0]

    # Create a value map such that the index of the array represents
    # the input value, and the contents at that index is the output
    inputValues = np.array([lowerOutput] * upperInput, int)
    for i in range(lowerInput, upperInput):
        inputValues[i] = i
    return array.array(
        "I",
        np.round(
            np.interp(
                inputValues,
                inputRange,
                outputRange,
            ),
            0,  # Round to the nearest int
        ).astype(int),
    )
