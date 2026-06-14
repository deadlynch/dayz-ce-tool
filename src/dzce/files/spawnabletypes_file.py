"""Handler for cfgspawnabletypes.xml -- attachments & cargo on spawned items.

This decides what a weapon spawns *with* (magazine, optic) and what a container
spawns *inside* it. A modded rifle with no entry here spawns bone-dry with no
magazine -- which players read as "broken loot".
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .. import xmlio


class SpawnableTypesFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <spawnabletypes>

    def names(self) -> set[str]:
        return {t.get("name") for t in self.root.findall("type") if t.get("name")}

    def duplicate_names(self) -> list[str]:
        """Type names that appear more than once -- a real defect in many mod
        files (e.g. a copy-paste leaving two identical entries). DayZ keeps only
        one, so the duplicate is dead weight and a sign of an editing mistake."""
        seen: dict[str, int] = {}
        for t in self.root.findall("type"):
            n = t.get("name")
            if n:
                seen[n] = seen.get(n, 0) + 1
        return sorted(n for n, c in seen.items() if c > 1)

    def has(self, name: str) -> bool:
        return name in self.names()

    def get(self, name: str) -> etree._Element | None:
        for t in self.root.findall("type"):
            if t.get("name") == name:
                return t
        return None

    def add_with_attachment_group(self, name: str, attachments: list[str],
                                  chance: float = 1.0) -> etree._Element:
        """Create a ``<type>`` giving ``name`` one attachment slot picking among
        ``attachments`` (e.g. compatible magazines). Existing entry is replaced,
        but any existing ``<damage>`` range is preserved."""
        old = self.get(name)
        damage = None
        if old is not None:
            d = old.find("damage")
            if d is not None:
                damage = (d.get("min"), d.get("max"))
            self.root.remove(old)
        t = etree.SubElement(self.root, "type", name=name)
        if damage is not None:
            etree.SubElement(t, "damage", min=damage[0] or "0", max=damage[1] or "1")
        grp = etree.SubElement(t, "attachments", chance=f"{chance:g}")
        for a in attachments:
            etree.SubElement(grp, "item", name=a, chance="1.00")
        xmlio.indent_like_siblings(self.root, t)
        return t

    def save(self) -> None:
        xmlio.save(self.tree, self.path)

    # -- attachment / cargo spawn-chance editing --------------------------
    def chance_rows(self, kind: str = "all") -> list[tuple[str, str, float]]:
        """Return (type_name, group_kind, chance) for each attachments/cargo
        group. ``kind`` is 'attachments', 'cargo' or 'all'."""
        groups = ("attachments", "cargo") if kind == "all" else (kind,)
        rows: list[tuple[str, str, float]] = []
        for t in self.root.findall("type"):
            name = t.get("name") or "?"
            for gk in groups:
                for grp in t.findall(gk):
                    c = grp.get("chance")
                    if c is not None:
                        try:
                            rows.append((name, gk, float(c)))
                        except ValueError:
                            pass
        return rows

    def scale_chances(self, factor: float, *, kind: str = "all") -> int:
        """Multiply the spawn ``chance`` of attachment/cargo groups by ``factor``,
        clamped to [0, 1]. Returns how many groups were changed."""
        groups = ("attachments", "cargo") if kind == "all" else (kind,)
        changed = 0
        for t in self.root.findall("type"):
            for gk in groups:
                for grp in t.findall(gk):
                    c = grp.get("chance")
                    if c is None:
                        continue
                    try:
                        new = min(1.0, max(0.0, float(c) * factor))
                    except ValueError:
                        continue
                    grp.set("chance", f"{new:.2f}")
                    changed += 1
        return changed

    def set_chance(self, name: str, value: float, *, kind: str = "attachments") -> bool:
        """Set the spawn chance of one type's attachment/cargo group."""
        t = self.get(name)
        if t is None:
            return False
        value = min(1.0, max(0.0, value))
        ok_any = False
        for grp in t.findall(kind):
            grp.set("chance", f"{value:.2f}")
            ok_any = True
        return ok_any
