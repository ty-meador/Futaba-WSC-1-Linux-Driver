#!/usr/bin/env python3
"""Build script to create standalone executable for Futaba RC Driver."""

import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class BuildPaths:
    """Centralized path management for the build process."""

    def __init__(self, scriptPath: Path):
        self.scriptDir = scriptPath.resolve().parent
        self.projectRoot = self.scriptDir.parent
        self.pyprojectPath = self.projectRoot / "pyproject.toml"

        # Load configuration
        self._config = self._loadConfig()

        # Build paths from config
        self.buildDir = self.projectRoot / self._config["tool"]["build_tool"]["build_dir"]
        self.executableName = self._config["tool"]["build_tool"]["executable_name"]
        self.installDir = Path(self._config["tool"]["build_tool"]["install_dir"]).resolve()
        self.installScriptName = self._config["tool"]["build_tool"]["install_script_name"]
        self.packageDir = self.projectRoot / self._config["tool"]["build_tool"]["package_dir"]
        self.uninstallScriptName = self._config["tool"]["build_tool"]["uninstall_script_name"]
        self.webInstallScriptName = self._config["tool"]["build_tool"]["web_install_script_name"]

        # Source paths
        self.sourceMain = self.projectRoot / "src" / "main.py"
        self.nuitkaOutputDir = Path("main.dist")
        self.wrapperScript = Path(self.executableName)

    def _loadConfig(self) -> dict[str, Any]:
        """Load pyproject.toml configuration."""
        with self.pyprojectPath.open("rb") as f:
            return tomllib.load(f)

    @property
    def config(self) -> dict[str, Any]:
        """Get the loaded configuration."""
        return self._config

    def getCleanTargets(self) -> list[Path]:
        """Get list of paths to clean during build."""
        return [
            Path("build"),
            Path("main.dist"),
            Path("main.build"),
            Path(f"{self.executableName}.dist"),
            Path(f"{self.executableName}.build"),
            self.buildDir,
        ]


class CommandRunner:
    """Utility for running shell commands with consistent error handling."""

    @staticmethod
    def run(
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


class EnvironmentValidator:
    """Validates the build environment for required tools."""

    def __init__(self, cmdRunner: CommandRunner):
        self.cmdRunner = cmdRunner

    def validate(self) -> None:
        """Validate that all required tools are available."""
        self._checkNuitka()
        self._checkCCompiler()
        self._checkCcache()

    def _checkNuitka(self) -> None:
        """Check if Nuitka is installed."""
        try:
            subprocess.run(
                ["python3", "-m", "nuitka", "--version"], capture_output=True, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise BuildError("Nuitka not found. Install with: pip3 install nuitka") from e

    def _checkCCompiler(self) -> None:
        """Check for C compiler availability."""
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

    def _checkCcache(self) -> None:
        """Check for ccache (optional optimization)."""
        try:
            subprocess.run(["ccache", "--version"], capture_output=True, check=True)
            print("✅ ccache detected - faster C compilation")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                "⚠️  ccache not found - install with 'sudo apt install ccache' for faster rebuilds"
            )


class LibraryFinder:
    """Finds and manages native libraries for inclusion in the build."""

    def findNativeLibraries(self) -> list[str]:
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

        nuitkaArgs = ["--include-package-data=uinput"]

        # Library search patterns
        libraryPatterns = {
            "uinput": ["*uinput*.so", "_*uinput*.so", "libsuinput*.so", "_libsuinput*.so"],
            "usb": ["*usb*.so", "libusb*.so"],
        }

        for libType, patterns in libraryPatterns.items():
            foundLibraries = self._findLibrariesByPatterns(patterns)

            for libPath in foundLibraries:
                filename = libPath.name
                nuitkaArgs.append(f"--include-data-files={libPath}={filename}")

                emoji = "📚" if libType == "uinput" else "🔌"
                print(f"{emoji} Found {libType} library: {filename}")

        return nuitkaArgs

    def _getPackagePaths(self) -> Iterator[Path]:
        """Get all package installation paths from sys.path."""
        for pathStr in sys.path:
            path = Path(pathStr)
            if any(pkg in path.name for pkg in ["site-packages", "dist-packages"]):
                yield path

    def _findLibrariesByPatterns(self, patterns: list[str]) -> Iterator[Path]:
        """Find all library files matching the given patterns in package paths."""
        for packagePath in self._getPackagePaths():
            for pattern in patterns:
                for libPath in packagePath.rglob(pattern):
                    if libPath.is_file():
                        yield libPath

    def verifyNativeLibraries(self, outputDir: Path) -> None:
        """Verify that native libraries are present in the output directory."""
        print("\n🔍 Verifying native libraries...")
        soFiles = list(outputDir.glob("*.so"))

        if soFiles:
            print("✅ Native libraries found:")
            for soFile in soFiles:
                fileSize = soFile.stat().st_size
                print(f"  📚 {soFile.name} ({fileSize:,} bytes)")
        else:
            print("❌ No native libraries found in output!")
            self._manualCopyLibraries(outputDir)

    def _manualCopyLibraries(self, outputDir: Path) -> None:
        """Attempt to manually copy missing libraries."""
        print("🔧 Attempting to manually copy missing libraries...")
        try:
            for pathStr in sys.path:
                path = Path(pathStr)
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


class NuitkaBuilder:
    """Handles the Nuitka build process and configuration."""

    def __init__(self, paths: BuildPaths, cmdRunner: CommandRunner, libFinder: LibraryFinder):
        self.paths = paths
        self.cmdRunner = cmdRunner
        self.libFinder = libFinder

    def build(self) -> Path | None:
        """Execute the Nuitka build command and find the executable."""
        nativeLibArgs = self.libFinder.findNativeLibraries()
        nuitkaCmd = self._buildCommand(nativeLibArgs)

        print("🎯 Running optimized Nuitka build:")
        print(f"   Command: {' '.join(nuitkaCmd[:6])}... (truncated)")

        try:
            subprocess.run(nuitkaCmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Nuitka build failed with exit code {e.returncode}")
            return None

        return self._findExecutable()

    def _buildCommand(self, nativeLibArgs: list[str]) -> list[str]:
        """Build the Nuitka command with all necessary arguments."""
        import os

        cpuCount = os.cpu_count() or 4
        jobs = min(cpuCount, 12)
        print(f"🚀 Using {jobs} CPU cores")

        nuitkaCmd = [
            "python3",
            "-m",
            "nuitka",
            "--standalone",
            "--assume-yes-for-downloads",
            "--show-progress",
            "--show-memory",
            f"--output-filename={self.paths.executableName}",
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
            str(self.paths.sourceMain),
        ]
        nuitkaCmd.extend(nativeLibArgs)
        return nuitkaCmd

    def _findExecutable(self) -> Path | None:
        """Find the built executable in the output directory."""
        if not self.paths.nuitkaOutputDir.exists():
            print(f"❌ No build output directory found: {self.paths.nuitkaOutputDir}")
            return None

        # Try specified name first, then fallback to 'main'
        for execName in [self.paths.executableName, "main"]:
            execPath = self.paths.nuitkaOutputDir / execName
            if execPath.exists():
                print(f"✅ Build completed: {execPath}")
                return execPath

        print(f"❌ No executable found in {self.paths.nuitkaOutputDir}")
        return None


class BuildCleaner:
    """Handles cleaning of build artifacts."""

    def __init__(self, paths: BuildPaths):
        self.paths = paths

    def clean(self) -> None:
        """Remove previous build artifacts."""
        print("🧹 Cleaning previous builds...")
        import shutil

        for dirPath in self.paths.getCleanTargets():
            if dirPath.exists():
                print(f"  Removing {dirPath}")
                shutil.rmtree(dirPath)


class ExecutableManager:
    """Manages executable setup, testing, and statistics."""

    def __init__(self, paths: BuildPaths, cmdRunner: CommandRunner, libFinder: LibraryFinder):
        self.paths = paths
        self.cmdRunner = cmdRunner
        self.libFinder = libFinder

    def setupExecutable(self, executablePath: Path) -> None:
        """Set up the executable distribution."""
        import shutil

        # Make executable
        self.cmdRunner.run(f"chmod +x {executablePath}")

        # Verify native libraries
        outputDir = executablePath.parent
        self.libFinder.verifyNativeLibraries(outputDir)

        # Move build and create wrapper
        shutil.move(str(outputDir), str(self.paths.buildDir))
        self._createWrapperScript()
        self._showBuildStatistics()

    def testExecutable(self) -> bool:
        """Test the built executable."""
        print("\n🧪 Testing executable...")
        executablePath = self.paths.buildDir / self.paths.executableName

        testResult = self.cmdRunner.run(f"{executablePath} --version", capture=True)
        if testResult is not None:
            print("✅ Executable test successful")
            return True
        else:
            print("⚠️  Executable test failed, trying --help...")
            testResult = self.cmdRunner.run(f"{executablePath} --help", capture=True)
            if testResult is not None:
                print("✅ Executable runs (--help works)")
                return True
            else:
                print("⚠️  Executable may have issues")
                return False

    def _createWrapperScript(self) -> None:
        """Create wrapper script in root directory."""
        wrapperContent = f"""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$SCRIPT_DIR/{self.paths.buildDir.name}"
exec ./{self.paths.executableName} "$@"
"""
        self.paths.wrapperScript.write_text(wrapperContent)
        self.paths.wrapperScript.chmod(0o755)
        print(f"🔗 Created wrapper script: ./{self.paths.executableName}")

    def _showBuildStatistics(self) -> None:
        """Display build statistics."""
        print("\n📊 Build Statistics:")
        result = self.cmdRunner.run(f"du -sh {self.paths.buildDir}")
        if result:
            print(f"📦 Distribution size: {result.split()[0]}")

        fileCount = len([f for f in self.paths.buildDir.iterdir() if f.is_file()])
        print(f"📄 File count: {fileCount}")


class DependencyInstaller:
    """Handles installation of build dependencies."""

    def __init__(self, paths: BuildPaths, cmdRunner: CommandRunner):
        self.paths = paths
        self.cmdRunner = cmdRunner

    def installBuildDependencies(self) -> None:
        """Install the packages necessary to build the executable."""
        buildDependencies = self.paths.config["build-system"]["requires"]
        self.cmdRunner.run(f"pip3 install {' '.join(buildDependencies)}")
        self.cmdRunner.run("pip3 install -r requirements.txt")


class BuildError(Exception):
    """Custom exception for build-related errors."""

    pass


class BuildOrchestrator:
    """Main orchestrator for the build process."""

    def __init__(self):
        self.paths = BuildPaths(Path(__file__))
        self.cmdRunner = CommandRunner()
        self.envValidator = EnvironmentValidator(self.cmdRunner)
        self.libFinder = LibraryFinder()
        self.nuitkaBuilder = NuitkaBuilder(self.paths, self.cmdRunner, self.libFinder)
        self.buildCleaner = BuildCleaner(self.paths)
        self.executableManager = ExecutableManager(self.paths, self.cmdRunner, self.libFinder)
        self.dependencyInstaller = DependencyInstaller(self.paths, self.cmdRunner)

    def buildExecutable(self) -> bool:
        """Build the standalone executable using Nuitka.

        Compiles the Python application into a standalone executable with all
        dependencies included. Optimizes for real-time performance and minimal size.

        Returns:
            True if build completed successfully, False otherwise
        """
        print("🔨 Building Futaba RC Driver executable...")

        try:
            self.envValidator.validate()
            self.buildCleaner.clean()
            self._validateSource()

            executablePath = self.nuitkaBuilder.build()
            if not executablePath:
                return False

            self.executableManager.setupExecutable(executablePath)
            return self.executableManager.testExecutable()

        except BuildError as e:
            print(f"❌ {e}")
            return False

    def _validateSource(self) -> None:
        """Verify source file exists."""
        if not self.paths.sourceMain.exists():
            print("❌ src/main.py not found!")
            print("📁 Current directory contents:")
            self.cmdRunner.run("ls -la", capture=False)
            srcDir = Path("src")
            if srcDir.exists():
                print("📁 src/ directory contents:")
                self.cmdRunner.run("ls -la src/", capture=False)
            sys.exit(1)


def main() -> None:
    """Main entry point for the build script."""
    print("🎮 Futaba RC Driver Build Script")
    print("=" * 35)

    orchestrator = BuildOrchestrator()
    orchestrator.dependencyInstaller.installBuildDependencies()
    success = orchestrator.buildExecutable()

    if success:
        print("\n🎉 Build completed successfully!")
        print("\n🚀 To run the driver:")
        print(f"   sudo ./{orchestrator.paths.executableName}")
        print("\n📝 Note: sudo is required for uinput device access")
    else:
        print("\n❌ Build failed!")
        print("\n💡 Troubleshooting:")
        print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check that uinput kernel module is loaded: lsmod | grep uinput")
        print("3. Try a simpler build: python3 -m nuitka --standalone src/main.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
