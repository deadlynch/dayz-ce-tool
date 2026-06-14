#!/usr/bin/env bash
#
# uninstall.sh -- remove the dzce CLI installed by install.sh.
#
set -euo pipefail

c_ok()  { printf '\033[32m\xE2\x9C\x93\033[0m %s\n' "$1"; }
c_err() { printf '\033[31m\xE2\x9C\x97\033[0m %s\n' "$1" >&2; }

if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q '\bdzce\b'; then
    pipx uninstall dzce
    c_ok "dzce removed."
else
    c_err "dzce does not appear to be installed via pipx."
    c_err "If you installed with pip, run: pip uninstall dzce"
    exit 1
fi

printf 'Note: per-mission backups in .dzce-backups/ are left untouched.\n'
