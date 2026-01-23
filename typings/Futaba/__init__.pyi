from .Driver import FutabaDeviceDriver as FutabaDeviceDriver
from .Manager import FutabaDeviceManager as FutabaDeviceManager
from .Util import CalibrationWidget as CalibrationWidget
from .Util import newLogger as newLogger

__all__ = ['CalibrationWidget', 'FutabaDeviceDriver', 'FutabaDeviceManager', 'newLogger']

DeviceDriver = FutabaDeviceDriver
DeviceManager = FutabaDeviceManager
