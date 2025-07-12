"""Futaba Device Specific Errors."""

from dataclasses import dataclass


@dataclass
class FutabaError(Exception):
    """Parent class for all Futaba errors."""


@dataclass
class DeviceNotFoundError(FutabaError):
    """Custom exception raised when a Futaba device is not found."""

    message = "Futaba device not found. Please ensure a Futaba USB device is connected."

    def __str__(self):
        """Cast this error to a string.

        Returns:
            string: Error Message

        """
        return self.message
