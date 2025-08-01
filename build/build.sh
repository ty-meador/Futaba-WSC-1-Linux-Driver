#!/bin/bash
set -e

echo "🚀 RC Driver Build System"
echo "========================="

# Check if running as root (not recommended for building)
if [[ $EUID -eq 0 ]]; then
   echo "❌ Don't run the build as root. Use a regular user account."
   exit 1
fi

# Install build dependencies
echo "📦 Installing build dependencies..."
pip3 install --user nuitka ordered-set zstandard

# Run the build
echo "🔨 Starting build process..."
python3 build.py

echo ""
echo "✅ Build complete!"
echo "📁 Your executable is ready: ./rc-driver"
echo ""
echo "🎯 Usage:"
echo "   sudo ./rc-driver --autostart"
echo "   sudo ./rc-driver --endpoint <endpoint>"
echo ""