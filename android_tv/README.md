# SMarTrPlay — Android TV Build & Install Anleitung

> **SMarTrPlay** ist die Android TV App für SMartrAgents — optimiert für Leanback/D-Pad Steuerung.

---

## 📋 Voraussetzungen

### Build-Umgebung
| Komponente | Mindestversion | Hinweis |
|---|---|---|
| **OS** | Ubuntu 20.04+ / macOS 12+ | Linux empfohlen |
| **Java JDK** | 11 (OpenJDK 11) | `sudo apt install openjdk-11-jdk` |
| **Python** | 3.9+ | Buildozer benötigt Python |
| **buildozer** | 1.5.1+ | `pip install buildozer` |
| **Android SDK** | API 31+ | Wird von buildozer automatisch heruntergeladen |
| **Android NDK** | r25b+ | Wird von buildozer automatisch heruntergeladen |
| **Cython** | 0.29.x+ | `pip install Cython` |
| **Git** | 2.x+ | Für Dependencies |

### Optional (Docker-Build)
- **Docker** 20.10+ — für reproduzierbare Builds ohne lokale Abhängigkeiten

### Installation auf Android TV
- **ADB** (Android Debug Bridge) — `sudo apt install adb`
- **Android TV Gerät** mit aktiviertem USB-Debugging oder Netzwerk-ADB

---

## 🔧 Build Anleitung

### Option A: Lokaler Build mit buildozer

```bash
# 1. Voraussetzungen installieren
sudo apt update
sudo apt install -y openjdk-11-jdk python3-pip git zip unzip
pip3 install buildozer Cython

# 2. In das SMarTrPlay Verzeichnis wechseln
cd /home/tongie/$SMartrAgent/SMarTrOlay/android_tv/

# 3. Assets generieren (optional, falls noch nicht vorhanden)
python3 generate_assets.py

# 4. buildozer initialisieren (falls buildozer.spec noch nicht vorhanden)
#    buildozer spec  # Erstellt buildozer.spec, dann anpassen!

# 5. APK bauen
buildozer -v android debug

# APK liegt nach erfolgreichem Build unter:
# bin/SMarTrPlay-1.0.0-debug.apk
```

### Option B: Docker-Build (empfohlen für CI/CD)

```bash
# 1. Docker Image von Kivy verwenden
docker run --rm \
    -v $(pwd):/home/user/hostcwd \
    -v ~/.buildozer:/home/user/.buildozer \
    -e USER_ID=$(id -u) \
    -e GROUP_ID=$(id -g) \
    kivy/buildozer:latest android debug

# 2. APK liegt unter:
# bin/SMarTrPlay-1.0.0-debug.apk
```

### Option C: Build-Script (build_apk.sh)

```bash
#!/bin/bash
# build_apk.sh — SMarTrPlay APK Build Script
set -e

echo "[1/4] Assets generieren..."
python3 generate_assets.py

echo "[2/4] buildozer clean..."
buildozer android clean || true

echo "[3/4] APK bauen..."
buildozer -v android debug

echo "[4/4] APK verifizieren..."
ls -lh bin/*.apk

echo "✅ Build erfolgreich! APK: bin/SMarTrPlay-1.0.0-debug.apk"
```

---

## 📱 Installation auf Android TV

### Methode 1: ADB über USB

```bash
# 1. ADB installieren
sudo apt install adb

# 2. Android TV per USB verbinden (oder über Netzwerk)
#    Auf dem TV: Einstellungen > Entwickleroptionen > USB-Debugging aktivieren

# 3. Gerät verbinden
adb devices

# 4. APK installieren
adb install bin/SMarTrPlay-1.0.0-debug.apk

# 5. App starten
adb shell am start -n ai.smartragents.smartrplay/org.kivy.android.PythonActivity
```

### Methode 2: ADB über Netzwerk (WLAN)

```bash
# 1. ADB über Netzwerk verbinden (IP des Android TV herausfinden)
adb connect <ANDROID_TV_IP>:5555

# 2. Gerät verifizieren
adb devices

# 3. APK installieren
adb install bin/SMarTrPlay-1.0.0-debug.apk
```

### Methode 3: Sideload Launcher

1. **Sideload Launcher** aus Google Play Store auf Android TV installieren
2. APK auf USB-Stick kopieren
3. Mit Dateimanager-App auf dem TV die APK installieren
4. App über Sideload Launcher starten

---

## 🎮 D-Pad Steuerung

SMarTrPlay ist für Android TV Leanback optimiert. Die Steuerung erfolgt über den D-Pad der Fernbedienung:

| Taste | Aktion |
|---|---|
| **↑ / ↓** | Navigation durch Listen und Menüs |
| **← / →** | Zwischen Kategorien / Tabs wechseln |
| **OK / Enter** | Element auswählen / bestätigen |
| **Back** | Zurück / Menü schließen |
| **Home** | Home-Screen / App beenden |
| **Play/Pause** | Medienwiedergabe steuern |

### Steuerungs-Prinzipien
- **Fokus-basiert**: Eines Element ist immer fokussiert (Highlight-Ring in Cyan `#1bf1fb`)
- **D-Pad-Navigation**: Alle Aktionen mit Fernbedienung erreichbar — keine Touch-Bedienung nötig
- **Landscape-Modus**: App läuft fix im Querformat (`screenOrientation: landscape`)
- **Fullscreen**: Keine Status-Bar — voller Bildschirm für Inhalte

---

## 🎨 Branding & Assets

### Asset-Generierung

```bash
python3 generate_assets.py
```

Generiert folgende Assets im Verzeichnis `assets/`:

| Datei | Größe | Verwendung |
|---|---|---|
| `icon.png` | 512×512 px | App Icon (Launcher) |
| `splash.png` | 1920×1080 px | Splash Screen / Loading |
| `banner.png` | 320×180 px | Android TV Home-Screen Banner |

### Brand Colors

Siehe `assets/brand_colors.json` für die komplette Farbdefinition.

| Farbe | Hex | Verwendung |
|---|---|---|
| **BG Deep** | `#0A0F1E` | Hintergrund |
| **Accent Cyan** | `#1bf1fb` | Primärer Akzent / Fokus-Ring |
| **Accent Purple** | `#8D7CF6` | Sekundärer Akzent |
| **Text Primary** | `#F5F7FA` | Haupttext |
| **Text Secondary** | `#9BA5B7` | Sekundärer Text |

---

## ⚠️ Bekannte Issues

| Issue | Status | Workaround |
|---|---|---|
| **buildozer erste Build-Dauer** | ℹ️ Normal | Erster Build dauert 20-40 Min (SDK/NDK Download) |
| **Pillow nicht installiert** | ✅ Gelöst | `generate_assets.py` nutzt Fallback mit `struct`+`zlib` |
| **ADB verbindet nicht** | ⚠️ Häufig | TV neu starten, USB-Debugging erneut aktivieren |
| **Leanback Launcher nicht sichtbar** | ⚠️ Bekannt | Sideload Launcher verwenden oder `adb shell am start` |
| **Touchscreen-Feature Warning** | ✅ Behoben | `android.hardware.touchscreen` auf `required=false` gesetzt |
| **Splash Screen flackert** | ℹ️ Bekannt | Kivy splash - kann in `buildozer.spec` deaktiviert werden |
| **Große APK-Größe** | ℹ️ Normal | Python Runtime + Kivy ≈ 20-30 MB overhead |
| **ARM/x86 Kompatibilität** | ⚠️ Prüfen | `buildozer.spec`: `android.archs = arm64-v8a, armeabi-v7a` |

---

## 📁 Verzeichnisstruktur

```
android_tv/
├── generate_assets.py          # Asset-Generator (icon, splash, banner)
├── AndroidManifest.xml.tmpl    # Android TV Manifest Template
├── README.md                   # Diese Datei
├── assets/
│   ├── icon.png                # 512×512 App Icon
│   ├── splash.png              # 1920×1080 Splash Screen
│   ├── banner.png              # 320×180 TV Banner
│   └── brand_colors.json       # Brand Farbdefinitionen
├── buildozer.spec              # (Zu erstellen) buildozer Konfiguration
├── build_apk.sh               # (Optional) Build-Script
└── bin/                        # Build-Output (APKs)
    └── SMarTrPlay-1.0.0-debug.apk
```

---

## 🔗 Nützliche Links

- [buildozer Dokumentation](https://buildozer.readthedocs.io/)
- [Kivy Android Guide](https://kivy.org/doc/stable/guide/packaging-android.html)
- [Android TV Leanback Guide](https://developer.android.com/training/tv)
- [ADB Quick Reference](https://developer.android.com/studio/command-line/adb)

---

## 📝 Build & Version History

| Version | Datum | Änderungen |
|---|---|---|
| 1.0.0 | 2026-08-13 | Initiale Android TV Assets, Manifest & Branding |

---

*SMarTrPlay — SMartrAgents auf deinem Fernseher.* 📺
