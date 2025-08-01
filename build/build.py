#!/usr/bin/env python3
"""Build script to create standalone executable."""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and handle errors."""
    try:
        result = subprocess.run(cmd, shell=True, check=True, cwd=cwd, 
                              capture_output=True, text=True)
        print(f"✓ {cmd}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"✗ {cmd}")
        print(f"Error: {e.stderr}")
        sys.exit(1)

def build_executable():
    """Build the standalone executable using Nuitka."""
    
    print("🔨 Building RC Driver executable...")
    
    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("main.dist"):
        shutil.rmtree("main.dist")
    
    # Nuitka build command
    nuitka_cmd = [
        "python3", "-m", "nuitka",
        "--onefile",                    # Single executable
        "--standalone",                 # Include all dependencies
        "--assume-yes-for-downloads",   # Auto-accept downloads
        "--output-filename=rc-driver",  # Output name
        "--remove-output",              # Clean temporary files
        
        # Optimization flags
        "--lto=yes",                    # Link time optimization
        "--jobs=4",                     # Parallel compilation
        
        # Include data files and dependencies
        "--include-package=Futaba",
        "--include-package=usb",
        "--include-package=uinput",
        "--include-package=scipy",
        
        # Linux-specific optimizations
        "--linux-onefile-icon=driver.ico",  # Optional: add icon
        "--disable-console",                 # Remove if you need console output
        
        # Entry point
        "src/main.py"
    ]
    
    run_command(" ".join(nuitka_cmd))
    
    # Make executable
    run_command("chmod +x rc-driver")
    
    print("✅ Build complete! Executable: rc-driver")
    print("📦 Size:", end=" ")
    run_command("ls -lh rc-driver | awk '{print $5}'")

if __name__ == "__main__":
    build_executable()