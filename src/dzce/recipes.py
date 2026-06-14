"""One-shot 'recipes' -- named bundles that apply a coherent set of changes.

A recipe can touch loot (by category, name pattern, or curated item group),
event counts (zombies/animals/vehicles), event-group loot (convoys/trains), and
attachment/cargo spawn chances. Each step degrades gracefully: if a category,
group, or file is absent on a server, that step simply affects nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import groups
from .balance import LootBalancer
from .files.eventgroups_file import EventGroupsFile
from .files.events_file import EventsFile
from .files.spawnabletypes_file import SpawnableTypesFile
from .files.types_file import TypesFile
from .mission import Mission


@dataclass
class Step:
    label: str
    filters: dict = field(default_factory=dict)   # passed to TypesFile.select()
    group: str | None = None                      # or a curated item-group key
    scale: float | None = None
    rarity: str | None = None


@dataclass
class Recipe:
    key: str
    title: str
    description: str
    steps: list[Step] = field(default_factory=list)
    events: dict[str, float] = field(default_factory=dict)        # kind -> factor
    eventgroups_loot: float | None = None                          # convoys/trains
    spawnable_chance: tuple[str, float] | None = None              # (kind, factor)


RECIPES: dict[str, Recipe] = {
    # ---- all-round loot levels -----------------------------------------
    "more-loot": Recipe(
        "more-loot", "More loot (everything 1.5x)",
        "Bumps spawn counts of all items by 50%. A gentle, all-round boost.",
        steps=[Step("all items x1.5", scale=1.5)],
    ),
    "loot-pinata": Recipe(
        "loot-pinata", "Loot pinata (everything 2x + more cars)",
        "Doubles all loot and adds 50% more vehicles. Casual / low-stress.",
        steps=[Step("all items x2", scale=2.0)],
        events={"vehicles": 1.5},
    ),
    "peaceful": Recipe(
        "peaceful", "Peaceful / build server (less loot, few zombies)",
        "Cuts loot to 60% and infected to 40%. Good for chill base-building.",
        steps=[Step("all items x0.6", scale=0.6)],
        events={"zombies": 0.4},
    ),

    # ---- combat / gear -------------------------------------------------
    "more-guns": Recipe(
        "more-guns", "More guns & ammo (2x)",
        "Doubles weapons, magazines and ammo so firefights are well-supplied.",
        steps=[
            Step("weapons x2", {"category": "weapons"}, scale=2.0),
            Step("magazines x2", group="magazines", scale=2.0),
            Step("ammo x2", group="ammo", scale=2.0),
        ],
    ),
    "military-ops": Recipe(
        "military-ops", "Military ops (geared PvP / milsim)",
        "High-tier military loot, weapons, ammo and optics up; guns more often "
        "spawn with attachments.",
        steps=[
            Step("Tier3 loot x2", {"tier": "Tier3"}, scale=2.0),
            Step("Tier4 loot x2", {"tier": "Tier4"}, scale=2.0),
            Step("ammo x2", group="ammo", scale=2.0),
            Step("magazines x2", group="magazines", scale=2.0),
            Step("optics x2", group="optics", scale=2.0),
        ],
        spawnable_chance=("attachments", 1.5),
    ),
    "full-kits": Recipe(
        "full-kits", "Full kits (guns spawn loaded & accessorized)",
        "Doubles attachment/cargo spawn chances and boosts mags+ammo, so you "
        "find usable, kitted weapons.",
        steps=[
            Step("magazines x1.5", group="magazines", scale=1.5),
            Step("ammo x1.5", group="ammo", scale=1.5),
        ],
        spawnable_chance=("attachments", 2.0),
    ),
    "scarce-ammo": Recipe(
        "scarce-ammo", "Scarce ammo (guns plenty, bullets precious)",
        "Cuts ammo and magazines to 40%. Every shot counts; melee matters.",
        steps=[
            Step("ammo x0.4", group="ammo", scale=0.4),
            Step("magazines x0.4", group="magazines", scale=0.4),
        ],
    ),

    # ---- survival difficulty ------------------------------------------
    "hardcore": Recipe(
        "hardcore", "Hardcore survival (scarce loot)",
        "Weapons become uncommon and food/medical are cut back. Tense, lethal.",
        steps=[
            Step("weapons -> uncommon", {"category": "weapons"}, rarity="uncommon"),
            Step("food x0.6", {"category": "food"}, scale=0.6),
            Step("medical x0.6", group="medical", scale=0.6),
        ],
    ),
    "survival-horror": Recipe(
        "survival-horror", "Survival horror (brutal scarcity + hordes)",
        "Halves all loot and triples infected. Stalker-style dread.",
        steps=[Step("all items x0.5", scale=0.5)],
        events={"zombies": 3.0},
    ),
    "coast-friendly": Recipe(
        "coast-friendly", "Fresh-spawn friendly coast",
        "Boosts coastal (Tier1) loot, food and medical so new spawns survive.",
        steps=[
            Step("Tier1 loot x2", {"tier": "Tier1"}, scale=2.0),
            Step("food x1.5", {"category": "food"}, scale=1.5),
            Step("medical x1.5", group="medical", scale=1.5),
        ],
    ),

    # ---- themed --------------------------------------------------------
    "base-builder": Recipe(
        "base-builder", "Base-building boom",
        "Boosts base-building materials and storage containers so bases are buildable.",
        steps=[
            Step("building x2.5", group="building", scale=2.5),
            Step("containers x1.5", {"category": "containers"}, scale=1.5),
        ],
    ),
    "medic": Recipe(
        "medic", "Medic / RP (plentiful medical)",
        "Boosts medical supplies 2.5x for medic roleplay or high-combat healing.",
        steps=[Step("medical x2.5", group="medical", scale=2.5)],
    ),
    "convoy-madness": Recipe(
        "convoy-madness", "Convoy madness (rich set-pieces + cars)",
        "Makes convoy/train/shipwreck loot 2.5x richer and adds 50% more vehicles.",
        events={"vehicles": 1.5},
        eventgroups_loot=2.5,
    ),

    # ---- events --------------------------------------------------------
    "zombie-apocalypse": Recipe(
        "zombie-apocalypse", "Zombie apocalypse (2.5x infected)",
        "Multiplies infected counts by 2.5. Towns become genuinely dangerous.",
        events={"zombies": 2.5},
    ),
    "vehicle-hunter": Recipe(
        "vehicle-hunter", "Vehicle hunter (2x cars)",
        "Doubles vehicle spawns so a working car is easier to find.",
        events={"vehicles": 2.0},
    ),
}


@dataclass
class RecipeResult:
    label: str
    affected: int


def apply_recipe(mission: Mission, recipe: Recipe) -> list[RecipeResult]:
    results: list[RecipeResult] = []

    if recipe.steps:
        types = TypesFile(mission.path("types"))
        bal = LootBalancer(types)
        touched: set[str] = set()  # each item is adjusted by at most one step
        for step in recipe.steps:
            if step.group:
                sel = groups.resolve(types.all(), step.group)
            else:
                sel = types.select(**step.filters)
            sel = [lt for lt in sel if lt.name not in touched]
            if step.rarity:
                n = bal.apply_rarity(sel, step.rarity)
            else:
                n = bal.scale(sel, step.scale or 1.0)
            touched.update(lt.name for lt in sel)
            results.append(RecipeResult(step.label, n))
        types.save()

    if recipe.events and mission.has("events"):
        ef = EventsFile(mission.path("events"))
        for kind, factor in recipe.events.items():
            n = ef.scale(ef.by_kind(kind), factor)
            results.append(RecipeResult(f"{kind} x{factor}", n))
        ef.save()

    if recipe.eventgroups_loot and mission.has("eventgroups"):
        egf = EventGroupsFile(mission.path("eventgroups"))
        n = egf.scale_loot(recipe.eventgroups_loot)
        egf.save()
        results.append(RecipeResult(f"event-group loot x{recipe.eventgroups_loot}", n))

    if recipe.spawnable_chance and mission.has("spawnabletypes"):
        kind, factor = recipe.spawnable_chance
        stp = SpawnableTypesFile(mission.path("spawnabletypes"))
        n = stp.scale_chances(factor, kind=kind)
        stp.save()
        results.append(RecipeResult(f"{kind} chance x{factor}", n))

    return results
