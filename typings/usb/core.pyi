# Copyright 2009-2017 Wander Lairson Costa
# Copyright 2009-2021 PyUSB contributors
#
# Type stub for usb.core module

import array
import threading
from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
    overload,
)

from typing_extensions import Self

# Type aliases for better readability
_BytesLike = Union[bytes, bytearray, array.array[int]]
_BufferLike = Union[int, array.array[int]]
_EndpointAddress = Union[int, 'Endpoint']

__author__: str
__all__: List[str]

_DEFAULT_TIMEOUT: int
_sentinel: object


def _set_attr(input: Any, output: Any, fields: Tuple[str, ...]) -> None:
    ...


def _try_getattr(object: Any, name: str) -> Any:
    ...


def _try_get_string(
    dev: 'Device',
    index: int,
    langid: Optional[int] = ...,
    default_str_i0: str = ...,
    default_access_error: str = ...
) -> str:
    ...


def _try_lookup(table: Dict[Any, str], value: Any, default: str = ...) -> str:
    ...


class _DescriptorInfo(str):
    def __repr__(self) -> str:
        ...


def synchronized(f: Callable[..., Any]) -> Callable[..., Any]:
    ...


class _ResourceManager:
    backend: Any
    _active_cfg_index: Optional[int]
    dev: Any
    handle: Optional[Any]
    _claimed_intf: Set[int]
    _intf_setting: Dict[int, int]
    _ep_info: Dict[int, Tuple['Interface', 'Endpoint']]
    lock: threading.RLock

    def __init__(self, dev: Any, backend: Any) -> None:
        ...

    def managed_open(self) -> Any:
        ...

    def managed_close(self) -> None:
        ...

    def managed_set_configuration(
        self, device: 'Device', config: Union[None, 'Configuration', int]
    ) -> None:
        ...

    def managed_claim_interface(self, device: 'Device', intf: Union['Interface', int]) -> None:
        ...

    def managed_release_interface(
        self, device: 'Device', intf: Union['Interface', int, None]
    ) -> None:
        ...

    def managed_set_interface(
        self, device: 'Device', intf: Union['Interface', int, None], alt: Optional[int]
    ) -> None:
        ...

    def setup_request(self, device: 'Device',
                      endpoint: _EndpointAddress) -> Tuple['Interface', 'Endpoint']:
        ...

    def get_interface_and_endpoint(self, device: 'Device',
                                   endpoint_address: int) -> Tuple['Interface', 'Endpoint']:
        ...

    def get_active_configuration(self, device: 'Device') -> 'Configuration':
        ...

    def release_all_interfaces(self, device: 'Device') -> None:
        ...

    def dispose(self, device: 'Device', close_handle: bool = ...) -> None:
        ...


class USBError(IOError):
    backend_error_code: Optional[Any]

    def __init__(
        self, strerror: str, error_code: Optional[Any] = ..., errno: Optional[int] = ...
    ) -> None:
        ...


class USBTimeoutError(USBError):
    ...


class NoBackendError(ValueError):
    ...


class Endpoint:
    device: 'Device'
    index: int
    bLength: int
    bDescriptorType: int
    bEndpointAddress: int
    bmAttributes: int
    wMaxPacketSize: int
    bInterval: int
    bRefresh: int
    bSynchAddress: int
    extra_descriptors: Any

    def __init__(
        self,
        device: 'Device',
        endpoint: int,
        interface: int = ...,
        alternate_setting: int = ...,
        configuration: int = ...
    ) -> None:
        ...

    def __repr__(self) -> str:
        ...

    def __str__(self) -> str:
        ...

    def write(self, data: _BytesLike, timeout: Optional[int] = ...) -> int:
        ...

    @overload
    def read(self, size_or_buffer: int, timeout: Optional[int] = ...) -> array.array[int]:
        ...

    @overload
    def read(self, size_or_buffer: array.array[int], timeout: Optional[int] = ...) -> int:
        ...

    def clear_halt(self) -> None:
        ...

    def _str(self) -> str:
        ...


class Interface:
    device: 'Device'
    alternate_index: int
    index: int
    configuration: int
    bLength: int
    bDescriptorType: int
    bInterfaceNumber: int
    bAlternateSetting: int
    bNumEndpoints: int
    bInterfaceClass: int
    bInterfaceSubClass: int
    bInterfaceProtocol: int
    iInterface: int
    extra_descriptors: Any

    def __init__(
        self,
        device: 'Device',
        interface: int = ...,
        alternate_setting: int = ...,
        configuration: int = ...
    ) -> None:
        ...

    def __repr__(self) -> str:
        ...

    def __str__(self) -> str:
        ...

    def endpoints(self) -> Tuple[Endpoint, ...]:
        ...

    def set_altsetting(self) -> None:
        ...

    def __iter__(self) -> Iterator[Endpoint]:
        ...

    def __getitem__(self, index: int) -> Endpoint:
        ...

    def _str(self) -> str:
        ...

    def _get_full_descriptor_str(self) -> str:
        ...


class Configuration:
    device: 'Device'
    index: int
    bLength: int
    bDescriptorType: int
    wTotalLength: int
    bNumInterfaces: int
    bConfigurationValue: int
    iConfiguration: int
    bmAttributes: int
    bMaxPower: int
    extra_descriptors: Any

    def __init__(self, device: 'Device', configuration: int = ...) -> None:
        ...

    def __repr__(self) -> str:
        ...

    def __str__(self) -> str:
        ...

    def interfaces(self) -> Tuple[Interface, ...]:
        ...

    def set(self) -> None:
        ...

    def __iter__(self) -> Iterator[Interface]:
        ...

    def __getitem__(self, index: Tuple[int, int]) -> Interface:
        ...

    def _get_power_multiplier(self) -> int:
        ...

    def _str(self) -> str:
        ...

    def _get_full_descriptor_str(self) -> str:
        ...


class Device:
    _ctx: _ResourceManager
    __default_timeout: int
    _serial_number: Optional[str]
    _product: Optional[str]
    _manufacturer: Optional[str]
    _langids: Optional[Tuple[int, ...]]
    bLength: int
    bDescriptorType: int
    bcdUSB: int
    bDeviceClass: int
    bDeviceSubClass: int
    bDeviceProtocol: int
    bMaxPacketSize0: int
    idVendor: int
    idProduct: int
    bcdDevice: int
    iManufacturer: int
    iProduct: int
    iSerialNumber: int
    bNumConfigurations: int
    address: Optional[int]
    bus: Optional[int]
    port_number: Optional[int]
    port_numbers: Optional[List[int]]
    speed: Optional[int]
    _has_parent: Optional[bool]
    _parent: Optional['Device']

    def __init__(self, dev: Any, backend: Any) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...

    def __repr__(self) -> str:
        ...

    def __str__(self) -> str:
        ...

    def configurations(self) -> Tuple[Configuration, ...]:
        ...

    @property
    def langids(self) -> Tuple[int, ...]:
        ...

    @property
    def serial_number(self) -> str:
        ...

    @property
    def product(self) -> str:
        ...

    @property
    def parent(self) -> Optional['Device']:
        ...

    @property
    def manufacturer(self) -> str:
        ...

    @property
    def backend(self) -> Any:
        ...

    @property
    def default_timeout(self) -> int:
        ...

    @default_timeout.setter
    def default_timeout(self, value: int) -> None:
        ...

    def set_configuration(self, configuration: Union[None, Configuration, int] = ...) -> None:
        ...

    def get_active_configuration(self) -> Configuration:
        ...

    def set_interface_altsetting(
        self,
        interface: Union[Interface, int, None] = ...,
        alternate_setting: Optional[int] = ...
    ) -> None:
        ...

    def clear_halt(self, ep: _EndpointAddress) -> None:
        ...

    def reset(self) -> None:
        ...

    def write(
        self, endpoint: _EndpointAddress, data: _BytesLike, timeout: Optional[int] = ...
    ) -> int:
        ...

    @overload
    def read(self,
             endpoint: _EndpointAddress,
             size_or_buffer: int,
             timeout: Optional[int] = ...) -> array.array[int]:
        ...

    @overload
    def read(
        self,
        endpoint: _EndpointAddress,
        size_or_buffer: array.array[int],
        timeout: Optional[int] = ...
    ) -> int:
        ...

    def ctrl_transfer(
        self,
        bmRequestType: int,
        bRequest: int,
        wValue: int = ...,
        wIndex: int = ...,
        data_or_wLength: Union[None, int, _BytesLike, array.array[int]] = ...,
        timeout: Optional[int] = ...
    ) -> Union[int, array.array[int]]:
        ...

    def is_kernel_driver_active(self, interface: int) -> bool:
        ...

    def detach_kernel_driver(self, interface: int) -> None:
        ...

    def attach_kernel_driver(self, interface: int) -> None:
        ...

    def __iter__(self) -> Iterator[Configuration]:
        ...

    def __getitem__(self, index: int) -> Configuration:
        ...

    def _finalize_object(self) -> None:
        ...

    def _str(self) -> str:
        ...

    def _get_full_descriptor_str(self) -> str:
        ...


@overload
def find(
    find_all: Literal[True],
    backend: Optional[Any] = ...,
    custom_match: Optional[Callable[[Device], bool]] = ...,
    **args: Any
) -> Iterator[Device]:
    ...


@overload
def find(
    find_all: Literal[False] = ...,
    backend: Optional[Any] = ...,
    custom_match: Optional[Callable[[Device], bool]] = ...,
    **args: Any
) -> Optional[Device]:
    ...


def show_devices(verbose: bool = ..., **kwargs: Any) -> _DescriptorInfo:
    ...
