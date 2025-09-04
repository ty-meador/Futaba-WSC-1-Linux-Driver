# Futaba RC USB Driver - Standalone Distribution

## Quick Start

1. Extract this archive
2. Run the installer: `sudo ./install.sh`
3. Or run directly: `sudo ./futaba-rc-driver`

## What's Included

- `futaba-rc-driver` - Main executable (requires sudo for uinput access)
- `install.sh` - System installer script
- `README.md` - This file
- `LICENSE` - License information

## System Requirements

- Linux x86_64
- Kernel 3.0+ with uinput support
- USB permissions for your user (or run as sudo)

## Running the Driver

### Option 1: Quick Run (Temporary)
```bash
sudo ./futaba-rc-driver
```

### Option 2: System Install (Permanent)
```bash
./install.sh
# Then run from anywhere:
futaba-rc-driver
```

## Supported Devices

- Futaba WSC-1
- Other Futaba USB receivers (auto-detected)

## Usage

The driver automatically detects connected Futaba receivers and creates virtual joystick devices in `/dev/input/`. These can be used by any Linux application that supports joysticks (games, simulators, etc.).

### Basic Usage
1. Connect your Futaba USB receiver
2. Run `sudo ./futaba-rc-driver`
3. The driver will auto-detect and configure your receiver
4. Use CTRL+C to stop

## Troubleshooting

### Permission Denied
- Make sure you're running with sudo: `sudo ./futaba-rc-driver`
- Or add your user to input group: `sudo usermod -a -G input $USER`

### Device Not Detected
- Check USB connection
- Verify device with: `lsusb | grep Futaba`
- Try a different USB port

### uinput Module Not Found
```bash
# Load the module:
sudo modprobe uinput

# Make it permanent:
echo 'uinput' | sudo tee -a /etc/modules
```

### Still Having Issues?
1. Check kernel logs: `dmesg | tail -20`
2. Verify USB permissions: `ls -l /dev/bus/usb/*/*`
3. Ensure no other drivers are conflicting

## Performance Notes

- This driver is optimized for real-time RC applications (frames are processed in O(1))
- Low latency, high precision input processing
- Memory usage on a WSC-1 is approx 13 kilobytes per channel
  - YMMV - every device is different. The theoretical "maximum" memory consumption would be approx 260 kilobytes per channel.
  - Memory consuption per channel will change after the device is calibrated.

## Support

For issues, updates, and documentation visit:
https://gitlab.com/futaba-linux-support/futaba-rc-linux-driver

---
Built with ❤️ for the RC community
