from .__config__ import DeviceConfig as DeviceConfig
from .InputChannel import InputChannel as InputChannel
from .IPC import WorkerControl as WorkerControl

def run(controller: WorkerControl, deviceConfig: DeviceConfig, deviceChannels: list[InputChannel], name: str, interruptEndpoint: int) -> None: ...
