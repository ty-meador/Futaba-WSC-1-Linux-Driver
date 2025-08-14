"""Inter-process communication tools."""

import multiprocessing
from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class WorkerControl:
    """Effecient picklable wrapper for worker inter-process communication methods."""

    pipe: multiprocessing.Pipe
    killswitch: multiprocessing.Event = field(default_factory=multiprocessing.Event)
    runFlag: multiprocessing.Event = field(default_factory=multiprocessing.Event)
    echoFlag: multiprocessing.Event = field(default_factory=multiprocessing.Event)
