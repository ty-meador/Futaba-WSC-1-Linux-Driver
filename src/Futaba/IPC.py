"""Inter-process communication tools."""

from __future__ import annotations
from multiprocessing import Event
from multiprocessing.synchronize import Event as EventType
from multiprocessing.connection import Connection
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
    killswitch: EventType = field(default_factory=Event)
    runFlag: EventType = field(default_factory=Event)
    echoFlag: EventType = field(default_factory=Event)
