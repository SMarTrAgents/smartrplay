# Changelog

All notable changes to **SMarTrPlay** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v4.0.0] — Advanced & Cast

### Added
- 📡 **DLNA / Cast** — Cast streams to DLNA-compatible devices (TVs, speakers, smart home)
- 👤 **Multi-Profile** — Manage multiple IPTV providers with seamless switching
- 🖥️ **Mini Player** — Compact floating player widget for multitasking
- 📊 **EPG Timeline** — Visual timeline view of upcoming programs across all channels
- ⏯️ **Catch-up** — Watch previously aired content with catch-up support
- 🌐 **Web Remote** — Control SMarTrPlay from any browser on phone or tablet
- 📦 **Flatpak** — Flatpak package support for Linux distributions
- 📦 **Snap** — Snap package support for Linux distributions
- 🎬 **VOD Browser** — Browse video-on-demand content with metadata, posters, and categories
- 📖 **Series Browser Enhancement** — Improved series browsing with season/episode navigation and metadata
- 🔍 **Global Search** — Search across live channels, VOD, and series simultaneously
- 🖱️ **Double-Click Seek** — Double-click on the player to seek forward/backward

### Changed
- Refactored provider management for multi-profile support
- Improved EPG data parsing and caching performance
- Enhanced UI responsiveness on high-DPI displays

### Fixed
- Fixed EPG not updating when switching providers
- Fixed recording path not persisting across restarts
- Fixed series episode order for certain providers

---

## [v3.0.0] — Power User Features

### Added
- 🪟 **Picture-in-Picture (PiP)** — Watch in a floating mini window while browsing
- 💬 **Subtitles** — Load and display subtitle tracks (SRT, SSA, embedded)
- ⏺️ **Recording** — Record live streams to local storage
- 🔄 **Auto-Refresh** — Automatically refresh playlists and EPG data at configurable intervals
- 📦 **AppImage** — Portable Linux AppImage builds for distribution

### Changed
- Updated ffplay integration for better stream compatibility
- Improved settings persistence with SQLite backend
- Optimized playlist loading for large M3U files

### Fixed
- Fixed PiP window not staying on top on certain Linux window managers
- Fixed subtitle encoding issues with non-UTF-8 files
- Fixed auto-refresh timer drift on long-running sessions

---

## [v2.0.0] — Enhanced Experience

### Added
- 📅 **EPG (Electronic Program Guide)** — View program schedules for channels
- ⚙️ **Settings Panel** — Configure player, streams, and UI preferences
- 📚 **Series Browser** — Browse and watch series from your provider
- ⭐ **Favorites** — Mark channels, VOD, and series as favorites for quick access

### Changed
- Redesigned main UI layout with tabbed navigation
- Improved channel list rendering performance
- Enhanced error handling for invalid stream URLs

### Fixed
- Fixed favorites not loading on application startup
- Fixed EPG timezone offset issues
- Fixed settings not saving on certain Linux distributions

---

## [v1.0.0] — Initial Release

### Added
- 📺 **Live TV** — Stream live IPTV channels with ffplay backend
- 📋 **M3U Playlist Support** — Import and parse M3U/M3U8 playlists from URL or local file
- 🔗 **Xtream Codes API** — Full Xtream Codes panel integration (live, VOD, series endpoints)
- 🎨 **SMarTr Brand Design** — Custom dark blue (#0A1A2F) & cyan (#00D9FF) themed UI
- 🖥️ **Cross-Platform** — Runs on Linux and Windows
- ⚙️ **Configurable Player** — ffplay backend with volume, fullscreen, and playback controls

---

## Version History Summary

| Version | Release Date | Key Features |
|---|---|---|
| v1.0.0 | 2026-Q1 | M3U, Xtream, Live TV, ffplay, SMarTr Brand |
| v2.0.0 | 2026-Q2 | EPG, Settings, Series Browser, Favorites |
| v3.0.0 | 2026-Q3 | PiP, Subtitles, Recording, Auto-Refresh, AppImage |
| v4.0.0 | 2026-Q4 | DLNA/Cast, Multi-Profile, Mini Player, EPG Timeline, Catch-up, Web Remote, Flatpak, Snap, VOD Browser, Series Enhancement, Global Search, Double-Click Seek |

---

<div align="center">

© 2026 SMartrAgents / Karl Heinz Marko  
[smartragents.ai](https://smartragents.ai)

</div>
