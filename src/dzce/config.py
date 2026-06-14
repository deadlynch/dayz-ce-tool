"""Tiny persistent config so dzce remembers your mission between runs.

Stored as JSON at $XDG_CONFIG_HOME/dzce/config.json (usually
~/.config/dzce/config.json). The only thing kept today is the last mission
folder used, so you can run plain `dzce` without re-typing --mission each time.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "dzce" / "config.json"


def load() -> dict:
    p = config_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(cfg: dict) -> bool:
    p = config_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def get_last_mission() -> str | None:
    return load().get("last_mission")


def set_last_mission(path: str) -> None:
    cfg = load()
    if cfg.get("last_mission") == path:
        return
    cfg["last_mission"] = path
    save(cfg)
