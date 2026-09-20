# Changelog

All notable changes to **SMarTrPlay** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v5.0.0] — VLC, Fullscreen & Master Search — 2026-09-20

### Changed
- 🎬 **Playback now runs on libVLC** instead of ffplay. ffplay reads keys only from its own
  SDL window, so pause, seek, mute and volume did nothing and there was no position
  feedback. All of that works now, including hardware acceleration, subtitles and
  multiple audio tracks.

### Added
- 🖥️ **Fullscreen with a real control bar** — double-click the picture to enter and leave.
  The embedded video window stays in place, so the stream never restarts. Buttons are
  64 px and the font is 20 px, built for low vision.
- 📡 **Zapping without leaving fullscreen** — arrow keys switch channel, `L` opens a
  searchable channel list on top of the running picture.
- 📺 **Episode zapping** — series episodes now play in the application's video area instead
  of a separate VLC window, and arrow keys move through the season.
- 🔍 **Master search across all categories** in movies and series, not just the loaded one.
- 📦 **Windows installer** (Inno Setup, per-user, no admin rights) and **Linux AppImage**
  (one file, no installation), both built and start-tested by GitHub Actions.
- 🧪 **tests/** — four acceptance runs with 70 checks that measure the running window.

### Fixed
- 💥 **Crash on close** — `QThread: Destroyed while thread is still running`. Threads are
  now detached and parked instead of being torn down mid-run.
- 📜 **Series would not load at all.** The API timeout was too short: the provider needs
  12 to 17 seconds for series, the limit was 8. Separate timeouts now: 8 s for lists,
  45 s for content.
- 🗂️ **22 037 series were unreachable.** The provider's category list named 49 ids while
  the catalogue used 207. Entries without a known category now get a collection by
  language, 88 categories instead of 49.
- 🔒 **Diagnostics server was bound to 0.0.0.0** and served the subscription credentials in
  clear text without any authentication. It is bound to localhost with a token now.
- 🪟 **Windows startup** — `import resource` does not exist there.
- 📁 **Read-only install locations** — the log folder was created next to the executable,
  which fails inside an AppImage and in Program Files. Logs go to the user folder now.
- 🖱️ **Visible scrollbars, larger fonts, keyboard operation** throughout.
- ⚡ **Loading is much faster** — the full catalogue is fetched in one request where the
  provider supports it: live 1.1 s instead of 26 s.

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
