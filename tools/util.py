#!/usr/bin/env python3
"""Utilities and constants for the build system."""

import subprocess
from pathlib import Path


def renderTemplate(
    templatePath: Path,
    replacements: dict[str, Path | str],
    outputPath: Path | None = None,
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


def runCommand(
    cmd: str | list[str],
    cwd: str | None = None,
    capture: bool = True,
    shell: bool = True,
    check: bool = True,
) -> str | None:
    """Run a command and handle errors.

    Args:
        cmd: Command to run as shell string
        cwd: Working directory for command execution
        capture: Whether to capture and return output

    Returns:
        Str: Command output if capture=True and successful, empty string if capture=False and successful

    """
    if capture:
        result = subprocess.run(
            cmd,
            shell=shell,
            check=check,  # Raise exception if non-zero exit
            cwd=cwd,
            capture_output=True,
            text=True,  # str instead of raw bytes
        )
        return result.stdout.strip()
    else:
        subprocess.run(cmd, shell=shell, check=check, cwd=cwd)
        return ""


def _getNestedValue(dictionary: dict, path: str) -> any:
    """
    Retrieve a value from a nested dictionary using dot notation.

    Args:
        dictionary: The dictionary to search
        path: String with dot notation (e.g., "my.value")

    Returns:
        The value at the path, or None if not found
    """
    keys = path.split('.')
    value = dictionary

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


if __name__ == "__main__":
    from __config__ import PYPROJECT
    from argparse import ArgumentParser
    from sys import stderr, argv

    parser = ArgumentParser()
    parser.add_argument("--pyproject", action="store", help="Print a value from pyproject.toml")
    ARGS = parser.parse_args()

    # Script name is always passed
    if len(argv) == 1:
        print("Futaba RC Driver Development Utilities")
        print("=" * 40)
        parser.print_help(stderr)

    if ARGS.pyproject:
        try:
            print(_getNestedValue(PYPROJECT, ARGS.pyproject))
        except Exception as e:
            print(e)
