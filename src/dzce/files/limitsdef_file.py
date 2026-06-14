"""Handler for cfglimitsdefinition.xml -- the controlled vocabulary.

types.xml may only reference category / usage / value(tier) / tag names that are
declared here. Anything else is dropped by the Central Economy and the item
silently never spawns -- a top cause of "broken" modded loot.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .. import xmlio

# group element name -> child element name
GROUPS = {
    "categories": "category",
    "tags": "tag",
    "usageflags": "usage",
    "valueflags": "value",
}


class LimitsDefinitionFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <lists>

    def _group(self, group: str) -> etree._Element | None:
        return self.root.find(group)

    def names(self, group: str) -> set[str]:
        g = self._group(group)
        if g is None:
            return set()
        child = GROUPS[group]
        return {c.get("name") for c in g.findall(child) if c.get("name")}

    @property
    def categories(self) -> set[str]:
        return self.names("categories")

    @property
    def usages(self) -> set[str]:
        return self.names("usageflags")

    @property
    def tiers(self) -> set[str]:
        return self.names("valueflags")

    @property
    def tags(self) -> set[str]:
        return self.names("tags")

    def add(self, group: str, name: str) -> bool:
        """Declare a new vocabulary entry. Returns False if it already exists."""
        if name in self.names(group):
            return False
        g = self._group(group)
        if g is None:
            g = etree.SubElement(self.root, group)
        el = etree.SubElement(g, GROUPS[group], name=name)
        xmlio.indent_like_siblings(g, el)
        return True

    def save(self) -> None:
        xmlio.save(self.tree, self.path)
