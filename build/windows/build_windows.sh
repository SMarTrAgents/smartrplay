#!/bin/bash
# SMarTrPlay Windows EXE Build Script
# Requires: pip install pyinstaller PyQt5
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$PROJECT_DIR/src"
BUILD_DIR="$SCRIPT_DIR"

# Check PyInstaller
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Check PyQt5
if ! pip show PyQt5 > /dev/null 2>&1; then
    echo "Installing PyQt5..."
    pip install PyQt5
fi

# Build
pyinstaller "$BUILD_DIR/smartrplay.spec" --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/build" --clean

echo "Build complete!"
echo "EXE: $BUILD_DIR/dist/SMarTrPlay/SMarTrPlay.exe"
echo ""
echo "For a single-file EXE:"
echo "pyinstaller --onefile --windowed --name SMarTrPlay --add-data ... main.py"
