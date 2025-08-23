"""Utilities and constants for the build system."""

import subprocess
import tomllib
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
UNINSTALL_SCRIPT_NAME = build_config["uninstall_script_name"]
WEB_INSTALL_SCRIPT_NAME = build_config["web_install_script_name"]

# Project metadata
HOMEPAGE = project_config["urls"]["Homepage"]
DISTRIBUTABLES_PAGE = project_config["urls"]["Distributables"]
REPOSITORY = project_config["urls"]["Repository"]
VERSION = project_config["version"]

# Template paths
TEMPLATES_DIR = PWD / "artifact-templates"
SCRIPTS_TEMPLATES_DIR = TEMPLATES_DIR / "scripts"

# Additional build-specific paths
SOURCE_MAIN = PROJECT_ROOT / "src" / "main.py"
NUITKA_OUTPUT_DIR = PROJECT_ROOT / f"{SOURCE_MAIN.stem}.dist"
WRAPPER_SCRIPT = PROJECT_ROOT / EXECUTABLE_NAME


def renderTemplate(
    templatePath: Path,
    replacements: dict,
    outputPath: Path = None,
) -> str | None:
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
        if outputPath:
            outputPath.write_text(rendered)
            outputPath.chmod(0o755)

        return rendered
    except Exception as e:
        raise RuntimeError("Failed to render template file.") from e
    return True


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
                cmd,
                shell=True,
                check=True,  # Raise exception if non-zero exit
                cwd=cwd,
                capture_output=True,
                text=True,  # str instead of raw bytes
            )
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd)
            return ""
    except subprocess.CalledProcessError as e:
        if capture and e.stderr:
            print(f"Error: {e.stderr}")
        return None
