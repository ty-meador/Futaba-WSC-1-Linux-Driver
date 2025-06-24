#!/usr/bin/python3
"""The main program - run with `sudo python3 main.py`"""

from argparse import ArgumentParser

from driver.UI import DriverUI

parser = ArgumentParser()


parser.add_argument(
    "--text-ui",
    action="store_true",
    help="Start the text-based UI",
)

parser.add_argument(
    "--debug",
    action="store_true",
    help="Enable debug log level",
)


if __name__ == "__main__":
    args = parser.parse_args()

    if args.text_ui:
        DriverUI(debug=True).run()
    else:
        pass  # TO-DO
