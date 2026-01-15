"""Worker module that contains the code which will run in a seperate process for each driver."""
# pylint: disable=import-outside-toplevel

from .InputChannel import InputChannel
from .IPC import WorkerControl
from .__config__ import DeviceConfig


def run(
    controller: WorkerControl,
    deviceConfig: DeviceConfig,
    deviceChannels: list[InputChannel],
    name: str,
    interruptEndpoint: int,
) -> None:
    """Start a worker for the given device with the given settings.

    This is meant to be run in a seperate process via
    `multiprocessing.Process(target=_workerProcess,...)`

    Args:
        controller (WorkerControl): The worker controller used to control this subproc
        deviceConfig (dict): The devices configuration.
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
    from .__config__ import (
        DEFAULT_DEADZONE,
        DEFAULT_NOISE_FILTER,
        EVENT_MAX_VAL,
        EVENT_MIN_VAL,
        FUTABA_VENDOR_ID,
    )
    from .Error import DeviceNotFoundError
    from .IPC import DataFrame

    logger = utils.newLogger(f"{name}_subproc")

    coreDevice = None
    coreDevice = utils.findEndpointDevice(interruptEndpoint)
    if coreDevice is None:
        raise DeviceNotFoundError

    logger.debug("Subprocess started")

    # Set realtime priority at the start of the process
    try:
        # SCHED_FIFO with priority 99 (highest realtime priority)
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(99))
    except PermissionError:
        logger.warning("Warning: Need CAP_SYS_NICE capability or root for realtime scheduling")
        try:
            # Fallback to highest nice priority
            os.nice(-20)
        except PermissionError:
            logger.warning("Warning: Cannot set process priority")

    channelEventsMap, channelValueMaps, channelIndexOffsets = zip(
        *[(
            getattr(uinput, channel.eventName),
            channel.valueMap,
            channel.indexOffset,
        ) for channel in deviceChannels],
        strict=True,
    )

    noiseFilter = DEFAULT_NOISE_FILTER
    if deviceConfig.noiseFilter:
        noiseFilter = deviceConfig.noiseFilter

    deadZone = DEFAULT_DEADZONE
    if deviceConfig.deadZone:
        deadZone = deviceConfig.deadZone

    # Create a virtual device for the found device
    channelEventsMap = tuple(channelEventsMap)
    virtualDevice = uinput.Device(
        tuple([
            event + (EVENT_MIN_VAL, EVENT_MAX_VAL, deadZone, noiseFilter)
            for event in channelEventsMap
        ]),
        name,
        vendor=FUTABA_VENDOR_ID,
    )

    ##
    # Cache all attribute lookups to maximize main loop performance.
    # (See "Attributes Lookup" section in docstring above)
    ##
    product = coreDevice.product
    frameSize = deviceConfig.frameSize
    rawData = bytearray(frameSize)  # Reusable buffer
    emit = virtualDevice.emit
    sync = virtualDevice.syn
    fromBytes = int.from_bytes
    killswitchIsSet = controller.killswitch.is_set
    runFlagIsSet = controller.runFlag.is_set
    echoFlagIsSet = controller.echoFlag.is_set
    pipe = controller.pipe
    readDevice = coreDevice.read

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    logger.info("Driver started: %s -> %s", interruptEndpoint, name)

    # -- MAIN LOOP --
    # - Runs until main process sets the killswitch event
    # - if runFlag is not set then inputs will not be processed
    while not killswitchIsSet():
        rawData = None
        try:
            # Prevent busy waiting if we aren't actively running
            if not runFlagIsSet():
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
                indexOffset = channelIndexOffsets[channel]
                rawValue = int(fromBytes(rawData[i:i + 2], byteorder="little"))

                # Avoid index OOB errors
                maxInputVal = len(valueMap) - 1
                if rawValue > maxInputVal:
                    rawValue = maxInputVal
                # The way that we generate the calibration table means there will always be an
                # "index 0", and it will always have the lowest possible value.
                elif rawValue < 0:
                    rawValue = 0

                calibratedValue = valueMap[rawValue + indexOffset]

                emit(  # Pass our calibrated input to the virtual device
                    channelEventsMap[channel],
                    calibratedValue,
                    syn=False,
                )

                if echoFlagIsSet():  # Echo back the data frames info - useful for calibration
                    # Only send if there's space (non-blocking check)
                    if not pipe.poll(0):  # Check if pipe has data waiting to be read
                        try:
                            pipe.send(DataFrame(
                                channelEventsMap[channel],
                                rawValue,
                                calibratedValue,
                            ))
                        except BlockingIOError:
                            # Pipe is full - nobody's reading, disable echo
                            controller.echoFlag.clear()
                            logger.warning("Echo disabled: pipe buffer full (no consumer)")
                    # pipe.send(DataFrame(
                    #     channelEventsMap[channel],
                    #     rawValue,
                    #     calibratedValue,
                    # ))
            # Fire all channel events at once
            sync()

        except usb.core.USBTimeoutError:
            pass  # Ignore, happens if device doesn't send a frame for a bit
        except usb.core.USBError as e:
            if e.errno == 19:  # Device disconnected
                logger.warning("device disconnected: %s", product)
                # Set our own killswitch and exit gracefully
                controller.killswitch.set()
            else:
                logger.warning(e)
        except KeyboardInterrupt:
            # Set our own killswitch and exit gracefully
            controller.killswitch.set()
        except Exception as e:
            # We want to capture everything and log it to a file and then re-raise it.
            # This is because this will be running in a seperate process and as such
            # print statements don't do much good.
            logger.critical(e)
            raise e

    logger.debug("Releasing the USB interface...")
    try:
        usb.util.release_interface(coreDevice, 0)
    except Exception as e:
        logger.warning("Unable to release the USB interface %s", e)

    logger.debug("Reattaching the kernel ..")
    try:
        coreDevice.attach_kernel_driver(0)
    except Exception as e:
        logger.warning("Unable to reattach the kernel driver, %s", e)

    logger.debug("Resetting device...")
    try:
        coreDevice.reset()
    except Exception as e:
        logger.warning("Unable to reset the USB interface, %s", e)
