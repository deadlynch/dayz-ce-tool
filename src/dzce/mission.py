"""Locate and describe a DayZ mission folder and its Central Economy files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Known stock mission folder names per map.
KNOWN_MISSIONS = ("dayzOffline.chernarusplus", "dayzOffline.enoch")

# Files that live at the mission root.
ROOT_FILES = {
    "economycore": "cfgeconomycore.xml",
    "spawnabletypes": "cfgspawnabletypes.xml",
    "limitsdefinition": "cfglimitsdefinition.xml",
    "limitsuser": "cfglimitsdefinitionuser.xml",
    "eventspawns": "cfgeventspawns.xml",
    "eventgroups": "cfgeventgroups.xml",
    "randompresets": "cfgrandompresets.xml",
    "environment": "cfgenvironment.xml",
    "gameplay": "cfggameplay.json",
}

# Files that live under db/.
DB_FILES = {
    "types": "db/types.xml",
    "globals": "db/globals.xml",
    "events": "db/events.xml",
    "economy": "db/economy.xml",
    "messages": "db/messages.xml",
}


@dataclass
class Mission:
    root: Path

    def path(self, key: str) -> Path:
        if key in ROOT_FILES:
            return self.root / ROOT_FILES[key]
        if key in DB_FILES:
            return self.root / DB_FILES[key]
        raise KeyError(f"unknown CE file key: {key}")

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    def present_files(self) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for key in {**ROOT_FILES, **DB_FILES}:
            p = self.path(key)
            if p.exists():
                out[key] = p
        return out

    @property
    def map_name(self) -> str:
        return self.root.name


def looks_like_mission(folder: Path) -> bool:
    return (folder / "db" / "types.xml").exists() or (folder / "cfgeconomycore.xml").exists()


def discover(start: Path | None = None) -> Mission | None:
    """Find a mission folder from a start dir: the dir itself, a child, or an mpmissions tree."""
    start = (Path(start) if start else Path.cwd()).resolve()
    candidates: list[Path] = [start]
    candidates += [start / name for name in KNOWN_MISSIONS]
    mp = start / "mpmissions"
    if mp.is_dir():
        candidates += [c for c in mp.iterdir() if c.is_dir()]
    candidates += [c for c in start.iterdir() if c.is_dir()] if start.is_dir() else []
    for c in candidates:
        if c.is_dir() and looks_like_mission(c):
            return Mission(c.resolve())
    return None
