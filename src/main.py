#!/usr/bin/python3
"""RC USB Receiver Driver - Standalone Version."""

import os
import signal
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

# Ensure we can import our modules regardless of execution context
if getattr(sys, "frozen", False):
    # Running as compiled executable
    bundle_dir = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
else:
    # Running as script
    bundle_dir = Path(__file__).parent

# Add the bundle directory to Python path
sys.path.insert(0, str(bundle_dir))

try:
    import Futaba
except ImportError as e:
    print(f"❌ Failed to import Futaba module: {e}")
    print("Make sure all required modules are available.")
    sys.exit(1)


def check_privileges():
    """Ensure the driver is running with proper privileges."""
    if os.geteuid() != 0:
        print("❌ This driver requires root privileges to access USB devices.")
        print("Please run with sudo:")
        print(f"   sudo {sys.argv[0]} {' '.join(sys.argv[1:])}")
        sys.exit(1)


def setup_signal_handlers():
    """Setup graceful shutdown handlers."""

    def signal_handler(signum, frame):
        print("\n🛑 Shutdown signal received. Cleaning up...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def create_parser():
    """Create command line argument parser."""
    parser = ArgumentParser(
        description="RC USB Receiver Driver - Standalone Version",
        epilog="Example: sudo ./rc-driver --autostart",
    )

    parser.add_argument(
        "--autostart", action="store_true", help="Start the first device found automatically"
    )

    parser.add_argument("--bus", help="The bus of the device you want to start a driver for")

    parser.add_argument("--calibrate", action="store_true", help="Used for calibration mode")

    parser.add_argument("--endpoint", help="Start a driver on the device at this endpoint")

    parser.add_argument("--port", help="The port of the device you want start a driver for")

    parser.add_argument(
        "--ui", action="store_true", help="Launch the terminal based UI (not yet implemented)"
    )

    parser.add_argument("--version", action="version", version="RC Driver v1.0.0 (Standalone)")

    return parser


def cli_mode(args):
    """Run the driver in CLI mode."""
    print("🎮 RC USB Receiver Driver")
    print("=" * 30)

    try:
        manager = Futaba.DeviceManager()
        device = None

        if args.endpoint is not None:
            device = manager.findDevice(endpoint=args.endpoint)
        else:
            device_list = manager.listDevices()
            device_count = len(device_list)

            if device_count == 0:
                print("❌ No Futaba devices found.")
                print("Make sure your device is connected and try again.")
                return
            elif device_count == 1 or args.autostart:
                print(f"✅ Found {device_count} Futaba device(s)")
                print(f"🚀 Auto-starting {device_list[0]['name']}")
                device = device_list[0]
            else:
                print(f"📋 Found {device_count} devices. Please select:")
                for i, dev in enumerate(device_list):
                    print(f"  [{i}] {dev['name']}")

                try:
                    selection = int(input("Enter selection: "))
                    device = device_list[selection]
                except (ValueError, IndexError):
                    print("❌ Invalid selection.")
                    return

        if device is None:
            print("❌ Could not find or select a device.")
            return

        # Start the device
        manager.start(device["key"])
        print(f"✅ Started {device['name']}")
        print("🎯 Driver is running. Press CTRL+C to stop.")

        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print("👋 Driver stopped. Goodbye!")


def main():
    """Main entry point."""
    setup_signal_handlers()
    check_privileges()

    parser = create_parser()
    args = parser.parse_args()

    if args.ui:
        print("❌ UI mode is not yet implemented.")
        print("Use CLI mode instead (remove --ui flag).")
        sys.exit(1)
    else:
        cli_mode(args)


if __name__ == "__main__":
    main()
