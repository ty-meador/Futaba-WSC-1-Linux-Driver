from dataclasses import dataclass, field
from multiprocessing import Event
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Event as MultiprocessingEvent

@dataclass(slots=True, frozen=True)
class DataFrame:
    event: str
    rawValue: int
    calibratedValue: int
    def __iter__(self): ...

@dataclass(slots=True, frozen=True)
class WorkerControl:
    pipe: Connection
    killswitch: MultiprocessingEvent = field(default_factory=Event)
    runFlag: MultiprocessingEvent = field(default_factory=Event)
    echoFlag: MultiprocessingEvent = field(default_factory=Event)
