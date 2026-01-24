from .IPC import WorkerControl as WorkerControl
from .InputChannel import InputChannel as InputChannel
from .__config__ import DeviceConfig as DeviceConfig

def run(controller: WorkerControl, deviceConfig: DeviceConfig, deviceChannels: list[InputChannel], name: str, interruptEndpoint: int) -> None: ...
