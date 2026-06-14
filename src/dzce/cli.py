"""dzce -- DayZ Central Economy toolkit CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .balance import RARITY_PRESETS, LootBalancer
from .console import console, err, info, ok, warn
from .files.events_file import EventsFile
from .files.globals_file import GlobalsFile
from .files.types_file import TypesFile
from .mission import Mission, discover
from .mods import ModIntegrator
from .validate import validate as run_validate

app = typer.Typer(
    add_completion=True,
    no_args_is_help=False,
    help="Configure and balance DayZ Central Economy XML files from the terminal.",
)
types_app = typer.Typer(help="Inspect and edit individual loot types.")
balance_app = typer.Typer(help="Balance loot in bulk.")
events_app = typer.Typer(help="Scale zombies, animals and vehicles.")
globals_app = typer.Typer(help="Read and write global economy variables.")
mod_app = typer.Typer(help="Integrate and balance mods.")
backup_app = typer.Typer(help="Manage automatic backups.")
recipe_app = typer.Typer(help="Apply one-shot setup presets.")
spawnables_app = typer.Typer(help="Edit attachment/cargo spawn chances.")
eventgroups_app = typer.Typer(help="Scale loot inside event groups (convoys, trains).")
app.add_typer(types_app, name="types")
app.add_typer(balance_app, name="balance")
app.add_typer(events_app, name="events")
app.add_typer(globals_app, name="globals")
app.add_typer(mod_app, name="mod")
app.add_typer(backup_app, name="backup")
app.add_typer(recipe_app, name="recipe")
app.add_typer(spawnables_app, name="spawnables")
app.add_typer(eventgroups_app, name="eventgroups")


def _resolve_mission(ctx: typer.Context) -> Mission:
    m: Optional[Mission] = ctx.obj.get("mission") if ctx.obj else None
    if m is None:
        err("No DayZ mission folder found. Run inside a mission folder or pass --mission.")
        raise typer.Exit(2)
    return m


def _group_or_select(types, group, category, usage, tier, name):
    """Resolve a selection either from a curated item group or from filters."""
    if group:
        from . import groups as _groups
        if group not in _groups.GROUPS:
            err(f"unknown group '{group}'. run: dzce groups")
            raise typer.Exit(1)
        return _groups.resolve(types.all(), group)
    return types.select(name_glob=name, category=category, usage=usage, tier=tier)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    mission: Optional[Path] = typer.Option(
        None, "--mission", "-m", help="Path to the mission folder (or its parent)."),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Simulate: show what would change without writing any file."),
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
):
    if version:
        console.print(f"dzce {__version__}")
        raise typer.Exit()
    if dry_run:
        from . import xmlio
        xmlio.DRY_RUN = True
        console.print("[warn]DRY RUN[/warn] [muted]-- simulating; no files will be "
                      "written and no backups made.[/muted]\n")
    from . import config as _config
    from .mission import Mission, looks_like_mission
    if mission is not None:                     # explicit -m always wins
        m = discover(mission)
    elif looks_like_mission(Path.cwd()):        # running inside a mission
        m = Mission(Path.cwd().resolve())
    else:                                       # remembered default, then scan
        saved = _config.get_last_mission()
        if saved and looks_like_mission(Path(saved)):
            m = Mission(Path(saved).resolve())
        else:
            m = discover(None)
    if m is not None:
        _config.set_last_mission(str(m.root))
    ctx.obj = {"mission": m, "dry_run": dry_run}
    if ctx.invoked_subcommand is None:
        from .menu import run_menu
        run_menu(ctx.obj["mission"])


# --------------------------------------------------------------------------
# top-level: info / summary / validate
# --------------------------------------------------------------------------
@app.command()
def info_cmd(ctx: typer.Context):  # name overridden below
    """Show the detected mission and which CE files are present."""
    m = _resolve_mission(ctx)
    console.print(Panel.fit(f"[accent]{m.map_name}[/accent]\n{m.root}", title="Mission"))
    table = Table("file", "key", "status")
    for key in ("types", "globals", "events", "economy", "economycore",
                "spawnabletypes", "limitsdefinition"):
        p = m.path(key)
        status = "[ok]found[/ok]" if p.exists() else "[muted]missing[/muted]"
        table.add_row(p.name, key, status)
    console.print(table)


app.command(name="info")(info_cmd)


@app.command()
def overview(ctx: typer.Context):
    """One-shot read-only snapshot of the whole server: files, mods, loot,
    events, spawnables, globals and health. Run this first."""
    m = _resolve_mission(ctx)
    from .overview import render_overview
    render_overview(m)


@app.command()
def fix(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", "-y", help="skip confirmation"),
):
    """Apply only the SAFE, mechanical fixes (wrap broken mod files; give min
    headroom). Judgment-call issues are reported by `dzce doctor`, not changed."""
    m = _resolve_mission(ctx)
    from . import fixes, xmlio
    simulate = bool(ctx.obj and ctx.obj.get("dry_run"))

    # preview by scanning without applying (dry pass), unless already in dry-run
    if not simulate and not yes:
        xmlio.DRY_RUN = True
        preview = fixes.plan_and_apply(m)
        xmlio.DRY_RUN = False
        if preview.total == 0 and not preview.unwrappable:
            ok("Nothing to auto-fix.")
            _fix_report_unfixable(m)
            return
        if preview.wrapped:
            info(f"will wrap {len(preview.wrapped)} broken file(s): "
                 f"{', '.join(preview.wrapped)}")
        if preview.headroom:
            info(f"will give min-headroom to {len(preview.headroom)} item(s)")
        if not typer.confirm("Apply these safe fixes? Backups are saved first."):
            raise typer.Exit(0)

    plan = fixes.plan_and_apply(m)
    verb = "would fix" if simulate else "fixed"
    if plan.wrapped:
        ok(f"{verb}: wrapped {len(plan.wrapped)} broken file(s) -> "
           f"{', '.join(plan.wrapped)}")
    if plan.headroom:
        ok(f"{verb}: lowered min on {len(plan.headroom)} item(s) (min was >= nominal)")
    if not plan.total:
        ok("No safe fixes needed.")
    if plan.unwrappable:
        warn("these files are broken but NOT auto-fixable (open them at the "
             "reported line): " + ", ".join(plan.unwrappable))
    _fix_report_unfixable(m)


def _fix_report_unfixable(m):
    """Point the user at doctor for the judgment-call problems fix won't touch."""
    from .doctor import diagnose
    kinds = {f.area for f in diagnose(m)
             if f.area in ("unreachable loot", "nominal outlier", "empty weapons",
                           "mod flooding", "dead usage", "dead tier")}
    if kinds:
        info("Not auto-fixed (need your judgment): " + ", ".join(sorted(kinds))
             + ".  See `dzce doctor`.")


@app.command()
def config(
    ctx: typer.Context,
    set_mission: Optional[Path] = typer.Option(
        None, "--set-mission", help="Save a default mission folder."),
):
    """Show or set saved settings (like your default mission folder)."""
    from . import config as _config
    if set_mission is not None:
        mm = discover(set_mission)
        if mm is None:
            err(f"{set_mission} doesn't look like a mission folder.")
            raise typer.Exit(1)
        _config.set_last_mission(str(mm.root))
        ok(f"default mission saved: {mm.root}")
        return
    cfg = _config.load()
    console.print(f"[field]Config file:[/field] {_config.config_path()}")
    console.print(f"[field]Default mission:[/field] {cfg.get('last_mission') or '(none yet)'}")


@app.command()
def groups(ctx: typer.Context):
    """List curated item groups (medical, building, ammo, ...) and how many
    items each currently matches on this server."""
    m = _resolve_mission(ctx)
    from . import groups as _groups
    types = TypesFile(m.path("types")) if m.has("types") else None
    all_types = types.all() if types else []
    t = Table("group", "matches here", "what it covers")
    for g in _groups.GROUPS.values():
        n = len(_groups.resolve(all_types, g.key)) if all_types else 0
        t.add_row(g.key, str(n), g.description)
    console.print(t)
    console.print("[muted]Use with: dzce balance scale 1.5 --group medical[/muted]")


@app.command()
def summary(ctx: typer.Context):
    """High-level shape of the economy: categories, tiers, events."""
    m = _resolve_mission(ctx)
    types = TypesFile(m.path("types"))
    bal = LootBalancer(types)
    t = Table("category", "types", "total nominal", title="Loot by category")
    for s in bal.category_stats():
        t.add_row(s.category, str(s.count), str(s.total_nominal))
    console.print(t)
    console.print(f"[field]Total types:[/field] {len(types.all())}    "
                  f"[field]Total nominal:[/field] {bal.total_nominal()}")
    if m.has("events"):
        ev = EventsFile(m.path("events")).summary()
        console.print(f"[field]Events:[/field] zombies={ev['zombies']} "
                      f"animals={ev['animals']} vehicles={ev['vehicles']} total={ev['total']}")


@app.command()
def doctor(ctx: typer.Context):
    """Heuristic health check: surface suspicious patterns with suggestions
    (advisory, read-only). Complements `validate` (hard errors)."""
    m = _resolve_mission(ctx)
    from .doctor import run_doctor
    run_doctor(m)


@app.command()
def validate(ctx: typer.Context):
    """Cross-check files for the mistakes DayZ fails on silently."""
    m = _resolve_mission(ctx)
    findings = run_validate(m)
    if not findings:
        ok("No problems found.")
        return
    t = Table("level", "where", "message")
    for f in findings:
        style = "err" if f.level == "error" else "warn"
        t.add_row(f"[{style}]{f.level}[/{style}]", f.where, f.message)
    console.print(t)
    errors = sum(1 for f in findings if f.level == "error")
    console.print(f"\n{errors} error(s), {len(findings) - errors} warning(s).")
    if errors:
        raise typer.Exit(1)


# --------------------------------------------------------------------------
# types
# --------------------------------------------------------------------------
@types_app.command("list")
def types_list(
    ctx: typer.Context,
    category: Optional[str] = typer.Option(None),
    usage: Optional[str] = typer.Option(None),
    tier: Optional[str] = typer.Option(None),
    name: Optional[str] = typer.Option(None, help="glob, e.g. 'mag_*'"),
    limit: int = typer.Option(40),
):
    """List loot types, optionally filtered."""
    m = _resolve_mission(ctx)
    types = TypesFile(m.path("types"))
    sel = types.select(name_glob=name, category=category, usage=usage, tier=tier)
    t = Table("name", "nominal", "min", "restock", "cost", "category", "tiers")
    for lt in sel[:limit]:
        t.add_row(lt.name, str(lt.nominal), str(lt.min), str(lt.restock),
                  str(lt.cost), lt.category or "-", ",".join(lt.values) or "-")
    console.print(t)
    if len(sel) > limit:
        info(f"showing {limit} of {len(sel)} matches (use --limit)")


@types_app.command("show")
def types_show(ctx: typer.Context, name: str):
    """Show every field of one type."""
    m = _resolve_mission(ctx)
    lt = TypesFile(m.path("types")).get(name)
    if lt is None:
        err(f"'{name}' not found")
        raise typer.Exit(1)
    console.print(lt)


@types_app.command("set")
def types_set(
    ctx: typer.Context,
    name: str,
    nominal: Optional[int] = typer.Option(None),
    min_: Optional[int] = typer.Option(None, "--min"),
    lifetime: Optional[int] = typer.Option(None),
    restock: Optional[int] = typer.Option(None),
    cost: Optional[int] = typer.Option(None),
):
    """Set numeric fields on a single type."""
    m = _resolve_mission(ctx)
    types = TypesFile(m.path("types"))
    lt = types.get(name)
    if lt is None:
        err(f"'{name}' not found")
        raise typer.Exit(1)
    fields = {k: v for k, v in dict(
        nominal=nominal, min=min_, lifetime=lifetime, restock=restock, cost=cost
    ).items() if v is not None}
    LootBalancer(types).set_fields(lt, **fields)
    types.save()
    ok(f"updated {name}: {fields}")


# --------------------------------------------------------------------------
# balance
# --------------------------------------------------------------------------
@balance_app.command("scale")
def balance_scale(
    ctx: typer.Context,
    factor: float,
    category: Optional[str] = typer.Option(None),
    usage: Optional[str] = typer.Option(None),
    tier: Optional[str] = typer.Option(None),
    name: Optional[str] = typer.Option(None, help="glob"),
    group: Optional[str] = typer.Option(None, help="curated item group (see `dzce groups`)"),
):
    """Multiply nominal & min of a selection by FACTOR (e.g. 1.5)."""
    m = _resolve_mission(ctx)
    types = TypesFile(m.path("types"))
    sel = _group_or_select(types, group, category, usage, tier, name)
    n = LootBalancer(types).scale(sel, factor)
    types.save()
    ok(f"scaled {n} types by x{factor}")


@balance_app.command("rarity")
def balance_rarity(
    ctx: typer.Context,
    rarity: str = typer.Argument(..., help=f"one of: {', '.join(RARITY_PRESETS)}"),
    category: Optional[str] = typer.Option(None),
    usage: Optional[str] = typer.Option(None),
    tier: Optional[str] = typer.Option(None),
    name: Optional[str] = typer.Option(None, help="glob"),
    group: Optional[str] = typer.Option(None, help="curated item group (see `dzce groups`)"),
):
    """Apply a rarity preset (nominal/min/restock/cost) to a selection."""
    m = _resolve_mission(ctx)
    if rarity not in RARITY_PRESETS:
        err(f"unknown rarity. choose from: {', '.join(RARITY_PRESETS)}")
        raise typer.Exit(1)
    types = TypesFile(m.path("types"))
    sel = _group_or_select(types, group, category, usage, tier, name)
    n = LootBalancer(types).apply_rarity(sel, rarity)
    types.save()
    ok(f"set {n} types to '{rarity}'")


# --------------------------------------------------------------------------
# events (zombies / animals / vehicles)
# --------------------------------------------------------------------------
@events_app.command("scale")
def events_scale(
    ctx: typer.Context,
    kind: str = typer.Argument(..., help="zombies | animals | vehicles"),
    factor: float = typer.Argument(...),
):
    """Scale nominal/min/max for all events of KIND."""
    m = _resolve_mission(ctx)
    ef = EventsFile(m.path("events"))
    try:
        sel = ef.by_kind(kind)
    except KeyError as e:
        err(str(e))
        raise typer.Exit(1)
    n = ef.scale(sel, factor)
    ef.save()
    ok(f"scaled {n} {kind} events by x{factor}")


# --------------------------------------------------------------------------
# globals
# --------------------------------------------------------------------------
@globals_app.command("get")
def globals_get(ctx: typer.Context, name: str):
    m = _resolve_mission(ctx)
    val = GlobalsFile(m.path("globals")).get(name)
    if val is None:
        err(f"variable '{name}' not found")
        raise typer.Exit(1)
    console.print(f"{name} = {val}")


@globals_app.command("set")
def globals_set(ctx: typer.Context, name: str, value: str):
    m = _resolve_mission(ctx)
    g = GlobalsFile(m.path("globals"))
    if not g.set(name, value):
        err(f"variable '{name}' not found")
        raise typer.Exit(1)
    g.save()
    ok(f"{name} = {value}")


@globals_app.command("list")
def globals_list(ctx: typer.Context):
    m = _resolve_mission(ctx)
    t = Table("variable", "value")
    for k, v in GlobalsFile(m.path("globals")).all().items():
        t.add_row(k, v)
    console.print(t)


# --------------------------------------------------------------------------
# mod integration
# --------------------------------------------------------------------------
@mod_app.command("add")
def mod_add(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Folder containing the mod's types.xml"),
    rarity: Optional[str] = typer.Option(
        None, help=f"force a rarity instead of baseline: {', '.join(RARITY_PRESETS)}"),
    baseline: str = typer.Option(
        "stock", help="balance against 'stock' (db/types.xml) or 'merged' "
                      "(stock + already-integrated mods)"),
    fix_vocab: bool = typer.Option(True, help="auto-declare missing categories/usages/tiers"),
    no_balance: bool = typer.Option(False, help="skip rebalancing the mod's values"),
):
    """Full pipeline: register, validate vocab, balance vs vanilla, audit deps."""
    m = _resolve_mission(ctx)
    mi = ModIntegrator(m)
    scan = mi.scan(path)
    if scan.types_path is None:
        err(f"no types.xml found under {path}")
        raise typer.Exit(1)
    info(f"mod '{scan.name}': {len(scan.items)} types from {scan.types_path}")

    if mi.register(scan):
        ok(f"registered CE folder '{scan.name}' in cfgeconomycore.xml")
    else:
        info("CE folder already registered")

    rep = mi.check_vocabulary(scan)
    if rep.ok:
        ok("vocabulary OK -- all categories/usages/tiers/tags are declared")
    else:
        warn("undeclared vocabulary found:")
        for label, vals in (("categories", rep.missing_categories),
                            ("usages", rep.missing_usages),
                            ("tiers", rep.missing_tiers), ("tags", rep.missing_tags)):
            if vals:
                console.print(f"  {label}: {', '.join(sorted(vals))}")
        if fix_vocab:
            n = mi.fix_vocabulary(rep)
            ok(f"declared {n} new vocabulary entries in cfglimitsdefinition.xml")
        else:
            warn("items using these will NOT spawn until declared (run with --fix-vocab)")

    if not no_balance:
        changes = mi.balance(scan, rarity=rarity, baseline=baseline)
        if changes:
            t = Table("item", "nominal", "min", "cost",
                      f"peers ({baseline})")
            for c in changes:
                t.add_row(c.name,
                          f"{c.before[0]}->{c.after[0]}",
                          f"{c.before[1]}->{c.after[1]}",
                          f"{c.before[2]}->{c.after[2]}",
                          str(c.peers) if c.peers else "(forced)")
            console.print(t)
            ok(f"rebalanced {len(changes)} mod items")
        else:
            info("nothing to rebalance")

    issues = mi.audit(scan)
    dups = mi.spawnable_duplicates(scan)
    if dups:
        warn("duplicate entries in the mod's cfgspawnabletypes.xml "
             "(DayZ keeps only one):")
        for d in dups:
            console.print(f"  [warn]{d}[/warn]")
    if issues:
        warn("dependency issues (these weapons may spawn empty):")
        for iss in issues:
            console.print(f"  [warn]{iss.weapon}[/warn]: {iss.reason}")
        info("add a cfgspawnabletypes entry giving each a magazine attachment.")
    else:
        ok("dependency audit clean")


# --------------------------------------------------------------------------
# recipes (automation presets)
# --------------------------------------------------------------------------
@recipe_app.command("list")
def recipe_list():
    """Show available one-shot setup presets."""
    from .recipes import RECIPES
    t = Table("key", "title", "what it does")
    for r in RECIPES.values():
        t.add_row(r.key, r.title, r.description)
    console.print(t)


@recipe_app.command("apply")
def recipe_apply(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="recipe key (see `dzce recipe list`)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="skip confirmation"),
):
    """Apply a preset in one shot (great for scripts/automation)."""
    from .recipes import RECIPES, apply_recipe
    m = _resolve_mission(ctx)
    recipe = RECIPES.get(key)
    if recipe is None:
        err(f"unknown recipe '{key}'. run: dzce recipe list")
        raise typer.Exit(1)
    info(f"{recipe.title} -- {recipe.description}")
    if not yes:
        if not typer.confirm("Apply this preset? Backups are saved first."):
            raise typer.Exit(0)
    for r in apply_recipe(m, recipe):
        ok(f"{r.label}: {r.affected} item(s)")


# --------------------------------------------------------------------------
# spawnables (attachment/cargo chances)
# --------------------------------------------------------------------------
@spawnables_app.command("list")
def spawnables_list(
    ctx: typer.Context,
    kind: str = typer.Option("all", help="attachments | cargo | all"),
    limit: int = typer.Option(40),
):
    """List attachment/cargo spawn chances."""
    m = _resolve_mission(ctx)
    from .files.spawnabletypes_file import SpawnableTypesFile
    rows = SpawnableTypesFile(m.path("spawnabletypes")).chance_rows(kind)
    t = Table("item", "group", "chance")
    for name, gk, chance in rows[:limit]:
        t.add_row(name, gk, f"{chance:.2f}")
    console.print(t)
    if len(rows) > limit:
        info(f"showing {limit} of {len(rows)} (use --limit)")


@spawnables_app.command("scale-chance")
def spawnables_scale(
    ctx: typer.Context,
    factor: float,
    kind: str = typer.Option("all", help="attachments | cargo | all"),
):
    """Multiply attachment/cargo spawn chances by FACTOR (clamped to 0..1)."""
    m = _resolve_mission(ctx)
    from .files.spawnabletypes_file import SpawnableTypesFile
    stp = SpawnableTypesFile(m.path("spawnabletypes"))
    n = stp.scale_chances(factor, kind=kind)
    stp.save()
    ok(f"scaled {n} {kind} group chance(s) by x{factor}")


@spawnables_app.command("set-chance")
def spawnables_set(
    ctx: typer.Context,
    name: str,
    value: float,
    kind: str = typer.Option("attachments", help="attachments | cargo"),
):
    """Set the spawn chance (0..1) of one item's attachment/cargo group."""
    m = _resolve_mission(ctx)
    from .files.spawnabletypes_file import SpawnableTypesFile
    stp = SpawnableTypesFile(m.path("spawnabletypes"))
    if not stp.set_chance(name, value, kind=kind):
        err(f"no {kind} group found for '{name}'")
        raise typer.Exit(1)
    stp.save()
    ok(f"{name} {kind} chance = {min(1.0, max(0.0, value)):.2f}")


# --------------------------------------------------------------------------
# eventgroups (convoys / trains / shipwrecks loot)
# --------------------------------------------------------------------------
@eventgroups_app.command("list")
def eventgroups_list(ctx: typer.Context, limit: int = typer.Option(50)):
    """List event groups and their object counts."""
    m = _resolve_mission(ctx)
    from .files.eventgroups_file import EventGroupsFile
    egf = EventGroupsFile(m.path("eventgroups"))
    t = Table("group", "objects")
    for g in egf.groups()[:limit]:
        t.add_row(g.get("name") or "?", str(len(g.findall("child"))))
    console.print(t)
    s = egf.summary()
    console.print(f"[field]{s['groups']} groups, {s['children']} objects total[/field]")


@eventgroups_app.command("scale-loot")
def eventgroups_scale(
    ctx: typer.Context,
    factor: float,
    group: Optional[str] = typer.Option(None, help="limit to one group name"),
):
    """Scale lootmin/lootmax inside event groups (positions never change)."""
    m = _resolve_mission(ctx)
    from .files.eventgroups_file import EventGroupsFile
    egf = EventGroupsFile(m.path("eventgroups"))
    n = egf.scale_loot(factor, group=group)
    egf.save()
    scope = f"group '{group}'" if group else "all groups"
    ok(f"scaled loot on {n} object(s) in {scope} by x{factor}")


# --------------------------------------------------------------------------
# backups
# --------------------------------------------------------------------------
@mod_app.command("wrap")
def mod_wrap(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="The mod's types.xml (or its folder)."),
):
    """Fix a copy-paste loot snippet by wrapping its <type> entries in a proper
    <types> root, so it becomes a valid, loadable file."""
    from . import xmlio
    target = path
    if target.is_dir():
        for cand in (target / "types.xml", target / "db" / "types.xml"):
            if cand.exists():
                target = cand
                break
    if not target.exists():
        err(f"no types.xml found at {path}")
        raise typer.Exit(1)
    # already valid?
    try:
        xmlio.load(target)
        info(f"{target.name} is already valid XML -- nothing to wrap.")
        return
    except xmlio.CEParseError:
        pass
    if xmlio.wrap_fragment(target):
        ok(f"wrapped {target} in a proper root element (backup saved). It's valid now.")
        info("Next: the values may be low/zero -- run `dzce mod add` to balance it.")
    else:
        err("This file isn't a simple unwrapped <type> snippet; open it and fix "
            "the XML by hand around the reported line.")
        raise typer.Exit(1)


@backup_app.command("list")
def backup_list(ctx: typer.Context):
    m = _resolve_mission(ctx)
    from .xmlio import BACKUP_DIRNAME
    found = False
    for sub in (m.root, m.root / "db"):
        bdir = sub / BACKUP_DIRNAME
        if bdir.is_dir():
            for b in sorted(bdir.glob("*.bak")):
                console.print(b)
                found = True
    if not found:
        info("no backups yet")


@backup_app.command("restore")
def backup_restore(ctx: typer.Context, backup_file: Path):
    """Restore a .bak file over its original."""
    import shutil
    if not backup_file.exists():
        err("backup not found")
        raise typer.Exit(1)
    original = backup_file.parent.parent / backup_file.name.rsplit(".", 2)[0]
    shutil.copy2(backup_file, original)
    ok(f"restored {original}")


def run():
    """Entry point: run the app, turning CE file errors into clean messages."""
    from . import xmlio
    try:
        app()
    except (xmlio.CEParseError, xmlio.CEWriteError) as exc:
        err(str(exc))
        raise SystemExit(1)


if __name__ == "__main__":
    app()
