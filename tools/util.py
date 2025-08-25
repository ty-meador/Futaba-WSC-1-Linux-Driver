"""Utilities and constants for the build system."""

import subprocess
from pathlib import Path


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


def runCommand(
    cmd: str,
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
        Command output if capture=True and successful, empty string if capture=False and successful

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
