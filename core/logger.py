"""
core/logger.py - Session logging for Minecraft Jarvis.
Writes timestamped entries to console (with color) and optionally to a log file.
"""
import logging
import os
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

_logger = None
_config = {}


def setup(config: dict):
    """Initialize the logger. Call this once at startup."""
    global _logger, _config
    _config = config

    _logger = logging.getLogger("jarvis")
    _logger.setLevel(logging.DEBUG)
    _logger.handlers.clear()

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(_ColorFormatter())
    _logger.addHandler(ch)

    if config.get("log_to_file", True):
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config.get("log_dir", "logs"))
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"session_{timestamp}.log")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        _logger.addHandler(fh)
        _logger.info(f"Session log: {log_file}")

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
        msg = record.getMessage()
        return f"{prefix}{msg}{Style.RESET_ALL}"