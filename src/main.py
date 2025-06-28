#!/usr/bin/python3
"""The main program - run with `sudo python3 main.py`"""

from argparse import ArgumentParser

import driver
from UI import DriverUI

parser = ArgumentParser()

parser.add_argument(
    "--bus", help="The bus of the device you want to start a driver for"
)

parser.add_argument(
    "--calibrate", action="store_true", help="Used for calibration"
)

parser.add_argument(
    "--debug", action="store_true", help="Enable debug log level"
)

parser.add_argument(
    "--endpoint", help="Start a driver on the device at this endpoint"
)

parser.add_argument(
    "--port", help="The port of the device you want start a driver for"
)


def cliMode(args):
    """Run the driver in cli-mode

    Args:
        args (argparse.ArgumentParser.arg): Arguments passed to the cli

    Raises:
        RuntimeError: Raised if the specified device cannot be found
    """
    manager = driver.FutabaDeviceManager()

    device = None
    if args.endpoint is not None:
        device = manager.findDevice(endpoint=args.endpoint)
    elif (
        hasattr(args, "bus")
        and hasattr(args, "port")
        and args.bus is not None
        and args.port is not None
    ):
        device = manager.findDevice(bus=args.bus, port=args.port)
    if device is None:
        # TO-DO - Show menu and allow user to choose which device to start
        raise RuntimeError(
            "Could not find a Futaba device at the specified endpoint"
        )


if __name__ == "__main__":
    args = parser.parse_args()

    if args.endpoint is not None:
        cliMode(args)
    else:
        DriverUI(args).run()
