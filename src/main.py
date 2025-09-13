#!/usr/bin/env python3
"""The main program - run with `sudo python3 main.py`.

Futaba RC Driver  Copyright (C) 2025  Tyler Meador (gitlab="Native-Coder")
This program comes with ABSOLUTELY NO WARRANTY;.
This is free software, and you are welcome to redistribute it
under certain conditions; See GNU GPL V3 for more info.
"""
import asyncio
import atexit
import curses
import socket
import sys
import time
import traceback
from argparse import ArgumentParser
from contextlib import suppress
from pathlib import Path

import tomllib

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
    toml_data = tomllib.load(f)
PYPROJECT = toml_data
CALIBRATIONS_PATH = PWD / "Futaba/calibrations"
EXECUTABLE_NAME = PYPROJECT["tool"]["build_tool"]["executable_name"]

parser = ArgumentParser()
parser.add_argument("--bus", help="The bus of the device you want to start a driver for")
parser.add_argument("--calibrate", action="store_true", help="Used for calibration")
parser.add_argument("--daemonize", action="store_true", help="Run as a background daemon")
parser.add_argument("--endpoint", help="Start a driver on the device at this endpoint")
parser.add_argument("--port", help="The port of the device you want start a driver for")
parser.add_argument("--version", action="store_true", help="Get driver version")
ARGS = parser.parse_args()


def main():
    """Project entrypoint."""
    try:
        # No reason to proceed if all they want is the version.
        if ARGS.version:
            print(PYPROJECT["project"]["version"])
            sys.exit(0)

        # Futaba.Driver.ProcessLock: Prevents multiple driver instances from running.
        # Futaba.DeviceManager: It's a futaba device manager...
        mgr = Futaba.DeviceManager()
        with ProcessLock():
            if ARGS.calibrate:
                try:
                    curses.wrapper(calibrationMode, *(ARGS, mgr))
                except Exception:
                    # Make sure we get a stack trace from curses
                    traceback.print_exc()
                    raise
                print("Calibration complete!")
                sys.exit(0)
            elif ARGS.daemonize:
                loop = asyncio.new_event_loop()
                loop.create_task(daemonMode(mgr))
                loop.run_forever()
            else:
                print("asdf")
                choice = None
                devList = mgr.listDevices()
                keyList = list(map(lambda device: device["key"], devList))
                print(keyList)
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
    except OSError:
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
    print("Autostarting the following devices:")
    for device in mgr.listDevices():
        print(f"    {device['deviceUUID']}({device['productName']})")
    mgr.startAll()


def calibrationMode(
    parentScreen: curses.window,
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
    windowCoords = UI.WindowCoords(
        x=xMid,
        y=yMid,
        width=width,
        height=height,
    )

    ##
    # Allow user to select which receiver they want to calibrate
    ##
    menu = UI.MainMenu(windowCoords, deviceManager.listDevices())
    menu.render()
    while inpt != ENTER:
        inpt = menu.getch()
        if inpt == UP_ARROW:
            menu.up()
        elif inpt == DOWN_ARROW:
            menu.down()
    inpt = None

    selectedDevice = menu.getItem()
    menu.erase()
    parentScreen.refresh()

    deviceManager.start(selectedDevice["key"])
    pipe = deviceManager.getPipe(selectedDevice["key"])
    # Generates the calibration
    calibrationWidget = Futaba.Util.CalibrationWidget()
    # Handles user interaction
    calibrationUI = UI.CalibrationUI(UI.WindowCoords(x=xMid, y=yMid, width=width, height=height))
    calibrationUI.nodelay(True)
    calibrationUI.setTitle("( Center all inputs, then press enter )")
    calibrationUI.render()
    fileName = f"{selectedDevice['productName']}_{selectedDevice['deviceUUID']}.json"
    with suppress(KeyboardInterrupt):
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

    calibrationWidget.generateFile(fileName)
    mgr.stopAll()


class ProcessLock:
    """Create a lock that prevents multiple driver instances."""
    def lock(self):
        """Lock the process to prevent multiple instances."""
        # Socket-lock method
        self.lockSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.lockSocket.bind(("127.0.0.1", self.lockPort))

    def unlock(self):
        """Unlock the process and release resources back to OS."""
        if self.lockSocket:
            self.lockSocket.close()
            self.lockSocket = None

    def __init__(self):
        """Create a process lock."""
        self.lockPort = 1962  # 🥚
        self.lockSocket = None
        atexit.register(self.unlock)

    def __enter__(self):
        """Enter."""
        return self

    def __exit__(self, exc_type, exc_value, stacktrace):
        """Exit."""
        self.unlock()
        return self


if __name__ == "__main__":
    main()
