"""Utility functions for the project"""

import inspect
import json
import logging
import os
import time
from logging import handlers
from pathlib import Path

HANDLER = handlers.RotatingFileHandler(
    "logs.txt",
    maxBytes=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
)
# current_file_path = os.path.abspath(__file__)


def getConfigsPath():
    """Gets the abs path to the config files directory"""
    return os.path.abspath(os.path.join(getProjectRoot(), "driver", "configs"))


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


def generateLogger(
    name=inspect.stack()[1].function,  # Hack to get name of whatever called us :D
    level=logging.INFO,
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


def configSanityCheck():
    """Ensures that the default config file exists with default values"""
    configsPath = getConfigsPath()
    logger = generateLogger()
    # Ensure default config file exists
    if not os.path.exists(os.path.join(configsPath, "default.json")):
        logger.warning("default_config.json does not exist")
        generateDefaultConfigFile()
    else:  # Is the default file sane?
        try:
            with open(
                os.path.join(configsPath, "default.json"), "r", encoding="utf-8"
            ) as cfgFile:
                json.load(cfgFile)
        except Exception:
            logger.error("Unable to parse configs/default.json. Regenerating it...")
            # Delete the existing default config and regenerate it
            generateDefaultConfigFile(forceRegenerate=True)


def generateDefaultConfigFile(forceRegenerate=False):
    """Regenerates the default config file

    Args:
        forceRegenerate (bool, optional): If true the existing configuration file will be deleted and a new one will be created using default values. Defaults to False.
    """
    logger = generateLogger()
    configsPath = getConfigsPath()
    fileName = os.path.join(configsPath, "default.json")
    backupFileName = f"{fileName}.{time.time()}.BACKUP"

    logger.info("Attempting to generate the default config file...")
    if os.path.exists(fileName):
        logger.warning("Default config file already exists...")
        # Force regenerate will delete the existing file and generate a
        # new one from scratch
        if forceRegenerate is True:
            os.rename(fileName, backupFileName)
            logger.warning(
                f"-> Force regnerating default config file: your config file was backed up to {backupFileName}"
            )
        else:  # file exists, not force regenerating - do nothing
            return

    # A dict with a 1:1 representation of the JSON file that will be generated...
    defaultConfig = {"frame_size": 16, "event_max_value": 32768}

    # ...told ya
    with open(fileName, "w+", encoding="utf-8") as cfgFile:
        cfgFile.write(json.dumps(defaultConfig, indent=4))
