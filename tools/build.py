#!./.venv/bin/python
"""Build script to create standalone executable for Futaba RC Driver."""

import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

from clean import cleanBuildArtifacts
from util import (
    BUILD_DIR,
    EXECUTABLE_NAME,
    NUITKA_OUTPUT_DIR,
    PROJECT_ROOT,
    PYPROJECT,
    SCRIPTS_TEMPLATES_DIR,
    SOURCE_MAIN,
    WRAPPER_SCRIPT,
    renderTemplate,
)

parser = ArgumentParser()
parser.add_argument("--clean", action="store_true")


def build():
    """Main entry point."""
    print("🎮 Futaba RC Driver Build Script")
    print("=" * 35)

    installDependencies()
    validateEnvironment()
    cleanBuildArtifacts()

    execPath = buildExecutable()
    if not execPath:
        sys.exit(1)

    setupExecutable(execPath)

    if testExecutable():
        print("\n🎉 Build completed successfully!")
        print(f"\n🚀 To run: sudo ./{EXECUTABLE_NAME}")
    else:
        print("\n❌ Build completed but executable test failed")
        sys.exit(1)


def buildExecutable():
    """Build the executable with Nuitka."""
    print("🔨 Building executable...")

    if not SOURCE_MAIN.exists():
        print(f"❌ Source file not found: {SOURCE_MAIN}")
        sys.exit(1)

    # Get native library args
    nativeLibArgs = findNativeLibraries()

    # Build Nuitka command
    import os

    jobs = min(os.cpu_count() or 4, 12)

    cmd = [
        "python3",
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--show-progress",
        f"--output-filename={EXECUTABLE_NAME}",
        "--remove-output",
        f"--jobs={jobs}",
        "--lto=yes",
        "--enable-plugin=anti-bloat",
        "--enable-plugin=implicit-imports",
        "--include-package=Futaba",
        "--include-package=usb",
        "--include-package=uinput",
        "--follow-import-to=uinput",
        "--follow-import-to=usb",
        "--follow-import-to=Futaba",
        "--include-package-data=Futaba",
        "--include-package-data=uinput",
        "--include-package-data=usb",
        "--include-data-files=pyproject.toml=pyproject.toml",
        str(SOURCE_MAIN),
    ]
    cmd.extend(nativeLibArgs)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print("❌ Nuitka build failed")
        return None

    # Find the executable
    for execName in [EXECUTABLE_NAME, "main"]:
        execPath = NUITKA_OUTPUT_DIR / execName
        if execPath.exists():
            return execPath

    print(f"❌ No executable found in {NUITKA_OUTPUT_DIR}")
    return None


def findNativeLibraries():
    """Find native libraries to include."""
    print("🔍 Locating native libraries...")

    nuitkaArgs = ["--include-package-data=uinput"]

    try:
        import uinput

        print(f"📍 uinput found at: {Path(uinput.__file__).parent}")
    except ImportError:
        print("❌ uinput not found")
        return nuitkaArgs

    # Find .so files in package paths
    for pathStr in sys.path:
        path = Path(pathStr)
        if "site-packages" in path.name or "dist-packages" in path.name:
            for pattern in ["*uinput*.so", "*usb*.so"]:
                for libPath in path.rglob(pattern):
                    if libPath.is_file():
                        nuitkaArgs.append(f"--include-data-files={libPath}={libPath.name}")
                        print(f"📚 Found library: {libPath.name}")

    return nuitkaArgs


def installDependencies():
    """Install build dependencies."""
    print("📦 Installing dependencies...")

    # Install build requirements
    buildDeps = [
        *PYPROJECT["build-system"]["requires"],
        *PYPROJECT["project"]["dependencies"],
    ]
    if runCommand(f"pip3 install {' '.join(buildDeps)}") is None:
        sys.exit(1)

    # Install project requirements if they exist
    if (PROJECT_ROOT / "requirements.txt").exists() and runCommand(
        "pip3 install -r requirements.txt"
    ):
        sys.exit(1)


def runCommand(
    cmd: str,
    cwd: str | None = None,
    capture: bool = True,
) -> str | None:
    """Run a command and handle errors."""
    try:
        if capture:
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                cwd=cwd,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd)
            return ""
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        if capture and e.stderr:
            print(f"Error: {e.stderr}")
        return None


def setupExecutable(execPath):
    """Set up the final executable distribution."""
    print("🔧 Setting up executable...")

    # Make executable
    execPath.chmod(0o755)

    # Move to final location
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    shutil.move(str(execPath.parent), str(BUILD_DIR))

    renderTemplate(
        SCRIPTS_TEMPLATES_DIR / "wrapper-script.sh",
        {"build_dir": BUILD_DIR, "executable_name": EXECUTABLE_NAME},
        WRAPPER_SCRIPT,
    )

    # Show stats
    result = runCommand(f"du -sh {BUILD_DIR}")
    if result:
        print(f"📦 Distribution size: {result.split()[0]}")


def testExecutable():
    """Test the built executable."""
    print("🧪 Testing executable...")
    execPath = BUILD_DIR / EXECUTABLE_NAME

    # Try --version first, then --help
    for arg in ["--version", "--help"]:
        if runCommand(f"{execPath} {arg}", capture=True) is not None:
            print("✅ Executable test successful")
            return True

    print("⚠️  Executable may have issues")
    return False


def validateEnvironment():
    """Check that required tools are available."""
    print("🔍 Validating environment...")

    # Check Nuitka
    try:
        subprocess.run(["python3", "-m", "nuitka", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Nuitka not found. Install with: pip3 install nuitka")
        sys.exit(1)

    # Check C compiler
    for compiler in ["gcc", "clang", "cc"]:
        try:
            subprocess.run([compiler, "--version"], capture_output=True, check=True)
            print(f"✅ Found C compiler: {compiler}")
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    else:
        print("❌ No C compiler found! Install with: sudo apt install build-essential")
        sys.exit(1)


if __name__ == "__main__":
    args = parser.parse_args()
    if args.clean:
        cleanBuildArtifacts()
    else:
        build()
