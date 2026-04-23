"""
core/memory.py
==============
Lightweight local state store. Persists to data/memory.json.
Zero dependencies beyond stdlib.
"""
import json
import os
from datetime import datetime

_store: dict = {}
_path: str   = ""


def setup(config: dict):
    global _store, _path
    data_dir = config.get("data_dir", "data")
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
    return _store.get(key, default)


def set(key: str, value):
    _store[key] = value
    _save()


def append(key: str, value):
    lst = _store.get(key, [])
    lst.append({"value": value, "ts": datetime.now().isoformat()})
    _store[key] = lst
    _save()


def delete(key: str):
    _store.pop(key, None)
    _save()


def all_data() -> dict:
    return dict(_store)