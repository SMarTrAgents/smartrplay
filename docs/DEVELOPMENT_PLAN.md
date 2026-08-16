# SMarTrPlay IPTV Player - Entwicklungsplan

## Vision

SMarTrPlay ist der eigene IPTV-Player von SMarTrAgents. Er löst die Stabilitätsprobleme von IPTV Smarters Expert und bietet zusätzliche Features wie YouTube- und Netflix-Integration.

## Tech-Stack

| Komponente | Technologie | Begründung |
|---|---|---|
| UI Framework | Python + PyQt6 | Cross-Platform, stabil, gut in SMarTrAgents integrierbar |
| Video Backend | libmpv (python-mpv) | Gleicher Player wie IPTV Smarters, aber nativ ohne Flutter |
| Datenbank | SQLite | Stabiler als Isar, Standard, Backup-freundlich |
| M3U Parser | Eigene Implementierung | Voll kontrolle über Parsing und Caching |
| Xtream API | Eigene Implementierung | REST Client für Xtream Codes API |
| Brand Design | SMarTr Brand Standard | Dark Mode, Inter Font, Cyan/Violet Gradient |

## Features (MVP v1.0)

### Core Features
1. **M3U/M3U+ Playlist Import**
   - URL-basiert (HTTP/HTTPS)
   - Lokale Datei
   - Auto-Refresh ( konfigurierbar)

2. **Xtream Codes API Login**
   - Server URL + Username + Password
   - Live Categories
   - VOD (Movies) Categories
   - Series Categories
   - EPG (Electronic Program Guide)

3. **Video Playback**
   - mpv Backend (Hardware Decoding)
   - Live TV + VOD + Series
   - Catch-up / Replay Support

4. **YouTube Integration**
   - YouTube Link/URL abspielbar
   - YouTube Live Streams
   - Search (optional in v2)

5. **Netflix Integration**
   - Netflix Deep Links (öffnet Netflix App/Browser)
   - Netflix Suche via Browser

6. **SMarTr Brand Design**
   - Dark Mode (#0A0F1E Hintergrund)
   - Inter Font
   - Cyan/Violet Gradient Akzente
   - SMarTr Logo im Header

### Features v2.0 (geplant)
- Multi-Profile (mehrere IPTV Provider)
- Favorites / Watchlist
- Recording (PVR)
 - Chromecast / DLNA Support
- Subtitle Support
- Picture-in-Picture
- Mini Player

## Architektur

```
SMarTrPlay/
├── src/
│   ├── main/
│   │   ├── main.py          # Entry Point
│   │   ├── window.py         # Main Window (QMainWindow)
│   │   └── config.py         # App Configuration
│   ├── parser/
│   │   ├── m3u_parser.py     # M3U/M3U+ Parser
│   │   └── xtream_api.py     # Xtream Codes API Client
│   ├── player/
│   │   ├── player.py         # mpv Player Wrapper
│   │   └── playlist.py       # Playlist Manager
│   ├── ui/
│   │   ├── sidebar.py        # Category Sidebar
│   │   ├── channel_grid.py   # Channel/Grid View
│   │   ├── player_view.py    # Video Player View
│   │   ├── search_bar.py     # Search Widget
│   │   └── theme.py          # SMarTr Brand Theme
│   └── renderer/
│       └── resources.py     # Icons, Logos, Assets
├── assets/
│   └── logo.png              # SMarTr Logo
├── docs/
│   └── DEVELOPMENT_PLAN.md  # This file
└── build/
    └── (build artifacts)
```

## Entwicklungsphasen

### Phase 1: Core (Woche 1)
- [x] Projektstruktur erstellen
- [ ] M3U Parser implementieren
- [ ] Xtream API Client implementieren
- [ ] SQLite Datenbank-Schema
- [ ] Config/Settings System

### Phase 2: Player (Woche 1-2)
- [ ] mpv Player Integration (python-mpv)
- [ ] Video Playback (Live + VOD)
- [ ] Playlist Manager
- [ ] Channel List View

### Phase 3: UI (Woche 2)
- [ ] Main Window Layout
- [ ] SMarTr Brand Theme
- [ ] Sidebar (Kategorien)
- [ ] Channel Grid
- [ ] Search Bar
- [ ] Player View mit Controls

### Phase 4: Integration (Woche 3)
- [ ] YouTube Link Playback
- [ ] Netflix Deep Link Support
- [ ] EPG Display
- [ ] Settings Dialog

### Phase 5: Polish (Woche 3-4)
- [ ] Error Handling
- [ ] Auto-Refresh Playlists
- [ ] Performance Optimierung
- [ ] Packaging (Flatpak/AppImage)

## Vorteile gegenüber IPTV Smarters Expert

1. **Stabilität**: Kein Flutter, kein Snap, keine AppArmor-Probleme
2. **Performance**: Direkter mpv, kein Flutter-Engine-Overhead (90 Threads -> ~10)
3. **RAM**: Ziel <200MB statt 602MB
4. **Brand**: SMarTr Design, eigene Identität
5. **Features**: YouTube + Netflix Integration
6. **Wartbarkeit**: Python-Code, offen erweiterbar
