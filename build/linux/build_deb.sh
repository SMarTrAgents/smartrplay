#!/bin/bash
# SMarTrPlay Debian Package Builder
# Creates a .deb file that installs SMarTrPlay with a clickable desktop icon
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
SRC_DIR="$PROJECT_DIR/src"

VERSION="1.0.0"
APP_NAME="smartrplay"
APP_DISPLAY="SMarTrPlay"
MAINTAINER="SMarTrAgents <akatongie@smartragents.ai>"
ARCH="all"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[BUILD]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Pre-flight checks
if [ ! -f "$SRC_DIR/main.py" ]; then
    err "main.py nicht gefunden in $SRC_DIR"
    exit 1
fi

if ! command -v dpkg-deb &> /dev/null; then
    err "dpkg-deb nicht gefunden. Installieren mit: sudo apt install dpkg-dev"
    exit 1
fi

# Paths
BUILD_DIR="$SCRIPT_DIR/deb_build"
PKG_DIR="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}"
DEBIAN_DIR="$PKG_DIR/DEBIAN"

# Clean previous build
log "Saeubere vorherige Builds..."
rm -rf "$BUILD_DIR"
mkdir -p "$DEBIAN_DIR"

# ─── Directory Structure ───
mkdir -p "$PKG_DIR/usr/share/smartrplay"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/48x48/apps"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"

# ─── Step 1: Copy Python Source Files ───
log "Kopiere Python-Quelldateien..."
cp "$SRC_DIR"/*.py "$PKG_DIR/usr/share/smartrplay/"

# ─── Step 2: Create Wrapper Script ───
log "Erstelle Wrapper-Script..."
cat > "$PKG_DIR/usr/bin/smartrplay" << 'WRAPPER'
#!/bin/bash
# SMarTrPlay - Launcher
# SMarTrAgents IPTV Player

export PYTHONPATH="/usr/share/smartrplay:$PYTHONPATH"

# Wayland support
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland;xcb}"
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Check ffplay
if ! command -v ffplay &> /dev/null; then
    echo "WARNUNG: ffplay nicht gefunden. Video-Playback wird nicht funktionieren."
    echo "Installieren mit: sudo apt install ffmpeg"
fi

cd /usr/share/smartrplay
exec python3 main.py "$@"
WRAPPER
chmod 755 "$PKG_DIR/usr/bin/smartrplay"

# ─── Step 3: Create SVG Icon ───
log "Erstelle App-Icon (SVG)..."
cat > "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/smartrplay.svg" << 'SVG'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" style="stop-color:#0A0F1E"/>
      <stop offset="1" style="stop-color:#121A2E"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" style="stop-color:#1bf1fb"/>
      <stop offset="1" style="stop-color:#8D7CF6"/>
    </linearGradient>
  </defs>
  <rect width="256" height="256" rx="48" fill="url(#bg)"/>
  <rect x="56" y="72" width="144" height="112" rx="12" fill="none" stroke="url(#accent)" stroke-width="4"/>
  <polygon points="108,104 108,152 148,128" fill="url(#accent)"/>
  <text x="128" y="210" font-family="Inter,sans-serif" font-size="20" font-weight="bold"
        fill="#1bf1fb" text-anchor="middle">SMarTrPlay</text>
</svg>
SVG

# Generate PNG icons from SVG if rsvg-convert or Inkscape is available
if command -v rsvg-convert &> /dev/null; then
    log "Generiere PNG-Icons mit rsvg-convert..."
    rsvg-convert -w 48 -h 48 "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/smartrplay.svg" \
        -o "$PKG_DIR/usr/share/icons/hicolor/48x48/apps/smartrplay.png"
    rsvg-convert -w 256 -h 256 "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/smartrplay.svg" \
        -o "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/smartrplay.png"
elif command -v inkscape &> /dev/null; then
    log "Generiere PNG-Icons mit Inkscape..."
    inkscape -w 48 -h 48 "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/smartrplay.svg" \
        -o "$PKG_DIR/usr/share/icons/hicolor/48x48/apps/smartrplay.png" 2>/dev/null || true
    inkscape -w 256 -h 256 "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/smartrplay.svg" \
        -o "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/smartrplay.png" 2>/dev/null || true
else
    warn "Weder rsvg-convert noch Inkscape gefunden. Nur SVG-Icon wird installiert."
    warn "Fuer PNG-Icons installieren: sudo apt install librsvg2-bin"
    # Remove empty PNG dirs
    rmdir "$PKG_DIR/usr/share/icons/hicolor/48x48/apps" 2>/dev/null || true
    rmdir "$PKG_DIR/usr/share/icons/hicolor/256x256/apps" 2>/dev/null || true
    rmdir "$PKG_DIR/usr/share/icons/hicolor/48x48" 2>/dev/null || true
    rmdir "$PKG_DIR/usr/share/icons/hicolor/256x256" 2>/dev/null || true
fi

# ─── Step 4: Create .desktop File ───
log "Erstelle .desktop-Datei..."
cat > "$PKG_DIR/usr/share/applications/smartrplay.desktop" << DESKTOP
[Desktop Entry]
Name=SMarTrPlay
Comment=SMarTrAgents IPTV Player — M3U, M3U+, Xtream Codes
Comment[de]=SMarTrAgents IPTV Player — M3U, M3U+, Xtream Codes
Exec=smartrplay %U
Icon=smartrplay
Terminal=false
Type=Application
Categories=AudioVideo;Video;Player;TV;
Keywords=IPTV;Player;TV;Streaming;M3U;Xtream;
StartupNotify=true
MimeType=application/x-mpegurl;audio/x-mpegurl;
DESKTOP

# ─── Step 5: Create DEBIAN/control ───
log "Erstelle DEBIAN/control..."
cat > "$DEBIAN_DIR/control" << CONTROL
Package: ${APP_NAME}
Version: ${VERSION}
Section: video
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-pyqt5, ffmpeg
Recommends: python3-requests, python3-urllib3
Suggests: vlc
Maintainer: ${MAINTAINER}
Description: SMarTrPlay — SMarTrAgents IPTV Player
 IPTV Player for M3U, M3U+ and Xtream Codes API playlists.
 Features:
  * M3U/M3U+ playlist support
  * Xtream Codes API integration
  * Chromecast/DLNA casting
  * EPG (Electronic Program Guide)
  * Video on Demand (VoD) browser
  * Series browser with artwork
  * Mini player and Picture-in-Picture
  * Multi-profile support
  * Remote control support
  * Subtitle recording
  * Catchup TV support
  * Custom SMarTr dark theme
 .
 Built by SMartrAgents.
CONTROL

# ─── Step 6: Create postinst ───
log "Erstelle DEBIAN/postinst..."
cat > "$DEBIAN_DIR/postinst" << 'POSTINST'
#!/bin/bash
set -e

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi

# Create user config directory hint
echo "SMarTrPlay installiert. Starte mit 'smartrplay' oder ueber das Anwendungsmenue."
POSTINST
chmod 755 "$DEBIAN_DIR/postinst"

# ─── Step 7: Create prerm ───
log "Erstelle DEBIAN/prerm..."
cat > "$DEBIAN_DIR/prerm" << 'PRERM'
#!/bin/bash
set -e

# Kill any running instances
pkill -f "python3.*main.py.*smartrplay" 2>/dev/null || true
PRERM
chmod 755 "$DEBIAN_DIR/prerm"

# ─── Step 8: Create postrm ───
log "Erstelle DEBIAN/postrm..."
cat > "$DEBIAN_DIR/postrm" << 'POSTRM'
#!/bin/bash
set -e

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi

# Note: user config at ~/SMarTrPlay/ is NOT removed automatically
POSTRM
chmod 755 "$DEBIAN_DIR/postrm"

# ─── Step 9: Set Permissions ───
log "Setze Dateiberechtigungen..."
find "$PKG_DIR" -type d -exec chmod 755 {} \;
find "$PKG_DIR/usr/share/smartrplay" -name '*.py' -exec chmod 644 {} \;
chmod 644 "$PKG_DIR/usr/share/applications/smartrplay.desktop"
chmod 644 "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/smartrplay.svg" 2>/dev/null || true
find "$PKG_DIR/usr/share/icons" -name '*.png' -exec chmod 644 {} \; 2>/dev/null || true

# ─── Step 10: Build .deb ───
log "Baue .deb-Paket..."
DEB_FILE="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG_DIR" "$DEB_FILE"

if [ -f "$DEB_FILE" ]; then
    log "========================================="
    log "✅ .deb-Paket erstellt:"
    log "   $DEB_FILE"
    log ""
    log "   Installieren mit:"
    log "   sudo dpkg -i $DEB_FILE"
    log ""
    log "   Bei Abhaengigkeitsfehlern:"
    log "   sudo apt --fix-broken install"
    log ""
    log "   Deinstallieren mit:"
    log "   sudo dpkg -r $APP_NAME"
    log "========================================="
else
    err ".deb-Paket konnte nicht erstellt werden!"
    exit 1
fi

# Show package info
info "Paket-Inhalt:"
dpkg-deb --info "$DEB_FILE" 2>/dev/null | head -20
log "Fertig!"
