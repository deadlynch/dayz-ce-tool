"""Handler for db/types.xml -- the master loot table."""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .. import xmlio
from ..models import LootType


class TypesFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <types>
        self._index: dict[str, LootType] = {}
        self.reload_index()

    def reload_index(self) -> None:
        self._index = {}
        for el in self.root.findall("type"):
            lt = LootType.from_element(el)
            if lt.name:
                self._index[lt.name] = lt

    # -- queries ----------------------------------------------------------
    def all(self) -> list[LootType]:
        return list(self._index.values())

    def get(self, name: str) -> LootType | None:
        return self._index.get(name)

    def select(
        self,
        *,
        name_glob: str | None = None,
        category: str | None = None,
        usage: str | None = None,
        tier: str | None = None,
    ) -> list[LootType]:
        import fnmatch

        out = []
        for lt in self._index.values():
            if name_glob and not fnmatch.fnmatch(lt.name.lower(), name_glob.lower()):
                continue
            if category and lt.category != category:
                continue
            if usage and usage not in lt.usages:
                continue
            if tier and tier not in lt.values:
                continue
            out.append(lt)
        return out

    def categories(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for lt in self._index.values():
            out[lt.category or "(none)"] = out.get(lt.category or "(none)", 0) + 1
        return dict(sorted(out.items()))

    def tiers(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for lt in self._index.values():
            for v in lt.values or ["(none)"]:
                out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items()))

    # -- mutations --------------------------------------------------------
    def upsert(self, lt: LootType) -> None:
        """Insert a new type or write changes back onto its existing element."""
        if lt._el is not None and lt.name in self._index:
            lt.write_back()
            self._index[lt.name] = lt
            return
        el = self._build_element(lt)
        self.root.append(el)
        xmlio.indent_like_siblings(self.root, el)
        lt._el = el
        self._index[lt.name] = lt

    def remove(self, name: str) -> bool:
        lt = self._index.pop(name, None)
        if lt is None or lt._el is None:
            return False
        self.root.remove(lt._el)
        return True

    def _build_element(self, lt: LootType) -> etree._Element:
        el = etree.Element("type", name=lt.name)
        for tag in LootType._INT_FIELDS:
            child = etree.SubElement(el, tag)
            child.text = str(getattr(lt, tag))
        flags = etree.SubElement(el, "flags")
        lt.flags.apply_to(flags)
        if lt.category:
            etree.SubElement(el, "category", name=lt.category)
        for t in lt.tags:
            etree.SubElement(el, "tag", name=t)
        for u in lt.usages:
            etree.SubElement(el, "usage", name=u)
        for v in lt.values:
            etree.SubElement(el, "value", name=v)
        return el

    def save(self) -> None:
        xmlio.save(self.tree, self.path)
