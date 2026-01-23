import typing as t
from array import array
from dataclasses import dataclass, field
from logging import Logger

from _typeshed import Incomplete

from .__config__ import DEFAULT_INPUT_RANGE as DEFAULT_INPUT_RANGE
from .__config__ import DEFAULT_OUTPUT_RANGE as DEFAULT_OUTPUT_RANGE

class ChannelDict(t.TypedDict):
    eventName: str
    indexOffset: int
    valueMap: array[int]

@dataclass(frozen=True, slots=True)
class ChannelCalibration:
    inputRange: t.Iterable[int] = field(default_factory=Incomplete)
    outputRange: t.Iterable[int] = field(default_factory=Incomplete)
    indexOffset: int = ...
    logger: Logger = field(default_factory=Incomplete)
    reverse: bool = ...
    valueMap: array[int] = field(init=False, repr=False)
    valueMapSize: int = field(init=False, repr=False)
    def __post_init__(self) -> None: ...

@dataclass(frozen=True, slots=True)
class InputChannel:
    eventName: str
    calibrationRange: t.Iterable[int]
    isReversed: bool = ...
    indexOffset: int = ...
    valueMap: array[int] = field(default_factory=Incomplete)
    logger: Logger = field(default_factory=Incomplete)
    def __post_init__(self) -> None: ...
    def __eq__(self, other: object) -> bool: ...
