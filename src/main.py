#!/usr/bin/env python3
"""The main program - run with `sudo python3 main.py`.

Futaba RC Driver  Copyright (C) 2025  Tyler Meador (gitlab="Native-Coder")
This program comes with ABSOLUTELY NO WARRANTY;.
This is free software, and you are welcome to redistribute it
under certain conditions; See GNU GPL V3 for more info.
"""

import asyncio
import curses
import sys
import time
import tomllib
import traceback
from argparse import ArgumentParser, Namespace
from pathlib import Path

import Futaba
import UI

# Project structure
PWD = Path(__file__).parent.resolve()
PARENT = PWD.parent

PYPROJECT_PATH = PARENT / "pyproject.toml"
if not PYPROJECT_PATH.exists():
    raise FileNotFoundError("Unable to locate pyproject.toml")

# Load project configuration
with open(PYPROJECT_PATH, "rb") as f:
    """Load pyproject.toml file."""
    toml_data = tomllib.load(f)
PYPROJECT = toml_data
EXECUTABLE_NAME = PYPROJECT["tool"]["build_tool"]["executable_name"]
LOCK_SOCKET = None

parser = ArgumentParser()
parser.add_argument("--bus", help="The bus of the device you want to start a driver for")
parser.add_argument("--calibrate", action="store_true", help="Used for calibration")
parser.add_argument("--daemonize", action="store_true", help="Run as a background daemon")
parser.add_argument("--endpoint", help="Start a driver on the device at this endpoint")
parser.add_argument("--port", help="The port of the device you want start a driver for")
parser.add_argument("--version", action="store_true", help="Get driver version")


async def daemonMode(args: Namespace, mgr: Futaba.DeviceManager) -> None:
    """Run the driver in cli-mode.

    Args:
        args (argparse.ArgumentParser.arg): Arguments passed to the cli
        mgr (Futaba.DeviceManager): The global device manager

    Raises:
        RuntimeError: Raised if the specified device cannot be found

    """
    device = None
    if args.endpoint is not None:
        device = mgr.findDevice(endpoint=args.endpoint)
        if device is None:
            raise OSError(f"No Futaba device found at endpoint {args.endpoint}")
    else:
        print(f"Found {len(mgr.listDevices())} Futaba devices, autostarting all...")
        mgr.startAll()
        # TODO - Implement loop to detect new devices etc


def calibrationMode(
    parentScreen: curses.window,
    args: Namespace,
    mgr: Futaba.DeviceManager,
) -> None:
    """Run the driver with a text mode ui."""
    ##
    # Keycodes
    ##
    ENTER = 10
    SPACE = 32
    # LEFT_ARROW = 68
    UP_ARROW = 65
    # RIGHT_ARROW = 67
    DOWN_ARROW = 66

    yMax, xMax = parentScreen.getmaxyx()
    xMaxOverTwo = xMax // 2
    yMaxOverTwo = yMax // 2
    height = 20
    width = 80
    xMid = xMaxOverTwo - width // 2
    yMid = yMaxOverTwo - height // 2

    deviceManager = Futaba.DeviceManager()
    pipe = None
    selectedDevice = None
    inpt = None

    ##
    # Allow user to select which device they want to calibrate.
    ##
    menu = UI.MainMenu(
        UI.WindowCoords(
            x=xMid,
            y=yMid,
            width=width,
            height=height,
        ),
        [device for device in deviceManager.listDevices()],
    )

    menu.render()
    while inpt != ENTER:
        inpt = menu.getch()
        if inpt == UP_ARROW:
            menu.up()
        elif inpt == DOWN_ARROW:
            menu.down()

    selectedDevice = menu.getItem()
    menu.erase()
    parentScreen.refresh()

    ##
    # The name input by the user will be used in part of the calibration file name
    ##
    inputWindow = UI.TextInput(UI.WindowCoords(x=xMid, y=yMid, width=width, height=3))
    inputWindow.setTitle("( Enter a name for the transmitter you are calibrating )")
    txName = inputWindow.getValue().replace(" ", "-")  # tx = transmitter
    inputWindow.erase()
    parentScreen.refresh()

    ##
    # calibration process:
    #
    # - center all inputs
    # - move all inputs to extremes
    # - generate calibration file
    ##
    deviceManager.start(selectedDevice["key"])
    pipe = deviceManager.getPipe(selectedDevice["key"])
    # Generates the calibration
    calibrationWidget = Futaba.Util.CalibrationWidget()
    # Handles user interaction
    calibrationUI = UI.CalibrationUI(UI.WindowCoords(x=xMid, y=yMid, width=width, height=height))
    calibrationUI.nodelay(True)
    calibrationUI.setTitle("( Center all inputs, then press enter )")
    calibrationUI.render()
    fileName = f"{selectedDevice['deviceUUID']}_{txName}.json"
    try:
        mode = "center"
        done = False
        while not done:
            time.sleep(0.01)  # Prevent busy-waiting
            while pipe.poll():
                [channel, rawV, calibV] = pipe.recv()
                # move to next calibration step every time they press enter
                if calibrationUI.getch() == ENTER:
                    # If we've already min/maxd, we're done. generate the file.
                    if mode == "minmax":
                        done = True
                        break
                    mode = "minmax"
                    calibrationUI.setTitle(
                        "( Slowly move each channel to each of their extremes, then press enter )"
                    )
                if mode == "center":
                    calibrationWidget.mid(channel, rawV)
                elif mode == "minmax":
                    calibrationWidget.minMax(channel, rawV)
                calibrationUI.updateChannel(channel, calibV)
                calibrationUI.render()
    except KeyboardInterrupt:
        pass

    calibrationWidget.generateFile(fileName)
    mgr.stopAll()


if __name__ == "__main__":
    args = parser.parse_args()
    try:
        # No reason to proceed if all they want is the version.
        if args.version:
            print(PYPROJECT["project"]["version"])
            sys.exit(0)

        # Futaba.Driver.ProcessLock: Prevents multiple driver instances from running.
        # Futaba.DeviceManager: It's a futaba device manager...
        with Futaba.Driver.ProcessLock(), Futaba.DeviceManager() as mgr:
            if args.calibrate:
                try:
                    curses.wrapper(calibrationMode, *(args, mgr))
                except Exception:
                    traceback.print_exc()
                    raise
                print("Calibration complete!")
                sys.exit(0)
            elif args.daemonize:
                loop = asyncio.new_event_loop()
                loop.create_task(daemonMode(args, mgr))
                loop.run_forever()
            else:
                devList = mgr.listDevices()
                print(f"Found {len(devList)} Futaba devices")
                print("Which one would you like to test?")
                for device in devList:
                    print(f"{device['key']}: {device['name']}")
                choice = input("Choice: ")
                mgr.start(device["key"])
                print("🏳️  Driver running, ctrl+c to quit")

                while True:
                    time.sleep(0.1)  # Prevent busy waiting

    except OSError:
        print("🏁 Driver already running. Have Fun!")
    except KeyboardInterrupt:
        print("🏴 Driver stopped")
        pass
