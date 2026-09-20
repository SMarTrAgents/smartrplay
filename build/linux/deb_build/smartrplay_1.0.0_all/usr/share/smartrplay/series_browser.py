#!/usr/bin/env python3
"""SMarTrPlay - Series Browser (Xtream Series + Episodes + Player)

Improved version with:
- Category filtering via get_series_categories()
- Cover thumbnails with disk caching (~/.cache/smartrplay/series_covers/)
- Search/filter field for series names
- Separate seasons and episodes lists
- Async cover loading (SeriesCoverLoader)
- Async series info loading (SeriesInfoLoaderThread)
- Series info panel (name, plot, rating, genre)
- SMarTr brand design (#0A0F1E, #1BF1FB, #8D7CF6)
"""

import os
import hashlib
import urllib.request

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QLineEdit, QProgressBar, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor

from xtream_api import XtreamAPI
from player import PlayerBackend
from theme import (
    BG_DEEP, BG_CARD, BG_CARD_HOVER, BORDER, BORDER_LIGHT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_CYAN, ACCENT_PURPLE, ACCENT_VIOLET, get_font
)

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

COVER_CACHE_DIR = os.path.expanduser("~/.cache/smartrplay/series_covers")
COVER_THUMB_W = 60
COVER_THUMB_H = 90


# ----------------------------------------------------------------------
# Background Threads
# ----------------------------------------------------------------------

class CategoryLoaderThread(QThread):
    """Laedt Series-Kategorien im Hintergrund."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        try:
            cats = self.api.get_series_categories() or []
            self.finished.emit(cats)
        except Exception as e:
            self.error.emit(str(e))


class SeriesLoaderThread(QThread):
    """Laedt Series-Liste im Hintergrund."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, api, category_id=None):
        super().__init__()
        self.api = api
        self.category_id = category_id

    def run(self):
        try:
            series_list = self.api.get_series(self.category_id) or []
            self.finished.emit(series_list)
        except Exception as e:
            self.error.emit(str(e))


class SeriesInfoLoaderThread(QThread):
    """Laedt Series Info (Seasons + Episoden) im Hintergrund."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, api, series_id):
        super().__init__()
        self.api = api
        self.series_id = series_id

    def run(self):
        try:
            info = self.api.get_series_info(self.series_id)
            self.finished.emit(info if info else {})
        except Exception as e:
            self.error.emit(str(e))


class SeriesCoverLoader(QThread):
    """Laedt ein Cover-Bild asynchron mit lokalem Caching."""
    cover_loaded = pyqtSignal(str, QPixmap)  # series_id, pixmap

    def __init__(self, series_id, cover_url, parent=None):
        super().__init__(parent)
        self.series_id = str(series_id)
        self.cover_url = cover_url

    def run(self):
        try:
            pixmap = self._load_cover()
            if pixmap:
                self.cover_loaded.emit(self.series_id, pixmap)
        except Exception:
            pass

    def _load_cover(self):
        """Cover aus Cache oder per Download laden und als QPixmap zurueckgeben."""
        if not self.cover_url:
            return None

        os.makedirs(COVER_CACHE_DIR, exist_ok=True)
        url_hash = hashlib.md5(self.cover_url.encode("utf-8")).hexdigest()
        cache_path = os.path.join(COVER_CACHE_DIR, url_hash + ".jpg")

        # 1) Cache pruefen
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            pix = QPixmap()
            if pix.load(cache_path):
                return pix.scaled(
                    COVER_THUMB_W, COVER_THUMB_H,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )

        # 2) Download mit urllib.request
        try:
            req = urllib.request.Request(self.cover_url, headers={
                "User-Agent": "SMarTrPlay/1.0"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()

            if not data:
                return None

            # Im Cache speichern
            try:
                with open(cache_path, "wb") as fh:
                    fh.write(data)
            except Exception:
                pass

            pix = QPixmap()
            if pix.loadFromData(data):
                return pix.scaled(
                    COVER_THUMB_W, COVER_THUMB_H,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
        except Exception:
            pass

        return None


# ----------------------------------------------------------------------
# Main Dialog
# ----------------------------------------------------------------------

class SeriesBrowser(QDialog):
    """Series Browser Dialog mit Kategorien, Serien, Seasons und Episoden."""

    def __init__(self, api, player, parent=None):
        super().__init__(parent)
        self.api = api
        self.player = player
        self.current_series_id = None
        self.current_season_key = None
        self.all_series = []           # vollstaendige Series-Liste fuer Suche
        self._seasons_dict = {}        # season_key -> [episodes]
        self._cover_loaders = []       # aktive Cover-Loader referenzen
        self._bg_threads = []          # aktive Hintergrund-Threads

        self.setWindowTitle("SMarTrPlay - Series Browser")
        self.setMinimumSize(1100, 650)
        self.setStyleSheet(self._build_stylesheet())

        self._build_ui()
        self._load_categories()
        self._load_series()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        layout.addWidget(self._build_header())

        # Main horizontal splitter: left | right
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(1)
        main_splitter.setStyleSheet(
            "QSplitter::handle {{ background-color: {0}; }}".format(BORDER)
        )

        # --- LEFT: categories + search + series list ---
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(12, 12, 6, 12)
        left_l.setSpacing(8)

        # Categories
        cat_title = QLabel("KATEGORIEN")
        cat_title.setStyleSheet(self._sidebar_title_css())
        left_l.addWidget(cat_title)

        self.category_list = QListWidget()
        self.category_list.setUniformItemSizes(True)
        self.category_list.setMaximumHeight(140)
        self.category_list.itemClicked.connect(self._on_category_clicked)
        left_l.addWidget(self.category_list)

        # Search field
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        search_icon = QLabel("Suche:")
        search_icon.setStyleSheet(
            "color: {0}; font-size: 11px; font-weight: 600;".format(TEXT_MUTED)
        )
        search_row.addWidget(search_icon)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Series suchen...")
        self.search_field.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_field)
        left_l.addLayout(search_row)

        # Series list
        series_title = QLabel("SERIES")
        series_title.setStyleSheet(self._sidebar_title_css())
        left_l.addWidget(series_title)

        self.series_list = QListWidget()
        self.series_list.setUniformItemSizes(True)
        self.series_list.setSortingEnabled(False)
        self.series_list.setIconSize(QSize(COVER_THUMB_W, COVER_THUMB_H))
        self.series_list.itemClicked.connect(self._on_series_clicked)
        left_l.addWidget(self.series_list, stretch=1)

        # --- RIGHT: info + seasons + episodes ---
        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(6, 12, 12, 12)
        right_l.setSpacing(8)

        # Series info label
        self.info_label = QLabel("Waehle eine Serie aus, um Details anzuzeigen.")
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.RichText)
        self.info_label.setStyleSheet(
            "color: {0}; font-size: 12px; "
            "padding: 10px 14px; background-color: {1}; "
            "border: 1px solid {2}; border-radius: 8px;".format(
                TEXT_SECONDARY, BG_CARD, BORDER
            )
        )
        self.info_label.setMinimumHeight(60)
        self.info_label.setMaximumHeight(120)
        right_l.addWidget(self.info_label)

        # Vertical splitter: seasons | episodes
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(1)
        right_splitter.setStyleSheet(
            "QSplitter::handle {{ background-color: {0}; }}".format(BORDER)
        )

        # Seasons panel
        seasons_widget = QWidget()
        seasons_l = QVBoxLayout(seasons_widget)
        seasons_l.setContentsMargins(0, 0, 0, 0)
        seasons_l.setSpacing(4)

        seasons_title = QLabel("SEASONS")
        seasons_title.setStyleSheet(self._sidebar_title_css())
        seasons_l.addWidget(seasons_title)

        self.seasons_list = QListWidget()
        self.seasons_list.setUniformItemSizes(True)
        self.seasons_list.itemClicked.connect(self._on_season_clicked)
        seasons_l.addWidget(self.seasons_list)

        # Episodes panel
        episodes_widget = QWidget()
        episodes_l = QVBoxLayout(episodes_widget)
        episodes_l.setContentsMargins(0, 0, 0, 0)
        episodes_l.setSpacing(4)

        episodes_title = QLabel("EPISODEN")
        episodes_title.setStyleSheet(self._sidebar_title_css())
        episodes_l.addWidget(episodes_title)

        self.episodes_list = QListWidget()
        self.episodes_list.setUniformItemSizes(True)
        self.episodes_list.itemDoubleClicked.connect(
            self._on_episode_double_clicked
        )
        episodes_l.addWidget(self.episodes_list)

        right_splitter.addWidget(seasons_widget)
        right_splitter.addWidget(episodes_widget)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 2)

        right_l.addWidget(right_splitter, stretch=1)

        # Assemble main splitter
        main_splitter.addWidget(left)
        main_splitter.addWidget(right)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)

        layout.addWidget(main_splitter, stretch=1)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        # Status label
        self.status_label = QLabel("Bereit.")
        self.status_label.setStyleSheet(
            "color: {0}; font-size: 11px; "
            "padding: 6px 16px; background-color: {1};".format(
                TEXT_MUTED, BG_DEEP
            )
        )
        layout.addWidget(self.status_label)

    def _build_header(self):
        """Header-Leiste mit Titel und Buttons."""
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(
            "background-color: {0};"
            "border-bottom: 1px solid {1};".format(BG_DEEP, BORDER)
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        title = QLabel("Series Browser")
        title.setStyleSheet(
            "color: {0}; font-size: 20px; font-weight: 800;".format(TEXT_PRIMARY)
        )
        hl.addWidget(title)
        hl.addStretch()

        self.refresh_btn = QPushButton("Aktualisieren")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._on_refresh)
        hl.addWidget(self.refresh_btn)

        close_btn = QPushButton("Schliessen")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)

        return header

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    @staticmethod
    def _sidebar_title_css():
        return (
            "color: {0}; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1px; padding: 4px 8px;".format(TEXT_MUTED)
        )

    def _build_stylesheet(self):
        return """
        QDialog {{
            background-color: {bg_deep};
        }}
        QListWidget {{
            background-color: {bg_card};
            border: 1px solid {border};
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 8px 12px;
            border-radius: 6px;
            color: {text_sec};
        }}
        QListWidget::item:selected {{
            background-color: {accent_v};
            color: {text_pri};
        }}
        QListWidget::item:hover {{
            background-color: {bg_hover};
        }}
        QLineEdit {{
            background-color: {bg_card};
            border: 1px solid {border};
            border-radius: 8px;
            padding: 8px 12px;
            color: {text_pri};
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {accent_p};
        }}
        QPushButton {{
            background-color: {bg_card};
            border: 1px solid {border};
            border-radius: 8px;
            padding: 8px 16px;
            color: {text_pri};
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {bg_hover};
            border: 1px solid {accent_p};
        }}
        QProgressBar {{
            background-color: {bg_deep};
            border: none;
        }}
        QProgressBar::chunk {{
            background-color: {accent_c};
        }}
        QSplitter {{
            background-color: {bg_deep};
        }}
        """.format(
            bg_deep=BG_DEEP, bg_card=BG_CARD, bg_hover=BG_CARD_HOVER,
            border=BORDER, text_pri=TEXT_PRIMARY, text_sec=TEXT_SECONDARY,
            accent_v=ACCENT_VIOLET, accent_p=ACCENT_PURPLE,
            accent_c=ACCENT_CYAN
        )

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def _load_categories(self):
        """Kategorien im Hintergrund laden."""
        self.category_list.clear()

        # "Alle" Eintrag immer vorhanden
        all_item = QListWidgetItem("Alle Kategorien")
        all_item.setData(Qt.UserRole, None)
        self.category_list.addItem(all_item)

        loader = CategoryLoaderThread(self.api)
        self._bg_threads.append(loader)
        loader.finished.connect(self._on_categories_loaded)
        loader.error.connect(
            lambda e: self.status_label.setText("Kategorie-Fehler: " + e)
        )
        loader.start()

    def _on_categories_loaded(self, categories):
        """Kategorien in Liste einfuegen."""
        for cat in categories:
            cat_id = cat.get("category_id")
            cat_name = cat.get("category_name", "Unbekannt")
            item = QListWidgetItem(cat_name)
            item.setData(Qt.UserRole, cat_id)
            self.category_list.addItem(item)

    def _on_category_clicked(self, item):
        """Kategorie ausgewaehlt -> Series fuer diese Kategorie laden."""
        cat_id = item.data(Qt.UserRole)
        self._load_series(cat_id)

    # ------------------------------------------------------------------
    # Series Loading
    # ------------------------------------------------------------------

    def _on_refresh(self):
        """Aktualisieren: Kategorien und Series neu laden."""
        self._load_categories()
        self._load_series()

    def _load_series(self, category_id=None):
        """Series-Liste im Hintergrund laden."""
        self.series_list.clear()
        self.seasons_list.clear()
        self.episodes_list.clear()
        self.current_series_id = None
        self.current_season_key = None
        self.all_series = []
        self.info_label.setText(
            "Waehle eine Serie aus, um Details anzuzeigen."
        )
        self.progress.show()
        self.status_label.setText("Lade Series...")

        loader = SeriesLoaderThread(self.api, category_id)
        self._bg_threads.append(loader)
        loader.finished.connect(self._on_series_loaded)
        loader.error.connect(self._on_series_error)
        loader.start()

    def _on_series_loaded(self, series_list):
        """Series-Liste empfangen und mit Covers anzeigen."""
        self.progress.hide()
        self.all_series = series_list
        count = len(series_list)
        self.status_label.setText("{0} Series gefunden.".format(count))
        self._populate_series_list(series_list)

    def _populate_series_list(self, series_list):
        """Series-Liste fuellen und Cover-Loader starten."""
        self.series_list.clear()

        for item in series_list:
            name = item.get("name", "Unbekannt")
            series_id = str(item.get("series_id", ""))
            cover = item.get("cover", "")

            list_item = QListWidgetItem(name)
            list_item.setData(Qt.UserRole, series_id)
            list_item.setData(Qt.UserRole + 1, item)
            list_item.setToolTip(name)
            self.series_list.addItem(list_item)

            # Cover asynchron laden
            if cover:
                loader = SeriesCoverLoader(series_id, cover, self)
                loader.cover_loaded.connect(self._on_cover_loaded)
                self._cover_loaders.append(loader)
                loader.start()

    def _on_cover_loaded(self, series_id, pixmap):
        """Cover-Bild fuer das passende Series-Item setzen."""
        for i in range(self.series_list.count()):
            item = self.series_list.item(i)
            if item.data(Qt.UserRole) == series_id:
                item.setIcon(QIcon(pixmap))
                break

    def _on_series_error(self, error_msg):
        """Fehler beim Laden der Series."""
        self.progress.hide()
        self.status_label.setText("Fehler: " + error_msg)
        QMessageBox.warning(
            self, "Fehler",
            "Series konnten nicht geladen werden:\n" + error_msg
        )

    # ------------------------------------------------------------------
    # Search / Filter
    # ------------------------------------------------------------------

    def _on_search_changed(self, text):
        """Series-Liste nach Suchbegriff filtern."""
        text = text.strip().lower()
        if not text:
            self._populate_series_list(self.all_series)
            self.status_label.setText(
                "{0} Series gefunden.".format(len(self.all_series))
            )
            return

        filtered = [
            s for s in self.all_series
            if text in (s.get("name", "") or "").lower()
        ]
        self._populate_series_list(filtered)
        self.status_label.setText(
            "{0} Series gefunden (gefiltert).".format(len(filtered))
        )

    # ------------------------------------------------------------------
    # Series Info -> Seasons + Episodes
    # ------------------------------------------------------------------

    def _on_series_clicked(self, item):
        """Series angeklickt -> Info (Seasons + Episoden) laden."""
        series_id = item.data(Qt.UserRole)
        if not series_id or series_id == self.current_series_id:
            return

        self.current_series_id = series_id
        self.seasons_list.clear()
        self.episodes_list.clear()
        self.current_season_key = None
        self.progress.show()
        self.status_label.setText("Lade Info fuer: {0}...".format(item.text()))

        loader = SeriesInfoLoaderThread(self.api, series_id)
        self._bg_threads.append(loader)
        loader.finished.connect(self._on_series_info_loaded)
        loader.error.connect(self._on_series_info_error)
        loader.start()

    def _on_series_info_loaded(self, info):
        """Series-Info verarbeiten: Seasons fuellen, erste Season auto-waehlen."""
        self.progress.hide()

        if not info or not isinstance(info, dict):
            self.status_label.setText("Keine Serien-Info gefunden.")
            return

        # --- Series Info Panel ---
        series_info = info.get("info", {})
        if not isinstance(series_info, dict):
            series_info = {}

        name = series_info.get("name", "Unbekannt")
        plot = series_info.get("plot", "") or ""
        rating = series_info.get("rating", "") or ""
        genre = series_info.get("genre", "") or ""
        cast = series_info.get("cast", "") or ""
        release_date = series_info.get("releaseDate", "") or ""
        season_count = series_info.get("season_count", "") or ""

        # Info-HTML zusammenbauen
        parts = [
            "<b style='color:{0};font-size:14px;'>{1}</b>".format(TEXT_PRIMARY, name)
        ]
        if rating:
            parts.append(
                "<span style='color:{0};'>★ {1}</span>".format(ACCENT_CYAN, rating)
            )
        if genre:
            parts.append(
                "<span style='color:{0};'>{1}</span>".format(TEXT_MUTED, genre)
            )
        if release_date:
            parts.append(
                "<span style='color:{0};'>{1}</span>".format(TEXT_MUTED, release_date)
            )
        if season_count:
            parts.append(
                "<span style='color:{0};'>{1} Staffeln</span>".format(
                    TEXT_MUTED, season_count
                )
            )

        info_html = "  |  ".join(parts)
        if plot:
            short_plot = plot[:300] + ("..." if len(plot) > 300 else "")
            info_html += (
                "<br><span style='color:{0};font-size:11px;'>{1}</span>".format(
                    TEXT_SECONDARY, short_plot
                )
            )

        self.info_label.setText(info_html)

        # --- Episodes Daten parsen ---
        episodes_data = info.get("episodes", {})

        # Episodes koennen dict (season_key -> [ep]) oder flat list sein
        if isinstance(episodes_data, dict):
            seasons_dict = episodes_data
        elif isinstance(episodes_data, list):
            seasons_dict = {}
            for ep in episodes_data:
                sn = str(ep.get("season_number", ep.get("season", "1")))
                seasons_dict.setdefault(sn, []).append(ep)
        else:
            seasons_dict = {}

        self._seasons_dict = seasons_dict
        seasons_list_data = info.get("seasons", [])

        # --- Seasons Liste fuellen ---
        self._populate_seasons(seasons_dict, seasons_list_data)

        # Erste Season automatisch auswaehlen
        if self.seasons_list.count() > 0:
            first = self.seasons_list.item(0)
            self.seasons_list.setCurrentItem(first)
            self._on_season_clicked(first)

        self.status_label.setText("Series-Info geladen: " + name)

    def _populate_seasons(self, seasons_dict, seasons_list_data=None):
        """Seasons-Liste fuellen (aus seasons_list oder abgeleitet aus episodes)."""
        self.seasons_list.clear()
        self._seasons_dict = seasons_dict

        if seasons_list_data and isinstance(seasons_list_data, list) \
                and len(seasons_list_data) > 0:
            # Explizite Seasons-Liste verwenden
            for season in sorted(
                seasons_list_data,
                key=lambda s: self._safe_int(s.get("season_number", 0))
            ):
                sn = str(season.get("season_number", "?"))
                sname = season.get("name", "Staffel " + sn)
                ep_count = season.get("episode_count", "?")

                label = "Staffel {0} - {1}".format(sn, sname)
                if ep_count and ep_count != "?":
                    label += "  ({0} Ep.)".format(ep_count)

                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, sn)
                item.setToolTip(sname)
                self.seasons_list.addItem(item)
        else:
            # Seasons aus episodes-dict Schluesseln ableiten
            try:
                sorted_keys = sorted(seasons_dict.keys(), key=lambda s: int(s))
            except (ValueError, TypeError):
                sorted_keys = sorted(seasons_dict.keys())

            for skey in sorted_keys:
                eps = seasons_dict.get(skey, [])
                ep_count = len(eps) if isinstance(eps, list) else 0
                label = "Staffel {0}  ({1} Ep.)".format(skey, ep_count)

                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, skey)
                item.setToolTip(label)
                self.seasons_list.addItem(item)

    def _on_season_clicked(self, item):
        """Season angeklickt -> Episoden fuer diese Season anzeigen."""
        season_key = item.data(Qt.UserRole)
        if season_key is None or season_key == self.current_season_key:
            return

        self.current_season_key = season_key
        self.episodes_list.clear()

        episodes = self._seasons_dict.get(season_key, [])
        if not isinstance(episodes, list):
            return

        # Episoden nach episode_num sortieren
        try:
            episodes = sorted(
                episodes, key=lambda e: self._safe_int(e.get("episode_num", 0))
            )
        except (ValueError, TypeError):
            pass

        for ep in episodes:
            ep_id = str(ep.get("id", ""))
            ep_num = ep.get("episode_num", "?")
            ep_title = ep.get("title", "") or "Ohne Titel"
            ext = ep.get("container_extension", "mp4")

            # Dauer aus info-Subdict falls vorhanden
            ep_info = ep.get("info", {})
            if not isinstance(ep_info, dict):
                ep_info = {}
            duration = ep_info.get("duration", "") or ep_info.get(
                "duration_secs", ""
            )

            label = "E{0} - {1}".format(self._fmt_ep_num(ep_num), ep_title)
            if duration:
                label += "  [{0}]".format(self._fmt_duration(duration))

            list_item = QListWidgetItem(label)
            list_item.setData(Qt.UserRole, ep_id)
            list_item.setData(Qt.UserRole + 1, ext)
            list_item.setData(Qt.UserRole + 2, ep)
            list_item.setToolTip(ep_title)
            self.episodes_list.addItem(list_item)

        self.status_label.setText(
            "Staffel {0}: {1} Episoden.".format(season_key, len(episodes))
        )

    def _on_series_info_error(self, error_msg):
        """Fehler beim Laden der Series-Info."""
        self.progress.hide()
        self.status_label.setText("Fehler: " + error_msg)
        QMessageBox.warning(
            self, "Fehler",
            "Series-Info konnte nicht geladen werden:\n" + error_msg
        )

    # ------------------------------------------------------------------
    # Episode Playback
    # ------------------------------------------------------------------

    def _on_episode_double_clicked(self, item):
        """Doppelklick auf Episode -> Stream mit Player abspielen."""
        ep_id = item.data(Qt.UserRole)
        if not ep_id:
            return

        ext = item.data(Qt.UserRole + 1) or "mp4"
        url = self._build_series_url(ep_id, ext)

        self.status_label.setText("Spiele: {0}".format(item.text()))

        success = self.player.play(url)
        if not success:
            self.status_label.setText("Playback fehlgeschlagen.")
            QMessageBox.warning(
                self, "Playback Fehler",
                "Konnte Episode nicht abspielen:\n" + url
            )

    def _build_series_url(self, episode_id, ext="mp4"):
        """Series Stream URL konstruieren.

        Format: {server}/series/{user}/{pass}/{episode_id}.{ext}
        """
        ext = ext if ext else "mp4"
        return "{0}/series/{1}/{2}/{3}.{4}".format(
            self.api.server_url,
            self.api.username,
            self.api.password,
            episode_id,
            ext
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Auf laufende Threads warten vor dem Schliessen."""
        for loader in self._cover_loaders:
            if loader.isRunning():
                loader.wait(3000)
        for thread in self._bg_threads:
            if thread.isRunning():
                thread.wait(3000)
        event.accept()

    # ------------------------------------------------------------------
    # Static Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_int(val, default=0):
        """Sicherer int()-Cast mit Fallback."""
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _fmt_ep_num(num):
        """Episode-Nummer zweistellig formatieren."""
        try:
            return "{0:02d}".format(int(num))
        except (ValueError, TypeError):
            return str(num)

    @staticmethod
    def _fmt_duration(duration):
        """Dauer in lesbares Format umwandeln (Sekunden -> Xm / Xh Ym)."""
        try:
            secs = float(duration)
            hours = int(secs // 3600)
            mins = int((secs % 3600) // 60)
            if hours > 0:
                return "{0}h {1}m".format(hours, mins)
            return "{0}m".format(mins)
        except (ValueError, TypeError):
            return str(duration)


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    font = get_font()
    font.setPointSize(11)
    app.setFont(font)

    # Dummy API fuer Testing
    class DummyAPI:
        server_url = "http://example.com:8080"
        username = "test"
        password = "test"

        def get_series_categories(self):
            return [
                {"category_id": "1", "category_name": "Action"},
                {"category_id": "2", "category_name": "Drama"},
            ]

        def get_series(self, category_id=None):
            return [
                {"series_id": "1", "name": "Test Series 1", "cover": "",
                 "category_id": "1", "plot": "Test plot", "rating": "8.5",
                 "genre": "Action"},
                {"series_id": "2", "name": "Test Series 2", "cover": "",
                 "category_id": "2", "plot": "Another plot", "rating": "7.0",
                 "genre": "Drama"},
            ]

        def get_series_info(self, series_id):
            return {
                "info": {
                    "name": "Test Series 1",
                    "cover": "",
                    "plot": "A test plot for testing.",
                    "rating": "8.5",
                    "genre": "Action",
                    "cast": "Actor A, Actor B",
                    "releaseDate": "2024",
                    "season_count": "2",
                },
                "seasons": [
                    {"season_number": 1, "name": "Season 1", "cover": "",
                     "episode_count": 2},
                    {"season_number": 2, "name": "Season 2", "cover": "",
                     "episode_count": 1},
                ],
                "episodes": {
                    "1": [
                        {"id": "100", "episode_num": 1, "title": "Pilot",
                         "container_extension": "mp4",
                         "info": {"duration": "3600"}},
                        {"id": "101", "episode_num": 2, "title": "Episode 2",
                         "container_extension": "mp4",
                         "info": {"duration": "3300"}},
                    ],
                    "2": [
                        {"id": "200", "episode_num": 1, "title": "S2 Premiere",
                         "container_extension": "mp4",
                         "info": {"duration": "3000"}},
                    ],
                }
            }

    class DummyPlayer:
        def play(self, url, window_id=None):
            print("[DummyPlayer] play: " + url)
            return True

    dialog = SeriesBrowser(DummyAPI(), DummyPlayer())
    dialog.exec_()
