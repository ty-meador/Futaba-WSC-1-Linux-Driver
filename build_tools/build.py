#!/usr/bin/env python3
"""Build script to create standalone executable for Futaba RC Driver."""

import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path

# Path constants using pathlib
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

# Load pyproject.toml
with PYPROJECT_PATH.open("rb") as f:
    toml_data = tomllib.load(f)
PYPROJECT = toml_data

# Build configuration paths
BUILD_DIR = PROJECT_ROOT / PYPROJECT["tool"]["build_tool"]["build_dir"]
EXECUTABLE_NAME = PYPROJECT["tool"]["build_tool"]["executable_name"]
INSTALL_DIR = Path(PYPROJECT["tool"]["build_tool"]["install_dir"]).resolve()
INSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["install_script_name"]
PACKAGE_DIR = PROJECT_ROOT / PYPROJECT["tool"]["build_tool"]["package_dir"]
UNINSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["uninstall_script_name"]
WEB_INSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["web_install_script_name"]


def runCommand(
    cmd: str | list[str],
    cwd: Path | None = None,
    capture: bool = True,
) -> str | None:
    """Run a command and handle errors.

    Args:
        cmd: Command to run (string or list of arguments)
        cwd: Working directory for command execution
        capture: Whether to capture and return output

    Returns:
        Command output if capture=True and successful, empty string if capture=False and successful,
        None if command failed
    """
    # Prepare command display string and subprocess arguments
    cmdStr = " ".join(cmd) if isinstance(cmd, list) else cmd

    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=cwd,
            shell=isinstance(cmd, str),
            capture_output=capture,
            text=capture,
        )
        print(f"✓ {cmdStr}")
        return result.stdout.strip() if capture else ""

    except subprocess.CalledProcessError as e:
        print(f"✗ {cmdStr}")
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

    try:
        import uinput  # noqa: PLC0415

        print(f"📍 uinput module at: {Path(uinput.__file__).parent}")
    except ImportError:
        print("❌ uinput not found in current environment")
        return []

    nuitka_args = ["--include-package-data=uinput"]

    # Library search patterns
    library_patterns = {
        "uinput": ["*uinput*.so", "_*uinput*.so", "libsuinput*.so", "_libsuinput*.so"],
        "usb": ["*usb*.so", "libusb*.so"],
    }

    for lib_type, patterns in library_patterns.items():
        found_libraries = _find_libraries_by_patterns(patterns)

        for lib_path in found_libraries:
            filename = lib_path.name
            nuitka_args.append(f"--include-data-files={lib_path}={filename}")

            emoji = "📚" if lib_type == "uinput" else "🔌"
            print(f"{emoji} Found {lib_type} library: {filename}")

    return nuitka_args


def _get_package_paths() -> Iterator[Path]:
    """Get all package installation paths from sys.path."""
    for path_str in sys.path:
        path = Path(path_str)
        if any(pkg in path.name for pkg in ["site-packages", "dist-packages"]):
            yield path


def _find_libraries_by_patterns(patterns: list[str]) -> Iterator[Path]:
    """Find all library files matching the given patterns in package paths."""
    for package_path in _get_package_paths():
        for pattern in patterns:
            for lib_path in package_path.rglob(pattern):
                if lib_path.is_file():
                    yield lib_path


class BuildError(Exception):
    """Custom exception for build-related errors."""

    pass


def buildExecutable() -> bool:  # noqa: C901, PLR0912, PLR0915
    """Build the standalone executable using Nuitka.

    Compiles the Python application into a standalone executable with all
    dependencies included. Optimizes for real-time performance and minimal size.

    Returns:
        True if build completed successfully, False otherwise

    """
    print("🔨 Building Futaba RC Driver executable...")

    try:
        _validateEnvironment()
        _cleanPreviousBuilds()
        _validateSource()

        nativeLibArgs = findNativeLibraries()
        nuitkaCmd = _buildNuitkaCommand(nativeLibArgs)

        executablePath = _runBuild(nuitkaCmd)
        if not executablePath:
            return False

        _setupExecutable(executablePath)
        return _testExecutable()

    except BuildError as e:
        print(f"❌ {e}")
        return False


def _validateEnvironment() -> None:
    """Validate that all required tools are available."""
    # Check if Nuitka is installed
    try:
        subprocess.run(["python3", "-m", "nuitka", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise BuildError("Nuitka not found. Install with: pip3 install nuitka") from e

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

    # Check for ccache
    try:
        subprocess.run(["ccache", "--version"], capture_output=True, check=True)
        print("✅ ccache detected - faster C compilation")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  ccache not found - install with 'sudo apt install ccache' for faster rebuilds")


def _cleanPreviousBuilds() -> None:
    """Remove previous build artifacts."""
    print("🧹 Cleaning previous builds...")
    dirsToClean = [
        Path("build"),
        Path("main.dist"),
        Path("main.build"),
        Path(f"{EXECUTABLE_NAME}.dist"),
        Path(f"{EXECUTABLE_NAME}.build"),
        BUILD_DIR,
    ]
    for dir_path in dirsToClean:
        if dir_path.exists():
            print(f"  Removing {dir_path}")
            import shutil

            shutil.rmtree(dir_path)


def _validateSource() -> None:
    """Verify source file exists."""
    source_path = PROJECT_ROOT / "src" / "main.py"
    if not source_path.exists():
        print("❌ src/main.py not found!")
        print("📁 Current directory contents:")
        runCommand("ls -la", capture=False)
        src_dir = Path("src")
        if src_dir.exists():
            print("📁 src/ directory contents:")
            runCommand("ls -la src/", capture=False)
        sys.exit(1)


def _buildNuitkaCommand(nativeLibArgs) -> list:
    """Build the Nuitka command with all necessary arguments."""
    import os

    cpuCount = os.cpu_count() or 4
    jobs = min(cpuCount, 12)
    print(f"🚀 Using {jobs} CPU cores")

    source_main = PROJECT_ROOT / "src" / "main.py"

    nuitkaCmd = [
        "python3",
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
        f"--output-filename={EXECUTABLE_NAME}",
        "--remove-output",
        f"--jobs={jobs}",
        # Performance optimizations
        "--lto=yes",
        # Essential plugins
        "--enable-plugin=anti-bloat",
        "--enable-plugin=implicit-imports",
        # Package inclusion
        "--include-package=Futaba",
        "--include-package=usb",
        "--include-package=uinput",
        "--follow-import-to=uinput",
        "--follow-import-to=usb",
        "--follow-import-to=Futaba",
        "--include-package-data=Futaba",
        "--include-package-data=uinput",
        "--include-package-data=usb",
        str(source_main),
    ]
    nuitkaCmd.extend(nativeLibArgs)
    return nuitkaCmd


def _runBuild(nuitkaCmd) -> Path | None:
    """Execute the Nuitka build command and find the executable."""
    print("🎯 Running optimized Nuitka build:")
    print(f"   Command: {' '.join(nuitkaCmd[:6])}... (truncated)")

    try:
        subprocess.run(nuitkaCmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Nuitka build failed with exit code {e.returncode}")
        return None

    # Find executable
    nuitka_output_dir = Path("main.dist")
    if not nuitka_output_dir.exists():
        print(f"❌ No build output directory found: {nuitka_output_dir}")
        return None

    # Try specified name first, then fallback to 'main'
    for execName in [EXECUTABLE_NAME, "main"]:
        exec_path = nuitka_output_dir / execName
        if exec_path.exists():
            print(f"✅ Build completed: {exec_path}")
            return exec_path

    print(f"❌ No executable found in {nuitka_output_dir}")
    return None


def _setupExecutable(executablePath: Path) -> None:
    """Set up the executable distribution."""
    import shutil

    # Make executable
    runCommand(f"chmod +x {executablePath}")

    # Verify native libraries
    output_dir = executablePath.parent
    _verifyNativeLibraries(output_dir)

    # Move build and create wrapper
    shutil.move(str(output_dir), str(BUILD_DIR))
    _createWrapperScript()
    _showBuildStatistics()


def _verifyNativeLibraries(outputDir: Path) -> None:
    """Verify that native libraries are present."""
    print("\n🔍 Verifying native libraries...")
    so_files = list(outputDir.glob("*.so"))

    if so_files:
        print("✅ Native libraries found:")
        for so_file in so_files:
            file_size = so_file.stat().st_size
            print(f"  📚 {so_file.name} ({file_size:,} bytes)")
    else:
        print("❌ No native libraries found in output!")
        # Try manual fix
        print("🔧 Attempting to manually copy missing libraries...")
        try:
            for path_str in sys.path:
                path = Path(path_str)
                if any(pkg in path.name for pkg in ["site-packages", "dist-packages"]):
                    for pattern in ["**/libsuinput*.so", "**/_libsuinput*.so", "**/uinput*.so"]:
                        for match in path.rglob(pattern[3:]):  # Remove **/ prefix for rglob
                            if match.is_file():
                                dest = outputDir / match.name
                                import shutil

                                shutil.copy2(match, dest)
                                dest.chmod(0o755)
                                print(f"🔧 Copied: {match.name}")
        except Exception as e:
            print(f"❌ Manual copy failed: {e}")


def _createWrapperScript() -> None:
    """Create wrapper script in root directory."""
    wrapper_path = Path(EXECUTABLE_NAME)
    wrapper_content = f"""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$SCRIPT_DIR/{BUILD_DIR.name}"
exec ./{EXECUTABLE_NAME} "$@"
"""
    wrapper_path.write_text(wrapper_content)
    wrapper_path.chmod(0o755)
    print(f"🔗 Created wrapper script: ./{EXECUTABLE_NAME}")


def _showBuildStatistics() -> None:
    """Display build statistics."""
    print("\n📊 Build Statistics:")
    result = runCommand(f"du -sh {BUILD_DIR}")
    if result:
        print(f"📦 Distribution size: {result.split()[0]}")

    file_count = len([f for f in BUILD_DIR.iterdir() if f.is_file()])
    print(f"📄 File count: {file_count}")


def _testExecutable() -> bool:
    """Test the built executable."""
    print("\n🧪 Testing executable...")
    executable_path = BUILD_DIR / EXECUTABLE_NAME

    testResult = runCommand(f"{executable_path} --version", capture=True)
    if testResult is not None:
        print("✅ Executable test successful")
        return True
    else:
        print("⚠️  Executable test failed, trying --help...")
        testResult = runCommand(f"{executable_path} --help", capture=True)
        if testResult is not None:
            print("✅ Executable runs (--help works)")
            return True
        else:
            print("⚠️  Executable may have issues")
            return False


def installBuildDependencies() -> None:
    """Install the packages necessary to build the executable."""
    buildDependencies = PYPROJECT["build-system"]["requires"]
    runCommand(f"pip3 install {' '.join(buildDependencies)}")
    runCommand("pip3 install -r requirements.txt")


if __name__ == "__main__":
    print("🎮 Futaba RC Driver Build Script")
    print("=" * 35)

    installBuildDependencies()
    success = buildExecutable()

    if success:
        print("\n🎉 Build completed successfully!")
        print("\n🚀 To run the driver:")
        print(f"   sudo ./{EXECUTABLE_NAME}")
        print("\n📝 Note: sudo is required for uinput device access")
    else:
        print("\n❌ Build failed!")
        print("\n💡 Troubleshooting:")
        print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check that uinput kernel module is loaded: lsmod | grep uinput")
        print("3. Try a simpler build: python3 -m nuitka --standalone src/main.py")
        sys.exit(1)
