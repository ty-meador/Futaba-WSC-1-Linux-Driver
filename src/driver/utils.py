"""Utility functions for the project"""

import logging
import os
from logging import handlers
from pathlib import Path

HANDLER = handlers.RotatingFileHandler(
    "logs.txt",
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)


def getProjectRoot():
    """
    Gets the project root directory, assuming this function is called
    from a file within the project, and that there's a 'pyproject.toml'
    file at the project root.
    """

    # Start from THIS file's directory
    currentFile = Path(__file__).resolve()  # Using resolve to get an absolute path.
    # Go up directories until we find 'pyproject.toml'
    for parent in currentFile.parents:  # Iterate over every parent.
        if (parent / ".pylintrc").exists():  # Checks if file exists
            return parent
    raise FileNotFoundError("Project root (with .pylintrc) not found.")


ROOT_DIR = os.path.abspath(getProjectRoot() / "src")
CONFIG_PATH = os.path.join(ROOT_DIR, "driver", "configs")
CALIBRATION_PATH = os.path.join(ROOT_DIR, "driver", "calibrations")


def getLogger(
    name="logs",
    level=logging.warning,
):
    """Generates a logger

    Args:
        name (str): _description_
        maxSize (int, optional): Max file size of log files. Defaults to 5*1024*1024.
        backupCount (int, optional): Number of backup logs to keep in rotation. Defaults to 5
        level (loglevel, optional): The level the logger should output. Defaults to logging.WARNING.

    Returns:
        logger: The generated logger
    """
    handler = HANDLER
    handler.setFormatter(
        logging.Formatter(f"%(asctime)s - {name} %(levelname)s\t: %(message)s")
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger
