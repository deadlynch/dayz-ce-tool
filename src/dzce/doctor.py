"""dzce doctor -- heuristic, qualitative health analysis of the economy.

Unlike `validate` (hard correctness errors) and `overview` (raw numbers), the
doctor applies rules-of-thumb to surface *suspicions* worth a human's attention,
each with the reasoning and a suggested action. DayZ economies have no single
'correct' shape, so every finding is advisory, the thresholds are shown, and
nothing here modifies any file.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from rich.table import Table

from .console import console
from .files.limitsdef_file import LimitsDefinitionFile
from .files.spawnabletypes_file import SpawnableTypesFile
from .mission import Mission
from .models import LootType
from .overview import gather_economy

# Tunable heuristic thresholds (shown to the user so the logic is transparent).
OUTLIER_RATIO = 5.0          # item nominal > N x its category median = outlier
OUTLIER_MIN_ABS = 30         # ...and at least this big, to avoid noise on tiny cats
MOD_FLOOD_RATIO = 2.0        # mod nominal in a category > N x stock = flooding
BIG_ECONOMY_NOMINAL = 60000  # total nominal above which to note perf risk


@dataclass
class Finding:
    level: str           # "warn" | "info"
    area: str
    message: str
    suggestion: str = ""


def _referenced(types: list[LootType], attr: str) -> set[str]:
    out: set[str] = set()
    for lt in types:
        out |= set(getattr(lt, attr))
    return out


def diagnose(mission: Mission) -> list[Finding]:
    eco = gather_economy(mission)
    stock: list[LootType] = eco["stock"]
    mods: list[LootType] = eco["mods"]
    merged: list[LootType] = eco["merged"]
    findings: list[Finding] = []

    if not merged:
        return [Finding("warn", "loot", "No loot types found at all.",
                        "Check that db/types.xml exists and is registered.")]

    # --- declared-but-unused vocabulary (dead zones) --------------------
    if mission.has("limitsdefinition"):
        try:
            limits = LimitsDefinitionFile(mission.path("limitsdefinition"))
            decl_usages, decl_tiers = set(limits.usages), set(limits.tiers)
            decl_cats = set(limits.categories)
            if mission.has("limitsuser"):
                from .files.limitsuser_file import LimitsUserFile
                u = LimitsUserFile(mission.path("limitsuser"))
                decl_usages |= u.usages
                decl_tiers |= u.tiers
            used_usages = _referenced(merged, "usages")
            used_tiers = _referenced(merged, "values")
            used_cats = {lt.category for lt in merged if lt.category}
            for u in sorted(decl_usages - used_usages):
                findings.append(Finding(
                    "warn", "dead usage",
                    f"usage '{u}' is declared but no loot uses it",
                    "buildings tagged with this usage will spawn nothing"))
            for t in sorted(decl_tiers - used_tiers):
                findings.append(Finding(
                    "warn", "dead tier",
                    f"tier '{t}' is declared but no loot uses it",
                    "that map zone tier will have no tiered loot"))
            for c in sorted(decl_cats - used_cats):
                findings.append(Finding(
                    "info", "empty category",
                    f"category '{c}' is declared but has no items", ""))
        except (OSError, ValueError):
            pass

    # --- items that can't spawn -----------------------------------------
    cant_spawn = [lt for lt in merged
                  if lt.nominal > 0 and not lt.usages and not lt.values
                  and not lt.name.lower().startswith(("ammo_", "mag_"))]
    if cant_spawn:
        sample = ", ".join(lt.name for lt in cant_spawn[:5])
        findings.append(Finding(
            "warn", "unreachable loot",
            f"{len(cant_spawn)} item(s) have nominal>0 but no usage and no tier "
            f"(e.g. {sample})",
            "give them a usage/tier, or they only spawn via events/cargo"))

    # --- no restock headroom (min >= nominal) ---------------------------
    tight = [lt for lt in merged if lt.nominal > 0 and lt.min >= lt.nominal]
    if tight:
        findings.append(Finding(
            "warn", "no headroom",
            f"{len(tight)} item(s) have min >= nominal",
            "set min below nominal so the CE isn't always at the restock floor"))

    # --- per-item nominal outliers --------------------------------------
    by_cat: dict[str, list[LootType]] = {}
    for lt in merged:
        by_cat.setdefault(lt.category or "(none)", []).append(lt)
    outliers: list[tuple[str, int, str]] = []
    for cat, items in by_cat.items():
        noms = [i.nominal for i in items if i.nominal > 0]
        if len(noms) < 4:
            continue
        med = statistics.median(noms)
        if med <= 0:
            continue
        for i in items:
            if i.nominal >= OUTLIER_MIN_ABS and i.nominal > OUTLIER_RATIO * med:
                outliers.append((i.name, i.nominal, cat))
    for name, nom, cat in sorted(outliers, key=lambda x: -x[1])[:8]:
        findings.append(Finding(
            "warn", "nominal outlier",
            f"'{name}' nominal={nom} is far above the '{cat}' median",
            f"more than {OUTLIER_RATIO:g}x the category median -- likely a typo"))

    # --- mod flooding by category ---------------------------------------
    stock_cat = {c: sum(x.nominal for x in stock if (x.category or '(none)') == c)
                 for c in {x.category or '(none)' for x in stock}}
    mod_cat = {c: sum(x.nominal for x in mods if (x.category or '(none)') == c)
               for c in {x.category or '(none)' for x in mods}}
    for cat, mod_nom in mod_cat.items():
        stock_nom = stock_cat.get(cat, 0)
        if stock_nom > 0 and mod_nom > MOD_FLOOD_RATIO * stock_nom:
            findings.append(Finding(
                "warn", "mod flooding",
                f"mods add nominal {mod_nom} in '{cat}' vs stock {stock_nom}",
                f"more than {MOD_FLOOD_RATIO:g}x stock -- consider "
                "`dzce mod add ... --baseline merged` to rebalance"))

    # --- weapons that spawn empty (no spawnable entry) ------------------
    if mission.has("spawnabletypes"):
        try:
            stp_names = SpawnableTypesFile(mission.path("spawnabletypes")).names()
            empty_guns = [lt.name for lt in merged
                          if lt.category == "weapons"
                          and not lt.name.lower().startswith(("ammo_", "mag_"))
                          and lt.name not in stp_names]
            if empty_guns:
                sample = ", ".join(empty_guns[:5])
                findings.append(Finding(
                    "warn", "empty weapons",
                    f"{len(empty_guns)} weapon(s) have no cfgspawnabletypes entry "
                    f"(e.g. {sample})",
                    "they spawn with no magazine -- add an attachment group"))
        except (OSError, ValueError):
            pass

    # --- overall economy size (perf) ------------------------------------
    total = sum(lt.nominal for lt in merged)
    if total > BIG_ECONOMY_NOMINAL:
        findings.append(Finding(
            "info", "economy size",
            f"total nominal across all loot is {total}",
            f"above ~{BIG_ECONOMY_NOMINAL} can stress CE/server on lower-end hosts"))

    return findings


def run_doctor(mission: Mission) -> None:
    findings = diagnose(mission)
    if not findings:
        console.print("[ok]Doctor: nothing suspicious. Your economy looks sane.[/ok]")
        return
    warns = [f for f in findings if f.level == "warn"]
    infos = [f for f in findings if f.level == "info"]
    t = Table("", "area", "finding", "suggestion")
    for f in warns + infos:
        mark = "[warn]\u26a0[/warn]" if f.level == "warn" else "[info]i[/info]"
        t.add_row(mark, f.area, f.message, f.suggestion or "")
    console.print(t)
    console.print(f"\n{len(warns)} suspicion(s), {len(infos)} note(s). "
                  "[muted]Heuristic only -- advisory, not errors.[/muted]")
