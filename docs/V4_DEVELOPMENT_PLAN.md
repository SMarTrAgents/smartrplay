# SMarTrPlay v4.0 - Entwicklungsplan

## Vision

v4 macht SMarTrPlay zum vollwertigen Media-Center: Casting, Multi-Profile, Mini Player, EPG Timeline, Catch-up, Remote Control und Cross-Platform Packaging.

## Module (8 neue Dateien)

### 1. chromecast_dlna.py - Chromecast & DLNA Support
- DLNA/UPnP Device Discovery (via SSDP/UDP)
- Stream an DLNA-Renderer senden (SOAP/GENA)
- Chromecast Support (Google Cast Protocol via HTTP)
- Device-Liste Widget mit SMarTr Design
- Play/Pause/Stop/Seek auf Remote Device
- Cast-Button in Player-Controls

### 2. multi_profile.py - Multi-Profile Manager
- Mehrere Provider-Profile verwalten
- Schnellwechsel zwischen Profilen (Dropdown oder Tabs)
- Pro-Profile: Einstellungen, Favoriten, zuletzt gesehen
- Profil-Import/Export (JSON)
- SMarTr Brand Design Profile-Selector Widget

### 3. mini_player.py - Mini Player Mode
- Kompaktes 480x270px immer-im-Vordergrund Fenster
- Video + Controls in einem Frame
- Drag-to-Move, Snap-to-Edge
- Quick-Channel-Switch Dropdown
- Volume + Play/Pause + Channel-Info
- SMarTr Brand Design

### 4. epg_timeline.py - EPG Timeline View
- Horizontale Timeline (Stunden-Raster)
- Programme als Blocks mit Farbe nach Kategorie
- Jetzt-Linie (rot/cyan)
- Klick auf Programm zeigt Details
- Scroll horizontal (Zeit) und vertikal (Kanaele)
- SMarTr Brand Design

### 5. catchup.py - Catch-up / Replay Support
- Xtream API get_live_stream_epg mit catchup
- Catch-up URL generieren: {server}/live/{user}/{pass}/{stream_id}?start={unix}&duration={secs}
- Programme aus EPG fuer Catch-up auswaehlen
- ffplay mit catch-up URL starten
- Replay-Dialog mit Programm-Auswahl

### 6. remote_control.py - Web Remote Control
- Embedded HTTP-Server (Python http.server)
- Mobile-friendly Web-UI (HTML/CSS/JS)
- Endpoints: /play, /pause, /stop, /volume, /channel, /search
- QR-Code fuer schnellen Zugriff
- WebSocket fuer Live-Updates
- SMarTr Brand Design Web-UI

### 7. flatpak_build.sh - Flatpak Packaging
- flatpak-builder manifest (JSON)
- Python-Dependencies als pip-modules
- PyQt5 Runtime-Dependencies
- SMarTrPlay.desktop Integration
- Build + Install Script

### 8. snap_build.sh - Snap Packaging
- snapcraft.yaml mit loosened confinement
- Python + PyQt5 stage-packages
- Desktop + GPU interfaces
- Build + Pack Script

## Multi-Agent Orchestrierung

### Agent 1 (Networking): chromecast_dlna.py + catchup.py
### Agent 2 (UI): multi_profile.py + mini_player.py
### Agent 3 (Feature): epg_timeline.py + remote_control.py
### Agent 4 (Packaging): flatpak_build.sh + snap_build.sh

## Integration

- main_window.py: v4 Imports, Menu-Einträge, Methoden
- Menu: Geraete (Cast), Profile, Mini Player, EPG Timeline, Catch-up, Remote Control
- closeEvent: v4 cleanup (HTTP-Server stoppen, Cast disconnect)

## Test & Start

1. Syntax-Check aller v4 Dateien
2. Import-Test
3. App-Launch-Test
4. Start auf spacemen (DISPLAY=:0)
