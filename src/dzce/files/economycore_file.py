"""Handler for cfgeconomycore.xml -- root classes and CE folder includes.

The Bohemia-sanctioned way to add modded loot is NOT to paste entries into the
stock types.xml, but to register an extra CE folder here::

    <ce folder="MyWeaponsMod">
        <file name="types.xml" type="types"/>
    </ce>

DayZ then merges that folder's types.xml into the economy at load. This keeps
mod loot isolated and update-safe.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .. import xmlio


class EconomyCoreFile:
    def __init__(self, path: Path):
        self.path = path
        self.tree = xmlio.load(path)
        self.root = self.tree.getroot()  # <economycore>

    def ce_folders(self) -> list[str]:
        return [c.get("folder") for c in self.root.findall("ce") if c.get("folder")]

    def ce_includes(self) -> list[tuple[str, list[str]]]:
        """Return (folder, [type-file names]) for every registered CE block,
        listing only files declared as type='types'."""
        out: list[tuple[str, list[str]]] = []
        for ce in self.root.findall("ce"):
            folder = ce.get("folder")
            if not folder:
                continue
            files = [f.get("name") for f in ce.findall("file")
                     if f.get("type") == "types" and f.get("name")]
            out.append((folder, files))
        return out

    def ce_all_files(self) -> list[tuple[str, str, str]]:
        """Return (folder, filename, type) for EVERY <file> linked in every CE
        block, regardless of type -- the full picture of what's wired up."""
        out: list[tuple[str, str, str]] = []
        for ce in self.root.findall("ce"):
            folder = ce.get("folder")
            if not folder:
                continue
            for f in ce.findall("file"):
                name = f.get("name")
                if name:
                    out.append((folder, name, f.get("type") or "?"))
        return out

    def has_folder(self, folder: str) -> bool:
        return folder in self.ce_folders()

    def register(self, folder: str, files: dict[str, str] | None = None) -> bool:
        """Add a ``<ce folder=...>`` block. ``files`` maps filename -> CE type.

        Returns False if the folder was already registered.
        """
        if self.has_folder(folder):
            return False
        files = files or {"types.xml": "types"}
        ce = etree.SubElement(self.root, "ce", folder=folder)
        for fname, ftype in files.items():
            etree.SubElement(ce, "file", name=fname, type=ftype)
        xmlio.indent_like_siblings(self.root, ce)
        return True

    def save(self) -> None:
        xmlio.save(self.tree, self.path)
