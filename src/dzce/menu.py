"""Guided interactive menu -- the primary experience for non-technical admins.

Design rules:
  * The tool surfaces the choices; the user never has to know category names,
    classnames, glob syntax or what 'nominal' means.
  * Everything is phrased in plain language ('Make it rarer', not 'scale 0.5').
  * Every change is previewed (before -> after) and confirmed before writing.
  * One-tap 'Quick setups' cover the common scenarios without any drilling-in.
"""
from __future__ import annotations

from pathlib import Path

import questionary
from rich.table import Table

from . import groups, xmlio
from .balance import LootBalancer
from .console import console, err, info, ok, warn
from .files.events_file import EventsFile
from .files.types_file import TypesFile
from .mission import Mission, discover
from .mods import ModIntegrator
from .recipes import RECIPES, apply_recipe
from .validate import validate as run_validate

# Plain-language adjustment intents -> balancer operation.
INTENTS: list[tuple[str, dict]] = [
    ("Much more common", {"scale": 2.0}),
    ("Somewhat more common", {"scale": 1.5}),
    ("Somewhat rarer", {"scale": 0.66}),
    ("Much rarer", {"scale": 0.5}),
    ("Make it rare (endgame-ish)", {"rarity": "rare"}),
    ("Make it very rare (legendary)", {"rarity": "very_rare"}),
    ("Custom amount...", {"custom": True}),
]

PREVIEW_ROWS = 15


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _ask_mission() -> Mission | None:
    path = questionary.path("Where is your mission folder? (or its parent)").ask()
    if not path:
        return None
    return discover(Path(path))


def _ask_intent() -> dict | None:
    label = questionary.select("How should they change?",
                               choices=[i[0] for i in INTENTS]).ask()
    if label is None:
        return None
    op = dict(next(o for lbl, o in INTENTS if lbl == label))
    if op.get("custom"):
        txt = questionary.text(
            "Multiplier (e.g. 2 = twice as much, 0.5 = half):").ask()
        if not txt:
            return None
        try:
            op = {"scale": float(txt)}
        except ValueError:
            err("Not a number.")
            return None
    return op


def _preview_and_apply(types: TypesFile, selection, op: dict, *,
                       what: str) -> None:
    if not selection:
        warn("Nothing matched that choice.")
        return
    bal = LootBalancer(types)
    rows = bal.plan(selection, scale=op.get("scale"), rarity=op.get("rarity"))

    table = Table("item", "spawn count", "minimum", title=f"Preview: {what}")
    changed = 0
    for name, nb, na, mb, ma in rows[:PREVIEW_ROWS]:
        if (nb, mb) != (na, ma):
            changed += 1
        table.add_row(name, f"{nb} -> {na}", f"{mb} -> {ma}")
    console.print(table)
    if len(rows) > PREVIEW_ROWS:
        info(f"...and {len(rows) - PREVIEW_ROWS} more item(s) affected.")

    if not questionary.confirm(
            f"Apply this to {len(selection)} item(s)? A backup is saved first.").ask():
        info("Cancelled. Nothing was changed.")
        return
    if op.get("rarity"):
        bal.apply_rarity(selection, op["rarity"])
    else:
        bal.scale(selection, op["scale"])
    types.save()
    ok(f"Done. {len(selection)} item(s) updated (backup written).")


# --------------------------------------------------------------------------
# top-level entry
# --------------------------------------------------------------------------
def run_menu(mission: Mission | None) -> None:
    console.print("[accent]dzce[/accent] -- DayZ loot & economy made simple\n")
    if mission is None:
        mission = _ask_mission()
        if mission is None:
            err("No mission folder selected.")
            return
        from . import config
        config.set_last_mission(str(mission.root))
    ok(f"Server: {mission.map_name}")

    actions = {
        "Quick setups (one-tap presets)": _recipes,
        "Adjust loot by category or group (weapons, medical, building...)": _adjust_category,
        "Find & adjust specific items": _adjust_items,
        "Zombies, animals & vehicles": _events,
        "Attachment & cargo spawn chances": _spawn_chances,
        "Event-group loot (convoys, trains)": _eventgroups,
        "Add / balance a mod": _mod,
        "Check my files for problems": _validate,
        "Health check (suggestions)": _doctor,
        "Fix common problems (safe auto-fixes)": _fix,
        "See my whole server at a glance": _overview,
        "Quit": None,
    }
    while True:
        console.print()
        choice = questionary.select("What would you like to do?",
                                    choices=list(actions)).ask()
        if choice is None or choice == "Quit":
            return
        try:
            actions[choice](mission)
        except (xmlio.CEParseError, xmlio.CEWriteError) as exc:
            err(str(exc))
        except Exception as exc:  # keep the menu alive on any error
            err(f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# flows
# --------------------------------------------------------------------------
def _recipes(m: Mission) -> None:
    labels = {r.title: r for r in RECIPES.values()}
    pick = questionary.select("Pick a setup:",
                              choices=list(labels) + ["Back"]).ask()
    if pick in (None, "Back"):
        return
    recipe = labels[pick]
    console.print(f"\n[field]{recipe.title}[/field]\n  {recipe.description}")
    bullets = [f"loot: {s.label}" for s in recipe.steps]
    bullets += [f"events: {k} x{v}" for k, v in recipe.events.items()]
    if recipe.eventgroups_loot:
        bullets.append(f"event-group loot x{recipe.eventgroups_loot}")
    if recipe.spawnable_chance:
        k, f = recipe.spawnable_chance
        bullets.append(f"{k} spawn chance x{f}")
    for b in bullets:
        console.print(f"  - {b}")

    action = questionary.select(
        "What now?",
        choices=["Simulate first (preview, writes nothing)",
                 "Apply for real (backups saved first)", "Cancel"]).ask()
    if action in (None, "Cancel"):
        info("Cancelled.")
        return

    simulate = action.startswith("Simulate")
    if simulate:
        xmlio.DRY_RUN = True
    try:
        results = apply_recipe(m, recipe)
    finally:
        xmlio.DRY_RUN = False

    verb = "would change" if simulate else "changed"
    for r in results:
        ok(f"{r.label}: {r.affected} item(s) {verb}")
    if simulate:
        console.print("[warn]Simulation only -- nothing was written.[/warn]")
        if questionary.confirm("Apply it for real now?").ask():
            for r in apply_recipe(m, recipe):
                ok(f"{r.label}: {r.affected} item(s) changed")


def _adjust_category(m: Mission) -> None:
    types = TypesFile(m.path("types"))
    bal = LootBalancer(types)
    stats = bal.category_stats()
    cat_choices = [f"{s.category}  ({s.count} items)" for s in stats]
    label2cat = {c: s.category for c, s in zip(cat_choices, stats)}
    # curated groups (medical, building, ...) with live coverage counts
    grp_choices, label2grp = [], {}
    for g in groups.GROUPS.values():
        n = len(groups.resolve(types.all(), g.key))
        if n:
            lbl = f"[group] {g.title}  ({n} items)"
            grp_choices.append(lbl)
            label2grp[lbl] = g.key
    pick = questionary.select(
        "Which loot?",
        choices=["Everything"] + cat_choices + grp_choices + ["Back"]).ask()
    if pick in (None, "Back"):
        return
    if pick == "Everything":
        selection, what = types.select(), "all items"
    elif pick in label2grp:
        key = label2grp[pick]
        selection, what = groups.resolve(types.all(), key), groups.GROUPS[key].title
    else:
        category = label2cat[pick]
        selection, what = types.select(category=category), f"all '{category}'"
    op = _ask_intent()
    if op is None:
        return
    _preview_and_apply(types, selection, op, what=what)


def _adjust_items(m: Mission) -> None:
    types = TypesFile(m.path("types"))
    term = questionary.text("Type part of an item name (e.g. 'morphine', 'm4'):").ask()
    if not term:
        return
    matches = [lt for lt in types.all() if term.lower() in lt.name.lower()]
    if not matches:
        warn("No items matched.")
        return
    if len(matches) > 60:
        warn(f"{len(matches)} matches -- type more letters to narrow it down.")
        return
    picked = questionary.checkbox(
        "Select the items to change (space to tick, enter to confirm):",
        choices=[lt.name for lt in matches]).ask()
    if not picked:
        info("Nothing selected.")
        return
    selection = [lt for lt in matches if lt.name in picked]
    op = _ask_intent()
    if op is None:
        return
    _preview_and_apply(types, selection, op, what=f"{len(selection)} chosen item(s)")


def _events(m: Mission) -> None:
    if not m.has("events"):
        err("This server has no events.xml.")
        return
    ef = EventsFile(m.path("events"))
    kind_labels = {
        "Zombies (infected)": "zombies",
        "Animals (wildlife)": "animals",
        "Vehicles (cars/boats)": "vehicles",
    }
    pick = questionary.select("Which?",
                              choices=list(kind_labels) + ["Back"]).ask()
    if pick in (None, "Back"):
        return
    kind = kind_labels[pick]
    n_events = len(ef.by_kind(kind))
    intent = questionary.select(
        f"You have {n_events} {kind} event(s). Change them how?",
        choices=["Twice as many (2x)", "50% more (1.5x)",
                 "Half as many (0.5x)", "Custom...", "Back"]).ask()
    factor = {"Twice as many (2x)": 2.0, "50% more (1.5x)": 1.5,
              "Half as many (0.5x)": 0.5}.get(intent)
    if intent in (None, "Back"):
        return
    if factor is None:  # custom
        txt = questionary.text("Multiplier:").ask()
        try:
            factor = float(txt)
        except (TypeError, ValueError):
            err("Not a number.")
            return
    if not questionary.confirm(
            f"Scale all {kind} by x{factor}? Backup saved first.").ask():
        info("Cancelled.")
        return
    n = ef.scale(ef.by_kind(kind), factor)
    ef.save()
    ok(f"Updated {n} {kind} event(s).")


def _mod(m: Mission) -> None:
    path = questionary.path("Mod folder (the one containing its types.xml):").ask()
    if not path:
        return
    mi = ModIntegrator(m)
    scan = mi.scan(Path(path))
    if scan.types_path is None:
        err("Couldn't find a types.xml in that folder.")
        return
    info(f"Found {len(scan.items)} loot entries in '{scan.name}'.")

    if questionary.confirm(
            "Register this mod's loot with the economy (recommended)?").ask():
        ok("Registered.") if mi.register(scan) else info("Already registered.")

    rep = mi.check_vocabulary(scan)
    if not rep.ok:
        warn("Some of the mod's tags aren't declared yet -- items using them "
             "would never spawn.")
        if questionary.confirm("Fix this automatically?").ask():
            ok(f"Declared {mi.fix_vocabulary(rep)} new tag(s).")
    else:
        ok("All the mod's tags are valid.")

    mode = questionary.select(
        "How should the mod's loot be balanced?",
        choices=["Match my existing loot, mods included (recommended)",
                 "Make it rare", "Make it very rare", "Leave it as-is"]).ask()
    if mode and mode != "Leave it as-is":
        rarity = {"Make it rare": "rare",
                  "Make it very rare": "very_rare"}.get(mode)
        changes = mi.balance(scan, rarity=rarity, baseline="merged")
        ok(f"Rebalanced {len(changes)} item(s) so they fit your server.")

    issues = mi.audit(scan)
    if issues:
        warn("Heads up -- these weapons would spawn with no magazine:")
        for iss in issues:
            console.print(f"  - {iss.weapon}")
        info("They need a magazine entry in cfgspawnabletypes.xml to work right.")
    else:
        ok("No empty-weapon problems detected.")


def _spawn_chances(m: Mission) -> None:
    if not m.has("spawnabletypes"):
        err("This server has no cfgspawnabletypes.xml.")
        return
    from .files.spawnabletypes_file import SpawnableTypesFile
    stp = SpawnableTypesFile(m.path("spawnabletypes"))
    kind = {"Attachments (scopes, magazines, bags)": "attachments",
            "Cargo (items inside containers)": "cargo",
            "Both": "all"}[questionary.select(
                "Which spawn chances?",
                choices=["Attachments (scopes, magazines, bags)",
                         "Cargo (items inside containers)", "Both"]).ask()]
    intent = questionary.select(
        "Change them how?",
        choices=["More likely (1.5x)", "Much more likely (2x)",
                 "Less likely (0.66x)", "Custom...", "Back"]).ask()
    factor = {"More likely (1.5x)": 1.5, "Much more likely (2x)": 2.0,
              "Less likely (0.66x)": 0.66}.get(intent)
    if intent in (None, "Back"):
        return
    if factor is None:
        try:
            factor = float(questionary.text("Multiplier:").ask())
        except (TypeError, ValueError):
            err("Not a number.")
            return
    if not questionary.confirm(
            f"Scale {kind} chances by x{factor} (capped at 100%)? Backup first.").ask():
        info("Cancelled.")
        return
    n = stp.scale_chances(factor, kind=kind)
    stp.save()
    ok(f"Updated {n} spawn-chance group(s).")


def _eventgroups(m: Mission) -> None:
    if not m.has("eventgroups"):
        err("This server has no cfgeventgroups.xml.")
        return
    from .files.eventgroups_file import EventGroupsFile
    egf = EventGroupsFile(m.path("eventgroups"))
    s = egf.summary()
    info(f"{s['groups']} groups, {s['children']} objects.")
    intent = questionary.select(
        "Change the loot inside event groups how?",
        choices=["More loot (1.5x)", "Lots more loot (2x)",
                 "Less loot (0.5x)", "Custom...", "Back"]).ask()
    factor = {"More loot (1.5x)": 1.5, "Lots more loot (2x)": 2.0,
              "Less loot (0.5x)": 0.5}.get(intent)
    if intent in (None, "Back"):
        return
    if factor is None:
        try:
            factor = float(questionary.text("Multiplier:").ask())
        except (TypeError, ValueError):
            err("Not a number.")
            return
    if not questionary.confirm(
            f"Scale group loot by x{factor}? Positions are never touched. "
            "Backup first.").ask():
        info("Cancelled.")
        return
    n = egf.scale_loot(factor)
    egf.save()
    ok(f"Updated loot on {n} object(s).")


def _fix(m: Mission) -> None:
    from . import fixes
    # always preview first (dry), then offer to apply
    xmlio.DRY_RUN = True
    try:
        preview = fixes.plan_and_apply(m)
    finally:
        xmlio.DRY_RUN = False
    if not preview.total and not preview.unwrappable:
        ok("Nothing to auto-fix -- the mechanical stuff is already clean.")
    else:
        if preview.wrapped:
            info(f"Would wrap {len(preview.wrapped)} broken mod file(s): "
                 f"{', '.join(preview.wrapped)}")
        if preview.headroom:
            info(f"Would give min-headroom to {len(preview.headroom)} item(s).")
        if preview.unwrappable:
            warn("Broken but NOT auto-fixable: " + ", ".join(preview.unwrappable))
        if preview.total and questionary.confirm(
                "Apply these safe fixes? Backups are saved first.").ask():
            plan = fixes.plan_and_apply(m)
            ok(f"Done: wrapped {len(plan.wrapped)}, min-fixed {len(plan.headroom)}.")
    # point at the judgment-call stuff
    from .doctor import diagnose
    kinds = sorted({f.area for f in diagnose(m)
                    if f.area in ("unreachable loot", "nominal outlier",
                                  "empty weapons", "mod flooding", "dead usage",
                                  "dead tier")})
    if kinds:
        info("Needs your judgment (not auto-fixed): " + ", ".join(kinds)
             + ".  Use 'Health check' for details.")


def _doctor(m: Mission) -> None:
    from .doctor import run_doctor
    run_doctor(m)


def _validate(m: Mission) -> None:
    findings = run_validate(m)
    if not findings:
        ok("No problems found. Your files look healthy.")
        return
    errors = [f for f in findings if f.level == "error"]
    for f in findings[:40]:
        (err if f.level == "error" else warn)(f"{f.where}: {f.message}")
    console.print()
    info(f"{len(errors)} error(s), {len(findings) - len(errors)} warning(s).")


def _overview(m: Mission) -> None:
    from .overview import render_overview
    render_overview(m)


def _summary(m: Mission) -> None:
    types = TypesFile(m.path("types"))
    bal = LootBalancer(types)
    table = Table("category", "items", "total spawn count")
    for s in bal.category_stats()[:14]:
        table.add_row(s.category, str(s.count), str(s.total_nominal))
    console.print(table)
    if m.has("events"):
        ev = EventsFile(m.path("events")).summary()
        console.print(f"Zombies: {ev['zombies']} event types | "
                      f"Animals: {ev['animals']} | Vehicles: {ev['vehicles']}")
