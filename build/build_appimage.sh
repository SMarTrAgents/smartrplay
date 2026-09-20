#!/bin/bash
set -euo pipefail

# SMarTrPlay - AppImage Build Script
# Erstellt ein AppImage aus den Python-Quellcodedateien.

VERSION="3.0.0"
APP_NAME="SMarTrPlay"
APP_DIR="AppDir"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/../src"
BUILD_DIR="$SCRIPT_DIR"
ICON="video-x-generic"

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[BUILD]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }

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

# Clean
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin" "$APP_DIR/usr/lib" "$APP_DIR/usr/share/applications" "$APP_DIR/usr/share/smartrplay"

# Step 1: Copy source files
log "Kopiere Quelldateien..."
cp "$SRC_DIR"/*.py "$APP_DIR/usr/share/smartrplay/"

# Step 2: Create wrapper script
cat > "$APP_DIR/usr/bin/smartrplay" << 'WRAPPER'
#!/bin/bash
export PYTHONPATH="$APPDIR/usr/share/smartrplay:$PYTHONPATH"
exec python3 "$APPDIR/usr/share/smartrplay/main.py" "$@"
WRAPPER
chmod +x "$APP_DIR/usr/bin/smartrplay"

# Step 3: Create .desktop file
cat > "$APP_DIR/usr/share/applications/smartrplay.desktop" << DESKTOP
[Desktop Entry]
Name=SMarTrPlay
Comment=SMarTrAgents IPTV Player
Exec=smartrplay
Icon=video-x-generic
Terminal=false
Type=Application
Categories=AudioVideo;Video;Player;TV;
DESKTOP

# Step 4: Create AppRun
cat > "$APP_DIR/AppRun" << 'APPRUN'
#!/bin/bash
exec "$APPDIR/usr/bin/smartrplay" "$@"
APPRUN
chmod +x "$APP_DIR/AppRun"

# Step 5: Download appimagetool if not present
if [ ! -f "$BUILD_DIR/appimagetool" ]; then
    log "Lade appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "$BUILD_DIR/appimagetool" || {
        warn "appimagetool konnte nicht heruntergeladen werden."
        warn "AppDir wurde erstellt unter: $BUILD_DIR/$APP_DIR"
        warn "Um AppImage zu erstellen: appimagetool $BUILD_DIR/$APP_DIR"
        exit 0
    }
    chmod +x "$BUILD_DIR/appimagetool"
fi

# Step 6: Create AppImage
log "Erstelle AppImage..."
if command -v $BUILD_DIR/appimagetool &> /dev/null; then
    $BUILD_DIR/appimagetool "$APP_DIR" "${APP_NAME}-${VERSION}-x86_64.AppImage" || {
        warn "AppImage-Erstellung fehlgeschlagen. AppDir ist verfuegbar unter: $BUILD_DIR/$APP_DIR"
    }
    if [ -f "${APP_NAME}-${VERSION}-x86_64.AppImage" ]; then
        log "AppImage erstellt: ${APP_NAME}-${VERSION}-x86_64.AppImage"
    fi
else
    warn "appimagetool nicht ausfuehrbar. AppDir erstellt unter: $BUILD_DIR/$APP_DIR"
fi

log "Fertig!"
