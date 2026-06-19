"""
core/memory.py - Lightweight local state store.
Data goes to %APPDATA%\Jarvis\data\ to avoid Windows Defender Controlled Folder Access.
Includes secure API key storage via set_api_key / get_api_key.
"""
import json
import os
import threading
from datetime import datetime

_store: dict = {}
_path: str   = ""
_lock = threading.Lock()

def _default_data_dir() -> str:
    """Returns %APPDATA%\Jarvis\data — always writable by Python on Windows."""
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Jarvis", "data")


def setup(config: dict):
    global _store, _path
    data_dir = config.get("data_dir", "") or _default_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    _path = os.path.join(data_dir, "memory.json")
    if os.path.exists(_path):
        try:
            with open(_path, "r", encoding="utf-8") as f:
                _store = json.load(f)
        except Exception:
            _store = {}
    else:
        _store = {}


def _save():
    with open(_path, "w", encoding="utf-8") as f:
        json.dump(_store, f, indent=2, ensure_ascii=False, default=str)


def get(key: str, default=None):
    with _lock:
        return _store.get(key, default)


def set(key: str, value):
    with _lock:
        _store[key] = value
        _save()


def append(key: str, value):
    with _lock:
        lst = _store.get(key, [])
        lst.append({"value": value, "ts": datetime.now().isoformat()})
        _store[key] = lst
        _save()


def delete(key: str):
    with _lock:
        _store.pop(key, None)
        _save()


def all_data() -> dict:
    with _lock:
        return dict(_store)


# ── Secure API Key helpers ─────────────────────────────────────────────────────

def set_api_key(provider: str, key: str):
    """Persist an API key for the given provider into memory.json under 'api_keys'."""
    with _lock:
        keys = _store.get("api_keys", {})
        keys[provider.lower()] = key.strip()
        _store["api_keys"] = keys
        _save()


def get_api_key(provider: str) -> str | None:
    """Retrieve the stored API key for the given provider, or None if not set."""
    with _lock:
        return _store.get("api_keys", {}).get(provider.lower())
