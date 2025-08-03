#!/usr/bin/env python3
"""Package Futaba RC Driver into a standalone distribution."""

import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime


def runCommand(cmd: str, cwd: str | None = None, capture: bool = True) -> str | None:
    """Run a command and handle errors.

    Args:
        cmd: Command to run as shell string
        cwd: Working directory for command execution
        capture: Whether to capture and return output

    Returns:
        Command output if capture=True and successful, empty string if capture=False and successful,
        None if command failed

    """
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


def getVersionInfo() -> tuple[str, str]:
    """Extract version and build info from git and current timestamp.

    Attempts to get version information from git tags, falls back to default
    version if git is not available or no tags exist.

    Returns:
        Tuple containing (version, buildDate) strings

    """
    version = "1.0.0"  # Default version

    # Try to get version from git
    gitVersion = runCommand("git describe --tags --always --dirty 2>/dev/null")
    if gitVersion:
        version = gitVersion

    buildDate = datetime.now().strftime("%Y%m%d_%H%M%S")
    return version, buildDate


def createReadme() -> str:
    """Create a comprehensive README for the distribution.

    Generates complete documentation including installation instructions,
    usage examples, troubleshooting guide, and system requirements.

    Returns:
        Complete README content as string

    """
    readmeContent = """# Futaba RC USB Driver - Standalone Distribution

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
sudo ./install.sh
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

### Advanced Options
```bash
sudo ./futaba-rc-driver --help          # Show all options
sudo ./futaba-rc-driver --list-devices  # List detected receivers
sudo ./futaba-rc-driver --calibrate     # Run calibration mode
```

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

- This driver is optimized for real-time RC applications
- Low latency, high precision input processing
- Minimal CPU usage in normal operation

## Support

For issues, updates, and documentation visit:
https://github.com/your-repo/futaba-usb-linux-driver

---
Built with ❤️ for the RC community
"""
    return readmeContent


def createInstallScript() -> str:
    """Create system installation script.

    Generates a comprehensive installer script that:
    - Installs files to system directories
    - Sets up USB permissions via udev rules
    - Configures uinput module loading
    - Creates systemd service for auto-start

    Returns:
        Complete installation script content as string

    """
    installScript = """#!/bin/bash
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
cp futaba-rc-driver "$INSTALL_DIR/"
cp README.md "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/futaba-rc-driver"

# Copy the entire distribution directory
if [ -d "main.dist" ]; then
    cp -r main.dist "$INSTALL_DIR/"
elif [ -d "futaba-rc-driver.dist" ]; then
    cp -r futaba-rc-driver.dist "$INSTALL_DIR/"
fi

# Create symlink in PATH
echo "🔗 Creating system command..."
ln -sf "$INSTALL_DIR/futaba-rc-driver" "$BIN_DIR/futaba-rc-driver"

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
ExecStart=/opt/futaba-rc-driver/futaba-rc-driver
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
echo "  futaba-rc-driver                           # Run the driver"
echo "  systemctl start futaba-rc-driver           # Start as service"
echo "  systemctl enable futaba-rc-driver          # Auto-start at boot"
echo ""
echo "📝 Note: You may need to log out and back in for group changes to take effect"
echo "🔧 Test with: futaba-rc-driver --help"
"""
    return installScript


def createUninstallScript() -> str:
    """Create uninstall script.

    Generates a complete uninstaller that removes all installed files,
    services, and configuration created by the installer.

    Returns:
        Complete uninstallation script content as string

    """
    uninstallScript = """#!/bin/bash
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
rm -f "$BIN_DIR/futaba-rc-driver"
rm -f "$SERVICE_DIR/futaba-rc-driver.service"

echo "⚙️  Removing udev rules..."
rm -f /etc/udev/rules.d/99-futaba-rc.rules

echo "🔄 Reloading systemd and udev..."
systemctl daemon-reload
udevadm control --reload-rules
udevadm trigger

echo "✅ Uninstall complete!"
"""
    return uninstallScript


def packageDistribution() -> None:
    """Create the standalone distribution package.

    Creates a complete distribution package including:
    - Compiled executable and dependencies
    - Documentation and installation scripts
    - Compressed archives with checksums
    - Quick install script for easy deployment

    Raises:
        SystemExit: If build directory is not found or other critical errors occur

    """
    print("📦 Creating standalone distribution package...")

    # Find the build directory
    possibleBuildDirs = ["main.dist", "futaba-rc-driver.dist"]
    buildDir = None

    for dirName in possibleBuildDirs:
        if os.path.exists(dirName):
            buildDir = dirName
            print(f"✅ Found build directory: {buildDir}")
            break

    if not buildDir:
        print("❌ No build found! Run build script first.")
        print(f"   Looking for: {', '.join(possibleBuildDirs)}")
        sys.exit(1)

    # Get version info
    version, buildDate = getVersionInfo()
    print(f"📋 Version: {version}")
    print(f"📅 Build: {buildDate}")

    # Create package directory
    packageName = f"futaba-rc-driver-{version}-linux-x86_64"
    packageDir = f"dist/{packageName}"

    print(f"📁 Creating package: {packageName}")

    # Clean and create dist directory
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    os.makedirs(packageDir)

    # Copy the main executable and its dependencies
    print("📋 Copying executable...")
    shutil.copytree(buildDir, f"{packageDir}/{buildDir}")

    # Find the actual executable
    possibleExecutables = ["futaba-rc-driver", "main"]
    executableName = None

    for execName in possibleExecutables:
        executablePath = os.path.join(buildDir, execName)
        if os.path.exists(executablePath) and os.access(executablePath, os.X_OK):
            executableName = execName
            print(f"✅ Found executable: {executablePath}")
            break

    if not executableName:
        print(f"❌ No executable found in {buildDir}")
        print("📁 Contents of build directory:")
        for item in os.listdir(buildDir):
            print(f"  - {item}")
        sys.exit(1)

    # Create wrapper script that works from any location
    wrapperScript = f"""#!/bin/bash
# Futaba RC Driver Wrapper
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
exec "$SCRIPT_DIR/{buildDir}/{executableName}" "$@"
"""

    with open(f"{packageDir}/futaba-rc-driver", "w") as f:
        f.write(wrapperScript)
    os.chmod(f"{packageDir}/futaba-rc-driver", 0o755)

    # Create documentation
    print("📄 Creating documentation...")
    with open(f"{packageDir}/README.md", "w") as f:
        f.write(createReadme())

    # Create installation scripts
    print("🔧 Creating installation scripts...")
    with open(f"{packageDir}/install.sh", "w") as f:
        f.write(createInstallScript())
    os.chmod(f"{packageDir}/install.sh", 0o755)

    with open(f"{packageDir}/uninstall.sh", "w") as f:
        f.write(createUninstallScript())
    os.chmod(f"{packageDir}/uninstall.sh", 0o755)

    # Copy license if it exists
    if os.path.exists("LICENSE"):
        shutil.copy2("LICENSE", f"{packageDir}/")
    else:
        # Create a basic license file
        with open(f"{packageDir}/LICENSE", "w") as f:
            f.write("MIT License - See project repository for full license text\n")

    # Create version info file
    with open(f"{packageDir}/VERSION", "w") as f:
        f.write(f"Version: {version}\n")
        f.write(f"Build Date: {buildDate}\n")
        f.write("Platform: Linux x86_64\n")

    # Calculate sizes
    print("📊 Calculating package size...")
    duResult = runCommand(f"du -sh {packageDir}")
    if duResult:
        packageSize = duResult.split()[0]
        print(f"📦 Package size: {packageSize}")

    # Create compressed archives
    print("🗜️  Creating compressed archives...")

    # Create tar.gz (most compatible)
    tarGzName = f"dist/{packageName}.tar.gz"
    with tarfile.open(tarGzName, "w:gz") as tar:
        tar.add(packageDir, arcname=packageName)

    # Create tar.xz (smaller size)
    tarXzName = f"dist/{packageName}.tar.xz"
    runCommand(f"cd dist && tar -cJf {os.path.basename(tarXzName)} {packageName}")

    # Get archive sizes
    tarGzSize = (
        runCommand(f"du -sh {tarGzName}").split()[0]
        if runCommand(f"du -sh {tarGzName}")
        else "Unknown"
    )
    tarXzSize = (
        runCommand(f"du -sh {tarXzName}").split()[0]
        if runCommand(f"du -sh {tarXzName}")
        else "Unknown"
    )

    # Create checksums
    print("🔐 Creating checksums...")
    runCommand(f"cd dist && sha256sum {packageName}.tar.gz > {packageName}.tar.gz.sha256")
    runCommand(f"cd dist && sha256sum {packageName}.tar.xz > {packageName}.tar.xz.sha256")

    # Create download script
    downloadScript = f"""#!/bin/bash
# Quick Download and Install Script for Futaba RC Driver

set -e

PACKAGE_NAME="{packageName}"
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
echo "🎯 Run with: futaba-rc-driver"
"""

    with open("dist/quick-install.sh", "w") as f:
        f.write(downloadScript)
    os.chmod("dist/quick-install.sh", 0o755)

    # Summary
    print("\n🎉 Distribution package created successfully!")
    print("=" * 50)
    print(f"📦 Package: {packageName}")
    print(f"📏 Uncompressed: {packageSize}")
    print(f"🗜️  tar.gz: {tarGzSize}")
    print(f"🗜️  tar.xz: {tarXzSize}")
    print("📁 Location: dist/")
    print("\n📋 Files created:")

    distFiles = os.listdir("dist")
    for f in sorted(distFiles):
        filePath = f"dist/{f}"
        if os.path.isfile(filePath):
            size = (
                runCommand(f"du -sh {filePath}").split()[0]
                if runCommand(f"du -sh {filePath}")
                else "?"
            )
            print(f"  📄 {f} ({size})")
        else:
            print(f"  📁 {f}/")

    print("\n🚀 Ready for distribution!")
    print("📤 Upload these files for release:")
    print(f"   • {packageName}.tar.gz")
    print(f"   • {packageName}.tar.xz")
    print(f"   • {packageName}.tar.gz.sha256")
    print(f"   • {packageName}.tar.xz.sha256")
    print("   • quick-install.sh")

    print("\n💡 Users can install with:")
    print(
        "   wget https://your-site.com/quick-install.sh && chmod +x quick-install.sh && ./quick-install.sh"
    )
    print("   # OR")
    print(f"   wget https://your-site.com/{packageName}.tar.gz")
    print(f"   tar -xzf {packageName}.tar.gz")
    print(f"   cd {packageName}")
    print("   sudo ./install.sh")


if __name__ == "__main__":
    print("📦 Futaba RC Driver Packaging Tool")
    print("=" * 40)
    packageDistribution()
