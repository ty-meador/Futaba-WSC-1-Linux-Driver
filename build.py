#!/usr/bin/env python3
"""Build script to create standalone executable."""

import glob
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
                return result.stdout.strip()
            else:
                result = subprocess.run(cmd, check=True, cwd=cwd)
                print(f"✓ {' '.join(cmd)}")
                return ""
        elif capture:
            result = subprocess.run(
                cmd, shell=True, check=True, cwd=cwd, capture_output=True, text=True
            )
            print(f"✓ {cmd}")
            return result.stdout.strip()
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
        return None


def find_native_libraries():
    """Find all native libraries that need to be included."""
    print("🔍 Locating native libraries...")

    nuitka_args = []

    try:
        # Find uinput library location
        import uinput

        uinput_file = uinput.__file__
        uinput_dir = os.path.dirname(uinput_file)
        print(f"📍 uinput module at: {uinput_dir}")

        # Search for all uinput-related native libraries in site-packages
        import sys

        for path in sys.path:
            if any(pkg in path for pkg in ["site-packages", "dist-packages"]):
                # Find all uinput related .so files
                patterns = [
                    os.path.join(path, "**", "*uinput*.so"),
                    os.path.join(path, "**", "_*uinput*.so"),
                    os.path.join(path, "**", "libsuinput*.so"),
                    os.path.join(path, "**", "_libsuinput*.so"),
                ]

                for pattern in patterns:
                    matches = glob.glob(pattern, recursive=True)
                    for match in matches:
                        if os.path.isfile(match):
                            filename = os.path.basename(match)
                            # Include the file directly in the root of the distribution
                            nuitka_args.append(f"--include-data-files={match}={filename}")
                            print(f"📚 Found native library: {filename}")

        # Also include the entire uinput package data
        nuitka_args.append("--include-package-data=uinput")

        # Find USB libraries too
        try:
            import usb

            usb_backend_path = None

            # Try to find libusb backend
            for path in sys.path:
                if any(pkg in path for pkg in ["site-packages", "dist-packages"]):
                    usb_patterns = [
                        os.path.join(path, "**", "*usb*.so"),
                        os.path.join(path, "**", "libusb*.so"),
                    ]
                    for pattern in usb_patterns:
                        matches = glob.glob(pattern, recursive=True)
                        for match in matches:
                            if os.path.isfile(match):
                                filename = os.path.basename(match)
                                nuitka_args.append(f"--include-data-files={match}={filename}")
                                print(f"📚 Found USB library: {filename}")
        except ImportError:
            print("⚠️  USB module not found")

    except ImportError:
        print("❌ uinput not found in current environment")
        return []

    return nuitka_args


def build_executable():
    """Build the standalone executable using Nuitka."""
    print("🔨 Building RC Driver executable...")

    # Check if Nuitka is installed
    try:
        subprocess.run(["python3", "-m", "nuitka", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Nuitka not found. Install with: pip3 install nuitka")
        sys.exit(1)

    # Check for C compiler
    compiler_found = False
    for compiler in ["gcc", "clang", "cc"]:
        try:
            subprocess.run([compiler, "--version"], capture_output=True, check=True)
            print(f"✅ Found C compiler: {compiler}")
            compiler_found = True
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    if not compiler_found:
        print("❌ No C compiler found! Install with:")
        print("   sudo apt install build-essential")
        print("   # or")
        print("   sudo apt install gcc")
        sys.exit(1)

    # Check for ccache
    try:
        subprocess.run(["ccache", "--version"], capture_output=True, check=True)
        print("✅ ccache detected - faster C compilation")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  ccache not found - install with 'sudo apt install ccache' for faster rebuilds")

    # Detect resources
    cpu_count = os.cpu_count() or 4
    jobs = min(cpu_count, 8)  # Cap at 8 to avoid memory issues
    print(f"🚀 Using {jobs} CPU cores")

    # Clean previous builds
    print("🧹 Cleaning previous builds...")
    dirs_to_clean = ["build", "main.dist", "rc-driver.dist", "main.build", "rc-driver.build"]
    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"  Removing {d}")
            shutil.rmtree(d)

    # Check if main.py exists
    if not os.path.exists("src/main.py"):
        print("❌ src/main.py not found!")
        print("📁 Current directory contents:")
        run_command("ls -la", capture=False)
        if os.path.exists("src"):
            print("📁 src/ directory contents:")
            run_command("ls -la src/", capture=False)
        sys.exit(1)

    # Find native libraries
    native_lib_args = find_native_libraries()

    # Optimized Nuitka build command for real-time performance
    nuitka_cmd = [
        "python3",
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
        "--verbose",
        "--output-filename=rc-driver",
        "--remove-output",
        f"--jobs={jobs}",
        # Performance optimizations
        "--lto=yes",  # Link-time optimization
        # Essential plugins
        "--enable-plugin=anti-bloat",
        "--enable-plugin=implicit-imports",
        # Package inclusion - be explicit about what we need
        "--include-package=Futaba",
        "--include-package=usb",
        "--include-package=uinput",
        # Follow imports for critical packages
        "--follow-import-to=uinput",
        "--follow-import-to=usb",
        "--follow-import-to=Futaba",
        # Include package data
        "--include-package-data=Futaba",
        "--include-package-data=uinput",
        "--include-package-data=usb",
        # Exclude unnecessary packages to keep size small
        "--nofollow-import-to=numpy.f2py",
        "--nofollow-import-to=numpy.distutils",
        "--nofollow-import-to=numpy.testing",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=scipy",
        "--nofollow-import-to=pandas",
        # Entry point
        "src/main.py",
    ]

    # Add native library inclusion arguments
    nuitka_cmd.extend(native_lib_args)

    print("🎯 Running optimized Nuitka build:")
    print(f"   Command: {' '.join(nuitka_cmd[:6])}... (truncated)")

    # Run the build command
    try:
        result = subprocess.run(nuitka_cmd, check=True)
        build_success = True
    except subprocess.CalledProcessError as e:
        print(f"❌ Nuitka build failed with exit code {e.returncode}")
        build_success = False

    # Find the output directory
    possible_dirs = ["rc-driver.dist", "main.dist"]
    output_dir = None
    executable_path = None

    for dir_name in possible_dirs:
        if os.path.exists(dir_name):
            output_dir = dir_name
            exec_path = os.path.join(dir_name, "rc-driver")
            if os.path.exists(exec_path):
                executable_path = exec_path
                break
            exec_path = os.path.join(dir_name, "main")
            if os.path.exists(exec_path):
                executable_path = exec_path
                break

    if not output_dir:
        print("❌ No output directory found!")
        return False

    if not executable_path:
        print(f"❌ No executable found in {output_dir}")
        return False

    print(f"✅ Build completed: {executable_path}")

    # Make executable
    run_command(f"chmod +x {executable_path}")

    # Verify native libraries are present
    print("\n🔍 Verifying native libraries...")
    so_files = glob.glob(os.path.join(output_dir, "*.so"))

    if so_files:
        print("✅ Native libraries found:")
        for so_file in so_files:
            filename = os.path.basename(so_file)
            file_size = os.path.getsize(so_file)
            print(f"  📚 {filename} ({file_size:,} bytes)")
    else:
        print("❌ No native libraries found in output!")

        # Try manual fix
        print("🔧 Attempting to manually copy missing libraries...")
        try:
            import sys

            for path in sys.path:
                if any(pkg in path for pkg in ["site-packages", "dist-packages"]):
                    for pattern in ["**/libsuinput*.so", "**/_libsuinput*.so", "**/uinput*.so"]:
                        matches = glob.glob(os.path.join(path, pattern), recursive=True)
                        for match in matches:
                            if os.path.isfile(match):
                                dest = os.path.join(output_dir, os.path.basename(match))
                                shutil.copy2(match, dest)
                                os.chmod(dest, 0o755)
                                print(f"🔧 Copied: {os.path.basename(match)}")
        except Exception as e:
            print(f"❌ Manual copy failed: {e}")

    # Create wrapper script in root directory
    wrapper_content = f"""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$SCRIPT_DIR/{output_dir}"
exec ./{"rc-driver" if "rc-driver" in executable_path else "main"} "$@"
"""

    with open("rc-driver", "w") as f:
        f.write(wrapper_content)
    os.chmod("rc-driver", 0o755)
    print("🔗 Created wrapper script: ./rc-driver")

    # Show build statistics
    print("\n📊 Build Statistics:")
    result = run_command(f"du -sh {output_dir}")
    if result:
        print(f"📦 Distribution size: {result.split()[0]}")

    file_count = len(
        [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]
    )
    print(f"📄 File count: {file_count}")

    # Test the executable
    print("\n🧪 Testing executable...")
    test_result = run_command(
        f"./{output_dir}/{'rc-driver' if 'rc-driver' in executable_path else 'main'} --version",
        capture=True,
    )
    if test_result is not None:
        print("✅ Executable test successful")
        return True
    else:
        print("⚠️  Executable test failed, trying --help...")
        test_result = run_command(
            f"./{output_dir}/{'rc-driver' if 'rc-driver' in executable_path else 'main'} --help",
            capture=True,
        )
        if test_result is not None:
            print("✅ Executable runs (--help works)")
            return True
        else:
            print("⚠️  Executable may have issues")
            return build_success


if __name__ == "__main__":
    print("🎮 RC Driver Build Script")
    print("=" * 30)

    success = build_executable()

    if success:
        print("\n🎉 Build completed successfully!")
        print("\n🚀 To run the driver:")
        print("   sudo ./rc-driver")
        print("\n📝 Note: sudo is required for uinput device access")
    else:
        print("\n❌ Build failed!")
        print("\n💡 Troubleshooting:")
        print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check that uinput kernel module is loaded: lsmod | grep uinput")
        print("3. Try a simpler build: python3 -m nuitka --standalone src/main.py")
        sys.exit(1)
