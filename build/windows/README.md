# SMarTrPlay — Windows EXE Build Instructions

## Übersicht

Dieses Verzeichnis enthält alle Dateien, um SMarTrPlay als Windows `.exe` zu bauen.

## Dateien

| Datei | Beschreibung |
|---|---|
| `smartrplay.spec` | PyInstaller Spec-File (PyQt5, windowed, no console) |
| `build_windows.sh` | Lokales Build-Script (Linux/macOS/WSL) |
| `smartrplay.ico` | (Optional) Icon-Datei — im selben Ordner ablegen |

## Voraussetzungen

```bash
pip install pyinstaller PyQt5
```

## Lokaler Build

```bash
# Im build/windows/ Verzeichnis
cd build/windows
chmod +x build_windows.sh
./build_windows.sh
```

**Ergebnis:** `dist/SMarTrPlay/SMarTrPlay.exe`

## Single-File EXE (alternativ)

```bash
pyinstaller --onefile --windowed --name SMarTrPlay \
    --add-data "src/config:config" \
    src/main.py
```

## GitHub Actions CI/CD

Die Workflow-Datei `.github/workflows/build-windows.yml` baut automatisch bei:

- **Tag Push** (`v*`) → Build + GitHub Release mit EXE
- **Manueller Trigger** (`workflow_dispatch`) → Build + Artifact Download

### Release erstellen

```bash
git tag v1.0.0
git push origin v1.0.0
```

Die EXE wird automatisch als Release-Asset hochgeladen.

## PyInstaller Spec Details

| Option | Wert | Bedeutung |
|---|---|---|
| `console` | `False` | Kein Konsolenfenster (GUI-only) |
| `upx` | `True` | EXE-Kompression mit UPX |
| `hiddenimports` | PyQt5 Module | Stellt alle Qt-Module bereit |
| `icon` | `smartrplay.ico` | Optional, falls Datei existiert |

## Troubleshooting

### Fehlendes PyQt5
```bash
pip install PyQt5 PyQt5-sip
```

### Icon nicht gefunden
Die Spec-Datei prüft mit `os.path.exists('smartrplay.ico')` — falls keine ICO vorhanden, wird ohne Icon gebaut.

### Build schlägt fehl
```bash
# Clean rebuild
rm -rf build/ dist/
pyinstaller smartrplay.spec --clean
```

### Windows Defender / AV Fehlalarm
PyInstaller-EXEs werden oft fälschlich als Malware erkannt. Lösungen:
- Code Signing Zertifikat verwenden (`codesign_identity` in Spec)
- Whitelist beim Anwender
- Single-File EXE stattdessen verwenden

## Output-Struktur

```
build/windows/
├── smartrplay.spec
├── build_windows.sh
├── README.md
├── smartrplay.ico (optional)
├── build/          # PyInstaller Temp-Files
└── dist/
    └── SMarTrPlay/
        ├── SMarTrPlay.exe
        └── _internal/
            └── ...  # Qt5 DLLs, Python runtime, etc.
```
