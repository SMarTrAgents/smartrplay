#!/bin/bash
# SMarTrPlay IPTV Player - Launch Script
# SMarTrAgents

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/src"

# Use system Python (PyQt5 is installed for system Python)
PYTHON=/usr/bin/python3

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

exec $PYTHON main.py "$@"
