"""A worker function that hooks the specified device and starts the driver with the given parameters"""

import uinput
import usb

import driver


def start(
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

    logger = driver.getLogger(name)
    channel = None
    endpointAddress = None

    logger = driver.getLogger(f"{name}(SUBPROC)")
    logger.DEBUG(
        f"Subprocess started, searching for device {name} on bus {bus}, port {port}"
    )

    coreDevice = [
        device
        for device in usb.core.find(find_all=True)
        if int(device.port_number) == int(port) and int(device.bus_) == int(bus)
    ][0]

    logger.DEBUG(
        f"--> device found ({coreDevice}), searching for interrupt endpoint address"
    )
    for _config in coreDevice:
        for _interface in _config:
            for _endpoint in _interface:
                if (
                    usb.util.endpoint_direction(_endpoint.bEndpointAddress)
                    == usb.util.ENDPOINT_IN
                    and _endpoint.bmAttributes == 0x3
                ):
                    endpointAddress = _endpoint.bEndpointAddress
                    logger.DEBUG(f"----> address found ({endpointAddress})")
                    break
    if coreDevice is None:
        raise TypeError(
            f"Unable to locate A device with an interrupt endpoint at {endpointAddress}"
        )

    channelEventsMap = []
    channelReverseFlags = []
    channelValueMaps = []
    for channel in deviceChannels:
        channelEventsMap.append(getattr(uinput, channel.eventName))
        channelReverseFlags.append(channel.isReversed)
        channelValueMaps.append(channelValueMaps)
    channelEventsMap = tuple(channelEventsMap)
    channelReverseFlags = tuple(channelReverseFlags)
    channelReverseFlags = tuple(channelReverseFlags)

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple([event + (0, driver.EVENT_MAX_VAL, 0, 0) for event in channelEventsMap]),
        name,
        vendor=driver.FUTABA_VENDOR_ID,
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
            for (
                data,
                event,
                reverseFlag,
            ) in zip(
                channelData,
                channelEventsMap,
                channelReverseFlags,
            ):
                if reverseFlag:
                    data = driver.EVENT_MAX_VAL - data
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
