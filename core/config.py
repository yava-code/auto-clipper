import json
import os
import sys

DEFAULTS = {
    "sleep_ms": 15,
    "hotkey": "ctrl+v",
    "window_x": None,
    "window_y": None,
    "delimiter": ";",
    "custom_mode": "delimiter",   # delimiter | regex_split | regex_findall
    "regex_pattern": "",
    "transform_prefix": "",
    "transform_suffix": "",
    "groq_api_key": "",
}


def _path():
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config.json")


def load():
    p = _path()
    if not os.path.exists(p):
        return dict(DEFAULTS)
    with open(p) as f:
        return {**DEFAULTS, **json.load(f)}


def save(cfg):
    with open(_path(), "w") as f:
        json.dump(cfg, f, indent=2)
