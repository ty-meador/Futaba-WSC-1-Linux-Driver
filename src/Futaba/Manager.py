"""Module provides a simple interface to spawn and manage multiple Futaba RC to USB adapters."""

import atexit

import usb

from . import Util as utils
from .Driver import DriverState, FutabaDeviceDriver
from .Error import DeviceNotFoundError


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB device drivers."""

    def __init__(self, debugMode=False):
        """Create an object that manages Futaba drivers.

        Raises:
            RuntimeError: Raised if no Futaba USB devices are detected

        """
        if len(self.futabaDevices) == 0:
            raise DeviceNotFoundError

        self.logger = utils.newLogger("FutabaDeviceManager")
        atexit.register(self.stopAll)

    @property
    def futabaDevices(self):
        """A tuple of supported Futaba devices."""
        return tuple(
            [
                FutabaDeviceDriver(device)
                for device in usb.core.find(find_all=True)
                if FutabaDeviceDriver.deviceIsSupported(device)
            ]
        )

    def findDevice(self, endpoint=None):
        """Find the Futaba device that has the provided endpoint.

        Args:
            endpoint (int, optional): The endpoint of the device you are looking for. Defaults to
            None.

        Returns:
            usb.core.Device or None: Returns None if a device was not found. Otherwise returns the
            core device handle.

        """
        if endpoint is not None:
            return self._findDeviceByEndpoint(endpoint)
        return None

    def getDeviceStatus(self, deviceIndex):
        """Get the status of the device at the given index.

        Args:
            deviceIndex (int): The device that you want the status of

        Returns:
            string: "RUNNING" or "IDLE"

        """
        try:
            return self.futabaDevices[deviceIndex].getState()
        except Exception as e:
            self.logger.warning(e)
            return False

    def listDevices(self):
        """Get an ordered list of available devices.

        Returns:
            tuple of string: Ordered list of available devices

        """
        return [{"key": i, **device.toDict()} for i, device in enumerate(self.futabaDevices)]

    def start(self, deviceIndex):
        """Start the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to
            start. Defaults to [].

        """
        self.logger.debug(f"Attempting to start device at index[s] {deviceIndex}")
        if isinstance(deviceIndex, int):
            result = self.futabaDevices[deviceIndex].start()

            if result:
                self.logger.debug(f"-> {self.futabaDevices[deviceIndex]} started")
            else:
                raise RuntimeError(
                    f"Start requested failed for item at index {deviceIndex}",
                )
        elif hasattr("__iter__", deviceIndex):
            self.logger.debug("-> Iterable detected, attempting to start multiple...")
            for idx in deviceIndex:
                result = self.futabaDevices[idx].start()
                if result:
                    self.logger.debug(f"--> {self.futabaDevices[deviceIndex]} started")
                else:
                    raise RuntimeError(
                        f"Start requested failed for item at index {idx}",
                    )

        return self.listDevices()

    def stop(self, deviceIndex):
        """Stop the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to
            stop. Defaults to [].

        """
        try:
            if isinstance(deviceIndex, int):
                self.futabaDevices[deviceIndex].stop()
            elif hasattr("__iter__", deviceIndex):
                for idx in deviceIndex:
                    self.futabaDevices[idx].stop()
        except Exception as e:
            self.logger.warning(e)
        return self.listDevices()

    def stopAll(self):
        """Stop all running drivers."""
        try:
            for device in self.futabaDevices:
                device.stop()
        except Exception as e:
            self.logger.warning(e)
        return self.listDevices()

    @staticmethod
    def _deviceIsRunning(futabaDeviceDriver):
        """Determine if the provided driver is currently running or not.

        Args:
            futabaDeviceDriver (FutabaDeviceDriver): The device to check

        Returns:
            bool: True if the device has a subprocess

        """
        return futabaDeviceDriver.getState() == DriverState.RUNNING

    def _findDeviceByEndpoint(self, endpoint):
        """Find which device has the given endpoint.

        Args:
            endpoint (int): The endpoint of the device to find.

        Returns:
            dict: A dictionary representation of the device with the given
            endpoint.

        """
        endpoint = int(endpoint)
        for device in self.listDevices():
            if device["interruptEndpoint"] == endpoint:
                return device
        return None
