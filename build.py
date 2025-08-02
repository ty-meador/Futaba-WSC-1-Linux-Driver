#!/usr/bin/env python3
"""Build script to create standalone executable."""

import os
import shutil
import subprocess
import sys


def run_command(cmd, cwd=None, capture=True):
    """Run a command and handle errors."""
    try:
        if isinstance(cmd, list):
            if capture:
                result = subprocess.run(cmd, check=True, cwd=cwd, capture_output=True, text=True)
                print(f"✓ {' '.join(cmd)}")
                return result.stdout
            else:
                # Stream output directly to console
                result = subprocess.run(cmd, check=True, cwd=cwd)
                print(f"✓ {' '.join(cmd)}")
                return ""
        elif capture:
            result = subprocess.run(
                cmd, shell=True, check=True, cwd=cwd, capture_output=True, text=True
            )
            print(f"✓ {cmd}")
            return result.stdout
        else:
            result = subprocess.run(cmd, shell=True, check=True, cwd=cwd)
            print(f"✓ {cmd}")
            return ""
    except subprocess.CalledProcessError as e:
        if isinstance(cmd, list):
            print(f"✗ {' '.join(cmd)}")
        else:
            print(f"✗ {cmd}")
        if capture and hasattr(e, "stderr") and e.stderr:
            print(f"Error: {e.stderr}")
        sys.exit(1)


def build_executable():
    """Build the standalone executable using Nuitka."""
    print("🔨 Building RC Driver executable...")

    # Check if Nuitka is installed
    try:
        subprocess.run(["python3", "-m", "nuitka", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Nuitka not found. Install with: pip3 install nuitka")
        sys.exit(1)

    # Check for ccache (speeds up C compilation significantly)
    try:
        subprocess.run(["ccache", "--version"], capture_output=True, check=True)
        print("✅ ccache detected - C compilation will be cached")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  ccache not found - install with 'sudo apt install ccache' for faster rebuilds")

    # Detect available resources - with high RAM, use all cores!
    cpu_count = os.cpu_count()
    jobs = cpu_count  # Use all available cores

    # Get available memory in GB
    with open("/proc/meminfo") as f:
        meminfo = f.read()
    mem_total_kb = int([line for line in meminfo.split("\n") if "MemTotal" in line][0].split()[1])
    mem_total_gb = round(mem_total_kb / 1024 / 1024, 1)

    print(f"🚀 High-performance build: Using all {jobs} CPU cores with {mem_total_gb}GB RAM")

    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("main.dist"):
        shutil.rmtree("main.dist")

    # Nuitka build command
    nuitka_cmd = [
        "python3",
        "-m",
        "nuitka",
        "--onefile",  # Single executable
        "--standalone",  # Include all dependencies
        "--assume-yes-for-downloads",  # Auto-accept downloads
        "--show-progress",  # Show detailed progress
        "--show-memory",  # Show memory usage
        "--verbose",  # Verbose output
        "--output-filename=rc-driver",  # Output name
        "--remove-output",  # Clean temporary files
        # High-performance build flags for 64GB RAM system
        "--lto=yes",  # Link time optimization
        f"--jobs={jobs}",  # Use ALL CPU cores
        "--clang",  # Use clang if available (often faster)
        # Aggressive optimization for high-end system
        "--assume-yes-for-downloads",  # Auto-accept downloads
        "--show-progress",  # Show detailed progress
        "--show-memory",  # Show memory usage (interesting with 64GB!)
        "--verbose",  # Verbose output
        # Optimization plugins (not caching, but helpful)
        "--enable-plugin=anti-bloat",  # Remove unused code more aggressively
        "--enable-plugin=implicit-imports",  # Better import detection
        # Enable caching optimizations
        # Note: ccache is automatically used if installed
        # Include data files and dependencies
        "--include-package=Futaba",
        "--include-package=usb",
        "--include-package=uinput",
        # Include config files and other data
        "--include-data-dir=src/Futaba/configs=Futaba/configs",
        "--include-data-dir=src/Futaba/calibrations=Futaba/calibrations",
        # Linux-specific optimizations
        # "--linux-onefile-icon=driver.ico",  # Optional: add icon if you have one
        # "--disable-console",                 # Remove if you need console output
        # Entry point
        "src/main.py",
    ]

    run_command(nuitka_cmd, capture=False)  # Don't capture output - show Nuitka progress

    # Make executable
    run_command("chmod +x rc-driver")

    print("✅ Build complete! Executable: rc-driver")
    print("📦 Size:", end=" ")
    run_command("ls -lh rc-driver | awk '{print $5}'")


if __name__ == "__main__":
    build_executable()
