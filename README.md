# Futaba RC USB Driver - Standalone Distribution

![gif of driver allowing device to show up in VRC-Pro](/screenshots/example.gif)

A high-performance Linux driver for Futaba RC USB receivers, providing low-latency joystick input for simulators and games.

## Quick Install

```sh
# The quick install script will automatically
# download the latest release and install it.
wget https://tylermeador.com/futaba-rc-driver/dist/web-installer.sh
chmod +x web-installer.sh
./web-installer.sh
```

## What's Included

- `futaba-rc-driver` - Main executable (requires sudo for uinput access)
- `install.sh` - System installer script
- `README.md` - This file
- `LICENSE` - License information
- `NOTICE` - Third-party notices
- `udev.rules` - USB device permissions

## System Requirements

- Linux x86_64
- Kernel 3.0+ with uinput support
- USB permissions for your user (or run as sudo)
- Python 3.11+ (for development only)

## Supported Devices

- Futaba WSC-1
- Futaba T16IZ
- Other Futaba USB receivers (auto-detected)

---

## Installation

### Manual Installation

1. **Download the latest release:**

    ```sh
    wget https://tylermeador.com/futaba-rc-driver/dist/futaba-rc-driver-1.4.1-linux-x86_64.tar.gz
    tar -xzf futaba-rc-driver-1.4.1-linux-x86_64.tar.gz
    cd futaba-rc-driver-1.4.1-linux-x86_64
    ```

2. **Run the installer:**

    ```sh
    ./install.sh
    ```

    The installer will:
    - Copy files to `~/.local/share/futaba-rc-driver/`
    - Create a symlink in `~/.local/bin/`
    - Set up USB permissions (requires sudo)
    - Add user to `input` group (requires sudo)
    - Configure uinput module to load at boot
    - Add auto-start to your shell profile
    - Run initial calibration

3. **Log out and back in** for group changes to take effect

### Steam Deck Installation

The installer automatically detects Steam Deck and uses optimized settings:

- Installation survives SteamOS updates (user-space install)
- Works best in Desktop Mode
- Configures as user service

```sh
# In Desktop Mode (Konsole)
wget https://tylermeador.com/futaba-rc-driver/dist/web-installer.sh
chmod +x web-installer.sh
./web-installer.sh
```

---

## Uninstallation

```sh
cd ~/.local/share/futaba-rc-driver/
./uninstall.sh
```

The uninstaller will:

- Stop all running driver instances
- Remove the command from PATH
- Remove auto-start entries from shell profiles
- Remove installation directory
- Remove USB permissions and udev rules
- Remove uinput module configuration
- Clean up log files

**Note:** User group membership (input group) is preserved. You may want to log out and back in to refresh your environment.

---

## Usage

### Basic Commands

```sh
# Run the driver manually
sudo futaba-rc-driver

# Calibration mode (interactive)
sudo futaba-rc-driver --calibrate

# Run as background daemon
sudo futaba-rc-driver --daemonize

# Display help
futaba-rc-driver --help

# Show version
futaba-rc-driver --version
```

### Auto-start

The driver is configured to start automatically when you log in. It runs continuously in the background and prevents duplicate instances.

**Manual control:**

```sh
# Stop the driver
pkill -f futaba-rc-driver

# Check if running
pgrep -f futaba-rc-driver
```

### Steam Deck Service Management

```sh
# Start service
systemctl --user start futaba-rc-driver

# Enable auto-start with session
systemctl --user enable futaba-rc-driver

# Check status
systemctl --user status futaba-rc-driver

# View logs
journalctl --user -u futaba-rc-driver -f

# Stop service
systemctl --user stop futaba-rc-driver
```

---

## Troubleshooting

### Permission Denied

- Make sure you're running with sudo: `sudo ./futaba-rc-driver`
- Or add your user to input group: `sudo usermod -a -G input $USER`
- Log out and back in for group changes to take effect

### Device Not Detected

- Check USB connection: `lsusb | grep Futaba`
- Try a different USB port
- Check kernel logs: `dmesg | tail -20`
- Verify USB permissions: `ls -l /dev/bus/usb/*/*`

### uinput Module Not Found

```bash
# Load the module manually:
sudo modprobe uinput

# Make it permanent:
echo 'uinput' | sudo tee -a /etc/modules

# Or (for systemd-based systems):
echo 'uinput' | sudo tee /etc/modules-load.d/uinput.conf
```

### Calibration Issues

- Ensure transmitter is bound to receiver before calibration
- Move all sticks and switches through their full range during calibration
- Recalibrate if you experience drift: `sudo futaba-rc-driver --calibrate`

### Still Having Issues?

1. Check the log file: `cat ~/.futaba-rc-driver-logs.txt`
2. Ensure no other drivers are conflicting
3. Verify udev rules are loaded: `sudo udevadm control --reload-rules && sudo udevadm trigger`

---

## Performance Notes

- Optimized for real-time RC applications (O(1) frame processing)
- Low latency, high precision input processing
- Minimal CPU overhead
- Supports multiple simultaneous receivers

---
