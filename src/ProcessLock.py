"""Module for preventing duplicate processes."""
import atexit
import socket


class LockNotAcquired(Exception):
    """Exception which represents a failure to acquire a process lock"""
    def __init__(self, message):
        super().__init__(message)


class ProcessLock:
    """Create a lock that prevents multiple driver instances."""
    def lock(self):
        """Lock the process to prevent multiple instances."""
        # Socket-lock method
        try:
            self.lockSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.lockSocket.bind(("127.0.0.1", self.lockPort))
        except Exception as e:
            raise LockNotAcquired(
                "Unable to obtain process lock, driver is likely already running"
            ) from e

    def unlock(self):
        """Unlock the process and release resources back to OS."""
        if self.lockSocket:
            self.lockSocket.close()
            self.lockSocket = None

    def __init__(self):
        """Create a process lock."""
        self.lockPort = 1962  # 🥚
        self.lockSocket = None
        atexit.register(self.unlock)

    def __enter__(self):
        """Enter."""
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, stacktrace):
        """Exit."""
        self.unlock()
        return self
