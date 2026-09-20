#!/usr/bin/env python3
"""SMarTrPlay - Main Window (PyQt5 + SMarTr Brand Design)

Redesigned v6: Tab-based navigation, no blocking dialogs.
All browsers and settings are inline widgets in tabs.
Only AddProviderDialog remains modal.
"""

import os
import sys
import logging
import time
import traceback
import subprocess
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QLineEdit, QPushButton,
    QToolBar, QAction, QStatusBar, QMenu, QTabWidget, QDialog,
    QFormLayout, QComboBox, QMessageBox, QProgressBar, QFrame,
    QScrollArea, QGridLayout, QSizePolicy, QApplication, QShortcut
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QPixmap, QIcon, QFont, QCursor, QKeySequence

from vollbild import VollbildLeiste, ZappListe

from config import Config
from debug_server import DebugServer
from m3u_parser import M3UParser
from xtream_api import XtreamAPI
from player import PlayerBackend

# VLC-Backend bevorzugt: Es steuert libvlc direkt, deshalb wirken Pause,
# Spulen, Stummschalten und die Lautstärke sofort, und Position und Dauer
# sind abfragbar. Scheitert der Import (zum Beispiel fehlt das Paket
# python-vlc), greift der Rückfall auf den alten ffplay-Backend; dann
# bleiben Pause, Spulen, Stummschaltung und Positionsanzeige wirkungslos.
try:
    from player_vlc import VlcPlayerBackend
    VLC_BACKEND_AVAILABLE = True
except Exception as vlc_import_fehler:
    VlcPlayerBackend = None
    VLC_BACKEND_AVAILABLE = False
    logging.warning(
        "Achtung: Das VLC-Backend (player_vlc) konnte nicht geladen werden: %s — "
        "die Oberfläche fällt auf den alten ffplay-Backend zurück. Pause, Spulen, "
        "Stummschaltung und die Positionsanzeige arbeiten dort nicht.",
        vlc_import_fehler,
    )
from theme import apply_theme, BG_DEEP, BG_CARD, BG_CARD_HOVER, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT_CYAN, ACCENT_PURPLE, ACCENT_VIOLET
import theme  # Modul als Ganzes, damit theme.setze_schriftgroesse zur Laufzeit aufrufbar ist
import fadenpark

# v2 imports
try:
    from settings_dialog import SettingsDialog
    from series_browser import SeriesBrowser
    from epg import EpgWidget, EpgService
    V2_AVAILABLE = True
except Exception as e:
    V2_AVAILABLE = False
    print(f"v2 modules warning: {e}")

# v3 imports
try:
    from pip import PIPWindow
    from subtitle_recording import SubtitleManager, RecordingManager
    from auto_refresh import AutoRefreshManager
    V3_AVAILABLE = True
except Exception as e:
    V3_AVAILABLE = False
    print(f"v3 modules warning: {e}")

# v4 imports
try:
    from chromecast_dlna import CastWidget, DLNADiscovery, DLNARenderer
    from catchup import CatchupManager, CatchupDialog
    from remote_control import RemoteControlServer, RemoteControlWidget, RemoteControlController
    from multi_profile import ProfileSelector
    from mini_player import MiniPlayer
    from epg_timeline import EpgTimelineWidget
    from vod_browser import VodBrowser
    from search_browser import SearchBrowser
    V4_AVAILABLE = True
except Exception as e:
    V4_AVAILABLE = False
    print(f"v4 modules warning: {e}")

# v5 imports - Video Controls & Audio/Subtitle Options
try:
    from video_controls import VideoControlsBar
    from audio_subtitle_options import AudioSubtitleBar
    V5_AVAILABLE = True
except Exception as e:
    V5_AVAILABLE = False
    print(f"v5 modules warning: {e}")


# === Debug Logger ===
logger = logging.getLogger('SMarTrPlay.MainWindow')


class AddProviderDialog(QDialog):
    """Dialog zum Hinzufuegen eines IPTV Providers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Provider hinzufuegen")
        self.setMinimumWidth(420)
        self.config = Config()

        layout = QVBoxLayout(self)

        # Provider Type Tabs
        self.type_tabs = QTabWidget()

        # M3U Tab
        m3u_widget = QWidget()
        m3u_layout = QFormLayout(m3u_widget)
        self.m3u_name = QLineEdit(placeholderText="z.B. Mein IPTV Provider")
        self.m3u_url = QLineEdit(placeholderText="http://example.com/playlist.m3u")
        m3u_layout.addRow("Name:", self.m3u_name)
        m3u_layout.addRow("M3U URL:", self.m3u_url)
        self.type_tabs.addTab(m3u_widget, "M3U Playlist")

        # Xtream Tab
        xtream_widget = QWidget()
        xtream_layout = QFormLayout(xtream_widget)
        self.xt_name = QLineEdit(placeholderText="z.B. Xtream Provider")
        self.xt_server = QLineEdit(placeholderText="http://server.com:8080")
        self.xt_user = QLineEdit(placeholderText="Username")
        self.xt_pass = QLineEdit(placeholderText="Password", echoMode=QLineEdit.Password)
        xtream_layout.addRow("Name:", self.xt_name)
        xtream_layout.addRow("Server URL:", self.xt_server)
        xtream_layout.addRow("Username:", self.xt_user)
        xtream_layout.addRow("Password:", self.xt_pass)
        self.type_tabs.addTab(xtream_widget, "Xtream Codes")

        layout.addWidget(self.type_tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_add = QPushButton("Hinzufuegen")
        self.btn_add.setObjectName("primaryBtn")
        self.btn_add.clicked.connect(self.accept_provider)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)

    def accept_provider(self):
        """Provider speichern."""
        idx = self.type_tabs.currentIndex()

        if idx == 0:  # M3U
            name = self.m3u_name.text().strip()
            url = self.m3u_url.text().strip()
            if not name or not url:
                QMessageBox.warning(self, "Fehler", "Name und URL sind erforderlich.")
                return
            self.provider_type = "m3u"
            self.provider_name = name
            self.provider_url = url
            self.provider_user = None
            self.provider_pass = None
        else:  # Xtream
            name = self.xt_name.text().strip()
            server = self.xt_server.text().strip()
            user = self.xt_user.text().strip()
            pwd = self.xt_pass.text().strip()
            if not name or not server or not user or not pwd:
                QMessageBox.warning(self, "Fehler", "Alle Felder sind erforderlich.")
                return
            self.provider_type = "xtream"
            self.provider_name = name
            self.provider_url = server
            self.provider_user = user
            self.provider_pass = pwd

        self.accept()


class LoadPlaylistThread(QThread):
    """Thread fuer das Laden von Playlists im Hintergrund (Optimized v2).

    Features:
    - Progress-Signal fuer UI-Feedback (Status-Text, Current, Total)
    - SQLite Cache: Bei erneutem Laden innerhalb 1h wird Cache verwendet
    - Lazy Loading: Nur Live TV beim ersten Laden, VOD/Series bei Auswahl
    - 15s Timeout pro API-Call (ueber XtreamAPI)
    """
    progress = pyqtSignal(str, int, int)  # status_text, current, total
    finished = pyqtSignal(list, str)  # channels, content_type
    error = pyqtSignal(str)

    CACHE_MAX_AGE = 3600  # 1 Stunde in Sekunden

    def __init__(self, provider_type, url, username=None, password=None,
                 provider_id=None, load_type='live', config=None):
        super().__init__()
        self.provider_type = provider_type
        self.url = url
        self.username = username
        self.password = password
        self.provider_id = provider_id
        self.load_type = load_type
        self.config = config
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _check_cache(self, content_type):
        """Prueft ob gueltiger Cache existiert und gibt Channels aus DB zurueck."""
        if not self.config or not self.provider_id:
            return None
        if self.config.is_cache_valid(self.provider_id, content_type, self.CACHE_MAX_AGE):
            channels = []
            db_channels = self.config.get_channels(provider_id=self.provider_id, type=content_type)
            for ch in db_channels:
                channels.append({
                    "name": ch[2],
                    "url": ch[3],
                    "logo": ch[4] or "",
                    "category": ch[5] or "",
                    "tvg_id": ch[6] or "",
                    "tvg_name": ch[7] or "",
                    "type": ch[8] or content_type,
                })
            return channels
        return None

    def run(self):
        _log = logging.getLogger('SMarTrPlay.LoadPlaylistThread')
        import time as _time
        t0 = _time.time()
        _log.info(f"=== LoadPlaylistThread START === type={self.provider_type} load_type={self.load_type} url={self.url} user={self.username}")
        try:
            if self.provider_type == "m3u":
                _log.info(f"[{_time.time()-t0:.2f}s] M3U: parse_url started")
                self.progress.emit("Lade M3U Playlist...", 0, 1)
                parser = M3UParser()
                channels = parser.parse_url(self.url)
                _log.info(f"[{_time.time()-t0:.2f}s] M3U: parse_url done, {len(channels)} channels")
                if not channels:
                    _log.warning(f"[{_time.time()-t0:.2f}s] WARNING: M3U returned 0 channels")
                self.finished.emit(channels, 'm3u')

            elif self.provider_type == "xtream":
                api = XtreamAPI(self.url, self.username, self.password)
                # Abbruchflag durchreichen, damit ein Providerwechsel den
                # laufenden Abruf wirklich beendet und nicht nur die Anzeige.
                try:
                    if hasattr(api, 'setze_abbruchpruefung'):
                        api.setze_abbruchpruefung(lambda: self._cancelled)
                except Exception as e:
                    _log.warning(f"Abbruchpruefung nicht gesetzt: {e}")

                # 1. Authentifizierung
                _log.info(f"[{_time.time()-t0:.2f}s] Xtream: authenticating...")
                self.progress.emit("Authentifiziere...", 0, 3)
                auth = api.authenticate()
                if not auth:
                    _log.error(f"[{_time.time()-t0:.2f}s] Xtream: auth FAILED")
                    self.error.emit("Authentifizierung fehlgeschlagen. Server: " + self.url + " User: " + str(self.username))
                    return
                ui = auth.get("user_info", {})
                _log.info(f"[{_time.time()-t0:.2f}s] Xtream: auth OK — status={ui.get('status','unknown')} exp={ui.get('exp_date','unknown')}")

                if self._cancelled:
                    _log.info(f"[{_time.time()-t0:.2f}s] LoadPlaylistThread cancelled after auth")
                    return

                # 2. Cache pruefen (nur fuer Live TV Erstladung)
                if self.load_type == 'live':
                    cached = self._check_cache('live')
                    if cached is not None and len(cached) > 0:
                        _log.info(f"[{_time.time()-t0:.2f}s] Cache aktiv: {len(cached)} Live-TV Kanaele aus Cache")
                        self.progress.emit(f"Cache aktiv: {len(cached)} Kanaele", 1, 1)
                        self.finished.emit(cached, 'live_cached')
                        return
                    _log.info(f"[{_time.time()-t0:.2f}s] No cache hit for live, loading from API...")

                # 3. Load basierend auf load_type
                if self.load_type == 'live':
                    _log.info(f"[{_time.time()-t0:.2f}s] Xtream: loading Live TV channels...")
                    channels = api.get_live_channels_lazy(
                        progress_callback=lambda msg, cur, tot: self.progress.emit(msg, cur, tot)
                    )
                    _log.info(f"[{_time.time()-t0:.2f}s] Live TV: {len(channels)} Kanaele geladen")
                    if not channels:
                        _log.warning(f"[{_time.time()-t0:.2f}s] WARNING: Keine Live TV Kanaele gefunden!")
                    self.finished.emit(channels, 'live')

                elif self.load_type == 'vod':
                    cached = self._check_cache('vod')
                    if cached is not None and len(cached) > 0:
                        _log.info(f"[{_time.time()-t0:.2f}s] VOD Cache: {len(cached)} Filme")
                        self.progress.emit(f"VOD Cache: {len(cached)} Filme", 1, 1)
                        self.finished.emit(cached, 'vod_cached')
                        return
                    _log.info(f"[{_time.time()-t0:.2f}s] Xtream: loading VOD channels...")
                    channels = api.get_vod_channels_lazy(
                        progress_callback=lambda msg, cur, tot: self.progress.emit(msg, cur, tot)
                    )
                    _log.info(f"[{_time.time()-t0:.2f}s] VOD: {len(channels)} Filme geladen")
                    if not channels:
                        _log.warning(f"[{_time.time()-t0:.2f}s] WARNING: Keine VOD Kanaele gefunden!")
                    self.finished.emit(channels, 'vod')

                elif self.load_type == 'series':
                    cached = self._check_cache('series')
                    if cached is not None and len(cached) > 0:
                        _log.info(f"[{_time.time()-t0:.2f}s] Series Cache: {len(cached)} Serien")
                        self.progress.emit(f"Serien Cache: {len(cached)} Serien", 1, 1)
                        self.finished.emit(cached, 'series_cached')
                        return
                    _log.info(f"[{_time.time()-t0:.2f}s] Xtream: loading Series channels...")
                    channels = api.get_series_channels_lazy(
                        progress_callback=lambda msg, cur, tot: self.progress.emit(msg, cur, tot)
                    )
                    _log.info(f"[{_time.time()-t0:.2f}s] Serien: {len(channels)} geladen")
                    if not channels:
                        _log.warning(f"[{_time.time()-t0:.2f}s] WARNING: Keine Serien gefunden!")
                    self.finished.emit(channels, 'series')

                elif self.load_type == 'all':
                    _log.info(f"[{_time.time()-t0:.2f}s] Xtream: loading ALL channels (live+vod+series)...")
                    channels = api.get_all_channels(
                        progress_callback=lambda msg, cur, tot: self.progress.emit(msg, cur, tot)
                    )
                    _log.info(f"[{_time.time()-t0:.2f}s] Alle: {len(channels)} Kanaele geladen")
                    if not channels:
                        _log.warning(f"[{_time.time()-t0:.2f}s] WARNING: Keine Kanaele gefunden!")
                    self.finished.emit(channels, 'all')

            else:
                _log.warning(f"[{_time.time()-t0:.2f}s] Unknown provider type: {self.provider_type}")
                self.finished.emit([], 'unknown')

            _log.info(f"=== LoadPlaylistThread DONE === in {_time.time()-t0:.2f}s")

        except Exception as e:
            import traceback as _tb
            tb_str = _tb.format_exc()
            _log.error(f"=== LoadPlaylistThread ERROR === {e}\n{tb_str}")
            self.error.emit(f"{e}\n\nTraceback:\n{tb_str}")


class LazyLoadThread(QThread):
    """Thread fuer Hintergrund-Laden von VOD/Series nach initialer Live-TV Ladung."""
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(self, api, content_type, provider_id=None, config=None):
        super().__init__()
        self.api = api
        self.content_type = content_type
        self.provider_id = provider_id
        self.config = config
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        # Das Abbruchflag an die Xtream-Schnittstelle durchreichen. Ohne das
        # laeuft ein abgebrochener Ladevorgang in den Netzabrufen weiter und
        # haengt als abgenabelter Faden im Hintergrund. Gemessen am 19.09.2026:
        # nach vier Bedienrunden liefen vier alte Ladevorgaenge weiter.
        try:
            if hasattr(self.api, 'setze_abbruchpruefung'):
                self.api.setze_abbruchpruefung(lambda: self._cancelled)
        except Exception as e:
            logging.getLogger('SMarTrPlay').warning(
                f"Abbruchpruefung nicht gesetzt: {e}"
            )
        _log = logging.getLogger('SMarTrPlay.LazyLoadThread')
        import time as _time
        t0 = _time.time()
        _log.info(f"=== LazyLoadThread START === content_type={self.content_type} provider_id={self.provider_id}")
        try:
            if self.content_type == 'vod':
                _log.info(f"[{_time.time()-t0:.2f}s] Loading VOD channels...")
                self.progress.emit("Lade VOD (Filme) im Hintergrund...", 0, 1)
                channels = self.api.get_vod_channels_lazy(
                    progress_callback=lambda msg, cur, tot: self.progress.emit(msg, cur, tot)
                )
                _log.info(f"[{_time.time()-t0:.2f}s] VOD: {len(channels)} geladen")
                if not channels:
                    _log.warning(f"[{_time.time()-t0:.2f}s] WARNING: Keine VOD Kanaele gefunden!")
            elif self.content_type == 'series':
                _log.info(f"[{_time.time()-t0:.2f}s] Loading Series channels...")
                self.progress.emit("Lade Serien im Hintergrund...", 0, 1)
                channels = self.api.get_series_channels_lazy(
                    progress_callback=lambda msg, cur, tot: self.progress.emit(msg, cur, tot)
                )
                _log.info(f"[{_time.time()-t0:.2f}s] Series: {len(channels)} geladen")
                if not channels:
                    _log.warning(f"[{_time.time()-t0:.2f}s] WARNING: Keine Serien gefunden!")
            else:
                _log.warning(f"[{_time.time()-t0:.2f}s] Unknown content_type: {self.content_type}")
                channels = []
            if not self._cancelled:
                _log.info(f"=== LazyLoadThread DONE === {len(channels)} channels in {_time.time()-t0:.2f}s")
                self.finished.emit(channels, self.content_type)
            else:
                _log.info(f"[{_time.time()-t0:.2f}s] LazyLoadThread cancelled")
        except Exception as e:
            import traceback as _tb
            tb_str = _tb.format_exc()
            _log.error(f"=== LazyLoadThread ERROR === {e}\n{tb_str}")
            if not self._cancelled:
                self.error.emit(f"{e}\n\nTraceback:\n{tb_str}")


class EpgAbrufThread(QThread):
    """Kurzlebiger Faden für den EPG-Abruf eines Live-Kanals.

    Der Abruf darf den Bedienfaden nicht blockieren, weil ein langsamer
    Xtream-Server die Oberfläche sonst mehrere Sekunden einfrieren würde.
    run() überschreibt die Basismethode ohne Ereignisschleife, deshalb ist
    quit() wirkungslos und cancel() der einzige Abbruchweg. Das Ergebnis kommt
    per Signal in die Oberfläche; Fehler bleiben still (kein Dialog).
    """

    epg_geladen = pyqtSignal(object, str)  # epg_daten (Liste oder None), kanalname

    def __init__(self, basis_url, benutzername, passwort, tvg_id, kanalname):
        super().__init__()
        self.basis_url = basis_url
        self.benutzername = benutzername
        self.passwort = passwort
        self.tvg_id = tvg_id
        self.kanalname = kanalname
        self._cancelled = False

    def cancel(self):
        """Abbruchflag setzen — der einzige Abbruchweg dieses Fadens."""
        self._cancelled = True

    def run(self):
        try:
            service = EpgService(self.basis_url, self.benutzername, self.passwort)
            epg_daten = service.get_live_stream_epg(int(self.tvg_id))
        except Exception as e:
            logger.warning(f"EPG-Abruf für '{self.kanalname}' fehlgeschlagen: {e}")
            epg_daten = None
        if self._cancelled:
            # Der Nutzer hat inzwischen weitergeschaltet — Ergebnis verwerfen
            return
        self.epg_geladen.emit(epg_daten, self.kanalname)


class ChannelListWidget(QListWidget):
    """Custom Channel List Widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUniformItemSizes(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setSpacing(2)


# === Tab Index Constants ===
TAB_LIVE_TV = 0
TAB_FILME = 1
TAB_SERIEN = 2
TAB_SUCHE = 3
TAB_EINSTELLUNGEN = 4

# Obergrenze der Kanalliste: Mehr als 2000 Zeilen auf einmal sind für niemanden
# bedienbar und blockieren die Oberfläche. Der Rest erscheint als Hinweiszeile.
MAX_LISTEN_EINTRAEGE = 2000

# Vorgabegröße der Schrift in Punkten; der Rahmen liegt bei 9 bis 28 Punkten
# (Begrenzung übernimmt theme.setze_schriftgroesse).
SCHRIFT_STANDARD = 13


class MainWindow(QMainWindow):
    """SMarTrPlay Hauptfenster — Tab-based navigation, no blocking dialogs."""

    # --- Vollbild: Vorgaben, damit Ereignisse vor dem Aufbau nicht stolpern ---
    _vollbild_aktiv = False
    _vollbild_versteckt = ()
    _vollbild_leiste = None
    _zappliste = None
    _vollbild_war_maximiert = False
    _folgenreihe = ()      # laufende Serienstaffel: Liste aus {'titel','url'}
    _folgen_index = -1     # welche Folge davon gerade laeuft

    def __init__(self):
        super().__init__()
        self.config = Config()
        # Gespeicherte Schriftgröße vom letzten Start anwenden. Die Vorgabe
        # sind 13 Punkte; der erlaubte Rahmen liegt bei 9 bis 28 Punkten.
        try:
            gespeicherte_schriftgroesse = int(self.config.get_setting("schriftgroesse", SCHRIFT_STANDARD))
        except (TypeError, ValueError):
            gespeicherte_schriftgroesse = SCHRIFT_STANDARD
        theme.setze_schriftgroesse(QApplication.instance(), gespeicherte_schriftgroesse)
        # VLC-Backend verwenden; nur wenn dessen Import scheiterte, greift
        # der alte ffplay-Backend als Rückfall.
        if VLC_BACKEND_AVAILABLE:
            self.player = VlcPlayerBackend()
        else:
            self.player = PlayerBackend()
        self.current_provider_id = None
        self.current_category = None
        self.channels = []

        # Tab lazy-init flags
        self._vod_initialized = False
        self._series_initialized = False
        self._search_initialized = False
        self._settings_initialized = False

        # Inline widget references
        self._vod_widget = None
        self._series_widget = None
        self._search_widget = None
        self._settings_widget = None

        # Pending series to open after tab init
        self._pending_series_name = None
        self._pending_series_url = None

        # Verwaltung abgestürzter Fäden: Läuft ein QThread nach der Wartezeit
        # noch, wird er hier geparkt und erst nach seinem Ende gelöscht.
        self._zombie_threads = []
        # Kurzlebiger Faden für den EPG-Abruf beim Kanal-Klick
        self._epg_thread = None

        self.setWindowTitle("SMarTrPlay - IPTV Player")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 850)

        self._build_ui()
        self._baue_tastenkuerzel()
        self._load_providers()
        self._letzten_provider_waehlen()

        # Player check timer — läuft jede Sekunde; Position und Dauer
        # kommen aus dem Player selbst, nicht aus einer Wanduhr.
        self.player_timer = QTimer(self)
        self.player_timer.timeout.connect(self._check_player)
        self.player_timer.start(1000)

        # Einmaliger Timer für die Spurabfrage: Erst etwa eine Sekunde nach
        # dem Kanalstart hat libvlc das Medium ausgewertet. Die Abfrage läuft
        # über den Timer im Bedienfaden und blockiert die Oberfläche nicht.
        self._tracks_timer = QTimer(self)
        self._tracks_timer.setSingleShot(True)
        self._tracks_timer.timeout.connect(self._lade_spuren_vom_player)

        # FD (File Descriptor) Monitor — prueft alle 30s offene FDs
        self._fd_logger = logging.getLogger('SMarTrPlay.FDMonitor')
        self._fd_warning_threshold = 800
        self._fd_critical_threshold = 950
        self._fd_warning_logged = False
        self.fd_monitor_timer = QTimer(self)
        self.fd_monitor_timer.timeout.connect(self._check_fd_usage)
        self.fd_monitor_timer.start(30000)
        self._fd_logger.info("FD-Monitor gestartet (Interval: 30s, Warnung: >800, Kritisch: >950)")

        # Debug-Server starten (HTTP Diagnose auf Port 8421).
        # DebugServer.start() protokolliert den Start bereits selbst; die Meldung
        # hier erscheint nur, wenn der Server laut eigener Zustandsabfrage läuft.
        self.debug_server = DebugServer(port=8421, config=self.config)
        self.debug_server.start()
        if self.debug_server.is_running():
            logging.getLogger('SMarTrPlay').info('Debug-Server läuft auf Port 8421')

    # =========================================================================
    # UI BUILDING
    # =========================================================================

    def _build_ui(self):
        """UI aufbauen — Tab-based layout with non-blocking inline widgets."""
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header ---
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_DEEP};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)

        # Logo / Title
        title_label = QLabel("SMarTrPlay")
        title_label.setObjectName("headerTitle")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: 22px;
                font-weight: 800;
            }}
        """)
        subtitle = QLabel("IPTV Player")
        subtitle.setObjectName("headerSubtitle")
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; padding-left: 8px; padding-bottom: 2px;")

        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Provider selector (global, in header)
        self.provider_combo = QComboBox()
        self.provider_combo.setFixedWidth(200)
        self.provider_combo.setFixedHeight(36)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_change)
        header_layout.addWidget(self.provider_combo)

        # Add Provider Button (global, in header)
        self.btn_add_provider = QPushButton("+ Provider")
        self.btn_add_provider.setFixedHeight(36)
        self.btn_add_provider.clicked.connect(self._add_provider)
        header_layout.addWidget(self.btn_add_provider)

        main_layout.addWidget(header)

        # --- Main Splitter: Left (Tabs) | Right (Video) ---
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT: Tab Widget with 5 tabs
        self.content_tabs = QTabWidget()
        self.content_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER};
                background-color: {BG_DEEP};
            }}
            QTabBar::tab {{
                background-color: {BG_DEEP};
                color: {TEXT_MUTED};
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 600;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {ACCENT_CYAN};
                border-bottom: 2px solid {ACCENT_CYAN};
            }}
            QTabBar::tab:hover {{
                color: {TEXT_SECONDARY};
            }}
        """)
        self.content_tabs.setTabsClosable(False)
        self.content_tabs.currentChanged.connect(self._on_tab_changed)

        # Build each tab
        self._build_live_tv_tab()
        self._build_filme_tab()
        self._build_serien_tab()
        self._build_suche_tab()
        self._build_einstellungen_tab()

        main_splitter.addWidget(self.content_tabs)

        # RIGHT: Video Area (always visible)
        main_splitter.addWidget(self._build_video_area())

        # Splitter ratios: content 55% | video 45%
        main_splitter.setSizes([770, 630])
        main_splitter.setHandleWidth(2)

        main_layout.addWidget(main_splitter)

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Bereit")
        self.setStatusBar(self.status_bar)

        # Dauerhafter Markenhinweis rechts in der Fusszeile.
        # Er sitzt als permanentes Widget in der Statusleiste und wird deshalb
        # von kurzlebigen Statusmeldungen nicht ueberschrieben.
        self.marken_hinweis = QLabel('coded with <b>smartragents.ai</b>')
        self.marken_hinweis.setObjectName("markenHinweis")
        self.marken_hinweis.setTextFormat(Qt.RichText)
        self.marken_hinweis.setCursor(Qt.PointingHandCursor)
        self.marken_hinweis.setToolTip(
            "Gebaut mit SMarTrAgents. Anklicken oeffnet smartragents.ai im Browser."
        )
        self.marken_hinweis.setStyleSheet(
            "#markenHinweis {"
            f" color: {ACCENT_CYAN};"
            " font-size: 13px;"
            " padding: 2px 10px;"
            " border: 1px solid #1e2a3a;"
            " border-radius: 6px;"
            "}"
            "#markenHinweis:hover {"
            f" color: {ACCENT_PURPLE};"
            f" border-color: {ACCENT_CYAN};"
            "}"
        )
        self.marken_hinweis.mousePressEvent = self._oeffne_smartragents
        self.status_bar.addPermanentWidget(self.marken_hinweis)

        # Menu Bar
        self._build_menu()

    def _build_live_tv_tab(self):
        """Tab 0: Live TV — categories + channels + search."""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        # Search field at top
        search_frame = QFrame()
        search_frame.setFixedHeight(44)
        search_frame.setStyleSheet(f"background-color: {BG_CARD}; border-bottom: 1px solid {BORDER};")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(12, 6, 12, 6)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Kanaele suchen...")
        self.search_bar.setFixedHeight(32)
        # Zeitpuffer für die Suche: Erst 300 Millisekunden nach der letzten
        # Eingabe läuft die Datenbanksuche. Jede Eingabe startet den einmaligen
        # Zeitgeber neu, dadurch löst schnelles Tippen genau EINEN Suchlauf aus,
        # statt bei jedem Tastendruck die gesamte Liste neu zu füllen.
        self._such_timer = QTimer(self)
        self._such_timer.setSingleShot(True)
        self._such_timer.setInterval(300)
        self._such_timer.timeout.connect(self._suche_nach_zeitpuffer)
        self.search_bar.textChanged.connect(self._suche_zeitpuffer_starten)
        search_layout.addWidget(self.search_bar)
        tab_layout.addWidget(search_frame)

        # Horizontal splitter: categories | channels
        live_splitter = QSplitter(Qt.Horizontal)

        # Left: Categories
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        sidebar_title = QLabel("KATEGORIEN")
        sidebar_title.setObjectName("sidebarTitle")
        sidebar_title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
                padding: 12px 12px 6px 12px;
            }}
        """)
        sidebar_layout.addWidget(sidebar_title)

        self.category_list = QListWidget()
        self.category_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {BG_DEEP};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 16px;
                color: {TEXT_SECONDARY};
                border-radius: 0;
            }}
            QListWidget::item:selected {{
                background-color: {ACCENT_VIOLET};
                color: {TEXT_PRIMARY};
            }}
            QListWidget::item:hover {{
                background-color: {BG_CARD_HOVER};
            }}
        """)
        self.category_list.currentItemChanged.connect(self._on_category_change)
        # Sichtbare senkrechte Bildlaufleiste, sobald die Liste länger als das
        # Fenster ist — für den Besitzer die Voraussetzung zur Bedienung.
        self.category_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sidebar_layout.addWidget(self.category_list)

        # YouTube / Netflix Buttons in sidebar
        extra_btns = QWidget()
        extra_btns.setStyleSheet(f"background-color: {BG_DEEP};")
        extra_layout = QVBoxLayout(extra_btns)
        extra_layout.setContentsMargins(8, 8, 8, 8)
        extra_layout.setSpacing(4)

        yt_btn = QPushButton("YouTube")
        yt_btn.setFixedHeight(34)
        yt_btn.clicked.connect(self._open_youtube)
        extra_layout.addWidget(yt_btn)

        nf_btn = QPushButton("Netflix")
        nf_btn.setFixedHeight(34)
        nf_btn.clicked.connect(self._open_netflix)
        extra_layout.addWidget(nf_btn)

        sidebar_layout.addWidget(extra_btns)

        live_splitter.addWidget(sidebar_widget)

        # Right: Channel list
        channel_widget = QWidget()
        channel_layout = QVBoxLayout(channel_widget)
        channel_layout.setContentsMargins(0, 0, 0, 0)
        channel_layout.setSpacing(0)

        channel_header = QLabel("Kanaele")
        channel_header.setFixedHeight(40)
        channel_header.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_CARD};
                color: {TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 600;
                padding: 10px 16px;
                border-bottom: 1px solid {BORDER};
            }}
        """)
        channel_layout.addWidget(channel_header)

        self.channel_list = ChannelListWidget()
        self.channel_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {BG_CARD};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 16px;
                color: {TEXT_PRIMARY};
                border-bottom: 1px solid {BORDER};
                border-radius: 0;
            }}
            QListWidget::item:selected {{
                background-color: {BG_CARD_HOVER};
                color: {ACCENT_CYAN};
            }}
            QListWidget::item:hover {{
                background-color: {BG_CARD_HOVER};
            }}
        """)
        # Sichtbare senkrechte Bildlaufleiste, sobald die Liste länger als das
        # Fenster ist — die Liste scrollt selbst und braucht keine Bildlauffläche.
        self.channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.channel_list.itemDoubleClicked.connect(self._play_channel)
        # Eingabetaste startet den Kanal ebenfalls (Tastaturbedienung)
        self.channel_list.itemActivated.connect(self._play_channel)
        self.channel_list.itemClicked.connect(self._on_channel_click)
        channel_layout.addWidget(self.channel_list)

        # Loading bar
        self.loading_bar = QProgressBar()
        self.loading_bar.setVisible(False)
        self.loading_bar.setFixedHeight(3)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {BG_DEEP};
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_CYAN};
            }}
        """)
        channel_layout.addWidget(self.loading_bar)

        live_splitter.addWidget(channel_widget)
        live_splitter.setSizes([250, 450])
        live_splitter.setHandleWidth(1)

        tab_layout.addWidget(live_splitter)
        self.content_tabs.addTab(tab_widget, "Live TV")

    def _build_filme_tab(self):
        """Tab 1: Filme — VodBrowser as inline widget (lazy init)."""
        self._vod_container = QWidget()
        self._vod_container_layout = QVBoxLayout(self._vod_container)
        self._vod_container_layout.setContentsMargins(0, 0, 0, 0)
        self._vod_container_layout.setSpacing(0)

        # Bildlauffläche um den Film-Browser: Sein Inhalt kann länger werden
        # als das Fenster. Die Fläche liegt von Anfang an im Reiter, bleibt
        # aber unsichtbar, bis der Browser beim ersten Öffnen hineingelegt wird.
        self._vod_scroll = QScrollArea()
        self._vod_scroll.setWidgetResizable(True)
        self._vod_scroll.setFrameShape(QFrame.NoFrame)
        self._vod_scroll.setVisible(False)
        self._vod_container_layout.addWidget(self._vod_scroll)

        # Placeholder label
        placeholder = QLabel("Wähle einen Xtream Provider aus, um Filme zu durchsuchen.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; padding: 40px;")
        self._vod_container_layout.addWidget(placeholder)
        self._vod_placeholder = placeholder

        self.content_tabs.addTab(self._vod_container, "Filme")

    def _build_serien_tab(self):
        """Tab 2: Serien — SeriesBrowser as inline widget (lazy init)."""
        self._series_container = QWidget()
        self._series_container_layout = QVBoxLayout(self._series_container)
        self._series_container_layout.setContentsMargins(0, 0, 0, 0)
        self._series_container_layout.setSpacing(0)

        # Bildlauffläche um den Serien-Browser (siehe Filme-Reiter)
        self._series_scroll = QScrollArea()
        self._series_scroll.setWidgetResizable(True)
        self._series_scroll.setFrameShape(QFrame.NoFrame)
        self._series_scroll.setVisible(False)
        self._series_container_layout.addWidget(self._series_scroll)

        placeholder = QLabel("Wähle einen Xtream Provider aus, um Serien zu durchsuchen.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; padding: 40px;")
        self._series_container_layout.addWidget(placeholder)
        self._series_placeholder = placeholder

        self.content_tabs.addTab(self._series_container, "Serien")

    def _build_suche_tab(self):
        """Tab 3: Suche — SearchBrowser as inline widget (lazy init)."""
        self._search_container = QWidget()
        self._search_container_layout = QVBoxLayout(self._search_container)
        self._search_container_layout.setContentsMargins(0, 0, 0, 0)
        self._search_container_layout.setSpacing(0)

        # Bildlauffläche um den Such-Browser (siehe Filme-Reiter)
        self._search_scroll = QScrollArea()
        self._search_scroll.setWidgetResizable(True)
        self._search_scroll.setFrameShape(QFrame.NoFrame)
        self._search_scroll.setVisible(False)
        self._search_container_layout.addWidget(self._search_scroll)

        placeholder = QLabel("Wähle einen Provider aus, um die globale Suche zu nutzen.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; padding: 40px;")
        self._search_container_layout.addWidget(placeholder)
        self._search_placeholder = placeholder

        self.content_tabs.addTab(self._search_container, "Suche")

    def _build_einstellungen_tab(self):
        """Tab 4: Einstellungen — Provider list + Settings inline widget."""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        tab_layout.setSpacing(12)

        # --- Provider Management Section ---
        provider_section = QLabel("PROVIDER")
        provider_section.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }}
        """)
        tab_layout.addWidget(provider_section)

        # Provider list
        self.settings_provider_list = QListWidget()
        self.settings_provider_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                color: {TEXT_PRIMARY};
            }}
            QListWidget::item:selected {{
                background-color: {BG_CARD_HOVER};
                color: {ACCENT_CYAN};
            }}
        """)
        self.settings_provider_list.setMaximumHeight(150)
        # Auch diese Liste zeigt ihre senkrechte Bildlaufleiste bei Bedarf
        self.settings_provider_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tab_layout.addWidget(self.settings_provider_list)

        # Provider buttons
        provider_btn_layout = QHBoxLayout()
        provider_btn_layout.setSpacing(8)

        btn_add = QPushButton("+ Hinzufuegen")
        btn_add.setFixedHeight(34)
        btn_add.clicked.connect(self._add_provider)
        provider_btn_layout.addWidget(btn_add)

        btn_remove = QPushButton("Entfernen")
        btn_remove.setFixedHeight(34)
        btn_remove.clicked.connect(self._remove_provider_from_settings)
        provider_btn_layout.addWidget(btn_remove)

        btn_refresh = QPushButton("Aktualisieren")
        btn_refresh.setFixedHeight(34)
        btn_refresh.clicked.connect(self._refresh_provider_list_in_settings)
        provider_btn_layout.addWidget(btn_refresh)

        provider_btn_layout.addStretch()
        tab_layout.addLayout(provider_btn_layout)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER};")
        tab_layout.addWidget(sep)

        # --- Settings Section (inline) ---
        settings_label = QLabel("EINSTELLUNGEN")
        settings_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }}
        """)
        tab_layout.addWidget(settings_label)

        # Container for SettingsDialog inline widget (lazy init)
        self._settings_container = QWidget()
        self._settings_container_layout = QVBoxLayout(self._settings_container)
        self._settings_container_layout.setContentsMargins(0, 0, 0, 0)
        self._settings_container_layout.setSpacing(0)

        settings_placeholder = QLabel("Einstellungen werden geladen...")
        settings_placeholder.setAlignment(Qt.AlignCenter)
        settings_placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; padding: 20px;")
        self._settings_container_layout.addWidget(settings_placeholder)
        self._settings_placeholder = settings_placeholder

        tab_layout.addWidget(self._settings_container, stretch=1)

        # Der Reiterinhalt kann länger werden als das Fenster, deshalb liegt
        # er vollständig in einer Bildlauffläche mit mitwachsendem Inhalt.
        einstellungen_scroll = QScrollArea()
        einstellungen_scroll.setWidgetResizable(True)
        einstellungen_scroll.setFrameShape(QFrame.NoFrame)
        # Mindestbreite, damit die Formulare nicht zusammengedrückt werden;
        # bei schmalen Fenstern scrollt die Fläche stattdessen waagerecht.
        tab_widget.setMinimumWidth(560)
        einstellungen_scroll.setWidget(tab_widget)
        self.content_tabs.addTab(einstellungen_scroll, "Einstellungen")

    def _build_video_area(self):
        """Build the always-visible video player area (right side of splitter)."""
        player_widget = QWidget()
        player_layout = QVBoxLayout(player_widget)
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.setSpacing(0)

        player_header = QLabel("Player")
        player_header.setFixedHeight(40)
        player_header.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_CARD};
                color: {TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 600;
                padding: 10px 16px;
                border-bottom: 1px solid {BORDER};
            }}
        """)
        player_layout.addWidget(player_header)

        # Player area (black background for video)
        self.video_container = QWidget()
        # Ohne diesen Namen findet die globale Suche das Videofenster nicht
        # und zeigt kein Bild.
        self.video_container.setObjectName("video_container")
        self.video_container.setStyleSheet(f"background-color: black;")
        self.video_container.setMinimumSize(480, 270)
        player_layout.addWidget(self.video_container, stretch=1)

        # Enable double-click seek on video container
        self.video_container.installEventFilter(self)
        self.video_container.setMouseTracking(True)

        # Now Playing label
        self.now_playing_label = QLabel("Kein Kanal ausgewaehlt")
        self.now_playing_label.setFixedHeight(36)
        self.now_playing_label.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_DEEP};
                color: {TEXT_SECONDARY};
                font-size: 12px;
                padding: 10px 16px;
                border-top: 1px solid {BORDER};
            }}
        """)
        player_layout.addWidget(self.now_playing_label)

        # Player Controls — nur noch der YouTube-Knopf. Play und Stop liegen
        # allein in der VideoControlsBar, damit es keine doppelte Bedienung
        # mit zwei Reihen gleicher Funktion gibt.
        controls = QFrame()
        controls.setFixedHeight(56)
        controls.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_DEEP};
                border-top: 1px solid {BORDER};
            }}
        """)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(16, 8, 16, 8)
        controls_layout.setSpacing(8)

        controls_layout.addStretch()

        self.btn_youtube_play = QPushButton("YouTube URL")
        self.btn_youtube_play.setFixedHeight(36)
        self.btn_youtube_play.clicked.connect(self._play_youtube_url)
        controls_layout.addWidget(self.btn_youtube_play)

        player_layout.addWidget(controls)

        # v5: Video Controls Bar (Play/Stop, Seek, 10s, Volume, Stumm)
        if V5_AVAILABLE:
            self.video_controls = VideoControlsBar()
            self.video_controls.set_enabled(False)
            player_layout.addWidget(self.video_controls)

            # v5: Audio/Subtitle Options Bar
            self.audio_subtitle_bar = AudioSubtitleBar()
            self.audio_subtitle_bar.set_enabled(False)
            player_layout.addWidget(self.audio_subtitle_bar)

            # Connect VideoControlsBar signals
            self.video_controls.play_clicked.connect(self._toggle_play)
            self.video_controls.stop_clicked.connect(self._stop_player)
            self.video_controls.seek_10s_back.connect(lambda: self.player.seek_relative(-10))
            self.video_controls.seek_10s_forward.connect(lambda: self.player.seek_relative(10))
            self.video_controls.vollbild_clicked.connect(self._vollbild_umschalten)
            self.video_controls.seek_changed.connect(self._on_seek)
            self.video_controls.volume_changed.connect(self._on_volume_changed)
            self.video_controls.mute_clicked.connect(self._toggle_mute)

            # Connect AudioSubtitleBar signals
            self.audio_subtitle_bar.audio_track_changed.connect(self._on_audio_track_changed)
            self.audio_subtitle_bar.subtitle_changed.connect(self._on_subtitle_changed)
            self.audio_subtitle_bar.subtitle_delay_changed.connect(self._on_subtitle_delay)

        # Fuer das Vollbild: die Geschwister des Videobilds werden dort versteckt.
        self.player_widget = player_widget
        return player_widget

    def _build_menu(self):
        """Menu bar — actions now switch tabs instead of opening modal dialogs."""
        menubar = self.menuBar()

        # Datei Menu
        file_menu = menubar.addMenu("Datei")

        add_action = QAction("Provider hinzufuegen", self)
        add_action.triggered.connect(self._add_provider)
        file_menu.addAction(add_action)

        refresh_action = QAction("Playlist aktualisieren", self)
        refresh_action.triggered.connect(self._refresh_playlist)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        settings_action = QAction("Einstellungen", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(lambda: self.content_tabs.setCurrentIndex(TAB_EINSTELLUNGEN))
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("Beenden", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Ansicht Menu
        view_menu = menubar.addMenu("Ansicht")

        live_action = QAction("Live TV", self)
        live_action.setShortcut("Ctrl+L")
        live_action.triggered.connect(lambda: self.content_tabs.setCurrentIndex(TAB_LIVE_TV))
        view_menu.addAction(live_action)

        vod_action = QAction("Filme / VOD", self)
        vod_action.triggered.connect(lambda: self.content_tabs.setCurrentIndex(TAB_FILME))
        view_menu.addAction(vod_action)

        series_action = QAction("Serien", self)
        series_action.setShortcut("Ctrl+S")
        series_action.triggered.connect(lambda: self.content_tabs.setCurrentIndex(TAB_SERIEN))
        view_menu.addAction(series_action)

        global_search_action = QAction("Globale Suche", self)
        global_search_action.setShortcut("Ctrl+G")
        global_search_action.triggered.connect(lambda: self.content_tabs.setCurrentIndex(TAB_SUCHE))
        view_menu.addAction(global_search_action)

        view_menu.addSeparator()

        # Schriftgröße — große, gut lesbare Schrift ist für den Besitzer die
        # Voraussetzung zur Bedienung. Alle drei Befehle wirken sofort und
        # werden dauerhaft in den Einstellungen gespeichert.
        schrift_groesser_action = QAction("Schrift größer", self)
        schrift_groesser_action.setShortcut("Ctrl++")
        schrift_groesser_action.triggered.connect(lambda: self._schrift_aendern(1))
        view_menu.addAction(schrift_groesser_action)

        schrift_kleiner_action = QAction("Schrift kleiner", self)
        schrift_kleiner_action.setShortcut("Ctrl+-")
        schrift_kleiner_action.triggered.connect(lambda: self._schrift_aendern(-1))
        view_menu.addAction(schrift_kleiner_action)

        schrift_zuruecksetzen_action = QAction("Schrift zurücksetzen", self)
        schrift_zuruecksetzen_action.setShortcut("Ctrl+0")
        schrift_zuruecksetzen_action.triggered.connect(self._schrift_zuruecksetzen)
        view_menu.addAction(schrift_zuruecksetzen_action)

        view_menu.addSeparator()

        epg_action = QAction("EPG anzeigen", self)
        epg_action.setShortcut("Ctrl+E")
        epg_action.triggered.connect(self._toggle_epg)
        view_menu.addAction(epg_action)

        fav_action = QAction("Favoriten anzeigen", self)
        fav_action.setShortcut("Ctrl+F")
        fav_action.triggered.connect(self._show_favorites)
        view_menu.addAction(fav_action)

        mini_player_action = QAction("Mini Player", self)
        mini_player_action.triggered.connect(self._toggle_mini_player)
        view_menu.addAction(mini_player_action)

        epg_timeline_action = QAction("EPG Timeline", self)
        epg_timeline_action.triggered.connect(self._show_epg_timeline)
        view_menu.addAction(epg_timeline_action)

        catchup_action = QAction("Catch-up / Replay", self)
        catchup_action.triggered.connect(self._open_catchup)
        view_menu.addAction(catchup_action)

        # Werkzeuge Menu
        tools_menu = menubar.addMenu("Werkzeuge")

        pip_action = QAction("Bild-im-Bild", self)
        pip_action.setShortcut("Ctrl+P")
        pip_action.triggered.connect(self._toggle_pip)
        tools_menu.addAction(pip_action)

        subtitle_action = QAction("Untertitel laden", self)
        subtitle_action.triggered.connect(self._load_subtitle)
        tools_menu.addAction(subtitle_action)

        recording_action = QAction("Aufnahme starten/stoppen", self)
        recording_action.setShortcut("Ctrl+R")
        recording_action.triggered.connect(self._toggle_recording)
        tools_menu.addAction(recording_action)

        autorefresh_action = QAction("Auto-Refresh aktivieren", self)
        autorefresh_action.triggered.connect(self._toggle_auto_refresh)
        tools_menu.addAction(autorefresh_action)

        # Geraete Menu
        devices_menu = menubar.addMenu("Geraete")

        cast_action = QAction("DLNA/Chromecast Cast", self)
        cast_action.triggered.connect(self._open_cast)
        devices_menu.addAction(cast_action)

        remote_action = QAction("Web Remote Control", self)
        remote_action.triggered.connect(self._toggle_remote_control)
        devices_menu.addAction(remote_action)

        # Profil Menu
        profile_menu = menubar.addMenu("Profil")

        switch_profile_action = QAction("Profil wechseln", self)
        switch_profile_action.triggered.connect(self._switch_profile)
        profile_menu.addAction(switch_profile_action)

        # Markenmenue: dauerhafter Hinweis auf SMarTrAgents, zweiter Weg
        # neben dem anklickbaren Hinweis in der Fusszeile.
        hilfe_menu = menubar.addMenu("SMarTrAgents")

        webseite_action = QAction("smartragents.ai oeffnen", self)
        webseite_action.setStatusTip("Oeffnet smartragents.ai im Browser")
        webseite_action.triggered.connect(self._oeffne_smartragents)
        hilfe_menu.addAction(webseite_action)

        ueber_action = QAction("Ueber SMarTrPlay", self)
        ueber_action.triggered.connect(self._zeige_ueber)
        hilfe_menu.addAction(ueber_action)

    def _zeige_ueber(self):
        """Kurzer Hinweis, wer die Anwendung gebaut hat."""
        kasten = QMessageBox(self)
        kasten.setWindowTitle("Ueber SMarTrPlay")
        kasten.setTextFormat(Qt.RichText)
        kasten.setText(
            "<h3>SMarTrPlay</h3>"
            "<p>IPTV-Player fuer M3U, M3U+ und Xtream Codes.</p>"
            "<p>coded with <b>smartragents.ai</b></p>"
            '<p><a href="https://smartragents.ai">https://smartragents.ai</a></p>'
        )
        kasten.setStandardButtons(QMessageBox.Ok)
        knopf_web = kasten.addButton("Webseite oeffnen", QMessageBox.ActionRole)
        kasten.exec_()
        if kasten.clickedButton() is knopf_web:
            self._oeffne_smartragents()

    def _schrift_aendern(self, schritt):
        """Schriftgröße um einen Schritt ändern und dauerhaft merken.

        Die Begrenzung auf 9 bis 28 Punkte übernimmt theme.setze_schriftgroesse;
        am Rand des Bereichs bleibt die Größe einfach unverändert.
        """
        try:
            aktuell = int(self.config.get_setting("schriftgroesse", SCHRIFT_STANDARD))
        except (TypeError, ValueError):
            aktuell = SCHRIFT_STANDARD
        neu = theme.setze_schriftgroesse(QApplication.instance(), aktuell + schritt)
        self.config.set_setting("schriftgroesse", neu)
        if neu == aktuell:
            self.status_bar.showMessage(f"Schriftgröße bereits am Rand des Bereichs: {neu} Punkte", 2000)
        else:
            self.status_bar.showMessage(f"Schriftgröße: {neu} Punkte", 2000)
        logger.info(f"Schriftgröße geändert: {aktuell} -> {neu} Punkte (Schritt {schritt:+d})")

    def _schrift_zuruecksetzen(self):
        """Schriftgröße auf die Vorgabe von 13 Punkten zurücksetzen."""
        neu = theme.setze_schriftgroesse(QApplication.instance(), SCHRIFT_STANDARD)
        self.config.set_setting("schriftgroesse", neu)
        self.status_bar.showMessage(f"Schriftgröße zurückgesetzt: {neu} Punkte", 2000)
        logger.info(f"Schriftgröße zurückgesetzt auf {neu} Punkte")

    def _baue_tastenkuerzel(self):
        """Tastenkürzel für Wiedergabe, Spulen und Stummschaltung anlegen.

        Die Kürzel gelten anwendungsweit (Qt.ApplicationShortcut), wirken aber
        nicht, während der Schreibmarke im Suchfeld steht — dort gehört jede
        Taste dem eingegebenen Text.
        """
        def kuerzel_anlegen(taste, zielfunktion):
            sc = QShortcut(QKeySequence(taste), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda: self._kuerzel_ausfuehren(zielfunktion))

        kuerzel_anlegen(Qt.Key_Space, self._toggle_play)          # Wiedergabe und Pause
        kuerzel_anlegen(Qt.Key_S, self._stop_player)             # Stopp
        kuerzel_anlegen(Qt.Key_Right, lambda: self._spulen(10))  # zehn Sekunden vor
        kuerzel_anlegen(Qt.Key_Left, lambda: self._spulen(-10))  # zehn Sekunden zurück
        kuerzel_anlegen(Qt.Key_M, self._toggle_mute)             # stumm

    def _kuerzel_ausfuehren(self, zielfunktion):
        """Kürzel nur ausführen, wenn der Schreibmarke nicht im Suchfeld steht."""
        if QApplication.focusWidget() is self.search_bar:
            return
        try:
            zielfunktion()
        except Exception as e:
            logger.warning(f"Tastenkürzel konnte nicht ausgeführt werden: {e}")

    def _spulen(self, sekunden):
        """Um zehn Sekunden vor- oder zurückspulen, wenn ein Medium läuft."""
        if not (self.player.is_playing and self.player.is_running()):
            return
        if hasattr(self.player, "seek_relative"):
            self.player.seek_relative(sekunden)
            richtung = "vor" if sekunden > 0 else "zurück"
            self.status_bar.showMessage(f"10 Sekunden {richtung}", 1500)

    # =========================================================================
    # TAB LAZY INITIALIZATION
    # =========================================================================

    def _on_tab_changed(self, index):
        """Handle tab change — lazy init browser widgets."""
        if index == TAB_FILME and not self._vod_initialized:
            self._init_vod_tab()
        elif index == TAB_SERIEN and not self._series_initialized:
            self._init_series_tab()
        elif index == TAB_SUCHE and not self._search_initialized:
            self._init_search_tab()
        elif index == TAB_EINSTELLUNGEN and not self._settings_initialized:
            self._init_settings_tab()

    def _init_vod_tab(self):
        """Initialize VodBrowser as inline widget in Filme tab."""
        self._vod_initialized = True
        if not V4_AVAILABLE:
            self._vod_placeholder.setText("VOD Browser Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            self._vod_placeholder.setText("Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider or provider[2] != "xtream":
                self._vod_placeholder.setText("VOD Browser benoetigt einen Xtream Codes Provider.")
                return
            api = XtreamAPI(provider[3], provider[4], provider[5])
            # Remove placeholder
            self._vod_placeholder.setParent(None)
            # Create VodBrowser as inline widget (not modal dialog)
            self._vod_widget = VodBrowser(api, self.player, parent=self._vod_container)
            self._vod_widget.setWindowFlags(Qt.Widget)
            # Browser in die Bildlauffläche legen — sein Inhalt kann länger
            # werden als das Fenster.
            self._vod_scroll.setWidget(self._vod_widget)
            self._vod_scroll.setVisible(True)
            self.status_bar.showMessage("VOD Browser geladen", 2000)
        except Exception as e:
            self._vod_placeholder.setText(f"Fehler beim Laden des VOD Browsers: {e}")
            logger.error(f"VOD tab init error: {e}", exc_info=True)

    def _init_series_tab(self):
        """Initialize SeriesBrowser as inline widget in Serien tab."""
        self._series_initialized = True
        if not V2_AVAILABLE:
            self._series_placeholder.setText("Series Browser Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            self._series_placeholder.setText("Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider or provider[2] != "xtream":
                self._series_placeholder.setText("Serien-Browser benoetigt einen Xtream Codes Provider.")
                return
            api = XtreamAPI(provider[3], provider[4], provider[5])
            # Remove placeholder
            self._series_placeholder.setParent(None)
            # Create SeriesBrowser as inline widget
            self._series_widget = SeriesBrowser(api, self.player, parent=self._series_container)
            self._series_widget.setWindowFlags(Qt.Widget)
            # Browser in die Bildlauffläche legen (siehe Filme-Reiter)
            self._series_scroll.setWidget(self._series_widget)
            self._series_scroll.setVisible(True)
            self.status_bar.showMessage("Serien-Browser geladen", 2000)
        except Exception as e:
            self._series_placeholder.setText(f"Fehler beim Laden des Serien-Browsers: {e}")
            logger.error(f"Series tab init error: {e}", exc_info=True)

    def _init_search_tab(self):
        """Initialize SearchBrowser as inline widget in Suche tab."""
        self._search_initialized = True
        if not V4_AVAILABLE:
            self._search_placeholder.setText("Such-Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            self._search_placeholder.setText("Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider:
                self._search_placeholder.setText("Kein Provider gefunden.")
                return
            ptype = provider[2]
            # Remove placeholder
            self._search_placeholder.setParent(None)
            if ptype == "xtream":
                api = XtreamAPI(provider[3], provider[4], provider[5])
                self._search_widget = SearchBrowser(
                    provider_type="xtream",
                    api=api,
                    player=self.player,
                    parent=self._search_container
                )
            else:
                self._search_widget = SearchBrowser(
                    provider_type="m3u",
                    config=self.config,
                    provider_id=self.current_provider_id,
                    player=self.player,
                    parent=self._search_container
                )
            self._search_widget.setWindowFlags(Qt.Widget)
            # Browser in die Bildlauffläche legen (siehe Filme-Reiter)
            self._search_scroll.setWidget(self._search_widget)
            self._search_scroll.setVisible(True)
            self.status_bar.showMessage("Suche geladen", 2000)
        except Exception as e:
            self._search_placeholder.setText(f"Fehler beim Laden der Suche: {e}")
            logger.error(f"Search tab init error: {e}", exc_info=True)

    def _init_settings_tab(self):
        """Initialize SettingsDialog as inline widget in Einstellungen tab."""
        self._settings_initialized = True
        self._refresh_provider_list_in_settings()
        if not V2_AVAILABLE:
            self._settings_placeholder.setText("Settings Modul nicht verfuegbar.")
            return
        try:
            # Remove placeholder
            self._settings_placeholder.setParent(None)
            # Create SettingsDialog as inline widget
            self._settings_widget = SettingsDialog(config=self.config, parent=self._settings_container)
            self._settings_widget.setWindowFlags(Qt.Widget)
            # Hide dialog button box if present (accept/reject not needed for inline)
            from PyQt5.QtWidgets import QDialogButtonBox
            for child in self._settings_widget.findChildren(QDialogButtonBox):
                child.hide()
            self._settings_container_layout.addWidget(self._settings_widget)
            self.status_bar.showMessage("Einstellungen geladen", 2000)
        except Exception as e:
            self._settings_placeholder.setText(f"Fehler beim Laden der Einstellungen: {e}")
            logger.error(f"Settings tab init error: {e}", exc_info=True)

    def _refresh_provider_list_in_settings(self):
        """Refresh the provider list shown in the Einstellungen tab."""
        if hasattr(self, 'settings_provider_list'):
            self.settings_provider_list.clear()
            providers = self.config.get_providers()
            for p in providers:
                item = QListWidgetItem(f"{p[1]} ({p[2]})")
                item.setData(Qt.UserRole, p[0])
                self.settings_provider_list.addItem(item)

    def _remove_provider_from_settings(self):
        """Remove the selected provider from the Einstellungen tab."""
        item = self.settings_provider_list.currentItem()
        if not item:
            QMessageBox.information(self, "Provider", "Bitte einen Provider auswaehlen.")
            return
        pid = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Provider entfernen",
            f"Provider '{item.text()}' wirklich entfernen?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.config.remove_provider(pid)
                self._load_providers()
                self._refresh_provider_list_in_settings()
                self.status_bar.showMessage("Provider entfernt", 3000)
            except Exception as e:
                QMessageBox.warning(self, "Provider", f"Fehler beim Entfernen: {e}")

    # =========================================================================
    # PROVIDER / PLAYLIST MANAGEMENT
    # =========================================================================

    def _load_providers(self):
        """Provider in ComboBox laden."""
        self.provider_combo.clear()
        self.provider_combo.addItem("-- Provider waehlen --", None)
        providers = self.config.get_providers()
        for p in providers:
            self.provider_combo.addItem(f"{p[1]} ({p[2]})", p[0])

    def _add_provider(self):
        """Provider hinzufuegen Dialog oeffnen (modal — einziger verbleibender Dialog)."""
        dialog = AddProviderDialog(self)
        if dialog.exec_():
            pid = self.config.add_provider(
                dialog.provider_name,
                dialog.provider_type,
                dialog.provider_url,
                dialog.provider_user,
                dialog.provider_pass
            )
            self._load_providers()
            self.provider_combo.setCurrentIndex(self.provider_combo.count() - 1)
            self._load_playlist(pid)
            self._refresh_provider_list_in_settings()

    def _on_provider_change(self, idx):
        """Provider gewechselt — reset lazy-init flags so browsers reload."""
        logger.debug(f"_on_provider_change: idx={idx}")
        if idx <= 0:
            logger.debug("_on_provider_change: idx<=0, ignoring")
            return
        pid = self.provider_combo.itemData(idx)
        logger.info(f"Provider ausgewaehlt: idx={idx} pid={pid}")
        if pid:
            self.current_provider_id = pid
            provider = self.config.get_provider(pid)
            if provider:
                logger.info(f"Provider '{provider[1]}' ausgewaehlt (type={provider[2]}, url={provider[3]})")
            # Die Wahl merken, damit sie beim naechsten Start wieder steht.
            # Das spart bei jedem Start einen Bedienschritt.
            try:
                self.config.set_setting("letzter_provider", str(pid))
            except Exception as e:
                logger.warning(f"Letzten Provider nicht gespeichert: {e}")
            # Reset lazy-init flags so browsers reinitialize with new provider
            self._reset_tab_init_flags()
            self._browser_scrollflaechen_ausblenden()
            self._load_playlist(pid)
        else:
            logger.warning(f"_on_provider_change: pid is None for idx={idx}")

    def _reset_tab_init_flags(self):
        """Reset lazy-init flags and remove old browser widgets when provider changes.

        Die Browser sind QDialog-Unterklassen mit eigener closeEvent-Methode, die
        dort ihre Hintergrundfäden anhält. deleteLater() löst closeEvent NICHT aus,
        deshalb wird close() zuerst aufgerufen und erst danach entfernt und gelöscht.
        """
        # VOD
        if self._vod_initialized:
            if self._vod_widget:
                try:
                    self._vod_widget.close()
                except Exception as e:
                    logger.warning(f"close() beim VOD-Browser fehlgeschlagen: {e}")
                try:
                    self._vod_widget.setParent(None)
                except Exception as e:
                    logger.warning(f"setParent(None) beim VOD-Browser fehlgeschlagen: {e}")
                try:
                    self._vod_widget.deleteLater()
                except Exception as e:
                    logger.warning(f"deleteLater() beim VOD-Browser fehlgeschlagen: {e}")
                self._vod_widget = None
            self._vod_initialized = False
            self._vod_container_layout.addWidget(self._vod_placeholder)
            self._vod_placeholder.setText("Wähle einen Xtream Provider aus, um Filme zu durchsuchen.")
        # Series
        if self._series_initialized:
            if self._series_widget:
                try:
                    self._series_widget.close()
                except Exception as e:
                    logger.warning(f"close() beim Serien-Browser fehlgeschlagen: {e}")
                try:
                    self._series_widget.setParent(None)
                except Exception as e:
                    logger.warning(f"setParent(None) beim Serien-Browser fehlgeschlagen: {e}")
                try:
                    self._series_widget.deleteLater()
                except Exception as e:
                    logger.warning(f"deleteLater() beim Serien-Browser fehlgeschlagen: {e}")
                self._series_widget = None
            self._series_initialized = False
            self._series_container_layout.addWidget(self._series_placeholder)
            self._series_placeholder.setText("Wähle einen Xtream Provider aus, um Serien zu durchsuchen.")
        # Search
        if self._search_initialized:
            if self._search_widget:
                try:
                    self._search_widget.close()
                except Exception as e:
                    logger.warning(f"close() beim Such-Browser fehlgeschlagen: {e}")
                try:
                    self._search_widget.setParent(None)
                except Exception as e:
                    logger.warning(f"setParent(None) beim Such-Browser fehlgeschlagen: {e}")
                try:
                    self._search_widget.deleteLater()
                except Exception as e:
                    logger.warning(f"deleteLater() beim Such-Browser fehlgeschlagen: {e}")
                self._search_widget = None
            self._search_initialized = False
            self._search_container_layout.addWidget(self._search_placeholder)
            self._search_placeholder.setText("Wähle einen Provider aus, um die globale Suche zu nutzen.")

    def _browser_scrollflaechen_ausblenden(self):
        """Leere Bildlaufflächen der Browser-Reiter verbergen.

        _reset_tab_init_flags nimmt den Browsern beim Providerwechsel das
        Widget aus den Flächen. Die Flächen selbst bleiben im Reiter, damit
        der nächste Erstaufruf sie nicht erneut einfügen muss; ohne Inhalt
        dürfen sie aber keinen Platz belegen.
        """
        for flaechenname in ("_vod_scroll", "_series_scroll", "_search_scroll"):
            flaeche = getattr(self, flaechenname, None)
            if flaeche is not None:
                try:
                    flaeche.setVisible(False)
                except Exception as e:
                    logger.warning(f"Ausblenden der Bildlauffläche {flaechenname} fehlgeschlagen: {e}")

    def _letzten_provider_waehlen(self):
        """Den zuletzt benutzten Provider beim Start wieder auswaehlen.

        Ohne das steht beim Start immer "-- Provider waehlen --" und der Nutzer
        muss erst suchen und klicken, bevor ueberhaupt etwas zu sehen ist.
        Die Auswahl loest ueber das vorhandene Signal den Ladevorgang aus.
        """
        try:
            gemerkt = self.config.get_setting("letzter_provider", None)
            if not gemerkt:
                return
            pid = int(gemerkt)
            for idx in range(self.provider_combo.count()):
                if self.provider_combo.itemData(idx) == pid:
                    logger.info(f"Zuletzt benutzter Provider {pid} wird wieder ausgewaehlt")
                    self.provider_combo.setCurrentIndex(idx)
                    return
            logger.info(f"Gemerkter Provider {pid} ist nicht mehr vorhanden")
        except Exception as e:
            logger.warning(f"Letzten Provider nicht wiederhergestellt: {e}")

    def _oeffne_smartragents(self, event=None):
        """Oeffnet smartragents.ai im Standardbrowser.

        Haengt am dauerhaften Markenhinweis in der Fusszeile. Der Aufruf laeuft
        ueber xdg-open in einem eigenen Prozess, damit die Oberflaeche nicht
        wartet, falls der Browser lange zum Starten braucht.
        """
        adresse = "https://smartragents.ai"
        try:
            subprocess.Popen(
                ["xdg-open", adresse],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.status_bar.showMessage(f"{adresse} wird im Browser geoeffnet...", 4000)
            logger.info(f"Markenhinweis angeklickt, oeffne {adresse}")
        except Exception as e:
            logger.warning(f"Browser liess sich nicht oeffnen: {e}")
            try:
                import webbrowser
                webbrowser.open(adresse)
            except Exception as e2:
                logger.warning(f"Auch der Rueckfallweg scheiterte: {e2}")
                self.status_bar.showMessage(
                    f"Bitte im Browser aufrufen: {adresse}", 8000
                )

    def _thread_sicher_entsorgen(self, thread, name, wartezeit_ms=3000):
        """Entsorgt einen QThread, ohne ihn im laufenden Zustand zu zerstören.

        LoadPlaylistThread und LazyLoadThread überschreiben run() ohne exec_(),
        deshalb ist quit() bei ihnen wirkungslos; cancel() setzt das einzige
        Abbruchflag. Läuft der Faden nach der Wartezeit noch, übernimmt ihn der
        Fadenpark: dort wird er vom Elternobjekt abgenabelt und modulweit
        gehalten, bis er von selbst endet. Eine Liste am Fenster reicht nicht —
        stirbt das Fenster, nimmt Qt jedes laufende Kind mit, und genau das war
        am 19.09.2026 der Absturz beim Providerwechsel.
        Kein Fall darf eine Ausnahme nach außen werfen.
        """
        vorher = fadenpark.anzahl_geparkt()
        fadenpark.entsorge_faden(thread, wartezeit_ms=wartezeit_ms, name=name)
        if fadenpark.anzahl_geparkt() > vorher:
            # Spiegelliste am Fenster nur noch zur Anzeige, nicht als Lebensversicherung
            try:
                self._zombie_threads.append(thread)
            except Exception:
                pass

    def _load_playlist(self, provider_id):
        """Playlist fuer Provider laden (Optimized v2 - Lazy Loading + Cache)."""
        logger = logging.getLogger('SMarTrPlay.MainWindow')
        logger.info(f"=== _load_playlist START === provider_id={provider_id}")
        provider = self.config.get_provider(provider_id)
        if not provider:
            logger.error(f"Provider {provider_id} nicht gefunden")
            return

        ptype = provider[2]
        url = provider[3]
        username = provider[4]
        password = provider[5]

        # Vorherigen LoadPlaylistThread sauber beenden
        alter_faden = getattr(self, "load_thread", None)
        if alter_faden is not None:
            try:
                alter_faden.finished.disconnect()
                alter_faden.error.disconnect()
                if hasattr(alter_faden, 'progress'):
                    alter_faden.progress.disconnect()
            except (TypeError, RuntimeError):
                pass
            # cancel()/wait()/deleteLater() übernimmt die sichere Entsorgung
            self._thread_sicher_entsorgen(alter_faden, "LoadPlaylistThread")
        self.load_thread = None

        # Vorherigen LazyLoadThread sauber beenden
        alter_faden = getattr(self, "lazy_thread", None)
        if alter_faden is not None:
            try:
                alter_faden.finished.disconnect()
                alter_faden.error.disconnect()
                alter_faden.progress.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._thread_sicher_entsorgen(alter_faden, "LazyLoadThread")
        self.lazy_thread = None

        self.current_provider_id = provider_id
        self.loading_bar.setVisible(True)
        self.loading_bar.setRange(0, 100)
        self.loading_bar.setValue(0)
        self.status_bar.showMessage(f"Lade Playlist von {provider[1]}...")

        # LoadPlaylistThread mit provider_id, load_type und config
        load_type = 'live'  # Erste Ladung: nur Live TV
        if ptype == 'xtream':
            self.load_thread = LoadPlaylistThread(
                ptype, url, username, password,
                provider_id=provider_id,
                load_type=load_type,
                config=self.config
            )
        else:
            # M3U: alles laden (kein Lazy Loading fuer M3U)
            self.load_thread = LoadPlaylistThread(
                ptype, url, username, password,
                provider_id=provider_id,
                load_type='all',
                config=self.config
            )

        self.load_thread.progress.connect(self._on_load_progress)
        self.load_thread.finished.connect(self._on_playlist_loaded)
        self.load_thread.error.connect(self._on_playlist_error)
        self.load_thread.start()

    def _on_load_progress(self, status_text, current, total):
        """Progress-Update vom LoadPlaylistThread."""
        if total > 0:
            progress = int((current / total) * 100)
            self.loading_bar.setRange(0, 100)
            self.loading_bar.setValue(progress)
        else:
            self.loading_bar.setRange(0, 0)  # Indeterminate
        self.status_bar.showMessage(status_text)

    def _on_playlist_loaded(self, channels, content_type):
        """Playlist erfolgreich geladen (Optimized v2)."""
        logger = logging.getLogger('SMarTrPlay.MainWindow')
        logger.info(f"=== _on_playlist_loaded === type={content_type}, channels={len(channels)}")
        self.loading_bar.setVisible(False)

        provider_id = self.current_provider_id
        if not provider_id:
            logger.error("_on_playlist_loaded: no current_provider_id")
            return

        # Channels in DB speichern (nur den geladenen Typ)
        if content_type in ('live', 'vod', 'series'):
            self.config.add_channels_for_type(provider_id, channels, content_type)
            self.config.save_cache_meta(provider_id, content_type, len(channels))
        elif content_type in ('live_cached', 'vod_cached', 'series_cached'):
            # Cache-Treffer: Channels bereits in DB, nur Meta aktualisieren
            actual_type = content_type.replace('_cached', '')
            self.config.save_cache_meta(provider_id, actual_type, len(channels))
            logger.info(f"Cache-Treffer fuer {actual_type}: {len(channels)} Kanaele")
        elif content_type in ('m3u', 'all'):
            # M3U oder full load: alle Channels ersetzen
            self.config.add_channels(provider_id, channels)
            self.config.save_cache_meta(provider_id, 'all', len(channels))
        else:
            self.config.add_channels(provider_id, channels)

        self.status_bar.showMessage(f"{len(channels)} Kanaele geladen", 3000)

        # Kategorien zaehlen fuer Log
        live_count = sum(1 for ch in channels if ch.get('type') == 'live')
        vod_count = sum(1 for ch in channels if ch.get('type') == 'vod')
        series_count = sum(1 for ch in channels if ch.get('type') == 'series')
        cat_count = len(set(ch.get('category', '') for ch in channels if ch.get('category')))
        logger.info(f"Playlist geladen: {len(channels)} Kanaele, {cat_count} Kategorien (Live={live_count}, VOD={vod_count}, Series={series_count})")

        # _update_categories wählt die erste Kategorie mit blockierten Signalen,
        # löst also über currentItemChanged KEINE zweite Kanalabfrage mehr aus.
        # Deshalb läuft die Kanalliste nach einem Ladevorgang genau EINMAL, hier.
        logger.info("Playlist geladen — Kanalliste wird genau einmal aktualisiert")
        self._update_categories()
        self._update_channels()

        # Lazy Loading: VOD und Series im Hintergrund laden (nur bei Xtream)
        if content_type in ('live', 'live_cached'):
            provider = self.config.get_provider(provider_id)
            if provider and provider[2] == 'xtream':
                self._start_lazy_load('vod')
                # Series wird nach VOD gestartet

    def _start_lazy_load(self, content_type):
        """Startet Hintergrund-Laden von VOD oder Series."""
        logger = logging.getLogger('SMarTrPlay.MainWindow')
        if not self.current_provider_id:
            return
        provider = self.config.get_provider(self.current_provider_id)
        if not provider or provider[2] != 'xtream':
            return

        # Pruefe Cache zuerst
        if self.config.is_cache_valid(self.current_provider_id, content_type, 3600):
            count = self.config.get_channel_count_by_type(self.current_provider_id, content_type)
            if count > 0:
                logger.info(f"{content_type} Cache gueltig: {count} Eintraege - kein Lazy Load noetig")
                # Nach VOD Cache: Series starten
                if content_type == 'vod':
                    self._start_lazy_load('series')
                return

        logger.info(f"Starte Lazy Load: {content_type}")
        api = XtreamAPI(provider[3], provider[4], provider[5])

        # Vorherigen LazyLoadThread beenden
        alter_faden = getattr(self, 'lazy_thread', None)
        if alter_faden is not None:
            try:
                alter_faden.finished.disconnect()
                alter_faden.error.disconnect()
                alter_faden.progress.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._thread_sicher_entsorgen(alter_faden, "LazyLoadThread")
        self.lazy_thread = None

        self.lazy_thread = LazyLoadThread(api, content_type, provider_id=self.current_provider_id, config=self.config)
        self.lazy_thread.progress.connect(self._on_lazy_load_progress)
        self.lazy_thread.finished.connect(self._on_lazy_load_finished)
        self.lazy_thread.error.connect(self._on_lazy_load_error)
        self.lazy_thread.start()

    def _on_lazy_load_progress(self, status_text, current, total):
        """Progress-Update vom LazyLoadThread (im Hintergrund)."""
        # Nur Status-Bar aktualisieren, keine loading_bar (die ist fuer Live TV)
        self.status_bar.showMessage(status_text)

    def _on_lazy_load_finished(self, channels, content_type):
        """Lazy Load abgeschlossen (VOD oder Series)."""
        logger = logging.getLogger('SMarTrPlay.MainWindow')
        logger.info(f"Lazy Load fertig: {content_type} = {len(channels)} Kanaele")
        provider_id = self.current_provider_id
        if provider_id and channels:
            self.config.add_channels_for_type(provider_id, channels, content_type)
            self.config.save_cache_meta(provider_id, content_type, len(channels))
            # Kategorien aktualisieren um neue VOD/Series Kategorien zu zeigen
            self._update_categories()
        self.status_bar.showMessage(f"{content_type.upper()}: {len(channels)} geladen", 3000)

        # Nach VOD: Series laden
        if content_type == 'vod':
            self._start_lazy_load('series')

    def _on_lazy_load_error(self, error_msg):
        """Lazy Load Fehler (nur loggen, nicht blockierend)."""
        logger = logging.getLogger('SMarTrPlay.MainWindow')
        logger.warning(f"Lazy Load Fehler (nicht kritisch): {error_msg}")
        self.status_bar.showMessage(f"Hintergrund-Laden fehlgeschlagen: {error_msg}", 5000)

    def _on_playlist_error(self, error_msg):
        """Playlist Fehler."""
        logger = logging.getLogger('SMarTrPlay.MainWindow')
        logger.error(f"Playlist Fehler: {error_msg}")
        self.loading_bar.setVisible(False)
        self.status_bar.showMessage(f"Fehler: {error_msg}")
        QMessageBox.warning(self, "Playlist Fehler", error_msg)

    # =========================================================================
    # CATEGORIES / CHANNELS
    # =========================================================================

    def _update_categories(self):
        """Kategorien in Sidebar laden (type-spezifisch mit Fallback)."""
        logger.info(f"=== _update_categories === provider_id={self.current_provider_id}")
        self.category_list.clear()
        item = QListWidgetItem("Alle")
        item.setData(Qt.UserRole, None)
        self.category_list.addItem(item)

        # Type-spezifische Kategorien abrufen
        live_cats = self.config.get_categories(self.current_provider_id, type="live")
        vod_cats = self.config.get_categories(self.current_provider_id, type="vod")
        series_cats = self.config.get_categories(self.current_provider_id, type="series")
        logger.info(f"Kategorien aktualisiert: {len(live_cats)} Live, {len(vod_cats)} VOD, {len(series_cats)} Series")

        # Fallback: Wenn alle type-spezifischen Listen leer sind,
        # alle Kategorien ohne Type-Filter abrufen
        if not live_cats and not vod_cats and not series_cats:
            logger.warning(f"Keine type-spezifischen Kategorien gefunden — verwende Fallback ohne Type-Filter")
            all_cats = self.config.get_categories(self.current_provider_id)
            logger.info(f"Fallback: {len(all_cats)} Kategorien gesamt")
            for cat in all_cats:
                if cat:
                    item = QListWidgetItem(cat)
                    item.setData(Qt.UserRole, cat)
                    self.category_list.addItem(item)
            # Zeilenauswahl ohne Signalwirkung, damit currentItemChanged keine
            # zweite Kanalabfrage auslöst. Der einzige _update_channels-Aufruf
            # nach dem Laden steht in _on_playlist_loaded.
            self.category_list.blockSignals(True)
            self.category_list.setCurrentRow(0)
            self.category_list.blockSignals(False)
            return

        # Live Kategorien
        if live_cats:
            sep = QListWidgetItem("\u2500\u2500 Live TV \u2500\u2500")
            sep.setData(Qt.UserRole, None)
            sep.setFlags(Qt.NoItemFlags)
            self.category_list.addItem(sep)
            for cat in live_cats:
                if cat:
                    item = QListWidgetItem(cat)
                    item.setData(Qt.UserRole, cat)
                    self.category_list.addItem(item)

        # VOD Kategorien
        if vod_cats:
            sep = QListWidgetItem("\u2500\u2500 VOD (Filme) \u2500\u2500")
            sep.setData(Qt.UserRole, None)
            sep.setFlags(Qt.NoItemFlags)
            self.category_list.addItem(sep)
            for cat in vod_cats:
                if cat:
                    item = QListWidgetItem(cat)
                    item.setData(Qt.UserRole, cat)
                    self.category_list.addItem(item)

        # Series Kategorien
        if series_cats:
            sep = QListWidgetItem("\u2500\u2500 Serien \u2500\u2500")
            sep.setData(Qt.UserRole, None)
            sep.setFlags(Qt.NoItemFlags)
            self.category_list.addItem(sep)
            for cat in series_cats:
                if cat:
                    item = QListWidgetItem(cat)
                    item.setData(Qt.UserRole, cat)
                    self.category_list.addItem(item)

        # Zeilenauswahl ohne Signalwirkung, damit currentItemChanged keine zweite
        # Kanalabfrage auslöst. Der einzige _update_channels-Aufruf nach dem
        # Laden steht in _on_playlist_loaded — genau ein Lauf je Ladevorgang.
        self.category_list.blockSignals(True)
        self.category_list.setCurrentRow(0)
        self.category_list.blockSignals(False)

    def _update_channels(self, search=None):
        """Kanaele in Liste laden — begrenzt, gebündelt und mit Typanzeige.

        Jeder Aufruf protokolliert sich mit einer Zeile, damit im Protokoll
        sichtbar bleibt, dass nach einem Ladevorgang genau EIN Lauf erfolgt.
        """
        logger.info(f"=== _update_channels === Kategorie='{self.current_category}' Suche='{search}' (ein Lauf je Auslöser)")
        fuell_start = time.monotonic()
        self.channel_list.clear()
        # Obergrenze: Mehr als 2000 Zeilen auf einmal sind nicht bedienbar.
        # Die Gesamtzahl kommt aus dem zählenden Abruf, ohne alles zu laden.
        channels = self.config.get_channels(
            provider_id=self.current_provider_id,
            category=self.current_category,
            search=search,
            limit=MAX_LISTEN_EINTRAEGE
        )
        self.channels = channels
        gesamtzahl = self.config.get_channel_count(
            provider_id=self.current_provider_id,
            category=self.current_category,
            search=search
        )
        if gesamtzahl > len(channels):
            logger.info(f"Kanalliste gekürzt: {len(channels)} von {gesamtzahl} Einträgen geladen")
        elif not channels:
            logger.warning(f"Keine Kanaele gefunden fuer Kategorie='{self.current_category}' provider_id={self.current_provider_id}")
        # Live-Kanaele zeigen den Bildschirm, Filme die Filmklappe und Serien
        # das Bücherregal — drei deutlich unterscheidbare Symbole.
        type_icons = {"live": "\U0001F4FA", "vod": "\U0001F3AC", "series": "\U0001F4DA"}
        # Stapelverarbeitung: Neuzeichnen und Signale während des Füllens
        # unterbinden, damit die Liste nicht nach jedem Eintrag einzeln
        # zeichnet und die Auswahl nicht zwischendurch feuert.
        self.channel_list.setUpdatesEnabled(False)
        self.channel_list.blockSignals(True)
        try:
            for ch in channels:
                ch_id, _, name, url, logo, cat, tvg_id, tvg_name, ch_type = ch
                icon = type_icons.get(ch_type, "\U0001F4FA")
                display = f"{icon} {name}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, ch_id)
                item.setToolTip(f"{name}\nKategorie: {cat}\nTyp: {ch_type}")
                self.channel_list.addItem(item)
            # Wurde die Liste gekürzt, zeigt die letzte Zeile die echte
            # Restzahl. Sie trägt kein Kennungsdatum und ist nicht anwählbar,
            # kann also weder abgespielt werden noch reagieren.
            if gesamtzahl > len(channels):
                rest = gesamtzahl - len(channels)
                hinweis = QListWidgetItem(f"... {rest} weitere Eintraege, bitte die Suche benutzen")
                hinweis.setFlags(Qt.ItemIsEnabled)
                self.channel_list.addItem(hinweis)
        finally:
            # Auch im Fehlerfall muss die Liste wieder zeichnen und melden
            self.channel_list.blockSignals(False)
            self.channel_list.setUpdatesEnabled(True)
        fuell_dauer_ms = (time.monotonic() - fuell_start) * 1000.0
        logger.info(f"Kanalliste gefüllt: {len(channels)} Einträge in {fuell_dauer_ms:.1f} ms")
        self.status_bar.showMessage(f"{len(channels)} Kanaele", 2000)

    def _on_category_change(self, current, previous):
        """Kategorie gewechselt."""
        if not current:
            return
        self.current_category = current.data(Qt.UserRole)
        self._update_channels(self.search_bar.text())

    def _suche_zeitpuffer_starten(self, text):
        """Jede Eingabe startet den einmaligen Suchzeitgeber neu (300 ms)."""
        self._such_timer.start(300)

    def _suche_nach_zeitpuffer(self):
        """Zeitgeber abgelaufen — erst jetzt läuft die Suche genau einmal aus."""
        self._on_search(self.search_bar.text())

    def _on_search(self, text):
        """Suche ausgeführt (nach Ablauf des Zeitpuffers)."""
        self._update_channels(text)

    # =========================================================================
    # PLAYBACK
    # =========================================================================

    def _play_channel(self, item):
        """Kanal abspielen."""
        ch_id = item.data(Qt.UserRole)
        if ch_id is None:
            # Hinweiszeile der gekürzten Liste — nicht abspielbar
            return
        # Einzelabruf über den Primärschlüssel: eine Zeile statt aller
        # Kanäle, die Spaltenreihenfolge bleibt unverändert.
        ch = self.config.get_channel(ch_id)
        if not ch:
            logger.warning(f"Kanal mit Kennung {ch_id} nicht abspielbar: Eintrag fehlt")
            return
        name = ch[2]
        url = ch[3]
        ch_type = ch[8] if len(ch) > 8 else "live"

        # Series: Switch to Series tab instead of opening modal dialog
        if ch_type == "series":
            self.status_bar.showMessage(f"Oeffne Serien-Browser: {name}...")
            self._open_series_browser_for_series(name, url)
            return

        self.now_playing_label.setText(f"Spielt: {name}")
        self.status_bar.showMessage(f"Spiele {name}...")

        # Ein Kanal loest eine laufende Staffel ab: ab jetzt wird wieder
        # durch die Kanaele gezappt, nicht durch Folgen.
        self._folgenreihe = ()
        self._folgen_index = -1

        # In Qt Fenster einbetten
        wid = int(self.video_container.winId())
        self.player.play(url, window_id=wid)

        # v5: Bedienleisten aktivieren. Position und Dauer kommen
        # jetzt im Sekundentakt aus dem Player; die Spurabfrage
        # startet verzögert über den einmaligen Timer.
        if V5_AVAILABLE:
            self.video_controls.set_enabled(True)
            self.video_controls.set_playing(True)
            self.video_controls.set_volume(self.player.volume)
            if hasattr(self.player, "is_muted"):
                self.video_controls.set_muted(self.player.is_muted())
            self.audio_subtitle_bar.set_enabled(True)
            self._tracks_versuche = 0
            self._tracks_timer.start(1000)

    def _toggle_play(self):
        """Play/Pause umschalten — echtes Pausieren, kein Neustart des Stroms.

        Der Strom bleibt geladen; ein Film springt bei „weiter“ also nicht
        an den Anfang zurück. Der Zielzustand wird vor dem Umschalten gelesen,
        weil libvlc den Befehl asynchron übernimmt und is_paused() unmittelbar
        danach noch den alten Zustand melden würde.
        """
        if not self.player.current_url or not self.player.is_running():
            # Ohne laufende Wiedergabe gibt es nichts umzuschalten
            return
        if hasattr(self.player, "is_paused"):
            ziel_pausiert = not self.player.is_paused()
            self.player.set_paused(ziel_pausiert)
            pausiert = ziel_pausiert
        else:
            # Alter ffplay-Rückfall: pause() ist dort wirkungslos, deshalb
            # wird der gemerkte Zustand manuell gepflegt — ohne Neustart.
            self.player.is_playing = not self.player.is_playing
            pausiert = not self.player.is_playing
        if V5_AVAILABLE:
            self.video_controls.set_playing(not pausiert)

    def _stop_player(self):
        """Player stoppen."""
        self.player.stop()
        self.now_playing_label.setText("Kein Kanal ausgewaehlt")
        self.status_bar.showMessage("Gestoppt")

        # v5: Bedienleisten zurücksetzen und Spurabfrage nicht mehr auslösen
        if V5_AVAILABLE:
            self._tracks_timer.stop()
            self.video_controls.reset()
            self.video_controls.set_enabled(False)
            self.audio_subtitle_bar.reset()
            self.audio_subtitle_bar.set_enabled(False)

    def _on_seek(self, position):
        """v5: Spulbalken losgelassen — absolut auf die gewählte Sekunde springen.

        Der Balken meldet die Zielsekunde; ob das Medium spulbar ist, prüft
        der Player selbst, die Zehnsekundenknöpfe laufen dagegen relativ.
        """
        if hasattr(self.player, "seek_to") and self.player.is_seekable():
            self.player.seek_to(int(position))

    def _on_volume_changed(self, volume):
        """v5: Volume changed via slider."""
        self.player.set_volume(volume)

    def _toggle_mute(self):
        """v5: Stummschaltung umschalten und das Lautsprechersymbol nachziehen."""
        self.player.mute()
        if V5_AVAILABLE and hasattr(self.player, "is_muted"):
            self.video_controls.set_muted(self.player.is_muted())

    def _lade_spuren_vom_player(self):
        """v5: Ton- und Untertitelspuren vom Player abfragen, Felder füllen.

        Der einmalige QTimer ruft diese Methode etwa eine Sekunde nach dem
        Kanalstart im Bedienfaden auf; libvlc hat das Medium dann meist
        ausgewertet. Die Abfrage blockiert die Oberfläche dadurch nicht.
        Meldet der Player noch keine Tonspur, wird der Timer bis zu fünfmal
        erneut gestartet, bevor die Felder im Grundzustand bleiben.
        """
        if not (V5_AVAILABLE and self.player.is_playing and self.player.is_running()):
            return
        if not hasattr(self.player, "get_audio_tracks"):
            # Alter ffplay-Rückfall: keine Spurabfrage möglich, Felder leer lassen
            return

        ton_spuren = self.player.get_audio_tracks()
        ut_spuren = self.player.get_subtitle_tracks()

        # Noch keine Tonspur erkannt: Mediauswertung offenbar noch nicht weit
        # genug — in einer Sekunde erneut versuchen (höchstens fünfmal).
        if not ton_spuren:
            versuche = getattr(self, "_tracks_versuche", 0) + 1
            self._tracks_versuche = versuche
            if versuche < 5:
                self._tracks_timer.start(1000)
                return

        leiste = self.audio_subtitle_bar

        # Tonspuren eintragen; die Spur-Id reist als Datenfeld mit und wird
        # bei der Auswahl wieder an set_audio_track übergeben.
        leiste.audio_combo.blockSignals(True)
        leiste.audio_combo.clear()
        for spur_id, name in ton_spuren:
            leiste.audio_combo.addItem(name or f"Spur {spur_id}", str(spur_id))
        if leiste.audio_combo.count() == 0:
            leiste.audio_combo.addItem("Standard", "default")
        leiste.audio_combo.blockSignals(False)

        # Untertitelspuren eintragen; die Id -1 ist der Eintrag „Aus“.
        leiste.subtitle_combo.blockSignals(True)
        leiste.subtitle_combo.clear()
        for spur_id, name in ut_spuren:
            leiste.subtitle_combo.addItem(name or f"UT {spur_id}", str(spur_id))
        if leiste.subtitle_combo.count() == 0:
            leiste.subtitle_combo.addItem("Aus", "off")
        leiste.subtitle_combo.blockSignals(False)

        logger.info(
            f"Spuren vom Player geladen: {len(ton_spuren)} Tonspuren, "
            f"{len(ut_spuren)} Untertitelspuren"
        )

    def _on_audio_track_changed(self, track_key):
        """v5: Gewählte Tonspur sofort im Player aktivieren."""
        logger.info(f"Audio track changed: {track_key}")
        if not hasattr(self.player, "set_audio_track"):
            self.status_bar.showMessage(f"Audio-Spur: {track_key} (erfordert VLC-Backend)", 3000)
            return
        try:
            spur_id = int(track_key)
        except (TypeError, ValueError):
            self.status_bar.showMessage(f"Audio-Spur: {track_key} unbekannt", 3000)
            return
        bezeichnung = self.audio_subtitle_bar.audio_combo.currentText() or track_key
        if self.player.set_audio_track(spur_id):
            self.status_bar.showMessage(f"Audio-Spur: {bezeichnung}", 3000)
        else:
            self.status_bar.showMessage(f"Audio-Spur {bezeichnung} nicht wählbar", 3000)

    def _on_subtitle_changed(self, sub_key):
        """v5: Gewählte Untertitelspur sofort im Player aktivieren."""
        logger.info(f"Subtitle changed: {sub_key}")
        if not hasattr(self.player, "set_subtitle_track"):
            self.status_bar.showMessage(f"Untertitel: {sub_key} (erfordert VLC-Backend)", 3000)
            return
        try:
            spur_id = int(sub_key)
        except (TypeError, ValueError):
            # „off“ oder ein unbekannter Schlüssel bedeuten: Untertitel aus
            self.status_bar.showMessage("Untertitel: Aus", 3000)
            return
        if self.player.set_subtitle_track(spur_id):
            if spur_id == -1:
                self.status_bar.showMessage("Untertitel: Aus", 3000)
            else:
                bezeichnung = self.audio_subtitle_bar.subtitle_combo.currentText() or f"Spur {spur_id}"
                self.status_bar.showMessage(f"Untertitel: {bezeichnung}", 3000)
        else:
            self.status_bar.showMessage(f"Untertitel-Spur {spur_id} nicht wählbar", 3000)

    def _on_subtitle_delay(self, delay_ms):
        """v5: Untertitel-Verzögerung unmittelbar an den Player durchreichen."""
        logger.info(f"Subtitle delay: {delay_ms}ms")
        if hasattr(self.player, "set_subtitle_delay"):
            self.player.set_subtitle_delay(delay_ms)

    def _refresh_playlist(self):
        """Playlist aktualisieren."""
        if self.current_provider_id:
            self._load_playlist(self.current_provider_id)

    def _open_youtube(self):
        """YouTube im Browser oeffnen (Suche oder URL)."""
        import subprocess
        import urllib.parse
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "YouTube", "Suchbegriff oder URL eingeben:")
        if ok and text:
            text = text.strip()
            if text.startswith("http"):
                url = text
            else:
                url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(text)
            try:
                subprocess.Popen(["xdg-open", url],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                self.status_bar.showMessage("YouTube im Browser geoeffnet", 3000)
            except Exception as e:
                QMessageBox.warning(self, "YouTube", f"Fehler beim Oeffnen: {e}")

    def _play_youtube_url(self):
        """YouTube URL abspielen."""
        self._open_youtube()

    def _open_netflix(self):
        """Netflix im Browser oeffnen."""
        from PyQt5.QtWidgets import QInputDialog
        url, ok = QInputDialog.getText(self, "Netflix", "Netflix URL eingeben (oder leer fuer Startseite):", text="https://www.netflix.com")
        if ok and url:
            self.player.open_netflix(url)
            self.status_bar.showMessage(f"Netflix geoeffnet: {url}", 3000)

    def _check_player(self):
        """Player-Status prüfen — Position und Dauer kommen aus dem Player.

        Der Taktgeber läuft jede Sekunde. Bei Live ohne Dauer meldet
        get_position() die Dauer 0, die Anzeige zeigt dann nur die
        verstrichene Zeit.
        """
        # Wiedergabe hat geendet oder ist fehlgeschlagen: Leisten zurücksetzen
        if self.player.is_playing and not self.player.is_running():
            self.player.is_playing = False
            if V5_AVAILABLE:
                self.video_controls.reset()
                self.video_controls.set_enabled(False)
                self.audio_subtitle_bar.reset()
                self.audio_subtitle_bar.set_enabled(False)

        # v5: Echte Position und Dauer aus dem Player in die Leiste schreiben
        if V5_AVAILABLE and self.player.is_playing and self.player.is_running():
            if hasattr(self.player, "get_position"):
                position, dauer = self.player.get_position()
                self.video_controls.set_position(position, dauer)
            # Nicht spulbare Ströme: Spulbalken und Zehnsekundenknöpfe
            # ausgrauen, statt Klicks wirkungslos laufen zu lassen
            spulbar = self.player.is_seekable() if hasattr(self.player, "is_seekable") else False
            self.video_controls.set_seekable(spulbar)

        # Die schwebende Vollbildleiste bekommt denselben Stand wie die feste.
        if self._vollbild_aktiv and self._vollbild_leiste is not None and self._vollbild_leiste.isVisible():
            try:
                jetzt, dauer = (self.player.get_position()
                                if hasattr(self.player, "get_position") else (0, 0))
                stumm = self.player.is_muted() if hasattr(self.player, "is_muted") else False
                spielt = not (self.player.is_paused() if hasattr(self.player, "is_paused") else False)
                self._vollbild_leiste.stand(jetzt, dauer, spielt, stumm,
                                            getattr(self.player, "volume", 50),
                                            self.now_playing_label.text())
            except Exception as e:
                logger.debug(f"Stand der Vollbildleiste nicht lesbar: {e}")

    def _check_fd_usage(self):
        """Prueft die Anzahl offener File-Descriptors und reagiert bei kritischen Werten."""
        try:
            fd_count = len(os.listdir('/proc/self/fd'))
        except Exception as e:
            self._fd_logger.debug(f"FD-Count nicht ermittelbar: {e}")
            return

        self._fd_logger.debug(f"Offene FDs: {fd_count}")

        if fd_count > self._fd_critical_threshold:
            self._fd_logger.critical(
                f"FD-CRITICAL: {fd_count} offene File-Descriptors (>{self._fd_critical_threshold})! "
                "App-Neustart wird empfohlen."
            )
            self.status_bar.showMessage(
                f"\u26a0 {fd_count} FDs offen — Neustart empfohlen!", 10000
            )
            if not self._fd_warning_logged:
                self._fd_warning_logged = True
                from PyQt5.QtWidgets import QMessageBox as QMB
                QMB.warning(
                    self, "File-Descriptor-Kritisch",
                    f"Die App hat {fd_count} offene File-Descriptors.\n"
                    "Ein Absturz durch EMFILE ist wahrscheinlich.\n\n"
                    "Bitte starten Sie die App neu."
                )

        elif fd_count > self._fd_warning_threshold:
            self._fd_logger.warning(
                f"FD-WARNING: {fd_count} offene File-Descriptors (>{self._fd_warning_threshold}). "
                "Triggering QThread/Connection-Cleanup."
            )
            self.status_bar.showMessage(
                f"\u26a0 {fd_count} FDs offen — Cleanup aktiv", 5000
            )
            self._fd_warning_logged = False
            self._cleanup_leaking_threads()
        else:
            if self._fd_warning_logged:
                self._fd_warning_logged = False

    def _cleanup_leaking_threads(self):
        """Bereinigt potentiell leckende QThreads und Connections."""
        try:
            if hasattr(self, 'load_thread') and self.load_thread.isFinished():
                try:
                    self.load_thread.deleteLater()
                except Exception:
                    pass
                self.load_thread = None
                self._fd_logger.info("LoadPlaylistThread cleanup durchgefuehrt")
        except Exception as e:
            self._fd_logger.debug(f"Thread cleanup error: {e}")

    # =========================================================================
    # INLINE TAB SWITCHING (replaces modal dialog methods)
    # =========================================================================

    def _open_settings(self):
        """Einstellungen Tab oeffnen (inline, nicht modal)."""
        self.content_tabs.setCurrentIndex(TAB_EINSTELLUNGEN)
        if not self._settings_initialized:
            self._init_settings_tab()

    def _open_series_browser(self):
        """Serien Tab oeffnen (inline, nicht modal)."""
        self.content_tabs.setCurrentIndex(TAB_SERIEN)
        if not self._series_initialized:
            self._init_series_tab()

    def _open_series_browser_for_series(self, series_name, series_url):
        """Serien Tab oeffnen fuer eine spezifische Serie (inline, nicht modal)."""
        self._pending_series_name = series_name
        self._pending_series_url = series_url
        self.content_tabs.setCurrentIndex(TAB_SERIEN)
        if not self._series_initialized:
            self._init_series_tab()
        # Note: SeriesBrowser loads all series; user can find the specific one.
        # Future enhancement: auto-select series_name in the browser.
        self.status_bar.showMessage(f"Serien-Browser geoeffnet — suche: {series_name}", 3000)

    def _open_vod_browser(self):
        """Filme Tab oeffnen (inline, nicht modal)."""
        self.content_tabs.setCurrentIndex(TAB_FILME)
        if not self._vod_initialized:
            self._init_vod_tab()

    def _open_global_search(self):
        """Suche Tab oeffnen (inline, nicht modal)."""
        self.content_tabs.setCurrentIndex(TAB_SUCHE)
        if not self._search_initialized:
            self._init_search_tab()

    def _open_catchup(self):
        """Catch-up / Replay — non-modal window (nicht blockierend)."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "v4", "Catch-up Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            QMessageBox.information(self, "Catch-up", "Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider or provider[2] != "xtream":
                QMessageBox.information(self, "Catch-up", "Catch-up benoetigt einen Xtream Codes Provider.")
                return
            api = XtreamAPI(provider[3], provider[4], provider[5])
            catchup_mgr = CatchupManager(api)
            dialog = CatchupDialog(catchup_mgr, parent=self)
            dialog.setModal(False)
            dialog.show()
        except Exception as e:
            QMessageBox.warning(self, "Catch-up", f"Fehler: {e}")

    # =========================================================================
    # v2 METHODS
    # =========================================================================

    def _toggle_epg(self):
        """EPG anzeigen/ausblenden."""
        if not V2_AVAILABLE:
            QMessageBox.information(self, "v2", "EPG Modul nicht verfuegbar.")
            return
        if not hasattr(self, "epg_widget"):
            QMessageBox.information(self, "EPG", "EPG-Widget wird beim naechsten Kanal-Klick initialisiert.")
            return
        if self.epg_widget.isVisible():
            self.epg_widget.hide()
            self.status_bar.showMessage("EPG ausgeblendet", 2000)
        else:
            self.epg_widget.show()
            self.status_bar.showMessage("EPG angezeigt", 2000)

    def _show_favorites(self):
        """Favoriten anzeigen."""
        self.category_list.clear()
        item = QListWidgetItem("< Favoriten >")
        item.setData(Qt.UserRole, "__favorites__")
        self.category_list.addItem(item)
        cats = self.config.get_categories(self.current_provider_id)
        for cat in cats:
            if cat:
                item = QListWidgetItem(cat)
                item.setData(Qt.UserRole, cat)
                self.category_list.addItem(item)
        self._load_favorites()

    def _load_favorites(self):
        """Favoriten in Kanal-Liste laden."""
        self.channel_list.clear()
        favs = self.config.get_favorites()
        self.channels = favs
        for ch in favs:
            ch_id, _, name, url, logo, cat, tvg_id, tvg_name, ch_type = ch
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, ch_id)
            item.setToolTip(f"{name}\nKategorie: {cat}\nTyp: {ch_type}")
            self.channel_list.addItem(item)
        self.status_bar.showMessage(f"{len(favs)} Favoriten", 2000)

    def _on_channel_click(self, item):
        """Kanal angeklickt."""
        ch_id = item.data(Qt.UserRole)
        if ch_id is None:
            return
        # Einzelabruf über den Primärschlüssel statt aller Kanäle
        # (gleiche Spaltenreihenfolge wie bisher, nur schneller)
        ch = self.config.get_channel(ch_id)
        if not ch:
            return
        self.now_playing_label.setText(f"Jetzt: {ch[2]}")
        # v2: EPG für Live-Kanäle im Hintergrund laden (nicht blockierend)
        if V2_AVAILABLE and ch[8] == "live" and self.current_provider_id:
            provider = self.config.get_provider(self.current_provider_id)
            if provider and provider[2] == "xtream":
                tvg_id = ch[6]
                if tvg_id:
                    self._starte_epg_abruf(ch[2], tvg_id, provider)

    def _starte_epg_abruf(self, kanalname, tvg_id, provider):
        """EPG-Abruf im kurzlebigen Hintergrundfaden starten.

        Der Bedienfaden bleibt frei; die Statuszeile zeigt den Ladezustand.
        Ein bereits laufender Abruf wird abgebrochen und sicher entsorgt.
        """
        try:
            # Bereits laufenden EPG-Abruf ersetzen (Signale lösen, dann entsorgen)
            if getattr(self, "_epg_thread", None) is not None:
                try:
                    self._epg_thread.epg_geladen.disconnect(self._on_epg_geladen)
                except (TypeError, RuntimeError):
                    pass
                self._thread_sicher_entsorgen(self._epg_thread, "EpgAbrufThread")
                self._epg_thread = None
            self._epg_thread = EpgAbrufThread(
                provider[3], provider[4], provider[5], tvg_id, kanalname
            )
            self._epg_thread.epg_geladen.connect(self._on_epg_geladen)
            self.status_bar.showMessage("EPG wird geladen...")
            self._epg_thread.start()
        except Exception as e:
            # Start darf die Oberfläche niemals stören
            self._epg_thread = None
            logger.warning(f"EPG-Abruf für '{kanalname}' konnte nicht gestartet werden: {e}")
            self.status_bar.showMessage("EPG wird nicht geladen", 3000)

    def _on_epg_geladen(self, epg_daten, kanalname):
        """EPG-Ergebnis aus dem Hintergrundfaden übernehmen."""
        try:
            if epg_daten:
                # EpgEntry ist ein Objekt mit Attributen (kein Dictionary)
                titel = getattr(epg_daten[0], "title", "") or ""
                if titel:
                    self.now_playing_label.setText(f"Jetzt: {kanalname} | {titel}")
                self.status_bar.showMessage("EPG geladen", 2000)
            else:
                # Fehler oder Zeitüberschreitung: stille Statusmeldung, kein Dialog
                self.status_bar.showMessage("EPG nicht verfügbar", 3000)
        except Exception as e:
            logger.warning(f"Anzeige des EPG-Ergebnisses für '{kanalname}' fehlgeschlagen: {e}")
            self.status_bar.showMessage("EPG nicht verfügbar", 3000)
        finally:
            # Faden gehört zu diesem Abruf und ist praktisch immer bereits beendet
            faden = getattr(self, "_epg_thread", None)
            if faden is not None:
                self._thread_sicher_entsorgen(faden, "EpgAbrufThread")
                self._epg_thread = None

    # =========================================================================
    # v3 METHODS
    # =========================================================================

    def _toggle_pip(self):
        """Bild-im-Bild Fenster umschalten."""
        if not V3_AVAILABLE:
            QMessageBox.information(self, "v3", "PiP Modul nicht verfuegbar.")
            return
        if hasattr(self, "pip_window") and self.pip_window.isVisible():
            self.pip_window.stop_video()
            self.pip_window.hide()
            self.status_bar.showMessage("PiP geschlossen", 2000)
        else:
            try:
                self.pip_window = PIPWindow(backend=self.player, parent=None)
                self.pip_window.show()
                if self.player.current_url:
                    self.pip_window.start_video(self.player.current_url)
                self.status_bar.showMessage("PiP geoeffnet", 2000)
            except Exception as e:
                QMessageBox.warning(self, "PiP", f"Fehler: {e}")

    def _load_subtitle(self):
        """Untertitel-Datei laden."""
        if not V3_AVAILABLE:
            QMessageBox.information(self, "v3", "Untertitel-Modul nicht verfuegbar.")
            return
        try:
            from PyQt5.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                self, "Untertitel laden", "",
                "Untertitel (*.srt *.vtt *.ass *.ssa);;Alle Dateien (*)"
            )
            if path:
                if not hasattr(self, "subtitle_mgr"):
                    self.subtitle_mgr = SubtitleManager()
                self.subtitle_mgr.subtitle_file = path
                # Geladene Untertiteldatei sofort an den Player durchreichen;
                # läuft schon ein Medium, wird sie direkt angehängt, sonst
                # beim nächsten Start.
                if hasattr(self.player, "set_subtitle_file"):
                    self.player.set_subtitle_file(path)
                self.status_bar.showMessage(f"Untertitel: {os.path.basename(path)}", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Untertitel", f"Fehler: {e}")

    def _toggle_recording(self):
        """Aufnahme starten/stoppen."""
        if not V3_AVAILABLE:
            QMessageBox.information(self, "v3", "Aufnahme-Modul nicht verfuegbar.")
            return
        try:
            if not hasattr(self, "recording_mgr"):
                self.recording_mgr = RecordingManager()
            if self.recording_mgr.is_recording():
                self.recording_mgr.stop_recording()
                self.status_bar.showMessage("Aufnahme gestoppt", 3000)
            else:
                if self.player.current_url:
                    self.recording_mgr.start_recording(self.player.current_url)
                    self.status_bar.showMessage("Aufnahme gestartet", 3000)
                else:
                    QMessageBox.information(self, "Aufnahme", "Bitte zuerst einen Kanal abspielen.")
        except Exception as e:
            QMessageBox.warning(self, "Aufnahme", f"Fehler: {e}")

    def _toggle_auto_refresh(self):
        """Auto-Refresh aktivieren/deaktivieren."""
        if not V3_AVAILABLE:
            QMessageBox.information(self, "v3", "Auto-Refresh Modul nicht verfuegbar.")
            return
        try:
            if not hasattr(self, "auto_refresh_mgr"):
                hours = int(self.config.get_setting("playlist_refresh_hours", 24))
                self.auto_refresh_mgr = AutoRefreshManager(self)
                self.auto_refresh_mgr.set_interval(hours)
                self.auto_refresh_mgr.refresh_success.connect(
                    lambda d: self.status_bar.showMessage(f"Auto-Refresh: {d.get('channels', 0)} Kanaele aktualisiert", 5000)
                )
                self.auto_refresh_mgr.refresh_error.connect(
                    lambda e: self.status_bar.showMessage(f"Auto-Refresh Fehler: {e}", 5000)
                )
            if self.auto_refresh_mgr.enabled:
                self.auto_refresh_mgr.stop()
                self.status_bar.showMessage("Auto-Refresh deaktiviert", 3000)
            else:
                self.auto_refresh_mgr.start()
                self.status_bar.showMessage("Auto-Refresh aktiviert", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Auto-Refresh", f"Fehler: {e}")

    # =========================================================================
    # v4 METHODS
    # =========================================================================

    def _open_cast(self):
        """DLNA/Chromecast Cast Dialog oeffnen."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "v4", "Cast Modul nicht verfuegbar.")
            return
        try:
            if not hasattr(self, "cast_widget"):
                self.cast_widget = CastWidget(parent=self)
            if self.player.current_url:
                self.cast_widget.setStyleSheet("")
            self.cast_widget.show()
            self.status_bar.showMessage("Cast: Suche DLNA-Geraete...", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Cast", f"Fehler: {e}")

    def _toggle_remote_control(self):
        """Web Remote Control Server starten/stoppen."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "v4", "Remote Control Modul nicht verfuegbar.")
            return
        try:
            if not hasattr(self, "remote_controller"):
                self.remote_controller = RemoteControlController()
                self.remote_controller.play_requested.connect(lambda: self.player.play(self.player.current_url, int(self.video_container.winId())) if self.player.current_url else None)
                self.remote_controller.pause_requested.connect(self.player.pause)
                self.remote_controller.stop_requested.connect(self._stop_player)
                self.remote_controller.volume_requested.connect(self.player.set_volume)
            if hasattr(self, "remote_widget") and self.remote_widget.isVisible():
                self.remote_widget.close()
                self.status_bar.showMessage("Remote Control gestoppt", 3000)
            else:
                self.remote_widget = RemoteControlWidget(self.remote_controller, parent=self)
                self.remote_widget.start_server()
                self.remote_widget.show()
                self.status_bar.showMessage("Remote Control gestartet (Port 8420)", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Remote Control", f"Fehler: {e}")

    def _switch_profile(self):
        """Profil wechseln Dialog."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "v4", "Multi-Profile Modul nicht verfuegbar.")
            return
        try:
            from PyQt5.QtWidgets import QInputDialog
            providers = self.config.get_providers()
            if not providers:
                QMessageBox.information(self, "Profile", "Keine Provider vorhanden. Bitte zuerst einen Provider hinzufuegen.")
                return
            items = [f"{p[1]} ({p[2]})" for p in providers]
            item, ok = QInputDialog.getItem(self, "Profil wechseln", "Provider auswaehlen:", items, 0, False)
            if ok and item:
                idx = items.index(item)
                pid = providers[idx][0]
                self.current_provider_id = pid
                self.provider_combo.setCurrentIndex(idx + 1)
                self._load_playlist(pid)
                self.status_bar.showMessage(f"Profil gewechselt: {providers[idx][1]}", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Profile", f"Fehler: {e}")

    def _toggle_mini_player(self):
        """Mini Player umschalten."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "v4", "Mini Player Modul nicht verfuegbar.")
            return
        try:
            if hasattr(self, "mini_player") and self.mini_player.isVisible():
                self.mini_player.stop_video()
                self.mini_player.hide()
                self.status_bar.showMessage("Mini Player geschlossen", 2000)
            else:
                self.mini_player = MiniPlayer(backend=self.player, parent=None)
                self.mini_player.show()
                if self.player.current_url:
                    self.mini_player.start_video(self.player.current_url)
                self.status_bar.showMessage("Mini Player geoeffnet", 2000)
        except Exception as e:
            QMessageBox.warning(self, "Mini Player", f"Fehler: {e}")

    def _show_epg_timeline(self):
        """EPG Timeline anzeigen."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "v4", "EPG Timeline Modul nicht verfuegbar.")
            return
        try:
            if not hasattr(self, "epg_timeline_widget"):
                self.epg_timeline_widget = EpgTimelineWidget(parent=self)
            # Die Programmzeitschrift gehört zu Live-Kanälen; Filme und Serien
            # haben kein Sendeschema und werden deshalb herausgefiltert.
            channels = self.config.get_channels(
                provider_id=self.current_provider_id,
                type="live"
            )
            self.epg_timeline_widget.set_channels(channels)
            self.epg_timeline_widget.show()
            self.status_bar.showMessage("EPG Timeline geoeffnet", 2000)
        except Exception as e:
            QMessageBox.warning(self, "EPG Timeline", f"Fehler: {e}")

    # =========================================================================
    # EVENT FILTER / CLOSE
    # =========================================================================

    def eventFilter(self, obj, event):
        """Maus auf dem Videobild: Doppelklick schaltet das Vollbild um.

        Gespult wird ueber die Knoepfe und die Pfeiltasten, nicht mehr ueber
        den Doppelklick. Der Doppelklick ist der Weg zurueck aus dem Vollbild
        in die kleine Wiedergabe, ohne dass das Bild abreisst.
        """
        if obj == self.video_container:
            if event.type() == QEvent.MouseButtonDblClick:
                self._vollbild_umschalten()
                return True
            if event.type() == QEvent.MouseMove and self._vollbild_aktiv:
                self._leiste_zeigen()
        return super().eventFilter(obj, event)


    # ==================================================================
    # Vollbild: grosse Bedienung, Zappen im laufenden Betrieb
    # ==================================================================
    # Das Videobild liegt in einem eingebetteten X11-Fenster. Wuerde man es
    # umhaengen, verlaengert sich seine Fenster-Kennung und libvlc malt ins
    # Leere: das Bild reisst ab. Deshalb bleibt das Videofenster an seinem
    # Platz und stattdessen werden alle GESCHWISTER versteckt. So laeuft das
    # Bild beim Wechsel ohne Stocken weiter.

    def _ist_vorfahre_des_videos(self, widget):
        """Liegt das Videobild innerhalb dieses Widgets?"""
        knoten = self.video_container
        while knoten is not None:
            if knoten is widget:
                return True
            knoten = knoten.parentWidget()
        return False

    def _vollbild_umschalten(self):
        if self._vollbild_aktiv:
            self._vollbild_aus()
        else:
            self._vollbild_an()

    def _vollbild_an(self):
        if self._vollbild_aktiv:
            return
        versteckt = []

        def verstecke(widget):
            if widget is not None and widget is not self.video_container and widget.isVisible():
                widget.hide()
                versteckt.append(widget)

        # Geschwister innerhalb des Playerbereichs (Kopfzeile, Bedienleiste, Titel)
        layout = self.player_widget.layout() if hasattr(self, "player_widget") else None
        if layout is not None:
            for i in range(layout.count()):
                verstecke(layout.itemAt(i).widget())
        # Alles im Hauptfenster, was das Videobild nicht enthaelt
        zentral = self.centralWidget()
        if zentral is not None and zentral.layout() is not None:
            haupt = zentral.layout()
            for i in range(haupt.count()):
                w = haupt.itemAt(i).widget()
                if w is not None and not self._ist_vorfahre_des_videos(w):
                    verstecke(w)
        verstecke(self.content_tabs)
        verstecke(self.menuBar())
        verstecke(self.statusBar())

        self._vollbild_versteckt = versteckt
        self._vollbild_war_maximiert = self.isMaximized()
        self._vollbild_aktiv = True
        self.showFullScreen()

        if self._vollbild_leiste is None:
            self._vollbild_leiste = VollbildLeiste(self)
            self._vollbild_leiste.beenden.connect(self._vollbild_aus)
            self._vollbild_leiste.pause_um.connect(self._vollbild_pause)
            self._vollbild_leiste.stopp.connect(self._vollbild_stopp)
            self._vollbild_leiste.springen.connect(self._vollbild_springen)
            self._vollbild_leiste.suchen_zu.connect(self._vollbild_suchen_zu)
            self._vollbild_leiste.stumm_um.connect(self._vollbild_stumm)
            self._vollbild_leiste.lautstaerke.connect(self._vollbild_lautstaerke)
            self._vollbild_leiste.zappliste_um.connect(self._zappliste_umschalten)
            self._vollbild_leiste.kanal_weiter.connect(self._zappe_um)
        if not hasattr(self, "_leiste_timer"):
            self._leiste_timer = QTimer(self)
            self._leiste_timer.setSingleShot(True)
            self._leiste_timer.timeout.connect(self._leiste_verbergen)
        self._leiste_zeigen()
        self.setFocus()
        self.status_bar.showMessage("Vollbild: Doppelklick oder Escape zurueck, L fuer die Kanalliste", 4000)

    def _vollbild_aus(self):
        if not self._vollbild_aktiv:
            return
        self._vollbild_aktiv = False
        if self._vollbild_leiste is not None:
            self._vollbild_leiste.hide()
        if self._zappliste is not None:
            self._zappliste.hide()
        if hasattr(self, "_leiste_timer"):
            self._leiste_timer.stop()
        for widget in self._vollbild_versteckt:
            try:
                widget.show()
            except RuntimeError:
                pass
        self._vollbild_versteckt = ()
        if self._vollbild_war_maximiert:
            self.showMaximized()
        else:
            self.showNormal()

    # --- Einblenden und Ausblenden der schwebenden Leiste ---

    def _leiste_zeigen(self):
        if not self._vollbild_aktiv or self._vollbild_leiste is None:
            return
        self._vollbild_leiste.platziere(self.geometry())
        self._vollbild_leiste.show()
        self._vollbild_leiste.raise_()
        self._leiste_timer.start(4000)

    def _leiste_verbergen(self):
        # Solange die Kanalliste offen ist, bleibt auch die Leiste stehen.
        if self._zappliste is not None and self._zappliste.isVisible():
            self._leiste_timer.start(4000)
            return
        if self._vollbild_leiste is not None:
            self._vollbild_leiste.hide()

    # --- Bedienbefehle aus der schwebenden Leiste ---

    def _vollbild_pause(self):
        try:
            if hasattr(self.player, "pause"):
                self.player.pause()
        except Exception as e:
            logger.warning(f"Pause im Vollbild fehlgeschlagen: {e}")
        self._leiste_zeigen()

    def _vollbild_stopp(self):
        try:
            self.player.stop()
        except Exception as e:
            logger.warning(f"Stopp im Vollbild fehlgeschlagen: {e}")
        self._vollbild_aus()

    def _vollbild_springen(self, sekunden):
        try:
            if hasattr(self.player, "seek_relative"):
                self.player.seek_relative(sekunden)
        except Exception as e:
            logger.warning(f"Spulen im Vollbild fehlgeschlagen: {e}")
        self._leiste_zeigen()

    def _vollbild_suchen_zu(self, sekunde):
        try:
            if hasattr(self.player, "seek_to"):
                self.player.seek_to(int(sekunde))
        except Exception as e:
            logger.warning(f"Springen im Vollbild fehlgeschlagen: {e}")
        self._leiste_zeigen()

    def _vollbild_stumm(self):
        try:
            if hasattr(self.player, "set_muted"):
                self.player.set_muted(not self.player.is_muted())
            elif hasattr(self.player, "mute"):
                self.player.mute()
        except Exception as e:
            logger.warning(f"Stummschalten im Vollbild fehlgeschlagen: {e}")
        self._leiste_zeigen()

    def _vollbild_lautstaerke(self, wert):
        try:
            self.player.set_volume(int(wert))
        except Exception as e:
            logger.warning(f"Lautstaerke im Vollbild fehlgeschlagen: {e}")

    # --- Zappen: Kanalliste ueber dem laufenden Bild ---

    def spiele_in_videoflaeche(self, url, titel, folgen=None, index=-1):
        """Spielt eine Adresse in der Videoflaeche der App ab.

        Der Serienbrowser rief bisher player.play(url) OHNE Fensterkennung.
        Dann oeffnet libvlc ein eigenes Fenster: die Folge lief ausserhalb der
        App, war im Vollbild nicht sichtbar und ueber die Bedienleiste nicht
        steuerbar. Mit dieser Methode landet sie in derselben Flaeche wie ein
        Kanal, und die uebergebene Staffel wird zum Zappen gemerkt.
        """
        wid = int(self.video_container.winId())
        erfolg = self.player.play(url, window_id=wid)
        if not erfolg:
            self.status_bar.showMessage("Wiedergabe fehlgeschlagen", 5000)
            return False
        self.now_playing_label.setText(f"Spielt: {titel}")
        self.status_bar.showMessage(f"Spiele {titel}...", 4000)
        self._folgenreihe = list(folgen or ())
        self._folgen_index = index
        if V5_AVAILABLE:
            self.video_controls.set_enabled(True)
            self.video_controls.set_playing(True)
            self.video_controls.set_volume(self.player.volume)
            if hasattr(self.player, "is_muted"):
                self.video_controls.set_muted(self.player.is_muted())
            self.audio_subtitle_bar.set_enabled(True)
            self._tracks_versuche = 0
            self._tracks_timer.start(1000)
        if self._vollbild_leiste is not None:
            self._vollbild_leiste.titel.setText(titel[:60])
        return True

    def _spiele_folge(self, index):
        """Spielt die Folge mit dieser Nummer aus der gemerkten Staffel."""
        reihe = self._folgenreihe
        if not (0 <= index < len(reihe)):
            return False
        folge = reihe[index]
        return self.spiele_in_videoflaeche(
            folge.get("url", ""), folge.get("titel", ""), reihe, index)

    def _zappliste_umschalten(self):
        if self._zappliste is not None and self._zappliste.isVisible():
            self._zappliste.hide()
            self.setFocus()
            return
        if self._zappliste is None:
            self._zappliste = ZappListe(self)
            self._zappliste.gewaehlt.connect(self._zappe_zu)
            self._zappliste.schliessen.connect(self._zappliste_umschalten)
        if self._folgenreihe:
            namen = [f.get("titel", "") for f in self._folgenreihe]
            self._zappliste.fuellen(namen, self._folgen_index)
        else:
            namen = [self.channel_list.item(i).text() for i in range(self.channel_list.count())]
            self._zappliste.fuellen(namen, self.channel_list.currentRow())
        self._zappliste.platziere(self.geometry())
        self._zappliste.show()
        self._zappliste.raise_()
        self._zappliste.filter.setFocus()
        self._leiste_zeigen()

    def _zappe_zu(self, zeile):
        """Auf eine Folge oder einen Kanal umschalten, ohne das Vollbild zu verlassen."""
        if self._folgenreihe:
            if self._spiele_folge(zeile):
                self._leiste_zeigen()
            return
        if not (0 <= zeile < self.channel_list.count()):
            return
        eintrag = self.channel_list.item(zeile)
        if eintrag is None or eintrag.data(Qt.UserRole) is None:
            return
        self.channel_list.setCurrentRow(zeile)
        self._play_channel(eintrag)
        if self._vollbild_leiste is not None:
            self._vollbild_leiste.titel.setText(eintrag.text()[:60])
        self._leiste_zeigen()

    def _zappe_um(self, richtung):
        """Eine Folge oder einen Kanal weiter, je nachdem was gerade laeuft.

        Uebersprungen werden Hinweiszeilen ohne Kennung und Kanaele, zu denen
        die Datenbank keinen Eintrag mehr hat. Ohne diese zweite Pruefung
        bliebe das Zappen an einer toten Zeile haengen und das Bild stuende.
        Die Suche bricht nach 60 Zeilen ab, damit sie nie die ganze Liste
        durchmisst.
        """
        # Laeuft eine Serienstaffel, wird durch ihre Folgen gezappt.
        if self._folgenreihe:
            ziel = self._folgen_index + richtung
            if ziel < 0:
                self.status_bar.showMessage("Das ist bereits die erste Folge", 3000)
                return
            if ziel >= len(self._folgenreihe):
                self.status_bar.showMessage("Das war die letzte Folge der Staffel", 3000)
                return
            if self._spiele_folge(ziel):
                if self._zappliste is not None and self._zappliste.isVisible():
                    self._zappliste.liste.setCurrentRow(ziel)
                self._leiste_zeigen()
            return

        anzahl = self.channel_list.count()
        if anzahl == 0:
            return
        zeile = self.channel_list.currentRow()
        if zeile < 0:
            zeile = 0
        for _ in range(min(anzahl, 60)):
            zeile = (zeile + richtung) % anzahl
            eintrag = self.channel_list.item(zeile)
            if eintrag is None:
                continue
            kennung = eintrag.data(Qt.UserRole)
            if kennung is None:
                continue
            try:
                if not self.config.get_channel(kennung):
                    continue
            except Exception as e:
                logger.debug(f"Kanalpruefung beim Zappen fehlgeschlagen: {e}")
                continue
            self._zappe_zu(zeile)
            return
        self.status_bar.showMessage("Kein abspielbarer Kanal in der Naehe gefunden", 3000)

    def keyPressEvent(self, ereignis):
        """Tastatur im Vollbild. Ausserhalb des Vollbilds nur F11 und F."""
        taste = ereignis.key()
        if taste in (Qt.Key_F11,) or (taste == Qt.Key_F and not self._vollbild_aktiv):
            self._vollbild_umschalten()
            return
        if self._vollbild_aktiv:
            if taste in (Qt.Key_Escape, Qt.Key_F):
                self._vollbild_aus()
                return
            if taste == Qt.Key_Space:
                self._vollbild_pause()
                return
            if taste == Qt.Key_Left:
                self._vollbild_springen(-10)
                return
            if taste == Qt.Key_Right:
                self._vollbild_springen(10)
                return
            if taste == Qt.Key_Up:
                self._zappe_um(-1)
                return
            if taste == Qt.Key_Down:
                self._zappe_um(1)
                return
            if taste in (Qt.Key_L, Qt.Key_K):
                self._zappliste_umschalten()
                return
            if taste == Qt.Key_M:
                self._vollbild_stumm()
                return
            if taste in (Qt.Key_Plus, Qt.Key_Equal):
                self._vollbild_lautstaerke(min(100, int(getattr(self.player, "volume", 50)) + 5))
                self._leiste_zeigen()
                return
            if taste == Qt.Key_Minus:
                self._vollbild_lautstaerke(max(0, int(getattr(self.player, "volume", 50)) - 5))
                self._leiste_zeigen()
                return
        super().keyPressEvent(ereignis)

    def changeEvent(self, ereignis):
        """Haelt das Vollbild gegen den Fenstermanager.

        Manche Fenstermanager heben den Vollbildzustand auf, sobald das Fenster
        den Tastaturfokus verliert. Genau das passiert, wenn die schwebende
        Zappliste den Fokus fuer ihr Suchfeld nimmt. Solange der Nutzer das
        Vollbild will, wird es deshalb sofort wiederhergestellt. Minimieren
        bleibt erlaubt, sonst liesse sich das Fenster nicht mehr weglegen.
        """
        if (ereignis.type() == QEvent.WindowStateChange
                and self._vollbild_aktiv
                and not self.isFullScreen()
                and not self.isMinimized()):
            QTimer.singleShot(0, self.showFullScreen)
        super().changeEvent(ereignis)

    def resizeEvent(self, ereignis):
        """Bildschirmgroesse geaendert: die schwebenden Fenster nachfuehren."""
        super().resizeEvent(ereignis)
        if self._vollbild_aktiv:
            if self._vollbild_leiste is not None and self._vollbild_leiste.isVisible():
                self._vollbild_leiste.platziere(self.geometry())
            if self._zappliste is not None and self._zappliste.isVisible():
                self._zappliste.platziere(self.geometry())

    def mouseMoveEvent(self, ereignis):
        if self._vollbild_aktiv:
            self._leiste_zeigen()
        super().mouseMoveEvent(ereignis)

    def closeEvent(self, event):
        """App schließen — alles Laufende anhalten, ohne eine Ausnahme nach außen.

        Reihenfolge: Player und Timer, Browser schließen, Fäden entsorgen,
        Dienste stoppen, Debug-Server stoppen, begrenzt auf Zombies warten.
        """
        # Schwebende Vollbildfenster zuerst schliessen, sonst bleiben sie stehen
        for schwebend in (self._vollbild_leiste, self._zappliste):
            try:
                if schwebend is not None:
                    schwebend.close()
            except Exception:
                pass
        try:
            # 1. Player stoppen und alle QTimer anhalten
            try:
                self.player.stop()
            except Exception as e:
                logger.warning(f"Stoppen des Players fehlgeschlagen: {e}")
            # libvlc sauber freigeben, falls das Backend release() anbietet
            try:
                if hasattr(self.player, "release"):
                    self.player.release()
            except Exception as e:
                logger.warning(f"Freigeben des Players fehlgeschlagen: {e}")
            for timer_name in ("player_timer", "fd_monitor_timer"):
                try:
                    timer = getattr(self, timer_name, None)
                    if timer is not None:
                        timer.stop()
                except Exception as e:
                    logger.warning(f"Anhalten des Timers {timer_name} fehlgeschlagen: {e}")

            # 2. Browser-Dialoge schließen (hält ihre Hintergrundfäden an)
            for widget_name in ("_vod_widget", "_series_widget", "_search_widget"):
                try:
                    widget = getattr(self, widget_name, None)
                    if widget is not None:
                        widget.close()
                except Exception as e:
                    logger.warning(f"Schließen von {widget_name} fehlgeschlagen: {e}")

            # 3. Lade-Fäden sicher entsorgen (cancel, begrenztes Warten, Zombie-Weg)
            try:
                self._thread_sicher_entsorgen(getattr(self, "load_thread", None), "LoadPlaylistThread")
                self.load_thread = None
            except Exception as e:
                logger.warning(f"Entsorgung des LoadPlaylistThread fehlgeschlagen: {e}")
            try:
                self._thread_sicher_entsorgen(getattr(self, "lazy_thread", None), "LazyLoadThread")
                self.lazy_thread = None
            except Exception as e:
                logger.warning(f"Entsorgung des LazyLoadThread fehlgeschlagen: {e}")
            try:
                self._thread_sicher_entsorgen(getattr(self, "_epg_thread", None), "EpgAbrufThread")
                self._epg_thread = None
            except Exception as e:
                logger.warning(f"Entsorgung des EpgAbrufThread fehlgeschlagen: {e}")

            # 4. Hintergrund-Dienste stoppen
            try:
                if hasattr(self, "pip_window"):
                    self.pip_window.stop_video()
            except Exception as e:
                logger.warning(f"Stoppen des Bild-im-Bild-Fensters fehlgeschlagen: {e}")
            try:
                if hasattr(self, "recording_mgr"):
                    self.recording_mgr.stop_recording()
            except Exception as e:
                logger.warning(f"Stoppen der Aufnahme fehlgeschlagen: {e}")
            try:
                if hasattr(self, "auto_refresh_mgr"):
                    self.auto_refresh_mgr.stop()
            except Exception as e:
                logger.warning(f"Stoppen des Auto-Refresh fehlgeschlagen: {e}")
            try:
                if hasattr(self, "mini_player"):
                    self.mini_player.stop_video()
            except Exception as e:
                logger.warning(f"Stoppen des Mini-Players fehlgeschlagen: {e}")
            try:
                if hasattr(self, "remote_controller"):
                    self.remote_controller.stop_server()
            except Exception as e:
                logger.warning(f"Stoppen der Fernsteuerung fehlgeschlagen: {e}")
            try:
                if hasattr(self, "remote_widget"):
                    self.remote_widget.close()
            except Exception as e:
                logger.warning(f"Schließen des Fernsteuerungsfensters fehlgeschlagen: {e}")
            try:
                if hasattr(self, "cast_widget"):
                    self.cast_widget.close()
            except Exception as e:
                logger.warning(f"Schließen des Cast-Fensters fehlgeschlagen: {e}")

            # 5. Debug-Server stoppen
            try:
                if hasattr(self, "debug_server"):
                    self.debug_server.stop()
            except Exception as e:
                logger.warning(f"Stoppen des Debug-Servers fehlgeschlagen: {e}")

            # 6. Höchstens 3 Sekunden gesamt auf geparkte Fäden warten.
            #    Die Fäden liegen im Fadenpark, sind dort vom Fenster abgenabelt
            #    und können niemanden mehr mit in den Tod reißen. Deshalb wird
            #    nach der Frist nicht weiter blockiert.
            try:
                verbleibend = fadenpark.warte_auf_geparkte(3000)
                if verbleibend:
                    logger.warning(
                        f"{verbleibend} Hintergrundfaden laufen beim Schließen "
                        "noch, sie sind abgenabelt und blockieren nicht"
                    )
            except Exception as e:
                logger.warning(f"Warten auf geparkte Fäden fehlgeschlagen: {e}")
        except Exception as e:
            # closeEvent darf niemals eine Ausnahme nach außen werfen
            logger.error(f"Fehler beim Schließen der Anwendung: {e}", exc_info=True)
        finally:
            event.accept()
