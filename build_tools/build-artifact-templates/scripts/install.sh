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

# Add distribution warning and Steam Deck detection
IS_STEAMOS=false
USE_USER_SERVICE=false

if [ -f /etc/os-release ]; then
    . /etc/os-release
    case $ID in
        ubuntu|debian)
            echo "✅ Supported distribution: $ID"
            ;;
        steamos)
            IS_STEAMOS=true
            echo "🎮 Steam Deck detected (SteamOS $VERSION_ID)"
            # Check if root filesystem is read-only (immutable mode)
            if mount | grep -q "/ .*ro,"; then
                USE_USER_SERVICE=true
                echo "   Using user-space installation for update persistence"
            fi
            ;;
        arch)
            if [ -f /etc/steamos-release ]; then
                IS_STEAMOS=true
                USE_USER_SERVICE=true
                echo "🎮 Steam Deck detected (Arch-based SteamOS)"
                echo "   Using user-space installation for update persistence"
            else
                echo "✅ Supported distribution: Arch Linux"
            fi
            ;;
        *)
            echo "⚠️  WARNING: This installer is primarily tested on Ubuntu/Debian"
            echo "   Your distribution: $ID"
            echo "   Installation will continue, but you may need manual configuration."
            ;;
    esac
fi

# Adjust paths for Steam Deck user-space installation
if [ "$USE_USER_SERVICE" = true ]; then
    INSTALL_DIR="/home/deck/.local/opt/futaba-rc-driver"
    BIN_DIR="/home/deck/.local/bin"
    SERVICE_DIR="/home/deck/.config/systemd/user"
    echo "📍 Using Steam Deck persistent paths:"
    echo "   Install: $INSTALL_DIR"
    echo "   Binary:  $BIN_DIR"
    echo "   Service: $SERVICE_DIR"
fi

echo "📦 Installing Futaba RC Driver..."

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Copy files - with existence check
if [ ! -f "{{executable_name}}" ]; then
    echo "❌ Executable not found in package. Installation cannot continue."
    exit 1
fi

echo "📋 Copying driver files..."
cp {{executable_name}} "$INSTALL_DIR/"
[ -f "README.md" ] && cp README.md "$INSTALL_DIR/"
[ -f "LICENSE" ] && cp LICENSE "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/{{executable_name}}"

# Copy the entire distribution directory if it exists
if [ -d "{{executable_name}}.dist" ]; then
    cp -r {{executable_name}}.dist "$INSTALL_DIR/"
elif [ -d "build" ]; then
    cp -r build "$INSTALL_DIR/"
fi

# Set ownership for Steam Deck user installation
if [ "$USE_USER_SERVICE" = true ]; then
    chown -R deck:deck "$INSTALL_DIR"
fi

# Create symlink in PATH
echo "🔗 Creating system command..."
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/{{executable_name}}" "$BIN_DIR/{{executable_name}}"

# Set ownership for Steam Deck user installation
if [ "$USE_USER_SERVICE" = true ]; then
    chown -R deck:deck "$BIN_DIR"
    # Add to PATH in .bashrc if not already there
    if [ -f /home/deck/.bashrc ] && ! grep -q "/home/deck/.local/bin" /home/deck/.bashrc; then
        echo 'export PATH="/home/deck/.local/bin:$PATH"' >> /home/deck/.bashrc
        chown deck:deck /home/deck/.bashrc
    fi
fi

# Create udev rules for USB permissions
echo "⚙️  Setting up USB permissions..."
mkdir -p /etc/udev/rules.d

if [ "$IS_STEAMOS" = true ]; then
    # Steam Deck optimized udev rules
    cat > /etc/udev/rules.d/99-{{executable_name}}.rules << 'EOF'
# Futaba RC USB receivers - Steam Deck optimized
SUBSYSTEM=="usb", ATTR{idVendor}=="0925", GROUP="input", MODE="0664", TAG+="uaccess"
# Allow input group and deck user to access uinput
KERNEL=="uinput", GROUP="input", MODE="0660", TAG+="uaccess"
EOF
    
    # Ensure deck user is in input group
    if ! groups deck | grep -q input; then
        echo "👤 Adding deck user to input group..."
        usermod -a -G input deck
        echo "   ⚠️  You'll need to log out and back in for group changes to take effect"
    fi
else
    # Standard udev rules
    cat > /etc/udev/rules.d/99-{{executable_name}}.rules << 'EOF'
# Futaba RC USB receivers
SUBSYSTEM=="usb", ATTR{idVendor}=="0925", GROUP="input", MODE="0664"
# Allow input group to access uinput
KERNEL=="uinput", GROUP="input", MODE="0660"
EOF
fi

# Reload udev rules
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules
    udevadm trigger
else
    echo "⚠️  udevadm not found. Please restart for USB permissions to take effect."
fi

# Ensure uinput module loads at boot
echo "🔧 Configuring uinput module..."
if [ -f /etc/modules ]; then
    if ! grep -q "^uinput" /etc/modules 2>/dev/null; then
        echo "uinput" >> /etc/modules
    fi
elif [ -d /etc/modules-load.d ]; then
    echo "uinput" > /etc/modules-load.d/uinput.conf
else
    echo "⚠️  Could not configure uinput auto-loading. You may need to run 'sudo modprobe uinput' after reboot."
fi

# Load uinput module now
modprobe uinput || echo "⚠️  Could not load uinput module. Try: sudo modprobe uinput"

# Create systemd service (if systemd is available)
if command -v systemctl >/dev/null 2>&1 && [ -d "$SERVICE_DIR" ] || [ "$USE_USER_SERVICE" = true ]; then
    echo "🚀 Creating systemd service..."
    
    # Create service directory if it doesn't exist (for user services)
    mkdir -p "$SERVICE_DIR"
    
    if [ "$USE_USER_SERVICE" = true ]; then
        # Steam Deck user service
        cat > "$SERVICE_DIR/{{executable_name}}.service" << 'EOF'
[Unit]
Description=Futaba RC USB Driver
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=/home/deck/.local/opt/futaba-rc-driver/{{executable_name}}
Restart=always
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
EOF
        
        # Set correct ownership for user service
        chown -R deck:deck "$SERVICE_DIR"
        
        echo "   📝 User service created for Steam Deck. To enable:"
        echo "   systemctl --user daemon-reload"
        echo "   systemctl --user enable {{executable_name}}"
        echo "   systemctl --user start {{executable_name}}"
    else
        # Standard system service
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
        systemctl daemon-reload
    fi
else
    echo "⚠️  Systemd not available. Manual execution only."
fi

echo "✅ Installation complete!"
echo ""
echo "🎯 Usage:"
echo "  {{executable_name}}                           # Run the driver"

if [ "$USE_USER_SERVICE" = true ]; then
    echo "  systemctl --user start {{executable_name}}   # Start as user service"
    echo "  systemctl --user enable {{executable_name}}  # Auto-start with session"
    echo ""
    echo "🎮 Steam Deck Notes:"
    echo "  - Driver installed in user space for update persistence"
    echo "  - You may need to log out and back in for PATH changes to take effect"
    echo "  - User service runs when deck user logs in to desktop mode"
    echo "  - Installation will survive SteamOS updates"
elif command -v systemctl >/dev/null 2>&1; then
    echo "  systemctl start {{executable_name}}           # Start as service"
    echo "  systemctl enable {{executable_name}}          # Auto-start at boot"
fi

echo ""
echo "📝 Note: You may need to log out and back in for group changes to take effect"
echo "🔧 Test with: {{executable_name}} --help"