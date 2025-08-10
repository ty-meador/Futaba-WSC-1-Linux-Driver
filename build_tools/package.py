#!/usr/bin/env python3
"""Package Futaba RC Driver into a standalone distribution."""

import shutil
import subprocess
import tarfile
import tomllib
from datetime import datetime
from pathlib import Path

# Project structure
PWD = Path(__file__).parent.resolve()
PROJECT_ROOT = PWD.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

# Load project configuration
with open(PYPROJECT_PATH, "rb") as f:
    """Load pyproject.toml file."""
    toml_data = tomllib.load(f)
PYPROJECT = toml_data

# Extract configuration values
project_config = PYPROJECT["project"]
build_config = PYPROJECT["tool"]["build_tool"]

# Build configuration
BIN_DIR = build_config["bin_dir"]
BUILD_DIR = PROJECT_ROOT / build_config["build_dir"]
EXECUTABLE_NAME = build_config["executable_name"]
INSTALL_DIR = build_config["install_dir"]
INSTALL_SCRIPT_NAME = build_config["install_script_name"]
PACKAGE_DIR = PROJECT_ROOT / build_config["package_dir"]
SERVICE_DIR = build_config["service_dir"]
UNINSTALL_SCRIPT_NAME = build_config["uninstall_script_name"]
WEB_INSTALL_SCRIPT_NAME = build_config["web_install_script_name"]

# Project metadata
HOMEPAGE = project_config["urls"]["Homepage"]
DISTRIBUTABLES_PAGE = project_config["urls"]["Distributables"]
REPOSITORY = project_config["urls"]["Repository"]
VERSION = project_config["version"]

# Template paths
TEMPLATES_DIR = PWD / "build-artifact-templates"
SCRIPTS_TEMPLATES_DIR = TEMPLATES_DIR / "scripts"


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


def renderTemplateToFile(templatePath: Path, replacements: dict, outputPath: Path) -> str:
    """Render a template file with given replacements.

    Args:
        templatePath: Path to the template file.
        replacements: Dictionary of placeholders and their corresponding values.
        outputPath: The path to write the rendered file to.

    Returns:
        str: Rendered template content as string.
    """
    try:
        rendered = templatePath.read_text()
        # Placeholders are in the form of {{i_am_a_placeholder}}
        for placeholder, value in replacements.items():
            rendered = rendered.replace(f"{{{{{str(placeholder)}}}}}", str(value))

        # Write file and set proper permissions
        outputPath.write_text(rendered)
        outputPath.chmod(0o755)
    except Exception as e:
        raise RuntimeError("Failed to render template file.") from e
    return True


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
    packagePath = PACKAGE_DIR / packageName

    print(f"📁 Creating package: {packageName}")

    # Clean and create dist directory
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True)

    # Copy the main executable and its dependencies
    print("📋 Copying executable...")
    shutil.copytree(BUILD_DIR, packagePath / BUILD_DIR.name)

    # Create wrapper script that works from any location
    renderTemplateToFile(
        SCRIPTS_TEMPLATES_DIR / "wrapper.sh",
        {"executable_path": f"{BUILD_DIR.name}/{EXECUTABLE_NAME}"},  # use relative path
        packagePath / EXECUTABLE_NAME,
    )

    print("📄 Creating documentation...")

    # Create README
    renderTemplateToFile(
        TEMPLATES_DIR / "README.md",
        {
            "version": VERSION,
            "executable_name": EXECUTABLE_NAME,
            "repo_url": REPOSITORY,
            "install_script_name": INSTALL_SCRIPT_NAME,
        },
        packagePath / "README.md",
    )

    print("🔧 Creating installation scripts...")

    ##
    # create installer
    ##
    renderTemplateToFile(
        SCRIPTS_TEMPLATES_DIR / INSTALL_SCRIPT_NAME,
        {
            "repo_url": REPOSITORY,
            "executable_name": EXECUTABLE_NAME,
            "install_script_name": INSTALL_SCRIPT_NAME,
            "install_dir": INSTALL_DIR,
            "bin_dir": BIN_DIR,
            "service_dir": SERVICE_DIR,
        },
        packagePath / INSTALL_SCRIPT_NAME,
    )

    ##
    # Create uninstaller
    ##
    renderTemplateToFile(
        SCRIPTS_TEMPLATES_DIR / UNINSTALL_SCRIPT_NAME,
        {
            "repo_url": REPOSITORY,
            "executable_name": EXECUTABLE_NAME,
            "install_script_name": INSTALL_SCRIPT_NAME,
            "install_dir": INSTALL_DIR,
            "bin_dir": BIN_DIR,
            "service_dir": SERVICE_DIR,
        },
        packagePath / UNINSTALL_SCRIPT_NAME,
    )

    ##
    # Copy license if it exists
    ##
    licensePath = PROJECT_ROOT / "LICENSE"
    packageLicensePath = packagePath / "LICENSE"
    if licensePath.exists():
        shutil.copy2(licensePath, packageLicensePath)
    else:
        raise PermissionError("Uable to find LICENSE, refusing to package.")

    # Create version info file
    renderTemplateToFile(
        TEMPLATES_DIR / "VERSION",
        {"version": version, "build_date": buildDate},
        packagePath / "VERSION",
    )

    ##
    # Create archives
    ##
    print("📊 Calculating package size...")
    duResult = runCommand(f"du -sh {packagePath}")
    if duResult:
        packageSize = duResult.split()[0]
        print(f"📦 Package size: {packageSize}")

    print("🗜️  Creating compressed archives...")

    # Create tar.gz outside the package dir first
    tarGzName = f"{packageName}.tar.gz"
    tempTarGz = PACKAGE_DIR / tarGzName
    with tarfile.open(tempTarGz, "w:gz") as tar:
        tar.add(packagePath, arcname=packageName)

    # Create tar.xz outside the package dir
    tarXzName = f"{packageName}.tar.xz"
    tempTarXz = PACKAGE_DIR / tarXzName
    runCommand(f"tar -cJf {tempTarXz} -C {PACKAGE_DIR} {packageName}")

    # Now move them into the package directory
    finalTarGz = packagePath / tarGzName
    finalTarXz = packagePath / tarXzName
    shutil.move(tempTarGz, finalTarGz)
    shutil.move(tempTarXz, finalTarXz)

    # Get archive sizes
    tarGzSize = (
        runCommand(f"du -sh {finalTarGz}").split()[0]
        if runCommand(f"du -sh {finalTarGz}")
        else "Unknown"
    )
    tarXzSize = (
        runCommand(f"du -sh {finalTarXz}").split()[0]
        if runCommand(f"du -sh {finalTarXz}")
        else "Unknown"
    )

    # Create checksums
    print("🔐 Creating checksums...")
    runCommand(f"cd {packagePath} && sha256sum {tarGzName} > {tarGzName}.sha256")
    runCommand(f"cd {packagePath} && sha256sum {tarXzName} > {tarXzName}.sha256")

    # Create web installer
    renderTemplateToFile(
        SCRIPTS_TEMPLATES_DIR / WEB_INSTALL_SCRIPT_NAME,
        {
            "package_name": packageName,
            "download_url": f"{DISTRIBUTABLES_PAGE}/{packageName}/{tarGzName}",
        },
        packagePath / WEB_INSTALL_SCRIPT_NAME,
    )

    # Summary
    print("\n🎉 Distribution package created successfully!")
    print("=" * 50)
    print(f"📦 Package: {packageName}")
    print(f"📏 Uncompressed: {packageSize}")
    print(f"🗜️  tar.gz: {tarGzSize}")
    print(f"🗜️  tar.xz: {tarXzSize}")
    print("📁 Location: dist/")
    print("\n📋 Files created:")

    distFiles = list(packagePath.iterdir())
    for filePath in sorted(distFiles):
        fileName = filePath.name
        if filePath.is_file():
            size = (
                runCommand(f"du -sh {filePath}").split()[0]
                if runCommand(f"du -sh {filePath}")
                else "?"
            )
            print(f"  📄 {fileName} ({size})")
        else:
            print(f"  📁 {fileName}/")

    print("\n🚀 Ready for distribution!")
    print("📤 Upload these files for release:")
    print(f"   • {tarGzName}")
    print(f"   • {tarXzName}")
    print(f"   • {tarGzName}.sha256")
    print(f"   • {tarXzName}.sha256")
    print(f"   • {WEB_INSTALL_SCRIPT_NAME}")

    print("\n💡 Users can install with:")
    print(
        f"   wget {DISTRIBUTABLES_PAGE}/{WEB_INSTALL_SCRIPT_NAME} "
        f"&& chmod +x {WEB_INSTALL_SCRIPT_NAME} && ./{WEB_INSTALL_SCRIPT_NAME}"
    )
    print("   # OR")
    print(f"   wget {DISTRIBUTABLES_PAGE}/{tarGzName}")
    print(f"   tar -xzf {tarGzName}")
    print(f"   cd {packageName}")
    print(f"   sudo ./{INSTALL_SCRIPT_NAME}")


if __name__ == "__main__":
    print("📦 Futaba RC Driver Packaging Tool")
    print("=" * 40)
    packageDistribution()
