"""Handler for db/globals.xml -- global economy variables.

Each entry is ``<var name="..." type="0|1" value="..."/>`` where type 0 is an
integer and type 1 is a float. Notable vars: CleanupLifetimeDefault,
ZombieMaxCount, AnimalMaxCount, ZoneSpawnDist, TimeLogin, etc.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .. import xmlio


class GlobalsFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <variables>

    def _find(self, name: str) -> etree._Element | None:
        for v in self.root.findall("var"):
            if v.get("name") == name:
                return v
        return None

    def all(self) -> dict[str, str]:
        return {v.get("name"): v.get("value") for v in self.root.findall("var")}

    def get(self, name: str) -> str | None:
        el = self._find(name)
        return el.get("value") if el is not None else None

    def set(self, name: str, value: str | int | float) -> bool:
        el = self._find(name)
        if el is None:
            return False
        el.set("value", str(value))
        return True

    def save(self) -> None:
        xmlio.save(self.tree, self.path)
