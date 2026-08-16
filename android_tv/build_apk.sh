#!/bin/bash
# SMarTrPlay Android TV APK Build Script
# Requires: buildozer, Java 11+, Android SDK/NDK (auto-downloaded by buildozer)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check buildozer
if ! command -v buildozer &> /dev/null; then
    echo "Installing buildozer..."
    pip3 install buildozer
fi

# Check Java
if ! java -version &> /dev/null 2>&1; then
    echo "ERROR: Java not found. Install with: sudo apt install openjdk-11-jdk"
    exit 1
fi

# Clean previous builds
rm -rf .buildozer/ bin/ build/ dist/

# Build APK
echo "Building SMarTrPlay Android TV APK..."
echo "This will take 15-30 minutes on first run (downloading SDK/NDK)..."
buildozer -v android debug

# Check result
APK_FILE="$(find bin/ -name '*.apk' -print -quit)"
if [ -n "$APK_FILE" ]; then
    echo ""
    echo "=== BUILD SUCCESSFUL ==="
    echo "APK: $APK_FILE"
    echo "Size: $(du -h "$APK_FILE" | cut -f1)"
    echo ""
    echo "Install on Android TV:"
    echo "  adb install $APK_FILE"
    echo "  or transfer via USB"
else
    echo "BUILD FAILED - check output above"
    exit 1
fi
