"""Module for preventing duplicate application instances."""

import atexit
import errno
import os
import socket
from pathlib import Path
from types import TracebackType

from Futaba import newLogger

PWD = Path(__file__).parent.resolve()


class LockNotAcquired(Exception):
    """Exception which represents a failure to acquire a socket lock"""

    def __init__(self, message: str):
        super().__init__(message)


class DuplicateProcess(LockNotAcquired):
    """Exception which should be raised if the process is already running"""


class SocketLock:
    """Create a lock that prevents multiple application instances."""

    def lock(self) -> None:
        """Create a socket lock to prevent multiple application instances."""
        self.logger.debug("attempting to lock...")
        try:
            self.lockSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.lockSocket.bind(("127.0.0.1", self.lockPort))
            self.pidFile.touch()
        except OSError as e:
            self.logger.warning(
                "Unable to obtain socket lock, driver is likely already running"
            )
            if e.errno == errno.EADDRINUSE:
                raise DuplicateProcess(
                    "Unable to obtain socket lock, driver is likely already running"
                ) from e
            raise e

    def unlock(self) -> None:
        """Remove socket lock and release resources back to os."""
        self.logger.debug("attempting to unlock...")
        if not self.lockSocket:
            self.logger.debug("...socket not locked!")
        else:
            self.logger.debug("socket locked...")
            self.lockSocket.close()
            self.lockSocket = None
            self.logger.debug("...successfully closed socket!")

        if not self.pidFile.exists():
            self.logger.debug("...no pid file exists!")
        else:
            self.logger.debug("pid file exists...")
            self.pidFile.unlink()
            self.logger.debug("...successfully removed pid file!")

        self.logger.debug("done!")

    def __init__(self, port: int = 1962):  # 🥚
        """Create a SocketLock instance

        Args:
            port (int, optional): The port to bind the lock to. Defaults to 1962.
        """
        self.lockPort = port
        self.lockSocket = None
        self.logger = newLogger("SocketLock")
        self.pidFile = PWD / f"{os.getpid()}.pid"
        atexit.register(self.unlock)

    def __enter__(self):
        self.lock()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        stacktrace: TracebackType | None,
    ) -> bool | None:
        if exc_type:
            self.logger.error("exc_type: %s", exc_type)
        if exc_value:
            self.logger.error("exc_value: %s", exc_value)
        if stacktrace:
            self.logger.error("stacktrace: %s", stacktrace)
        self.unlock()
        return False  # Propogate any exceptions that were raised
