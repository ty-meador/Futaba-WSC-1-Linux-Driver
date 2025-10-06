#!/bin/bash
# Futaba RC Driver System Installer - Universal Profile-Based Installation

set -e

# Safely evaluate any environmetn variables that are stored in our settings
INSTALL_DIR=$( echo "{{install_dir}}" | envsubst )
BIN_DIR=$( echo "{{bin_dir}}" | envsubst )
EXECUTABLE=$( echo "{{executable_name}}" | envsubst )

echo "🎮 Futaba RC Driver System Installer"
echo "===================================="

# Detect current user and warn if running as root
if [[ $EUID -eq 0 ]]; then
    echo "❌ This installer should NOT be run as root"
    echo "   Run as your regular user - sudo will be used only when needed"
    exit 1
fi

# Distribution detection for informational purposes
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "ℹ️  Detected distribution: ${ID:-unknown}"
fi

echo "📍 Using universal user-space installation:"
echo "   Install: ${INSTALL_DIR}"
echo "   Binary:  ${BIN_DIR}"

echo "📦 Installing Futaba RC Driver..."

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "${INSTALL_DIR}"

# Copy files - with existence check
if [ ! -f "${EXECUTABLE}" ]; then
    echo "❌ Executable not found in package. Installation cannot continue."
    exit 1
fi

echo "📋 Copying driver files..."
[ -f "README.md" ] && cp README.md "${INSTALL_DIR}/"
[ -f "LICENSE" ] && cp LICENSE "${INSTALL_DIR}/"
[ -f "VERSION" ] && cp VERSION "${INSTALL_DIR}/"
[ -f "uninstall.sh" ] && cp uninstall.sh "${INSTALL_DIR}/"
[ -f "build/pyproject.toml" ] && cp build/pyproject.toml "${INSTALL_DIR}/"
[ -d "build" ] && cp -r build "${INSTALL_DIR}/"
cp "${EXECUTABLE}" "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/${EXECUTABLE}"

# Create symlink in PATH
echo "🔗 Creating user command..."
mkdir -p "${BIN_DIR}"
ln -sf "${INSTALL_DIR}/${EXECUTABLE}" "${BIN_DIR}/${EXECUTABLE}"

for profile in "${HOME}/.profile" "${HOME}/.bashrc" "${HOME}/.zshrc"; do
    if [ -f "${profile}" ]; then
        # Check if already added
        header="Futaba RC Driver"
        if ! grep -q "^# ${header}$" "${profile}" 2>/dev/null; then
            echo "# ${header}" >> "${profile}"
            echo "(${INSTALL_DIR}/${EXECUTABLE} --daemonize > ${HOME}/.${EXECUTABLE}-logs.txt 2>&1 &)" >> "${profile}"
            echo "" >> "${profile}"
            echo "   📝 Added auto-start to $(basename "${profile}")"
        fi

        if ! grep -q "${INSTALL_DIR}" "${profile}"; then
            echo "export PATH=\"\$PATH:${INSTALL_DIR}\"" >> "${profile}"
            echo "   📝 Added ~/${INSTALL_DIR} to PATH in $(basename "${profile}")"
        fi
        break
    fi
done

# Setup USB permissions (requires sudo)
echo "⚙️  Setting up USB permissions (requires sudo)..."
sudo mkdir -p /etc/udev/rules.d
sudo cp ./udev.rules /etc/udev/rules.d/99-${EXECUTABLE}.rules

# Ensure user is in input group
if ! groups | grep -q input; then
    echo "👤 Adding user to input group (requires sudo)..."
    sudo usermod -a -G input "$USER"
    sudo setcap cap_sys_nice+ep "${INSTALL_DIR}/${EXECUTABLE}"
    echo "   ⚠️  You'll need to log out and back in for group changes to take effect"
    GROUP_CHANGE_NEEDED=true
fi

# Reload udev rules
if command -v udevadm >/dev/null; then
    sudo udevadm control --reload-rules
    sudo udevadm trigger
else
    echo "⚠️  udevadm not found. Please restart for USB permissions to take effect."
fi

# Ensure uinput module loads at boot
echo "🔧 Configuring uinput module (requires sudo)..."
if [ -d /etc/modules-load.d ]; then
    echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
elif [ -f /etc/modules ]; then
    if ! sudo grep -q "^uinput" /etc/modules 2>/dev/null; then
        echo "uinput" | sudo tee -a /etc/modules > /dev/null
    fi
else
    echo "⚠️  Could not configure uinput auto-loading. You may need to run 'sudo modprobe uinput' after reboot."
fi

# Load uinput module now
sudo modprobe uinput || echo "⚠️  Could not load uinput module. Try: sudo modprobe uinput"

echo ""
echo "✅ Installation complete!"

echo ""
echo "🔗 If you are using a wireless transmitter please bind it to USB receiver now."
read -p "Press Enter to continue..."

echo ""
echo "🔋 Turn on your transmitter and prepare to perform initial calibration."
read -p "Press Enter to continue..."


${INSTALL_DIR}/${EXECUTABLE} --calibrate

echo ""
echo "🎯 Usage:"
echo "  ${EXECUTABLE}  # Run the driver manually"

(${INSTALL_DIR}/${EXECUTABLE} --daemonize > ${HOME}/.${EXECUTABLE}-logs.txt 2>&1 &)

if [ "${GROUP_CHANGE_NEEDED:-false}" = true ]; then
    echo "⚠️  IMPORTANT: The driver will start automatically when you log in."
    echo "    If you are using a SteamDeck and are experiencing issues try desktop mode."
fi

echo "🚀 The driver will now start automatically when you log in"
echo "🔧 Test installation: ${EXECUTABLE} --help"
echo "📝 Driver runs continuously in the background and prevents duplicate instances"
echo "🥇 Driver started, good luck!"
echo ""