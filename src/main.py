#!/usr/bin/python3
"""The main program - run with `sudo python3 main.py`.

Futaba RC Driver  Copyright (C) 2025  Ty Meador (gitlab="Native-Coder")
This program comes with ABSOLUTELY NO WARRANTY;.
This is free software, and you are welcome to redistribute it
under certain conditions; See GNU GPL V3 for more info.
"""

import atexit
import curses
import socket
import subprocess
import sys
import time
import tomllib
from argparse import ArgumentParser, Namespace
from pathlib import Path

import Futaba
from UI import MainMenu, WindowCoords
from UI.Calibration import CalibrationWidget

# Project structure
PWD = Path(__file__).parent.resolve()
PARENT = PWD.parent

PYPROJECT_PATH = PARENT / "pyproject.toml"
if not PYPROJECT_PATH.exists():
    PYPROJECT_PATH = PWD / "pyproject.toml"
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
parser.add_argument("--autostart", action="store_true", help="Start the first device found")
parser.add_argument("--bus", help="The bus of the device you want to start a driver for")
parser.add_argument("--calibrate", action="store_true", help="Used for calibration")
parser.add_argument("--endpoint", help="Start a driver on the device at this endpoint")
parser.add_argument("--port", help="The port of the device you want start a driver for")
parser.add_argument("--ui", action="store_true", help="Launch the terminal based UI")


def cliMode(args: Namespace) -> None:
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

    # pipe = manager.getPipe(device["key"])
    # calibrator = Futaba.InputChannel.ChannelCalibrator()
    # print(pipe)
    # Block indefinitely so that background process stays alive
    try:
        while True:
            #     while pipe.poll():
            #         calibrator.minMax(pipe.recv())
            time.sleep(0.1)
    except KeyboardInterrupt:
        # print(calibrator._generateCalibration())
        pass

    manager.stopAll()
    print("Goodbye!")


def uiMode(
    parentScreen: curses.window,
    args: Namespace,
) -> None:
    """Run the driver with a text mode ui."""
    ##
    # Keycodes
    ##
    SPACE = 10
    ENTER = 32
    # LEFT_ARROW = 68
    UP_ARROW = 65
    # RIGHT_ARROW = 67
    DOWN_ARROW = 66

    yMax, xMax = parentScreen.getmaxyx()
    xMaxOverTwo = xMax // 2

    deviceManager = Futaba.DeviceManager()

    menu = MainMenu(
        WindowCoords(x=0, y=0, width=xMaxOverTwo, height=yMax),
        [device for device in deviceManager.listDevices()],
    )

    menu.render()

    selectedDevice = None
    pipe = None

    while True:
        inpt = menu.getch()
        if inpt == UP_ARROW:
            menu.up()
        elif inpt == DOWN_ARROW:
            menu.down()
        elif inpt in (SPACE, ENTER):
            selectedDevice = menu.getItem()
            deviceManager.start(selectedDevice["key"])
            calibWindow = CalibrationWidget(
                WindowCoords(
                    y=0,
                    x=xMaxOverTwo,
                    width=xMaxOverTwo,
                    height=yMax,
                )
            )
            pipe = deviceManager.getPipe(selectedDevice["key"])

        if pipe:
            while True:
                while pipe.poll():
                    [evt, rawV, calibV] = pipe.recv()
                    # Steering
                    if evt == (3, 0):
                        calibWindow.setSteeringPos(calibV)
                    # Throttle
                    elif evt == (3, 1):
                        calibWindow.setThrottlePos(calibV)

        calibWindow.render()


def runCommand(cmd: str, cwd: str | None = None, capture: bool = True) -> str | None:
    """Run a command and handle errors.

    Args:
        cmd: Command to run as shell string
        cwd: Working directory for command execution
        capture: Whether to capture and return output

    Returns:
        Command output if capture=True and successful, empty string if capture=False and successful,
        None if command failed

    """
    try:
        if capture:
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                cwd=cwd,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd)
            return ""
    except subprocess.CalledProcessError as e:
        if capture and e.stderr:
            print(f"Error: {e.stderr}")
        return None


if __name__ == "__main__":
    args = parser.parse_args()

    # Socket-lock method to prevent duplicate driver instances
    lockPort = 1962  # 🥚 📻🎮
    try:
        LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        LOCK_SOCKET.bind(("127.0.0.1", lockPort))

        # Ensure socket is cleaned up on exit
        atexit.register(lambda: LOCK_SOCKET.close() if LOCK_SOCKET else None)
    except OSError:
        print("🏁 Driver already running. Have Fun!")
        sys.exit(1)

    if args.ui:
        curses.wrapper(uiMode, args)
    else:
        cliMode(args)
