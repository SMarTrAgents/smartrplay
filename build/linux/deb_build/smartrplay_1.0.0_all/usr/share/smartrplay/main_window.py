#!/usr/bin/env python3
"""SMarTrPlay - Main Window (PyQt5 + SMarTr Brand Design)"""

import os
import sys
import threading
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QLineEdit, QPushButton,
    QToolBar, QAction, QStatusBar, QMenu, QTabWidget, QDialog,
    QFormLayout, QComboBox, QMessageBox, QProgressBar, QFrame,
    QScrollArea, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QPixmap, QIcon, QFont, QCursor

from config import Config
from m3u_parser import M3UParser
from xtream_api import XtreamAPI
from player import PlayerBackend
from theme import apply_theme, BG_DEEP, BG_CARD, BG_CARD_HOVER, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT_CYAN, ACCENT_PURPLE, ACCENT_VIOLET

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
    """Thread fuer das Laden von Playlists im Hintergrund."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, provider_type, url, username=None, password=None):
        super().__init__()
        self.provider_type = provider_type
        self.url = url
        self.username = username
        self.password = password

    def run(self):
        try:
            if self.provider_type == "m3u":
                parser = M3UParser()
                channels = parser.parse_url(self.url)
            elif self.provider_type == "xtream":
                api = XtreamAPI(self.url, self.username, self.password)
                channels = api.get_all_channels()
            else:
                channels = []
            self.finished.emit(channels)
        except Exception as e:
            self.error.emit(str(e))


class ChannelListWidget(QListWidget):
    """Custom Channel List Widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUniformItemSizes(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setSpacing(2)


class MainWindow(QMainWindow):
    """SMarTrPlay Hauptfenster."""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.player = PlayerBackend()
        self.current_provider_id = None
        self.current_category = None
        self.channels = []

        self.setWindowTitle("SMarTrPlay - IPTV Player")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 850)

        self._build_ui()
        self._load_providers()

        # Player check timer
        self.player_timer = QTimer(self)
        self.player_timer.timeout.connect(self._check_player)
        self.player_timer.start(1000)

    def _build_ui(self):
        """UI aufbauen."""
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
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

        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Kanaele suchen...")
        self.search_bar.setFixedWidth(260)
        self.search_bar.setFixedHeight(36)
        self.search_bar.textChanged.connect(self._on_search)
        header_layout.addWidget(self.search_bar)

        # Provider selector
        self.provider_combo = QComboBox()
        self.provider_combo.setFixedWidth(200)
        self.provider_combo.setFixedHeight(36)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_change)
        header_layout.addWidget(self.provider_combo)

        # Add Provider Button
        self.btn_add_provider = QPushButton("+ Provider")
        self.btn_add_provider.setFixedHeight(36)
        self.btn_add_provider.clicked.connect(self._add_provider)
        header_layout.addWidget(self.btn_add_provider)

        main_layout.addWidget(header)

        # Content Area (Splitter)
        splitter = QSplitter(Qt.Horizontal)

        # Left Sidebar (Categories)
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

        splitter.addWidget(sidebar_widget)

        # Middle (Channel List)
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
        self.channel_list.itemDoubleClicked.connect(self._play_channel)
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

        splitter.addWidget(channel_widget)

        # Right (Player View)
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
        self.video_container.setStyleSheet(f"background-color: black;")
        self.video_container.setMinimumSize(640, 360)
        player_layout.addWidget(self.video_container, stretch=1)

        # Enable double-click seek on video container
        self.video_container.installEventFilter(self)

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

        # Player Controls
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

        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedHeight(36)
        self.btn_play.clicked.connect(self._toggle_play)
        controls_layout.addWidget(self.btn_play)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.clicked.connect(self._stop_player)
        controls_layout.addWidget(self.btn_stop)

        controls_layout.addStretch()

        self.btn_youtube_play = QPushButton("YouTube URL")
        self.btn_youtube_play.setFixedHeight(36)
        self.btn_youtube_play.clicked.connect(self._play_youtube_url)
        controls_layout.addWidget(self.btn_youtube_play)

        player_layout.addWidget(controls)

        splitter.addWidget(player_widget)

        # Splitter ratios
        splitter.setSizes([220, 380, 600])
        splitter.setHandleWidth(1)

        main_layout.addWidget(splitter)

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Bereit")
        self.setStatusBar(self.status_bar)

        # Menu Bar
        menubar = self.menuBar()
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
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("Beenden", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Ansicht Menu
        view_menu = menubar.addMenu("Ansicht")

        series_action = QAction("Serien durchsuchen", self)
        series_action.setShortcut("Ctrl+S")
        series_action.triggered.connect(self._open_series_browser)
        view_menu.addAction(series_action)

        epg_action = QAction("EPG anzeigen", self)
        epg_action.setShortcut("Ctrl+E")
        epg_action.triggered.connect(self._toggle_epg)
        view_menu.addAction(epg_action)

        fav_action = QAction("Favoriten anzeigen", self)
        fav_action.setShortcut("Ctrl+F")
        fav_action.triggered.connect(self._show_favorites)
        view_menu.addAction(fav_action)

        # v3 Menu
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

        # v4 Menu
        devices_menu = menubar.addMenu("Geraete")

        cast_action = QAction("DLNA/Chromecast Cast", self)
        cast_action.triggered.connect(self._open_cast)
        devices_menu.addAction(cast_action)

        remote_action = QAction("Web Remote Control", self)
        remote_action.triggered.connect(self._toggle_remote_control)
        devices_menu.addAction(remote_action)

        profile_menu = menubar.addMenu("Profil")

        switch_profile_action = QAction("Profil wechseln", self)
        switch_profile_action.triggered.connect(self._switch_profile)
        profile_menu.addAction(switch_profile_action)

        # v4 in Ansicht Menu
        mini_player_action = QAction("Mini Player", self)
        mini_player_action.triggered.connect(self._toggle_mini_player)
        view_menu.addAction(mini_player_action)

        epg_timeline_action = QAction("EPG Timeline", self)
        epg_timeline_action.triggered.connect(self._show_epg_timeline)
        view_menu.addAction(epg_timeline_action)

        catchup_action = QAction("Catch-up / Replay", self)
        catchup_action.triggered.connect(self._open_catchup)
        view_menu.addAction(catchup_action)

        vod_action = QAction("Filme / VOD durchsuchen", self)
        vod_action.triggered.connect(self._open_vod_browser)
        view_menu.addAction(vod_action)

        global_search_action = QAction("Globale Suche", self)
        global_search_action.setShortcut("Ctrl+G")
        global_search_action.triggered.connect(self._open_global_search)
        view_menu.addAction(global_search_action)

    def _load_providers(self):
        """Provider in ComboBox laden."""
        self.provider_combo.clear()
        self.provider_combo.addItem("-- Provider waehlen --", None)
        providers = self.config.get_providers()
        for p in providers:
            self.provider_combo.addItem(f"{p[1]} ({p[2]})", p[0])

    def _add_provider(self):
        """Provider hinzufuegen Dialog oeffnen."""
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

    def _on_provider_change(self, idx):
        """Provider gewechselt."""
        if idx <= 0:
            return
        pid = self.provider_combo.itemData(idx)
        if pid:
            self.current_provider_id = pid
            self._load_playlist(pid)

    def _load_playlist(self, provider_id):
        """Playlist fuer Provider laden."""
        provider = self.config.get_provider(provider_id)
        if not provider:
            return

        ptype = provider[2]
        url = provider[3]
        username = provider[4]
        password = provider[5]

        self.loading_bar.setVisible(True)
        self.loading_bar.setRange(0, 0)
        self.status_bar.showMessage(f"Lade Playlist von {provider[1]}...")

        self.load_thread = LoadPlaylistThread(ptype, url, username, password)
        self.load_thread.finished.connect(lambda channels: self._on_playlist_loaded(provider_id, channels))
        self.load_thread.error.connect(self._on_playlist_error)
        self.load_thread.start()

    def _on_playlist_loaded(self, provider_id, channels):
        """Playlist erfolgreich geladen."""
        self.loading_bar.setVisible(False)
        self.config.add_channels(provider_id, channels)
        self.status_bar.showMessage(f"{len(channels)} Kanaele geladen", 3000)
        self._update_categories()
        self._update_channels()

    def _on_playlist_error(self, error_msg):
        """Playlist Fehler."""
        self.loading_bar.setVisible(False)
        self.status_bar.showMessage(f"Fehler: {error_msg}")
        QMessageBox.warning(self, "Playlist Fehler", error_msg)

    def _update_categories(self):
        """Kategorien in Sidebar laden (type-spezifisch mit Fallback)."""
        self.category_list.clear()
        item = QListWidgetItem("Alle")
        item.setData(Qt.UserRole, None)
        self.category_list.addItem(item)

        # Type-spezifische Kategorien abrufen
        live_cats = self.config.get_categories(self.current_provider_id, type="live")
        vod_cats = self.config.get_categories(self.current_provider_id, type="vod")
        series_cats = self.config.get_categories(self.current_provider_id, type="series")

        # Fallback: Wenn alle type-spezifischen Listen leer sind,
        # alle Kategorien ohne Type-Filter abrufen
        if not live_cats and not vod_cats and not series_cats:
            all_cats = self.config.get_categories(self.current_provider_id)
            for cat in all_cats:
                if cat:
                    item = QListWidgetItem(cat)
                    item.setData(Qt.UserRole, cat)
                    self.category_list.addItem(item)
            self.category_list.setCurrentRow(0)
            return

        # Live Kategorien
        if live_cats:
            sep = QListWidgetItem("── Live TV ──")
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
            sep = QListWidgetItem("── VOD (Filme) ──")
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
            sep = QListWidgetItem("── Serien ──")
            sep.setData(Qt.UserRole, None)
            sep.setFlags(Qt.NoItemFlags)
            self.category_list.addItem(sep)
            for cat in series_cats:
                if cat:
                    item = QListWidgetItem(cat)
                    item.setData(Qt.UserRole, cat)
                    self.category_list.addItem(item)

        self.category_list.setCurrentRow(0)

    def _update_channels(self, search=None):
        """Kanaele in Liste laden (mit Type-Indikator)."""
        self.channel_list.clear()
        channels = self.config.get_channels(
            provider_id=self.current_provider_id,
            category=self.current_category,
            search=search
        )
        self.channels = channels
        type_icons = {"live": "📺", "vod": "🎬", "series": "📺"}
        for ch in channels:
            ch_id, _, name, url, logo, cat, tvg_id, tvg_name, ch_type = ch
            icon = type_icons.get(ch_type, "📺")
            display = f"{icon} {name}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, ch_id)
            item.setToolTip(f"{name}\nKategorie: {cat}\nTyp: {ch_type}")
            self.channel_list.addItem(item)
        self.status_bar.showMessage(f"{len(channels)} Kanaele", 2000)

    def _on_category_change(self, current, previous):
        """Kategorie gewechselt."""
        if not current:
            return
        self.current_category = current.data(Qt.UserRole)
        self._update_channels(self.search_bar.text())

    def _on_search(self, text):
        """Suche eingegeben."""
        self._update_channels(text)

    def _play_channel(self, item):
        """Kanal abspielen."""
        ch_id = item.data(Qt.UserRole)
        channels = self.config.get_channels()
        for ch in channels:
            if ch[0] == ch_id:
                name = ch[2]
                url = ch[3]
                ch_type = ch[8] if len(ch) > 8 else "live"

                # Series: Series-Browser oeffnen statt direktes Abspielen
                if ch_type == "series":
                    self.status_bar.showMessage(f"Oeffne Serien-Browser: {name}...")
                    self._open_series_browser_for_series(name, url)
                    return

                self.now_playing_label.setText(f"Spielt: {name}")
                self.status_bar.showMessage(f"Spiele {name}...")

                # In Qt Fenster einbetten
                wid = int(self.video_container.winId())
                self.player.play(url, window_id=wid)
                self.btn_play.setText("Pause")
                break

    def _toggle_play(self):
        """Play/Pause toggeln."""
        if self.player.is_playing:
            self.player.pause()
            self.btn_play.setText("Play")
            self.player.is_playing = False
        else:
            if self.player.current_url:
                wid = int(self.video_container.winId())
                self.player.play(self.player.current_url, window_id=wid)
                self.btn_play.setText("Pause")
                self.player.is_playing = True

    def _stop_player(self):
        """Player stoppen."""
        self.player.stop()
        self.btn_play.setText("Play")
        self.now_playing_label.setText("Kein Kanal ausgewaehlt")
        self.status_bar.showMessage("Gestoppt")

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
        """Player Status pruefen."""
        if self.player.process and not self.player.is_running():
            self.btn_play.setText("Play")
            self.player.is_playing = False

    # === v2 Methods ===

    def _open_settings(self):
        """Einstellungen Dialog oeffnen."""
        if not V2_AVAILABLE:
            QMessageBox.information(self, "v2", "Settings Modul nicht verfuegbar.")
            return
        try:
            dialog = SettingsDialog(config=self.config, parent=self)
            if dialog.exec_():
                self.status_bar.showMessage("Einstellungen gespeichert", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Einstellungen", f"Fehler: {e}")

    def _open_series_browser(self):
        """Serien-Browser oeffnen."""
        if not V2_AVAILABLE:
            QMessageBox.information(self, "v2", "Series Browser Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            QMessageBox.information(self, "Serien", "Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider or provider[2] != "xtream":
                QMessageBox.information(self, "Serien", "Serien-Browser benoetigt einen Xtream Codes Provider.")
                return
            api = XtreamAPI(provider[3], provider[4], provider[5])
            browser = SeriesBrowser(api, self.player, parent=self)
            browser.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Serien", f"Fehler: {e}")

    def _open_series_browser_for_series(self, series_name, series_url):
        """Series-Browser fuer eine spezifische Serie aus der Kanal-Liste oeffnen."""
        if not V2_AVAILABLE:
            QMessageBox.information(self, "v2", "Series Browser Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            QMessageBox.information(self, "Serien", "Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider or provider[2] != "xtream":
                QMessageBox.information(self, "Serien", "Serien-Browser benoetigt einen Xtream Codes Provider.")
                return
            api = XtreamAPI(provider[3], provider[4], provider[5])
            browser = SeriesBrowser(api, self.player, parent=self)
            browser.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Serien", f"Fehler: {e}")

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
        channels = self.config.get_channels()
        for ch in channels:
            if ch[0] == ch_id:
                self.now_playing_label.setText(f"Jetzt: {ch[2]}")
                # v2: EPG fuer Live-Kanaele laden
                if V2_AVAILABLE and ch[8] == "live" and self.current_provider_id:
                    provider = self.config.get_provider(self.current_provider_id)
                    if provider and provider[2] == "xtream":
                        try:
                            tvg_id = ch[6]
                            if tvg_id:
                                service = EpgService(provider[3], provider[4], provider[5])
                                epg_data = service.get_live_stream_epg(int(tvg_id))
                                if epg_data:
                                    self.now_playing_label.setText(f"Jetzt: {ch[2]} | {epg_data[0].get('title', '')}")
                        except Exception:
                            pass
                break

    # === v3 Methods ===

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

    # === v4 Methods ===

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
            channels = self.config.get_channels(provider_id=self.current_provider_id)
            self.epg_timeline_widget.set_channels(channels)
            self.epg_timeline_widget.show()
            self.status_bar.showMessage("EPG Timeline geoeffnet", 2000)
        except Exception as e:
            QMessageBox.warning(self, "EPG Timeline", f"Fehler: {e}")

    def _open_catchup(self):
        """Catch-up / Replay Dialog oeffnen."""
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
            dialog = CatchupDialog(api, self.player, parent=self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Catch-up", f"Fehler: {e}")

    def _open_vod_browser(self):
        """VOD Browser (Filme) oeffnen."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "VOD", "VOD Browser Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            QMessageBox.information(self, "VOD", "Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider or provider[2] != "xtream":
                QMessageBox.information(self, "VOD", "VOD Browser benoetigt einen Xtream Codes Provider.")
                return
            api = XtreamAPI(provider[3], provider[4], provider[5])
            dialog = VodBrowser(api, self.player, parent=self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "VOD Browser", f"Fehler: {e}")

    def _open_global_search(self):
        """Globale Suche ueber alle Inhaltstypen."""
        if not V4_AVAILABLE:
            QMessageBox.information(self, "Suche", "Such-Modul nicht verfuegbar.")
            return
        if not self.current_provider_id:
            QMessageBox.information(self, "Suche", "Bitte zuerst einen Provider auswaehlen.")
            return
        try:
            provider = self.config.get_provider(self.current_provider_id)
            if not provider:
                QMessageBox.information(self, "Suche", "Kein Provider gefunden.")
                return
            ptype = provider[2]
            if ptype == "xtream":
                api = XtreamAPI(provider[3], provider[4], provider[5])
                dialog = SearchBrowser(
                    provider_type="xtream",
                    api=api,
                    player=self.player,
                    parent=self
                )
            else:
                dialog = SearchBrowser(
                    provider_type="m3u",
                    config=self.config,
                    provider_id=self.current_provider_id,
                    player=self.player,
                    parent=self
                )
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Globale Suche", f"Fehler: {e}")

    def eventFilter(self, obj, event):
        """Event filter for double-click seek on video container."""
        if obj == self.video_container and event.type() == QEvent.MouseButtonDblClick:
            if self.player.is_playing and self.player.is_running():
                click_x = event.pos().x()
                width = self.video_container.width()
                if click_x < width / 2:
                    # Left half: seek backward 10s
                    self.player.seek_relative(-10)
                    self.status_bar.showMessage("<< 10s zurueck", 1500)
                else:
                    # Right half: seek forward 10s
                    self.player.seek_relative(10)
                    self.status_bar.showMessage("10s vor >>", 1500)
            return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """App schliessen."""
        self.player.stop()
        self.player_timer.stop()
        # v3 cleanup
        if hasattr(self, "pip_window"):
            self.pip_window.stop_video()
        if hasattr(self, "recording_mgr"):
            self.recording_mgr.stop_recording()
        if hasattr(self, "auto_refresh_mgr"):
            self.auto_refresh_mgr.stop()
        # v4 cleanup
        if hasattr(self, "mini_player"):
            self.mini_player.stop_video()
        if hasattr(self, "remote_controller"):
            try:
                self.remote_controller.stop_server()
            except Exception:
                pass
        if hasattr(self, "cast_widget"):
            try:
                self.cast_widget.close()
            except Exception:
                pass
        event.accept()
