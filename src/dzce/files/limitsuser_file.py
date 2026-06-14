"""Handler for cfglimitsdefinitionuser.xml -- admin/mod custom vocabulary.

This sibling of cfglimitsdefinition.xml is where servers declare *custom* usage
and value (tier) names without touching the stock file. Each top-level entry is
an alias that expands to base usages/values::

    <user>
        <usagevalues>
            <usage name="Bunker"><usage name="Military"/></usage>
        </usagevalues>
        <valuevalues>
            <value name="Tier5"><value name="Tier4"/></value>
        </valuevalues>
    </user>

For validation we only need the alias *names* (``Bunker``, ``Tier5``): a type
referencing them is legal. Ignoring this file makes a modded server look broken
when it is fine -- so dzce must union it with the stock vocabulary.
"""
from __future__ import annotations

from pathlib import Path

from .. import xmlio


class LimitsUserFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <user>

    def _top_names(self, group: str, child: str) -> set[str]:
        g = self.root.find(group)
        if g is None:
            return set()
        return {c.get("name") for c in g.findall(child) if c.get("name")}

    @property
    def usages(self) -> set[str]:
        return self._top_names("usagevalues", "usage")

    @property
    def tiers(self) -> set[str]:
        return self._top_names("valuevalues", "value")
