"""
core/logger.py - Session logging for Jarvis.
Logs go to %APPDATA%\Jarvis\logs\ to avoid Windows Defender Controlled Folder Access.
Conversation exchanges are written to %APPDATA%\Jarvis\data\conversations.txt.
"""
import logging
import os
import threading
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

_logger = None
_config = {}
_conv_path: str = ""
_conv_lock = threading.Lock()


def _default_log_dir() -> str:
    """Returns %APPDATA%\Jarvis\logs — always writable by Python on Windows."""
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Jarvis", "logs")


def _default_data_dir() -> str:
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Jarvis", "data")


def setup(config: dict):
    global _logger, _config, _conv_path
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

    # Conversation log path
    data_dir = config.get("data_dir", "") or _default_data_dir()
    try:
        os.makedirs(data_dir, exist_ok=True)
        _conv_path = os.path.join(data_dir, "conversations.txt")
    except Exception as e:
        _logger.warning(f"Conversation logging path setup failed: {e}")
        _conv_path = ""

    return _logger


def get() -> logging.Logger:
    if _logger is None:
        raise RuntimeError("Logger not initialized. Call logger.setup(config) first.")
    return _logger


def log_exchange(mode: str, user_text: str, assistant_text: str):
    """
    Write a user/assistant exchange to conversations.txt in the format:
      [YYYY-MM-DD HH:MM:SS] [INPUT MODE: VOICE|TEXT] USER: <query>
      [YYYY-MM-DD HH:MM:SS] ASSISTANT: <response>
      ----------------------------------------------------------------------
    Thread-safe via _conv_lock.
    """
    if not _conv_path:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_upper = (mode or "TEXT").upper()
    lines = (
        f"[{ts}] [INPUT MODE: {mode_upper}] USER: {user_text}\n"
        f"[{ts}] ASSISTANT: {assistant_text}\n"
        f"----------------------------------------------------------------------\n"
    )
    with _conv_lock:
        try:
            with open(_conv_path, "a", encoding="utf-8") as f:
                f.write(lines)
        except Exception as exc:
            if _logger:
                _logger.warning(f"Conversation log write failed: {exc}")


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
