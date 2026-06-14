"""Handler for db/events.xml -- dynamic events.

This single file drives infected (zombies), animals, and vehicles, plus loot
events (heli crashes, etc.). Each ``<event name="...">`` carries nominal / min /
max counts, lifetime, restock, an ``active`` flag and a ``<children>`` list of
spawnable classnames. Naming convention: ``Infected*`` = zombies, ``Animal*`` =
wildlife, ``Vehicle*`` = cars/boats.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .. import xmlio

KIND_PREFIXES = {
    "zombies": ("Infected",),
    "animals": ("Animal",),
    "vehicles": ("Vehicle",),
}


class EventsFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <events>

    def events(self) -> list[etree._Element]:
        return self.root.findall("event")

    def names(self) -> list[str]:
        return [e.get("name") for e in self.events()]

    def by_kind(self, kind: str) -> list[etree._Element]:
        prefixes = KIND_PREFIXES.get(kind)
        if not prefixes:
            raise KeyError(f"unknown kind {kind!r}; use one of {list(KIND_PREFIXES)}")
        return [e for e in self.events() if (e.get("name") or "").startswith(prefixes)]

    def get(self, name: str) -> etree._Element | None:
        for e in self.events():
            if e.get("name") == name:
                return e
        return None

    def _scale_int_child(self, ev: etree._Element, tag: str, factor: float,
                         minimum: int = 0) -> None:
        node = ev.find(tag)
        if node is None or node.text is None:
            return
        try:
            cur = int(node.text.strip())
        except ValueError:
            return
        if cur <= 0:  # -1 / 0 are sentinels; leave untouched
            return
        node.text = str(max(minimum, round(cur * factor)))

    def scale(self, events: list[etree._Element], factor: float) -> int:
        """Scale nominal/min/max of the given events by ``factor``. Returns count."""
        for ev in events:
            for tag in ("nominal", "min", "max"):
                self._scale_int_child(ev, tag, factor, minimum=0)
        return len(events)

    def set_field(self, name: str, tag: str, value: str | int) -> bool:
        ev = self.get(name)
        if ev is None:
            return False
        node = ev.find(tag)
        if node is None:
            node = etree.SubElement(ev, tag)
        node.text = str(value)
        return True

    def summary(self) -> dict[str, int]:
        out = {}
        for kind in KIND_PREFIXES:
            out[kind] = len(self.by_kind(kind))
        out["total"] = len(self.events())
        return out

    def save(self) -> None:
        xmlio.save(self.tree, self.path)
