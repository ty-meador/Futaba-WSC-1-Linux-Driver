# Type stubs for PyUSB - minimal version that handles dynamic attributes
from typing import Any

# Allow any attribute access on the usb module and its submodules
def __getattr__(name: str) -> Any: ...