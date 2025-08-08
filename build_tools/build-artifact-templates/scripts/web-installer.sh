#!/bin/bash
# Quick Download and Install Script for Futaba RC Driver

set -e

PACKAGE_NAME='{{package_name}}'
DOWNLOAD_URL='{{download_url}}'

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
ec