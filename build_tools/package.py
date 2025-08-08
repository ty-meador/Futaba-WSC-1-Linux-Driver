#!/usr/bin/env python3
"""Package Futaba RC Driver into a standalone distribution."""

import os
import shutil
import subprocess
import tarfile
import tomllib
from datetime import datetime

PWD = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PWD, ".."))
PYPROJECT_PATH = os.path.join(PROJECT_ROOT, "pyproject.toml")

with open(PYPROJECT_PATH, "rb") as f:
    """Load pyproject.toml file."""
    toml_data = tomllib.load(f)
PYPROJECT = toml_data

BIN_DIR = PYPROJECT["tool"]["build_tool"]["bin_dir"]
BUILD_DIR = os.path.join(PROJECT_ROOT, PYPROJECT["tool"]["build_tool"]["build_dir"])
EXECUTABLE_NAME = PYPROJECT["tool"]["build_tool"]["executable_name"]
HOMEPAGE = PYPROJECT["project"]["urls"]["Homepage"]
DISTRIBUTABLES_PAGE = PYPROJECT["project"]["urls"]["Distributables"]
INSTALL_DIR = PYPROJECT["tool"]["build_tool"]["install_dir"]
INSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["install_script_name"]
PACKAGE_DIR = os.path.join(PROJECT_ROOT, PYPROJECT["tool"]["build_tool"]["package_dir"])
REPOSITORY = PYPROJECT["project"]["urls"]["Repository"]
SERVICE_DIR = PYPROJECT["tool"]["build_tool"]["service_dir"]
UNINSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["uninstall_script_name"]
VERSION = PYPROJECT["project"]["version"]
WEB_INSTALL_SCRIPT_NAME = PYPROJECT["tool"]["build_tool"]["web_install_script_name"]


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


def renderTemplate(templatePath: str, replacements: dict) -> str:
    """Render a template file with given replacements.

    Args:
        templatePath (str): Path to the template file.
        replacements (dict): Dictionary of placeholders and their corresponding values.

    Returns:
        str: Rendered template content as string.
    """
    rendered = ""

    with open(templatePath) as template:
        rendered = template.read()

    for placeholder, value in replacements.items():
        rendered = rendered.replace(f"{{{{{placeholder}}}}}", value)

    return rendered


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

    print(f"📁 Creating package: {packageName}")

    # Clean and create dist directory
    if os.path.exists(PACKAGE_DIR):
        shutil.rmtree(PACKAGE_DIR)
    os.makedirs(PACKAGE_DIR)

    # Copy the main executable and its dependencies
    print("📋 Copying executable...")
    shutil.copytree(BUILD_DIR, os.path.join(PACKAGE_DIR, os.path.basename(BUILD_DIR)))

    # Create wrapper script that works from any location
    wrapperScript = f"""#!/bin/bash
# Futaba RC Driver Wrapper
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
exec "$SCRIPT_DIR/{os.path.basename(BUILD_DIR)}/{EXECUTABLE_NAME}" "$@"
"""

    with open(os.path.join(PACKAGE_DIR, EXECUTABLE_NAME), "w") as f:
        f.write(wrapperScript)
    os.chmod(f"{PACKAGE_DIR}/{EXECUTABLE_NAME}", 0o755)

    print("📄 Creating documentation...")

    # Create README
    readmePath = os.path.join(PWD, "build-artifact-templates", "README.md")
    readmeReplacements = {
        "version": VERSION,
        "executable_name": EXECUTABLE_NAME,
        "repo_url": REPOSITORY,
        "install_script_name": INSTALL_SCRIPT_NAME,
    }
    with open(os.path.join(PACKAGE_DIR, "README.md"), "w") as f:
        f.write(renderTemplate(readmePath, readmeReplacements))

    print("🔧 Creating installation scripts...")
    installScriptPath = os.path.join(
        PWD, "build-artifact-templates", "scripts", INSTALL_SCRIPT_NAME
    )

    # create installer
    installScriptReplacements = {
        "repo_url": REPOSITORY,
        "executable_name": EXECUTABLE_NAME,
        "install_script_name": INSTALL_SCRIPT_NAME,
        "install_dir": INSTALL_DIR,
        "bin_dir": BIN_DIR,
        "service_dir": SERVICE_DIR,
    }
    with open(os.path.join(PACKAGE_DIR, INSTALL_SCRIPT_NAME), "w") as f:
        f.write(renderTemplate(installScriptPath, installScriptReplacements))
    os.chmod(os.path.join(PACKAGE_DIR, INSTALL_SCRIPT_NAME), 0o755)

    # Create uninstaller
    uninstallScriptPath = os.path.join(
        PWD, "build-artifact-templates", "scripts", INSTALL_SCRIPT_NAME
    )
    uninstallScriptReplacements = {
        "repo_url": REPOSITORY,
        "executable_name": EXECUTABLE_NAME,
        "install_script_name": INSTALL_SCRIPT_NAME,
        "install_dir": INSTALL_DIR,
        "bin_dir": BIN_DIR,
        "service_dir": SERVICE_DIR,
    }

    with open(os.path.join(PACKAGE_DIR, UNINSTALL_SCRIPT_NAME), "w") as f:
        f.write(renderTemplate(uninstallScriptPath, uninstallScriptReplacements))
    os.chmod(os.path.join(PACKAGE_DIR, UNINSTALL_SCRIPT_NAME), 0o755)

    # Copy license if it exists
    if os.path.exists("LICENSE"):
        shutil.copy2("LICENSE", f"{PACKAGE_DIR}/")
    else:
        # Create a basic license file
        with open(f"{PACKAGE_DIR}/LICENSE", "w") as f:
            f.write("MIT License - See project repository for full license text\n")

    # Create version info file
    with open(f"{PACKAGE_DIR}/VERSION", "w") as f:
        f.write(f"Version: {version}\n")
        f.write(f"Build Date: {buildDate}\n")
        f.write("Platform: Linux x86_64\n")

    # Calculate sizes
    print("📊 Calculating package size...")
    duResult = runCommand(f"du -sh {PACKAGE_DIR}")
    if duResult:
        packageSize = duResult.split()[0]
        print(f"📦 Package size: {packageSize}")
    # Create compressed archives
    print("🗜️  Creating compressed archives...")

    parentDir = os.path.dirname(PACKAGE_DIR)
    packageBaseName = os.path.basename(PACKAGE_DIR)

    # Create tar.gz outside the package dir first
    tarGzName = f"{packageName}.tar.gz"
    tempTarGz = os.path.join(parentDir, tarGzName)
    with tarfile.open(tempTarGz, "w:gz") as tar:
        tar.add(PACKAGE_DIR, arcname=packageBaseName)

    # Create tar.xz outside the package dir
    tarXzName = f"{packageName}.tar.xz"
    tempTarXz = os.path.join(parentDir, tarXzName)
    runCommand(f"tar -cJf {tempTarXz} -C {parentDir} {packageBaseName}")

    # Now move them into the package directory
    shutil.move(tempTarGz, os.path.join(PACKAGE_DIR, tarGzName))
    shutil.move(tempTarXz, os.path.join(PACKAGE_DIR, tarXzName))
    # Get archive sizes
    tarGzSize = (
        runCommand(f"du -sh {PACKAGE_DIR}/{tarGzName}").split()[0]
        if runCommand(f"du -sh {PACKAGE_DIR}/{tarGzName}")
        else "Unknown"
    )
    tarXzSize = (
        runCommand(f"du -sh {PACKAGE_DIR}/{tarXzName}").split()[0]
        if runCommand(f"du -sh {PACKAGE_DIR}/{tarXzName}")
        else "Unknown"
    )

    # Create checksums
    print("🔐 Creating checksums...")
    runCommand(f"cd {PACKAGE_DIR} && sha256sum {packageName}.tar.gz > {packageName}.tar.gz.sha256")
    runCommand(f"cd {PACKAGE_DIR} && sha256sum {packageName}.tar.xz > {packageName}.tar.xz.sha256")

    # Create web installer
    downloadUrl = f"{HOMEPAGE}/{packageName}.tar.gz"
    webInstallerPath = os.path.join(
        PWD, "build-artifact-templates", "scripts", WEB_INSTALL_SCRIPT_NAME
    )
    webInstallerReplacements = {
        "package_name": packageName,
        "download_url": downloadUrl,
    }
    with open(os.path.join(PACKAGE_DIR, WEB_INSTALL_SCRIPT_NAME), "w") as f:
        f.write(renderTemplate(webInstallerPath, webInstallerReplacements))
    os.chmod(os.path.join(PACKAGE_DIR, WEB_INSTALL_SCRIPT_NAME), 0o755)

    # Summary
    print("\n🎉 Distribution package created successfully!")
    print("=" * 50)
    print(f"📦 Package: {packageName}")
    print(f"📏 Uncompressed: {packageSize}")
    print(f"🗜️  tar.gz: {tarGzSize}")
    print(f"🗜️  tar.xz: {tarXzSize}")
    print("📁 Location: dist/")
    print("\n📋 Files created:")

    distFiles = os.listdir(PACKAGE_DIR)
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
    print(f"   • {WEB_INSTALL_SCRIPT_NAME}")

    print("\n💡 Users can install with:")
    print(
        f"   wget {DISTRIBUTABLES_PAGE}/{WEB_INSTALL_SCRIPT_NAME} && chmod +x {WEB_INSTALL_SCRIPT_NAME} "
        f"&& ./{WEB_INSTALL_SCRIPT_NAME}"
    )
    print("   # OR")
    print(f"   wget {DISTRIBUTABLES_PAGE}/{packageName}.tar.gz")
    print(f"   tar -xzf {packageName}.tar.gz")
    print(f"   cd {packageName}")
    print(f"   sudo ./{INSTALL_SCRIPT_NAME}")


if __name__ == "__main__":
    print("📦 Futaba RC Driver Packaging Tool")
    print("=" * 40)
    packageDistribution()
