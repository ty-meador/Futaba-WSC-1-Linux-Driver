#!/usr/bin/env python3
"""Package RC Driver into a standalone distribution."""

import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime


def run_command(cmd, cwd=None, capture=True):
    """Run a command and handle errors."""
    try:
        if capture:
            result = subprocess.run(
                cmd, shell=True, check=True, cwd=cwd, capture_output=True, text=True
            )
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd)
            return ""
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        if capture and e.stderr:
            print(f"Error: {e.stderr}")
        return None


def get_version_info():
    """Extract version and build info."""
    version = "1.0.0"  # Default version

    # Try to get version from git
    git_version = run_command("git describe --tags --always --dirty 2>/dev/null")
    if git_version:
        version = git_version

    build_date = datetime.now().strftime("%Y%m%d_%H%M%S")
    return version, build_date


def create_readme():
    """Create a comprehensive README for the distribution."""
    readme_content = """# Futaba RC USB Driver - Standalone Distribution

## Quick Start

1. Extract this archive
2. Run the installer: `sudo ./install.sh`
3. Or run directly: `sudo ./rc-driver`

## What's Included

- `rc-driver` - Main executable (requires sudo for uinput access)
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
sudo ./rc-driver
```

### Option 2: System Install (Permanent)
```bash
sudo ./install.sh
# Then run from anywhere:
rc-driver
```

## Supported Devices

- Futaba WSC-1
- Other Futaba USB receivers (auto-detected)

## Usage

The driver automatically detects connected Futaba receivers and creates virtual joystick devices in `/dev/input/`. These can be used by any Linux application that supports joysticks (games, simulators, etc.).

### Basic Usage
1. Connect your Futaba USB receiver
2. Run `sudo ./rc-driver`
3. The driver will auto-detect and configure your receiver
4. Use CTRL+C to stop

### Advanced Options
```bash
sudo ./rc-driver --help          # Show all options
sudo ./rc-driver --list-devices  # List detected receivers
sudo ./rc-driver --calibrate     # Run calibration mode
```

## Troubleshooting

### Permission Denied
- Make sure you're running with sudo: `sudo ./rc-driver`
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

- This driver is optimized for real-time RC applications
- Low latency, high precision input processing
- Minimal CPU usage in normal operation

## Support

For issues, updates, and documentation visit:
https://github.com/your-repo/futaba-usb-linux-driver

---
Built with ❤️ for the RC community
"""
    return readme_content


def create_install_script():
    """Create system installation script."""
    install_script = """#!/bin/bash
# Futaba RC Driver System Installer

set -e

INSTALL_DIR="/opt/futaba-rc-driver"
BIN_DIR="/usr/local/bin"
SERVICE_DIR="/etc/systemd/system"

echo "🎮 Futaba RC Driver System Installer"
echo "===================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

echo "📦 Installing Futaba RC Driver..."

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"

    # Copy files
echo "📋 Copying driver files..."
cp rc-driver "$INSTALL_DIR/"
cp README.md "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/rc-driver"

# Copy the entire distribution directory
if [ -d "main.dist" ]; then
    cp -r main.dist "$INSTALL_DIR/"
elif [ -d "rc-driver.dist" ]; then
    cp -r rc-driver.dist "$INSTALL_DIR/"
fi

# Create symlink in PATH
echo "🔗 Creating system command..."
ln -sf "$INSTALL_DIR/rc-driver" "$BIN_DIR/rc-driver"

# Create udev rules for USB permissions
echo "⚙️  Setting up USB permissions..."
cat > /etc/udev/rules.d/99-futaba-rc.rules << 'EOF'
# Futaba RC USB receivers
SUBSYSTEM=="usb", ATTR{idVendor}=="0925", GROUP="input", MODE="0664"
# Allow input group to access uinput
KERNEL=="uinput", GROUP="input", MODE="0660"
EOF

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

# Ensure uinput module loads at boot
echo "🔧 Configuring uinput module..."
if ! grep -q "^uinput" /etc/modules 2>/dev/null; then
    echo "uinput" >> /etc/modules
fi

# Load uinput module now
modprobe uinput || true

# Create systemd service (optional)
echo "🚀 Creating systemd service..."
cat > "$SERVICE_DIR/futaba-rc-driver.service" << 'EOF'
[Unit]
Description=Futaba RC USB Driver
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
ExecStart=/opt/futaba-rc-driver/rc-driver
Restart=always
RestartSec=5
User=root
Group=input

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Installation complete!"
echo ""
echo "🎯 Usage:"
echo "  rc-driver                    # Run the driver"
echo "  systemctl start futaba-rc-driver   # Start as service"
echo "  systemctl enable futaba-rc-driver  # Auto-start at boot"
echo ""
echo "📝 Note: You may need to log out and back in for group changes to take effect"
echo "🔧 Test with: rc-driver --help"
"""
    return install_script


def create_uninstall_script():
    """Create uninstall script."""
    uninstall_script = """#!/bin/bash
# Futaba RC Driver Uninstaller

set -e

INSTALL_DIR="/opt/futaba-rc-driver"
BIN_DIR="/usr/local/bin"
SERVICE_DIR="/etc/systemd/system"

echo "🗑️  Futaba RC Driver Uninstaller"
echo "==============================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

echo "🛑 Stopping and disabling service..."
systemctl stop futaba-rc-driver 2>/dev/null || true
systemctl disable futaba-rc-driver 2>/dev/null || true

echo "📁 Removing installation files..."
rm -rf "$INSTALL_DIR"
rm -f "$BIN_DIR/rc-driver"
rm -f "$SERVICE_DIR/futaba-rc-driver.service"

echo "⚙️  Removing udev rules..."
rm -f /etc/udev/rules.d/99-futaba-rc.rules

echo "🔄 Reloading systemd and udev..."
systemctl daemon-reload
udevadm control --reload-rules
udevadm trigger

echo "✅ Uninstall complete!"
"""
    return uninstall_script


def package_distribution():
    """Create the standalone distribution package."""
    print("📦 Creating standalone distribution package...")

    # Find the build directory
    build_dir = None
    possible_dirs = ["rc-driver.dist", "main.dist"]

    for dir_name in possible_dirs:
        if os.path.exists(dir_name):
            build_dir = dir_name
            print(f"✅ Found build directory: {build_dir}")
            break

    if not build_dir:
        print("❌ No build found! Run build script first.")
        print(f"   Looking for: {', '.join(possible_dirs)}")
        sys.exit(1)

    # Get version info
    version, build_date = get_version_info()
    print(f"📋 Version: {version}")
    print(f"📅 Build: {build_date}")

    # Create package directory
    package_name = f"futaba-rc-driver-{version}-linux-x86_64"
    package_dir = f"dist/{package_name}"

    print(f"📁 Creating package: {package_name}")

    # Clean and create dist directory
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    os.makedirs(package_dir)

    # Copy the main executable and its dependencies
    print("📋 Copying executable...")
    shutil.copytree(build_dir, f"{package_dir}/{build_dir}")

    # Find the actual executable name
    exec_name = "rc-driver"  # Default
    possible_execs = ["rc-driver", "main"]

    for exe in possible_execs:
        exe_path = os.path.join(build_dir, exe)
        if os.path.exists(exe_path) and os.access(exe_path, os.X_OK):
            exec_name = exe
            print(f"✅ Found executable: {exe_path}")
            break

    # Create wrapper script that works from any location
    wrapper_script = f"""#!/bin/bash
# Futaba RC Driver Wrapper
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
exec "$SCRIPT_DIR/{build_dir}/{exec_name}" "$@"
"""

    with open(f"{package_dir}/rc-driver", "w") as f:
        f.write(wrapper_script)
    os.chmod(f"{package_dir}/rc-driver", 0o755)

    # Create documentation
    print("📄 Creating documentation...")
    with open(f"{package_dir}/README.md", "w") as f:
        f.write(create_readme())

    # Create installation scripts
    print("🔧 Creating installation scripts...")
    with open(f"{package_dir}/install.sh", "w") as f:
        f.write(create_install_script())
    os.chmod(f"{package_dir}/install.sh", 0o755)

    with open(f"{package_dir}/uninstall.sh", "w") as f:
        f.write(create_uninstall_script())
    os.chmod(f"{package_dir}/uninstall.sh", 0o755)

    # Copy license if it exists
    if os.path.exists("LICENSE"):
        shutil.copy2("LICENSE", f"{package_dir}/")
    else:
        # Create a basic license file
        with open(f"{package_dir}/LICENSE", "w") as f:
            f.write("MIT License - See project repository for full license text\n")

    # Create version info file
    with open(f"{package_dir}/VERSION", "w") as f:
        f.write(f"Version: {version}\n")
        f.write(f"Build Date: {build_date}\n")
        f.write("Platform: Linux x86_64\n")

    # Calculate sizes
    print("📊 Calculating package size...")
    du_result = run_command(f"du -sh {package_dir}")
    if du_result:
        package_size = du_result.split()[0]
        print(f"📦 Package size: {package_size}")

    # Create compressed archives
    print("🗜️  Creating compressed archives...")

    # Create tar.gz (most compatible)
    tar_gz_name = f"dist/{package_name}.tar.gz"
    with tarfile.open(tar_gz_name, "w:gz") as tar:
        tar.add(package_dir, arcname=package_name)

    # Create tar.xz (smaller size)
    tar_xz_name = f"dist/{package_name}.tar.xz"
    run_command(f"cd dist && tar -cJf {os.path.basename(tar_xz_name)} {package_name}")

    # Get archive sizes
    tar_gz_size = (
        run_command(f"du -sh {tar_gz_name}").split()[0]
        if run_command(f"du -sh {tar_gz_name}")
        else "Unknown"
    )
    tar_xz_size = (
        run_command(f"du -sh {tar_xz_name}").split()[0]
        if run_command(f"du -sh {tar_xz_name}")
        else "Unknown"
    )

    # Create checksums
    print("🔐 Creating checksums...")
    run_command(f"cd dist && sha256sum {package_name}.tar.gz > {package_name}.tar.gz.sha256")
    run_command(f"cd dist && sha256sum {package_name}.tar.xz > {package_name}.tar.xz.sha256")

    # Create download script
    download_script = f"""#!/bin/bash
# Quick Download and Install Script for Futaba RC Driver

set -e

PACKAGE_NAME="{package_name}"
DOWNLOAD_URL="https://github.com/your-repo/releases/download/v{version}/"

echo "🎮 Futaba RC Driver Quick Installer"
echo "===================================="

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ This package is for Linux only"
    exit 1
fi

# Check architecture
if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "❌ This package requires x86_64 architecture"
    exit 1
fi

# Download and install
echo "📥 Downloading latest release..."
wget -q --show-progress "${{DOWNLOAD_URL}}${{PACKAGE_NAME}}.tar.gz" || {{
    echo "❌ Download failed. Please download manually from:"
    echo "   ${{DOWNLOAD_URL}}${{PACKAGE_NAME}}.tar.gz"
    exit 1
}}

echo "📦 Extracting package..."
tar -xzf "${{PACKAGE_NAME}}.tar.gz"

echo "🚀 Running installer..."
cd "$PACKAGE_NAME"
sudo ./install.sh

echo "🧹 Cleaning up..."
cd ..
rm -rf "${{PACKAGE_NAME}}" "${{PACKAGE_NAME}}.tar.gz"

echo "✅ Installation complete!"
echo "🎯 Run with: rc-driver"
"""

    with open("dist/quick-install.sh", "w") as f:
        f.write(download_script)
    os.chmod("dist/quick-install.sh", 0o755)

    # Summary
    print("\n🎉 Distribution package created successfully!")
    print("=" * 50)
    print(f"📦 Package: {package_name}")
    print(f"📏 Uncompressed: {package_size}")
    print(f"🗜️  tar.gz: {tar_gz_size}")
    print(f"🗜️  tar.xz: {tar_xz_size}")
    print("📁 Location: dist/")
    print("\n📋 Files created:")

    dist_files = os.listdir("dist")
    for f in sorted(dist_files):
        file_path = f"dist/{f}"
        if os.path.isfile(file_path):
            size = (
                run_command(f"du -sh {file_path}").split()[0]
                if run_command(f"du -sh {file_path}")
                else "?"
            )
            print(f"  📄 {f} ({size})")
        else:
            print(f"  📁 {f}/")

    print("\n🚀 Ready for distribution!")
    print("📤 Upload these files for release:")
    print(f"   • {package_name}.tar.gz")
    print(f"   • {package_name}.tar.xz")
    print(f"   • {package_name}.tar.gz.sha256")
    print(f"   • {package_name}.tar.xz.sha256")
    print("   • quick-install.sh")

    print("\n💡 Users can install with:")
    print(
        "   wget https://your-site.com/quick-install.sh && chmod +x quick-install.sh && ./quick-install.sh"
    )
    print("   # OR")
    print(f"   wget https://your-site.com/{package_name}.tar.gz")
    print(f"   tar -xzf {package_name}.tar.gz")
    print(f"   cd {package_name}")
    print("   sudo ./install.sh")


if __name__ == "__main__":
    print("📦 Futaba RC Driver Packaging Tool")
    print("=" * 40)
    package_distribution()
