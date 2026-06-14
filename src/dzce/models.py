"""Typed models mapping CE XML elements to Python objects and back."""
from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

# ---------------------------------------------------------------------------
# types.xml
# ---------------------------------------------------------------------------

FLAG_KEYS = (
    "count_in_cargo",
    "count_in_hoarder",
    "count_in_map",
    "count_in_player",
    "crafted",
    "deloot",
)


@dataclass
class Flags:
    count_in_cargo: int = 0
    count_in_hoarder: int = 0
    count_in_map: int = 1
    count_in_player: int = 0
    crafted: int = 0
    deloot: int = 0

    @classmethod
    def from_element(cls, el: etree._Element | None) -> "Flags":
        if el is None:
            return cls()
        return cls(**{k: int(el.get(k, "0")) for k in FLAG_KEYS})

    def apply_to(self, el: etree._Element) -> None:
        for k in FLAG_KEYS:
            el.set(k, str(getattr(self, k)))


@dataclass
class LootType:
    """One ``<type>`` entry from types.xml."""

    name: str
    nominal: int = 0
    lifetime: int = 3600
    restock: int = 0
    min: int = 0
    quantmin: int = -1
    quantmax: int = -1
    cost: int = 100
    flags: Flags = field(default_factory=Flags)
    category: str | None = None
    usages: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)  # tiers
    tags: list[str] = field(default_factory=list)
    _el: etree._Element | None = field(default=None, repr=False, compare=False)

    _INT_FIELDS = ("nominal", "lifetime", "restock", "min", "quantmin", "quantmax", "cost")

    @classmethod
    def from_element(cls, el: etree._Element) -> "LootType":
        def text(tag: str, default: int) -> int:
            node = el.find(tag)
            if node is None or node.text is None or node.text.strip() == "":
                return default
            return int(node.text.strip())

        return cls(
            name=el.get("name", ""),
            nominal=text("nominal", 0),
            lifetime=text("lifetime", 3600),
            restock=text("restock", 0),
            min=text("min", 0),
            quantmin=text("quantmin", -1),
            quantmax=text("quantmax", -1),
            cost=text("cost", 100),
            flags=Flags.from_element(el.find("flags")),
            category=(el.find("category").get("name") if el.find("category") is not None else None),
            usages=[u.get("name") for u in el.findall("usage")],
            values=[v.get("name") for v in el.findall("value")],
            tags=[t.get("name") for t in el.findall("tag")],
            _el=el,
        )

    def write_back(self) -> None:
        """Push current field values onto the backing element in place."""
        if self._el is None:
            raise RuntimeError("LootType has no backing element; build one first")
        el = self._el
        for f in self._INT_FIELDS:
            node = el.find(f)
            if node is None:
                node = etree.SubElement(el, f)
            node.text = str(getattr(self, f))
        flags = el.find("flags")
        if flags is None:
            flags = etree.SubElement(el, "flags")
        self.flags.apply_to(flags)
        el.set("name", self.name)
