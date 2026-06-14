# Balancing loot

## The fields that matter (types.xml)

| Field | Meaning |
|-------|---------|
| `nominal` | Target count the CE tries to keep on the map |
| `min` | Lower threshold that triggers restocking |
| `lifetime` | Seconds an untouched item persists before despawn |
| `restock` | Seconds before a depleted type may refill (0 = immediate) |
| `cost` | Spawn priority weight (higher wins contested spawn points) |
| `quantmin`/`quantmax` | Fill % for ammo/liquids/etc. (-1 = full/N/A) |

## Two ways to balance

### Scale
Multiply `nominal` and `min` by a factor across a selection. Sentinels
(`0`, `-1`) are left untouched.

```bash
dzce balance scale 1.5 --category food   # 50% more food on the map
dzce balance scale 0.5 --tier Tier4      # halve high-tier loot
```

### Rarity presets
Apply a coherent `nominal/min/restock/cost` template:

| preset | nominal | min | restock | cost |
|--------|--------:|----:|--------:|-----:|
| abundant | 80 | 40 | 0 | 100 |
| common | 40 | 20 | 0 | 100 |
| uncommon | 20 | 8 | 1800 | 100 |
| rare | 8 | 3 | 1800 | 100 |
| very_rare | 4 | 1 | 3600 | 100 |
| unique | 1 | 0 | 0 | 100 |

```bash
dzce balance rarity rare --name "M4A1"
dzce balance rarity uncommon --category weapons --tier Tier3
```

## Reality checks

- A higher `nominal` does nothing if there are no spawn points for that item's
  category and tier. Tiers map to map zones via `cfglimitsdefinition.xml`.
- Category-wide spawn caps in `cfglimitsdefinition.xml` still apply on top of
  per-item `nominal`. `dzce summary` shows total nominal per category so you can
  see when you're pushing a category too hard.
- Always run `dzce validate` after big changes.

## Targeting by item group

DayZ's categories are coarse: there is **no "medical" or "base-building"
category**. Medical items live under `tools`, building materials are spread
across `tools`/`containers`/uncategorized. So "make all medical rarer" can't be
done by category.

dzce solves this with **item groups** — curated bundles matched by item name:

| group | covers |
|-------|--------|
| `medical` | bandages, morphine, saline, antibiotics, blood, ... |
| `building` | nails, planks, fences, wire, locks, ... |
| `ammo` | loose rounds and ammo boxes |
| `magazines` | detachable magazines |
| `optics` | scopes and red-dots |

```bash
dzce groups                          # list groups + how many items each matches here
dzce balance scale 0.5 --group medical
dzce balance scale 2.0 --group building
```

In the guided menu, groups appear right alongside your categories under
"Adjust loot by category or group", with a live item count.

> Groups match by name pattern, so a mod with an unusual classname can slip
> through. `dzce groups` shows the match count so you can sanity-check coverage;
> patterns live in `src/dzce/groups.py` and are easy to extend.
