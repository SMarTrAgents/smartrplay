[app]
title = SMarTrPlay
package.name = smartrplay
package.domain = ai.smartragents
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0

requirements = hostpython3==3.11.9,python3==3.11.9,openssl,kivy==2.3.0,pyjnius

orientation = landscape

# Android TV specific
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b
android.arch = arm64-v8a,armeabi-v7a

# Android TV Leanback support
android.meta_data = android.intent.category.LEANBACK_LAUNCHER
android.apptheme = @android:style/Theme.NoTitleBar.Fullscreen

# Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

# Build settings
fullscreen = True
android.entrypoint = main.py
android.debuggable = False
android.accept_sdk_license = True
android.allow_backup = True

# presplash
presplash.filename = assets/splash.png

# icon
icon.filename = assets/icon.png

[buildozer]
log_level = 2
warn_on_root = 1

[app-specific]
# Android TV: D-Pad navigation required
android.tv_feature = true
android.leanback = true
