#!/usr/bin/env bash
# =============================================================================
# SMarTrPlay v4 — Flatpak Packaging Script
# =============================================================================
# Erstellt ein Flatpak-Paket für SMarTrPlay mit flatpak-builder.
#
# App ID:  ai.smartragents.SMarTrPlay
# Runtime: org.freedesktop.Platform 23.08
# SDK:     org.freedesktop.Sdk 23.08
# Python-Dependencies: PyQt5, requests (via pip)
#
# Usage:  ./flatpak_build.sh [--install]
#   --install  Installiert das fertige Flatpak nach dem Build.
#
# Requirements: flatpak, flatpak-builder
# =============================================================================
set -euo pipefail

# ── Konfiguration ─────────────────────────────────────────────────────────────
APP_ID="ai.smartragents.SMarTrPlay"
RUNTIME="org.freedesktop.Platform"
RUNTIME_VERSION="23.08"
SDK="org.freedesktop.Sdk"
SDK_VERSION="23.08"
BRANCH="stable"

# Build-Verzeichnisse
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/_flatpak_build"
REPO_DIR="$SCRIPT_DIR/_flatpak_repo"
MANIFEST="$SCRIPT_DIR/${APP_ID}.json"

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

    if ! command -v flatpak &>/dev/null; then
        warn "flatpak ist nicht installiert."
        missing=1
    fi

    if ! command -v flatpak-builder &>/dev/null; then
        warn "flatpak-builder ist nicht installiert."
        missing=1
    fi

    if [[ $missing -eq 1 ]]; then
        echo ""
        err "Erforderliche Tools fehlen! Installation:"
        echo ""
        echo "  Ubuntu/Debian:"
        echo "    sudo apt update && sudo apt install flatpak flatpak-builder"
        echo ""
        echo "  Fedora:"
        echo "    sudo dnf install flatpak flatpak-builder"
        echo ""
        echo "  Arch:"
        echo "    sudo pacman -S flatpak flatpak-builder"
        echo ""
        echo "  Flathub Runtime hinzufügen:"
        echo "    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo"
        echo "    flatpak install flathub ${RUNTIME}//${RUNTIME_VERSION}"
        echo "    flatpak install flathub ${SDK}//${SDK_VERSION}"
        echo ""
        exit 1
    fi

    ok "flatpak und flatpak-builder gefunden."
}

# ── Manifest generieren ───────────────────────────────────────────────────────
generate_manifest() {
    info "Generiere Flatpak-Manifest: $MANIFEST"

    cat > "$MANIFEST" << 'MANIFEST_EOF'
{
    "app-id": "ai.smartragents.SMarTrPlay",
    "runtime": "org.freedesktop.Platform",
    "runtime-version": "23.08",
    "sdk": "org.freedesktop.Sdk",
    "command": "smartrplay",
    "finish-args": [
        "--share=ipc",
        "--socket=x11",
        "--socket=wayland",
        "--device=dri",
        "--share=network",
        "--socket=pulseaudio",
        "--filesystem=home"
    ],
    "modules": [
        {
            "name": "python-deps",
            "buildsystem": "simple",
            "build-commands": [
                "pip3 install --prefix=/app --no-cache-dir PyQt5 requests"
            ],
            "sources": []
        },
        {
            "name": "smartrplay",
            "buildsystem": "simple",
            "build-commands": [
                "mkdir -p /app/bin",
                "mkdir -p /app/share/smartrplay",
                "cp src/*.py /app/share/smartrplay/",
                "cp smartrplay.desktop /app/share/applications/ || true",
                "printf '#!/bin/sh\nexec python3 /app/share/smartrplay/main.py "$@"\n' > /app/bin/smartrplay",
                "chmod +x /app/bin/smartrplay"
            ],
            "sources": [
                {
                    "type": "dir",
                    "path": ".."
                }
            ]
        }
    ]
}
MANIFEST_EOF

    ok "Manifest erstellt: $MANIFEST"
}

# ── .desktop File erstellen (falls nicht vorhanden) ────────────────────────────
generate_desktop_file() {
    local desktop_file="$PROJECT_DIR/smartrplay.desktop"

    if [[ ! -f "$desktop_file" ]]; then
        info "Erstelle .desktop File: $desktop_file"
        cat > "$desktop_file" << 'DESKTOP_EOF'
[Desktop Entry]
Name=SMarTrPlay
Comment=SMarTrPlay v4 — SMartrAgents Overlay Application
Exec=smartrplay
Icon=ai.smartragents.SMarTrPlay
Terminal=false
Type=Application
Categories=Utility;AudioVideo;
DESKTOP_EOF
        ok ".desktop File erstellt."
    fi
}

# ── Runtime + SDK installieren ────────────────────────────────────────────────
ensure_runtimes() {
    info "Stelle Runtime und SDK sicher..."

    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true

    flatpak install --assumeyes flathub "${RUNTIME}//${RUNTIME_VERSION}" 2>/dev/null || true
    flatpak install --assumeyes flathub "${SDK}//${SDK_VERSION}" 2>/dev/null || true

    ok "Runtime und SDK bereit."
}

# ── Build ──────────────────────────────────────────────────────────────────────
run_build() {
    info "Starte Flatpak-Build..."

    rm -rf "$BUILD_DIR" "$REPO_DIR"
    mkdir -p "$BUILD_DIR" "$REPO_DIR"

    # flatpak-builder ausführen
    flatpak-builder \
        --force-clean \
        --repo="$REPO_DIR" \
        "$BUILD_DIR" \
        "$MANIFEST"

    ok "Build abgeschlossen."
}

# ── Bundle erstellen ──────────────────────────────────────────────────────────
create_bundle() {
    local bundle="$SCRIPT_DIR/${APP_ID}.flatpak"

    info "Erstelle Flatpak-Bundle: $bundle"

    flatpak build-bundle "$REPO_DIR" "$bundle" "$APP_ID" "$BRANCH"

    ok "Bundle erstellt: $bundle"
    echo ""
    ls -lh "$bundle"
}

# ── Install (optional) ────────────────────────────────────────────────────────
install_flatpak() {
    info "Installiere Flatpak lokal..."

    flatpak remote-add --user --if-not-exists local "$REPO_DIR" 2>/dev/null || true
    flatpak install --user --assumeyes local "$APP_ID" "$BRANCH" || true

    ok "Installation abgeschlossen."
    echo "  Starten mit: flatpak run $APP_ID"
}

# ── Main ────────────────────────────────────────────────────────────────────────
main() {
    local do_install=false

    if [[ "${1:-}" == "--install" ]]; then
        do_install=true
    fi

    echo ""
    echo "========================================"
    echo "  SMarTrPlay v4 — Flatpak Packaging"
    echo "========================================"
    echo ""

    check_dependencies
    generate_manifest
    generate_desktop_file
    ensure_runtimes
    run_build
    create_bundle

    if [[ "$do_install" == true ]]; then
        install_flatpak
    fi

    echo ""
    ok "Flatpak-Paket erfolgreich erstellt!"
    echo "  Bundle: $SCRIPT_DIR/${APP_ID}.flatpak"
    echo "  Installieren: flatpak install --user $SCRIPT_DIR/${APP_ID}.flatpak"
    echo "  Ausführen: flatpak run $APP_ID"
    echo ""
}

main "$@"
