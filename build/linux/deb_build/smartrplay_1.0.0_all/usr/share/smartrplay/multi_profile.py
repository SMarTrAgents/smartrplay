#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
SMarTrPlay v4 — Multi-Profile Manager
Verwaltet mehrere IPTV Provider-Profile in SQLite.
SMarTr Brand Design: #0A0F1E / #1bf1fb / #8D7CF6
"""

import json
import sqlite3
import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QDialog, QFormLayout, QLineEdit,
    QLabel, QMessageBox, QFileDialog, QInputDialog
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont, QColor, QPalette


# ─── SMarTr Brand Colors ───
BG_DARK = "#0A0F1E"
ACCENT_CYAN = "#1bf1fb"
ACCENT_PURPLE = "#8D7CF6"
TEXT_WHITE = "#FFFFFF"
TEXT_DIM = "#8B8FA3"

SMARTR_QSS = f"""
QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_WHITE};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}}
QComboBox {{
    background-color: #151B2E;
    border: 1px solid #2A3454;
    border-radius: 6px;
    padding: 6px 12px;
    min-width: 200px;
    color: {TEXT_WHITE};
}}
QComboBox:hover {{
    border: 1px solid {ACCENT_CYAN};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: #151B2E;
    border: 1px solid #2A3454;
    selection-background-color: {ACCENT_PURPLE};
}}
QPushButton {{
    background-color: #1A2040;
    border: 1px solid #2A3454;
    border-radius: 6px;
    padding: 7px 16px;
    color: {TEXT_WHITE};
}}
QPushButton:hover {{
    background-color: #252D52;
    border: 1px solid {ACCENT_CYAN};
}}
QPushButton:pressed {{
    background-color: {ACCENT_PURPLE};
}}
QLineEdit {{
    background-color: #151B2E;
    border: 1px solid #2A3454;
    border-radius: 4px;
    padding: 6px 10px;
    color: {TEXT_WHITE};
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT_CYAN};
}}
QLabel {{
    color: {TEXT_DIM};
}}
QDialog {{
    background-color: {BG_DARK};
}}
"""


class ProfileConfig:
    """Zentrale Profile-Config-Klasse für SQLite-Profilverwaltung."""

    def __init__(self, db_path=None):
        if db_path is None:
            base = os.path.expanduser("~/.config/smartrplay")
            os.makedirs(base, exist_ok=True)
            db_path = os.path.join(base, "profiles.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iptv_profiles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL DEFAULT 'm3u',
                url         TEXT NOT NULL,
                user        TEXT,
                pass        TEXT,
                last_channel TEXT,
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
        conn.commit()
        conn.close()

    def get_conn(self):
        return sqlite3.connect(self.db_path)

    # ─── CRUD ───

    def add_profile(self, name, ptype, url, user="", password="", last_channel=""):
        now = datetime.utcnow().isoformat()
        conn = self.get_conn()
        cur = conn.execute(
            "INSERT INTO iptv_profiles (name, type, url, user, pass, last_channel, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, ptype, url, user, password, last_channel, now, now)
        )
        conn.commit()
        pid = cur.lastrowid
        conn.close()
        return pid

    def update_profile(self, pid, name=None, ptype=None, url=None, user=None, password=None, last_channel=None):
        fields = []
        values = []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if ptype is not None:
            fields.append("type = ?")
            values.append(ptype)
        if url is not None:
            fields.append("url = ?")
            values.append(url)
        if user is not None:
            fields.append("user = ?")
            values.append(user)
        if password is not None:
            fields.append("pass = ?")
            values.append(password)
        if last_channel is not None:
            fields.append("last_channel = ?")
            values.append(last_channel)
        if not fields:
            return
        fields.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(pid)
        conn = self.get_conn()
        conn.execute(f"UPDATE iptv_profiles SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def delete_profile(self, pid):
        conn = self.get_conn()
        conn.execute("DELETE FROM iptv_profiles WHERE id = ?", (pid,))
        conn.commit()
        conn.close()

    def get_profile(self, pid):
        conn = self.get_conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM iptv_profiles WHERE id = ?", (pid,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_profiles(self):
        conn = self.get_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM iptv_profiles ORDER BY name ASC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def set_last_channel(self, pid, channel):
        self.update_profile(pid, last_channel=channel)

    # ─── Import / Export ───

    def export_json(self, filepath):
        profiles = self.get_all_profiles()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"profiles": profiles, "exported_at": datetime.utcnow().isoformat()}, f, indent=2)
        return len(profiles)

    def import_json(self, filepath, overwrite=False):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        profiles = data.get("profiles", [])
        if overwrite:
            conn = self.get_conn()
            conn.execute("DELETE FROM iptv_profiles")
            conn.commit()
            conn.close()
        count = 0
        for p in profiles:
            self.add_profile(
                name=p.get("name", "Imported"),
                ptype=p.get("type", "m3u"),
                url=p.get("url", ""),
                user=p.get("user", ""),
                password=p.get("pass", ""),
                last_channel=p.get("last_channel", "")
            )
            count += 1
        return count


class ProfileEditDialog(QDialog):
    """Dialog zum Hinzufügen/Bearbeiten eines Profils."""

    def __init__(self, parent=None, profile=None):
        super().__init__(parent)
        self.setWindowTitle("Profil bearbeiten")
        self.setMinimumWidth(420)
        self.setStyleSheet(SMARTR_QSS)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.type_edit.setPlaceholderText("m3u, xtream, ...")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://provider.com/playlist.m3u")
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.last_channel_edit = QLineEdit()

        if profile:
            self.name_edit.setText(profile.get("name", ""))
            self.type_edit.setText(profile.get("type", "m3u"))
            self.url_edit.setText(profile.get("url", ""))
            self.user_edit.setText(profile.get("user", ""))
            self.pass_edit.setText(profile.get("pass", ""))
            self.last_channel_edit.setText(profile.get("last_channel", ""))

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Typ:", self.type_edit)
        layout.addRow("URL:", self.url_edit)
        layout.addRow("Benutzer:", self.user_edit)
        layout.addRow("Passwort:", self.pass_edit)
        layout.addRow("Letzter Kanal:", self.last_channel_edit)

        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Speichern")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addRow(btn_layout)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "ptype": self.type_edit.text().strip() or "m3u",
            "url": self.url_edit.text().strip(),
            "user": self.user_edit.text().strip(),
            "password": self.pass_edit.text().strip(),
            "last_channel": self.last_channel_edit.text().strip(),
        }


class ProfileSelector(QWidget):
    """Widget mit QComboBox + Add/Remove/Edit Buttons."""

    profile_changed = pyqtSignal(int, str)  # provider_id, name

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config or ProfileConfig()
        self.setStyleSheet(SMARTR_QSS)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        label = QLabel("Provider:")
        label.setStyleSheet(f"color: {ACCENT_CYAN}; font-weight: bold;")
        layout.addWidget(label)

        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo, 1)

        self.btn_add = QPushButton("➕")
        self.btn_add.setToolTip("Profil hinzufügen")
        self.btn_add.setFixedSize(36, 32)
        self.btn_add.clicked.connect(self._add_profile)
        layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("✏️")
        self.btn_edit.setToolTip("Profil bearbeiten")
        self.btn_edit.setFixedSize(36, 32)
        self.btn_edit.clicked.connect(self._edit_profile)
        layout.addWidget(self.btn_edit)

        self.btn_remove = QPushButton("🗑️")
        self.btn_remove.setToolTip("Profil entfernen")
        self.btn_remove.setFixedSize(36, 32)
        self.btn_remove.clicked.connect(self._remove_profile)
        layout.addWidget(self.btn_remove)

        self.btn_import = QPushButton("📥")
        self.btn_import.setToolTip("Profile importieren (JSON)")
        self.btn_import.setFixedSize(36, 32)
        self.btn_import.clicked.connect(self._import_profiles)
        layout.addWidget(self.btn_import)

        self.btn_export = QPushButton("📤")
        self.btn_export.setToolTip("Profile exportieren (JSON)")
        self.btn_export.setFixedSize(36, 32)
        self.btn_export.clicked.connect(self._export_profiles)
        layout.addWidget(self.btn_export)

        self._current_pid = None
        self.refresh()

    def refresh(self):
        """ComboBox neu laden."""
        self.combo.blockSignals(True)
        self.combo.clear()
        profiles = self.config.get_all_profiles()
        self._profile_map = {}
        for p in profiles:
            display = f"{p['name']} ({p['type']})"
            self.combo.addItem(display)
            self._profile_map[self.combo.count() - 1] = p["id"]
        self.combo.blockSignals(False)
        if profiles:
            self.combo.setCurrentIndex(0)
            self._current_pid = profiles[0]["id"]
        else:
            self._current_pid = None

    def _on_combo_changed(self, index):
        if index >= 0 and index in self._profile_map:
            pid = self._profile_map[index]
            self._current_pid = pid
            name = self.combo.itemText(index)
            self.profile_changed.emit(pid, name)

    def profile_switch(self, provider_id):
        """Schnellwechsel zu einem Provider per ID."""
        for idx, pid in self._profile_map.items():
            if pid == provider_id:
                self.combo.setCurrentIndex(idx)
                return True
        return False

    def get_current_profile(self):
        if self._current_pid is None:
            return None
        return self.config.get_profile(self._current_pid)

    def get_current_pid(self):
        return self._current_pid

    # ─── Button Handlers ───

    def _add_profile(self):
        dlg = ProfileEditDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"] or not data["url"]:
                QMessageBox.warning(self, "Fehler", "Name und URL sind erforderlich.")
                return
            self.config.add_profile(**data)
            self.refresh()

    def _edit_profile(self):
        if self._current_pid is None:
            QMessageBox.information(self, "Info", "Kein Profil ausgewählt.")
            return
        profile = self.config.get_profile(self._current_pid)
        if not profile:
            return
        dlg = ProfileEditDialog(self, profile=profile)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            self.config.update_profile(self._current_pid, **data)
            self.refresh()

    def _remove_profile(self):
        if self._current_pid is None:
            return
        reply = QMessageBox.question(
            self, "Bestätigung",
            "Profil wirklich entfernen?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.delete_profile(self._current_pid)
            self.refresh()

    def _import_profiles(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Profile importieren", "", "JSON Dateien (*.json)"
        )
        if path:
            reply = QMessageBox.question(
                self, "Import",
                "Bestehende Profile überschreiben?",
                QMessageBox.Yes | QMessageBox.No
            )
            overwrite = (reply == QMessageBox.Yes)
            count = self.config.import_json(path, overwrite=overwrite)
            self.refresh()
            QMessageBox.information(self, "Import", f"{count} Profile importiert.")

    def _export_profiles(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Profile exportieren", "smartrplay_profiles.json", "JSON Dateien (*.json)"
        )
        if path:
            count = self.config.export_json(path)
            QMessageBox.information(self, "Export", f"{count} Profile exportiert.")


# ─── Self-Test (nur bei direktem Aufruf) ───
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyleSheet(SMARTR_QSS)
    widget = ProfileSelector()
    widget.setWindowTitle("SMarTrPlay — Profile Manager")
    widget.resize(500, 60)
    widget.show()
    sys.exit(app.exec_())
