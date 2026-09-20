#!/bin/bash
# SMarTrPlay IPTV Player - Launch Script
# SMarTrAgents

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJEKT="$SCRIPT_DIR"
cd "$PROJEKT/src"

# Use system Python (PyQt5 is installed for system Python)
PYTHON="$PROJEKT/.venv/bin/python"
# Die Projektumgebung traegt python-vlc. Ohne sie faellt der Player auf ffplay zurueck.
if [ ! -x "$PYTHON" ]; then
    echo "WARNUNG: .venv fehlt, nutze System-Python ohne VLC-Anbindung"
    PYTHON=/usr/bin/python3
fi

# Wayland support (spacemen runs Wayland)
export QT_QPA_PLATFORM=xcb
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}

# Set environment for better video playback
export LIBGL_ALWAYS_SOFTWARE=0
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Check ffplay
if ! command -v ffplay &> /dev/null; then
    echo "WARNUNG: ffplay nicht gefunden. Video-Playback wird nicht funktionieren."
    echo "Installieren mit: sudo apt install ffmpeg"
fi

# Start as systemd user service (survives terminal disconnects)
systemctl --user stop smartrplay 2>/dev/null
systemctl --user reset-failed smartrplay 2>/dev/null
systemd-run --user --unit=smartrplay \
  -p LimitNOFILE=65536 \
  --working-directory="$PROJEKT/src" \
  --setenv=QT_QPA_PLATFORM=xcb \
  --setenv=DISPLAY=${DISPLAY:-:0} \
  $PYTHON main.py "$@"
echo "SMarTrPlay als systemd-Service gestartet."
echo "Status: systemctl --user status smartrplay"
echo "Stop:   systemctl --user stop smartrplay"
