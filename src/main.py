#!/usr/bin/env python3
"""The main program - run with `sudo python3 main.py`.

Futaba RC Driver  Copyright (C) 2025  Tyler Meador (gitlab="Native-Coder")
This program comes with ABSOLUTELY NO WARRANTY;.
This is free software, and you are welcome to redistribute it
under certain conditions; See GNU GPL V3 for more info.
"""
import asyncio
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

import tomllib
from SocketLock import LockNotAcquired, SocketLock

import Futaba

# Project structure
PWD = Path(__file__).parent.resolve()
PARENT = PWD.parent

PYPROJECT_PATH = PARENT / "pyproject.toml"
if not PYPROJECT_PATH.exists():
    raise FileNotFoundError("Unable to locate pyproject.toml")

# Load project configuration
with open(PYPROJECT_PATH, "rb") as f:
    toml_data = tomllib.load(f)
PYPROJECT = toml_data
CALIBRATIONS_PATH = PWD / "Futaba/calibrations"
EXECUTABLE_NAME = PYPROJECT["tool"]["build_tool"]["executable_name"]

parser = ArgumentParser()
parser.add_argument("--calibrate", action="store_true", help="Used for calibration")
parser.add_argument("--daemonize", action="store_true", help="Run as a background daemon")
parser.add_argument("--port", help="The port of the device you want start a driver for")
parser.add_argument("--version", action="store_true", help="Get driver version")
parser.add_argument(
    "--setup", action="store_true", help="Setup a new device or reconfigure an existing one"
)
ARGS = parser.parse_args()


def main():
    """Project entrypoint."""
    try:
        # No reason to proceed if all they want is the version.
        if ARGS.version:
            print(PYPROJECT["project"]["version"])
            sys.exit(0)

        # Futaba.Driver.SocketLock: Prevents multiple driver instances from running.
        # Futaba.DeviceManager: It's a futaba device manager...
        mgr = Futaba.DeviceManager()
        with SocketLock():
            if ARGS.daemonize:
                loop = asyncio.new_event_loop()
                loop.create_task(daemonMode(mgr))
                loop.run_forever()
            elif ARGS.setup:
                setup()
            else:
                devList = mgr.listDevices()
                keyList = list(map(lambda device: device["key"], devList))
                choice = -1  # Keys will never be negative
                while choice not in keyList:
                    print(f"Found {len(devList)} Futaba devices")
                    print("Which one would you like to test?")
                    for device in devList:
                        print(f"{device['key']}: {device['name']}")
                    choice = int(input("Choice: "))
                mgr.start(choice)
                print("🏳️  Driver running, ctrl+c to quit")

                while True:
                    time.sleep(0.1)  # Prevent busy waiting
    except LockNotAcquired:
        print("🏁 Driver already running. Have Fun!")
    except KeyboardInterrupt:
        print("🏴 Driver stopped")


async def daemonMode(mgr: Futaba.DeviceManager) -> None:
    """Run the driver in cli-mode.

    Args:
        ARGS (argparse.ArgumentParser.arg): Arguments passed to the cli
        mgr (Futaba.DeviceManager): The global device manager

    Raises:
        RuntimeError: Raised if the specified device cannot be found

    """
    print("Running in deamon mode: Scanning and starting new devices every second")

    while True:
        mgr.scanForDevices()  # scan for devices,
        mgr.startAll()  # start new ones.
        await asyncio.sleep(1)  # yield to event loop for at least 1 second


def setup(mgr: Futaba.DeviceManager) -> None:
    """Set up a new device"""

    print("Which Futaba device would you like to set up?")
    mgr.scanForDevices()
    for device in mgr.listDevices():
        print(device)


if __name__ == "__main__":
    main()
