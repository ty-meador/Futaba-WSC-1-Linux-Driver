#!/bin/bash
# Futaba RC Driver System Uninstaller - Universal Profile-Based Removal

set -e

# Safely evaluate any environment variables that are stored in our settings
INSTALL_DIR=$( echo "{{install_dir}}" | envsubst )
BIN_DIR=$( echo "{{bin_dir}}" | envsubst )
EXECUTABLE=$( echo "{{executable_name}}" | envsubst )
# pgrep/pkill -x match the kernel comm name, which is truncated to 15 chars;
# everything else (symlinks, udev rules, logs) needs the full name
COMM_NAME="${EXECUTABLE:0:15}"

echo "Futaba RC Driver System Uninstaller"
echo "======================================"

# Detect current user and warn if running as root
if [[ $EUID -eq 0 ]]; then
    echo "ERROR: This uninstaller should NOT be run as root"
    echo "       Run as your regular user - sudo will be used only when needed"
    exit 1
fi

echo "Removing universal user-space installation:"
echo "   Install: ${INSTALL_DIR}"
echo "   Binary:  ${BIN_DIR}"

# Stop any running instances
echo "Stopping any running driver instances..."
if pgrep -x "${COMM_NAME}" >/dev/null 2>&1; then
    pkill -x "${COMM_NAME}" 2>/dev/null || true
    for _ in $(seq 1 50); do
        pgrep -x "${COMM_NAME}" >/dev/null 2>&1 || break
        sleep 0.1
    done
    if pgrep -x "${COMM_NAME}" >/dev/null 2>&1; then
        echo "   WARNING: Some driver processes did not exit (stuck in kernel I/O)."
        echo "            They will only disappear after a reboot."
    fi
fi


echo "Uninstalling Futaba RC Driver..."

# Remove symlink from PATH
echo "Removing user command..."
if [ -L "${BIN_DIR}/${EXECUTABLE}" ]; then
    rm -f "${BIN_DIR}/${EXECUTABLE}"
    echo "   Removed symlink from ${BIN_DIR}"
fi

# Remove auto-start entries from profile files
for profile in "${HOME}/.profile" "${HOME}/.bashrc" "${HOME}/.zshrc"; do
    if [ -f "${profile}" ]; then
        header="Futaba RC Driver"
        # Create a temporary file without the Futaba RC Driver section
        if grep -q "^# ${header}$" "${profile}" 2>/dev/null; then
            # Remove the header line, the executable line, and empty lines around it
            sed -i "/^# ${header}$/,/^$/d" "${profile}"
            echo "   Removed auto-start from $(basename "${profile}")"
        fi
        
        # Remove PATH export line
        if grep -q "${INSTALL_DIR}" "${profile}"; then
            sed -i "\|export PATH.*${INSTALL_DIR}|d" "${profile}"
            echo "   Removed PATH entry from $(basename "${profile}")"
        fi
    fi
done

# Remove installation directory
echo "Removing installation directory..."
if [ -d "${INSTALL_DIR}" ]; then
    rm -rf "${INSTALL_DIR}"
    echo "   Removed ${INSTALL_DIR}"
fi

# Remove USB permissions (requires sudo)
echo "Removing USB permissions (requires sudo)..."
for UDEV_RULE in "/etc/udev/rules.d/70-${EXECUTABLE}.rules" "/etc/udev/rules.d/99-${EXECUTABLE}.rules"; do
    if [ -f "${UDEV_RULE}" ]; then
        sudo rm -f "${UDEV_RULE}"
        echo "   Removed udev rule ${UDEV_RULE}"
    fi
done

# Remove uinput module configuration
echo "Removing uinput module configuration (requires sudo)..."
if [ -f "/etc/modules-load.d/uinput.conf" ]; then
    sudo rm -f /etc/modules-load.d/uinput.conf
    echo "   Removed uinput module auto-loading"
elif [ -f "/etc/modules" ]; then
    if sudo grep -q "^uinput" /etc/modules 2>/dev/null; then
        sudo sed -i '/^uinput$/d' /etc/modules
        echo "   Removed uinput from /etc/modules"
    fi
fi

# Reload udev rules
if command -v udevadm >/dev/null; then
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "   Reloaded udev rules"
fi

# Clean up log files
LOG_FILE="${HOME}/.${EXECUTABLE}-logs.txt"
if [ -f "${LOG_FILE}" ]; then
    rm -f "${LOG_FILE}"
    echo "   Removed log file"
fi

echo ""
echo "Uninstallation complete!"
echo ""
echo "Notes:"
echo "  • User group membership (input group) was not changed"
echo "  • You may want to log out and back in to refresh your environment"
echo "  • The uinput kernel module is still loaded but won't auto-load on next boot"
echo ""
echo "Futaba RC Driver has been completely removed from your system"