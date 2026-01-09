#!/bin/bash
# Quick Download and Install Script for Futaba RC Driver

set -e

PACKAGE_NAME='{{package_name}}'
DOWNLOAD_URL='{{download_url}}'

echo "Futaba RC Driver Quick Installer"
echo "===================================="

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "ERROR: This package is for Linux only"
    exit 1
fi

# Check architecture
if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "ERROR: This package requires x86_64 architecture"
    exit 1
fi

# Add distribution warning and Steam Deck detection
IS_STEAMOS=false

if [ -f /etc/os-release ]; then
    . /etc/os-release
    case $ID in
        ubuntu|debian)
            echo "Supported distribution detected: $ID"
            ;;
        steamos)
            IS_STEAMOS=true
            echo "Steam Deck detected (SteamOS $VERSION_ID)"
            echo "   Installing with Steam Deck optimizations"
            ;;
        arch)
            if [ -f /etc/steamos-release ]; then
                IS_STEAMOS=true
                echo "Steam Deck detected (Arch-based SteamOS)"
                echo "   Installing with Steam Deck optimizations"
            else
                echo "Supported distribution detected: Arch Linux"
            fi
            ;;
        *)
            echo "WARNING: This installer is primarily tested on Ubuntu/Debian/Arch"
            echo "         Your distribution: $ID"
            echo "         The driver should work, but installation may require manual steps."
            ;;
    esac
elif [ -f /etc/steamos-release ]; then
    IS_STEAMOS=true
    echo "Steam Deck detected"
    echo "   Installing with Steam Deck optimizations"
fi

# Steam Deck specific pre-installation info
if [ "$IS_STEAMOS" = true ]; then
    echo ""
    echo "Steam Deck Installation Notes:"
    echo "   - Installation will be placed in user space to survive SteamOS updates"
    echo "   - You may need to be in Desktop Mode for full functionality"
    echo "   - The driver will run as a user service when you're logged in"
    
    # Check if we're in Desktop Mode
    if [ "$XDG_CURRENT_DESKTOP" = "KDE" ]; then
        echo "   Desktop Mode detected"
    else
        echo "   WARNING: Consider running this from Desktop Mode for best results"
    fi
fi

# Download and install
echo "Downloading latest release..."
wget -q --show-progress "${DOWNLOAD_URL}" || {
    echo "ERROR: Download failed. Please download manually from:"
    echo "       ${DOWNLOAD_URL}"
    exit 1
}

echo "Extracting package..."
tar -xzf "${PACKAGE_NAME}.tar.gz"

echo "Running installer..."
cd "$PACKAGE_NAME"
./install.sh

# Steam Deck specific post-installation
if [ "$IS_STEAMOS" = true ] && [ $? -eq 0 ]; then
    echo ""
    echo "Steam Deck Post-Installation Setup Complete!"
    echo ""
    echo "Next Steps for Steam Deck:"
    echo "   1. Log out and back in (or restart) for all changes to take effect"
    echo "   2. Open Konsole (terminal) in Desktop Mode"
    echo "   3. Test with: {{executable_name}} --help"
    echo "   4. Enable auto-start: systemctl --user enable {{executable_name}}"
    echo "   5. Start service: systemctl --user start {{executable_name}}"
    echo ""
    echo "Steam Deck Service Management:"
    echo "   systemctl --user status {{executable_name}}    # Check status"
    echo "   systemctl --user stop {{executable_name}}      # Stop service"
    echo "   journalctl --user -u {{executable_name}} -f    # View logs"
    echo ""
    echo "Steam Deck Reminders:"
    echo "   - Driver is installed in user space and will survive SteamOS updates"
    echo "   - Keep this installer for easy reinstallation if needed"
    echo "   - Service runs when logged into Desktop Mode"
fi

echo "Cleaning up..."
cd ..
rm -rf "$PACKAGE_NAME" "${PACKAGE_NAME}.tar.gz"

echo "Installation complete!"
echo ""
echo "Usage:"
echo "  {{executable_name}}                           # Run the driver"

if [ "$IS_STEAMOS" = true ]; then
    echo "  systemctl --user start {{executable_name}}   # Start as user service"
    echo "  systemctl --user enable {{executable_name}}  # Auto-start with session"
else
    echo "  systemctl start {{executable_name}}           # Start as service"
    echo "  systemctl enable {{executable_name}}          # Auto-start at boot"
fi

echo ""
echo "Test installation: {{executable_name}} --help"