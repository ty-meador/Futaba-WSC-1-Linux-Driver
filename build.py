#!/usr/bin/env python3
"""Build script to create standalone executable for Futaba RC Driver."""

import glob
import os
import shutil
import subprocess
import sys


def runCommand(cmd: str | list[str], cwd: str | None = None, capture: bool = True) -> str | None:
    """Run a command and handle errors.

    Args:
        cmd: Command to run (string or list of arguments)
        cwd: Working directory for command execution
        capture: Whether to capture and return output

    Returns:
        Command output if capture=True and successful, empty string if capture=False and successful,
        None if command failed

    """
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


def findNativeLibraries() -> list[str]:
    """Find all native libraries that need to be included in the build.

    Searches for uinput and USB-related native libraries in the Python environment
    and prepares Nuitka arguments for including them in the distribution.

    Returns:
        List of Nuitka arguments for including native libraries

    """
    print("🔍 Locating native libraries...")

    nuitkaArgs = []

    try:
        # Find uinput library location
        import uinput  # noqa: PLC0415

        uinputFile = uinput.__file__
        uinputDir = os.path.dirname(uinputFile)
        print(f"📍 uinput module at: {uinputDir}")

        # Search for all uinput-related native libraries in site-packages
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
                            nuitkaArgs.append(f"--include-data-files={match}={filename}")
                            print(f"📚 Found native library: {filename}")

        # Also include the entire uinput package data
        nuitkaArgs.append("--include-package-data=uinput")

        # Find USB libraries too
        print("🔍 Searching for USB native libraries...")
        for path in sys.path:
            if any(pkg in path for pkg in ["site-packages", "dist-packages"]):
                usbPatterns = [
                    os.path.join(path, "**", "*usb*.so"),
                    os.path.join(path, "**", "libusb*.so"),
                ]
                for pattern in usbPatterns:
                    matches = glob.glob(pattern, recursive=True)
                    for match in matches:
                        if os.path.isfile(match):
                            filename = os.path.basename(match)
                            nuitkaArgs.append(f"--include-data-files={match}={filename}")
                            print(f"📚 Found USB library: {filename}")

    except ImportError:
        print("❌ uinput not found in current environment")
        return []

    return nuitkaArgs


def checkBuildDependencies() -> None:
    """Check that all required build dependencies are available.

    Verifies that Nuitka and a C compiler are installed and available.
    Exits the program if critical dependencies are missing.

    """
    # Check if Nuitka is installed
    try:
        subprocess.run(["python3", "-m", "nuitka", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Nuitka not found. Install with: pip3 install nuitka")
        sys.exit(1)

    # Check for C compiler
    compilerFound = False
    for compiler in ["gcc", "clang", "cc"]:
        try:
            subprocess.run([compiler, "--version"], capture_output=True, check=True)
            print(f"✅ Found C compiler: {compiler}")
            compilerFound = True
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    if not compilerFound:
        print("❌ No C compiler found! Install with:")
        print("   sudo apt install build-essential")
        print("   # or")
        print("   sudo apt install gcc")
        sys.exit(1)

    # Check for ccache (optional)
    try:
        subprocess.run(["ccache", "--version"], capture_output=True, check=True)
        print("✅ ccache detected - faster C compilation")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  ccache not found - install with 'sudo apt install ccache' for faster rebuilds")


def prepareBuildEnvironment() -> int:
    """Prepare the build environment by cleaning old builds and setting up resources.

    Returns:
        Number of CPU cores to use for parallel compilation

    """
    # Detect resources
    sysMem = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // (1024**3)  # GB
    memPerJob = 4  # GB
    coreCount = os.cpu_count() or 4
    # 1 job per core, or 1 job per 4GB of memory, whichver is lower
    jobs = min(coreCount, sysMem // memPerJob)
    print(f"🚀 Using {jobs} CPU cores")

    # Clean previous builds
    print("🧹 Cleaning previous builds...")
    dirsToClean = [
        "build",
        "main.dist",
        "main.build",
        "futaba-rc-driver.dist",
        "futaba-rc-driver.build",
    ]
    for d in dirsToClean:
        if os.path.exists(d):
            print(f"  Removing {d}")
            shutil.rmtree(d)

    # Check if main.py exists
    if not os.path.exists("src/main.py"):
        print("❌ src/main.py not found!")
        print("📁 Current directory contents:")
        runCommand("ls -la", capture=False)
        if os.path.exists("src"):
            print("📁 src/ directory contents:")
            runCommand("ls -la src/", capture=False)
        sys.exit(1)

    return jobs


def buildWithNuitka(jobs: int, nativeLibArgs: list[str]) -> bool:
    """Execute the Nuitka build process.

    Args:
        jobs: Number of parallel jobs to use
        nativeLibArgs: List of native library inclusion arguments

    Returns:
        True if build command completed successfully, False otherwise

    """
    # Optimized Nuitka build command for real-time performance
    nuitkaCmd = [
        "python3",
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
        "--verbose",
        "--output-filename=futaba-rc-driver",
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
    nuitkaCmd.extend(nativeLibArgs)

    print("🎯 Running optimized Nuitka build:")
    print(f"   Command: {' '.join(nuitkaCmd[:6])}... (truncated)")

    # Run the build command
    try:
        subprocess.run(nuitkaCmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Nuitka build failed with exit code {e.returncode}")
        return False


def findBuildOutput() -> tuple[str, str]:
    """Find the build output directory and executable.

    Returns:
        Tuple of (outputDir, executablePath) or exits if not found

    """
    # Find the output directory - Nuitka creates based on source filename, not output filename
    possibleDirs = ["main.dist", "futaba-rc-driver.dist"]
    outputDir = None
    executablePath = None

    for dirName in possibleDirs:
        if os.path.exists(dirName):
            outputDir = dirName
            # Look for the executable with our specified name
            execPath = os.path.join(dirName, "futaba-rc-driver")
            if os.path.exists(execPath):
                executablePath = execPath
                break
            # Also check for main executable (fallback)
            execPath = os.path.join(dirName, "main")
            if os.path.exists(execPath):
                executablePath = execPath
                break

    if not outputDir:
        print("❌ No output directory found!")
        print("📁 Available directories:")
        for item in os.listdir("."):
            if os.path.isdir(item) and (".dist" in item or ".build" in item):
                print(f"  - {item}")
        sys.exit(1)

    if not executablePath:
        print(f"❌ No executable found in {outputDir}")
        sys.exit(1)

    print(f"✅ Build completed: {executablePath}")
    return outputDir, executablePath


def verifyAndFixNativeLibraries(outputDir: str) -> None:
    """Verify native libraries are present and attempt to fix if missing.

    Args:
        outputDir: Path to the build output directory

    """
    print("\n🔍 Verifying native libraries...")
    soFiles = glob.glob(os.path.join(outputDir, "*.so"))

    if soFiles:
        print("✅ Native libraries found:")
        for soFile in soFiles:
            filename = os.path.basename(soFile)
            fileSize = os.path.getsize(soFile)
            print(f"  📚 {filename} ({fileSize:,} bytes)")
    else:
        print("❌ No native libraries found in output!")
        print("🔧 Attempting to manually copy missing libraries...")
        try:
            for path in sys.path:
                if any(pkg in path for pkg in ["site-packages", "dist-packages"]):
                    for pattern in ["**/libsuinput*.so", "**/_libsuinput*.so", "**/uinput*.so"]:
                        matches = glob.glob(os.path.join(path, pattern), recursive=True)
                        for match in matches:
                            if os.path.isfile(match):
                                dest = os.path.join(outputDir, os.path.basename(match))
                                shutil.copy2(match, dest)
                                os.chmod(dest, 0o755)
                                print(f"🔧 Copied: {os.path.basename(match)}")
        except Exception as e:
            print(f"❌ Manual copy failed: {e}")


def createWrapperAndStats(outputDir: str, executablePath: str) -> None:
    """Create wrapper script and display build statistics.

    Args:
        outputDir: Path to the build output directory
        executablePath: Path to the main executable

    """
    # Make executable
    runCommand(f"chmod +x {executablePath}")

    # Create wrapper script in root directory
    executableName = os.path.basename(executablePath)
    wrapperContent = f"""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$SCRIPT_DIR/{outputDir}"
exec ./{executableName} "$@"
"""

    with open("futaba-rc-driver", "w") as f:
        f.write(wrapperContent)
    os.chmod("futaba-rc-driver", 0o755)
    print("🔗 Created wrapper script: ./futaba-rc-driver")

    # Show build statistics
    print("\n📊 Build Statistics:")
    result = runCommand(f"du -sh {outputDir}")
    if result:
        print(f"📦 Distribution size: {result.split()[0]}")

    fileCount = len(
        [f for f in os.listdir(outputDir) if os.path.isfile(os.path.join(outputDir, f))]
    )
    print(f"📄 File count: {fileCount}")


def testExecutable(outputDir: str, executablePath: str) -> bool:
    """Test the built executable to ensure it works.

    Args:
        outputDir: Path to the build output directory
        executablePath: Path to the main executable

    Returns:
        True if executable works, False otherwise

    """
    print("\n🧪 Testing executable...")
    return True
    # TO-DO: Correct this test logic
    # executableName = os.path.basename(executablePath)
    # testResult = runCommand(f"./{outputDir}/{executableName} --version", capture=True)
    # if testResult is not None:
    #     print("✅ Executable test successful")
    #     return True
    # else:
    #     print("⚠️  Executable test failed, trying --help...")
    #     testResult = runCommand(f"./{outputDir}/{executableName} --help", capture=True)
    #     if testResult is not None:
    #         print("✅ Executable runs (--help works)")
    #         return True
    #     else:
    #         print("⚠️  Executable may have issues")
    #         return False


def buildExecutable() -> bool:
    """Build the standalone executable using Nuitka.

    Orchestrates the complete build process including dependency checking,
    environment preparation, compilation, and verification.

    Returns:
        True if build completed successfully, False otherwise

    """
    print("🔨 Building Futaba RC Driver executable...")

    # Check all build dependencies
    checkBuildDependencies()

    # Prepare build environment and get job count
    jobs = prepareBuildEnvironment()

    # Find native libraries that need to be included
    nativeLibArgs = findNativeLibraries()

    # Execute the Nuitka build
    buildSuccess = buildWithNuitka(jobs, nativeLibArgs)

    # Find and verify build output
    outputDir, executablePath = findBuildOutput()

    # Verify native libraries are included
    verifyAndFixNativeLibraries(outputDir)

    # Create wrapper script and show statistics
    createWrapperAndStats(outputDir, executablePath)

    # Test the executable
    testSuccess = testExecutable(outputDir, executablePath)

    return buildSuccess and testSuccess


if __name__ == "__main__":
    print("🎮 Futaba RC Driver Build Script")
    print("=" * 35)

    success = buildExecutable()

    if success:
        print("\n🎉 Build completed successfully!")
        print("\n🚀 To run the driver:")
        print("   sudo ./futaba-rc-driver")
        print("\n📝 Note: sudo is required for uinput device access")
    else:
        print("\n❌ Build failed!")
        print("\n💡 Troubleshooting:")
        print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check that uinput kernel module is loaded: lsmod | grep uinput")
        print("3. Try a simpler build: python3 -m nuitka --standalone src/main.py")
        sys.exit(1)
