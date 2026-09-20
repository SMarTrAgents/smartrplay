#!/bin/bash
# SMarTrPlay — APK Build + Sign Script
# Requires: Android SDK, Gradle 8.x, Java 11+

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APK_NAME="smartrplay"
KEYSTORE="${SCRIPT_DIR}/smartrplay.keystore"
KEYSTORE_PASS="smartrplay2026"
KEY_ALIAS="smartrplay"
KEY_PASS="smartrplay2026"

echo "========================================="
echo "  SMarTrPlay APK Build Script"
echo "========================================="
echo ""

# Check for ANDROID_HOME or ANDROID_SDK_ROOT
if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
    echo "⚠ ANDROID_HOME or ANDROID_SDK_ROOT not set!"
    echo "  Set it with: export ANDROID_HOME=/path/to/android-sdk"
    echo ""
    # Try common locations
    for p in "$HOME/Android/Sdk" "$HOME/android-sdk" "/opt/android-sdk" "/usr/local/android-sdk"; do
        if [ -d "$p" ]; then
            export ANDROID_HOME="$p"
            export ANDROID_SDK_ROOT="$p"
            echo "  Found SDK at: $p"
            break
        fi
    done
fi

if [ -z "$ANDROID_HOME" ]; then
    echo "❌ No Android SDK found. Please install Android SDK first."
    exit 1
fi

echo "Android SDK: $ANDROID_HOME"
echo ""

# Step 1: Check Java
if ! command -v java &>/dev/null; then
    echo "❌ Java not found. Install JDK 11+."
    exit 1
fi
JAVA_VER=$(java -version 2>&1 | head -1)
echo "Java: $JAVA_VER"
echo ""

# Step 2: Make gradlew if not present
if [ ! -f "${SCRIPT_DIR}/gradlew" ]; then
    echo "📦 Generating Gradle wrapper..."
    cd "$SCRIPT_DIR"
    if command -v gradle &>/dev/null; then
        gradle wrapper --gradle-version 8.2
    else
        echo "⚠ Gradle not found. Creating wrapper manually..."
        # Download gradle wrapper jar
        mkdir -p "$SCRIPT_DIR/gradle/wrapper"
        curl -sL "https://raw.githubusercontent.com/gradle/gradle/v8.2.0/gradle/wrapper/gradle-wrapper.jar" \
            -o "$SCRIPT_DIR/gradle/wrapper/gradle-wrapper.jar"
        cat > "$SCRIPT_DIR/gradlew" << 'GRADLEW_EOF'
#!/bin/sh
exec java -classpath "$APP_HOME/gradle/wrapper/gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain "$@"
GRADLEW_EOF
        chmod +x "$SCRIPT_DIR/gradlew"
    fi
fi

# Step 3: Build APK
echo "🔨 Building debug APK..."
cd "$SCRIPT_DIR"
./gradlew assembleDebug --no-daemon --stacktrace 2>&1 | tail -20

APK_DEBUG="${SCRIPT_DIR}/app/build/outputs/apk/debug/app-debug.apk"

if [ ! -f "$APK_DEBUG" ]; then
    echo "❌ Build failed! APK not found at: $APK_DEBUG"
    exit 1
fi

echo ""
echo "✅ Debug APK built successfully!"
ls -lh "$APK_DEBUG"
echo ""

# Step 4: Generate keystore for signing (if not exists)
if [ ! -f "$KEYSTORE" ]; then
    echo "🔐 Generating signing keystore..."
    keytool -genkeypair \
        -keystore "$KEYSTORE" \
        -storepass "$KEYSTORE_PASS" \
        -alias "$KEY_ALIAS" \
        -keypass "$KEY_PASS" \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -dname "CN=SMarTrAgents, OU=Development, O=SMarTrAgents.ai, L=Berlin, ST=Berlin, C=DE" 2>/dev/null
    echo "✅ Keystore generated: $KEYSTORE"
    echo ""
fi

# Step 5: Sign APK
echo "✍ Signing APK..."
APK_SIGNED="${SCRIPT_DIR}/${APK_NAME}-signed.apk"

# Use apksigner if available, otherwise jarsigner
if [ -f "$ANDROID_HOME/build-tools/latest/apksigner" ]; then
    APKSIGNER="$ANDROID_HOME/build-tools/latest/apksigner"
elif command -v apksigner &>/dev/null; then
    APKSIGNER="apksigner"
else
    APKSIGNER=""
fi

if [ -n "$APKSIGNER" ]; then
    "$APKSIGNER" sign \
        --ks "$KEYSTORE" \
        --ks-pass "pass:$KEYSTORE_PASS" \
        --ks-key-alias "$KEY_ALIAS" \
        --key-pass "pass:$KEY_PASS" \
        --out "$APK_SIGNED" \
        "$APK_DEBUG"
else
    # Fallback to jarsigner
    jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
        -keystore "$KEYSTORE" \
        -storepass "$KEYSTORE_PASS" \
        -keypass "$KEY_PASS" \
        "$APK_DEBUG" "$KEY_ALIAS"
    cp "$APK_DEBUG" "$APK_SIGNED"
fi

echo ""
echo "✅ APK signed successfully!"
echo "📦 Signed APK: $APK_SIGNED"
ls -lh "$APK_SIGNED"
echo ""
echo "========================================="
echo "  Build complete!"
echo "  Install: adb install $APK_SIGNED"
echo "========================================="
