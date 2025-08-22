"""Inter-process communication tools."""

import atexit
import multiprocessing
import socket
from dataclasses import dataclass, field


class ProcessLock:
    """Create a lock that prevents multiple process instances."""

    def __init__(self):
        """Create a process lock."""
        self.lockPort = 1962  # 🥚
        self.lockSocket = None
        atexit.register(self.unlock)

    def lock(self):
        """Lock the process to prevent multiple instances."""
        # Socket-lock method
        self.lockSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.lockSocket.bind(("127.0.0.1", self.lockPort))

    def unlock(self):
        """Unlock the process and release resources back to OS."""
        if self.lockSocket:
            self.lockSocket.close()
            self.lockSocket = None

    def __enter__(self):
        """Enter."""
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit."""
        self.unlock()
        return self


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
