import logging
from logging.handlers import RotatingFileHandler


def generateLogger(
    name,
    maxSize=5 * 1024 * 1024,  # 5 megabytes
    backupCount=5,
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
    handler = RotatingFileHandler(
        f"{name}.log", maxBytes=maxSize, backupCount=backupCount
    )
    handler.setFormatter(
        logging.Formatter(f"%(asctime)s - {name} %(levelname)s\t: %(message)s")
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger
