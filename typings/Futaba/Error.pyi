from dataclasses import dataclass

@dataclass
class FutabaError(Exception): ...

@dataclass
class DeviceNotFoundError(FutabaError):
    message: str = ...
