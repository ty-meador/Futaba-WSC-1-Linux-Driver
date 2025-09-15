"""Module provides a simple interface to spawn and manage multiple Futaba RC to USB adapters."""
from __future__ import annotations
import atexit

from multiprocessing.connection import Connection
from contextlib import suppress

import usb
from usb.core import Device
from typing import Any
from . import Util as utils
from .Driver import DriverState
from .Driver import FutabaDeviceDriver
from .Error import DeviceNotFoundError


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB device drivers."""
    def findDevice(self, endpoint: int | None = None) -> Device | None:
        """Find the Futaba device that has the provided endpoint.

        Args:
            endpoint (int, optional): The endpoint of the device you are looking for. Defaults to
            None.

        Returns:
            usb.core.Device or None: Returns None if a device was not found. Otherwise returns the
            core device handle.
            None: Returned when:
                - No Futaba device is found with the given endpoint

        """
        if endpoint is not None:
            return utils.findEndpointDevice(endpoint)
        return None

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

    def listDevices(self) -> list[dict[Any, ...]]:
        """Get an ordered list of available devices.

        Returns:
            list[dict]: A list of available devices.

        """
        return [{"key": i, **device.toDict()} for i, device in enumerate(self._drivers)]

    def scanForDevices(self) -> None:
        """Scan for new devices."""

        # Find all devices
        foundDevices = [
            device for device in usb.core.find(find_all=True)
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
        return self.listDevices()

    def start(self, deviceIndex: int) -> list[dict]:
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
            self.logger.debug("Device at index %s is already running!", deviceIndex)
            return

        if driver.start():
            self.logger.debug("%s -> started", self._drivers[deviceIndex])
        else:
            raise RuntimeError(
                f"Start requested failed for item at index {deviceIndex}",
            )

        return self.listDevices()

    def startAll(self, autoscan=True) -> list[dict]:
        """Start a driver for all connected Futaba devices

        Args:
            autoscan (bool, optional): If true a preliminary scan will be
            performed to detect devices. Defaults to True.

        Returns:
            list[dict]: list of dictionaries each representing a single
            detected Futaba device
        """
        if autoscan:
            self.scanForDevices()
        for driver in self._drivers:
            if driver.getState() != DriverState.RUNNING:
                driver.start()
        return self.listDevices()

    def stop(self, deviceIndex: int) -> list[dict]:
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
        return self.listDevices()

    def stopAll(self) -> list[dict]:
        """Stop all running drivers.

        Returns:
            list[dict]: A list of available devices.

        """
        for device, driver in zip(self._devices, self._drivers):
            if driver.getState() == DriverState.RUNNING:
                driver.stop()
            self._removeDevice(device)
        return self.listDevices()

    def __init__(self) -> None:
        """Create an object that manages Futaba drivers.

        Raises:
            RuntimeError: Raised if no Futaba USB devices are detected

        """
        self._devices = [
            device for device in usb.core.find(find_all=True)
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

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit."""
        self.stopAll()
        return self

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
