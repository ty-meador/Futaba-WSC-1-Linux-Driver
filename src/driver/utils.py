"""Utility functions for the project"""

import array
import logging
import os
from logging import handlers
from pathlib import Path

import numpy as np

CALIBRATION_PATH = None
CONFIG_PATH = None
LOG_PATH = None
ROOT_DIR = None

for parent in Path(__file__).resolve().parents:
    if (parent / ".pylintrc").exists():
        ROOT_DIR = os.path.abspath(os.path.join(parent, "src"))
        LOG_PATH = os.path.abspath((os.path.join(parent, "logs")))
        CONFIG_PATH = os.path.abspath(os.path.join(ROOT_DIR, "driver", "configs"))
        CALIBRATION_PATH = os.path.abspath(
            os.path.join(ROOT_DIR, "driver", "calibrations")
        )
        os.makedirs(LOG_PATH, exist_ok=True)
        os.makedirs(CONFIG_PATH, exist_ok=True)
        os.makedirs(CALIBRATION_PATH, exist_ok=True)


LOG_HANDLER = handlers.RotatingFileHandler(
    os.path.join(LOG_PATH, "log.txt"),
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)


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
