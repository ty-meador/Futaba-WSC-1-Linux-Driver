"""Development tools module."""

import sys
from pathlib import Path

# tomllib wasn't added until 3.11
try:
    import tomllib
except ModuleNotFoundError:
    print("Minimum python version is 3.11.0")
    print("Please create a venv with python version >= 3.11.0")
    print("Try: python3 --version?")
    sys.exit(1)

# Project structure
PWD = Path(__file__).parent.resolve()
PROJECT_ROOT = PWD.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

# Load project configuration
with open(PYPROJECT_PATH, "rb") as f:
    toml_data = tomllib.load(f)
PYPROJECT = toml_data

# Refuse to run if we aren't operating in a venv
if sys.prefix == sys.base_prefix:
    if not (PROJECT_ROOT / ".venv").exists():
        print("Script must be run from a venv. Try the following first.")
        print(f"NOTE: Python version requirement -> {PYPROJECT['project']['requires-python']}")
        print("python3 -m venv .venv")
    else:
        print(
            "You appear to have a virtual environment setup correctly but the python runtime used "
            "is not correct for that environment."
        )
        print("=" * 80)
        print("Troubleshooting steps:")
        print("  1: Ensure venv is activated:")
        print("      'source .venv/bin/activate'")
        print(
            "  2: Make sure you are not specifying a python version when you are running this "
            "script. For example:"
        )
        print("      ❌ /bin/usr/python3 ./tools/build.py")
        print("      ✅ ./tools/build.py")
        print("=" * 80)
    sys.exit(1)

# Extract configuration values
project_config = PYPROJECT["project"]
build_config = PYPROJECT["tool"]["build_tool"]

# Build configuration
BIN_DIR = build_config["bin_dir"]
BUILD_DIR: Path = PROJECT_ROOT / build_config["build_dir"]
EXECUTABLE_NAME: Path = build_config["executable_name"]
INSTALL_DIR: Path = build_config["install_dir"]
INSTALL_SCRIPT_NAME: Path = build_config["install_script_name"]
PACKAGE_DIR: Path = PROJECT_ROOT / build_config["package_dir"]
UNINSTALL_SCRIPT_NAME: Path = build_config["uninstall_script_name"]
WEB_INSTALL_SCRIPT_NAME: Path = build_config["web_install_script_name"]

# Project metadata
HOMEPAGE: Path = project_config["urls"]["Homepage"]
DISTRIBUTABLES_PAGE: Path = project_config["urls"]["Distributables"]
REPOSITORY: Path = project_config["urls"]["Repository"]
VERSION: Path = project_config["version"]

# Template paths
TEMPLATES_DIR: Path = PWD / "artifact-templates"
SCRIPTS_TEMPLATES_DIR: Path = TEMPLATES_DIR / "scripts"

# Additional build-specific paths
SOURCE_MAIN: Path = PROJECT_ROOT / "src" / "main.py"
NUITKA_OUTPUT_DIR: Path = PROJECT_ROOT / f"{SOURCE_MAIN.stem}.dist"
WRAPPER_SCRIPT: Path = PROJECT_ROOT / EXECUTABLE_NAME
