"""Mod integration & balancing engine.

Adding a weapons mod that ships nominal=50 on every gun wrecks the economy; a gun
with no magazine entry spawns empty. This engine makes a mod "play fair" with the
base loot:

  1. scan()            -- find the mod's types.xml / cfgspawnabletypes.xml
  2. register()        -- add a <ce folder> include in cfgeconomycore.xml
  3. check_vocabulary()-- ensure category/usage/tier/tag names exist (or add them)
  4. balance()         -- rewrite nominal/min/cost to match the vanilla peer group
  5. audit()           -- flag weapons that will spawn with no ammo/magazine
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import xmlio
from .balance import RARITY_PRESETS, compute_baseline
from .files.economycore_file import EconomyCoreFile
from .files.limitsdef_file import LimitsDefinitionFile
from .files.spawnabletypes_file import SpawnableTypesFile
from .files.types_file import TypesFile
from .mission import Mission
from .models import LootType


@dataclass
class ModScan:
    name: str
    folder: Path
    types_path: Path | None = None
    spawnabletypes_path: Path | None = None
    items: list[LootType] = field(default_factory=list)


@dataclass
class VocabularyReport:
    missing_categories: set[str] = field(default_factory=set)
    missing_usages: set[str] = field(default_factory=set)
    missing_tiers: set[str] = field(default_factory=set)
    missing_tags: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return not (self.missing_categories or self.missing_usages
                    or self.missing_tiers or self.missing_tags)


@dataclass
class BalanceChange:
    name: str
    before: tuple[int, int, int]
    after: tuple[int, int, int]
    peers: int


@dataclass
class DependencyIssue:
    weapon: str
    reason: str


class ModIntegrator:
    def __init__(self, mission: Mission):
        self.mission = mission

    # -- 1. scan ----------------------------------------------------------
    def scan(self, mod_path: Path) -> ModScan:
        mod_path = mod_path.resolve()
        name = mod_path.name
        scan = ModScan(name=name, folder=mod_path)
        # types.xml may sit at the mod root or under a db/ subfolder.
        for cand in (mod_path / "types.xml", mod_path / "db" / "types.xml"):
            if cand.exists():
                scan.types_path = cand
                break
        for cand in (mod_path / "cfgspawnabletypes.xml",
                     mod_path / "db" / "cfgspawnabletypes.xml"):
            if cand.exists():
                scan.spawnabletypes_path = cand
                break
        if scan.types_path:
            tree = xmlio.load(scan.types_path)
            scan.items = [LootType.from_element(el) for el in tree.getroot().findall("type")]
        return scan

    # -- 2. register ------------------------------------------------------
    def register(self, scan: ModScan, *, dest_folder: str | None = None) -> bool:
        folder = dest_folder or scan.name
        core = EconomyCoreFile(self.mission.path("economycore"))
        added = core.register(folder)
        if added:
            core.save()
        return added

    # -- 3. vocabulary ----------------------------------------------------
    def _known_vocab(self) -> dict[str, set[str]]:
        """Union of stock cfglimitsdefinition.xml and the custom
        cfglimitsdefinitionuser.xml, so custom mod tags aren't false-flagged."""
        limits = LimitsDefinitionFile(self.mission.path("limitsdefinition"))
        categories = set(limits.categories)
        usages = set(limits.usages)
        tiers = set(limits.tiers)
        tags = set(limits.tags)
        if self.mission.has("limitsuser"):
            from .files.limitsuser_file import LimitsUserFile
            try:
                user = LimitsUserFile(self.mission.path("limitsuser"))
                usages |= user.usages
                tiers |= user.tiers
            except (OSError, ValueError):
                pass
        return {"categories": categories, "usages": usages,
                "tiers": tiers, "tags": tags}

    def check_vocabulary(self, scan: ModScan) -> VocabularyReport:
        vocab = self._known_vocab()
        rep = VocabularyReport()
        for it in scan.items:
            if it.category and it.category not in vocab["categories"]:
                rep.missing_categories.add(it.category)
            rep.missing_usages |= {u for u in it.usages if u not in vocab["usages"]}
            rep.missing_tiers |= {v for v in it.values if v not in vocab["tiers"]}
            rep.missing_tags |= {t for t in it.tags if t not in vocab["tags"]}
        return rep

    def fix_vocabulary(self, rep: VocabularyReport) -> int:
        limits = LimitsDefinitionFile(self.mission.path("limitsdefinition"))
        n = 0
        for name in rep.missing_categories:
            n += limits.add("categories", name)
        for name in rep.missing_usages:
            n += limits.add("usageflags", name)
        for name in rep.missing_tiers:
            n += limits.add("valueflags", name)
        for name in rep.missing_tags:
            n += limits.add("tags", name)
        if n:
            limits.save()
        return n

    # -- 4. balance against existing loot --------------------------------
    def _baseline_types(self, exclude_folder: str | None = None) -> list[LootType]:
        """Collect LootTypes that define the 'existing economy' baseline: stock
        db/types.xml plus every other CE folder registered in cfgeconomycore.xml
        (so a new mod is balanced against loot that's already live), excluding
        the mod currently being integrated."""
        out: list[LootType] = []
        if self.mission.has("types"):
            out.extend(TypesFile(self.mission.path("types")).all())
        try:
            core = EconomyCoreFile(self.mission.path("economycore"))
        except (OSError, ValueError):
            return out
        for folder, files in core.ce_includes():
            if folder in ("db", exclude_folder):
                continue
            for fname in files:
                p = self.mission.root / folder / fname
                if not p.exists():
                    continue
                try:
                    tree = xmlio.load(p)
                except (OSError, ValueError):
                    continue
                out.extend(LootType.from_element(el)
                           for el in tree.getroot().findall("type"))
        return out

    def balance(self, scan: ModScan, *, rarity: str | None = None,
                baseline: str = "stock") -> list[BalanceChange]:
        """Rewrite the mod's types.xml so each item matches the existing-loot
        baseline for its category/tier. ``baseline`` is 'stock' (db/types.xml
        only) or 'merged' (stock + already-integrated mod CE folders). If
        ``rarity`` is given, force that preset instead. Writes the mod's own
        types.xml only."""
        if scan.types_path is None:
            return []
        if baseline == "merged":
            base_types = self._baseline_types(exclude_folder=scan.name)
        else:
            base_types = TypesFile(self.mission.path("types")).all()
        mod_types = TypesFile(scan.types_path)
        changes: list[BalanceChange] = []

        for lt in mod_types.all():
            before = (lt.nominal, lt.min, lt.cost)
            if rarity:
                nominal, mn, _restock, cost = RARITY_PRESETS[rarity]
                peers = 0
            else:
                base = compute_baseline(base_types, lt.category, lt.values)
                if base is None:
                    continue
                nominal, mn, cost, peers = base["nominal"], base["min"], base["cost"], base["peers"]
            lt.nominal, lt.min, lt.cost = nominal, mn, cost
            mod_types.upsert(lt)
            after = (lt.nominal, lt.min, lt.cost)
            if before != after:
                changes.append(BalanceChange(lt.name, before, after, peers))
        if changes:
            mod_types.save()
        return changes

    # -- 5. dependency audit ---------------------------------------------
    def spawnable_duplicates(self, scan: ModScan) -> list[str]:
        """Duplicate <type> entries inside the mod's own cfgspawnabletypes.xml."""
        if not scan.spawnabletypes_path:
            return []
        try:
            return SpawnableTypesFile(scan.spawnabletypes_path).duplicate_names()
        except (OSError, ValueError):
            return []

    def audit(self, scan: ModScan) -> list[DependencyIssue]:
        """Flag weapons that will spawn empty: no attachment/cargo entry in
        cfgspawnabletypes that would give them a magazine."""
        issues: list[DependencyIssue] = []
        try:
            stp = SpawnableTypesFile(self.mission.path("spawnabletypes"))
            base_spawnables = stp.names()
        except (OSError, ValueError):
            base_spawnables = set()
        mod_spawnables: set[str] = set()
        mod_spawnables_broken = False
        if scan.spawnabletypes_path:
            try:
                mod_spawnables = SpawnableTypesFile(scan.spawnabletypes_path).names()
            except (OSError, ValueError):
                mod_spawnables_broken = True
        known = base_spawnables | mod_spawnables

        if mod_spawnables_broken:
            issues.append(DependencyIssue(
                scan.spawnabletypes_path.name,
                "this file is invalid XML -- run `dzce mod wrap` on it; "
                "skipping the empty-weapon check until it's fixed",
            ))
            return issues

        for it in scan.items:
            if it.category != "weapons":
                continue
            # crude but useful: a firearm with no spawnable entry spawns empty.
            looks_like_ammo = it.name.lower().startswith(("ammo_", "mag_"))
            if looks_like_ammo:
                continue
            if it.name not in known:
                issues.append(DependencyIssue(
                    it.name,
                    "no cfgspawnabletypes entry -> spawns with no magazine/attachments",
                ))
        return issues
