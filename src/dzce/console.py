"""Shared Rich console and theming for the dzce CLI."""
from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

THEME = Theme(
    {
        "info": "cyan",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "muted": "grey62",
        "accent": "bold magenta",
        "field": "bold white",
    }
)

console = Console(theme=THEME, highlight=False)


def ok(msg: str) -> None:
    console.print(f"[ok]\u2713[/ok] {msg}")


def warn(msg: str) -> None:
    console.print(f"[warn]\u26a0[/warn] {msg}")


def err(msg: str) -> None:
    console.print(f"[err]\u2717[/err] {msg}")


def info(msg: str) -> None:
    console.print(f"[info]\u2192[/info] {msg}")
