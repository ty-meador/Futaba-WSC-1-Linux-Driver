#!/usr/bin/env python3
"""Package Futaba RC Driver into a standalone distribution."""

import shutil
import tarfile
from argparse import ArgumentParser
from datetime import datetime

from clean import cleanPackageArtifacts
from config import (
    BIN_DIR,
    BUILD_DIR,
    DISTRIBUTABLES_PAGE,
    EXECUTABLE_NAME,
    INSTALL_DIR,
    INSTALL_SCRIPT_NAME,
    PACKAGE_DIR,
    PROJECT_ROOT,
    REPOSITORY,
    SCRIPTS_TEMPLATES_DIR,
    TEMPLATES_DIR,
    UNINSTALL_SCRIPT_NAME,
    VERSION,
    WEB_INSTALL_SCRIPT_NAME,
)
from util import renderTemplate, runCommand

parser = ArgumentParser()
parser.add_argument("--clean", action="store_true")


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
    renderTemplate(
        SCRIPTS_TEMPLATES_DIR / "wrapper.sh",
        {"executable_path": f"{BUILD_DIR.name}/{EXECUTABLE_NAME}"},  # use relative path
        packagePath / EXECUTABLE_NAME,
    )

    print("📄 Creating documentation...")

    # Create README
    renderTemplate(
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
    renderTemplate(
        SCRIPTS_TEMPLATES_DIR / INSTALL_SCRIPT_NAME,
        {
            "repo_url": REPOSITORY,
            "executable_name": EXECUTABLE_NAME,
            "install_script_name": INSTALL_SCRIPT_NAME,
            "install_dir": INSTALL_DIR,
            "bin_dir": BIN_DIR,
            "artifact_dir": SCRIPTS_TEMPLATES_DIR,
        },
        packagePath / INSTALL_SCRIPT_NAME,
    )

    ##
    # Create uninstaller
    ##
    renderTemplate(
        SCRIPTS_TEMPLATES_DIR / UNINSTALL_SCRIPT_NAME,
        {
            "repo_url": REPOSITORY,
            "executable_name": EXECUTABLE_NAME,
            "install_script_name": INSTALL_SCRIPT_NAME,
            "install_dir": INSTALL_DIR,
            "bin_dir": BIN_DIR,
        },
        packagePath / UNINSTALL_SCRIPT_NAME,
    )

    pkgCriticalFiles = [
        PROJECT_ROOT / "LICENSE",
        TEMPLATES_DIR / "udev.rules",
        PROJECT_ROOT / "NOTICE",
    ]

    missing = [pkgFile for pkgFile in pkgCriticalFiles if not pkgFile.exists()]
    if missing:
        raise FileNotFoundError(
            f"🚨UNABLE TO FIND >{', '.join(map(str, missing))}< REFUSING TO PACKAGE🚨"
        )

    for pkgFile in pkgCriticalFiles:
        shutil.copy2(pkgFile, packagePath)

    ##
    # Create version info file
    ##
    renderTemplate(
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
    renderTemplate(
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
    print(f"   ./{INSTALL_SCRIPT_NAME}")


if __name__ == "__main__":
    print("📦 Futaba RC Driver Packaging Tool")
    print("=" * 40)
    args = parser.parse_args()
    if args.clean:
        cleanPackageArtifacts()
    else:
        packageDistribution()
