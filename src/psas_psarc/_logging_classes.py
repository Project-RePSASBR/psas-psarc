import logging
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class BColors:
    """
    ANSI escape sequences for colored terminal output.
    """

    HEADER: str = "\033[95m"
    OKBLUE: str = "\033[94m"
    OKCYAN: str = "\033[96m"
    OKGREEN: str = "\033[92m"
    WARNING: str = "\033[93m"
    FAIL: str = "\033[91m"
    ENDC: str = "\033[0m"
    BOLD: str = "\033[1m"
    UNDERLINE: str = "\033[4m"


class ColoredFormatter(logging.Formatter):
    """
    Custom logging formatter that adds color to log messages based on their severity level.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log message with color based on the log level.

        :param record: Log record to format
        :type record: logging.LogRecord
        :return: Formatted log message with color
        :rtype: str
        """
        log_message = super().format(record)
        if record.levelno == logging.DEBUG:
            return f"{BColors.OKBLUE}[{record.name}][{record.levelname}]{BColors.ENDC} {log_message}"
        elif record.levelno == logging.INFO:
            return f"{BColors.OKGREEN}[{record.name}][{record.levelname}]{BColors.ENDC} {log_message}"
        elif record.levelno == logging.WARNING:
            return f"{BColors.WARNING}[{record.name}][{record.levelname}]{BColors.ENDC} {log_message}"
        elif record.levelno == logging.ERROR:
            return f"{BColors.FAIL}[{record.name}][{record.levelname}]{BColors.ENDC} {log_message}"
        elif record.levelno == logging.CRITICAL:
            return f"{BColors.BOLD}{BColors.FAIL}[{record.name}][{record.levelname}]{BColors.ENDC} {log_message}"
        else:
            return log_message


def setup_loggers(name: str, level: int = logging.INFO):
    """
    Set up a logger with the specified name and level.

    :param name: Name of the logger
    :type name: str
    :param level: Logging level (default: logging.INFO)
    :type level: int
    """

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate console handlers when the CLI is invoked more than once in the same process.
    for existing_handler in list(logger.handlers):
        logger.removeHandler(existing_handler)
        existing_handler.close()

    # Create console handler with colored formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    formatter = ColoredFormatter()
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)

    # Prevent log messages from being propagated to the root logger
    logger.propagate = False
