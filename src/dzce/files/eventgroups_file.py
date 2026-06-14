"""Handler for cfgeventgroups.xml -- multi-object event group compositions.

Root is ``<eventgroupdef>`` with ``<group name="...">`` blocks, each holding
``<child type="..." lootmin="1" lootmax="3" deloot="0" x="" y="" z="" a=""/>``.
The x/y/z/a are world offsets and MUST NOT be touched. The safely-tunable values
are the per-child loot bounds, which control how much loot a group (convoy,
train, shipwreck, ...) carries. dzce only ever edits lootmin/lootmax here.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .. import xmlio


class EventGroupsFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <eventgroupdef>

    def groups(self) -> list[etree._Element]:
        return self.root.findall("group")

    def group_names(self) -> list[str]:
        return [g.get("name") for g in self.groups() if g.get("name")]

    def get(self, name: str) -> etree._Element | None:
        for g in self.groups():
            if g.get("name") == name:
                return g
        return None

    def summary(self) -> dict[str, int]:
        groups = self.groups()
        children = sum(len(g.findall("child")) for g in groups)
        return {"groups": len(groups), "children": children}

    def scale_loot(self, factor: float, *, group: str | None = None) -> int:
        """Scale lootmin/lootmax on group children by ``factor``. Positions are
        never touched. Returns the number of child objects affected."""
        targets = [self.get(group)] if group else self.groups()
        targets = [t for t in targets if t is not None]
        affected = 0
        for g in targets:
            for child in g.findall("child"):
                touched = False
                for attr in ("lootmin", "lootmax"):
                    val = child.get(attr)
                    if val is None:
                        continue
                    try:
                        cur = int(val)
                    except ValueError:
                        continue
                    if cur <= 0:
                        continue
                    child.set(attr, str(max(0, round(cur * factor))))
                    touched = True
                if touched:
                    affected += 1
        return affected

    def save(self) -> None:
        xmlio.save(self.tree, self.path)
