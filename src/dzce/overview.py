"""Consolidated 'state of the server' overview -- the first thing to run.

Pulls a read-only snapshot of the whole Central Economy in one shot: files
present, mods registered, loot by category/tier (stock and merged with mods),
events, event groups, spawnable attachments/cargo, key globals, and a health
line from the validator. Nothing is modified.
"""
from __future__ import annotations

from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from . import xmlio
from .console import console
from .files.economycore_file import EconomyCoreFile
from .files.eventgroups_file import EventGroupsFile
from .files.events_file import EventsFile
from .files.globals_file import GlobalsFile
from .files.spawnabletypes_file import SpawnableTypesFile
from .files.types_file import TypesFile
from .mission import Mission
from .models import LootType
from .validate import validate as run_validate

# Globals worth surfacing at a glance, if present.
KEY_GLOBALS = (
    "ZombieMaxCount", "AnimalMaxCount", "CleanupLifetimeDefault",
    "InitialSpawn", "ZoneSpawnDist", "TimeLogin",
)


def _safe(fn, default):
    try:
        return fn()
    except (OSError, ValueError, KeyError):
        return default


def _registered_type_files(mission: Mission) -> list[tuple[str, Path]]:
    """(folder, path) for every types file referenced in cfgeconomycore.xml."""
    out: list[tuple[str, Path]] = []
    if not mission.has("economycore"):
        return out
    core = _safe(lambda: EconomyCoreFile(mission.path("economycore")), None)
    if core is None:
        return out
    for folder, files in core.ce_includes():
        for fname in files:
            p = mission.root / folder / fname
            if p.exists():
                out.append((folder, p))
    return out


def _types_from(path: Path) -> list[LootType]:
    tree = _safe(lambda: xmlio.load(path), None)
    if tree is None:
        return []
    return [LootType.from_element(el) for el in tree.getroot().findall("type")]


def _category_counts(types: list[LootType]) -> dict[str, tuple[int, int]]:
    agg: dict[str, tuple[int, int]] = {}
    for lt in types:
        cat = lt.category or "(none)"
        c, n = agg.get(cat, (0, 0))
        agg[cat] = (c + 1, n + lt.nominal)
    return agg


def gather_economy(mission: Mission) -> dict:
    """Read-only snapshot of the loot economy: stock types, mod types, the
    merged set, and the (folder, path) list of mod CE folders."""
    type_files = _registered_type_files(mission)
    mods = [(f, p) for f, p in type_files if f != "db"]
    stock = _types_from(mission.path("types")) if mission.has("types") else []
    mod_types: list[LootType] = []
    for _folder, path in mods:
        mod_types += _types_from(path)
    return {"stock": stock, "mods": mod_types,
            "merged": stock + mod_types, "mod_folders": mods}


def render_overview(mission: Mission) -> None:
    console.print(Panel.fit(
        f"[accent]{mission.map_name}[/accent]\n{mission.root}",
        title="Server overview"))

    # --- files present --------------------------------------------------
    present = [k for k in ("types", "globals", "events", "economycore",
                           "spawnabletypes", "limitsdefinition", "limitsuser",
                           "eventgroups")
               if mission.has(k)]
    console.print(f"[field]Files present:[/field] {', '.join(present)}")

    # --- mods (CE folders) ----------------------------------------------
    type_files = _registered_type_files(mission)
    mods = [(f, p) for f, p in type_files if f != "db"]
    if mods:
        mt = Table("mod CE folder", "loot entries", title="Mods registered")
        for folder, path in mods:
            mt.add_row(folder, str(len(_types_from(path))))
        console.print(mt)
    else:
        console.print("[muted]No mod CE folders registered.[/muted]")

    # --- loot: stock vs merged ------------------------------------------
    stock = _types_from(mission.path("types")) if mission.has("types") else []
    merged = list(stock)
    for folder, path in mods:
        merged += _types_from(path)

    stock_cat = _category_counts(stock)
    merged_cat = _category_counts(merged)
    lt = Table("category", "stock items", "all items", "total nominal",
               title="Loot by category")
    for cat in sorted(merged_cat, key=lambda c: -merged_cat[c][1]):
        s_items = stock_cat.get(cat, (0, 0))[0]
        m_items, m_nom = merged_cat[cat]
        lt.add_row(cat, str(s_items), str(m_items), str(m_nom))
    console.print(lt)
    console.print(f"[field]Total loot types:[/field] {len(merged)} "
                  f"(stock {len(stock)}, mods {len(merged) - len(stock)})    "
                  f"[field]total nominal:[/field] {sum(x.nominal for x in merged)}")

    # --- tiers ----------------------------------------------------------
    tier_counts: dict[str, int] = {}
    for x in merged:
        for v in (x.values or ["(untiered)"]):
            tier_counts[v] = tier_counts.get(v, 0) + 1
    if tier_counts:
        console.print("[field]Tiers:[/field] " + "  ".join(
            f"{k}={v}" for k, v in sorted(tier_counts.items())))

    # --- events ---------------------------------------------------------
    if mission.has("events"):
        ev = _safe(lambda: EventsFile(mission.path("events")).summary(), {})
        if ev:
            console.print(f"[field]Events:[/field] zombies={ev.get('zombies', 0)} "
                          f"animals={ev.get('animals', 0)} "
                          f"vehicles={ev.get('vehicles', 0)} "
                          f"(total {ev.get('total', 0)})")

    # --- event groups ---------------------------------------------------
    if mission.has("eventgroups"):
        eg = _safe(lambda: EventGroupsFile(mission.path("eventgroups")).summary(), {})
        if eg:
            console.print(f"[field]Event groups:[/field] {eg.get('groups', 0)} "
                          f"groups, {eg.get('children', 0)} objects")

    # --- spawnables -----------------------------------------------------
    if mission.has("spawnabletypes"):
        stp = _safe(lambda: SpawnableTypesFile(mission.path("spawnabletypes")), None)
        if stp is not None:
            att = len(stp.chance_rows("attachments"))
            car = len(stp.chance_rows("cargo"))
            dups = stp.duplicate_names()
            line = (f"[field]Spawnables:[/field] {len(stp.names())} entries, "
                    f"{att} attachment groups, {car} cargo groups")
            if dups:
                line += f"  [warn]({len(dups)} duplicate entr{'y' if len(dups)==1 else 'ies'})[/warn]"
            console.print(line)

    # --- globals --------------------------------------------------------
    if mission.has("globals"):
        g = _safe(lambda: GlobalsFile(mission.path("globals")), None)
        if g is not None:
            shown = [(k, g.get(k)) for k in KEY_GLOBALS if g.get(k) is not None]
            if shown:
                console.print("[field]Globals:[/field] " +
                              "  ".join(f"{k}={v}" for k, v in shown))

    # --- health ---------------------------------------------------------
    findings = _safe(lambda: run_validate(mission), [])
    errors = sum(1 for f in findings if f.level == "error")
    warns = len(findings) - errors
    if not findings:
        console.print("[ok]Health: no problems found.[/ok]")
    else:
        style = "err" if errors else "warn"
        console.print(f"[{style}]Health: {errors} error(s), {warns} warning(s)[/{style}]"
                      "  -- run `dzce validate` for details.")
