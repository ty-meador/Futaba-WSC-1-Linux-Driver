#!/usr/bin/python3
"""The main program - run with `sudo python3 main.py`.

Futaba RC Driver  Copyright (C) 2025  Ty Meador (gitlab="Native-Coder")
This program comes with ABSOLUTELY NO WARRANTY;.
This is free software, and you are welcome to redistribute it
under certain conditions; See GNU GPL V3 for more info.
"""

import time
from argparse import ArgumentParser

import Futaba

parser = ArgumentParser()


parser.add_argument(
    "--autostart",
    action="store_true",
    help="Start the first device found",
)

parser.add_argument(
    "--bus",
    help="The bus of the device you want to start a driver for",
)

parser.add_argument(
    "--calibrate",
    action="store_true",
    help="Used for calibration",
)


parser.add_argument(
    "--endpoint",
    help="Start a driver on the device at this endpoint",
)

parser.add_argument(
    "--port",
    help="The port of the device you want start a driver for",
)


parser.add_argument(
    "--ui",
    help="Launch the terminal based UI",
)


def cliMode(args):
    """Run the driver in cli-mode.

    Args:
        args (argparse.ArgumentParser.arg): Arguments passed to the cli

    Raises:
        RuntimeError: Raised if the specified device cannot be found

    """
    manager = Futaba.DeviceManager()

    device = None
    if args.endpoint is not None:
        device = manager.findDevice(endpoint=args.endpoint)
    else:
        selection = None
        deviceList = manager.listDevices()
        deviceCount = len(deviceList)

        if deviceCount == 1 or args.autostart:
            print(f"Found {deviceCount} Futaba devices, autostarting {deviceList[0]['name']}")
            device = deviceList[0]
        elif deviceCount > 1:
            print("Which device would you like to start?")
            for device in deviceList:
                print(f"[ {device['key']} ] : {device['name']}")
            selection = int(input())
            device = deviceList[selection]

    if device is None:
        raise RuntimeError("Could not find a Futaba device at the specified endpoint")

    manager.start(device["key"])
    print(f"Started {device['name']}")
    print("CTRL + C to stop driver")

    try:
        while True:
            # Block indefinitely so that background process stays alive
            time.sleep(100)
    except KeyboardInterrupt:
        pass

    print("Goodbye!")


if __name__ == "__main__":
    args = parser.parse_args()

    # TO-DO
    if args.ui:
        raise RuntimeError("Not yet Impelmented")
        # DriverUI(args).run()
    else:
        cliMode(args)
