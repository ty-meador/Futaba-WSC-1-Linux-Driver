import json
import os
import subprocess
import time

import usb

from utils import generateLogger

logger = generateLogger("main")


def main():
    """Starts a driver in a subprocess for each Futaba USB device found

    Raises:
        Exception: If not Futaba USB devices are detected
    """
    try:
        futabaDevices = []
        subprocs = []

        for device in usb.core.find(find_all=True):
            if device.manufacturer.lower() == "futaba":
                futabaDevices.append(device)

        if len(futabaDevices) == 0:
            raise Exception("No Futaba USB device detected!")

        driversRunning = False
        for device in futabaDevices:
            driverCmd = ["python3", "driver.py", "--product-id", hex(device.idProduct)]
            subprocs.append(subprocess.Popen(driverCmd))
        driversRunning = True

        while driversRunning:
            running = 0
            stopped = 0
            total = len(subprocs)
            time.sleep(1)
            for subproc in subprocs:
                if subproc.poll() is None:
                    running += 1
                else:
                    stopped += 1
                if stopped == total:
                    driversRunning = False

    except KeyboardInterrupt:
        pass


def configSanityCheck():
    """Ensures that the default config file exists with default values"""
    # Ensure default config file exists
    if not os.path.exists("default_config.json"):
        generateDefaultConfigFile()
    else:  # Is the default file sane?
        try:
            with open("default_config.json", "r", encoding="utf-8") as cfgFile:
                json.load(cfgFile)
        except Exception:
            # Delete the existing default config and regenerate it
            generateDefaultConfigFile(forceRegenerate=True)


def generateDefaultConfigFile(forceRegenerate=False):
    """Regenerates the default config file

    Args:
        forceRegenerate (bool, optional): If true the existing configuration file will be deleted and a new one will be created using default values. Defaults to False.
    """
    fileName = "default_config.json"
    backupFileName = f"{fileName}.{time.time()}.BACKUP"

    logger.info("Attempting to generate the default config file...")
    if os.path.exists(fileName):
        logger.warning("Default config file already exists...")
        # Force regenerate will delete the existing file and generate a
        # new one from scratch
        if forceRegenerate is True:
            os.rename(fileName, backupFileName)
            logger.warning(
                f"-> Force regnerating default config file: your config file was backed up to {backupFileName}"
            )
        else:  # file exists, not force regenerating - do nothing
            return

    # A dict with a 1:1 representation of the JSON file that will be generated...
    defaultConfig = {"frame_size": 16, "event_max_value": 32768}

    # ...told ya
    with open(fileName, "w", encoding="utf-8") as cfgFile:
        cfgFile.write(json.dumps(defaultConfig, indent=4))


if __name__ == "__main__":
    configSanityCheck()
    main()
