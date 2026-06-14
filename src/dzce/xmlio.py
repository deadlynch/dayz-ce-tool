"""Structure-preserving XML I/O for DayZ Central Economy files.

DayZ refuses to load malformed CE files, and many community tools corrupt the
original formatting (comments, attribute order, indentation). We use lxml with
blank-text preservation so existing nodes are written back byte-faithfully, and
we re-emit the exact ``<?xml ... standalone="yes"?>`` declaration DayZ ships.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
from pathlib import Path

from lxml import etree

_DECL_RE = re.compile(rb"<\?xml[^>]*\?>")
_DEFAULT_DECL = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

BACKUP_DIRNAME = ".dzce-backups"
MAX_BACKUPS = 20

# When True, save() simulates: it neither backs up nor writes to disk. Set by
# the CLI's --dry-run flag (or temporarily by the menu's "simulate" option) so
# that every operation can be previewed without changing any file.
DRY_RUN = False


class CEParseError(ValueError):
    """A CE XML file could not be parsed. Carries a friendly, contextual message."""


class CEWriteError(Exception):
    """A CE file could not be written (usually a permission problem)."""


def _user_name(uid: int | None = None) -> str:
    try:
        import pwd
        return pwd.getpwuid(os.geteuid() if uid is None else uid).pw_name
    except Exception:
        return "?"


def _write_error(path: Path, exc: OSError) -> CEWriteError:
    me = _user_name()
    try:
        owner = _user_name(path.stat().st_uid) if path.exists() else _user_name(path.parent.stat().st_uid)
    except OSError:
        owner = "?"
    return CEWriteError(
        f"Couldn't write {path.name}: {exc.strerror or exc}.\n"
        f"dzce is running as '{me}', but that file/folder is owned by '{owner}'.\n"
        "Fix it one of these ways:\n"
        f"  - run dzce as the owner, e.g.:  sudo -u {owner} dzce ...\n"
        "  - or give your user write access to the mission folder\n"
        "Tip: add --dry-run to preview changes without writing anything."
    )


def make_parser() -> etree.XMLParser:
    # remove_blank_text=False keeps original indentation text nodes intact.
    return etree.XMLParser(remove_blank_text=False, strip_cdata=False, resolve_entities=False)


def _friendly_parse_error(path: Path, exc: etree.XMLSyntaxError) -> CEParseError:
    lineno = getattr(exc, "lineno", 0) or 0
    msg = (getattr(exc, "msg", None) or str(exc)).strip()
    block = ""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, lineno - 4)
        end = min(len(raw), lineno + 2)
        rendered = [
            f"{'  >> ' if (i + 1) == lineno else '     '}{i + 1:>4} | {raw[i]}"
            for i in range(start, end)
        ]
        if rendered:
            block = "\n" + "\n".join(rendered) + "\n"
    except OSError:
        pass
    low = msg.lower()
    if "extra content at the end" in low and looks_like_unwrapped_fragment(path):
        hint = (
            "\nThis looks like a copy-paste snippet of <type> entries with no "
            "<types> wrapper (some mods ship loot this way).\n"
            f"  Fix it automatically with:  dzce mod wrap {path.name}\n")
    elif "extra content at the end" in low:
        hint = (
            "\nLikely cause: something comes after the XML document already ended."
            " Usually one of:\n"
            "  - a second <types>...</types> block pasted after the first one\n"
            "  - <type> entries not all wrapped in one <types> ... </types>\n"
            "  - a stray or duplicated tag near that line\n")
    elif "tag mismatch" in low or "expected" in low or "not closed" in low:
        hint = "\nLikely cause: a tag near that line isn't opened/closed properly.\n"
    else:
        hint = ""
    return CEParseError(
        f"{path.name} is not valid XML, so DayZ would reject it too.\n"
        f"  Problem: {msg}" + (f"  (line {lineno})" if lineno else "") + "\n"
        f"{block}{hint}"
        f"Open {path.name} around line {lineno or '?'} to fix it, then try again."
    )


def load(path: Path) -> etree._ElementTree:
    """Parse a CE XML file, raising a friendly, contextual error on failure."""
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} does not exist")
    try:
        return etree.parse(str(path), make_parser())
    except etree.XMLSyntaxError as exc:
        raise _friendly_parse_error(Path(path), exc) from exc


def _body_without_declaration(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", raw, count=1)


# Correct root element per CE file, so wrapping a fragment uses the right tag
# (a spawnabletypes snippet must NOT be wrapped in <types>).
_ROOT_BY_FILENAME = {
    "types.xml": "types",
    "cfgspawnabletypes.xml": "spawnabletypes",
    "cfgeventgroups.xml": "eventgroupdef",
    "events.xml": "events",
}


def _infer_root_tag(path: Path) -> str:
    return _ROOT_BY_FILENAME.get(path.name.lower(), "types")


def looks_like_unwrapped_fragment(path: Path, root_tag: str | None = None) -> bool:
    """True if the file is a copy-paste snippet of entries with no single root
    element -- a common, fixable shape for mod loot/spawnable files."""
    path = Path(path)
    root_tag = root_tag or _infer_root_tag(path)
    try:
        wrapped = f"<{root_tag}>\n" + _body_without_declaration(path) + f"\n</{root_tag}>"
        root = etree.fromstring(wrapped.encode("utf-8"), make_parser())
    except etree.XMLSyntaxError:
        return False
    return any(isinstance(ch.tag, str) for ch in root)


def wrap_fragment(path: Path, root_tag: str | None = None) -> bool:
    """Wrap an unwrapped entry snippet in its proper root element and save it
    (with a backup). The root is inferred from the filename. Returns False if
    the file isn't that shape."""
    path = Path(path)
    root_tag = root_tag or _infer_root_tag(path)
    if not looks_like_unwrapped_fragment(path, root_tag):
        return False
    body = _body_without_declaration(path).strip("\n")
    new = _DEFAULT_DECL.decode() + f"\n<{root_tag}>\n" + body + f"\n</{root_tag}>\n"
    if not DRY_RUN:
        backup(path)
        try:
            path.write_text(new, encoding="utf-8")
        except OSError as exc:
            raise _write_error(path, exc) from exc
    return True


def _original_declaration(path: Path) -> bytes:
    try:
        head = path.read_bytes()[:200]
    except OSError:
        return _DEFAULT_DECL
    m = _DECL_RE.search(head)
    return m.group(0) if m else _DEFAULT_DECL


def backup(path: Path) -> Path | None:
    """Copy ``path`` into the mission's .dzce-backups dir before mutating it."""
    if not path.exists():
        return None
    bdir = path.parent / BACKUP_DIRNAME
    try:
        bdir.mkdir(exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = bdir / f"{path.name}.{stamp}.bak"
        shutil.copy2(path, dest)
    except OSError as exc:
        raise _write_error(bdir, exc) from exc
    _prune_backups(bdir, path.name)
    return dest


def _prune_backups(bdir: Path, filename: str) -> None:
    backups = sorted(bdir.glob(f"{filename}.*.bak"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-MAX_BACKUPS]:
        old.unlink(missing_ok=True)


def save(tree: etree._ElementTree, path: Path, *, do_backup: bool = True) -> None:
    """Write ``tree`` back to ``path`` preserving the original XML declaration.
    Under DRY_RUN this is a no-op (nothing is backed up or written)."""
    if DRY_RUN:
        return
    if do_backup:
        backup(path)
    decl = _original_declaration(path)
    body = etree.tostring(tree, encoding="UTF-8", xml_declaration=False)
    body = body.lstrip()
    try:
        path.write_bytes(decl + b"\n" + body + (b"" if body.endswith(b"\n") else b"\n"))
    except OSError as exc:
        raise _write_error(path, exc) from exc


def indent_like_siblings(parent: etree._Element, child: etree._Element) -> None:
    """Give a freshly inserted child the indentation of its siblings."""
    kids = list(parent)
    if len(kids) >= 2:
        prev = kids[-2]
        child.tail = prev.tail
        if prev.tail is None and parent.text:
            child.tail = parent.text
    elif parent.text:
        child.tail = parent.text
