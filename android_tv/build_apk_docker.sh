#!/bin/bash
# SMarTrPlay Android TV APK Build via Docker
# Uses kivy/buildozer Docker image
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building SMarTrPlay APK via Docker..."
docker run --rm \
    -v "$(pwd)":/home/user/hostcwd \
    -v "$(pwd)/.buildozer":/home/user/.buildozer \
    -e USER_ID=$(id -u) \
    -e GROUP_ID=$(id -g) \
    kivy/buildozer android debug

APK_FILE="$(find bin/ -name '*.apk' -print -quit)"
if [ -n "$APK_FILE" ]; then
    echo "APK: $APK_FILE"
    echo "Size: $(du -h "$APK_FILE" | cut -f1)"
else
    echo "BUILD FAILED"
    exit 1
fi
