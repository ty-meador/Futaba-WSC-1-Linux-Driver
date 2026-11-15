"""Classes for handling input channels."""

from __future__ import annotations

import sys
import typing as t
from array import array
from dataclasses import dataclass, field
from logging import Logger

from . import Util as utils
from .__config__ import DEFAULT_INPUT_RANGE, DEFAULT_OUTPUT_RANGE


class ChannelDict(t.TypedDict):
    """Picklable representation of the channel mappings."""

    eventName: str
    indexOffset: int
    valueMap: array[int]


@dataclass(frozen=True, slots=True)
class ChannelCalibration:
    """Provides a pickleable class based representation of a single channels calibration.

    Args:
        inputRange (Iterable[int], optional): The range of input values. Defaults to DEFAULT_INPUT_RANGE.
        outputRange (Iterable[int], optional): The range of output values. Defaults to DEFAULT_OUTPUT_RANGE.
        indexOffset (int, optional): An offset for the index. Defaults to 0.
        logger (Logger, optional): A logger instance. Defaults to a new logger named "ChannelCalibration".
        reverse (bool, optional): Whether the calibration should be reversed. Defaults to False.

    Attributes:
        inputRange (Tuple[int]): The range of input values as a tuple.
        outputRange (Tuple[int]): The range of output values as a tuple.
        indexOffset (int): An offset for the index.
        logger (Logger): A logger instance.
        reverse (bool): Whether the calibration should be reversed.
        valueMap (array[int]): A mapping array that calibrates input values to output values.
        valueMapSize (int): The memory footprint of the value map in kilobytes.

    Methods:
        _generateValueMap(inputRange, outputRange, reverse): Generates a mapping array based on the given input and output ranges.
    """

    inputRange: t.Iterable[int] = field(default_factory=lambda: DEFAULT_INPUT_RANGE)
    outputRange: t.Iterable[int] = field(default_factory=lambda: DEFAULT_OUTPUT_RANGE)
    indexOffset: int = 0

    logger: Logger = field(
        default_factory=lambda: utils.newLogger("ChannelCalibration")
    )
    reverse: bool = False
    valueMap: array[int] = field(init=False, repr=False)
    valueMapSize: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Generate the calibration mapping array."""
        inputRange = tuple(self.inputRange)
        outputRange = tuple(self.outputRange)
        indexOffset = abs(inputRange[0]) if inputRange[0] < 0 else 0
        logger = self.logger
        reverse = self.reverse
        valueMap = self._generateValueMap(
            inputRange,
            outputRange,
            reverse,
        )

        object.__setattr__(self, "valueMap", valueMap)
        object.__setattr__(self, "inputRange", inputRange)
        object.__setattr__(self, "outputRange", outputRange)
        object.__setattr__(self, "indexOffset", indexOffset)
        object.__setattr__(self, "valueMapSize", sys.getsizeof(valueMap) // 1024)  # kb

        logger.debug(
            "-= Channel Calibration(%s, %s) created! =-", (inputRange, outputRange)
        )
        logger.debug("    valueMap:")
        logger.debug("        elements: %s", len(valueMap))
        logger.debug("        unique values: %s", len(set(valueMap)))
        logger.debug("        mem footprint: %s Kb", self.valueMapSize)
        logger.debug("    isReversed: %s", reverse)
        logger.debug("    inputRange: %s total elements", inputRange[2] - inputRange[0])
        logger.debug("        high: %s", inputRange[2])
        logger.debug("        med: %s", inputRange[1])
        logger.debug("        low: %s", inputRange[0])
        logger.debug(
            "    outputRange: %s total elements", outputRange[2] - outputRange[0]
        )
        logger.debug("        high: %s", outputRange[2])
        logger.debug("        med: %s", outputRange[1])
        logger.debug("        low: %s", outputRange[0])

    def _generateValueMap(
        self,
        inputRange: t.Iterable[int],
        outputRange: t.Iterable[int],
        reverse: bool = False,
    ) -> array[int]:
        """Generate a list of values that maps the input range to the output range.

        Args:
            inputRange (t.t.Iterable[int]): This determines the size of the map.
            Defaults to utils.DEFAULT_INPUT_RANGE.
            outputRange (t.t.Iterable[int]): This determines what values are generated in the
            map. Defaults to utils.DEFAULT_OUTPUT_RANGE.
            reverse (bool, optional): If set to true the map will be generated backwards. This will
            reverse the direction of the input.

        Returns:
            array: An array of all possible output values which can be interpolated from the
            range of input values.

        """
        # Guarantee that we are working with ints
        inputRange = tuple(map(int, inputRange))
        outputRange = tuple(map(int, outputRange))

        inputMin, inputMid, inputMax = inputRange
        outputMin, outputMid, outputMax = outputRange

        assert inputMin < inputMid < inputMax, (
            f"Input range is not increasing ({inputMin}, {inputMid}, {inputMax})"
        )
        assert outputMin < outputMid < outputMax, (
            f"Output range is not increasing ({inputMin}, {inputMid}, {inputMax})"
        )

        # If the input uses both positive and negative values we need to
        # account for that in the array size
        mapSize = abs(inputMax - inputMin) if inputMin < 0 else abs(inputMax)

        # Create a value map such that the index of the array represents
        # the input value, and the contents at that index is the output
        allPossibleInputValues = array("i", [outputMin] * mapSize)
        indexOffset = abs(inputMin) if inputMin < 0 else 0
        arrayRange = range(inputMin, inputMax)
        if reverse:
            reversed(arrayRange)

        # The offset accounts for negative numbers
        for i in arrayRange:
            allPossibleInputValues[i + indexOffset] = i
        return array(
            "i",
            utils.interpolate(
                allPossibleInputValues,
                inputRange,
                outputRange,
                left=outputMin,
                right=outputMax,
            ),
        )


@dataclass(frozen=True, slots=True)
class InputChannel:
    """Provides a pickleable class based representation of a single input channel."""

    eventName: str
    calibrationRange: t.Iterable[int]
    isReversed: bool = False

    indexOffset: int = 0
    valueMap: array[int] = field(default_factory=lambda: array("i"))
    logger: Logger = field(default_factory=lambda: utils.newLogger("InputChannel"))

    def __post_init__(self) -> None:
        """Instantiate our ChannelCalibration object."""
        calibration = ChannelCalibration(
            logger=self.logger,
            inputRange=self.calibrationRange,
            reverse=self.isReversed,
        )

        object.__setattr__(
            self,
            "valueMap",
            calibration.valueMap,
        )

        object.__setattr__(
            self,
            "indexOffset",
            calibration.indexOffset,
        )

        self.logger.debug(f"-= InputChannel({self.eventName}) created =-")
        self.logger.debug(
            f"    direction: {'reversed' if self.isReversed else 'normal'}"
        )

    def __eq__(self, other: object) -> bool:
        """Determine if the Input Channels are equal.

        Args:
            other (object): The object to compare to.

        Returns:
            bool: True if the channels are equal, false otherwise.

        """
        return (
            isinstance(other, InputChannel)
            and hasattr(other, "eventName")
            and self.eventName == other.eventName
        )

    def __getstate__(self):
        """Returns a dict of attributes to be pickled"""
        return {
            "calibrationRange": self.calibrationRange,
            "eventName": self.eventName,
            "indexOffset": self.indexOffset,
            "isReversed": self.isReversed,
            "valueMap": self.valueMap,
        }

    def __setstate__(self, state: dict[str, t.Any]):
        """Recreate object when being unpickled."""
        object.__setattr__(self, "calibrationRange", state["calibrationRange"])
        object.__setattr__(self, "eventName", state["eventName"])
        object.__setattr__(self, "indexOffset", state["indexOffset"])
        object.__setattr__(self, "isReversed", state["isReversed"])
        object.__setattr__(self, "valueMap", state["valueMap"])
