#!/bin/bash
# Futaba RC Driver Uninstaller

set -e

INSTALL_DIR='{{install_dir}}'
BIN_DIR='{{bin_dir}}'
SERVICE_DIR='{{service_dir}}'
echo "🗑️  Futaba RC Driver Uninstaller"
echo "==============================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

echo "🛑 Stopping and disabling service..."
systemctl stop {{executable_name}} 2>/dev/null || true
systemctl disable {{executable_name}} 2>/dev/null || true

echo "📁 Removing installation files..."
rm -rf "$INSTALL_DIR"
rm -f "$BIN_DIR/{{executable_name}}"
rm -f "$SERVICE_DIR/{{executable_name}}.service"

echo "⚙️  Removing udev rules..."
rm -f /etc/udev/rules.d/99-{{executable_name}}.rules

echo "🔄 Reloading systemd and udev..."
systemctl daemon-reload
udevadm control --reload-rules
udevadm trigger

echo "✅ Uninstall complete!"
