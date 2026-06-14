# Usage

`dzce` has two modes:

- **Command mode** — scriptable subcommands, ideal for automation and CI.
- **Interactive mode** — run `dzce` with no subcommand for a guided menu.

## Selecting the mission

`dzce` auto-detects the mission folder if you run it from inside one, from its
parent, or from a folder containing `mpmissions/`. Otherwise pass it explicitly:

```bash
dzce --mission /srv/dayz/mpmissions/dayzOffline.chernarusplus summary
```

## Command reference

```
dzce --dry-run <any command>      Simulate: show what would change, write nothing
dzce groups                       List curated item groups (medical, building, ammo...) + coverage
dzce overview                     Full read-only snapshot of the whole server
dzce info                         Show detected mission + file presence
dzce summary                      Category/tier/event overview
dzce validate                     Cross-file checks + verifies EVERY mod linked in cfgeconomycore.xml
dzce config [--set-mission PATH]  Show or set your saved default mission (so you can skip --mission)
dzce doctor                       Heuristic health check (advisory suggestions)
dzce fix [--yes]                  Apply ONLY safe fixes (wrap broken mod files; min headroom)

dzce types list [--category C] [--usage U] [--tier T] [--name GLOB] [--limit N]
dzce types show NAME
dzce types set NAME [--nominal N --min N --lifetime N --restock N --cost N]

dzce balance scale FACTOR [--category C --usage U --tier T --name GLOB --group G]
dzce balance rarity RARITY [--category C --usage U --tier T --name GLOB --group G]

dzce events scale {zombies|animals|vehicles} FACTOR

dzce spawnables list [--kind attachments|cargo|all]
dzce spawnables scale-chance FACTOR [--kind ...]   Scale attachment/cargo chances (0..1)
dzce spawnables set-chance NAME VALUE [--kind ...]

dzce eventgroups list
dzce eventgroups scale-loot FACTOR [--group NAME]  Scale loot in convoys/trains (positions safe)

dzce globals get NAME
dzce globals set NAME VALUE
dzce globals list

dzce mod add PATH [--rarity R] [--baseline stock|merged] [--no-balance]

dzce recipe list                  List one-shot setup presets
dzce recipe apply KEY [--yes]     Apply a preset (skip prompt with --yes)

dzce backup list
dzce backup restore BACKUP_FILE
```

## Filters

`--category`, `--usage`, `--tier` and `--name` (a glob like `mag_*`) combine, so
you can target precisely:

```bash
# every Tier4 military weapon
dzce types list --category weapons --usage Military --tier Tier4

# scale only ammo
dzce balance scale 2.0 --name "Ammo_*"
```
