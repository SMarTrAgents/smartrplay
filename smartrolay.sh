#!/bin/bash
# SMarTrPlay IPTV Player - Launch Script
# SMarTrAgents

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/src"

# Use system Python (PyQt5 is installed for system Python)
PYTHON=/usr/bin/python3

# Set environment for better video playback
export LIBGL_ALWAYS_SOFTWARE=0
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Check ffplay
if ! command -v ffplay &> /dev/null; then
    echo "WARNUNG: ffplay nicht gefunden. Video-Playback wird nicht funktionieren."
    echo "Installieren mit: sudo apt install ffmpeg"
fi

# Check yt-dlp (for YouTube)
if ! command -v yt-dlp &> /dev/null; then
    echo "HINWEIS: yt-dlp nicht gefunden. YouTube-Playback eingeschraenkt."
fi

exec $PYTHON main.py "$@"
