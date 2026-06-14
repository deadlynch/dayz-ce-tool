"""Cross-file validation: catch the mistakes DayZ fails silently on."""
from __future__ import annotations

from dataclasses import dataclass

from .files.limitsdef_file import LimitsDefinitionFile
from .files.types_file import TypesFile
from .mission import Mission


@dataclass
class Finding:
    level: str  # "error" | "warn"
    where: str
    message: str


def validate(mission: Mission) -> list[Finding]:
    findings: list[Finding] = []

    if not mission.has("types"):
        return [Finding("error", "mission", "db/types.xml not found")]

    types = TypesFile(mission.path("types"))

    limits = None
    known_usages: set[str] = set()
    known_tiers: set[str] = set()
    if mission.has("limitsdefinition"):
        limits = LimitsDefinitionFile(mission.path("limitsdefinition"))
        known_usages = set(limits.usages)
        known_tiers = set(limits.tiers)
        if mission.has("limitsuser"):
            from .files.limitsuser_file import LimitsUserFile
            try:
                user = LimitsUserFile(mission.path("limitsuser"))
                known_usages |= user.usages
                known_tiers |= user.tiers
            except (OSError, ValueError):
                pass

    seen: set[str] = set()
    for lt in types.all():
        ctx = f"types.xml:{lt.name}"
        if lt.name in seen:
            findings.append(Finding("error", ctx, "duplicate type name"))
        seen.add(lt.name)

        if lt.min > lt.nominal and lt.nominal > 0:
            findings.append(Finding("warn", ctx, f"min({lt.min}) > nominal({lt.nominal})"))
        if lt.nominal > 0 and lt.lifetime <= 0:
            findings.append(Finding("warn", ctx, "nominal > 0 but lifetime <= 0"))

        if limits is not None:
            if lt.category and lt.category not in limits.categories:
                findings.append(Finding("error", ctx, f"unknown category '{lt.category}'"))
            for u in lt.usages:
                if u not in known_usages:
                    findings.append(Finding("error", ctx, f"unknown usage '{u}'"))
            for v in lt.values:
                if v not in known_tiers:
                    findings.append(Finding("error", ctx, f"unknown tier '{v}'"))
            if not lt.usages and not lt.values and lt.nominal > 0:
                findings.append(Finding(
                    "warn", ctx,
                    "no usage and no tier -> item may never find a spawn point"))

    # cfgspawnabletypes.xml: duplicate <type> entries are a common mod defect
    if mission.has("spawnabletypes"):
        from .files.spawnabletypes_file import SpawnableTypesFile
        try:
            stp = SpawnableTypesFile(mission.path("spawnabletypes"))
            for dup in stp.duplicate_names():
                findings.append(Finding(
                    "warn", f"cfgspawnabletypes.xml:{dup}",
                    "duplicate <type> entry -- DayZ keeps only one; remove the extra"))
        except (OSError, ValueError):
            pass

    # cfgeconomycore.xml: every linked CE file must exist and be valid XML.
    # On a modded server this catches a broken mod file across ALL mods at once.
    if mission.has("economycore"):
        from . import xmlio
        from .files.economycore_file import EconomyCoreFile
        try:
            core = EconomyCoreFile(mission.path("economycore"))
        except (OSError, ValueError):
            core = None
        if core is not None:
            for folder, fname, ftype in core.ce_all_files():
                p = mission.root / folder / fname
                ctx = f"cfgeconomycore.xml -> {folder}/{fname}"
                if not p.exists():
                    findings.append(Finding(
                        "error", ctx, "linked CE file is missing (won't load)"))
                    continue
                try:
                    xmlio.load(p)
                except xmlio.CEParseError:
                    extra = ("  run: dzce mod wrap " + fname
                             if xmlio.looks_like_unwrapped_fragment(p) else "")
                    findings.append(Finding(
                        "error", ctx, "linked CE file is invalid XML, so DayZ "
                        "skips it" + extra))
                except (OSError, ValueError):
                    findings.append(Finding("error", ctx, "linked CE file is invalid"))

    return findings
