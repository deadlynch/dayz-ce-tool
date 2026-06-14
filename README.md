# dzce — DayZ Central Economy Toolkit

**Tune your DayZ server's loot, zombies, vehicles and mods from the terminal — without hand-editing giant XML files or breaking your server.**

`dzce` is a friendly command-line tool for DayZ server admins. You point it at your mission folder, it reads your Central Economy (CE) files, and it lets you make changes in plain language ("make weapons rarer", "twice as many zombies", "balance this mod against my loot") instead of editing 24,000-line XML files by hand and praying the server still boots.

It speaks the real file structure documented by Bohemia Interactive ([DayZ-Central-Economy](https://github.com/BohemiaInteractive/DayZ-Central-Economy)), and **every change is backed up automatically before it's written**.

---

## Table of contents

- [Is this for me?](#is-this-for-me)
- [What problem does it solve?](#what-problem-does-it-solve)
- [Requirements](#requirements)
- [Installation (step by step)](#installation-step-by-step)
- [Try it now (no DayZ server needed)](#try-it-now-no-dayz-server-needed)
- [Your first 5 minutes](#your-first-5-minutes)
- [The guided menu (the easy way)](#the-guided-menu-the-easy-way)
- [One-tap setups (recipes)](#one-tap-setups-recipes)
- [A real example, start to finish](#a-real-example-start-to-finish)
- [Integrating a mod](#integrating-a-mod)
- [overview vs doctor vs validate](#check-fix--keep-it-healthy)
- [Safety: backups and undo](#safety-backups-and-undo)
- [Understanding your files (plain-English glossary)](#understanding-your-files-plain-english-glossary)
- [Command-line mode (for power users)](#command-line-mode-for-power-users)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [What it does NOT do](#what-it-does-not-do)
- [License](#license)

---

## Is this for me?

Yes, if you run (or want to run) a DayZ server and you've ever:

- wanted **more (or less) loot** without learning what `nominal` and `restock` mean,
- added a mod and watched it **flood the map** with overpowered guns,
- had loot **silently never spawn** and not known why,
- been afraid to touch `types.xml` because one typo stops the server from loading.

You do **not** need to be a programmer. The guided menu walks you through everything. The advanced command-line mode is there if you want it, but you can ignore it completely.

## What problem does it solve?

DayZ's loot system (the "Central Economy") is powerful but unforgiving:

- An item that points to a category/zone tag you didn't declare is **silently dropped** and never appears in game.
- A modded rifle with no magazine config spawns **completely empty**.
- A mod that ships `nominal=50` on every weapon **drowns** your carefully balanced economy.
- One malformed character and the server **refuses to load** the file.

`dzce` knows about these traps. It prevents the common ones, warns you about the rest, and never lets a bad edit corrupt your file formatting.

## Requirements

- **Linux**: Ubuntu, Debian, or Arch (these are tested; other distros with `python3` + `pipx` work too).
- **Python 3.10 or newer** — almost certainly already installed. Check with `python3 --version`.
- Your **DayZ server mission folder** (the one containing a `db/` folder and `cfgeconomycore.xml`), e.g. `.../mpmissions/dayzOffline.chernarusplus`.

The installer handles the Python bits for you.

## Installation (step by step)

**1. Get the code.**

```bash
git clone https://github.com/deadlynch/dayz-ce-tool.git
cd dayz-ce-tool
```

(Or download the ZIP from GitHub and extract it, then `cd` into the folder.)

**2. Run the installer.**

```bash
./install.sh
```

Here's exactly what that script does, so there are no surprises:

- detects whether your system uses `apt` (Ubuntu/Debian) or `pacman` (Arch),
- makes sure `python3`, `pip` and `pipx` are installed (it will ask for `sudo` if it needs to install them),
- installs `dzce` into its **own isolated environment** with `pipx`, so it never interferes with other Python software on your machine,
- puts the `dzce` command on your PATH.

**3. Open a new terminal** (so your PATH refreshes) and confirm it works:

```bash
dzce --version
dzce --help
```

If `dzce` isn't found, run `pipx ensurepath`, then close and reopen your terminal.

**To uninstall later:** `./uninstall.sh` (your backups are left untouched).

## Try it now (no DayZ server needed)

This repo ships a tiny **sample server** under `examples/` so you can try every
feature safely before touching your real files. From the project folder:

```bash
# a full snapshot of the sample server
dzce --mission examples/sample.chernarusplus overview

# what the health check thinks
dzce --mission examples/sample.chernarusplus doctor

# SIMULATE a change — shows what would happen, writes nothing
dzce --dry-run --mission examples/sample.chernarusplus recipe apply more-guns --yes

# simulate integrating the bundled example mod (an overpowered rifle)
dzce --dry-run --mission examples/sample.chernarusplus mod add examples/ExampleWeaponsMod
```

Everything above with `--dry-run` is a **simulation** — your sample files stay
untouched. When you're ready to see real edits happen, drop `--dry-run`. The
sample is safe to experiment on; if you mess it up, `git checkout examples/`
puts it back.

> **Tip:** `--dry-run` works on *any* command. It's the safest way to learn —
> see the change first, apply it only when you're happy.

## Your first 5 minutes

The golden rule: **look before you leap.** Go to your mission folder and get a read-only snapshot first.

```bash
cd /path/to/mpmissions/dayzOffline.chernarusplus

dzce overview
```

`overview` changes nothing. It prints a one-page picture of your whole server: which files exist, which mods are registered, how much loot you have per category, your zombie/animal/vehicle counts, and a health line at the bottom. **Run this first, every time.**

Next, ask the tool what looks off:

```bash
dzce doctor
```

`doctor` is also read-only. It applies rules-of-thumb and flags *suspicions* — "this mod is flooding the weapons category", "these map zones have no loot", "this weapon will spawn with no magazine" — each with a short reason and a suggested fix. These are advice, not errors.

Now make your first change the easy way — just run the tool with no arguments:

```bash
dzce
```

This opens the **guided menu**. Pick an option, answer a couple of plain-language questions, review the preview, confirm. Done — and a backup was saved automatically.

That's the whole loop: **overview → doctor → make a change → (optionally) validate before restarting your server.**

## The guided menu (the easy way)

Running `dzce` with no arguments opens an interactive menu. You move with the arrow keys and press Enter. You never have to memorize anything. The options:

| Menu option | What it does |
|---|---|
| **Quick setups (one-tap presets)** | Apply a whole scenario at once — "More guns", "Hardcore survival", "Zombie apocalypse", etc. (see [recipes](#one-tap-setups-recipes)). |
| **Adjust a whole category** | Pick a loot category (it lists yours for you) and choose "much more common", "make it rare", etc. Shows a preview before applying. |
| **Find & adjust specific items** | Type part of a name (e.g. `morphine`), tick the items you want from a list, pick how to change them. No need to know exact classnames. |
| **Zombies, animals & vehicles** | Scale how many spawn — "twice as many zombies", "half as many cars". |
| **Attachment & cargo spawn chances** | Change how often guns spawn with magazines/optics, or how often containers spawn with stuff inside. |
| **Event-group loot (convoys, trains)** | Make the loot inside big set-pieces richer or poorer (positions are never touched). |
| **Add / balance a mod** | Walks you through integrating a mod and balancing it against your existing loot (see [Integrating a mod](#integrating-a-mod)). |
| **Check my files for problems** | Runs `validate` — the hard error check. |
| **Health check (suggestions)** | Runs `doctor` — the advisory suggestions. |
| **See my whole server at a glance** | Runs `overview`. |

Every option that changes something shows you a **preview** ("M4A1 spawn count: 8 → 16") and asks you to confirm. Backups are automatic.

## One-tap setups (recipes)

Recipes apply a coherent bundle of changes in a single step. Great when you know the *vibe* you want but don't want to fiddle with individual numbers.

| Recipe | What it does |
|---|---|
| `more-loot` | Everything ~1.5× more common. A gentle, all-round boost. |
| `loot-pinata` | Everything 2× + 50% more vehicles. Casual / low-stress servers. |
| `more-guns` | Doubles weapons, magazines and ammo. |
| `hardcore` | Weapons become rare; food and medical supplies are cut back. Tense, lethal. |
| `zombie-apocalypse` | 2.5× more infected. Towns become genuinely dangerous. |
| `vehicle-hunter` | 2× vehicles, so a working car is easier to find. |

Use them from the menu (**Quick setups**) or from the command line:

```bash
dzce recipe list                       # see them all with descriptions
dzce recipe apply more-guns            # asks for confirmation
dzce recipe apply hardcore --yes       # skip the prompt (good for scripts)
```

## A real example, start to finish

**Goal: "I want more guns on my server, but medical supplies should be scarce."**

```bash
cd /path/to/mpmissions/dayzOffline.chernarusplus

# 1. See where you're starting from
dzce overview

# 2. Double the guns and ammo in one shot
dzce recipe apply more-guns --yes

# 3. Make medical supplies rare
dzce balance rarity rare --category medical

# 4. Make sure nothing broke before you restart the server
dzce validate
```

Prefer clicking through menus? Run `dzce`, choose **Quick setups → More guns & ammo**, then **Adjust a whole category → medical → Make it rare**. Same result, fully guided.

After changing loot, **restart your server** for the Central Economy to pick up the new values.

## Integrating a mod

Say you downloaded a weapons mod with its own `types.xml`. Drop the mod's CE folder **inside your mission folder**, then:

```bash
dzce mod add ./MyWeaponsMod
```

`dzce` runs a 5-step pipeline and explains each step as it goes:

1. **Finds** the mod's `types.xml` (and its `cfgspawnabletypes.xml` if it has one).
2. **Registers** it the official way — adds a `<ce folder="...">` entry to `cfgeconomycore.xml`. Your stock files stay clean and update-safe.
3. **Checks the vocabulary** — if the mod uses zone/usage tags you haven't declared, the items would silently never spawn. It tells you, and declares them for you.
4. **Balances it against your loot** — rewrites the mod's spawn counts so a new rifle is about as common as your existing rifles, instead of flooding the map. On a modded server, use `--baseline merged` so it compares against *all* your current loot, mods included.
5. **Audits for empty weapons** — flags any gun that would spawn with no magazine, so you can fix it.

```bash
# balance the mod against your full current economy (stock + already-installed mods)
dzce mod add ./MyWeaponsMod --baseline merged

# or just make everything from this mod rare
dzce mod add ./MyWeaponsMod --rarity rare
```

The guided menu (**Add / balance a mod**) does all of this with yes/no questions if you prefer.

### When a mod won't load (the copy-paste snippet problem)

Many mods ship their `types.xml` / `cfgspawnabletypes.xml` as a **copy-paste snippet** — a list of `<type>` entries with no single `<types>` wrapper. That's not valid XML, so **DayZ silently refuses to load it** and the mod's loot never spawns. dzce detects this and fixes it for you:

```bash
dzce mod wrap AsmondVanillaWeapons/types.xml
dzce mod wrap AsmondVanillaWeapons/cfgspawnabletypes.xml
```

`mod wrap` wraps the snippet in the correct root element (it knows `types.xml` needs `<types>` and `cfgspawnabletypes.xml` needs `<spawnabletypes>`), with a backup. To find every broken mod file at once across **all** your mods, run `dzce validate` — it checks every file linked in `cfgeconomycore.xml` — or just run `dzce fix` (below), which wraps them all in one go.

## Check, fix & keep it healthy

Four read-only-or-safe commands, four jobs:

| Command | Question it answers | Changes files? |
|---|---|---|
| `dzce overview` | "What have I got?" | No |
| `dzce doctor` | "What looks wrong?" (advisory, heuristic) | No |
| `dzce validate` | "Will the game choke on this?" — also checks **every mod** linked in `cfgeconomycore.xml` | No |
| `dzce fix` | "Fix the safe stuff automatically" | Yes (safe, mechanical only) |

`dzce fix` only touches problems with one unambiguous answer: it **wraps broken mod files** and gives **min-headroom** where `min >= nominal`. It deliberately does **not** guess at judgment calls (items with no usage/tier, suspicious nominal values, weapons with no magazine) — those it leaves for you and points you to `dzce doctor`. Preview it first with `dzce fix --dry-run`.

A good habit: `overview` to orient → `doctor`/`validate` to find problems → `fix` for the safe ones → restart your server.

## Safety: backups and undo

You don't have to trust the tool blindly.

- **Simulate anything first** with `--dry-run` — see every change, write nothing.
- **Before every real write**, `dzce` copies the file into a `.dzce-backups/` folder right next to it, with a timestamp.
- It keeps the last 20 backups of each file and prunes older ones.
- Your original comments, indentation and the exact XML header are preserved — the parts you didn't change stay byte-for-byte identical.

To roll back:

```bash
dzce backup list                       # see all backups with timestamps
dzce backup restore /path/to/db/.dzce-backups/types.xml.20260614-141318.bak
```

(The `.dzce-backups/` folders are also in `.gitignore`, so they never get committed by accident.)

## Understanding your files (plain-English glossary)

You don't *need* this to use the tool, but it helps to know what the numbers mean.

**The loot table — `db/types.xml`.** One entry per item. Key fields:

- **nominal** — how many of this item the server tries to keep on the map at once. Higher = more common.
- **min** — when the count drops below this, the economy restocks. Keep it below `nominal`.
- **lifetime** — seconds an untouched item stays before it despawns.
- **restock** — seconds before a depleted item type refills (`0` = immediately).
- **cost** — spawn priority when items compete for the same spot.
- **usage** — *what kind of building* it spawns in (Military, Police, Town, Farm…).
- **value / tier** — *which map zone tier* (Tier1 = coastal/starter … Tier4 = deep military). An item with no usage and no tier usually never spawns on the map.
- **category** — weapons, food, tools, clothes, etc.

> Reality check: raising `nominal` only helps up to the number of actual spawn points your map has for that item's zones. Past that, the extra simply won't appear — that ceiling lives in the map's spawn-point files, which `dzce` does not touch.

**Other files dzce works with:**

- `db/globals.xml` — server-wide knobs (max zombies, cleanup timers…).
- `db/events.xml` — how many zombies, animals and vehicles spawn.
- `cfgspawnabletypes.xml` — what spawns *attached to* or *inside* things (a gun's magazine, a backpack's contents).
- `cfgeventgroups.xml` — multi-object set pieces (convoys, trains, shipwrecks) and the loot inside them.
- `cfgeconomycore.xml` — registers loot folders, including mods.
- `cfglimitsdefinition.xml` + `cfglimitsdefinitionuser.xml` — the list of allowed category/usage/tier/tag names (the "vocabulary"). The `...user.xml` one is where mods and admins add custom tags.

## Command-line mode (for power users)

Everything in the menu is also a direct command, which is handy for scripts and automation. A taste:

```bash
dzce balance scale 1.5 --category weapons      # 50% more weapons
dzce balance rarity rare --name "M4A1"         # make one item rare
dzce balance scale 0.5 --group medical         # halve all medical supplies
dzce events scale zombies 2.0                  # twice the zombies
dzce spawnables scale-chance 1.5 --kind cargo  # containers spawn fuller
dzce eventgroups scale-loot 2.0                # richer convoys/trains
dzce types set M4A1 --nominal 12 --min 6       # set exact values
```

Filters (`--category`, `--usage`, `--tier`, `--name` with `*` wildcards) combine, so you can target precisely. **Item groups** (`--group`) cover things DayZ doesn't categorize — `medical`, `building`, `ammo`, `magazines`, `optics` — so you can target "all medical supplies" even though they live under the generic `tools` category. Run `dzce groups` to see them and how many items each matches on your server. The full command reference lives in [`docs/USAGE.md`](docs/USAGE.md), with deeper guides in [`docs/BALANCING.md`](docs/BALANCING.md) and [`docs/MODS.md`](docs/MODS.md).

## Troubleshooting

**`dzce: command not found` after installing.**
Run `pipx ensurepath`, then close and reopen your terminal. If it persists, `~/.local/bin` may not be on your PATH — add it.

**`No DayZ mission folder found.`**
Run `dzce` from *inside* your mission folder, or point at it explicitly:
```bash
dzce --mission /srv/dayz/mpmissions/dayzOffline.chernarusplus overview
```

**Permission denied writing a file.**
dzce now explains this clearly: it tells you which user owns the file and how to fix it. Run dzce as the owning user (e.g. `sudo -u dayz dzce ...`) or give your user write access. Tip: `--dry-run` lets you preview changes even without write access.

**It keeps asking for my mission folder / forgets it.**
Run once with `dzce --mission /path/to/mission ...` (or `dzce config --set-mission /path`). dzce remembers it, so afterwards plain `dzce` uses it automatically.

**The installer can't find `apt` or `pacman`.**
Your distro isn't auto-detected. Install `python3` and `pipx` with your package manager, then run `pipx install .` from the project folder.

**I made a change I regret.**
See [Safety: backups and undo](#safety-backups-and-undo). Every change is reversible.

## FAQ

**Will this break my server?**
It tries hard not to. It backs up before every write, preserves file formatting, and `validate` catches the errors DayZ chokes on. Still — always test on a staging server before production, and keep your own backups too.

**Does it work with modded maps (Livonia, Namalsk, custom)?**
Yes. It detects the mission by its files, not its name, so a folder like `RegularWinter.chernarusplus` works fine.

**Do I edit my live server while it's running?**
Make changes while the server is stopped (or restart it after). The Central Economy reads these files at load.

**Does it touch DayZ Expansion's trader/market files?**
No — those are JSON and out of scope (see below).

**My mod came with a `classname.txt` / item list — do I need it?**
No. `dzce` reads the mod's own `types.xml`, which is the authoritative list of
what the mod actually adds to the loot economy. A `classname.txt` is just a
human-readable reference; the tool doesn't need it to integrate or balance a mod.

**Can I preview a change before committing to it?**
Yes — that's exactly what `--dry-run` is for. Add it to any command (or pick
"Simulate first" in the menu) to see the full effect with nothing written.

## What it does NOT do

Being honest about the edges so you're not surprised:

- It does **not** edit DayZ Expansion's JSON configs (traders, market, airdrops, quests).
- It does **not** edit map spawn-point files (`mapgroupproto.xml`, `mapgrouppos.xml`, etc.) — these are huge, position-based, and rarely hand-edited. This is also the real ceiling on how much loot a map can hold.
- It does **not** edit `init.c` or any Enforce script.
- `doctor` gives *heuristic* advice, not guarantees — the thresholds are shown so you can judge for yourself.

## License

MIT — see [`LICENSE`](LICENSE). © 2026 Edson Batista.

The stock CE files shipped by Bohemia Interactive are covered by the [ADPL-SA](https://www.bohemia.net/community/licenses/arma-and-dayz-public-license-share-alike-adpl-sa); this tool does not redistribute them.

> Not affiliated with or endorsed by Bohemia Interactive. DayZ® is a trademark of Bohemia Interactive a.s.
