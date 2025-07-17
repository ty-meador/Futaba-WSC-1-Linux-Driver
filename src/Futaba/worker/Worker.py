"""debug module."""

# ruff: noqa: PLC0415
import multiprocessing


class Worker(multiprocessing.Process):
    """Custom Process subclass with start/stop functionality."""

    def __init__(
        self,
        coreDevice,
        deviceChannels,
        frameSize,
        name,
    ):
        # Call parent constructor
        super().__init__()

        # Custom attributes
        self.coreDevice = coreDevice
        self.name = name
        self.deviceChannels = deviceChannels
        self.frameSize = frameSize
        # Control attributes for start/stop functionality
        self.control_queue = multiprocessing.Queue()
        self.status_queue = multiprocessing.Queue()
        self.is_running = False
        self.should_terminate = False

    def run(self):  # noqa: C901, PLR0912, PLR0915
        """Start the main event loop."""
        import os
        from contextlib import suppress

        import uinput
        import usb

        from .. import errors, utils

        logger = utils.newLogger(f"{self.name}_subproc")

        coreDevice = self.coreDevice
        deviceChannels = self.deviceChannels
        frameSize = self.frameSize
        interruptEndpoint = utils.findInterruptEndpoint(coreDevice)
        name = self.name
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
        readDevice = coreDevice.read
        synchronize = virtualDevice.syn

        if coreDevice.is_kernel_driver_active(0):
            coreDevice.detach_kernel_driver(0)
        coreDevice.set_configuration()

        logger.debug("Subprocess started")

        if coreDevice is None:
            raise errors.DeviceNotFoundError

        print(f"Process {self.task_name} initialized (PID: {os.getpid()})")
        while not self.should_terminate:
            try:
                # Check for control commands (non-blocking)
                with suppress(Exception):
                    command = self.control_queue.get_nowait()
                    if command == "start":
                        self.is_running = True
                        print(f"Process {self.task_name} started execution")
                        self.status_queue.put("started")
                    elif command == "stop":
                        self.is_running = False
                        self.status_queue.put("stopped")
                    elif command == "terminate":
                        self.should_terminate = True
                        print(f"Process {self.task_name} terminating")
                        self.status_queue.put("terminated")
                        break

                # Execute task if running
                if self.is_running:
                    # -- MAIN LOOP --
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

    def start_execution(self):
        """Start the execution of the process task."""
        self.control_queue.put("start")
        # Wait for confirmation
        try:
            status = self.status_queue.get(timeout=1)
            return status == "started"
        except TimeoutError:
            return False

    def stop_execution(self):
        """Stop the execution of the process task."""
        self.control_queue.put("stop")
        # Wait for confirmation
        try:
            status = self.status_queue.get(timeout=1)
            return status == "stopped"
        except TimeoutError:
            return False

    def terminate_process(self):
        """Terminate the process entirely."""
        self.control_queue.put("terminate")
        # Wait for confirmation
        try:
            status = self.status_queue.get(timeout=1)
            return status == "terminated"
        except TimeoutError:
            return False


# # Usage example
# if __name__ == "__main__":
#     # Create a queue to collect results
#     result_queue = multiprocessing.Queue()

#     # Create custom process
#     process = CustomProcess("ControllableTask", [1, 2, 3, 4, 5], result_queue)

#     # Start the process (this creates the process but doesn't start execution)
#     process.start()

#     print("Process created and waiting for commands...")
#     time.sleep(1)

#     # Start execution
#     print("Starting execution...")
#     process.start_execution()
#     time.sleep(1)

#     # Stop execution
#     print("Stopping execution...")
#     process.stop_execution()
#     time.sleep(1)

#     # Start again
#     print("Starting execution again...")
#     process.start_execution()
#     time.sleep(1.5)

#     # Stop again
#     print("Stopping execution again...")
#     process.stop_execution()
#     time.sleep(1)

#     # Terminate the process
#     print("Terminating process...")
#     process.terminate_process()

#     # Wait for process to complete
#     process.join()

#     # Collect results from queue
#     results = []
#     while not result_queue.empty():
#         results.append(result_queue.get())

#     print("\nResults:")
#     for result in results:
#         print(
#             f"Task: {result['task_name']}, Result: {result.get('result', result.get('error'))}, Time: {result.get('timestamp')}"
#         )
