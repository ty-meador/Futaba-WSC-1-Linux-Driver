"""Driver and manager for Futaba RC to USB adapters."""

# Allows
# `from Futaba import FutabaDeviceManager`
# `some_var = FutabaDeviceManager()`

from .Driver import FutabaDeviceDriver
from .Manager import FutabaDeviceManager
from .Util import CalibrationWidget

__all__ = ["FutabaDeviceManager", "FutabaDeviceDriver", "CalibrationWidget"]

# Allows
# `import Futaba`
# `some_var = Futaba.DeviceManager()``
DeviceDriver = FutabaDeviceDriver
DeviceManager = FutabaDeviceManager
