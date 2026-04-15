import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import config


def test_defaults_include_ui_theme():
    assert "ui_theme" in config.DEFAULTS
    assert config.DEFAULTS["ui_theme"] == "light"


def test_load_merges_missing_ui_theme(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"sleep_ms": 20}), encoding="utf-8")
    monkeypatch.setattr(config, "_path", lambda: str(p))
    cfg = config.load()
    assert cfg["ui_theme"] == "light"
    assert cfg["sleep_ms"] == 20


def test_save_roundtrip_ui_theme(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    monkeypatch.setattr(config, "_path", lambda: str(p))
    cfg = {**config.DEFAULTS, "ui_theme": "dark"}
    config.save(cfg)
    cfg2 = config.load()
    assert cfg2["ui_theme"] == "dark"
