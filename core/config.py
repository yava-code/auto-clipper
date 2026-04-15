import json
import os
import sys
from core import log

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
    "groq_model": "llama-3.3-70b-versatile",
    "ui_theme": "light",
}


def _path():
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config.json")


def _env_api_key():
    """Read Groq key from .env — supports KEY=value or raw key on first line."""
    env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(env):
        return ""
    try:
        with open(env, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip().upper() in ("GROQ_API_KEY", "GROQ_KEY"):
                        return v.strip()
                elif line.startswith("gsk_"):
                    return line
    except Exception as e:
        log.get().warning("env read error: %s", e)
    return ""


def load():
    p = _path()
    if not os.path.exists(p):
        cfg = dict(DEFAULTS)
    else:
        with open(p) as f:
            cfg = {**DEFAULTS, **json.load(f)}

    if not cfg.get("groq_api_key"):
        env_key = _env_api_key()
        if env_key:
            cfg["groq_api_key"] = env_key
            log.get().info("groq key loaded from .env")

    return cfg


def save(cfg):
    with open(_path(), "w") as f:
        json.dump(cfg, f, indent=2)
