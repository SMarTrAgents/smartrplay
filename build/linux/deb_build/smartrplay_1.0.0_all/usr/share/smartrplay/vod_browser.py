#!/usr/bin/env python3
"""SMarTrPlay - VOD Browser (Movies) mit Covers, Ratings und Beschreibungen."""

import os
import hashlib
import urllib.request
import subprocess
import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QLineEdit, QLabel, QPushButton, QWidget, QProgressBar, QTextEdit,
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QMutex,
)
from PyQt5.QtGui import (
    QPixmap,
)

from xtream_api import XtreamAPI
from player import PlayerBackend

# SMarTr Brand Colors
COLOR_BG = "#0A0F1E"
COLOR_CYAN = "#1bf1fb"
COLOR_PURPLE = "#8D7CF6"
COLOR_DEEP_PURPLE = "#371689"
COLOR_CARD = "#121829"
COLOR_TEXT = "#E0E6ED"
COLOR_TEXT_DIM = "#8B95A5"

COVER_CACHE_DIR = os.path.expanduser("~/.cache/smartrplay/covers")
COVER_THUMB_W = 80
COVER_THUMB_H = 120
COVER_FULL_W = 300
COVER_FULL_H = 450

BRAND_QSS = f"""
QDialog, QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
}}
QListWidget {{
    background-color: {COLOR_CARD};
    border: 1px solid #2a3050;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    border-radius: 6px;
    padding: 4px;
}}
QListWidget::item:selected {{
    background-color: {COLOR_DEEP_PURPLE};
    border: 1px solid {COLOR_PURPLE};
}}
QListWidget::item:hover {{
    background-color: #1a2040;
}}
QLineEdit {{
    background-color: {COLOR_CARD};
    border: 1px solid #2a3050;
    border-radius: 6px;
    padding: 8px 12px;
    color: {COLOR_TEXT};
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 1px solid {COLOR_CYAN};
}}
QPushButton {{
    background-color: {COLOR_DEEP_PURPLE};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_PURPLE};
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {COLOR_PURPLE};
}}
QPushButton:pressed {{
    background-color: #2a1050;
}}
QPushButton#playBtn {{
    background-color: {COLOR_CYAN};
    color: {COLOR_BG};
    border: 1px solid {COLOR_CYAN};
    font-weight: 700;
}}
QPushButton#playBtn:hover {{
    background-color: #4df5ff;
}}
QPushButton#trailerBtn {{
    background-color: transparent;
    color: {COLOR_CYAN};
    border: 1px solid {COLOR_CYAN};
}}
QPushButton#trailerBtn:hover {{
    background-color: rgba(27, 241, 251, 0.1);
}}
QLabel#titleLabel {{
    font-size: 20px;
    font-weight: 700;
    color: {COLOR_TEXT};
}}
QLabel#ratingLabel {{
    font-size: 16px;
    color: #FFD700;
}}
QLabel#metaLabel {{
    font-size: 13px;
    color: {COLOR_TEXT_DIM};
}}
QLabel#sectionLabel {{
    font-size: 14px;
    font-weight: 600;
    color: {COLOR_CYAN};
}}
QSplitter::handle {{
    background-color: #2a3050;
    width: 2px;
}}
QProgressBar {{
    border: 1px solid #2a3050;
    border-radius: 4px;
    text-align: center;
    background-color: {COLOR_CARD};
    color: {COLOR_TEXT};
}}
QProgressBar::chunk {{
    background-color: {COLOR_CYAN};
    border-radius: 3px;
}}
QTextEdit {{
    background-color: {COLOR_CARD};
    border: 1px solid #2a3050;
    border-radius: 6px;
    color: {COLOR_TEXT};
    font-size: 13px;
    padding: 8px;
}}
"""


def cover_cache_path(url):
    """Generiere lokalen Cache-Pfad fuer eine Cover-URL."""
    if not url:
        return None
    os.makedirs(COVER_CACHE_DIR, exist_ok=True)
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    ext = ".jpg"
    for e in [".png", ".jpg", ".jpeg", ".webp"]:
        if e in url.lower():
            ext = e
            break
    return os.path.join(COVER_CACHE_DIR, url_hash + ext)


def download_cover(url, target_path):
    """Cover-Bild herunterladen und lokal cachen. Gibt Pfad oder None zurueck."""
    if not url or not target_path:
        return None
    if os.path.exists(target_path):
        return target_path
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "SMarTrPlay/1.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        with open(target_path, "wb") as f:
            f.write(data)
        return target_path
    except Exception:
        return None


def rating_to_stars(rating, max_stars=5):
    """Numerisches Rating in Sterne-String umwandeln (0-10 Skala -> 0-5 Sterne)."""
    try:
        r = float(rating)
    except (ValueError, TypeError):
        return "\u2605" * 0 + "\u2606" * max_stars
    filled = int(round(r / 2.0))
    filled = max(0, min(max_stars, filled))
    return "\u2605" * filled + "\u2606" * (max_stars - filled)


class VodLoaderThread(QThread):
    """Laedt VOD Streams im Hintergrund."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api = None
        self.category_id = None

    def start(self, api, category_id):
        """Thread starten mit API-Instanz und Category-ID."""
        self.api = api
        self.category_id = category_id
        super().start()

    def run(self):
        try:
            streams = self.api.get_vod_streams(self.category_id) or []
            self.finished.emit(streams)
        except Exception as e:
            self.error.emit(str(e))


class VodInfoLoaderThread(QThread):
    """Laedt VOD Info im Hintergrund."""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api = None
        self.vod_id = None

    def start(self, api, vod_id):
        """Thread starten mit API-Instanz und VOD-ID."""
        self.api = api
        self.vod_id = vod_id
        super().start()

    def run(self):
        try:
            info = self.api.get_vod_info(self.vod_id) or {}
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class CoverLoaderThread(QThread):
    """Laedt Cover-Bilder im Hintergrund (sequentiell, cached)."""

    cover_ready = pyqtSignal(str, QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._urls = []
        self._running = False
        self._mutex = QMutex()

    def load_covers(self, urls):
        """Liste von URLs zum Laden hinzufuegen und Thread starten."""
        self._mutex.lock()
        self._urls = list(urls)
        self._mutex.unlock()
        if not self.isRunning():
            super().start()

    def run(self):
        self._running = True
        while self._running:
            self._mutex.lock()
            if self._urls:
                url = self._urls.pop(0)
            else:
                url = None
            self._mutex.unlock()

            if url is None:
                break

            path = cover_cache_path(url)
            if path:
                if not os.path.exists(path):
                    download_cover(url, path)
                if os.path.exists(path):
                    pix = QPixmap(path)
                    if not pix.isNull():
                        self.cover_ready.emit(url, pix)
                        continue
            self.cover_ready.emit(url, QPixmap())

    def stop(self):
        """Thread anhalten und Warteschlange leeren."""
        self._running = False
        self._mutex.lock()
        self._urls.clear()
        self._mutex.unlock()


class VodListItemWidget(QWidget):
    """Custom Widget fuer einen VOD-Eintrag mit Cover, Name und Rating."""

    def __init__(self, stream_data, parent=None):
        super().__init__(parent)
        self.stream_data = stream_data
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Cover thumbnail
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(COVER_THUMB_W, COVER_THUMB_H)
        self.cover_label.setStyleSheet(
            f"background-color: {COLOR_CARD}; border-radius: 4px;"
        )
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("\U0001F3AC")
        layout.addWidget(self.cover_label)

        # Right side: name + rating
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)

        name = self.stream_data.get("name", "Unknown")
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: 13px; font-weight: 600;"
        )
        self.name_label.setWordWrap(True)
        right_layout.addWidget(self.name_label)

        rating = self.stream_data.get("rating", 0)
        stars = rating_to_stars(rating)
        rating_text = f"{stars}  ({rating})"
        self.rating_label = QLabel(rating_text)
        self.rating_label.setStyleSheet("color: #FFD700; font-size: 12px;")
        right_layout.addWidget(self.rating_label)

        right_layout.addStretch()
        layout.addLayout(right_layout, 1)

    def set_cover(self, pixmap):
        """Cover-Bild setzen."""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                COVER_THUMB_W, COVER_THUMB_H,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            self.cover_label.setPixmap(scaled)


class VodInfoDialog(QDialog):
    """Detail-Ansicht fuer einen VOD-Film."""

    def __init__(self, stream_data, api, player, parent=None):
        super().__init__(parent)
        self.stream_data = stream_data
        self.api = api
        self.player = player
        self.info_data = None
        self.info_thread = None
        self._init_ui()
        self._load_info()

    def _init_ui(self):
        self.setWindowTitle("SMarTrPlay - VOD Details")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(BRAND_QSS)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Top section: cover + details ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)

        # Cover (gross)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(COVER_FULL_W, COVER_FULL_H)
        self.cover_label.setStyleSheet(
            f"background-color: {COLOR_CARD}; border-radius: 8px;"
        )
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("\U0001F3AC")
        top_layout.addWidget(self.cover_label)

        # Details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(8)

        # Titel
        name = self.stream_data.get("name", "Unknown")
        self.title_label = QLabel(name)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setWordWrap(True)
        details_layout.addWidget(self.title_label)

        # Rating
        rating = self.stream_data.get("rating", 0)
        stars = rating_to_stars(rating)
        self.rating_label = QLabel(f"{stars}  ({rating}/10)")
        self.rating_label.setObjectName("ratingLabel")
        details_layout.addWidget(self.rating_label)

        # Meta info (genre, jahr, dauer)
        self.meta_label = QLabel("L\u00e4dt...")
        self.meta_label.setObjectName("metaLabel")
        details_layout.addWidget(self.meta_label)

        # Beschreibung
        desc_section = QLabel("Beschreibung")
        desc_section.setObjectName("sectionLabel")
        details_layout.addWidget(desc_section)

        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMaximumHeight(120)
        self.desc_text.setText("L\u00e4dt...")
        details_layout.addWidget(self.desc_text)

        # Cast
        cast_section = QLabel("Besetzung")
        cast_section.setObjectName("sectionLabel")
        details_layout.addWidget(cast_section)

        self.cast_label = QLabel("L\u00e4dt...")
        self.cast_label.setObjectName("metaLabel")
        self.cast_label.setWordWrap(True)
        details_layout.addWidget(self.cast_label)

        # Regie
        director_section = QLabel("Regie")
        director_section.setObjectName("sectionLabel")
        details_layout.addWidget(director_section)

        self.director_label = QLabel("L\u00e4dt...")
        self.director_label.setObjectName("metaLabel")
        self.director_label.setWordWrap(True)
        details_layout.addWidget(self.director_label)

        details_layout.addStretch()
        top_layout.addLayout(details_layout, 1)
        layout.addLayout(top_layout)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.play_btn = QPushButton("\u25B6  Abspielen")
        self.play_btn.setObjectName("playBtn")
        self.play_btn.clicked.connect(self._on_play)
        btn_layout.addWidget(self.play_btn)

        self.trailer_btn = QPushButton("\u25B6  Trailer")
        self.trailer_btn.setObjectName("trailerBtn")
        self.trailer_btn.clicked.connect(self._on_trailer)
        btn_layout.addWidget(self.trailer_btn)

        self.close_btn = QPushButton("Schlie\u00dfen")
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Cover sofort laden (stream_icon)
        self._load_cover()

    def _load_cover(self):
        """Cover-Bild laden (stream_icon, bei Info-Load durch cover_big ergaenzen)."""
        icon_url = self.stream_data.get("stream_icon", "")
        if icon_url:
            path = cover_cache_path(icon_url)
            if path:
                if not os.path.exists(path):
                    download_cover(icon_url, path)
                if os.path.exists(path):
                    pix = QPixmap(path)
                    if not pix.isNull():
                        scaled = pix.scaled(
                            COVER_FULL_W, COVER_FULL_H,
                            Qt.KeepAspectRatio, Qt.SmoothTransformation,
                        )
                        self.cover_label.setPixmap(scaled)
                        return
        self.cover_label.setText("\U0001F3AC Kein Cover")

    def _load_info(self):
        """VOD Info im Hintergrund laden."""
        vod_id = self.stream_data.get("stream_id")
        if not vod_id:
            return
        self.info_thread = VodInfoLoaderThread(self)
        self.info_thread.finished.connect(self._on_info_loaded)
        self.info_thread.error.connect(self._on_info_error)
        self.info_thread.start(self.api, vod_id)

    def _on_info_loaded(self, info):
        """Wenn VOD Info geladen wurde."""
        self.info_data = info
        info_dict = info.get("info", {})

        # Cover durch cover_big aktualisieren falls verfuegbar
        cover_big = info_dict.get("cover_big", "")
        if cover_big:
            path = cover_cache_path(cover_big)
            if path:
                if not os.path.exists(path):
                    download_cover(cover_big, path)
                if os.path.exists(path):
                    pix = QPixmap(path)
                    if not pix.isNull():
                        scaled = pix.scaled(
                            COVER_FULL_W, COVER_FULL_H,
                            Qt.KeepAspectRatio, Qt.SmoothTransformation,
                        )
                        self.cover_label.setPixmap(scaled)

        # Meta info zusammenstellen
        genre = info_dict.get("genre", "") or ""
        duration = info_dict.get("duration", "") or ""

        year = ""
        added = self.stream_data.get("added", "")
        if added:
            try:
                year = str(datetime.datetime.fromtimestamp(int(added)).year)
            except (ValueError, TypeError, OSError):
                pass

        meta_parts = []
        if genre:
            meta_parts.append(f"Genre: {genre}")
        if year:
            meta_parts.append(f"Jahr: {year}")
        if duration:
            meta_parts.append(f"Dauer: {duration}")
        self.meta_label.setText(
            "  |  ".join(meta_parts) if meta_parts else "Keine Metadata"
        )

        # Beschreibung
        desc = info_dict.get("description", "") or "Keine Beschreibung verf\u00fcgbar."
        self.desc_text.setText(desc)

        # Cast
        cast = info_dict.get("cast", "") or "Keine Informationen"
        self.cast_label.setText(cast)

        # Regie
        director = info_dict.get("director", "") or "Keine Informationen"
        self.director_label.setText(director)

    def _on_info_error(self, err):
        """Bei Fehler beim Laden der Info."""
        self.meta_label.setText("Fehler beim Laden der Details")
        self.desc_text.setText(f"Fehler: {err}")

    def _on_play(self):
        """Film abspielen mit ffplay ueber PlayerBackend."""
        stream_id = self.stream_data.get("stream_id")
        container_ext = self.stream_data.get("container_extension", "mp4")
        if not stream_id:
            return
        url = self.api.get_stream_url(stream_id, "vod", container_ext)
        self.player.play(url)

    def _on_trailer(self):
        """Trailer im Browser oeffnen (xdg-open YouTube)."""
        trailer = self.stream_data.get("trailer", "")
        if not trailer and self.info_data:
            trailer = self.info_data.get("info", {}).get("trailer", "")
        if trailer:
            url = f"https://www.youtube.com/watch?v={trailer}"
        else:
            # Fallback: YouTube-Suche nach Filmtitel + trailer
            name = self.stream_data.get("name", "")
            if not name:
                return
            url = f"https://www.youtube.com/results?search_query={name}+trailer"
        try:
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def closeEvent(self, event):
        """Cleanup beim Schlie\u00dfen."""
        if self.info_thread and self.info_thread.isRunning():
            self.info_thread.quit()
            self.info_thread.wait(3000)
        super().closeEvent(event)


class VodBrowser(QDialog):
    """Hauptdialog VOD Browser mit Kategorien, Filmen und Suche."""

    def __init__(self, api, player=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.player = player or PlayerBackend()
        self.categories = []
        self.current_streams = []
        self.loader_thread = None
        self.cover_thread = None
        self._item_widgets = {}

        self._init_ui()
        self._load_categories()

    def _init_ui(self):
        self.setWindowTitle("SMarTrPlay - VOD Browser")
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(BRAND_QSS)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QLabel("\U0001F3AC  VOD Filme")
        header.setStyleSheet(
            f"color: {COLOR_CYAN}; font-size: 18px; font-weight: 700;"
        )
        layout.addWidget(header)

        # Suchfeld
        search_layout = QHBoxLayout()
        search_label = QLabel("\U0001F50D")
        search_label.setStyleSheet("font-size: 16px;")
        search_layout.addWidget(search_label)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Filme suchen...")
        self.search_field.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_field)
        layout.addLayout(search_layout)

        # Splitter: Kategorien | Filme
        splitter = QSplitter(Qt.Horizontal)

        # Links: Kategorien
        self.cat_list = QListWidget()
        self.cat_list.setMinimumWidth(200)
        self.cat_list.setMaximumWidth(300)
        self.cat_list.itemClicked.connect(self._on_category_clicked)
        splitter.addWidget(self.cat_list)

        # Rechts: Filme
        self.movie_list = QListWidget()
        self.movie_list.setSpacing(2)
        self.movie_list.setResizeMode(QListWidget.Adjust)
        self.movie_list.itemDoubleClicked.connect(self._on_movie_double_click)
        splitter.addWidget(self.movie_list)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        # Status-Leiste
        self.status_label = QLabel("Bereit")
        self.status_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 12px;"
        )
        layout.addWidget(self.status_label)

        # Progress-Bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Cover-Loader Thread
        self.cover_thread = CoverLoaderThread(self)
        self.cover_thread.cover_ready.connect(self._on_cover_ready)

    def _load_categories(self):
        """VOD Kategorien laden."""
        self.status_label.setText("Lade Kategorien...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        try:
            self.categories = self.api.get_vod_categories() or []
            self.cat_list.clear()
            for cat in self.categories:
                cat_id = cat.get("category_id", "")
                cat_name = cat.get("category_name", "Unknown")
                item = QListWidgetItem(cat_name)
                item.setData(Qt.UserRole, cat_id)
                self.cat_list.addItem(item)
            self.status_label.setText(f"{len(self.categories)} Kategorien geladen")
        except Exception as e:
            self.status_label.setText(f"Fehler: {e}")
        finally:
            self.progress.setVisible(False)

    def _on_category_clicked(self, item):
        """Wenn eine Kategorie ausgewaehlt wird."""
        cat_id = item.data(Qt.UserRole)
        self._load_streams(cat_id)

    def _load_streams(self, category_id):
        """VOD Streams fuer eine Kategorie laden (im Hintergrund)."""
        self.status_label.setText("Lade Filme...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.movie_list.clear()
        self._item_widgets.clear()

        # Vorherigen Loader stoppen
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.quit()
            self.loader_thread.wait(3000)

        self.loader_thread = VodLoaderThread(self)
        self.loader_thread.finished.connect(self._on_streams_loaded)
        self.loader_thread.error.connect(self._on_streams_error)
        self.loader_thread.start(self.api, category_id)

    def _on_streams_loaded(self, streams):
        """Wenn Streams geladen wurden."""
        self.current_streams = streams
        self.progress.setVisible(False)

        if not streams:
            self.status_label.setText("Keine Filme in dieser Kategorie")
            return

        self.movie_list.setUpdatesEnabled(False)
        cover_urls = []

        for stream in streams:
            stream_id = stream.get("stream_id", "")
            icon_url = stream.get("stream_icon", "")

            item = QListWidgetItem()
            item.setData(Qt.UserRole, stream)

            widget = VodListItemWidget(stream)
            item.setSizeHint(widget.sizeHint())
            self.movie_list.addItem(item)
            self.movie_list.setItemWidget(item, widget)

            self._item_widgets[stream_id] = widget

            if icon_url:
                cover_urls.append(icon_url)

        self.movie_list.setUpdatesEnabled(True)
        self.status_label.setText(f"{len(streams)} Filme geladen")

        # Covers im Hintergrund laden
        if cover_urls:
            self.cover_thread.load_covers(cover_urls)

    def _on_streams_error(self, err):
        """Bei Fehler beim Laden der Streams."""
        self.progress.setVisible(False)
        self.status_label.setText(f"Fehler: {err}")

    def _on_cover_ready(self, url, pixmap):
        """Wenn ein Cover-Bild geladen wurde."""
        for stream_id, widget in self._item_widgets.items():
            stream = widget.stream_data
            if stream.get("stream_icon") == url:
                widget.set_cover(pixmap)
                break

    def _on_search(self, text):
        """Filme nach Suchbegriff filtern."""
        text = text.lower().strip()
        for i in range(self.movie_list.count()):
            item = self.movie_list.item(i)
            stream = item.data(Qt.UserRole)
            name = stream.get("name", "").lower()
            item.setHidden(bool(text) and text not in name)

    def _on_movie_double_click(self, item):
        """Film-Details in VodInfoDialog anzeigen."""
        stream = item.data(Qt.UserRole)
        dialog = VodInfoDialog(stream, self.api, self.player, self)
        dialog.exec_()

    def closeEvent(self, event):
        """Cleanup beim Schlie\u00dfen."""
        if self.cover_thread:
            self.cover_thread.stop()
            self.cover_thread.quit()
            self.cover_thread.wait(3000)
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.quit()
            self.loader_thread.wait(3000)
        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyleSheet(BRAND_QSS)

    # Demo: XtreamAPI mit Platzhalter-Werten
    api = XtreamAPI(
        "http://example.com:8080",
        "demo_user",
        "demo_pass",
    )
    browser = VodBrowser(api)
    browser.exec_()
