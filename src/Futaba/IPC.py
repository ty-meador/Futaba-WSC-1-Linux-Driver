"""Inter-process communication tools."""

import multiprocessing
from dataclasses import dataclass, field


##
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

    pipe: multiprocessing.Pipe
    killswitch: multiprocessing.Event = field(default_factory=multiprocessing.Event)
    runFlag: multiprocessing.Event = field(default_factory=multiprocessing.Event)
    echoFlag: multiprocessing.Event = field(default_factory=multiprocessing.Event)
