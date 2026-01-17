# Futaba RC USB Driver

### Professional-grade Linux driver for Futaba RC transmitters

Transform your Futaba RC transmitter into a high-precision game controller for racing simulators, flight sims, and more. Purpose-built for Linux with zero dependency hassles.

![Driver demonstration in VRC-Pro](/screenshots/example.gif)

---

## Why This Driver?

**Zero Configuration Headaches**

- Single-command installation
- No Python environments to manage
- No package conflicts
- Works on both desktop Linux and Steam Deck

**Built for Performance**

- Real-time scheduling for minimal latency
- O(1) frame processing - constant time regardless of input complexity
- Pre-calculated calibration maps eliminate runtime computation
- Optimized for racing and flight simulators where timing matters

**Rock-Solid Reliability**

- Each device runs in isolated process - one failure won't crash others
- Automatic device detection and recovery
- Survives system updates (user-space installation)
- Production-tested with multiple simultaneous transmitters

**Visual Calibration Interface**
Experience precise, visual feedback during calibration:

```
┌───( Slowly move each channel to each of their extremes, then press enter )───┐
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                       制                                     │
│                                       制                                     │
│                                       制                                     │
│                                       制                                     │
│                                       制                                     │
│                                     ▕ 制                                     │
│                               ▐██████ 制                                     │
│                                 ──────人──────                               │
│                                       速 █████▋                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

The intuitive UI shows real-time input visualization with precise center-point capture for accurate control mapping.

---

## Install

> Both install scripts are identical, the top one is just easier to copy and paste for non-technical users

### Easy Install

```shell
wget https://tylermeador.com/futaba-rc-driver/dist/futaba-rc-driver-1.4.4-linux-x86_64.tar.gz && tar -xzf futaba-rc-driver-1.4.4-linux-x86_64.tar.gz && cd futaba-rc-driver-1.4.4-linux-x86_64 && ./install.sh
```

### Manual Install

```shell
# Download the latest release
wget https://tylermeador.com/futaba-rc-driver/dist/futaba-rc-driver-1.4.4-linux-x86_64.tar.gz

# Extract the archive
tar -xvzf futaba-rc-driver-1.4.4-linux-x86_64.tar.gz

# Run the installer
cd futaba-rc-driver-1.4.4-linux-x86_64
./install.sh
```

**For Steam Deck users:** Install from Desktop Mode. The driver will auto-start the next time you log in.

---

## What's Included

- `futaba-rc-driver` - Standalone executable (no dependencies required)
- `install.sh` - System installer with guided setup
- `README.md` - This documentation
- `LICENSE` - License information

---

## System Requirements

- **OS:** Linux x86_64 (Ubuntu, Debian, Arch, SteamOS)
- **Kernel:** 3.0+ with uinput support
- **Permissions:** USB access (handled by installer)

### Tested Distributions

- Ubuntu 20.04+
- Pop!\_OS 22.04+
- Arch Linux
- SteamOS 3.x (Steam Deck)

---

## Supported Devices

- Futaba WSC-1
- Futaba T16IZ
- Other Futaba USB receivers (auto-detected)

Have a different Futaba transmitter? The driver auto-detects most Futaba USB devices.

---

## Usage

> For most users you need only install the driver. You will be automatically walked through the installation and calibration process.

### Manually Running the Driver

The driver starts automatically when you log in. Manual operation:

```bash
# Run in foreground
futaba-rc-driver

# Run calibration mode
futaba-rc-driver --calibrate

# Run as background daemon
futaba-rc-driver --daemonize
```

### Calibration

**Initial Setup (Required):**

1. Connect your transmitter's USB receiver
2. Power on your transmitter
3. Run: `futaba-rc-driver --calibrate`
4. Follow the on-screen instructions:
    - Move all sticks/controls through their full range
    - Press SPACE to capture center positions
    - Press ENTER when complete

The calibration is saved per-device and persists across sessions.

### Multiple Transmitters (needs more testing)

The driver automatically handles multiple connected transmitters:

- Each device gets its own virtual joystick (`/dev/input/jsX`)
- Independent calibration profiles
- Process isolation - one device failure won't affect others
- Hot-plug support (connect/disconnect while running)

---

## Application Integration

The driver creates standard Linux joystick devices that work with any application supporting joystick input:

**Racing Simulators:**

- VRC Pro
- Assetto Corsa
- BeamNG.drive

**Flight Simulators:**

- X-Plane
- FlightGear
- Microsoft Flight Simulator (via Proton)

**Configuration:**
Most applications auto-detect the joystick. Look for "Futaba" in your joystick/controller settings.

---

## Troubleshooting

### Permission Denied

```bash
# If running manually without installer:
sudo futaba-rc-driver

# Or add yourself to input group:
sudo usermod -a -G input $USER
# Log out and back in for group changes to take effect
```

### Device Not Detected

```bash
# Verify USB connection:
lsusb | grep Futaba

# Check kernel logs:
dmesg | tail -20

# Try different USB port (especially on Steam Deck)
```

### uinput Module Not Found

```bash
# Load module immediately:
sudo modprobe uinput

# Make permanent (installer does this automatically):
echo 'uinput' | sudo tee -a /etc/modules
```

### Driver Not Auto-Starting

```bash
# Verify profile configuration:
grep -r "futaba-rc-driver" ~/.profile ~/.bashrc ~/.zshrc

# Manual start for this session:
futaba-rc-driver --daemonize &
```

### Steam Deck Specific Issues

**"Device not detected" in Desktop Mode:**

- Try different USB ports (the side port works best)
- Ensure you're in Desktop Mode, not Gaming Mode
- Check `journalctl --user -u futaba-rc-driver -f` for errors

**Auto-start not working:**

- Verify installation: `systemctl --user status futaba-rc-driver`
- Enable if needed: `systemctl --user enable futaba-rc-driver`
- Check logs: `~/.futaba-rc-driver-logs.txt`

---

## Performance Notes

This driver is engineered for real-time RC applications:

- **O(1) Frame Processing:** Constant-time input handling regardless of complexity
- **Pre-calculated Calibration Maps:** Zero runtime computation overhead
- **Real-time Priority Scheduling:** Minimizes input latency (requires CAP_SYS_NICE)
- **Optimized Memory Access:** Local variable caching eliminates attribute lookup overhead
- **Process Isolation:** Each device runs independently for maximum reliability

Typical latency: <1ms from USB interrupt to virtual device event

---

## Uninstallation

```bash
# Run the uninstaller (included in installation directory):
${HOME}/.local/opt/futaba-rc-driver/uninstall.sh
```

The uninstaller removes:

- All driver files
- USB permissions (udev rules)
- Profile auto-start entries
- Log files
- Module configurations

Your system will be exactly as it was before installation.

---

## Advanced Configuration

### Custom Calibration Files

Calibration files are stored in `${HOME}/.local/opt/futaba-rc-driver/build/Futaba/calibrations/`

Format: `PRODUCTNAME_PRODUCTID-SERIAL.json`

Example:

```json
[
	[608, 2048, 3388], // Channel 1: min, center, max
	[608, 2048, 3388], // Channel 2
	[608, 2048, 3388] // Channel 3
	// ... one entry per channel
]
```

### Noise Filtering and Dead Zones

Edit device configs in `${HOME}/.local/opt/futaba-rc-driver/build/Futaba/configs/`

```json
{
	"dead_zone": 500, // Increase for drift compensation
	"noise_filter": 50, // Increase for electrical noise
	"frame_size": 16, // USB frame size (device-specific)
	"channel_events": [
		// Joystick axis mappings
		"ABS_X",
		"ABS_Y",
		"ABS_Z",
		"ABS_RX"
	]
}
```

---

## Technical Details

**Architecture:**

- Python 3.11+ with Nuitka compilation
- Multiprocessing for device isolation
- PyUSB for USB communication
- python-uinput for virtual device creation

**Virtual Device Specification:**

- Device type: Joystick (uinput)
- Vendor ID: 0x1008 (Futaba)
- Axis range: -32768 to 32767 (16-bit precision)
- Update rate: Device-dependent (typically 50-100Hz)

---

## Support & Development

**Issues, updates, and documentation:**
https://gitlab.com/Native-Coder/futaba-usb-driver/

**Found a bug?** Please include:

- Your distribution and kernel version (`uname -a`)
- Transmitter model
- Output from `futaba-rc-driver --version`
- Relevant logs from `~/.futaba-rc-driver-logs.txt`

---

## License

See `LICENSE` file for details.

---

**Built with ❤️ for the RC community**

_敬意を込めて_
