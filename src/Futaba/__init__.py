"""Driver and manager for Futaba RC to USB adapters."""

# Allow for some_var = Futaba.DeviceManager()
from .Driver import FutabaDeviceDriver as DeviceDriver
from .Manager import FutabaDeviceManager as DeviceManager

# Allow for from Futba import FutabaDeviceManager
FutabaDeviceDriver = DeviceDriver
FutabaDeviceManager = DeviceManager
__all__ = ["FutabaDeviceManager", "FutabaDeviceDriver"]
