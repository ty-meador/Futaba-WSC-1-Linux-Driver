"""FutabaDeviceDriver worker function.

Contains the atomic function that runs as a separate process for each FutabaDeviceDriver.
"""
##
# Disabled mccabe linting as this function is specifically meant to be the
# target of a separate process. As such the function is more complex and
# contains more statments that would otherwise be tolerated
##
# ruff: noqa: PLC0415, C901, PLR0915, PLR0912


def run(
    frameSize,
    deviceChannels,
    name,
    interruptEndpoint,
    pipe=None,
):
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
        pipe (multiprocessing.Pipe): The pipe to use to communicate with the main process. defaults to None.

    NOTE main event loop optimization:
        we initialize a local version of everything that will be used inside the main event loop.
        By doing this, the interpreter:
        - Does not have to re-create variables each iteration
        - Does not have to interpret dots, subscripts, etc

    """
    # Import everything inside the function for process/thread safety
    import uinput
    import usb

    from . import (
        EVENT_MAX_VAL,
        FUTABA_VENDOR_ID,
        HID_INTERFACE,
        INTERRUPT_ENDPOINT_ATTRIBUTE,
        newLogger,
    )

    channel = None
    coreDevice = None
    logger = newLogger(f"{name}_subproc")
    logger.debug("Subprocess started")
    for _device in usb.core.find(find_all=True):
        if _device.idVendor != FUTABA_VENDOR_ID:
            continue
        for _config in _device:
            for _interface in _config:
                if _interface.bInterfaceClass != HID_INTERFACE:
                    continue
                for _endpoint in _interface:
                    if (
                        _endpoint.bmAttributes == INTERRUPT_ENDPOINT_ATTRIBUTE
                        and usb.util.endpoint_direction(_endpoint.bEndpointAddress)
                        == usb.util.ENDPOINT_IN
                        and _endpoint.bEndpointAddress == interruptEndpoint
                    ):
                        interruptEndpoint = _endpoint.bEndpointAddress
                        coreDevice = _device
                        logger.debug(
                            f"Device at endpoint {interruptEndpoint}: {coreDevice}",
                        )
                        break

    if coreDevice is None:
        raise TypeError(
            f"No Futaba device found at interrupt endpoint {interruptEndpoint}",
        )

    channelEventsMap = []
    channelValueMaps = []
    for channel in deviceChannels:
        channelEventsMap.append(getattr(uinput, channel["eventName"]))
        channelValueMaps.append(channel["valueMap"])
    channelEventsMap = tuple(channelEventsMap)
    channelValueMaps = tuple(channelValueMaps)

    logger.debug("maps created")

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple([event + (0, EVENT_MAX_VAL, 0, 0) for event in channelEventsMap]),
        name,
        vendor=FUTABA_VENDOR_ID,
    )

    logger.debug("virtual device set up")

    # Create all variables outside the loop to avoid the overhead of
    # recreating them each iteration
    emit = virtualDevice.emit
    fromBytes = int.from_bytes
    maxInputVal = None
    rawData = None
    readDevice = coreDevice.read
    runFlag = True
    synchronize = virtualDevice.syn

    if coreDevice.is_kernel_driver_active(0):
        coreDevice.detach_kernel_driver(0)
    coreDevice.set_configuration()

    logger.info(f"Driver started: {interruptEndpoint} -> {name}")

    # -- MAIN LOOP --
    while runFlag:
        try:
            # - The transmitter may not send a new frame if the inputs remain
            # static
            # - No reason to care about timeouts
            # - - Long timeout length = less timeouts
            # - - Less timeouts = fewer exceptions raised
            # - - Fewer exceptions raised = less overhead
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
            if pipe is not None:
                pipe.put(channelData, False)
            # Queue one event for each channel
            for data, event in zip(channelData, channelEventsMap, strict=False):
                # Queue one event for each channel
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
