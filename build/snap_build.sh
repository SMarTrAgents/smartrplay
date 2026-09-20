#!/usr/bin/env bash
# =============================================================================
# SMarTrPlay v4 — Snap Packaging Script
# =============================================================================
# Erstellt ein Snap-Paket für SMarTrPlay mit snapcraft.
#
# Base:        core24
# Confinement: classic (vermeidet AppArmor-Probleme)
# App Command: python3 main.py
#
# Stage-Packages: python3, python3-pyqt5, ffmpeg
# Interfaces: wayland, x11, opengl, network, audio-playback
#
# Usage:  ./snap_build.sh [--install]
#   --install  Installiert das fertige Snap nach dem Build.
#
# Requirements: snapcraft
# =============================================================================
set -euo pipefail

# ── Konfiguration ─────────────────────────────────────────────────────────────
APP_NAME="smartr-o-lay"
SNAP_NAME="smartr-o-lay"
SUMMARY="SMarTrPlay v4 — SMartrAgents Overlay Application"
DESCRIPTION="SMarTrPlay ist die Overlay-Anwendung der SMartrAgents-Suite."
BASE="core24"
CONFINEMENT="classic"
APP_COMMAND="python3 main.py"

# Build-Verzeichnisse
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SNAPCRAFT_YAML="$SCRIPT_DIR/snapcraft.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Pre-flight Checks ────────────────────────────────────────────────────────
check_dependencies() {
    local missing=0

    if ! command -v snapcraft &>/dev/null; then
        warn "snapcraft ist nicht installiert."
        missing=1
    fi

    if ! command -v snap &>/dev/null; then
        warn "snapd (snap) ist nicht installiert."
        missing=1
    fi

    if [[ $missing -eq 1 ]]; then
        echo ""
        err "Erforderliche Tools fehlen! Installation:"
        echo ""
        echo "  Ubuntu/Debian (snapd):"
        echo "    sudo apt update && sudo apt install snapd"
        echo ""
        echo "  snapcraft (als Snap):"
        echo "    sudo snap install snapcraft --classic"
        echo ""
        echo "  snapcraft (via pip, falls Snap nicht verfügbar):"
        echo "    sudo apt install python3-pip && pip3 install snapcraft"
        echo ""
        echo "  LXD (für Multipass-Builds, empfohlen):"
        echo "    sudo snap install lxd"
        echo "    sudo lxd init --auto"
        echo ""
        echo "  Alternativ: Multipass für VM-basierte Builds:"
        echo "    sudo snap install multipass"
        echo ""
        echo "  Danach dieses Script erneut ausführen."
        echo ""
        exit 1
    fi

    ok "snapcraft und snap gefunden."
}

# ── snapcraft.yaml generieren ─────────────────────────────────────────────────
generate_snapcraft_yaml() {
    info "Generiere snapcraft.yaml: $SNAPCRAFT_YAML"

    cat > "$SNAPCRAFT_YAML" << 'YAML_EOF'
name: smartr-o-lay
version: '4.0'
summary: SMarTrPlay v4 — SMartrAgents Overlay Application
description: |
  SMarTrPlay ist die Overlay-Anwendung der SMartrAgents-Suite.
  Es bietet Audio-/Video-Overlay-Funktionen für Streams und Aufnahmen.

base: core24
confinement: classic
grade: stable

apps:
  smartr-o-lay:
    command: python3 $SNAP/usr/share/smartr-o-lay/main.py
    plugs:
      - wayland
      - x11
      - opengl
      - network
      - audio-playback
      - home
      - desktop
    environment:
      PYTHONPATH: $SNAP/usr/lib/python3/dist-packages:$SNAP/lib/python3.12/site-packages
      QT_QPA_PLATFORM: xcb
      DISPLAY: :0
      XDG_RUNTIME_DIR: /run/user/1000

parts:
  smartrplay-app:
    plugin: python
    source: ..
    source-type: local
    python-packages:
      - PyQt5
      - requests
    stage-packages:
      - python3
      - python3-pyqt5
      - ffmpeg
      - python3-requests
    organize:
      'src/*.py': usr/share/smartr-o-lay/
      'main.py': usr/share/smartr-o-lay/main.py
    prime:
      - -usr/share/doc
      - -usr/share/man
      - -usr/lib/python3*/dist-packages/__pycache__
YAML_EOF

    ok "snapcraft.yaml erstellt: $SNAPCRAFT_YAML"
}

# ── Build ──────────────────────────────────────────────────────────────────────
run_build() {
    info "Starte Snap-Build..."

    # Wechsel ins Build-Verzeichnis (snapcraft erwartet snapcraft.yaml im cwd)
    cd "$SCRIPT_DIR"

    # Snap bauen
    snapcraft clean 2>/dev/null || true
    snapcraft

    ok "Build abgeschlossen."
}

# ── Snap-File finden ───────────────────────────────────────────────────────────
find_snap_file() {
    local snap_file
    snap_file="$(find "$SCRIPT_DIR" -maxdepth 1 -name '*.snap' -print -quit)"

    if [[ -z "$snap_file" ]]; then
        err "Kein .snap-File gefunden nach dem Build!"
        exit 1
    fi

    echo "$snap_file"
}

# ── Install (optional) ────────────────────────────────────────────────────────
install_snap() {
    local snap_file="$1"

    info "Installiere Snap lokal: $snap_file"

    sudo snap install "$snap_file" --classic --dangerous

    ok "Installation abgeschlossen."
    echo "  Starten mit: snap run $SNAP_NAME"
}

# ── Main ────────────────────────────────────────────────────────────────────────
main() {
    local do_install=false

    if [[ "${1:-}" == "--install" ]]; then
        do_install=true
    fi

    echo ""
    echo "========================================"
    echo "  SMarTrPlay v4 — Snap Packaging"
    echo "========================================"
    echo ""

    check_dependencies
    generate_snapcraft_yaml
    run_build

    local snap_file
    snap_file="$(find_snap_file)"

    echo ""
    ok "Snap-Paket erfolgreich erstellt!"
    ls -lh "$snap_file"
    echo ""
    echo "  Snap-File: $snap_file"
    echo "  Installieren: sudo snap install $snap_file --classic --dangerous"
    echo "  Ausführen: snap run $SNAP_NAME"
    echo ""

    if [[ "$do_install" == true ]]; then
        install_snap "$snap_file"
    fi
}

main "$@"
