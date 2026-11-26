# Futaba RC USB Driver

> **Where this applies.** This project's one official, write-enabled repository exists only on GitLab:
> <{{repository}}>. Issues, merge requests and releases live there and
> nowhere else. If you are reading this on GitHub, you are on a push-only mirror kept for visibility: it is
> overwritten from GitLab, and an issue or pull request opened there is not seen.

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

- Elevated scheduling priority keeps input responsive even on a fully loaded system
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
wget {{download_url}}/{{package_name}}.tar.gz && tar -xzf {{package_name}}.tar.gz && cd {{package_name}} && ./{{install_script_name}}
```

### Manual Install

```shell
# Download the latest release
wget {{download_url}}/{{package_name}}.tar.gz

# Extract the archive
tar -xvzf {{package_name}}.tar.gz

# Run the installer
cd {{package_name}}
./{{install_script_name}}
```

**For Steam Deck users:** Install from Desktop Mode. The driver will auto-start the next time you log in.

---

## What's Included

- `{{executable_name}}` - Standalone executable (no dependencies required)
- `{{install_script_name}}` - System installer with guided setup
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
{{executable_name}}

# Run calibration mode
{{executable_name}} --calibrate

# Run as background daemon
{{executable_name}} --daemonize
```

### Calibration

**Initial Setup (Required):**

1. Connect your transmitter's USB receiver
2. Power on your transmitter
3. Run: `{{executable_name}} --calibrate`
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
sudo {{executable_name}}

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
grep -r "{{executable_name}}" ~/.profile ~/.bashrc ~/.zshrc

# Manual start for this session:
{{executable_name}} --daemonize &
```

### Steam Deck Specific Issues

**"Device not detected" in Desktop Mode:**

- Try different USB ports (the side port works best)
- Ensure you're in Desktop Mode, not Gaming Mode
- Check `journalctl --user -u {{executable_name}} -f` for errors

**Auto-start not working:**

- Verify installation: `systemctl --user status {{executable_name}}`
- Enable if needed: `systemctl --user enable {{executable_name}}`
- Check logs: `~/.{{executable_name}}-logs.txt`

---

## Performance Notes

This driver is engineered for real-time RC applications:

- **O(1) Frame Processing:** Constant-time input handling regardless of complexity
- **Pre-calculated Calibration Maps:** Zero runtime computation overhead
- **Elevated Process Priority:** Workers run at nice -10 — above game/simulator threads, below system audio — so input stays responsive under full load (requires CAP_SYS_NICE)
- **Optimized Memory Access:** Local variable caching eliminates attribute lookup overhead
- **Process Isolation:** Each device runs independently for maximum reliability

Typical latency: <1ms from USB interrupt to virtual device event

---

## Uninstallation

```bash
# Run the uninstaller (included in installation directory):
{{install_dir}}/uninstall.sh
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

Calibration files are stored in `{{install_dir}}/build/Futaba/calibrations/`

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

Edit device configs in `{{install_dir}}/build/Futaba/configs/`

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
- hid-parser for reading how a device describes its axes
- python-uinput for virtual device creation

**Virtual Device Specification:**

- Device type: Joystick (uinput)
- Vendor ID: 0x1008 (Futaba)
- Axis range: -32768 to 32767 (16-bit precision)
- Update rate: Device-dependent (typically 50-100Hz)

---

## Support & Development

**Issues, updates, and documentation:**
{{repository}}

**Contributing and security reports:**
[CONTRIBUTING.md]({{repository}}-/blob/main/CONTRIBUTING.md) and
[SECURITY.md]({{repository}}-/blob/main/SECURITY.md). Security problems go in a confidential GitLab issue,
never a public one.

**Found a bug?** Please include:

- Your distribution and kernel version (`uname -a`)
- Transmitter model
- Output from `{{executable_name}} --version`
- Relevant logs from `~/.{{executable_name}}-logs.txt`

---

## License

See `LICENSE` file for details.

---

**Built with ❤️ for the RC community**
