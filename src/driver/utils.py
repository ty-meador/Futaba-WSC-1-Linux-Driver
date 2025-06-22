"""Utility functions for the project"""

import array
import json
import logging
import os
from logging import handlers
from pathlib import Path

import numpy as np
import usb

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
        os.makedirs(CONFIG_PATH, exist_ok=True)
        os.makedirs(CALIBRATION_PATH, exist_ok=True)


LOG_HANDLER = handlers.RotatingFileHandler(
    os.path.join(LOG_PATH, "log.txt"),
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)


def getCoreDevice(bus, port):
    """Finds the core device on the given bus and port

    Args:
        bus (int): The bus of the device
        port (int): The port of the device

    Returns:
        usb.core.Device: The core device at the provided bus and port
    """

    results = [
        device
        for device in usb.core.find(find_all=True)
        if int(device.port_number) == int(port) and int(device.bus_) == int(bus)
    ]

    if len(results) != 1:
        return False
    return results[0]


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
    handler = LOG_HANDLER
    handler.setFormatter(
        logging.Formatter(f"%(asctime)s - {name} %(levelname)s\t: %(message)s")
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def generateValueMap(inputRange=None, outputRange=None):
    """Generate a list of values that maps the input range to the output range

    Args:
        inputRange (list, optional): This determines the size of the map. Defaults to [600, 3500].
        outputRange (list, optional): This determines what values are generated in the map. Defaults to [0, 32768].

    Returns:
        list: A list of all possible output values given the range of input values
    """
    logger = getLogger("generateValueMap")
    if not hasattr(inputRange, "__len__") or len(inputRange) != 2:
        logger.error("inputRange must be an array of length 2, using defaults instead")
        inputRange = [600, 3500]
    if not hasattr(outputRange, "__len__") or len(outputRange) != 2:
        logger.error("outputRange must be an array of length 2, using defaults instead")
        outputRange = [0, 32768]

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
        "I",  # int
        np.round(
            np.interp(
                inputValues,
                inputRange,
                outputRange,
            ),
            0,  # No decimals
        ).astype(int),
    )


def loadJsonFile(filePath):
    """Generic function to load a JSON file into a dictionary

    Args:
        filePath (str): The path to the json file you want to load

    Returns:
        dict: The parsed json
    """
    logger = getLogger("loadJsonFile")
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
