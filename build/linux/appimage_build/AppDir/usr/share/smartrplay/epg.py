#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMarTrPlay EPG Module — EPG-Datenabruf, SQLite-Caching und PyQt5 Widget
fuer SMarTrPlay (SMartrAgents IPTV Overlay System)

Features:
  - Xtream API EPG-Abfrage (get_live_stream_epg, get_short_epg)
  - SQLite-Caching mit TTL-Ablauf
  - PyQt5 EPG-Widget mit SMarTr Brand Design
  - Dark Mode #0A0F1E, Inter Font, Cyan/Violet Akzente

Kompatibel mit /usr/bin/python3 und PyQt5.

Author: SMartrAgents.ai
"""

import json
import sqlite3
import time
import logging
import threading
import argparse
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

# PyQt5 imports
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy
)

# --- Konstanten -----------------------------------------------------------------

MODULE_VERSION = "1.0.0"
MODULE_NAME = "SMarTrPlay-EPG"

# SMartr Brand Design Colors
SMARTR_BG_DARK = "#0A0F1E"
SMARTR_BG_DARKER = "#060A14"
SMARTR_BG_CARD = "#111827"
SMARTR_BG_CARD_HOVER = "#1A2332"
SMARTR_CYAN = "#00D9FF"
SMARTR_CYAN_DIM = "#0099BB"
SMARTR_VIOLET = "#7B61FF"
SMARTR_VIOLET_DIM = "#5A42CC"
SMARTR_TEXT_PRIMARY = "#E8ECF4"
SMARTR_TEXT_SECONDARY = "#8896A8"
SMARTR_TEXT_MUTED = "#5A6B7E"
SMARTR_BORDER = "#1E2A3E"
SMARTR_GREEN = "#22C55E"
SMARTR_RED = "#EF4444"

# Cache-Einstellungen
DEFAULT_CACHE_DB = Path.home() / ".smartr" / "smartr_epg_cache.db"
CACHE_TTL_DEFAULT = 3600  # 1 Stunde in Sekunden

# API-Einstellungen
API_TIMEOUT = 15  # Sekunden
API_USER_AGENT = f"SMarTrPlay/{MODULE_VERSION}"

# Logger
logger = logging.getLogger(MODULE_NAME)


# --- Hilfsfunktionen -------------------------------------------------------------

def _iso_to_local(iso_str: str) -> datetime:
    """Konvertiere ISO-8601 Timestamp zu lokalem datetime."""
    if not iso_str:
        return datetime.now()
    try:
        dt = datetime.strptime(iso_str.strip(), "%Y-%m-%d %H:%M:%S")
        return dt
    except (ValueError, AttributeError):
        try:
            dt = datetime.fromisoformat(iso_str.strip().replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone()
            return dt.replace(tzinfo=None)
        except (ValueError, AttributeError):
            return datetime.now()


def _ts_to_local(ts: str) -> datetime:
    """Konvertiere Unix-Timestamp (String/Int) zu lokalem datetime."""
    try:
        return datetime.fromtimestamp(int(ts))
    except (ValueError, TypeError, OSError):
        return datetime.now()


def _format_time(dt: datetime) -> str:
    """Formatiere datetime zu HH:MM."""
    return dt.strftime("%H:%M")


def _format_date(dt: datetime) -> str:
    """Formatiere datetime zu DD.MM. HH:MM."""
    return dt.strftime("%d.%m. %H:%M")


def _is_now(start_dt: datetime, stop_dt: datetime) -> bool:
    """Pruefe ob eine Sendung aktuell laeuft."""
    now = datetime.now()
    return start_dt <= now <= stop_dt


# --- EPG-Datenmodell ------------------------------------------------------------

class EpgEntry:
    """Repraesentiert eine einzelne EPG-Sendung."""
    __slots__ = ("title", "description", "start", "stop", "start_ts", "stop_ts")

    def __init__(self, title: str = "", description: str = "",
                 start: str = "", stop: str = "",
                 start_ts: str = "", stop_ts: str = ""):
        self.title = title or "Unbekannt"
        self.description = description or ""
        self.start = start
        self.stop = stop
        self.start_ts = start_ts
        self.stop_ts = stop_ts

    @property
    def start_dt(self) -> datetime:
        """Start als datetime-Objekt."""
        if self.start_ts:
            return _ts_to_local(self.start_ts)
        return _iso_to_local(self.start)

    @property
    def stop_dt(self) -> datetime:
        """Stop als datetime-Objekt."""
        if self.stop_ts:
            return _ts_to_local(self.stop_ts)
        return _iso_to_local(self.stop)

    @property
    def is_now(self) -> bool:
        """Laeuft diese Sendung aktuell?"""
        return _is_now(self.start_dt, self.stop_dt)

    @property
    def is_past(self) -> bool:
        """Liegt diese Sendung in der Vergangenheit?"""
        return self.stop_dt < datetime.now()

    @property
    def is_future(self) -> bool:
        """Liegt diese Sendung in der Zukunft?"""
        return self.start_dt > datetime.now()

    @property
    def time_label(self) -> str:
        """Zeit-Beschriftung: HH:MM - HH:MM"""
        return f"{_format_time(self.start_dt)} \u2013 {_format_time(self.stop_dt)}"

    def to_dict(self) -> Dict[str, str]:
        """Serialisiere zu Dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "start": self.start,
            "stop": self.stop,
            "start_ts": self.start_ts,
            "stop_ts": self.stop_ts,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EpgEntry":
        """Deserialisiere aus Dictionary."""
        return cls(
            title=d.get("title", ""),
            description=d.get("description", ""),
            start=d.get("start", ""),
            stop=d.get("stop", ""),
            start_ts=str(d.get("start_ts", "")),
            stop_ts=str(d.get("stop_ts", "")),
        )

    def __repr__(self):
        return f"EpgEntry(title={self.title!r}, start={self.time_label})"


# --- Xtream EPG API Client ------------------------------------------------------

class XtreamEpgClient:
    """
    HTTP Client fuer Xtream Codes API EPG-Endpunkte.
    Nutzt urllib aus der Standardbibliothek - keine externen Abhaengigkeiten.
    """

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._api_url = f"{self.base_url}/player_api.php"

    def _build_url(self, action: str, extra_params: Optional[Dict[str, str]] = None) -> str:
        """Erstelle API-URL mit Query-Parametern."""
        params = {
            "username": self.username,
            "password": self.password,
            "action": action,
        }
        if extra_params:
            params.update(extra_params)
        return f"{self._api_url}?{urlencode(params)}"

    def _fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """Fuehre HTTP GET aus und parse JSON-Antwort."""
        try:
            req = Request(url, headers={"User-Agent": API_USER_AGENT})
            with urlopen(req, timeout=API_TIMEOUT) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            return json.loads(data)
        except (URLError, HTTPError, json.JSONDecodeError, OSError) as exc:
            logger.error(f"API-Fehler fuer {url}: {exc}")
            return None

    @staticmethod
    def _parse_epg_listings(data: Optional[Dict[str, Any]]) -> List[EpgEntry]:
        """Extrahiere EpgEntry-Liste aus API-Antwort."""
        if not data or not isinstance(data, dict):
            return []
        listings = data.get("epg_listings", [])
        if not listings or not isinstance(listings, list):
            return []
        entries = []
        for item in listings:
            if not isinstance(item, dict):
                continue
            entry = EpgEntry(
                title=item.get("title", ""),
                description=item.get("description", ""),
                start=item.get("start", ""),
                stop=item.get("stop", ""),
                start_ts=str(item.get("start_timestamp", "")),
                stop_ts=str(item.get("stop_timestamp", "")),
            )
            entries.append(entry)
        return entries

    def get_live_stream_epg(self, stream_id: int) -> List[EpgEntry]:
        """
        Hole vollstaendige EPG-Liste fuer einen Live-Stream.
        Xtream API Action: get_live_stream_epg
        """
        url = self._build_url("get_live_stream_epg", {"stream_id": str(stream_id)})
        logger.debug(f"get_live_stream_epg: stream_id={stream_id}")
        data = self._fetch(url)
        return self._parse_epg_listings(data)

    def get_short_epg(self, stream_id: int) -> List[EpgEntry]:
        """
        Hole kurze EPG-Liste (aktuelle + naechste Sendung) fuer einen Live-Stream.
        Xtream API Action: get_short_epg
        """
        url = self._build_url("get_short_epg", {"stream_id": str(stream_id)})
        logger.debug(f"get_short_epg: stream_id={stream_id}")
        data = self._fetch(url)
        return self._parse_epg_listings(data)


# --- SQLite EPG Cache -----------------------------------------------------------

class EpgCache:
    """
    SQLite-basierter Cache fuer EPG-Daten mit TTL-Ablauf.
    Thread-safe durch Lock und Connection-Isolation.
    """

    def __init__(self, db_path: Optional[Path] = None, ttl: int = CACHE_TTL_DEFAULT):
        self.db_path = Path(db_path) if db_path else DEFAULT_CACHE_DB
        self.ttl = ttl
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialisiere SQLite-Datenbank und Tabelle."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epg_cache (
                    stream_id   INTEGER NOT NULL,
                    cache_type  TEXT    NOT NULL,
                    entries     TEXT    NOT NULL,
                    cached_at   REAL    NOT NULL,
                    PRIMARY KEY (stream_id, cache_type)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epg_stream
                ON epg_cache(stream_id)
            """)
            conn.commit()
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        """Erstelle neue SQLite-Verbindung (thread-safe)."""
        conn = sqlite3.connect(str(self.db_path), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    def get(self, stream_id: int, cache_type: str) -> Optional[List[EpgEntry]]:
        """
        Hole EPG-Daten aus Cache wenn nicht abgelaufen.
        cache_type: 'full' oder 'short'
        """
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                "SELECT entries, cached_at FROM epg_cache WHERE stream_id=? AND cache_type=?",
                (stream_id, cache_type)
            )
            row = cursor.fetchone()
            conn.close()

        if not row:
            return None

        cached_at = row[1]
        if (time.time() - cached_at) > self.ttl:
            logger.debug(f"Cache abgelaufen: stream_id={stream_id}, type={cache_type}")
            return None

        try:
            raw_list = json.loads(row[0])
            return [EpgEntry.from_dict(d) for d in raw_list]
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(f"Cache-Deserialisierung fehlgeschlagen: {exc}")
            return None

    def set(self, stream_id: int, cache_type: str, entries: List[EpgEntry]):
        """Speichere EPG-Daten im Cache."""
        raw = json.dumps([e.to_dict() for e in entries], ensure_ascii=False)
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT OR REPLACE INTO epg_cache (stream_id, cache_type, entries, cached_at) "
                "VALUES (?, ?, ?, ?)",
                (stream_id, cache_type, raw, time.time())
            )
            conn.commit()
            conn.close()

    def invalidate(self, stream_id: int, cache_type: Optional[str] = None):
        """Loesche Cache-Eintraege fuer einen Stream."""
        with self._lock:
            conn = self._connect()
            if cache_type:
                conn.execute(
                    "DELETE FROM epg_cache WHERE stream_id=? AND cache_type=?",
                    (stream_id, cache_type)
                )
            else:
                conn.execute(
                    "DELETE FROM epg_cache WHERE stream_id=?",
                    (stream_id,)
                )
            conn.commit()
            conn.close()

    def cleanup_expired(self):
        """Entferne alle abgelaufenen Cache-Eintraege."""
        cutoff = time.time() - self.ttl
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM epg_cache WHERE cached_at < ?", (cutoff,))
            conn.commit()
            conn.close()

    def get_age(self, stream_id: int, cache_type: str) -> Optional[int]:
        """Alter des Cache-Eintrags in Sekunden (None wenn nicht vorhanden)."""
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                "SELECT cached_at FROM epg_cache WHERE stream_id=? AND cache_type=?",
                (stream_id, cache_type)
            )
            row = cursor.fetchone()
            conn.close()
        if not row:
            return None
        return int(time.time() - row[0])


# --- EPG Service (API + Cache kombiniert) ---------------------------------------

class EpgService:
    """
    Kombiniert Xtream API Client und SQLite Cache.
    Liefert EPG-Daten aus Cache (falls gueltig) oder von API.
    """

    def __init__(self, base_url: str, username: str, password: str,
                 cache_path: Optional[Path] = None, cache_ttl: int = CACHE_TTL_DEFAULT):
        self.client = XtreamEpgClient(base_url, username, password)
        self.cache = EpgCache(cache_path, cache_ttl)

    def get_live_stream_epg(self, stream_id: int, force_refresh: bool = False) -> List[EpgEntry]:
        """Hole volle EPG-Liste (Cache-gestuetzt)."""
        if not force_refresh:
            cached = self.cache.get(stream_id, "full")
            if cached is not None:
                logger.debug(f"EPG (full) aus Cache: stream_id={stream_id}")
                return cached
        entries = self.client.get_live_stream_epg(stream_id)
        if entries:
            self.cache.set(stream_id, "full", entries)
        return entries

    def get_short_epg(self, stream_id: int, force_refresh: bool = False) -> List[EpgEntry]:
        """Hole kurze EPG-Liste (Cache-gestuetzt)."""
        if not force_refresh:
            cached = self.cache.get(stream_id, "short")
            if cached is not None:
                logger.debug(f"EPG (short) aus Cache: stream_id={stream_id}")
                return cached
        entries = self.client.get_short_epg(stream_id)
        if entries:
            self.cache.set(stream_id, "short", entries)
        return entries

    def refresh(self, stream_id: int, full: bool = True) -> List[EpgEntry]:
        """Erzwinge API-Refresh fuer einen Stream."""
        if full:
            self.cache.invalidate(stream_id, "full")
            return self.get_live_stream_epg(stream_id, force_refresh=True)
        else:
            self.cache.invalidate(stream_id, "short")
            return self.get_short_epg(stream_id, force_refresh=True)


# --- PyQt5 EPG Widget -----------------------------------------------------------

def _smartr_label(text: str, font_size: int = 12, color: str = SMARTR_TEXT_PRIMARY,
                  bold: bool = False, parent: Optional[QWidget] = None) -> QLabel:
    """Erstelle ein QLabel mit SMarTr Brand-Styling."""
    lbl = QLabel(text, parent)
    font = QFont("Inter", font_size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


class EpgCard(QFrame):
    """Einzelne EPG-Sendungs-Karte im SMarTr Design."""

    clicked_signal = pyqtSignal(object)  # Emit EpgEntry

    def __init__(self, entry: EpgEntry, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self._setup_ui()

    def _setup_ui(self):
        """Erstelle Karten-Layout."""
        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName("EpgCard")

        if self.entry.is_now:
            border_color = SMARTR_CYAN
            bg = SMARTR_BG_CARD
            accent = SMARTR_CYAN
            badge = "\u25CF JETZT"
            badge_color = SMARTR_GREEN
        elif self.entry.is_past:
            border_color = SMARTR_BORDER
            bg = SMARTR_BG_DARKER
            accent = SMARTR_TEXT_MUTED
            badge = ""
            badge_color = SMARTR_TEXT_MUTED
        else:
            border_color = SMARTR_BORDER
            bg = SMARTR_BG_CARD
            accent = SMARTR_VIOLET
            badge = "UPCOMING"
            badge_color = SMARTR_VIOLET

        self.setStyleSheet(f"""
            QFrame#EpgCard {{
                background-color: {bg};
                border: 1px solid {border_color};
                border-left: 3px solid {accent};
                border-radius: 8px;
            }}
            QFrame#EpgCard:hover {{
                background-color: {SMARTR_BG_CARD_HOVER};
                border-left: 3px solid {accent};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Linke Spalte: Zeit
        time_layout = QVBoxLayout()
        time_layout.setSpacing(2)

        self.start_label = _smartr_label(
            _format_time(self.entry.start_dt),
            font_size=16, color=accent, bold=True
        )
        self.start_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self.start_label)

        self.duration_label = _smartr_label(
            "\u2013", font_size=10, color=SMARTR_TEXT_MUTED
        )
        self.duration_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self.duration_label)

        self.stop_label = _smartr_label(
            _format_time(self.entry.stop_dt),
            font_size=12, color=SMARTR_TEXT_SECONDARY
        )
        self.stop_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self.stop_label)

        layout.addLayout(time_layout)

        # Vertikale Trennlinie
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet(
            f"color: {SMARTR_BORDER}; background: {SMARTR_BORDER}; max-width: 1px;"
        )
        separator.setFixedWidth(1)
        layout.addWidget(separator)

        # Mittlere Spalte: Titel + Beschreibung
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Titel + Badge Zeile
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        self.title_label = _smartr_label(
            self.entry.title, font_size=14, bold=True
        )
        if self.entry.is_past:
            self.title_label.setStyleSheet(
                f"color: {SMARTR_TEXT_MUTED}; background: transparent;"
            )
        title_row.addWidget(self.title_label, 1)

        if badge:
            self.badge_label = _smartr_label(
                badge, font_size=9, color=badge_color, bold=True
            )
            self.badge_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            title_row.addWidget(self.badge_label)
        else:
            self.badge_label = None

        info_layout.addLayout(title_row)

        # Beschreibung (gekuerzt)
        desc_text = self.entry.description or ""
        if len(desc_text) > 120:
            desc_text = desc_text[:117] + "..."
        self.desc_label = _smartr_label(
            desc_text or "Keine Beschreibung verfuegbar",
            font_size=11, color=SMARTR_TEXT_SECONDARY
        )
        self.desc_label.setWordWrap(True)
        info_layout.addWidget(self.desc_label)

        layout.addLayout(info_layout, 1)

        # Groesse
        self.setMinimumHeight(72)
        self.setMaximumHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def mousePressEvent(self, event):
        """Klick-Event weiterleiten."""
        if event.button() == Qt.LeftButton:
            self.clicked_signal.emit(self.entry)
        super().mousePressEvent(event)


class EpgWidget(QWidget):
    """
    Haupt-EPG-Widget: Scrollbare Liste von Sendungen mit SMarTr Brand Design.
    """

    entry_clicked = pyqtSignal(object)  # Emit EpgEntry

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._entries: List[EpgEntry] = []
        self._cards: List[EpgCard] = []
        self._auto_refresh_timer: Optional[QTimer] = None
        self._setup_ui()

    def _setup_ui(self):
        """Erstelle Widget-UI."""
        self.setObjectName("EpgWidget")
        self.setStyleSheet(f"""
            QWidget#EpgWidget {{
                background-color: {SMARTR_BG_DARK};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header_frame = QFrame()
        header_frame.setFixedHeight(44)
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {SMARTR_BG_DARKER};
                border-bottom: 1px solid {SMARTR_BORDER};
            }}
        """)

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(8)

        self.header_title = _smartr_label(
            "EPG", font_size=14, color=SMARTR_CYAN, bold=True
        )
        header_layout.addWidget(self.header_title)

        header_layout.addStretch()

        self.status_label = _smartr_label("", font_size=10, color=SMARTR_TEXT_MUTED)
        header_layout.addWidget(self.status_label)

        main_layout.addWidget(header_frame)

        # Scrollbare Liste
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {SMARTR_BG_DARK};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {SMARTR_BG_DARKER};
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {SMARTR_CYAN_DIM};
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {SMARTR_CYAN};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet(f"background-color: {SMARTR_BG_DARK};")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()

        self.scroll_area.setWidget(self.list_container)
        main_layout.addWidget(self.scroll_area, 1)

        # Empty State Label (initial sichtbar)
        self._empty_label = _smartr_label(
            "Keine EPG-Daten verfuegbar",
            font_size=13, color=SMARTR_TEXT_MUTED
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list_layout.insertWidget(0, self._empty_label)

    def set_entries(self, entries: List[EpgEntry]):
        """Aktualisiere die EPG-Liste."""
        self._entries = entries
        self._rebuild_cards()

    def _rebuild_cards(self):
        """Baue Karten neu auf."""
        self._clear_cards()

        if not self._entries:
            self._empty_label.show()
            self.status_label.setText("")
            return

        self._empty_label.hide()

        # Sortiere nach Startzeit
        sorted_entries = sorted(self._entries, key=lambda e: e.start_dt)

        # Finde aktuelle Sendung fuer Status
        current = None
        for entry in sorted_entries:
            if entry.is_now:
                current = entry
                break

        if current:
            status_text = current.title[:40]
            self.status_label.setText(f"\u25CF {status_text}")
            self.status_label.setStyleSheet(
                f"color: {SMARTR_GREEN}; background: transparent; font-size: 10px;"
            )
        else:
            self.status_label.setText(f"{len(sorted_entries)} Sendungen")
            self.status_label.setStyleSheet(
                f"color: {SMARTR_TEXT_MUTED}; background: transparent; font-size: 10px;"
            )

        # Karten erstellen (vor dem stretch)
        for entry in sorted_entries:
            card = EpgCard(entry, self.list_container)
            card.clicked_signal.connect(self._on_card_clicked)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            self._cards.append(card)

    def _clear_cards(self):
        """Entferne alle Karten."""
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

    def _on_card_clicked(self, entry: EpgEntry):
        """Klick auf eine EPG-Karte."""
        self.entry_clicked.emit(entry)

    def set_loading(self, loading: bool):
        """Zeige Ladezustand an."""
        if loading:
            self.status_label.setText("Lade...")
            self.status_label.setStyleSheet(
                f"color: {SMARTR_CYAN}; background: transparent; font-size: 10px;"
            )
        else:
            self._rebuild_cards()

    def start_auto_refresh(self, interval_ms: int = 60000):
        """Starte automatische Aktualisierung der EPG-Anzeige."""
        if self._auto_refresh_timer is None:
            self._auto_refresh_timer = QTimer(self)
            self._auto_refresh_timer.timeout.connect(self._refresh_display)
        self._auto_refresh_timer.start(interval_ms)

    def stop_auto_refresh(self):
        """Stoppe automatische Aktualisierung."""
        if self._auto_refresh_timer:
            self._auto_refresh_timer.stop()

    def _refresh_display(self):
        """Aktualisiere Anzeige (Badges neu berechnen) ohne API-Call."""
        if self._entries:
            self._rebuild_cards()

    def clear(self):
        """Leere die EPG-Liste."""
        self._entries = []
        self._clear_cards()
        self._empty_label.show()
        self.status_label.setText("")

    def cleanup(self):
        """Aufraeumen beim Schliessen."""
        self.stop_auto_refresh()
        self._clear_cards()


# --- Self-Test -------------------------------------------------------------------

def _run_self_test():
    """Minimaler Self-Test ohne GUI (fuer py_compile und Modul-Import)."""
    print(f"{MODULE_NAME} v{MODULE_VERSION} - Self-Test")
    print("=" * 50)

    # EpgEntry Tests
    entry = EpgEntry(
        title="Test Sendung",
        description="Eine Beschreibung",
        start_ts=str(int(time.time()) - 1800),
        stop_ts=str(int(time.time()) + 1800),
    )
    assert entry.title == "Test Sendung"
    assert entry.is_now
    assert not entry.is_past
    assert not entry.is_future
    assert "\u2013" in entry.time_label
    print(f"  EpgEntry: title={entry.title}, time={entry.time_label}, is_now={entry.is_now}")

    # Serialisierung
    d = entry.to_dict()
    entry2 = EpgEntry.from_dict(d)
    assert entry2.title == entry.title
    print("  Serialisierung: round-trip ok")

    # Cache Test (temp DB)
    tmp_db = Path(tempfile.mkdtemp()) / "test_epg.db"
    cache = EpgCache(tmp_db, ttl=60)

    sid = 12345
    assert cache.get(sid, "full") is None
    print("  Cache: leer bei neuem stream_id")

    cache.set(sid, "full", [entry])
    cached = cache.get(sid, "full")
    assert cached is not None
    assert len(cached) == 1
    assert cached[0].title == "Test Sendung"
    print("  Cache: store + retrieve ok")

    cache.invalidate(sid, "full")
    assert cache.get(sid, "full") is None
    print("  Cache: invalidate ok")

    # Aufraeumen
    tmp_db.unlink(missing_ok=True)
    tmp_db.parent.rmdir()

    print("=" * 50)
    print("  Alle Tests bestanden")
    return True


def _run_gui_demo():
    """Demo-GUI (nur bei direktem Aufruf mit --gui)."""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setFont(QFont("Inter", 10))

    widget = EpgWidget()

    # Demo-Daten
    now = datetime.now()
    demo_entries = [
        EpgEntry(
            title="Nachrichten",
            description="Aktuelle Nachrichten und Wetter",
            start_ts=str(int(now.timestamp()) - 3600),
            stop_ts=str(int(now.timestamp()) - 1800),
        ),
        EpgEntry(
            title="Live: Fussball Bundesliga",
            description="Bayern Muenchen vs. Borussia Dortmund - Spieltag 15",
            start_ts=str(int(now.timestamp()) - 900),
            stop_ts=str(int(now.timestamp()) + 2700),
        ),
        EpgEntry(
            title="Doku: Das Universum",
            description="Eine Reise durch die Galaxien und Schwarze Loecher.",
            start_ts=str(int(now.timestamp()) + 2700),
            stop_ts=str(int(now.timestamp()) + 5400),
        ),
        EpgEntry(
            title="Late Night Show",
            description="Gaeste, Musik und Comedy bis Mitternacht.",
            start_ts=str(int(now.timestamp()) + 5400),
            stop_ts=str(int(now.timestamp()) + 9000),
        ),
    ]

    widget.set_entries(demo_entries)
    widget.resize(420, 500)
    widget.setWindowTitle(f"{MODULE_NAME} - EPG Demo")
    widget.show()

    sys.exit(app.exec_())


# --- Modul-Exporte --------------------------------------------------------------

__all__ = [
    "EpgEntry",
    "XtreamEpgClient",
    "EpgCache",
    "EpgService",
    "EpgCard",
    "EpgWidget",
]

__version__ = MODULE_VERSION


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{MODULE_NAME} - EPG Modul")
    parser.add_argument("--test", action="store_true", help="Fuehre Self-Test aus")
    parser.add_argument("--gui", action="store_true", help="Starte Demo-GUI")
    args = parser.parse_args()

    if args.gui:
        _run_gui_demo()
    else:
        _run_self_test()
