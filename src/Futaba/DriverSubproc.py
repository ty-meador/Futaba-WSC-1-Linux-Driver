"""Worker module that contains the code which will run in a seperate process for each driver."""
# pylint: disable=import-outside-toplevel

from .__config__ import DeviceConfig

# Importing these is thread safe
from .InputChannel import InputChannel
from .IPC import WorkerControl


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

    NOTE:
        Main event loop optimization

        - we initialize a local version of everything that will be used inside the main event loop. The optimization works because:
            - Attribute lookups (like obj.method) generate LOAD_ATTR bytecode instructions that are slower than the LOAD_FAST instructions that are used for local variables.
            - By storing method references in local variables before the loop, the interpreter uses faster local variable access instead of attribute resolution
            - This reduces the number of bytecode instructions and eliminates repeated attribute traversal

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
        HID_INTERFACE_NUMBER,
    )
    from .Error import DeviceNotFoundError
    from .IPC import DataFrame

    logger = utils.newLogger(f"{name}_subproc")

    coreDevice = None
    coreDevice = utils.findEndpointDevice(interruptEndpoint)
    if coreDevice is None:
        raise DeviceNotFoundError

    logger.debug("Subprocess started")
    try:
        os.nice(-10)
    except PermissionError:
        logger.warning(
            "Warning: Cannot set process priority (Need CAP_SYS_NICE capability)"
        )

    # Extract and cache channel data arrays
    (
        channelEventsMap,
        channelValueMaps,
        channelIndexOffsets,
    ) = zip(
        *[
            (
                getattr(uinput, channel.eventName),
                channel.valueMap,
                channel.indexOffset,
            )
            for channel in deviceChannels
        ],
        strict=True,
    )

    noiseFilter = DEFAULT_NOISE_FILTER
    if deviceConfig.noiseFilter:
        noiseFilter = deviceConfig.noiseFilter

    deadZone = DEFAULT_DEADZONE
    if deviceConfig.deadZone:
        deadZone = deviceConfig.deadZone

    # Create a virtual device for the found device
    virtualDevice = uinput.Device(
        tuple(
            [
                event + (EVENT_MIN_VAL, EVENT_MAX_VAL, deadZone, noiseFilter)
                for event in channelEventsMap
            ]
        ),
        name,
        vendor=FUTABA_VENDOR_ID,
    )

    ##
    # Cache all attribute lookups to maximize main loop performance.
    # (See "Attributes Lookup" section in docstring above)
    ##
    product = coreDevice.product
    frameSize = deviceConfig.frameSize
    rawData = usb.util.create_buffer(frameSize) # Reusable buffer
    emit = virtualDevice.emit
    sync = virtualDevice.syn
    fromBytes = int.from_bytes
    killswitchIsSet = controller.killswitch.is_set
    setKillswitch = controller.killswitch.set
    runFlagIsSet = controller.runFlag.is_set
    echoFlagIsSet = controller.echoFlag.is_set
    clearEchoFlag = controller.echoFlag.clear
    pipe = controller.pipe
    pipePoll = pipe.poll
    pipeSend = pipe.send
    readDevice = coreDevice.read

    usbTimeoutError = usb.core.USBTimeoutError
    usbError = usb.core.USBError

    if coreDevice.is_kernel_driver_active(HID_INTERFACE_NUMBER):
        coreDevice.detach_kernel_driver(HID_INTERFACE_NUMBER)
    coreDevice.set_configuration()

    channelIsSigned = utils.parseAxisSignedness(
        utils.readReportDescriptor(coreDevice, HID_INTERFACE_NUMBER),
        len(deviceChannels),
    )

    logger.info("Driver started: %s -> %s", interruptEndpoint, name)

    # -- MAIN LOOP --
    # - Runs until main process sets the killswitch event
    # - if runFlag is not set then inputs will not be processed
    while not killswitchIsSet():
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
            bytesRead = readDevice(interruptEndpoint, rawData, timeout=250)

            # rawData is a reusable buffer, which retains its old contents. This check
            # ignores any reads that are less than the expected frame size to prevent
            # dispatching a mix of old and new values to the kernel
            if bytesRead != frameSize:
                continue

            ##
            # Usage Page (Generic Desktop) → Usage (Joystick)
            # Usages: X, Y, Z, Rx, Ry, Rz, Dial, Slider   ← 8 channels
            # Logical range 0–4096
            # Report Size 16 bits × Report Count 8 → Input (Data,Var,Abs)
            # The entire 46 bytes: exactly 8 × 16-bit axis values, nothing else.
            # No vendor-defined fields, no status bytes, no buttons, not even padding.
            ##
            for i in range(0, len(rawData), 2):
                channel = i // 2
                valueMap = channelValueMaps[channel]
                indexOffset = channelIndexOffsets[channel]
                rawValue = fromBytes(
                    rawData[i : i + 2],
                    byteorder="little",
                    signed=channelIsSigned[channel]
                )

                calibratedValue = valueMap[
                    # Clamp both ends of the axis range
                    max(0,min(rawValue + indexOffset, len(valueMap) - 1))
                ]

                # Pass our calibrated input to the virtual device
                emit(channelEventsMap[channel], calibratedValue, syn=False)

                if echoFlagIsSet() and not pipePoll(
                    0
                ):  # Echo back the data frames info - useful for calibration
                    try:
                        pipeSend(
                            DataFrame(
                                channelEventsMap[channel],
                                rawValue,
                                calibratedValue,
                            )
                        )
                    except BlockingIOError:
                        # Pipe is full - nobody's reading, disable echo
                        clearEchoFlag()
                        logger.warning("Echo disabled: pipe buffer full (no consumer)")
            # Fire all channel events at once
            sync()

        except usbTimeoutError:
            pass  # Ignore, happens if device doesn't send a frame for a bit
        except usbError as e:
            if e.errno == 19:  # Device disconnected
                logger.warning("device disconnected: %s", product)
                # Set our own killswitch and exit gracefully
                setKillswitch()
            else:
                logger.warning(e)
        except KeyboardInterrupt:
            # Set our own killswitch and exit gracefully
            setKillswitch()
        except Exception as e:
            # We want to capture everything and log it to a file and then re-raise it.
            # This is because this will be running in a seperate process and as such
            # print statements don't do much good.
            logger.critical(e)
            raise e

    # No need to cache these methods as we are out of the main event loop by this point
    logger.debug("Releasing the USB interface...")
    try:
        usb.util.release_interface(coreDevice, HID_INTERFACE_NUMBER)
    except Exception as e:
        logger.warning("Unable to release the USB interface %s", e)

    logger.debug("Reattaching the kernel ..")
    try:
        coreDevice.attach_kernel_driver(HID_INTERFACE_NUMBER)
    except Exception as e:
        logger.warning("Unable to reattach the kernel driver, %s", e)

    logger.debug("Resetting device...")
    try:
        coreDevice.reset()
    except Exception as e:
        logger.warning("Unable to reset the USB interface, %s", e)
