# Futaba RC USB Driver - Standalone Distribution
![gif of driver allowing device to show up in VRC-Pro](/screenshots/example.gif)

## Quick Install
```sh
# The quick install script will automatically
# download the latest release and install it.
wget https://example.com/quick-install.sh
chmod +x quick-install.sh
./quick-install.sh
```

## What's Included

- `futaba-rc-driver` - Main executable (requires sudo for uinput access)
- `install.sh` - System installer script
- `README.md` - This file
- `LICENSE` - License information

## System Requirements

- Linux x86_64
- Kernel 3.0+ with uinput support
- USB permissions for your user (or run as sudo)

## Supported Devices

- Futaba WSC-1
- Futaba T16IZ
- Other Futaba USB receivers (auto-detected)

## Usage

The driver automatically detects connected Futaba receivers and creates virtual joystick devices in `/dev/input/`. These can be used by any Linux application that supports joysticks (games, simulators, etc.).

1. Manual run: `sudo futaba-rc-driver`
2. Calibration mode: `sudo futaba-rc-driver --calibrate`
3. Daemon mode (autostart): `sudo futaba-rc-driver --daemonize`

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



## Support

For issues, updates, and documentation visit:
https://gitlab.com/Native-Coder/futaba-usb-driver/

---
Built with ❤️ for the RC community
