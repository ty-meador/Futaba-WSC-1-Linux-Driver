#!/usr/bin/env python3
"""The main program - run with `sudo python3 main.py`.

Futaba RC Driver  Copyright (C) 2026  Tyler Meador (gitlab="Native-Coder")
This program comes with ABSOLUTELY NO WARRANTY;.
This is free software, and you are welcome to redistribute it
under certain conditions; See GNU GPL V3 for more info.
"""
import asyncio
import curses
import os
import signal
import sys
import time
import traceback
from argparse import ArgumentParser
from pathlib import Path

import tomllib
from SocketLock import LockNotAcquired, SocketLock

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
parser.add_argument(
    "--calibrate", action="store_true", help="Calibrate a transmitter to a receiver"
)
parser.add_argument("--daemonize", action="store_true", help="Run as a background daemon")
parser.add_argument("--reload", action="store_true", help="Restart the running background daemon")
parser.add_argument("--version", action="store_true", help="Get driver version")
parser.add_argument(
    "--setup", action="store_true", help="Setup a new device or reconfigure an existing one"
)
ARGS = parser.parse_args()
# No reason to proceed if all they want is the version.
if ARGS.version:
    print(PYPROJECT["project"]["version"])
    sys.exit(0)


def main():
    """Project entrypoint."""
    mgr = Futaba.DeviceManager()
    try:
        if ARGS.calibrate:
            try:
                curses.wrapper(calibrationMode, mgr)
                print("Calibration complete!")
                sys.exit(0)
            except Exception:
                # Make sure we get a stack trace from curses
                traceback.print_exc()
                raise
        elif ARGS.daemonize:
            loop = asyncio.new_event_loop()
            loop.create_task(daemonMode(mgr))
            loop.run_forever()
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
    except KeyboardInterrupt:
        mgr.stopAll()
        print("🏴 Driver stopped")


def calibrationMode(
    parentScreen: curses.window,
    mgr: Futaba.DeviceManager,
) -> None:
    """Run the driver with a text mode ui."""
    ##
    # Keycodes
    ##
    ENTER = 10
    # SPACE = 32
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
    menu = UI.Menu(
        windowCoords,
        "( Which receiver is your transmitter paired to? )",
        [UI.MenuItem(device["name"], device) for device in deviceManager.listDevices()],
    )
    menu.render()
    while inpt != ENTER:
        inpt = menu.getch()
        if inpt == UP_ARROW:
            menu.up()
        elif inpt == DOWN_ARROW:
            menu.down()
    inpt = None

    selectedDevice = menu.getItem().value
    deviceManager.start(selectedDevice["key"])
    pipe = deviceManager.getPipe(selectedDevice["key"])

    menu.erase()
    parentScreen.refresh()

    # Generates the calibration (not a UI element)

    centerInputs = UI.TitleOnlyWindow(
        UI.WindowCoords(x=xMid, y=yMid, width=width, height=height),
        "( LOOKING FOR TRANSMITTER (is it on? is it connected?) )",
    )
    centerInputs.render()

    # As soon as we get a frame the script will continue
    while not pipe.poll():
        time.sleep(0.1)

    centerInputs.setTitle("( Center all inputs, then press enter )")
    centerInputs.render()
    # Flush the input buffer to clear any characters typed prior to now
    curses.flushinp()
    centerInputs.getch()

    centerInputs.setTitle("( STANDBY... )")
    centerInputs.render()
    # Give them 3 seconds to center everything
    calibrationWidget = Futaba.CalibrationWidget()
    stopAfter = time.time() + 3  # seconds
    while time.time() < stopAfter:
        while pipe.poll():
            [channel, rawV, calibV] = pipe.recv()
            calibrationWidget.mid(channel, rawV)

    # calibration UI elements
    calibrationUI = UI.CalibrationUI(
        UI.WindowCoords(x=xMid, y=yMid, width=width, height=height),
        "( Slowly move each channel to each of their extremes, then press enter )"
    )
    calibrationUI.nodelay(True)
    calibrationUI.render()
    fileName = f"{selectedDevice['product']}_{selectedDevice['deviceUUID']}.json"
    done = False
    try:
        mode = "minmax"
        while not done:
            time.sleep(0.01)  # Prevent busy-waiting
            while pipe.poll():
                [channel, rawV, calibV] = pipe.recv()
                # move to next calibration step every time they press enter
                if calibrationUI.getch() == ENTER:
                    done = True
                    break
                if mode == "minmax":
                    calibrationWidget.minMax(channel, rawV)
                calibrationUI.updateChannel(channel, calibV)
                calibrationUI.render()
        if not done:
            raise RuntimeError("CALIBRATION DID NOT COMPLETE SUCCESSFULLY")
        calibrationWidget.generateFile(fileName)
    finally:
        mgr.stopAll()


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
        await asyncio.sleep(.1)  # yield to event loop for at least .1 second


def findPidFile():
    """Find the pid file if one exists"""
    search = list(PWD.glob("*.pid"))
    if len(search) == 0:
        return None
    return search[0]


def killRunningProcess():
    """Reload the driver."""
    pidFile = findPidFile()
    if not pidFile:
        return
    print("⟳ Reloading driver")
    [pid, _] = pidFile.name.split(".")
    os.kill(int(pid), signal.SIGTERM)
    time.sleep(1)  # Give it time to shut down
    pidFile.unlink()


if __name__ == "__main__":
    try:
        with SocketLock():
            main()
    except LockNotAcquired:
        if ARGS.reload:
            killRunningProcess()
            with SocketLock():
                main()
        else:
            print("🏁 Driver already running. Have Fun!")
