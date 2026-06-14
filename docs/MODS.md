# Integrating mods

`dzce mod add PATH` runs a five-step pipeline so a mod plays fair with your loot.

### 1. Scan
Finds the mod's `types.xml` (at the folder root or under `db/`) and, if present,
its `cfgspawnabletypes.xml`.

### 2. Register (the official way)
Instead of pasting mod entries into your stock `types.xml`, dzce adds a CE folder
include to `cfgeconomycore.xml`:

```xml
<ce folder="MyWeapons">
    <file name="types.xml" type="types"/>
</ce>
```

DayZ merges that folder at load. Your stock file stays clean and update-safe.

### 3. Vocabulary check
Every `category` / `usage` / `value`(tier) / `tag` a mod uses must be declared in
`cfglimitsdefinition.xml` — otherwise the item is **silently dropped**. dzce
lists anything missing and (with `--fix-vocab`, the default) declares it for you.

### 4. Balance against vanilla
For each mod item, dzce finds the vanilla **peer group** (same category, with
overlapping tiers) and rewrites the mod's `nominal/min/cost` to the median of
that group. So a modded assault rifle ends up about as common as your vanilla
assault rifles — not flooding the map.

Force a fixed rarity instead with `--rarity`:

```bash
dzce mod add ./MyWeapons --rarity rare
```

Skip rebalancing entirely with `--no-balance`.

### 5. Dependency audit
Flags weapons that have **no** `cfgspawnabletypes.xml` entry — these spawn with
no magazine and read as "broken loot" in-game. dzce reports each so you can add
an attachment group giving them a compatible magazine.

> dzce edits the mod's own `types.xml` when rebalancing — never your stock file —
> and backs it up first.

## When a mod's file won't load (copy-paste snippets)

A lot of mods ship their `types.xml` or `cfgspawnabletypes.xml` as a **snippet**:
a list of `<type>` entries (often with comment headers like "QUICK COPY PASTE
METHOD") and **no `<types>` wrapper**. That isn't valid XML, so DayZ silently
ignores the file and the mod's loot never spawns.

dzce detects this and tells you exactly how to fix it:

```
✗ types.xml is not valid XML, so DayZ would reject it too.
  Problem: Extra content at the end of the document (line 24)
  ...
  Fix it automatically with:  dzce mod wrap types.xml
```

`dzce mod wrap <file>` wraps the snippet in the correct root element and saves a
backup. It is smart about the root: `types.xml` becomes `<types>`,
`cfgspawnabletypes.xml` becomes `<spawnabletypes>`, `cfgeventgroups.xml` becomes
`<eventgroupdef>`.

```bash
dzce mod wrap AsmondVanillaWeapons/types.xml
dzce mod wrap AsmondVanillaWeapons/cfgspawnabletypes.xml
```

To find and fix this across **every** registered mod at once:

```bash
dzce validate      # lists every linked mod file that is missing or invalid
dzce fix --yes     # wraps all the fixable ones in one go
```

Snippet loot usually has `nominal`/`min` set to 0, so after wrapping, run
`dzce mod add <folder> --baseline merged` to give it spawn values that match
your existing loot.
