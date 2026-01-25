"""Module provides a simple interface to spawn and manage multiple Futaba RC to USB adapters."""

from __future__ import annotations

import atexit
from contextlib import suppress
from multiprocessing.connection import Connection
from typing import Any

import usb

from . import Util as utils
from .Driver import DriverState, FutabaDeviceDriver
from .Error import DeviceNotFoundError


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB device drivers."""

    def __init__(self) -> None:
        """Create an object that manages Futaba drivers.

        Raises:
            RuntimeError: Raised if no Futaba USB devices are detected

        """
        self._devices = [
            device
            for device in usb.core.find(find_all=True)
            if FutabaDeviceDriver.deviceIsSupported(device)
        ]
        self._drivers = [FutabaDeviceDriver(device) for device in self._devices]

        if len(self._drivers) == 0:
            raise DeviceNotFoundError

        self.logger = utils.newLogger("FutabaDeviceManager")
        atexit.register(self.stopAll)

    def __enter__(self):
        """Enter."""
        return self

    def __exit__(
        self, exc_type: Any, exc_value: Any, traceback: Any
    ) -> FutabaDeviceManager:
        """Exit."""
        self.stopAll()
        return self

    def getDeviceStatus(self, deviceIndex: int) -> DriverState | None:
        """Get the status of the device at the given index.

        Args:
            deviceIndex (int): The device that you want the status of

        Returns:
            DriverState: The state of the driver
            None: Returned when
                - Attempting to get the current state raises and exception

        """
        try:
            return self._drivers[deviceIndex].getState()
        except Exception as e:
            self.logger.warning(e)
            return None

    def deviceInfo(self, deviceIndex: int, prop: str) -> Any:
        """Get a property value of the specified device.

        Args:
            deviceIndex (int): The device you want info for.
            prop (str): The property name of the value you want.

        Returns:
            str|int: The specified attributes value from the specified device.
        """
        return getattr(self._drivers[deviceIndex], prop)

    def getPipe(self, deviceIndex: int) -> Connection:
        """Get a duplex pipe for real-time driver communication.

        Args:
            deviceIndex (int): The device that you want the pipe for

        Returns:
            multiprocessing.Pipe: Front-end of a duplex pipe
        """
        self._drivers[deviceIndex].enableEcho()
        return self._drivers[deviceIndex].pipe

    def listDevices(self) -> list[dict[str, Any]]:
        """Get an ordered list of available devices.

        Returns:
            list[dict]: A list of available devices.

        """
        return [{"key": i, **device.__dict__} for i, device in enumerate(self._drivers)]

    def scanForDevices(self) -> None:
        """Scan for new devices."""

        # Find all devices
        foundDevices = [
            device
            for device in usb.core.find(find_all=True)
            if FutabaDeviceDriver.deviceIsSupported(device)
        ]

        # Add new devices
        for device in foundDevices:
            if device not in self._devices:
                self._addDevice(device)

        # Remove devices that are no longer present
        for device in self._devices:
            if device not in foundDevices:
                self._removeDevice(device)

    def start(self, deviceIndex: int) -> None:
        """Start the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to
            start. Defaults to [].

        Returns:
            list[dict]: A list of available devices.

        """
        self.logger.debug("Attempting to start device at index %s", deviceIndex)
        driver = self._drivers[deviceIndex]
        if driver.getState() == DriverState.RUNNING:
            self.logger.debug(
                "usb.core.Device at index %s is already running!", deviceIndex
            )
            return

        if driver.start():
            self.logger.debug("%s -> started", self._drivers[deviceIndex])
        else:
            raise RuntimeError(
                f"Start requested failed for item at index {deviceIndex}",
            )

    def startAll(self) -> None:
        """Start a driver for all connected Futaba devices

        Args:
            autoscan (bool, optional): If true a preliminary scan will be
            performed to detect devices. Defaults to True.

        Returns:
            list[dict]: list of dictionaries each representing a single
            detected Futaba device
        """
        for driver in self._drivers:
            if driver.getState() != DriverState.RUNNING:
                driver.start()

    def stop(self, deviceIndex: int) -> None:
        """Stop the devices at the given indexes.

        Args:
            deviceIndex (int): The key of the device to stop.

        Returns:
            list[dict]: A list of available devices.

        """
        try:
            self._drivers[deviceIndex].stop()
        except Exception as e:
            self.logger.warning(e)

    def stopAll(self) -> None:
        """Stop all running drivers.

        Returns:
            list[dict]: A list of available devices.

        """
        for device, driver in zip(self._devices, self._drivers):
            if driver.getState() == DriverState.RUNNING:
                driver.stop()
            self._removeDevice(device)

    @staticmethod
    def _deviceIsRunning(driver: FutabaDeviceDriver) -> bool:
        """Determine if the provided driver is currently running or not.

        Args:
            futabaDeviceDriver (FutabaDeviceDriver): The device to check

        Returns:
            bool: True if the device has a subprocess

        """
        return driver.getState() == DriverState.RUNNING

    def _addDevice(self, device: usb.core.Device) -> None:
        """Index a new Futaba device

        Args:
            device (usb.core.Device): The core device to index
        """
        assert len(self._devices) == len(self._drivers), "driver/device count mismatch"
        if device not in self._devices:
            self._devices.append(device)
            self._drivers.append(FutabaDeviceDriver(device))

    def _removeDevice(self, device: usb.core.Device) -> None:
        """Remove a Futaba device from the index

        Args:
            device (usb.core.Device): The core device to remove from the index
        """
        assert len(self._devices) == len(self._drivers), "driver/device count mismatch"
        # Safely clean up after ourselves here
        # Value errors raised if the device to remove doesn't exist, so we ignore them
        with suppress(ValueError):
            # Get index of driver or raise a value error, which we can safely ignore and
            # return from.
            idx = self._devices.index(device)
            self.stop(idx)  # Ensure driver is stopped
            del self._devices[idx]  # Remove from our index
            del self._drivers[idx]
