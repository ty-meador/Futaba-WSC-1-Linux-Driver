"""Module for preventing duplicate application instances."""
import atexit
import errno
import socket


class LockNotAcquired(Exception):
    """Exception which represents a failure to acquire a process lock"""
    def __init__(self, message: str):
        super().__init__(message)


class DuplicateProcess(LockNotAcquired):
    """Exception which should be raised if the process is already running"""


class SocketLock:
    """Create a lock that prevents multiple application instances."""
    def lock(self):
        """Create a socket lock to prevent multiple application instances."""
        try:
            self.lockSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.lockSocket.bind(("127.0.0.1", self.lockPort))
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                raise DuplicateProcess(
                    "Unable to obtain socket lock, driver is likely already running"
                ) from e
            raise e

    def unlock(self):
        """Remove socket lock and release resources back to os."""
        if self.lockSocket:
            self.lockSocket.close()
            self.lockSocket = None

    def __init__(self, port: int = 1962):  # 🥚
        """Create a SocketLock instance

        Args:
            port (int, optional): The port to bind the lock to. Defaults to 1962.
        """
        self.lockPort = port
        self.lockSocket = None
        atexit.register(self.unlock)

    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, stacktrace):
        self.unlock()
        return self
