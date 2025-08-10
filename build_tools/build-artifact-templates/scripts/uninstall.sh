#!/bin/bash
# Futaba RC Driver Uninstaller

set -e

INSTALL_DIR='{{install_dir}}'
BIN_DIR='{{bin_dir}}'
SERVICE_DIR='{{service_dir}}'

echo "🗑️  Futaba RC Driver Uninstaller"
echo "================================"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Detect Steam Deck and check for user-space installation
IS_STEAMOS=false
IS_USER_INSTALL=false

if [ -f /etc/os-release ]; then
    . /etc/os-release
    case $ID in
        steamos)
            IS_STEAMOS=true
            echo "🎮 Steam Deck detected (SteamOS $VERSION_ID)"
            ;;
        arch)
            if [ -f /etc/steamos-release ]; then
                IS_STEAMOS=true
                echo "🎮 Steam Deck detected (Arch-based SteamOS)"
            fi
            ;;
    esac
elif [ -f /etc/steamos-release ]; then
    IS_STEAMOS=true
    echo "🎮 Steam Deck detected"
fi

# Check for Steam Deck user-space installation
if [ "$IS_STEAMOS" = true ]; then
    USER_INSTALL_DIR="/home/deck/.local/opt/futaba-rc-driver"
    USER_BIN_DIR="/home/deck/.local/bin"
    USER_SERVICE_DIR="/home/deck/.config/systemd/user"
    
    if [ -d "$USER_INSTALL_DIR" ]; then
        echo "🔍 Found Steam Deck user-space installation"
        INSTALL_DIR="$USER_INSTALL_DIR"
        BIN_DIR="$USER_BIN_DIR"
        SERVICE_DIR="$USER_SERVICE_DIR"
        IS_USER_INSTALL=true
    else
        echo "🔍 Checking for system-wide installation"
    fi
fi

echo "🔍 Removing Futaba RC Driver installation..."

# Stop and disable systemd service if it exists
if [ "$IS_USER_INSTALL" = true ]; then
    # Handle user service for Steam Deck
    if [ -f "$SERVICE_DIR/{{executable_name}}.service" ]; then
        echo "🛑 Stopping and disabling user service..."
        sudo -u deck systemctl --user stop "{{executable_name}}" 2>/dev/null || true
        sudo -u deck systemctl --user disable "{{executable_name}}" 2>/dev/null || true
        sudo -u deck systemctl --user daemon-reload 2>/dev/null || true
        
        echo "🗑️  Removing user service file..."
        rm -f "$SERVICE_DIR/{{executable_name}}.service"
    fi
else
    # Handle system service
    if [ -f "$SERVICE_DIR/{{executable_name}}.service" ] && command -v systemctl >/dev/null 2>&1; then
        echo "🛑 Stopping and disabling system service..."
        systemctl stop "{{executable_name}}" 2>/dev/null || true
        systemctl disable "{{executable_name}}" 2>/dev/null || true
        
        echo "🗑️  Removing system service file..."
        rm -f "$SERVICE_DIR/{{executable_name}}.service"
        systemctl daemon-reload 2>/dev/null || true
    fi
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "🗑️  Removing installation directory: $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
else
    echo "⚠️  Installation directory not found: $INSTALL_DIR"
fi

# Remove symlink from PATH
if [ -L "$BIN_DIR/{{executable_name}}" ]; then
    echo "🗑️  Removing command symlink: $BIN_DIR/{{executable_name}}"
    rm -f "$BIN_DIR/{{executable_name}}"
elif [ -f "$BIN_DIR/{{executable_name}}" ]; then
    echo "🗑️  Removing command file: $BIN_DIR/{{executable_name}}"
    rm -f "$BIN_DIR/{{executable_name}}"
fi

# Remove udev rules
UDEV_RULES="/etc/udev/rules.d/99-{{executable_name}}.rules"
if [ -f "$UDEV_RULES" ]; then
    echo "🗑️  Removing udev rules: $UDEV_RULES"
    rm -f "$UDEV_RULES"
    
    # Reload udev rules
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules
        udevadm trigger
    fi
fi

# Remove uinput module configuration (optional - ask user)
MODULES_CONF="/etc/modules-load.d/uinput.conf"
MODULES_FILE="/etc/modules"

if [ -f "$MODULES_CONF" ]; then
    echo "🤔 Found uinput module configuration: $MODULES_CONF"
    read -p "   Remove uinput module auto-loading? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing uinput module configuration..."
        rm -f "$MODULES_CONF"
    fi
elif [ -f "$MODULES_FILE" ] && grep -q "^uinput" "$MODULES_FILE" 2>/dev/null; then
    echo "🤔 Found uinput in $MODULES_FILE"
    read -p "   Remove uinput module auto-loading? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing uinput from modules file..."
        sed -i '/^uinput$/d' "$MODULES_FILE"
    fi
fi

# Steam Deck specific cleanup
if [ "$IS_STEAMOS" = true ]; then
    # Check if we should remove deck user from input group
    echo "🤔 Remove deck user from input group?"
    echo "   (This may affect other input devices)"
    read -p "   Remove deck from input group? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "👤 Removing deck user from input group..."
        gpasswd -d deck input 2>/dev/null || echo "   User already not in input group"
        echo "   ⚠️  You may need to log out and back in for group changes to take effect"
    fi
    
    # Clean up PATH modification in .bashrc
    if [ -f /home/deck/.bashrc ] && grep -q "/home/deck/.local/bin" /home/deck/.bashrc; then
        echo "🤔 Found PATH modification in .bashrc"
        read -p "   Remove /home/deck/.local/bin from PATH? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  Removing PATH modification from .bashrc..."
            sed -i '\|export PATH="/home/deck/.local/bin:$PATH"|d' /home/deck/.bashrc
        fi
    fi
fi

echo ""
echo "✅ Uninstallation complete!"

if [ "$IS_STEAMOS" = true ]; then
    echo ""
    echo "🎮 Steam Deck Notes:"
    echo "   - All user-space files have been removed"
    echo "   - You may need to log out and back in for all changes to take effect"
    echo "   - Driver will not survive in the system after next SteamOS update anyway"
fi

echo ""
echo "📝 Note: You may need to restart for some changes to fully take effect"