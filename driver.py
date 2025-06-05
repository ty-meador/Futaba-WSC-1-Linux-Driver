"""Creates a driver with the given arguments and starts it. This script is meant to be called from main.py"""

import signal
from argparse import ArgumentParser

from FutabaUsbDevice import FutabaUsbDevice

parser = ArgumentParser()
parser.add_argument(
    "--product-id",
    dest="productID",
    type=str,
    help="Specify the product id of the Futaba USB device you want to start a driver for",
)

parser.add_argument(
    "--vendor-id",
    dest="vendorID",
    type=str,
    help="Specify the vendor id of the Futaba USB device you want to start a driver for",
)
args = parser.parse_args()


def main():
    """Creates the driver, sets up signal kill listeners and starts the driver"""
    try:
        driver = FutabaUsbDevice(productID=args.productID, vendorID=args.vendorID)
        stopSignals = [signal.SIGINT, signal.SIGTERM]
        for stopSignal in stopSignals:
            signal.signal(stopSignal, driver.stop)

        # Blocks the main thread - That's OK because this should be run as a subprocess anyway
        driver.start()
    except Exception:
        driver.stop()


if __name__ == "__main__":
    main()
