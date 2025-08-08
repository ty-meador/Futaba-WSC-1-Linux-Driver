#!/bin/bash
# Futaba RC Driver System Installer

set -e

INSTALL_DIR='{{install_dir}}'
BIN_DIR='{{bin_dir}}'
SERVICE_DIR='{{service_dir}}'

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
cp {{executable_name}} "$INSTALL_DIR/"
cp README.md "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/{{executable_name}}"

# Copy the entire distribution directory
cp -r {{executable_name}}.dist "$INSTALL_DIR/"

# Create symlink in PATH
echo "🔗 Creating system command..."
ln -sf "$INSTALL_DIR/{{executable_name}}" "$BIN_DIR/{{executable_name}}"

# Create udev rules for USB permissions
echo "⚙️  Setting up USB permissions..."
cat > /etc/udev/rules.d/99-{{executable_name}}.rules << 'EOF'
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
cat > "$SERVICE_DIR/{{executable_name}}.service" << 'EOF'
[Unit]
Description=Futaba RC USB Driver
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
ExecStart=/opt/futaba-rc-driver/{{executable_name}}
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
echo "  {{executable_name}}                           # Run the driver"
echo "  systemctl start {{executable_name}}           # Start as service"
echo "  systemctl enable {{executable_name}}          # Auto-start at boot"
echo ""
echo "📝 Note: You may need to log out and back in for group changes to take effect"
echo "🔧 Test with: {{executable_name}} --help"
