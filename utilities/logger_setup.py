import logging
import sys
from logging.handlers import TimedRotatingFileHandler, SysLogHandler
from pathlib import Path


def console_handler() -> logging.handlers:
    """
    Sends logs to the console.
    The console sends only messages by default no need for formatter.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    return handler


def server_handler(log_format: logging.Formatter) -> logging.handlers:
    """
    Sends logs to the syslog server.
    """
    handler = SysLogHandler(('192.168.31.114', 1514))
    handler.setLevel(logging.INFO)
    handler.setFormatter(log_format)
    return handler


def file_handler(log_format: logging.Formatter) -> logging.handlers:
    """
    Sends logs to the log file.
    """
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "runtime.log"
    handler = TimedRotatingFileHandler(log_file, 'H', 6, 20, 'utf-8')
    handler.namer = log_namer
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(log_format)
    return handler


def setup_logging() -> None:
    """
    Use the following to add logger to other modules.
    import logging
    logger = logging.getLogger(__name__)

    The following suppress log messages. It will not log messages of given module unless they are at least warnings.
    logging.getLogger("").setLevel(logging.WARNING)
    """
    # Create a custom logger.
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # Create formatters and add it to handlers.
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Add handlers to the logger.
    logger.addHandler(console_handler())
    logger.addHandler(server_handler(log_format))
    logger.addHandler(file_handler(log_format))


def log_namer(default_name: str) -> str:
    """
    This will be called when doing the log rotation
    default_name is the default filename that would be assigned, e.g. Rotate_Test.txt.YYYY-MM-DD
    Do any manipulations to that name here, for example this function changes the name to Rotate_Test.YYYY-MM-DD.txt
    """
    base_filename, ext, date = default_name.split(".")
    return f"{base_filename}.{date}.{ext}"
