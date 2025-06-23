import array
import json
import logging
import os
import re
from logging import handlers
from pathlib import Path

import numpy as np
import uinput
import usb

DEFAULT_CONFIG = {
    "frame_size": 16,
    "channel_events": [
        "ABS_X",
        "ABS_Y",
        "ABS_RX",
        "ABS_RY",
        "ABS_THROTTLE",
        "ABS_RUDDER",
        "ABS_TILT_X",
        "ABS_TILT_Y",
    ],
}

EVENT_MAX_VAL = 32768
EVENT_MIN_VAL = 0
DEFAULT_DEVICE_MIN_VAL = 704
DEFAULT_DEVICE_MAX_VAL = 3392

##
# Credit to https://github.com/shaozu/Futaba_T16IZ_Linux/blob/main/entry.py
# for this great starting point!
##
DEFAULT_CALIBRATION = [
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
    [[DEFAULT_DEVICE_MIN_VAL, DEFAULT_DEVICE_MAX_VAL], [EVENT_MIN_VAL, EVENT_MAX_VAL]],
]

FUTABA_VENDOR_ID = 4101


PRODUCTS = {
    "default": 999,
    "WSC-1": 10,
    "T16IZ": 11,
    10: "WSC-1",
    11: "T16IZ",
    999: "default",
}

CALIBRATION_PATH = None
CONFIG_PATH = None
LOG_PATH = None
SRC_PATH = None

for parent in Path(__file__).resolve().parents:
    if (parent / ".pylintrc").exists():
        PARENT = os.path.abspath(parent)
        SRC_PATH = os.path.join(PARENT, "src")
        LOG_PATH = os.path.join(PARENT, "logs")
        DRIVER_PATH = os.path.join(SRC_PATH, "driver")
        CONFIG_PATH = os.path.join(DRIVER_PATH, "configs")
        CALIBRATION_PATH = os.path.join(DRIVER_PATH, "calibrations")
        os.makedirs(LOG_PATH, exist_ok=True)
        break


def findInterruptEndpoint(device):
    """Find the USB interrupt endpoint for the provided device

    Args:
        device (usb.core.Device): The device that we want to emulate

    Raises:
        ValueError: Raised if the provided device is not an of type usb.core.device
        RuntimeError: Raised if the provided device does not have an endpoint

    Returns:
        int: The interrupt endpoint address
    """
    logger = newLogger("findInterruptEndpoint")
    logger.debug("looking for endpoint for device provided")

    if not isinstance(device, usb.core.Device):
        err = (
            f"Expected first param to be of type usb.core.Device, found {type(device)}"
        )
        logger.critical(err)
        raise ValueError(err)

    for config in device:
        for interface in config:
            for endpoint in interface:
                if (
                    usb.util.endpoint_direction(endpoint.bEndpointAddress)
                    == usb.util.ENDPOINT_IN
                    # 0x3 indicates interrupt endpoint
                    and endpoint.bmAttributes == 0x3
                ):
                    return endpoint.bEndpointAddress
    raise RuntimeError("No interrupt endpoint found!")


def getCoreDeviceInfo(bus, port):
    """Finds the core device on the given bus and port

    Args:
        bus (int): The bus of the device
        port (int): The port of the device

    Returns:
        usb.core.Device: The core device at the provided bus and port
    """

    logger = newLogger("getCoreDevice")
    logger.debug(f"looking for core device on bus {bus}, port {port}")
    results = [
        device
        for device in usb.core.find(find_all=True)
        if device.manufacturer.lower() == "futaba"
        and int(device.port_numbers[0]) == int(port)
        and int(device.bus) == int(bus)
    ]

    if len(results) != 1:
        logger.debug(f"Expected to find exactly 1 result, found {len(results)}")
        return False

    device = results[0]
    logger.debug(f"-> Found {results[0]}")
    return {
        "productID": device.idProduct,
        "serialNumber": device.serial_number,
        "product": device.product,
        "manufacturer": device.manufacturer,
        "speed": device.speed,
        "interruptEndpoint": findInterruptEndpoint(device),
    }


def newLogger(
    name="logs",
    fileName=None,
    level=logging.DEBUG,
):
    """Generates a logger

    Args:
        name (str): _description_
        maxSize (int, optional): Max file size of log files. Defaults to 5*1024*1024.
        backupCount (int, optional): Number of backup logs to keep in rotation. Defaults to 5
        level (loglevel, optional): The level the logger should output. Defaults to logging.WARNING.

    Returns:
        logger: The generated logger
    """
    if fileName is None:
        fileName = re.sub(r"\W", "_", name) + ".txt"

    handler = handlers.RotatingFileHandler(
        os.path.join(LOG_PATH, fileName),
        maxBytes=5 * 1024 * 1024,  # 5 megabytes
        backupCount=5,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s\t: %(message)s")
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def loadJsonFile(filePath):
    """Generic function to load a JSON file into a dictionary

    Args:
        filePath (str): The path to the json file you want to load

    Returns:
        dict: The parsed json
    """
    logger = newLogger("loadJsonFile")
    parsedJson = None

    try:
        logger.debug(f"> Looking for {filePath}")
        with open(filePath, "r", encoding="utf-8") as jsonFile:
            parsedJson = json.load(jsonFile)
        logger.debug("--> loaded!")
    except FileNotFoundError:
        # parsedJson defaults to None
        logger.debug("--> not found, returning >None<")

    return parsedJson


def eventDispatchWorker(
    killswitch,
    bus=None,
    config=None,
    deviceChannels=None,
    port=None,
    name=None,
):
    """The target function for the drivers' subprocess
    NOTE main event loop optimization:
        we initialize a local version of everything that will be used inside
        the main event loop. By doing this, the interpreter:
        - Does not have to re-create variables each iteration
        - Does not have to interpret dots, subscripts, etc
    """
    if (
        bus is None
        or deviceChannels is None
        or config is None
        or name is None
        or port is None
    ):
        raise TypeError("All parameters are required")

    logger = newLogger(name)
    channel = None
    coreDevice = None
    endpointAddress = None

    logger = newLogger(f"{name}(SUBPROC)")
    logger.debug(
        f"Subprocess started, searching for device {name} on bus {bus}, port {port}"
    )

    for device in usb.core.find(find_all=True):
        if int(device.port_numbers[0]) == int(port) and int(device.bus) == int(bus):
            coreDevice = device
            logger.debug(f"--> device found ({coreDevice})")
            break

    if coreDevice is None:
        raise TypeError(f"No device found at bus {bus} port {port}")

    for _config in coreDevice:
        for _interface in _config:
            for _endpoint in _interface:
                if (
                    usb.util.endpoint_direction(_endpoint.bEndpointAddress)
                    == usb.util.ENDPOINT_IN
                    and _endpoint.bmAttributes == 0x3
                ):
                    endpointAddress = _endpoint.bEndpointAddress
                    logger.debug(f"--> interrupt endpoint found ({endpointAddress})")
                    break

    if endpointAddress is None:
        raise TypeError("Unable to determine interrupt endpoint address")

    channelEventsMap = []
    channelReverseFlags = []
    channelValueMaps = []
    for channel in deviceChannels:
        channelEventsMap.append(getattr(uinput, channel.eventName))
        channelReverseFlags.append(channel.isReversed)
        channelValueMaps.append(channelValueMaps)
    channelEventsMap = tuple(channelEventsMap)
    channelReverseFlags = tuple(channelReverseFlags)
    channelValueMaps = tuple(channelValueMaps)

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple([event + (0, EVENT_MAX_VAL, 0, 0) for event in channelEventsMap]),
        name,
        vendor=FUTABA_VENDOR_ID,
    )

    # Create all variables outside the loop to avoid the overhead of
    # recreating them each iteration
    emit = virtualDevice.emit
    frameSize = config["frame_size"]
    fromBytes = int.from_bytes

    maxInputVal = None
    rawData = None
    readDevice = coreDevice.read
    synchronize = virtualDevice.syn
    logger.info(f"Driver started: {endpointAddress} -> {name}")

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    # -- MAIN LOOP --
    while not killswitch.is_set():
        try:
            # - The transmitter may not send a new frame if the inputs remain static
            # - No reason to care about timeouts
            # - - Long timeout length = less timeouts
            # - - Less timeouts = fewer exceptions caught
            # - - Fewer exceptions caught = less overhead
            rawData = readDevice(endpointAddress, frameSize, timeout=1000)

            channelData = []
            for i in range(0, len(rawData), 2):
                channel = i // 2
                valueMap = channelValueMaps[channel]

                rawValue = int(fromBytes(rawData[i : i + 2], byteorder="little"))

                # Avoid overflows and underflows
                # account for off-by-one
                maxInputVal = len(valueMap) - 1
                if rawValue > maxInputVal:
                    rawValue = maxInputVal
                # calibration map will always have an index 0, so we pull
                # the minimum value from that
                elif rawValue < 0:
                    rawValue = 0
                # Extract calibrated value from map
                channelData.append(valueMap[rawValue])
            channelData.reverse()

            # Queue one event for each channel
            for data, event in zip(channelData, channelEventsMap):
                # Queue one event for each channel
                emit(event, data, syn=False)
            # fire all queued events
            synchronize()
        except usb.core.USBError as e:
            # kaboom?
            if e.errno != 110:
                # Yes Rico, kaboom.
                logger.critical(e)
                raise e
        finally:
            try:
                logger.debug("Releasing the USB interface...")
                usb.util.release_interface(coreDevice, 0)
            except Exception as e:
                logger.warning(
                    "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)"
                )
                logger.warning(e)

            try:
                logger.debug("Reattaching the kernel driver...")
                coreDevice.attach_kernel_driver(0)
            except Exception as e:
                logger.warning(
                    "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)"
                )
                logger.warning(e)

            try:
                logger.debug("Resetting device...")
                coreDevice.reset()
            except Exception as e:
                logger.warning(
                    "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)"
                )
                logger.warning(e)
