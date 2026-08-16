#!/usr/bin/env python3
"""SMarTrPlay - Configuration Manager"""

import json
import os
import sqlite3
from pathlib import Path


class Config:
    """Zentrale Konfiguration fuer SMarTrPlay."""

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

    def _init_db(self):
        """SQLite Datenbank initialisieren."""
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()

        c.execute("""
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

        c.execute("""
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

        c.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                channel_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()
        conn.close()

    def get_setting(self, key, default=None):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else default

    def set_setting(self, key, value):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        conn.commit()
        conn.close()

    def add_provider(self, name, ptype, url=None, username=None, password=None):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute(
            "INSERT INTO providers (name, type, url, username, password) VALUES (?, ?, ?, ?, ?)",
            (name, ptype, url, username, password)
        )
        provider_id = c.lastrowid
        conn.commit()
        conn.close()
        return provider_id

    def get_providers(self):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute("SELECT id, name, type, url, username FROM providers ORDER BY name")
        rows = c.fetchall()
        conn.close()
        return rows

    def get_provider(self, provider_id):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute("SELECT id, name, type, url, username, password FROM providers WHERE id = ?", (provider_id,))
        row = c.fetchone()
        conn.close()
        return row

    def delete_provider(self, provider_id):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute("DELETE FROM channels WHERE provider_id = ?", (provider_id,))
        c.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        conn.commit()
        conn.close()

    def add_channels(self, provider_id, channels):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute("DELETE FROM channels WHERE provider_id = ?", (provider_id,))
        for ch in channels:
            c.execute(
                """INSERT INTO channels (provider_id, name, url, logo, category, tvg_id, tvg_name, type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (provider_id, ch.get("name", ""), ch.get("url", ""),
                 ch.get("logo", ""), ch.get("category", ""),
                 ch.get("tvg_id", ""), ch.get("tvg_name", ""),
                 ch.get("type", "live"))
            )
        conn.commit()
        conn.close()

    def get_channels(self, provider_id=None, category=None, search=None, type=None):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
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
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return rows

    def get_categories(self, provider_id=None, type=None):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        query = "SELECT DISTINCT category FROM channels WHERE category != ''"
        params = []
        if provider_id:
            query += " AND provider_id = ?"
            params.append(provider_id)
        if type:
            query += " AND type = ?"
            params.append(type)
        query += " ORDER BY category"
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def toggle_favorite(self, channel_id):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute("SELECT channel_id FROM favorites WHERE channel_id = ?", (channel_id,))
        if c.fetchone():
            c.execute("DELETE FROM favorites WHERE channel_id = ?", (channel_id,))
            result = False
        else:
            c.execute("INSERT INTO favorites (channel_id) VALUES (?)", (channel_id,))
            result = True
        conn.commit()
        conn.close()
        return result

    def get_favorites(self):
        conn = sqlite3.connect(str(self.DB_PATH))
        c = conn.cursor()
        c.execute("""
            SELECT ch.id, ch.provider_id, ch.name, ch.url, ch.logo, ch.category, ch.tvg_id, ch.tvg_name, ch.type
            FROM favorites f
            JOIN channels ch ON f.channel_id = ch.id
            ORDER BY ch.name
        """)
        rows = c.fetchall()
        conn.close()
        return rows
