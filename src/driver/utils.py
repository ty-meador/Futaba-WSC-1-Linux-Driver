"""Utility functions for the project"""

import logging
import os
from logging import handlers
from pathlib import Path

CALIBRATION_PATH = None
CONFIG_PATH = None
LOG_PATH = None
ROOT_DIR = None

for parent in Path(__file__).resolve().parents:
    if (parent / ".pylintrc").exists():
        LOG_PATH = os.path.abspath((os.path.join(parent, "logs")))
        ROOT_DIR = os.path.abspath(os.path.join(parent, "src"))
        CONFIG_PATH = os.path.abspath(os.path.join(ROOT_DIR, "configs"))
        CALIBRATION_PATH = os.path.abspath(os.path.join(ROOT_DIR, "calibrations"))

        os.makedirs(LOG_PATH, exist_ok=True)
        os.makedirs(ROOT_DIR, exist_ok=True)
        os.makedirs(CONFIG_PATH, exist_ok=True)
        os.makedirs(CALIBRATION_PATH, exist_ok=True)


LOG_HANDLER = handlers.RotatingFileHandler(
    os.path.join(LOG_PATH, "log.txt"),
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)


def getLogger(
    name="logs",
    level=logging.DEBUG,
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
    handler = LOG_HANDLER
    handler.setFormatter(
        logging.Formatter(f"%(asctime)s - {name} %(levelname)s\t: %(message)s")
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger
