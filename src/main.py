#!/usr/bin/env python3
"""The main program - run with `sudo python3 main.py`.

Futaba RC Driver  Copyright (C) 2026  Tyler Meador (gitlab="Native-Coder")
This program comes with ABSOLUTELY NO WARRANTY;.
This is free software, and you are welcome to redistribute it
under certain conditions; See GNU GPL V3 for more info.
"""

import argparse
import asyncio
import curses
import os
import signal
import sys
import time
import traceback
from pathlib import Path

import tomllib

import Futaba
import UI
from SocketLock import LockNotAcquired, SocketLock


def main():
    """Project entrypoint."""
    mgr = Futaba.DeviceManager()
    # Daemon mode tolerates an empty bus (it hot-plugs); interactive modes need
    # at least one device up front.
    if not ARGS.daemonize and not mgr.listDevices():
        print("No Futaba devices found. Is the receiver plugged in?")
        sys.exit(1)
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
            # asyncio.run propagates exceptions from daemonMode, so a crash
            # kills the process visibly instead of leaving a dead task behind
            asyncio.run(daemonMode(mgr))
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
        [UI.MenuItem(device["name"], device) for device in mgr.listDevices()],
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
    mgr.start(selectedDevice["key"])
    pipe = mgr.getPipe(selectedDevice["key"])

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

    centerInputs.setTitle(
        "( Center all inputs, Set expo to 0%, set dual rates to 100%, then press enter )"
    )
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
        time.sleep(0.01)  # Prevent busy-waiting
        while pipe.poll():
            [channel, rawV, calibV] = pipe.recv()
            calibrationWidget.mid(channel, rawV)

    # calibration UI elements
    calibrationUI = UI.CalibrationUI(
        UI.WindowCoords(x=xMid, y=yMid, width=width, height=height),
        "( Slowly move each channel to each of their extremes, then press enter )",
    )
    calibrationUI.nodelay(True)
    calibrationUI.render()
    fileName = f"{selectedDevice['product']}_{selectedDevice['deviceUUID']}.json"
    done = False
    try:
        mode = "minmax"
        while not done:
            time.sleep(0.01)  # Prevent busy-waiting
            # Checked outside the pipe drain so enter still registers when the
            # transmitter is idle and no frames are arriving
            if calibrationUI.getch() == ENTER:
                done = True
                continue
            while pipe.poll():
                [channel, rawV, calibV] = pipe.recv()
                if mode == "minmax":
                    calibrationWidget.minMax(channel, rawV)
                calibrationUI.updateChannel(channel, calibV)
                calibrationUI.render()
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
    print("Running in daemon mode: Scanning and starting new devices every second")

    while True:
        mgr.scanForDevices()  # scan for devices,
        mgr.startAll()  # start new ones.
        await asyncio.sleep(1)  # full USB re-enumeration is not free; once a second is plenty


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
    pid = int(pid)

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        # Stale pid file left over from a process that is already gone
        pidFile.unlink(missing_ok=True)
        return

    # Wait for the old process to exit so it can stop its driver
    # subprocesses and remove its own pid file on the way out.
    for _ in range(50):
        time.sleep(0.1)
        try:
            os.kill(pid, 0)  # Raises ProcessLookupError once the process is gone
        except ProcessLookupError:
            break
    else:
        print(f"⚠ Driver (pid {pid}) did not exit after SIGTERM, leaving its pid file in place")
        return

    # The old process normally unlinks this itself; clean up if it couldn't
    pidFile.unlink(missing_ok=True)


def parseArgs() -> argparse.Namespace:
    """Parses the CLI arguments passed to this script

    Returns:
        Namespace: The resulting namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Calibrate a transmitter to a receiver",
    )
    parser.add_argument(
        "--daemonize",
        action="store_true",
        help="Run as a background daemon",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart the running background daemon",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Get driver version",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Setup a new device or reconfigure an existing one",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Project structure
    PWD = Path(__file__).parent.resolve()
    PARENT = PWD.parent
    PYPROJECT_PATH = PARENT / "pyproject.toml"
    assert PYPROJECT_PATH.exists(), "Unable to locate pyproject.toml"

    # Load project configuration
    PYPROJECT = None
    with open(PYPROJECT_PATH, "rb") as f:
        PYPROJECT = tomllib.load(f)

    # Parse args
    ARGS = parseArgs()
    # No reason to proceed if all they want is the version.
    if ARGS.version:
        print(PYPROJECT["project"]["version"])
        sys.exit(0)

    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    # Start or reload device manager
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
