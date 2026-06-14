"""Loot balancing engine operating on a TypesFile."""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from .files.types_file import TypesFile
from .models import LootType

# Sane DayZ-aligned presets: (nominal, min, restock, cost).
RARITY_PRESETS: dict[str, tuple[int, int, int, int]] = {
    "abundant": (80, 40, 0, 100),
    "common": (40, 20, 0, 100),
    "uncommon": (20, 8, 1800, 100),
    "rare": (8, 3, 1800, 100),
    "very_rare": (4, 1, 3600, 100),
    "unique": (1, 0, 0, 100),
}


@dataclass
class CategoryStat:
    category: str
    count: int
    total_nominal: int


class LootBalancer:
    def __init__(self, types: TypesFile):
        self.types = types

    # -- reporting --------------------------------------------------------
    def category_stats(self) -> list[CategoryStat]:
        agg: dict[str, list[int]] = {}
        for lt in self.types.all():
            cat = lt.category or "(none)"
            agg.setdefault(cat, [0, 0])
            agg[cat][0] += 1
            agg[cat][1] += lt.nominal
        return sorted(
            (CategoryStat(c, n[0], n[1]) for c, n in agg.items()),
            key=lambda s: -s.total_nominal,
        )

    def total_nominal(self) -> int:
        return sum(lt.nominal for lt in self.types.all())

    # -- mutations --------------------------------------------------------
    def scale(self, selection: list[LootType], factor: float, *,
              fields: tuple[str, ...] = ("nominal", "min"),
              clamp_min: int = 0) -> int:
        """Multiply chosen numeric fields by ``factor`` across a selection."""
        changed = 0
        for lt in selection:
            for f in fields:
                cur = getattr(lt, f)
                if cur <= 0:
                    continue
                setattr(lt, f, max(clamp_min, round(cur * factor)))
            self.types.upsert(lt)
            changed += 1
        return changed

    def apply_rarity(self, selection: list[LootType], rarity: str) -> int:
        if rarity not in RARITY_PRESETS:
            raise ValueError(f"unknown rarity {rarity!r}; choose from {list(RARITY_PRESETS)}")
        nominal, mn, restock, cost = RARITY_PRESETS[rarity]
        for lt in selection:
            lt.nominal, lt.min, lt.restock, lt.cost = nominal, mn, restock, cost
            self.types.upsert(lt)
        return len(selection)

    def plan(self, selection: list[LootType], *, scale: float | None = None,
             rarity: str | None = None) -> list[tuple[str, int, int, int, int]]:
        """Compute (name, nominal_before, nominal_after, min_before, min_after)
        for a selection WITHOUT mutating anything. Used to preview changes."""
        rows: list[tuple[str, int, int, int, int]] = []
        for lt in selection:
            if rarity:
                nominal, mn, _r, _c = RARITY_PRESETS[rarity]
            else:
                f = scale or 1.0
                nominal = max(0, round(lt.nominal * f)) if lt.nominal > 0 else lt.nominal
                mn = max(0, round(lt.min * f)) if lt.min > 0 else lt.min
            rows.append((lt.name, lt.nominal, nominal, lt.min, mn))
        return rows

    def set_fields(self, lt: LootType, **fields) -> None:
        for k, v in fields.items():
            if not hasattr(lt, k):
                raise AttributeError(f"LootType has no field {k!r}")
            setattr(lt, k, v)
        self.types.upsert(lt)

    # -- vanilla baselines (used by the mod balancer) ---------------------
    def baseline_for(self, category: str | None, tiers: list[str]) -> dict[str, int] | None:
        return compute_baseline(self.types.all(), category, tiers)


def compute_baseline(all_types: list[LootType], category: str | None,
                     tiers: list[str]) -> dict[str, int] | None:
    """Median nominal/min/cost of the peer group sharing ``category`` and
    (optionally) overlapping ``tiers``. Works over any list of LootType, so the
    baseline can span stock loot plus already-integrated mod CE folders."""
    peers = [
        lt for lt in all_types
        if lt.category == category and (not tiers or set(lt.values) & set(tiers))
    ]
    if not peers:
        peers = [lt for lt in all_types if lt.category == category]
    if not peers:
        return None
    return {
        "nominal": round(statistics.median(p.nominal for p in peers)),
        "min": round(statistics.median(p.min for p in peers)),
        "cost": round(statistics.median(p.cost for p in peers)),
        "peers": len(peers),
    }
