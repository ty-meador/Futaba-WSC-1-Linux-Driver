"""The main program - run with `sudo python3 main.py`"""

import subprocess
import time

import usb

import utils


def main():
    """Starts a driver in a subprocess for each Futaba USB device found

    Raises:
        Exception: If not Futaba USB devices are detected
    """
    try:
        futabaDevices = findFutabaDevices()
        if len(futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")
        subprocs = startDrivers(futabaDevices)
        monitorDrivers(subprocs)
    except KeyboardInterrupt:
        pass


def monitorDrivers(subprocs):
    """A blocking function that infinitely monitors the provided subprocesses until they all exit

    Args:
        subprocs (list of subprocess): A list of subprocesses
    """
    running = len(subprocs)
    while running > 0:
        running = 0
        stopped = 0
        time.sleep(1)
        for subproc in subprocs:
            if subproc.poll() is None:
                running += 1
            else:
                stopped += 1


def findFutabaDevices():
    """Finds all Futaba USB devices that are currently connected

    Returns:
        list of usb.core.Device: A list of Futaba usb device handles
    """
    devices = []
    for device in usb.core.find(find_all=True):
        if device.manufacturer.lower() == "futaba":
            devices.append(device)
    return devices


def startDrivers(futabaDevices):
    """Starts all Futaba devices provided

    Args:
        futabaDevices (list of usb.core.Device): A list of Futaba USB device handles

    Returns:
        list of subprocess: A list of subprocesses each of which is responsable for
        a single device driver
    """
    subprocs = []
    try:
        for device in futabaDevices:
            driverCmd = ["python3", "driver.py", "--product-id", hex(device.idProduct)]
            subprocs.append(subprocess.Popen(driverCmd))
    except Exception as e:
        raise RuntimeError("Unable to start device drivers!") from e
    return subprocs


if __name__ == "__main__":
    utils.configSanityCheck()
    main()
