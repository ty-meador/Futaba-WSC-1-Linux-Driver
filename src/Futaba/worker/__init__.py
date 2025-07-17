"""Worker module that contains the code which will run in a seperate process for each driver."""
# ruff: noqa: PLC0415, C901, PLR0915, PLR0912


##
# Disabled mccabe linting as this function is specifically meant to be the
# target of a separate process. As such the function is more complex and
# contains more statments that would otherwise be tolerated
##
def run(killswitch, frameSize, deviceChannels, name, interruptEndpoint):
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
    import uinput
    import usb

    from .. import errors, utils

    coreDevice = None
    logger = utils.newLogger(f"{name}_subproc")
    logger.debug("Subprocess started")
    coreDevice = utils.getCoreDevice(interruptEndpoint)

    if coreDevice is None:
        raise errors.DeviceNotFoundError

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

    logger.debug("maps created")

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple([event + (0, utils.EVENT_MAX_VAL, 0, 0) for event in channelEventsMap]),
        name,
        vendor=utils.FUTABA_VENDOR_ID,
    )

    logger.debug("virtual device set up")

    emit = virtualDevice.emit
    fromBytes = int.from_bytes
    killswitchIsSet = killswitch.is_set
    readDevice = coreDevice.read
    synchronize = virtualDevice.syn

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    logger.info(f"Driver started: {interruptEndpoint} -> {name}")
    # -- MAIN LOOP --
    while not killswitchIsSet():
        try:
            # - The transmitter may not send a new frame if the inputs remain
            # static, causing read() to block until timeout
            # - When frames are actively being sent, timeout length has no performance
            # impact as read() returns immediately with data
            # - During idle periods (static inputs), longer timeouts reduce the
            # frequency of timeout exceptions, minimizing polling overhead
            # - 250ms timeout reduces exception frequency during idle periods
            # while remaining reasonable for process shutdown timing
            rawData = readDevice(interruptEndpoint, frameSize, timeout=250)
            channelData = []
            rawValues = []

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
                rawValues.append(rawValue)
                channelData.append(valueMap[rawValue])
            channelData.reverse()

            # Queue one event for each channel
            for data, event in zip(channelData, channelEventsMap, strict=True):
                emit(event, data, syn=False)

            # fire all queued events
            synchronize()
        except usb.core.USBTimeoutError:
            pass
        except KeyboardInterrupt:
            pass
        except Exception as e:
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
