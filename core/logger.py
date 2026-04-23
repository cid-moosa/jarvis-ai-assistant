"""
core/logger.py - Session logging for Jarvis.
Logs go to %APPDATA%\Jarvis\logs\ to avoid Windows Defender Controlled Folder Access.
"""
import logging
import os
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

_logger = None
_config = {}

def _default_log_dir() -> str:
    """Returns %APPDATA%\Jarvis\logs — always writable by Python on Windows."""
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Jarvis", "logs")


def setup(config: dict):
    global _logger, _config
    _config = config

    _logger = logging.getLogger("jarvis")
    _logger.setLevel(logging.DEBUG)
    _logger.handlers.clear()

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(_ColorFormatter())
    _logger.addHandler(ch)

    # File handler
    if config.get("log_to_file", True):
        log_dir = config.get("log_dir", "") or _default_log_dir()
        try:
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"session_{timestamp}.log")
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            _logger.addHandler(fh)
            _logger.info(f"Session log: {log_file}")
        except Exception as e:
            _logger.warning(f"File logging disabled: {e}")

    return _logger


def get() -> logging.Logger:
    if _logger is None:
        raise RuntimeError("Logger not initialized. Call logger.setup(config) first.")
    return _logger


class _ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG:    Fore.CYAN,
        logging.INFO:     Fore.GREEN,
        logging.WARNING:  Fore.YELLOW,
        logging.ERROR:    Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = f"{Fore.WHITE}[{ts}]{Style.RESET_ALL} {color}"
        return f"{prefix}{record.getMessage()}{Style.RESET_ALL}"