#!/usr/bin/env python3
"""SMarTrPlay - Configuration Manager"""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Config:
    """Zentrale Konfiguration für SMarTrPlay."""

    APP_NAME = "SMarTrPlay"
    APP_VERSION = "1.0.0"
    APP_AUTHOR = "SMarTrAgents"

    # Pfade
    HOME = Path.home()
    CONFIG_DIR = HOME / "SMarTrPlay"
    DB_PATH = CONFIG_DIR / "smartrplay.db"
    CACHE_DIR = CONFIG_DIR / "cache"
    LOG_DIR = CONFIG_DIR / "logs"

    # Player Defaults
    PLAYER_VOLUME = 80
    PLAYER_HWDEC = True
    PLAYER_CACHE_SECS = 10

    # Playlist Defaults
    PLAYLIST_REFRESH_HOURS = 24

    # Brand Colors (SMarTr Brand Standard)
    COLOR_BG_DEEP = "#0A0F1E"
    COLOR_BG_CARD = "#121A2E"
    COLOR_BG_CARD_HOVER = "#1A2540"
    COLOR_BORDER = "#232D45"
    COLOR_BORDER_LIGHT = "#2A3550"
    COLOR_TEXT_PRIMARY = "#F5F7FA"
    COLOR_TEXT_SECONDARY = "#9BA5B7"
    COLOR_TEXT_MUTED = "#6B7280"
    COLOR_ACCENT_CYAN = "#1bf1fb"
    COLOR_ACCENT_PURPLE = "#8D7CF6"
    COLOR_ACCENT_VIOLET = "#371689"
    COLOR_SUCCESS = "#10B981"
    COLOR_WARNING = "#F59E0B"
    COLOR_ERROR = "#EF4444"

    # Font
    FONT_FAMILY = "Inter"
    FONT_FALLBACK = "DejaVu Sans"

    def __init__(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _verbindung(self):
        """Zentrale Datenbankverbindung als Kontextmanager.

        Öffnet die Verbindung zu self.DB_PATH und schließt sie in jedem
        Fall wieder, auch wenn mitten in der Arbeit ein Fehler auftritt.
        Die Pragmas bereiten die Datenbank auf den gleichzeitigen Betrieb
        von Ladefäden und Oberfläche vor:

        - journal_mode=WAL erlaubt Lesen während eines Schreibvorgangs
        - busy_timeout=3000 wartet bis zu drei Sekunden auf Sperren,
          bevor der Fehler "database is locked" gemeldet wird
        - foreign_keys=ON erzwingt die deklarierten Referenzen

        Im Erfolgsfall wird committet, bei einem Fehler zurückgerollt.
        Das Schließen passiert im finally-Block garantiert immer.
        """
        conn = sqlite3.connect(str(self.DB_PATH), timeout=5)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=3000")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """SQLite Datenbank initialisieren.

        Legt fehlende Tabellen an. Bei einer bereits bestehenden Datenbank
        laufen dieselben Anweisungen ohne Schaden durch (IF NOT EXISTS) und
        tragen die Indizes sowie die Spalte vollstaendig nach, damit auch
        alte Datenbanken ohne manuellen Eingriff den aktuellen Stand
        erreichen. Es werden niemals Daten gelöscht oder Tabellen neu
        aufgebaut.
        """
        with self._verbindung() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    url TEXT,
                    username TEXT,
                    password TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    logo TEXT,
                    category TEXT,
                    tvg_id TEXT,
                    tvg_name TEXT,
                    type TEXT DEFAULT 'live',
                    FOREIGN KEY (provider_id) REFERENCES providers(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    channel_id INTEGER PRIMARY KEY,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_meta (
                    provider_id INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    channel_count INTEGER DEFAULT 0,
                    vollstaendig INTEGER DEFAULT 1,
                    PRIMARY KEY (provider_id, content_type),
                    FOREIGN KEY (provider_id) REFERENCES providers(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_id INTEGER NOT NULL,
                    category_id TEXT,
                    category_name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    FOREIGN KEY (provider_id) REFERENCES providers(id)
                )
            """)

            # Indizes für die häufigsten Abfragen. Ohne sie muss SQLite bei
            # jedem Kanalklick die gesamte Tabelle durchlesen (SCAN channels).
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channels_provider_type
                ON channels(provider_id, type, category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channels_provider_name
                ON channels(provider_id, name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channels_category
                ON channels(category)
            """)

            # Spalte vollstaendig nachtragen, falls sie in einer älteren
            # Datenbank noch fehlt. Vorher per PRAGMA table_info prüfen,
            # damit ALTER TABLE nur läuft, wenn es wirklich nötig ist.
            spalten = [zeile[1] for zeile in conn.execute("PRAGMA table_info(cache_meta)")]
            if "vollstaendig" not in spalten:
                conn.execute("ALTER TABLE cache_meta ADD COLUMN vollstaendig INTEGER DEFAULT 1")

    def get_setting(self, key, default=None):
        with self._verbindung() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self._verbindung() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )

    def add_provider(self, name, ptype, url=None, username=None, password=None):
        with self._verbindung() as conn:
            cursor = conn.execute(
                "INSERT INTO providers (name, type, url, username, password) VALUES (?, ?, ?, ?, ?)",
                (name, ptype, url, username, password)
            )
            return cursor.lastrowid

    def get_providers(self):
        with self._verbindung() as conn:
            rows = conn.execute(
                "SELECT id, name, type, url, username FROM providers ORDER BY name"
            ).fetchall()
        return rows

    def get_provider(self, provider_id):
        with self._verbindung() as conn:
            row = conn.execute(
                "SELECT id, name, type, url, username, password FROM providers WHERE id = ?",
                (provider_id,)
            ).fetchone()
        return row

    def delete_provider(self, provider_id):
        with self._verbindung() as conn:
            conn.execute("DELETE FROM channels WHERE provider_id = ?", (provider_id,))
            conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))

    def add_channels(self, provider_id, channels):
        """Speichert Kanäle eines Providers und ersetzt dessen alte Bestände.

        Alle Zeilen werden mit einem einzigen executemany in einer
        Transaktion geschrieben. Einzelne Einfügebefehle in einer Schleife
        wären bei großen Playlists um ein Vielfaches langsamer.
        """
        daten = [
            (provider_id, ch.get("name", ""), ch.get("url", ""),
             ch.get("logo", ""), ch.get("category", ""),
             ch.get("tvg_id", ""), ch.get("tvg_name", ""),
             ch.get("type", "live"))
            for ch in channels
        ]
        with self._verbindung() as conn:
            conn.execute("DELETE FROM channels WHERE provider_id = ?", (provider_id,))
            conn.executemany(
                """INSERT INTO channels (provider_id, name, url, logo, category, tvg_id, tvg_name, type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                daten
            )

    def get_channels(self, provider_id=None, category=None, search=None, type=None, limit=None, offset=0):
        """Lädt Kanäle, optional gefiltert.

        Mit gesetztem limit wird die Abfrage um LIMIT und OFFSET ergänzt,
        damit die Oberfläche später seitenweise laden kann. Ohne limit
        bleibt das Verhalten genau wie bisher.
        """
        with self._verbindung() as conn:
            query = "SELECT id, provider_id, name, url, logo, category, tvg_id, tvg_name, type FROM channels WHERE 1=1"
            params = []
            if provider_id:
                query += " AND provider_id = ?"
                params.append(provider_id)
            if category:
                query += " AND category = ?"
                params.append(category)
            if type:
                query += " AND type = ?"
                params.append(type)
            if search:
                query += " AND name LIKE ?"
                params.append(f"%{search}%")
            query += " ORDER BY name"
            if limit:
                query += " LIMIT ? OFFSET ?"
                params.append(limit)
                params.append(offset or 0)
            rows = conn.execute(query, params).fetchall()
        return rows

    def get_channel(self, channel_id):
        """Liefert genau einen Kanal per Primärschlüssel oder None.

        Die Spaltenreihenfolge entspricht exakt der von get_channels,
        damit die Oberfläche beide Rückgaben gleich verarbeiten kann.
        Der Zugriff über den Primärschlüssel ist um Größenordnungen
        schneller, als alle Zeilen zu laden und in Python zu suchen.
        """
        with self._verbindung() as conn:
            row = conn.execute(
                "SELECT id, provider_id, name, url, logo, category, tvg_id, tvg_name, type FROM channels WHERE id = ?",
                (channel_id,)
            ).fetchone()
        return row

    def get_channel_count(self, provider_id=None, category=None, search=None, type=None):
        """Gibt die Anzahl der Kanäle zurück, ohne die Zeilen zu laden."""
        with self._verbindung() as conn:
            query = "SELECT COUNT(*) FROM channels WHERE 1=1"
            params = []
            if provider_id:
                query += " AND provider_id = ?"
                params.append(provider_id)
            if category:
                query += " AND category = ?"
                params.append(category)
            if type:
                query += " AND type = ?"
                params.append(type)
            if search:
                query += " AND name LIKE ?"
                params.append(f"%{search}%")
            count = conn.execute(query, params).fetchone()[0]
        return count

    def get_categories(self, provider_id=None, type=None):
        with self._verbindung() as conn:
            query = "SELECT DISTINCT category FROM channels WHERE category != ''"
            params = []
            if provider_id:
                query += " AND provider_id = ?"
                params.append(provider_id)
            if type:
                query += " AND type = ?"
                params.append(type)
            query += " ORDER BY category"
            rows = conn.execute(query, params).fetchall()
        return [r[0] for r in rows]

    def toggle_favorite(self, channel_id):
        with self._verbindung() as conn:
            row = conn.execute(
                "SELECT channel_id FROM favorites WHERE channel_id = ?", (channel_id,)
            ).fetchone()
            if row:
                conn.execute("DELETE FROM favorites WHERE channel_id = ?", (channel_id,))
                result = False
            else:
                conn.execute("INSERT INTO favorites (channel_id) VALUES (?)", (channel_id,))
                result = True
        return result

    def get_favorites(self):
        with self._verbindung() as conn:
            rows = conn.execute("""
                SELECT ch.id, ch.provider_id, ch.name, ch.url, ch.logo, ch.category, ch.tvg_id, ch.tvg_name, ch.type
                FROM favorites f
                JOIN channels ch ON f.channel_id = ch.id
                ORDER BY ch.name
            """).fetchall()
        return rows

    # === Cache Methods ===

    def get_cache_age(self, provider_id, content_type):
        """Gibt das Alter des Caches in Sekunden zurück, oder None wenn kein Cache existiert."""
        with self._verbindung() as conn:
            row = conn.execute(
                "SELECT cached_at FROM cache_meta WHERE provider_id = ? AND content_type = ?",
                (provider_id, content_type)
            ).fetchone()
        if not row:
            return None
        try:
            from datetime import datetime, timezone
            cached_at_str = row[0]
            # SQLite TIMESTAMP format: YYYY-MM-DD HH:MM:SS
            # CURRENT_TIMESTAMP schreibt die Uhrzeit in UTC, deshalb muss
            # auch die Vergleichsuhr in UTC laufen. Mit der lokalen Uhr
            # waere das Alter je nach Zeitzone um Stunden verschoben und
            # ein frisch gespeicherter Cache waere scheinbar veraltet.
            cached_at = datetime.strptime(cached_at_str, "%Y-%m-%d %H:%M:%S")
            cached_at = cached_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            return age
        except Exception:
            return None

    def is_cache_valid(self, provider_id, content_type, max_age_seconds=3600):
        """Prüft, ob der Cache gültig ist.

        Gültig ist nur ein vollständiger Cache, der jünger als
        max_age_seconds ist. Ein per save_cache_fortschritt gespeicherter
        Teilstand (vollstaendig = 0) gilt niemals als gültig, damit die
        Oberfläche keinen halben Bestand anzeigt.
        """
        with self._verbindung() as conn:
            row = conn.execute(
                "SELECT vollstaendig FROM cache_meta WHERE provider_id = ? AND content_type = ?",
                (provider_id, content_type)
            ).fetchone()
        if not row:
            return False
        if row[0] is not None and row[0] != 1:
            return False
        age = self.get_cache_age(provider_id, content_type)
        if age is None:
            return False
        return age < max_age_seconds

    def save_cache_meta(self, provider_id, content_type, channel_count=0):
        """Speichert Metadaten eines vollständig geladenen Caches."""
        with self._verbindung() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_meta (provider_id, content_type, cached_at, channel_count, vollstaendig) VALUES (?, ?, CURRENT_TIMESTAMP, ?, 1)",
                (provider_id, content_type, channel_count)
            )

    def save_cache_fortschritt(self, provider_id, content_type, anzahl):
        """Speichert einen unvollständigen Teilstand des Caches.

        Der Ladevorgang kann damit Zwischenstände festhalten, ohne dass
        die Oberfläche den halben Bestand als gültigen Cache ansieht.
        is_cache_valid liefert für solche Sätze stets False.
        """
        with self._verbindung() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_meta (provider_id, content_type, cached_at, channel_count, vollstaendig) VALUES (?, ?, CURRENT_TIMESTAMP, ?, 0)",
                (provider_id, content_type, anzahl)
            )

    def clear_cache_meta(self, provider_id, content_type=None):
        """Löscht Cache-Metadaten für einen Provider (optional nur einen content_type)."""
        with self._verbindung() as conn:
            if content_type:
                conn.execute(
                    "DELETE FROM cache_meta WHERE provider_id = ? AND content_type = ?",
                    (provider_id, content_type)
                )
            else:
                conn.execute("DELETE FROM cache_meta WHERE provider_id = ?", (provider_id,))

    def add_categories(self, provider_id, categories, content_type):
        """Speichert Kategorien für einen Provider und content_type."""
        with self._verbindung() as conn:
            conn.execute(
                "DELETE FROM categories WHERE provider_id = ? AND content_type = ?",
                (provider_id, content_type)
            )
            for cat in categories:
                cat_id = cat.get("category_id", "") if isinstance(cat, dict) else str(cat)
                cat_name = cat.get("category_name", "") if isinstance(cat, dict) else str(cat)
                conn.execute(
                    "INSERT INTO categories (provider_id, category_id, category_name, content_type) VALUES (?, ?, ?, ?)",
                    (provider_id, cat_id, cat_name, content_type)
                )

    def get_stored_categories(self, provider_id, content_type=None):
        """Lädt gespeicherte Kategorien aus der DB."""
        with self._verbindung() as conn:
            if content_type:
                rows = conn.execute(
                    "SELECT category_id, category_name FROM categories WHERE provider_id = ? AND content_type = ? ORDER BY category_name",
                    (provider_id, content_type)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category_id, category_name, content_type FROM categories WHERE provider_id = ? ORDER BY content_type, category_name",
                    (provider_id,)
                ).fetchall()
        return rows

    def add_channels_for_type(self, provider_id, channels, content_type):
        """Fügt Kanäle eines bestimmten Typs hinzu, ohne andere Typen zu löschen.

        Wie add_channels werden alle Zeilen mit einem einzigen executemany
        in einer Transaktion geschrieben.
        """
        daten = [
            (provider_id, ch.get("name", ""), ch.get("url", ""),
             ch.get("logo", ""), ch.get("category", ""),
             ch.get("tvg_id", ""), ch.get("tvg_name", ""),
             ch.get("type", content_type))
            for ch in channels
        ]
        with self._verbindung() as conn:
            # Nur Kanäle dieses Typs für diesen Provider löschen
            conn.execute(
                "DELETE FROM channels WHERE provider_id = ? AND type = ?",
                (provider_id, content_type)
            )
            conn.executemany(
                """INSERT INTO channels (provider_id, name, url, logo, category, tvg_id, tvg_name, type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                daten
            )

    def get_channel_count_by_type(self, provider_id, content_type):
        """Gibt die Anzahl der gespeicherten Kanäle eines Typs zurück."""
        with self._verbindung() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM channels WHERE provider_id = ? AND type = ?",
                (provider_id, content_type)
            ).fetchone()[0]
        return count