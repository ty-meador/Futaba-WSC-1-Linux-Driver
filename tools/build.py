#!/usr/bin/env python3
"""Build script to create standalone executable for Futaba RC Driver."""

import os
import re
import shutil
import subprocess
import sys
from argparse import ArgumentParser

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
    runCommand,
)

# Refuse to run if we aren't operating in a venv
if sys.prefix == sys.base_prefix:
    if not (PROJECT_ROOT / ".venv").exists():
        print("Script must be run from a venv. Try the following first.")
        print(f"NOTE: Python version requirement -> {PYPROJECT['project']['requires-python']}")
        print("python3 -m venv venv")
    else:
        print(
            f"You appear to have a virtual environment setup in {PROJECT_ROOT / '.venv'} "
            "but it is not active. Try:"
        )
        print("`source .venv/bin/activate`")
    sys.exit(1)


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
        *findNativeLibraries(),
    ]

    try:
        runCommand(cmd, capture=False, shell=False)
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

    # Define the virtual environment path
    venvPath = PROJECT_ROOT / ".venv"

    if not venvPath.exists():
        raise OSError(f"❌ Virtual environment not found at: {venvPath}")

    # Find .so files in the virtual environment
    dependencyPatterns = [
        "*uinput*.so",
        *[
            f"*{re.split(r'(>=|==|~=)', dep)[0]}*.so"
            for dep in PYPROJECT["project"]["dependencies"]
        ],
    ]

    for pattern in dependencyPatterns:
        for libPath in venvPath.rglob(pattern):
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
    ) is None:
        sys.exit(1)


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
        {"build_dir": os.path.basename(BUILD_DIR), "executable_name": EXECUTABLE_NAME},
        WRAPPER_SCRIPT,
    )

    # Show stats
    result = runCommand(f"du -sh {BUILD_DIR}")
    if result:
        print(f"📦 Distribution size: {result.split()[0]}")


def testExecutable():
    """Test the built executable."""
    print("🧪 Testing executable...")
    if runCommand(f"{BUILD_DIR / EXECUTABLE_NAME} --version") is not None:
        print("✅ Executable test successful")
        return True
    print("⚠️  Executable may have issues")
    return False


def validateEnvironment():
    """Check that required tools are available."""
    print("🔍 Validating environment...")

    # Check Nuitka
    try:
        runCommand("python3 -m nuitka --version", capture=False)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Nuitka not found. Install with: pip3 install nuitka")
        sys.exit(1)

    # Check C compiler
    for compiler in ["gcc", "clang", "cc"]:
        try:
            runCommand(f"{compiler} --version", capture=False)
            print(f"✅ Found C compiler: {compiler}")
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    else:
        print("❌ No C compiler found! Install with: sudo apt install build-essential")
        sys.exit(1)


art = """
                                 Have                         ☁️
                                 Fun                             ☁️
                                 out    ✈️ 
                                 there!

...............................................................................


                                                                  🚤 🌊
____________________________________________________
                                                    \\
                                                     \\
                                             🚙___    \\
                                           🚗_____     \\
                                                        \\
                                                         \\
                                                          \\
                                                           \\
                                                            \\
                                                             \\
"""


if __name__ == "__main__":
    args = parser.parse_args()
    if args.clean:
        cleanBuildArtifacts()
    else:
        build()
