"""Module provides a simple interface to spawn and manage multiple Futaba RC to USB adapters."""

import atexit
import multiprocessing
import typing

import usb

from . import Util as utils
from .Driver import DriverState, FutabaDeviceDriver
from .Error import DeviceNotFoundError


class FutabaDeviceManager:
    """Provides a class-based interface for starting and stopping Futaba USB device drivers."""

    def __init__(self, debugMode: bool = False) -> None:
        """Create an object that manages Futaba drivers.

        Raises:
            RuntimeError: Raised if no Futaba USB devices are detected

        """
        self._futabaDevices = tuple(
            [
                FutabaDeviceDriver(device)
                for device in usb.core.find(find_all=True)
                if FutabaDeviceDriver.deviceIsSupported(device)
            ]
        )
        if len(self.futabaDevices) == 0:
            raise DeviceNotFoundError

        self.logger = utils.newLogger("FutabaDeviceManager")
        atexit.register(self.stopAll)

    @property
    def futabaDevices(self) -> tuple[FutabaDeviceDriver, ...]:
        """A tuple of supported Futaba devices."""
        return self._futabaDevices

    def findDevice(self, endpoint: int | None = None) -> usb.core.Device | None:
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
            return utils.getCoreDevice(endpoint)
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
            return self.futabaDevices[deviceIndex].getState()
        except Exception as e:
            self.logger.warning(e)
            return None

    def getPipe(self, deviceIndex: int) -> multiprocessing.Pipe:
        """Get a duplex pipe for real-time driver communication.

        Args:
            deviceIndex (int): The device that you want the pipe for

        Returns:
            multiprocessing.Pipe: Front-end of a duplex pipe
        """
        try:
            return self.futabaDevices[deviceIndex].pipe
        except Exception as e:
            self.logger.warning(e)
            return None

    def listDevices(self) -> list[dict]:
        """Get an ordered list of available devices.

        Returns:
            list[dict]: A list of available devices.

        """
        return [{"key": i, **device.toDict()} for i, device in enumerate(self.futabaDevices)]

    def start(self, deviceIndex: int | typing.Iterable[int]) -> list[dict]:
        """Start the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to
            start. Defaults to [].

        Returns:
            list[dict]: A list of available devices.

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
        elif hasattr(deviceIndex, "__iter__"):
            self.logger.debug("-> Iterable detected, attempting to start multiple...")
            for idx in deviceIndex:
                result = self.futabaDevices[idx].start()
                if result:
                    self.logger.debug(f"--> {self.futabaDevices[idx]} started")
                else:
                    raise RuntimeError(
                        f"Start requested failed for item at index {idx}",
                    )

        return self.listDevices()

    def stop(self, deviceIndex: int | typing.Iterable[int]) -> list[dict]:
        """Stop the devices at the given indexes.

        Args:
            deviceIndex (int or list of int, optional): The devices you want to
            stop. Defaults to [].

        Returns:
            list[dict]: A list of available devices.

        """
        try:
            if isinstance(deviceIndex, int):
                self.futabaDevices[deviceIndex].stop()
            elif hasattr(deviceIndex, "__iter__"):
                for idx in deviceIndex:
                    self.futabaDevices[idx].stop()
        except Exception as e:
            self.logger.warning(e)
        return self.listDevices()

    def stopAll(self) -> list[dict]:
        """Stop all running drivers.

        Returns:
            list[dict]: A list of available devices.

        """
        try:
            for device in self.futabaDevices:
                device.stop()
        except Exception as e:
            self.logger.warning(e)
        return self.listDevices()

    @staticmethod
    def _deviceIsRunning(futabaDeviceDriver: FutabaDeviceDriver) -> bool:
        """Determine if the provided driver is currently running or not.

        Args:
            futabaDeviceDriver (FutabaDeviceDriver): The device to check

        Returns:
            bool: True if the device has a subprocess

        """
        return futabaDeviceDriver.getState() == DriverState.RUNNING
