"""Inter-process communication tools."""

from __future__ import annotations
from multiprocessing import Event
# multiprocessing.Event is of data type multiprocessing.synchronize.Event
from multiprocessing.synchronize import Event as MultiprocessingEvent  # typing
from multiprocessing.connection import Connection  # typing
from dataclasses import dataclass, field


# Data Classes
##
@dataclass(slots=True, frozen=True)
class DataFrame:
    """Class representation of a single data frame."""

    event: str
    rawValue: int
    calibratedValue: int

    def __iter__(self):
        """Iter."""
        return iter((self.event, self.rawValue, self.calibratedValue))


@dataclass(slots=True, frozen=True)
class WorkerControl:
    """Effecient picklable wrapper for worker inter-process communication methods."""

    pipe: Connection
    killswitch: MultiprocessingEvent = field(default_factory=Event)
    runFlag: MultiprocessingEvent = field(default_factory=Event)
    echoFlag: MultiprocessingEvent = field(default_factory=Event)
