"""Safe, mechanical auto-fixes -- and a firm line about what is NOT auto-fixed.

dzce only ever auto-fixes problems whose correct resolution is unambiguous:
  * unwrapped mod fragment files  -> wrap in the right root element
  * min >= nominal (no headroom)  -> lower min below nominal

Judgment-call problems (items with no usage/tier, nominal outliers, weapons with
no magazine) are deliberately NOT touched: fixing them needs decisions only the
admin can make. The tool reports them (via `dzce doctor`) instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import xmlio
from .files.economycore_file import EconomyCoreFile
from .files.types_file import TypesFile
from .mission import Mission

# CE files we know how to wrap (and would find inside a mod folder).
_WRAPPABLE_FILENAMES = ("types.xml", "cfgspawnabletypes.xml", "cfgeventgroups.xml")


@dataclass
class FixPlan:
    wrapped: list[str] = field(default_factory=list)          # files wrapped
    unwrappable: list[str] = field(default_factory=list)      # broken, not auto-fixable
    headroom: list[tuple[str, int, int]] = field(default_factory=list)  # name, old, new

    @property
    def total(self) -> int:
        return len(self.wrapped) + len(self.headroom)


def _candidate_files(mission: Mission) -> list[Path]:
    """Every CE file worth checking: those linked in cfgeconomycore plus the
    known wrappable files sitting inside each registered mod folder."""
    seen: set[Path] = set()
    out: list[Path] = []

    def add(p: Path):
        p = p.resolve()
        if p not in seen and p.exists():
            seen.add(p)
            out.append(p)

    if mission.has("economycore"):
        try:
            core = EconomyCoreFile(mission.path("economycore"))
        except (OSError, ValueError):
            core = None
        if core is not None:
            for folder, fname, _ftype in core.ce_all_files():
                add(mission.root / folder / fname)
            for folder in {f for f, _n, _t in core.ce_all_files()}:
                for fname in _WRAPPABLE_FILENAMES:
                    add(mission.root / folder / fname)
    # the mission's own root spawnabletypes / eventgroups, in case they're broken
    for key in ("spawnabletypes", "eventgroups", "types"):
        if mission.has(key):
            add(mission.path(key))
    return out


def _type_files(mission: Mission) -> list[Path]:
    """Stock + every CE-linked types file, for headroom fixing."""
    out: list[Path] = []
    if mission.has("types"):
        out.append(mission.path("types"))
    if mission.has("economycore"):
        try:
            core = EconomyCoreFile(mission.path("economycore"))
            for folder, files in core.ce_includes():
                if folder == "db":
                    continue
                for fname in files:
                    p = mission.root / folder / fname
                    if p.exists():
                        out.append(p)
        except (OSError, ValueError):
            pass
    return out


def plan_and_apply(mission: Mission) -> FixPlan:
    """Apply the safe fixes (no-ops under xmlio.DRY_RUN) and report what changed
    or would change."""
    plan = FixPlan()

    # 1. wrap broken fragment files
    for p in _candidate_files(mission):
        try:
            xmlio.load(p)
            continue  # already valid
        except xmlio.CEParseError:
            pass
        except (OSError, ValueError):
            continue
        rel = str(p.relative_to(mission.root)) if p.is_relative_to(mission.root) else p.name
        if xmlio.looks_like_unwrapped_fragment(p):
            if xmlio.wrap_fragment(p):
                plan.wrapped.append(rel)
        else:
            plan.unwrappable.append(rel)

    # 2. lower min where min >= nominal (no restock headroom)
    for tf_path in _type_files(mission):
        try:
            tf = TypesFile(tf_path)
        except (OSError, ValueError):
            continue
        touched = False
        for lt in tf.all():
            if lt.nominal > 0 and lt.min >= lt.nominal:
                new_min = lt.nominal // 2
                plan.headroom.append((lt.name, lt.min, new_min))
                lt.min = new_min
                tf.upsert(lt)
                touched = True
        if touched:
            tf.save()

    return plan
