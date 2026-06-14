"""Curated 'item groups' -- semantic bundles for things DayZ doesn't categorize.

DayZ's vanilla categories are coarse (tools, containers, food, weapons, ...), so
medical supplies live under 'tools', base-building items are scattered across
'tools'/'containers'/uncategorized, etc. These groups let dzce reliably target
"all medical" or "all base-building" by classname pattern regardless of how the
server categorized them.

Matching is case-insensitive glob (fnmatch) on the item name, OR membership in
one of the group's categories. Patterns are intentionally broad (substring-style
``*x*``) to also catch modded variants. They're not perfect -- a mod can always
use an unusual name -- but they're extensible: add patterns here.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from .models import LootType


@dataclass
class ItemGroup:
    key: str
    title: str
    description: str
    name_globs: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


GROUPS: dict[str, ItemGroup] = {
    "medical": ItemGroup(
        "medical", "Medical supplies",
        "Bandages, meds, blood, antibiotics -- spread across 'tools' in vanilla.",
        name_globs=[
            "*bandage*", "*morphine*", "*epinephrine*", "*saline*", "*bloodbag*",
            "*bloodtest*", "*ivstart*", "*antibiotic*", "*tetracycline*",
            "*disinfect*", "*alcoholtincture*", "*vitamin*", "*charcoal*",
            "*painkiller*", "*defibrillator*", "*splint*", "*suture*",
            "*surgicalgloves*", "*thermometer*", "*firstaid*", "*medkit*",
            "*ducttape*",
        ],
    ),
    "building": ItemGroup(
        "building", "Base-building materials",
        "Nails, planks, fences, wire, locks -- DayZ has no base-building category.",
        name_globs=[
            "*nail*", "*plank*", "*woodenlog*", "*lumber*", "*fence*",
            "*watchtower*", "*metalwire*", "*barbedwire*", "*burlap*", "*rope*",
            "*sheetmetal*", "*combinationlock*", "*netting*", "*camonet*",
            "*territoryflag*", "*tarp*", "*shelterkit*", "*gardenplot*",
            "*stickbundle*", "*firewood*", "*hescobox*",
        ],
    ),
    "ammo": ItemGroup(
        "ammo", "Ammunition",
        "Loose rounds and ammo boxes.",
        name_globs=["ammo_*", "*ammobox*", "ammobox_*"],
    ),
    "magazines": ItemGroup(
        "magazines", "Magazines",
        "Detachable weapon magazines.",
        name_globs=["mag_*", "*_mag", "*magazine*"],
    ),
    "optics": ItemGroup(
        "optics", "Optics & sights",
        "Scopes and red-dots.",
        name_globs=["*optic*", "*scope*", "*reflex*", "*pso*", "*acog*"],
    ),
}


def resolve(types: list[LootType], key: str) -> list[LootType]:
    """Return the items in ``types`` that belong to the named group."""
    g = GROUPS[key]
    globs = [p.lower() for p in g.name_globs]
    out: list[LootType] = []
    for lt in types:
        if g.categories and lt.category in g.categories:
            out.append(lt)
            continue
        nm = lt.name.lower()
        if any(fnmatch.fnmatch(nm, pat) for pat in globs):
            out.append(lt)
    return out
