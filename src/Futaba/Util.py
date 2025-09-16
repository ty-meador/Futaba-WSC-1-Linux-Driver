"""Contains atomic utility functions for the project."""
from __future__ import annotations
import array
import bisect
from contextlib import suppress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
from typing import Any
import usb
from .__config__ import FUTABA_VENDOR_ID, LOG_PATH, PWD, INTERRUPT_ENDPOINT_ATTRIBUTE


def findEndpointDevice(endpoint: int) -> usb.core.Device | None:
    """Get the core USB device handle that has the provided enpoint.

    Args:
        endpoint (int): The interrupt endpoint address as an integer.

    Returns:
        usb.core.Device: The core device handle that has the provided endpoint.
        False: Returned when:
            - The number of devices found is not exactly 1

    """
    results = [
        device for device in usb.core.find(find_all=True)
        if device.idVendor == FUTABA_VENDOR_ID and findInterruptEndpoint(device) == endpoint
    ]

    if len(results) != 1:
        return None
    return results[0]


def findInterruptEndpoint(device: usb.core.Device) -> int | None:
    """Take in a device and returns is interrupt enpoint address.

    Args:
        device (usb.core.Device): The device that we want to emulate

    Raises:
        ValueError: Raised if the provided device is not an of type usb.core.device
        RuntimeError: Raised if the provided device does not have an endpoint

    Returns:
        int: The endpoint object used to capture frames from the physical device

    """
    for config in device:
        for interface in config:
            for endpoint in interface:
                if (
                    usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN
                    and endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
                ):
                    return endpoint.bEndpointAddress
    return None


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
        level = logging.WARNING
    if fileName is None:
        fileName = re.sub(r"\W", "_", name) + ".txt"

    handler = RotatingFileHandler(
        os.path.join(LOG_PATH, fileName),
        maxBytes=5 * 1024 * 1024,  # 5 megabytes
        backupCount=5,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s"))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def parseJsonFile(filePath: str) -> Any:
    """Load a JSON file into a dictionary.

    Args:
        filePath (str): The path to the json file you want to load

    Returns:
        dict or None: The parsed json as a dict. If the file is not found None is returned

    """
    parsedJson = None
    with suppress(FileNotFoundError):
        with open(filePath, encoding="utf-8") as jsonFile:
            parsedJson = json.load(jsonFile)
    return parsedJson


def interpolate(
    xVals: array.array[int],
    xPoints: tuple[int, ...],
    yPoints: tuple[int, ...],
    left: int | None = None,
    right: int | None = None,
) -> list[int]:
    """Perform a 1-d interpolation.

    Args:
        xVals: Values to interpolate at
        xPoints: X coordinates of known points
        yPoints: Y coordinates of known points
        left: Value for x < xPoints[0]
        right: Value for x > xPoints[-1]

    Returns:
        List of interpolated integer values
    """
    result: list[int] = []

    for x in xVals:
        # Handle boundary conditions
        if x <= xPoints[0]:
            result.append(left if left is not None else yPoints[0])
            continue
        if x >= xPoints[-1]:
            result.append(right if right is not None else yPoints[-1])
            continue

        # Find the right interval for interpolation
        i = bisect.bisect_right(xPoints, x) - 1

        x1, x2 = xPoints[i], xPoints[i + 1]
        y1, y2 = yPoints[i], yPoints[i + 1]

        interpolated = (
            y1 if x2 == x1  # Avoid division by zero
            else y1 + (y2 - y1) * (x - x1) / (x2 - x1)  # Linear interpolation
        )

        result.append(int(round(interpolated)))
    return result


class CalibrationWidget:
    """Generates a channel calibration for the running device."""
    def minMax(self, channel: Any, rawV: int) -> None:
        """Process value as min/max.

        If the provided value is a new high or low value for the given channel then the min or max
        value for that channel will be updated respectively

        Args:
            channel (any): a unique channel identifier
            rawV (int): the raw value from the device
        """
        # Detect new channels
        if channel not in self.knownChannels:
            self.knownChannels[channel] = self._defaultChannelDict(rawV)
        # Update boundaries
        elif rawV < self.knownChannels[channel]["min"]:
            self.knownChannels[channel]["min"] = rawV
        elif rawV > self.knownChannels[channel]["max"]:
            self.knownChannels[channel]["max"] = rawV

    def mid(self, channel: Any, rawV: int) -> None:
        """Set the mid point for the given channel.

        Args:
            channel (any): a unique channel identifier
            rawV (int): the raw value from the device
        """
        # Detect new channels
        if channel not in self.knownChannels:
            self.knownChannels[channel] = self._defaultChannelDict(rawV)

        # Update midpoint
        self.knownChannels[channel]["mid"] = rawV

    def generateFile(self, fileName: str) -> None:
        """Generate the calibration file.

        Args:
            fileName (str): The name to use for the generated file.
        """
        calibration = self._generateCalibrationBreakpoints()
        calibrationFile = PWD / "calibrations" / fileName
        calibrationFile.write_text(json.dumps(calibration, indent=4))

    def __init__(self) -> None:
        """Create a Channel calibrator."""
        self.knownChannels: dict[tuple[int, int], dict[str, int]] = {}

    def _defaultChannelDict(self, default: int) -> dict[str, int]:
        return {"min": default, "mid": default, "max": default}

    def _generateCalibrationBreakpoints(self) -> tuple[tuple[int, int, int], ...]:
        """Generate a tuple of channels, each containing a tuple of calibration break points."""
        channelList: list[tuple[int, int, int]] = []
        for channelData in self.knownChannels.values():
            # Account for channels that might not be used by the transmitter
            # We have to do this because the interpolation function used to generate the
            # calibrated value map requires an ascending input range to be considered "sane".
            if channelData["min"] == channelData["mid"] == channelData["max"]:
                channelData["min"] = channelData["mid"] - 1
                channelData["max"] = channelData["mid"] + 1
            channelList.append((channelData["min"], channelData["mid"], channelData["max"]))
        return tuple(channelList)
