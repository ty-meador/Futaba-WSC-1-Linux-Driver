#!/usr/bin/env python3
"""Build script to create standalone executable for Futaba RC Driver."""

import os
import shutil
import sys
from argparse import ArgumentParser
from pathlib import Path
from subprocess import CalledProcessError

import util
from __config__ import (
    BUILD_DIR,
    DOCS_DIR,
    EXECUTABLE_NAME,
    INSTALL_DIR,
    NUITKA_OUTPUT_DIR,
    PROJECT_ROOT,
    PYPROJECT,
    SCRIPTS_TEMPLATES_DIR,
    SOURCE_MAIN,
    WRAPPER_SCRIPT,
)
from clean import cleanBuildArtifacts


def build() -> None:
    """Main entry point."""
    print("Futaba RC Driver Build Script")
    print("=" * 35)

    installDependencies()
    validateEnvironment()
    cleanBuildArtifacts()
    generateTypeStubs()

    execPath = buildExecutable()
    if not execPath:
        sys.exit(1)

    setupExecutable(execPath)

    if testExecutable():
        print("\nBuild completed successfully!")
        print(f"\nTo run: sudo ./{EXECUTABLE_NAME}")
    else:
        print("\nBuild completed but executable test failed")
        sys.exit(1)


def buildExecutable() -> Path | None:
    """Build the executable with Nuitka."""
    print("Building executable...")

    if not SOURCE_MAIN.exists():
        print(f"Error: Source file not found: {SOURCE_MAIN}")
        sys.exit(1)

    jobs = min(os.cpu_count() or 4, 12)

    cmd = [
        "python3",
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=anti-bloat",
        "--show-progress",
        f"--output-filename={EXECUTABLE_NAME}",
        "--remove-output",
        f"--jobs={jobs}",
        "--lto=yes",
        "--include-package=Futaba",
        "--include-package=hid_parser",
        "--include-package=usb",
        "--include-package=uinput",
        "--noinclude-default-mode=error",
        "--noinclude-setuptools-mode=nofollow",
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
        "--noinclude-data-files=*.log",
        "--follow-import-to=hid_parser",
        "--follow-import-to=uinput",
        "--follow-import-to=usb",
        "--follow-import-to=Futaba",
        "--include-package-data=Futaba",
        "--include-package-data=uinput",
        "--include-package-data=usb",
        "--include-data-files=pyproject.toml=pyproject.toml",
        "--report=compilation-report.xml",
        str(SOURCE_MAIN),
        *findNativeLibraries(),
    ]

    try:
        util.runCommand(cmd, capture=False, shell=False)
    except CalledProcessError:
        print("Error: Nuitka build failed")
        return None

    # Find the executable
    for execName in [EXECUTABLE_NAME, "main"]:
        execPath = NUITKA_OUTPUT_DIR / str(execName)
        if execPath.exists():
            return execPath

    print(f"Error: No executable found in {NUITKA_OUTPUT_DIR}")
    return None


def findNativeLibraries() -> list[str]:
    """Find native libraries to include."""
    print("Locating native libraries...")
    # Hard-coded because the package name is "python-uinput"
    nuitkaArgs = []

    # Define the virtual environment path
    venvPath = PROJECT_ROOT / ".venv"

    if not venvPath.exists():
        raise OSError(f"Error: Virtual environment not found at: {venvPath}")

    # Find .so files in the virtual environment
    dependencyPatterns = [
        *[
            f"*{dep}*.so"
            for dep in PYPROJECT["tool"]["build_tool"]["native_dependencies"]
        ]
    ]

    for pattern in dependencyPatterns:
        print(f"    {pattern}")
        for libPath in venvPath.rglob(pattern):
            print(f"        {libPath}")
            if libPath.is_file():
                nuitkaArgs.append(f"--include-data-files={libPath}={libPath.name}")
                print(f"Found library: {libPath.name}")

    return nuitkaArgs


def installDependencies() -> None:
    """Install build dependencies."""
    print("Installing dependencies...")
    if util.runCommand("pip3 install -e .") is None:
        sys.exit(1)


def setupExecutable(execPath: Path) -> None:
    """Set up the final executable distribution."""
    print("Setting up executable...")

    # Make executable
    execPath.chmod(0o755)

    # Move to final location
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)  # shutil
    shutil.move(str(execPath.parent), str(BUILD_DIR))  # shutil

    util.renderTemplate(
        SCRIPTS_TEMPLATES_DIR / "wrapper-script.sh",
        {
            "build_dir": os.path.basename(BUILD_DIR),
            "executable_name": EXECUTABLE_NAME,
            "install_dir": INSTALL_DIR,
        },
        WRAPPER_SCRIPT,
    )

    # Show stats
    result = util.runCommand(f"du -sh {BUILD_DIR}")
    if result:
        print(f"Distribution size: {result.split()[0]}")


def testExecutable() -> bool:
    """Test the built executable."""
    print("Testing executable...")
    if util.runCommand(f"{BUILD_DIR / EXECUTABLE_NAME} --version") is not None:
        print("Executable test successful")
        return True
    print("Warning: Executable may have issues")
    return False


def validateEnvironment() -> None:
    """Check that required tools are available."""
    print("Validating environment...")

    # Check Nuitka
    try:
        util.runCommand("python3 -m nuitka --version", capture=False)
    except (CalledProcessError, FileNotFoundError):
        print("Error: Nuitka not found. Install with: pip3 install nuitka")
        sys.exit(1)

    # Check C compiler
    for compiler in ["gcc", "clang", "cc"]:
        try:
            util.runCommand(f"{compiler} --version", capture=False)
            print(f"Found C compiler: {compiler}")
            break
        except (CalledProcessError, FileNotFoundError):
            continue
    else:
        print(
            "Error: No C compiler found! Install with: sudo apt install build-essential"
        )
        sys.exit(1)


def generateTypeStubs() -> None:
    """Generate python3 type stubs for the Futaba package

    Raises:
        RuntimeError: If the operation fails for any reason

    Returns:
        None:
    """
    try:
        util.runCommand("stubgen src/Futaba/ -o typings/")
    except Exception as e:
        raise RuntimeError("Failed to generate type stubs!")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean up previously generated artifacts before building new ones.",
    )
    parser.add_argument(
        "--docs",
        action="store_true",
        help="Generate sphinx documentation and store the output in docs/build",
    )
    parser.add_argument(
        "--type-stubs",
        action="store_true",
        help="Generate python3 type stubs and store them in typings/",
    )
    ARGS = parser.parse_args()

    if ARGS.clean:
        cleanBuildArtifacts()

    if ARGS.type_stubs:
        generateTypeStubs()
    else:
        build()
