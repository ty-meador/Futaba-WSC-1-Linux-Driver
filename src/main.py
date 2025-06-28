#!/usr/bin/python3
"""The main program - run with `sudo python3 main.py`"""

from argparse import ArgumentParser

from driver.UI import DriverUI

parser = ArgumentParser()

parser.add_argument(
    "--debug",
    action="store_true",
    help="Enable debug log level",
)

parser.add_argument(
    "--calibrate",
    action="store_true",
    help="Used for calibration",
)

if __name__ == "__main__":
    args = parser.parse_args()
    DriverUI().run()
