#!/usr/bin/env bash
#
# install.sh -- install the dzce CLI natively on Ubuntu, Debian and Arch.
#
# Strategy: ensure python3 + pipx exist (using the distro package manager),
# then `pipx install` this project into an isolated environment and put the
# `dzce` command on the user's PATH. pipx is used so the tool never collides
# with system Python packages.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

c_info() { printf '\033[36m->\033[0m %s\n' "$1"; }
c_ok()   { printf '\033[32m\xE2\x9C\x93\033[0m %s\n' "$1"; }
c_err()  { printf '\033[31m\xE2\x9C\x97\033[0m %s\n' "$1" >&2; }

detect_pm() {
    if   command -v apt-get >/dev/null 2>&1; then echo "apt"
    elif command -v pacman  >/dev/null 2>&1; then echo "pacman"
    else echo "unknown"; fi
}

ensure_deps() {
    local pm="$1"
    case "$pm" in
        apt)
            c_info "Installing python3, pip and pipx via apt (sudo may prompt)..."
            sudo apt-get update -y
            sudo apt-get install -y python3 python3-pip pipx
            ;;
        pacman)
            c_info "Installing python, python-pip and python-pipx via pacman (sudo may prompt)..."
            sudo pacman -Sy --needed --noconfirm python python-pip python-pipx
            ;;
        *)
            c_err "Unsupported distro: no apt-get or pacman found."
            c_err "Install python3 and pipx manually, then run: pipx install '$SCRIPT_DIR'"
            exit 1
            ;;
    esac
}

main() {
    local pm; pm="$(detect_pm)"
    c_info "Detected package manager: $pm"

    if ! command -v pipx >/dev/null 2>&1; then
        ensure_deps "$pm"
    else
        c_ok "pipx already present"
    fi

    # Make sure pipx's bin dir is on PATH for future shells.
    pipx ensurepath >/dev/null 2>&1 || true

    c_info "Installing dzce from $SCRIPT_DIR ..."
    pipx install --force "$SCRIPT_DIR"

    c_ok "Installed. Open a new terminal (or run: source ~/.bashrc) then try:"
    printf '    dzce --help\n    dzce --version\n'
}

main "$@"
