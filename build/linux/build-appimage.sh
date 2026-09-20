#!/usr/bin/env bash
# Baut SMarTrPlay als AppImage: eine Datei, laeuft ohne Installation und ohne Root.
# SMarTrAgents.ai by AKATONGIE with Fable 5 (Anthropic). MIT license.
#
# Aufruf aus dem Projektwurzelverzeichnis:  bash build/linux/build-appimage.sh [Version]
#
# Der Weg: PyInstaller buendelt Python, PyQt5 und die Quellen zu einem Ordner,
# daraus wird ein AppDir gebaut und mit appimagetool zu einer Datei gepackt.
# libVLC wird NICHT mitgeliefert: die Wiedergabe nutzt das systemeigene VLC.
set -euo pipefail

VERSION="${1:-5.0.0}"
WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARBEIT="$WURZEL/build/linux/arbeit"
APPDIR="$ARBEIT/SMarTrPlay.AppDir"
ZIEL="$WURZEL/dist"

echo "==> Aufraeumen"
rm -rf "$ARBEIT"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$ZIEL"

echo "==> PyInstaller-Buendel"
python3 -m PyInstaller \
  --noconfirm --clean --name SMarTrPlay --windowed \
  --distpath "$ARBEIT/dist" --workpath "$ARBEIT/work" --specpath "$ARBEIT" \
  --paths "$WURZEL/src" \
  --hidden-import vlc --hidden-import requests \
  --hidden-import PyQt5.QtNetwork \
  --exclude-module tkinter --exclude-module matplotlib \
  "$WURZEL/src/main.py"

cp -a "$ARBEIT/dist/SMarTrPlay/." "$APPDIR/usr/bin/"

echo "==> X11-Bibliotheken der Qt-Plattformschicht nachlegen"
# Die Plattformschicht xcb wird von Qt erst zur Laufzeit nachgeladen. PyInstaller
# sieht diese Abhaengigkeit deshalb nicht, und auf einem schlanken System bricht
# die Anwendung mit "Could not load the Qt platform plugin xcb" ab. Genau das ist
# im GitHub-Bauplan passiert. Nachgelegt werden bewusst nur die xcb- und
# Tastaturbibliotheken; Kernbibliotheken wie libc oder libstdc++ bleiben drausen,
# weil sie aus dem Zielsystem kommen muessen.
PLATTFORM="$(find "$APPDIR/usr/bin" -name 'libqxcb.so' | head -1)"
if [ -n "$PLATTFORM" ]; then
  ZIELORDNER="$(dirname "$PLATTFORM")/../.."
  ldd "$PLATTFORM" 2>/dev/null | awk '/=> \//{print $3}' | while read -r LIB; do
    BASIS="$(basename "$LIB")"
    case "$BASIS" in
      libxcb*|libxkbcommon*|libXau*|libXdmcp*|libbsd*)
        ZIEL="$APPDIR/usr/bin/$BASIS"
        [ -e "$ZIEL" ] || cp -L "$LIB" "$ZIEL"
        ;;
    esac
  done
  echo "    $(ls "$APPDIR/usr/bin" | grep -cE '^libxcb|^libxkbcommon') Bibliotheken liegen bereit"
else
  echo "    libqxcb.so nicht gefunden, uebersprungen"
fi

echo "==> Symbol und Eintrag im Startmenue"
SYMBOL="$WURZEL/android_tv/assets/icon.png"
if [ -f "$SYMBOL" ]; then
  cp "$SYMBOL" "$APPDIR/usr/share/icons/hicolor/256x256/apps/smartrplay.png"
  cp "$SYMBOL" "$APPDIR/smartrplay.png"
else
  # Ohne Symbol verweigert appimagetool den Dienst, deshalb ein schlichtes Ersatzbild.
  python3 - "$APPDIR" <<'PY'
import sys, struct, zlib
pfad = sys.argv[1]
breite = hoehe = 256
zeilen = b''.join(b'\x00' + bytes([11, 15, 22, 255]) * breite for _ in range(hoehe))
def stueck(art, inhalt):
    roh = art + inhalt
    return struct.pack('>I', len(inhalt)) + roh + struct.pack('>I', zlib.crc32(roh))
png = (b'\x89PNG\r\n\x1a\n'
       + stueck(b'IHDR', struct.pack('>IIBBBBB', breite, hoehe, 8, 6, 0, 0, 0))
       + stueck(b'IDAT', zlib.compress(zeilen))
       + stueck(b'IEND', b''))
for ziel in (pfad + '/smartrplay.png',
             pfad + '/usr/share/icons/hicolor/256x256/apps/smartrplay.png'):
    open(ziel, 'wb').write(png)
PY
fi

cat > "$APPDIR/smartrplay.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=SMarTrPlay
GenericName=IPTV Player
Comment=Modern IPTV player with Xtream Codes support, EPG, VOD and series
Comment[de]=Moderner IPTV-Player mit Xtream-Codes, Programmzeitschrift, Filmen und Serien
Exec=SMarTrPlay
Icon=smartrplay
Categories=AudioVideo;Video;Player;TV;
Keywords=IPTV;TV;Stream;Xtream;M3U;EPG;VOD;
Terminal=false
DESKTOP
cp "$APPDIR/smartrplay.desktop" "$APPDIR/usr/share/applications/"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
# Startet SMarTrPlay aus dem AppImage heraus.
HIER="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$HIER/usr/bin:${LD_LIBRARY_PATH:-}"
exec "$HIER/usr/bin/SMarTrPlay" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "==> appimagetool besorgen"
WERKZEUG="$ARBEIT/appimagetool"
if ! command -v appimagetool >/dev/null 2>&1; then
  wget -q -O "$WERKZEUG" \
    https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$WERKZEUG"
else
  WERKZEUG="$(command -v appimagetool)"
fi

echo "==> AppImage packen"
AUSGABE="$ZIEL/SMarTrPlay-${VERSION}-x86_64.AppImage"
# In Bauumgebungen ohne FUSE muss appimagetool sich selbst entpacken.
if ! ARCH=x86_64 "$WERKZEUG" "$APPDIR" "$AUSGABE" 2>/dev/null; then
  ENTPACKT="$ARBEIT/tool"
  mkdir -p "$ENTPACKT"
  (cd "$ENTPACKT" && "$WERKZEUG" --appimage-extract >/dev/null)
  ARCH=x86_64 "$ENTPACKT/squashfs-root/AppRun" "$APPDIR" "$AUSGABE"
fi

chmod +x "$AUSGABE"
echo "==> Fertig: $AUSGABE"
ls -lh "$AUSGABE"
