#!/usr/bin/env python3
"""Package Futaba RC Driver into a standalone distribution."""

import os
import shutil
import subprocess
import tarfile
import tomllib
from datetime import datetime

with open("pyproject.toml", "rb") as f:
    """Load pyproject.toml file."""
    toml_data = tomllib.load(f)
PYPROJECT = toml_data

BUILD_DIR = PYPROJECT["tool"]["build_tool"]["build_dir"]
EXECUTABLE_NAME = PYPROJECT["tool"]["build_tool"]["executable_name"]
PACKAGE_DIR = PYPROJECT["tool"]["build_tool"]["package_dir"]
INSTALL_DIR = PYPROJECT["tool"]["build_tool"]["install_dir"]
BIN_DIR = PYPROJECT["tool"]["build_tool"]["bin_dir"]
SERVICE_DIR = PYPROJECT["tool"]["build_tool"]["service_dir"]
REPOSITORY = PYPROJECT["project"]["urls"]["Repository"]
VERSION = PYPROJECT["project"]["version"]
INSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["install_script_name"]
UNINSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["uninstall_script_name"]
WEB_INSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["web_install_script_name"]
REPO = PYPROJECT["project"]["urls"]["Repository"]
HOMEPAGE = PYPROJECT["project"]["urls"]["Homepage"]


def runCommand(cmd: str, cwd: str | None = None, capture: bool = True) -> str | None:
    """Run a command and handle errors.

    Args:
        cmd: Command to run as shell string
        cwd: Working directory for command execution
        capture: Whether to capture and return output

    Returns:
        Command output if capture=True and successful, empty string if capture=False and successful,
        None if command failed

    """
    try:
        if capture:
            result = subprocess.run(
                cmd, shell=True, check=True, cwd=cwd, capture_output=True, text=True
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


def getVersionInfo() -> tuple[str, str]:
    """Extract version and build info from git and current timestamp.

    Attempts to get version information from git tags, falls back to default
    version if git is not available or no tags exist.

    Returns:
        Tuple containing (version, buildDate) strings

    """
    version = "1.0.0"  # Default version

    # Try to get version from git
    gitVersion = runCommand("git describe --tags --always --dirty 2>/dev/null")
    if gitVersion:
        version = gitVersion

    buildDate = datetime.now().strftime("%Y%m%d_%H%M%S")
    return version, buildDate


def renderReadme() -> str:
    """Create a comprehensive README for the distribution.

    Generates complete documentation including installation instructions,
    usage examples, troubleshooting guide, and system requirements.

    Returns:
        Complete README content as string

    """
    renderedTemplate = None
    with open("build-artifact-templates/README.md") as template:
        renderedTemplate = template.read()
    renderedTemplate = renderedTemplate.replace("{{repo_url}}", REPOSITORY)
    renderedTemplate = renderedTemplate.replace("{{executable_name}}", EXECUTABLE_NAME)
    renderedTemplate = renderedTemplate.replace("{{install_script_name}}", INSTALL_SCRIPT_NAME)
    return renderedTemplate


def renderInstallScript() -> str:
    """Create system installation script.

    Generates a comprehensive installer script that:
    - Installs files to system directories
    - Sets up USB permissions via udev rules
    - Configures uinput module loading
    - Creates systemd service for auto-start

    Returns:
        Complete installation script content as string

    """
    renderedTemplate = None
    with open("build-artifact-templates/scripts/install.sh") as template:
        renderedTemplate = template.read()
    renderedTemplate = renderedTemplate.replace("{{install_dir}}", INSTALL_DIR)
    renderedTemplate = renderedTemplate.replace("{{bin_dir}}", BIN_DIR)
    renderedTemplate = renderedTemplate.replace("{{service_dir}}", SERVICE_DIR)
    renderedTemplate = renderedTemplate.replace("{{executable_name}}", EXECUTABLE_NAME)
    return renderedTemplate


def renderUnInstallScript() -> str:
    """Create uninstall script.

    Generates a complete uninstaller that removes all installed files,
    services, and configuration created by the installer.

    Returns:
        Complete uninstallation script content as string

    """
    renderedTemplate = None
    with open("build-artifact-templates/scripts/uninstall.sh") as template:
        renderedTemplate = template.read()
    renderedTemplate = renderedTemplate.replace("{{install_dir}}", INSTALL_DIR)
    renderedTemplate = renderedTemplate.replace("{{bin_dir}}", BIN_DIR)
    renderedTemplate = renderedTemplate.replace("{{service_dir}}", SERVICE_DIR)
    renderedTemplate = renderedTemplate.replace("{{executable_name}}", EXECUTABLE_NAME)
    return renderedTemplate


def renderWebInstaller(packageName, downloadUrl) -> str:
    """Create uninstall script.

    Generates a complete uninstaller that removes all installed files,
    services, and configuration created by the installer.

    Returns:
        Complete uninstallation script content as string

    """
    renderedTemplate = None
    with open("build-artifact-templates/scripts/web-installer.sh") as template:
        renderedTemplate = template.read()
    renderedTemplate = renderedTemplate.replace("{{package_name}}", packageName)
    renderedTemplate = renderedTemplate.replace("{{download_url}}", downloadUrl)
    return renderedTemplate


def packageDistribution() -> None:  # noqa: PLR0915
    """Create the standalone distribution package.

    Creates a complete distribution package including:
    - Compiled executable and dependencies
    - Documentation and installation scripts
    - Compressed archives with checksums
    - Quick install script for easy deployment

    Raises:
        SystemExit: If build directory is not found or other critical errors occur

    """
    print("📦 Creating standalone distribution package...")

    # Get version info
    version, buildDate = getVersionInfo()
    print(f"📋 Version: {version}")
    print(f"📅 Build: {buildDate}")

    # Create package directory
    packageName = f"{EXECUTABLE_NAME}-{version}-linux-x86_64"
    packageDir = f"{PACKAGE_DIR}/{packageName}"

    print(f"📁 Creating package: {packageName}")

    # Clean and create dist directory
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    os.makedirs(packageDir)

    # Copy the main executable and its dependencies
    print("📋 Copying executable...")
    shutil.copytree(BUILD_DIR, f"{packageDir}/{BUILD_DIR}")

    # Create wrapper script that works from any location
    wrapperScript = f"""#!/bin/bash
# Futaba RC Driver Wrapper
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
exec "$SCRIPT_DIR/{BUILD_DIR}/{EXECUTABLE_NAME}" "$@"
"""

    with open(f"{packageDir}/{EXECUTABLE_NAME}", "w") as f:
        f.write(wrapperScript)
    os.chmod(f"{packageDir}/{EXECUTABLE_NAME}", 0o755)

    # Create documentation
    print("📄 Creating documentation...")
    with open(f"{packageDir}/README.md", "w") as f:
        f.write(renderReadme())

    # Create installation scripts
    print("🔧 Creating installation scripts...")
    with open(f"{packageDir}/install.sh", "w") as f:
        f.write(renderInstallScript())
    os.chmod(f"{packageDir}/install.sh", 0o755)

    with open(f"{packageDir}/uninstall.sh", "w") as f:
        f.write(renderUnInstallScript())
    os.chmod(f"{packageDir}/uninstall.sh", 0o755)

    # Copy license if it exists
    if os.path.exists("LICENSE"):
        shutil.copy2("LICENSE", f"{packageDir}/")
    else:
        # Create a basic license file
        with open(f"{packageDir}/LICENSE", "w") as f:
            f.write("MIT License - See project repository for full license text\n")

    # Create version info file
    with open(f"{packageDir}/VERSION", "w") as f:
        f.write(f"Version: {version}\n")
        f.write(f"Build Date: {buildDate}\n")
        f.write("Platform: Linux x86_64\n")

    # Calculate sizes
    print("📊 Calculating package size...")
    duResult = runCommand(f"du -sh {packageDir}")
    if duResult:
        packageSize = duResult.split()[0]
        print(f"📦 Package size: {packageSize}")

    # Create compressed archives
    print("🗜️  Creating compressed archives...")

    # Create tar.gz (most compatible)
    tarGzName = f"dist/{packageName}.tar.gz"
    with tarfile.open(tarGzName, "w:gz") as tar:
        tar.add(packageDir, arcname=packageName)

    # Create tar.xz (smaller size)
    tarXzName = f"dist/{packageName}.tar.xz"
    runCommand(f"cd dist && tar -cJf {os.path.basename(tarXzName)} {packageName}")

    # Get archive sizes
    tarGzSize = (
        runCommand(f"du -sh {tarGzName}").split()[0]
        if runCommand(f"du -sh {tarGzName}")
        else "Unknown"
    )
    tarXzSize = (
        runCommand(f"du -sh {tarXzName}").split()[0]
        if runCommand(f"du -sh {tarXzName}")
        else "Unknown"
    )

    # Create checksums
    print("🔐 Creating checksums...")
    runCommand(f"cd dist && sha256sum {packageName}.tar.gz > {packageName}.tar.gz.sha256")
    runCommand(f"cd dist && sha256sum {packageName}.tar.xz > {packageName}.tar.xz.sha256")

    # Create download script
    downloadUrl = f"{HOMEPAGE}/{packageName}.tar.gz"
    webInstaller = renderWebInstaller(packageName, downloadUrl)
    with open("dist/web-installer.sh", "w") as f:
        f.write(webInstaller)
    os.chmod("dist/web-installer.sh", 0o755)

    # Summary
    print("\n🎉 Distribution package created successfully!")
    print("=" * 50)
    print(f"📦 Package: {packageName}")
    print(f"📏 Uncompressed: {packageSize}")
    print(f"🗜️  tar.gz: {tarGzSize}")
    print(f"🗜️  tar.xz: {tarXzSize}")
    print("📁 Location: dist/")
    print("\n📋 Files created:")

    distFiles = os.listdir("dist")
    for f in sorted(distFiles):
        filePath = f"dist/{f}"
        if os.path.isfile(filePath):
            size = (
                runCommand(f"du -sh {filePath}").split()[0]
                if runCommand(f"du -sh {filePath}")
                else "?"
            )
            print(f"  📄 {f} ({size})")
        else:
            print(f"  📁 {f}/")

    print("\n🚀 Ready for distribution!")
    print("📤 Upload these files for release:")
    print(f"   • {packageName}.tar.gz")
    print(f"   • {packageName}.tar.xz")
    print(f"   • {packageName}.tar.gz.sha256")
    print(f"   • {packageName}.tar.xz.sha256")
    print("   • quick-install.sh")

    print("\n💡 Users can install with:")
    print(
        "   wget https://your-site.com/quick-install.sh && chmod +x quick-install.sh "
        "&& ./quick-install.sh"
    )
    print("   # OR")
    print(f"   wget https://your-site.com/{packageName}.tar.gz")
    print(f"   tar -xzf {packageName}.tar.gz")
    print(f"   cd {packageName}")
    print("   sudo ./install.sh")


if __name__ == "__main__":
    print("📦 Futaba RC Driver Packaging Tool")
    print("=" * 40)
    packageDistribution()
