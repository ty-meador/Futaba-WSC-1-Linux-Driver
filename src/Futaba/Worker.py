"""Worker module that contains the code which will run in a seperate process for each driver."""
# ruff: noqa: PLC0415, C901, PLR0915, PLR0912

from enum import Enum, auto


class WorkerCommand(Enum):
    """Stores various worker commmand signals"""

    START = auto()
    STOP = auto()
    KILL = auto()


##
# Disabled mccabe linting as this function is specifically meant to be the
# target of a separate process. As such the function is more complex and
# contains more statments that would otherwise be tolerated
##
def run(killswitch, frameSize, deviceChannels, name, interruptEndpoint, pipe):
    """Start a worker for the given device with the given settings.

    This is meant to be run in a seperate process via
    `multiprocessing.Process(target=_workerProcess,...)`

    Args:
        killswitch (multiprocessing.Event): This worker will run an infinite loop until this event
        is set
        frameSize (int): The number of bytes to request from the usb device at one time
        deviceChannels (tuple of dict): a tuple where each value contained is a calibrated value map
        for its corresponding channel
        name (str): The name the device will show up as
        interruptEndpoint (int): The usb interrupt endpoint of the device that you want to start a
        driver for

    NOTE main event loop optimization:
        we initialize a local version of everything that will be used inside the main event loop.
        The optimization works because:

        - Attribute lookups (like obj.method) generate LOAD_ATTR bytecode instructions that are
        slower than LOAD_FAST instructions used for local variables
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
    from .Driver import DriverState
    from .Error import DeviceNotFoundError

    coreDevice = None
    logger = utils.newLogger(f"{name}_subproc")
    logger.debug("Subprocess started")
    coreDevice = utils.getCoreDevice(interruptEndpoint)

    if coreDevice is None:
        raise DeviceNotFoundError

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

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple([event + (0, utils.EVENT_MAX_VAL, 0, 0) for event in channelEventsMap]),
        name,
        vendor=utils.FUTABA_VENDOR_ID,
    )

    ##
    # Cache all attribute lookups to maximize main loop performance.
    # (See "Attributes Lookup" section in docstring above)
    ##
    channelEventsMap = tuple(reversed(channelEventsMap))
    # rawValues = [0] * len(deviceChannels) # For main process communication
    rawData = bytearray(frameSize)  # Reusable buffer
    emit = virtualDevice.emit
    fromBytes = int.from_bytes
    killswitchIsSet = killswitch.is_set
    poll = pipe.poll
    readDevice = coreDevice.read
    recv = pipe.recv
    send = pipe.send
    (
        RUNNING,
        STOPPED,
        INITIALIZING,
    ) = DriverState

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    logger.info(f"Driver started: {interruptEndpoint} -> {name}")

    # -- MAIN LOOP --
    # - Runs until main process sets the killswitch event
    # - If WorkerCommand.STOP is received on the provided duplex pipe, the USB inputs will
    # NOT be processed
    # - If WorkerCommand.START is received on the provided duplex pipe, the USB inputs WILL
    # be processsed
    state = RUNNING
    while not killswitchIsSet():
        try:
            # Check for command/control messages before we do anythying else
            if poll():
                msg = recv()
                if msg == WorkerCommand.START:
                    state = RUNNING
                elif msg == WorkerCommand.STOP:
                    state = STOPPED

            # Prevent busy waiting if we aren't actively running
            if state != RUNNING:
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
                # Avoid overflows and underflows
                # account for off-by-one
                maxInputVal = len(valueMap) - 1
                if rawValue > maxInputVal:
                    rawValue = maxInputVal
                # calibration map will always have an index 0, so we pull
                # the minimum value from that
                elif rawValue < 0:
                    rawValue = 0

                # Send data back to main process for calibration process,
                # monitoring, benchmarking,etc etc
                # send(rawData, valueMap[rawValue])
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
