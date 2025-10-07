"""Classes for handling input channels."""

from __future__ import annotations
from array import array
from dataclasses import dataclass, field
from logging import Logger
import sys
import typing as t

from . import Util as utils
from .__config__ import DEFAULT_INPUT_RANGE, DEFAULT_OUTPUT_RANGE


class ChannelDict(t.TypedDict):
    """Picklable representation of the channel mappings."""

    eventName: str
    indexOffset: int
    valueMap: array[int]


@dataclass(frozen=True, slots=True)
class ChannelCalibration:
    """Provides a class based representation of a single channels calibration.

    Args:
        logger (logging.Logger): The logger you want this class to use
        inputRange (t.t.Iterable, optional): An iterable of length 3 where each item represents
        the low, middle, and high point respectively in increasing order.
        defaults to DEFAULT_INPUT_RANGE
        outputRange (t.t.Iterable, optional): An iterable of length 3 where each item represents
        the low, middle, and high point respectively in increasing order.
        defaults to DEFAULT_OUTPUT_RANGE
        reverse (bool, optional): If reverse the calibrated values will be
        inserted into the resulting array backwards. This will reverse the
        direction of the input. Defaults to False.


    Why:
        - The range of values that is output on a given channel is different for
         each device manufactured.
        - To account for this difference, we use a process known as
        "calibrating" the device. Calibrating a device is simply the process of
        determining your devices unique range of values, and then mapping that
        range of values to a standardized range of values.
            - This requires a 1-d interpolation from the raw device values to
            the standardized output values. This must be done every single time
            we read data from the device (hundreds of times per second+).

    What:
        - Provide an interface that allows for on the fly interpolation of the
        devices input range to the standardized output range

    How:
        - Interpolate all possible input values ahead of time
        - Create an array with a length equal to that of the upper output limit
        - For each value in the input range, interpolate the value and store the
        interpolated_value at array[value]
        - To prevent out of bounds errors and ensure output continuity:
            - Fill all values below "min input value" with "min output value"
            - Fill all values above "max input value" with "max output value"

    Rationale:
        - Assume the following:
            - our calibration mapping array has already been generated and
            is stored in a variable named "calMap".
            - assume we have just read the raw input value from the device and
            stored it to a variable named "rawV".
        - Translating the raw value to the calibrated value is as simple as
        calMap[rawV]
        - Therefore, we are providing an interface with O(1) runtime at the
        cost of 16kb of memory on an 8 channel device.

    """

    inputRange: t.Iterable[int] = field(default_factory=lambda: DEFAULT_INPUT_RANGE)
    outputRange: t.Iterable[int] = field(default_factory=lambda: DEFAULT_OUTPUT_RANGE)
    indexOffset: int = 0

    logger: Logger = field(default_factory=lambda: utils.newLogger("ChannelCalibration"))
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

        logger.debug(f"-= Channel Calibration({inputRange}, {outputRange}) created! =-")
        logger.debug("    valueMap:")
        logger.debug(f"        elements: {len(valueMap)}")
        logger.debug(f"        unique values: {len(set(valueMap))}")
        logger.debug(f"        mem footprint: {self.valueMapSize} Kb")
        logger.debug(f"    isReversed: {reverse}")
        logger.debug(f"    inputRange: {inputRange[2] - inputRange[0]} total elements")
        logger.debug(f"        high: {inputRange[2]}")
        logger.debug(f"        med: {inputRange[1]}")
        logger.debug(f"        low: {inputRange[0]}")
        logger.debug(f"    outputRange: {outputRange[2] - outputRange[0]} total elements")
        logger.debug(f"        high: {outputRange[2]}")
        logger.debug(f"        med: {outputRange[1]}")
        logger.debug(f"        low: {outputRange[0]}")

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
            f"Insane input range ({inputMin}, {inputMid}, {inputMax})"
        )
        assert outputMin < outputMid < outputMax, (
            f"Insane output range ({inputMin}, {inputMid}, {inputMax})"
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
    """Provides a class based representation of a single input channel."""

    eventName: str
    calibrationRange: t.Iterable[int]
    isReversed: bool = False
    logger: Logger = field(default_factory=lambda: utils.newLogger("InputChannel"))
    valueMap: array[int] = field(default_factory=lambda: array('i'))
    calibration: ChannelCalibration | None = None

    def __post_init__(self) -> None:
        """Instantiate our ChannelCalibration object."""
        # Set calibration
        if self.calibration is None:
            object.__setattr__(
                self,
                "calibration",
                ChannelCalibration(
                    logger=self.logger,
                    inputRange=self.calibrationRange,
                    reverse=self.isReversed,
                ),
            )

        self.logger.debug(f"-= InputChannel({self.eventName}) created =-")
        self.logger.debug(f"    direction: {'reversed' if self.isReversed else 'normal'}")

    def __eq__(self, other: object) -> bool:
        """Determine if the Input Channels are equal.

        Args:
            other (object): The object to compare to.

        Returns:
            bool: True if the channels are equal, false otherwise.

        """
        if not isinstance(other, InputChannel):
            return False
        return hasattr(other, "eventName") and self.eventName == other.eventName

    def __hash__(self) -> int:
        """Determine the objects hash."""
        return hash(self.toDict())

    def toDict(self) -> ChannelDict:
        """Generate a dictionary representation of this input channel."""
        if self.calibration is None:
            raise TypeError("There is no calibration generated!")
        return ChannelDict(
            eventName=self.eventName,
            valueMap=self.calibration.valueMap,
            indexOffset=self.calibration.indexOffset,
        )
