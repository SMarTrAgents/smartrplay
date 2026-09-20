#!/bin/bash
# SMarTrPlay AppImage Builder
# Creates a portable AppImage from the Python source files.
# The resulting AppImage runs on any Linux without installation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
SRC_DIR="$PROJECT_DIR/src"

VERSION="1.0.0"
APP_NAME="SMarTrPlay"
APP_LOWERCASE="smartrplay"
APP_DIR="$SCRIPT_DIR/AppDir"
BUILD_DIR="$SCRIPT_DIR/appimage_build"
APPIMAGETOOL="$SCRIPT_DIR/appimagetool"
OUTPUT_NAME="${APP_NAME}-${VERSION}-x86_64.AppImage"

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

if ! command -v python3 &> /dev/null; then
    err "python3 nicht gefunden"
    exit 1
fi

log "Baue $APP_NAME v$VERSION AppImage..."

# ─── Clean & Prepare ───
log "Saeubere vorherige Builds..."
rm -rf "$APP_DIR" "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
APP_DIR="$BUILD_DIR/AppDir"

# ─── Directory Structure ───
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/lib"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APP_DIR/usr/share/$APP_LOWERCASE"

# ─── Step 1: Copy Python Source Files ───
log "Kopiere Python-Quelldateien..."
cp "$SRC_DIR"/*.py "$APP_DIR/usr/share/$APP_LOWERCASE/"

# ─── Step 2: Create Wrapper Script ───
log "Erstelle Wrapper-Script..."
cat > "$APP_DIR/usr/bin/$APP_LOWERCASE" << 'WRAPPER'
#!/bin/bash
# SMarTrPlay AppImage Launcher
# SMarTrAgents IPTV Player

APPDIR="${APPDIR:-$(dirname "$(readlink -f "$0")")/..}"
APP_SHARE="$APPDIR/usr/share/smartrplay"

export PYTHONPATH="$APP_SHARE:$PYTHONPATH"

# Wayland support (fallback to xcb if Wayland not available)
if [ -n "$WAYLAND_DISPLAY" ]; then
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"
else
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
fi
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Check ffplay
if ! command -v ffplay &> /dev/null; then
    echo "WARNUNG: ffplay nicht gefunden. Video-Playback wird nicht funktionieren."
    echo "Installieren mit: sudo apt install ffmpeg"
fi

cd "$APP_SHARE"
exec python3 main.py "$@"
WRAPPER
chmod 755 "$APP_DIR/usr/bin/$APP_LOWERCASE"

# ─── Step 3: Create SVG Icon ───
log "Erstelle App-Icon (SVG)..."
cat > "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_LOWERCASE.svg" << 'SVG'
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

# Generate 256x256 PNG icon from SVG if rsvg-convert or Inkscape is available
if command -v rsvg-convert &> /dev/null; then
    log "Generiere 256x256 PNG-Icon..."
    rsvg-convert -w 256 -h 256 \
        "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_LOWERCASE.svg" \
        -o "$APP_DIR/usr/share/icons/hicolor/256x256/apps/$APP_LOWERCASE.png"
elif command -v inkscape &> /dev/null; then
    log "Generiere 256x256 PNG-Icon mit Inkscape..."
    inkscape -w 256 -h 256 \
        "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_LOWERCASE.svg" \
        -o "$APP_DIR/usr/share/icons/hicolor/256x256/apps/$APP_LOWERCASE.png" 2>/dev/null || true
else
    warn "Weder rsvg-convert noch Inkscape gefunden. Nur SVG-Icon wird verwendet."
    warn "Fuer PNG-Icons installieren: sudo apt install librsvg2-bin"
    rmdir "$APP_DIR/usr/share/icons/hicolor/256x256/apps" 2>/dev/null || true
    rmdir "$APP_DIR/usr/share/icons/hicolor/256x256" 2>/dev/null || true
fi

# ─── Step 4: Create .desktop File ───
log "Erstelle .desktop-Datei..."
cat > "$APP_DIR/usr/share/applications/$APP_LOWERCASE.desktop" << DESKTOP
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

# Copy .desktop file to AppDir root (required by appimagetool)
cp "$APP_DIR/usr/share/applications/$APP_LOWERCASE.desktop" "$APP_DIR/$APP_LOWERCASE.desktop"
chmod 644 "$APP_DIR/$APP_LOWERCASE.desktop"

# Copy icon to AppDir root (required by appimagetool — looks for $Icon.{png,svg,xpm})
cp "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_LOWERCASE.svg" "$APP_DIR/$APP_LOWERCASE.svg" 2>/dev/null || true
if [ -f "$APP_DIR/usr/share/icons/hicolor/256x256/apps/$APP_LOWERCASE.png" ]; then
    cp "$APP_DIR/usr/share/icons/hicolor/256x256/apps/$APP_LOWERCASE.png" "$APP_DIR/$APP_LOWERCASE.png"
fi

# ─── Step 5: Create AppRun ───
log "Erstelle AppRun..."
cat > "$APP_DIR/AppRun" << 'APPRUN'
#!/bin/bash
# AppImage Entry Point — SMarTrPlay
# This script is executed when the AppImage is double-clicked or run.

SELF="$(readlink -f "$0")"
export APPDIR="${APPDIR:-$(dirname "$SELF")}"

exec "$APPDIR/usr/bin/smartrplay" "$@"
APPRUN
chmod 755 "$APP_DIR/AppRun"

# ─── Step 6: Create .DirIcon (for file managers) ───
log "Erstelle .DirIcon..."
if [ -f "$APP_DIR/usr/share/icons/hicolor/256x256/apps/$APP_LOWERCASE.png" ]; then
    cp "$APP_DIR/usr/share/icons/hicolor/256x256/apps/$APP_LOWERCASE.png" "$APP_DIR/.DirIcon"
else
    cp "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_LOWERCASE.svg" "$APP_DIR/.DirIcon"
fi

# ─── Step 7: Set Permissions ───
log "Setze Dateiberechtigungen..."
find "$APP_DIR" -type d -exec chmod 755 {} \;
find "$APP_DIR/usr/share/$APP_LOWERCASE" -name '*.py' -exec chmod 644 {} \;
chmod 644 "$APP_DIR/usr/share/applications/$APP_LOWERCASE.desktop"
chmod 644 "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_LOWERCASE.svg"
find "$APP_DIR/usr/share/icons" -name '*.png' -exec chmod 644 {} \; 2>/dev/null || true

# ─── Step 8: Download appimagetool ───
if [ ! -f "$APPIMAGETOOL" ]; then
    log "Lade appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
        -O "$APPIMAGETOOL" || {
        warn "appimagetool konnte nicht heruntergeladen werden."
        warn "AppDir wurde erstellt unter: $APP_DIR"
        warn "Um AppImage manuell zu erstellen:"
        warn "  1. appimagetool von https://github.com/AppImage/AppImageKit/releases herunterladen"
        warn "  2. chmod +x appimagetool"
        warn "  3. ARCH=x86_64 appimagetool $APP_DIR $OUTPUT_NAME"
        info "AppDir ist verfuegbar unter: $APP_DIR"
        exit 0
    }
    chmod +x "$APPIMAGETOOL"
fi

# ─── Step 9: Create AppImage ───
log "Erstelle AppImage..."
ARCH="$(uname -m)"
export ARCH

if "$APPIMAGETOOL" "$APP_DIR" "$SCRIPT_DIR/$OUTPUT_NAME" 2>&1; then
    log "========================================="
    log "✅ AppImage erstellt:"
    log "   $SCRIPT_DIR/$OUTPUT_NAME"
    log ""
    log "   Ausfuehren mit:"
    log "   chmod +x $SCRIPT_DIR/$OUTPUT_NAME"
    log "   $SCRIPT_DIR/$OUTPUT_NAME"
    log ""
    log "   Installation (systemweit):"
    log "   sudo mv $SCRIPT_DIR/$OUTPUT_NAME /usr/local/bin/"
    log "========================================="
else
    warn "AppImage-Erstellung fehlgeschlagen."
    warn "AppDir ist verfuegbar unter: $APP_DIR"
    warn "Manueller Versuch:"
    warn "  ARCH=x86_64 $APPIMAGETOOL $APP_DIR $SCRIPT_DIR/$OUTPUT_NAME"
    exit 1
fi

# Show file info
if [ -f "$SCRIPT_DIR/$OUTPUT_NAME" ]; then
    info "AppImage Details:"
    ls -lh "$SCRIPT_DIR/$OUTPUT_NAME"
    file "$SCRIPT_DIR/$OUTPUT_NAME"
fi

log "Fertig!"
