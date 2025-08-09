"""Worker module that contains the code which will run in a seperate process for each driver."""
# ruff: noqa: PLC0415, C901, PLR0915, PLR0912

import multiprocessing
from enum import Enum, auto

from .InputChannel import ChannelDict
from .Util import DeviceConfig


class WorkerCommand(Enum):
    """Stores various worker commmand signals."""

    START = auto()
    STOP = auto()
    KILL = auto()


##
# Disabled mccabe linting as this function is specifically meant to be the
# target of a separate process. As such the function is more complex and
# contains more statments that would otherwise be tolerated
##
def run(
    killswitch: multiprocessing.Event,
    runFlag: multiprocessing.Event,
    deviceConfig: DeviceConfig,
    deviceChannels: list[ChannelDict],
    name: str,
    interruptEndpoint: int,
) -> None:
    """Start a worker for the given device with the given settings.

    This is meant to be run in a seperate process via
    `multiprocessing.Process(target=_workerProcess,...)`

    Args:
        killswitch (multiprocessing.Event): This worker will run an infinite loop until this event
        is set.
        runFlag (multiprocessing.Event): This worker will process device inputs if this is set.
        frameSize (int): The number of bytes to request from the usb device at one time.
        deviceChannels (list[ChannelDict]) a tuple where each value contained is a calibrated value
        map for its corresponding channel.
        name (str): The name the device will show up as.
        interruptEndpoint (int): The usb interrupt endpoint of the device that you want to start a
        driver for.

    NOTE main event loop optimization:
        we initialize a local version of everything that will be used inside the main event loop.
        The optimization works because:

        - Attribute lookups (like obj.method) generate LOAD_ATTR bytecode instructions that are
        slower than the LOAD_FAST instructions that are used for local variables.
        - By storing method references in local variables before the loop, the interpreter uses
        faster local variable access instead of attribute resolution
        - This reduces the number of bytecode instructions and eliminates repeated attribute
        traversal

    """
    import os
    from time import sleep

    import uinput
    import usb

    from . import Util as utils
    from .Error import DeviceNotFoundError

    logger = utils.newLogger(f"{name}_subproc")

    coreDevice = None
    coreDevice = utils.getCoreDevice(interruptEndpoint)
    if coreDevice is None:
        raise DeviceNotFoundError

    logger.debug("Subprocess started")

    # Set realtime priority at the start of the process
    try:
        # SCHED_FIFO with priority 99 (highest realtime priority)
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(99))
    except PermissionError:
        print("Warning: Need CAP_SYS_NICE capability or root for realtime scheduling")
        try:
            # Fallback to highest nice priority
            os.nice(-20)
        except PermissionError:
            print("Warning: Cannot set process priority")

    # Extract event names and value maps from device channels in parallel
    # zip(*[...]) unpacks the list of tuples and transposes them:
    # - channelEventsMap gets all the uinput event attributes
    # - channelValueMaps gets all the corresponding value mapping dictionaries
    # strict=True force a 1:1 mapping between events and values
    channelEventsMap, channelValueMaps = zip(
        *[
            (getattr(uinput, channel["eventName"]), channel["valueMap"])
            for channel in deviceChannels
        ],
        strict=True,
    )
    noiseFilter = (
        deviceConfig.noiseFilter if deviceConfig.noiseFilter else utils.DEFAULT_NOISE_FILTER
    )
    deadZone = deviceConfig.deadZone if deviceConfig.deadZone else utils.DEFAULT_DEADZONE
    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple(
            [
                event
                + (
                    utils.EVENT_MIN_VAL,
                    utils.EVENT_MAX_VAL,
                    deadZone,
                    noiseFilter,
                )
                for event in channelEventsMap
            ]
        ),
        name,
        vendor=utils.FUTABA_VENDOR_ID,
    )

    ##
    # Cache all attribute lookups to maximize main loop performance.
    # (See "Attributes Lookup" section in docstring above)
    ##
    frameSize = deviceConfig.frameSize

    channelEventsMap = tuple(reversed(channelEventsMap))
    rawData = bytearray(frameSize)  # Reusable buffer
    emit = virtualDevice.emit
    fromBytes = int.from_bytes
    killswitchIsSet = killswitch.is_set
    readDevice = coreDevice.read

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    logger.info(f"Driver started: {interruptEndpoint} -> {name}")

    # -- MAIN LOOP --
    # - Runs until main process sets the killswitch event
    # - if runFlag is not set then inputs will not be processed
    while not killswitchIsSet():
        rawData = None
        try:
            # Prevent busy waiting if we aren't actively running
            if not runFlag.is_set():
                sleep(0.01)
                continue

            ## RUNNING ##
            # - The transmitter may not send a new frame if the inputs remain
            # static, causing read() to block until timeout
            # - When frames are actively being sent, timeout length has no performance
            # impact as read() returns immediately with data
            # - During idle periods (static inputs), longer timeouts reduce the
            # frequency of timeout exceptions, minimizing polling overhead
            # - 250ms timeout reduces exception frequency during idle periods
            # while remaining reasonable for process shutdown timing
            rawData = readDevice(interruptEndpoint, frameSize, timeout=250)

            for i in range(0, len(rawData), 2):
                channel = i // 2
                valueMap = channelValueMaps[channel]
                rawValue = int(fromBytes(rawData[i : i + 2], byteorder="little"))

                # Avoid index OOB errors
                maxInputVal = len(valueMap) - 1  # account for off-by-one
                if rawValue > maxInputVal:
                    rawValue = maxInputVal
                elif rawValue < 0:
                    rawValue = 0

                emit(  # Pass our calibrated input to the virtual device
                    channelEventsMap[channel],
                    valueMap[rawValue],
                    syn=True,
                )
        except usb.core.USBTimeoutError:
            pass
        except KeyboardInterrupt:
            pass
        except Exception as e:
            # We want to capture everything and log it to a file and then re-raise it.
            # This is because this will be running in a seperate process and such such
            # print statements don't do much good.
            logger.critical(e)
            raise e

    logger.debug("Releasing the USB interface...")
    try:
        usb.util.release_interface(coreDevice, 0)
    except Exception as e:
        logger.warning(f"Unable to release the USB interface, {e}")

    logger.debug("Reattaching the kernel ..")
    try:
        coreDevice.attach_kernel_driver(0)
    except Exception as e:
        logger.warning(f"Unable to reattach the kernel driver, {e}")

    logger.debug("Resetting device...")
    try:
        coreDevice.reset()
    except Exception as e:
        logger.warning(f"Unable to reset the USB interface, {e}")
