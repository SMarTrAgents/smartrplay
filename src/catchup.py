#!/usr/bin/env python3
"""
SMarTrPlay v4 — catchup.py
Catch-up / Replay manager for Xtream Codes streams.

Only Python stdlib + PyQt5. Compatible with /usr/bin/python3.
SMarTr Brand Design: #0A0F1E / #1bf1fb / #8D7CF6.
"""

import time
import subprocess
import datetime
import json
from typing import List, Optional, Dict, Any

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLabel,
    QComboBox, QDateTimeEdit, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QGroupBox, QSpinBox, QWidget
)
from PyQt5.QtGui import QFont

# ─── SMarTr Brand Design ───────────────────────────────────────────
SMARTR_BG       = "#0A0F1E"
SMARTR_BG_LIGHT = "#121831"
SMARTR_CYAN     = "#1bf1fb"
SMARTR_VIOLET   = "#8D7CF6"
SMARTR_TEXT     = "#E8ECF7"
SMARTR_TEXT_DIM = "#7A8299"

SMARTR_QSS = f"""
QWidget, QDialog {{
    background-color: {SMARTR_BG};
    color: {SMARTR_TEXT};
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
}}
QLabel {{
    color: {SMARTR_TEXT};
}}
QPushButton {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_CYAN};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {SMARTR_VIOLET};
    color: {SMARTR_TEXT};
}}
QPushButton:pressed {{
    background-color: {SMARTR_CYAN};
    color: {SMARTR_BG};
}}
QGroupBox {{
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    color: {SMARTR_CYAN};
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QComboBox {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 4px;
    padding: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    selection-background-color: {SMARTR_VIOLET};
}}
QDateTimeEdit, QSpinBox, QLineEdit {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 4px;
    padding: 6px;
}}
QListWidget {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background-color: {SMARTR_VIOLET};
    color: {SMARTR_TEXT};
}}
"""


# ─── Catchup Manager ───────────────────────────────────────────────

class CatchupManager:
    """Builds Xtream Codes catch-up URLs for live stream replay."""

    def __init__(self, server_url: str = "", username: str = "", password: str = ""):
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password

    def configure(self, server_url: str, username: str, password: str):
        """Update Xtream credentials."""
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password

    def build_catchup_url(self, stream_id: int, start_unix: int, duration_secs: int) -> str:
        """
        Build an Xtream catch-up URL.
        Format: {server}/live/{user}/{pass}/{stream_id}?start={unix}&duration={secs}
        """
        if not self.server_url:
            raise ValueError("Server URL nicht konfiguriert")
        url = (
            f"{self.server_url}/live/{self.username}/{self.password}/{stream_id}"
            f"?start={start_unix}&duration={duration_secs}"
        )
        return url

    @staticmethod
    def datetime_to_unix(dt: datetime.datetime) -> int:
        """Convert a datetime object to Unix timestamp."""
        return int(dt.timestamp())

    @staticmethod
    def unix_to_datetime(unix_ts: int) -> datetime.datetime:
        """Convert a Unix timestamp to datetime."""
        return datetime.datetime.fromtimestamp(unix_ts)

    def launch_ffplay(self, url: str, extra_args: Optional[List[str]] = None) -> subprocess.Popen:
        """Launch ffplay with the given catch-up URL."""
        cmd = ["ffplay", "-nodisp", "-autoexit", "-protocol_whitelist", "file,http,https,tcp,tls,pipe,udp,rtp"]
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(url)
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def load_epg_data(self, json_str: str) -> List[Dict[str, Any]]:
        """
        Parse EPG JSON data. Expected format:
        [{"title": "...", "start": 1234567890, "stop": 1234571490, "description": "..."}, ...]
        """
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "epg_listings" in data:
                return data["epg_listings"]
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def format_epg_entry(entry: Dict[str, Any]) -> str:
        """Format an EPG entry for display in the list widget."""
        title = entry.get("title", "Unbekannt")
        start = entry.get("start", 0)
        stop = entry.get("stop", 0)
        try:
            start_dt = datetime.datetime.fromtimestamp(int(start))
            stop_dt = datetime.datetime.fromtimestamp(int(stop))
            time_str = f"{start_dt.strftime('%d.%m. %H:%M')} – {stop_dt.strftime('%H:%M')}"
        except (ValueError, OSError):
            time_str = f"{start} – {stop}"
        return f"{title}  ({time_str})"


# ─── Catch-up Dialog ────────────────────────────────────────────────

class CatchupDialog(QDialog):
    """Dialog for selecting EPG entry and launching catch-up replay."""

    play_requested = pyqtSignal(str)  # emits the catch-up URL

    def __init__(self, catchup_manager: CatchupManager, stream_id: int = 0,
                 epg_data: Optional[List[Dict[str, Any]]] = None, parent=None):
        super().__init__(parent)
        self._manager = catchup_manager
        self._stream_id = stream_id
        self._epg_data = epg_data or []
        self._ffplay_process: Optional[subprocess.Popen] = None
        self._init_ui()
        self.setStyleSheet(SMARTR_QSS)
        self._populate_epg()

    def _init_ui(self):
        self.setWindowTitle("SMarTrPlay — Catch-up / Replay")
        self.setMinimumWidth(520)
        self.setMinimumHeight(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("⏪  Catch-up / Replay")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet(f"color: {SMARTR_CYAN};")
        layout.addWidget(header)

        # Stream ID
        id_group = QGroupBox("Stream")
        id_layout = QFormLayout(id_group)
        self._stream_id_spin = QSpinBox()
        self._stream_id_spin.setRange(0, 999999)
        self._stream_id_spin.setValue(self._stream_id)
        id_layout.addRow("Stream ID:", self._stream_id_spin)
        layout.addWidget(id_group)

        # EPG List
        epg_group = QGroupBox("EPG-Auswahl")
        epg_layout = QVBoxLayout(epg_group)
        self._epg_list = QListWidget()
        self._epg_list.setMinimumHeight(150)
        self._epg_list.itemClicked.connect(self._on_epg_selected)
        epg_layout.addWidget(self._epg_list)

        self._epg_info = QLabel("Wählen Sie einen Eintrag aus der EPG-Liste.")
        self._epg_info.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 11px;")
        self._epg_info.setWordWrap(True)
        epg_layout.addWidget(self._epg_info)
        layout.addWidget(epg_group)

        # Time Selection
        time_group = QGroupBox("Zeit-Auswahl")
        time_layout = QFormLayout(time_group)

        now = datetime.datetime.now()
        self._start_dt = QDateTimeEdit(now.replace(minute=0, second=0))
        self._start_dt.setDisplayFormat("dd.MM.yyyy HH:mm")
        self._start_dt.setCalendarPopup(True)
        time_layout.addRow("Start:", self._start_dt)

        self._end_dt = QDateTimeEdit(now.replace(minute=0, second=0) + datetime.timedelta(hours=1))
        self._end_dt.setDisplayFormat("dd.MM.yyyy HH:mm")
        self._end_dt.setCalendarPopup(True)
        time_layout.addRow("Ende:", self._end_dt)

        self._duration_label = QLabel("Dauer: 0 Sekunden")
        self._duration_label.setStyleSheet(f"color: {SMARTR_CYAN}; font-size: 11px;")
        time_layout.addRow(self._duration_label)

        self._start_dt.dateTimeChanged.connect(self._update_duration)
        self._end_dt.dateTimeChanged.connect(self._update_duration)

        layout.addWidget(time_group)

        # URL Preview
        url_group = QGroupBox("Catch-up URL")
        url_layout = QVBoxLayout(url_group)
        self._url_preview = QLineEdit()
        self._url_preview.setReadOnly(True)
        self._url_preview.setPlaceholderText("URL wird automatisch generiert …")
        url_layout.addWidget(self._url_preview)
        layout.addWidget(url_group)

        # Buttons
        btn_row = QHBoxLayout()
        self._btn_generate = QPushButton("🔗 URL generieren")
        self._btn_generate.clicked.connect(self._generate_url)
        btn_row.addWidget(self._btn_generate)

        self._btn_play = QPushButton("▶ ffplay starten")
        self._btn_play.clicked.connect(self._launch_ffplay)
        btn_row.addWidget(self._btn_play)

        self._btn_stop = QPushButton("⏹ Stop")
        self._btn_stop.clicked.connect(self._stop_ffplay)
        btn_row.addWidget(self._btn_stop)

        layout.addLayout(btn_row)

        # Close button
        self._btn_close = QPushButton("Schließen")
        self._btn_close.clicked.connect(self._on_close)
        layout.addWidget(self._btn_close)

        self._update_duration()

    def _populate_epg(self):
        """Populate the EPG list widget with loaded EPG data."""
        self._epg_list.clear()
        for entry in self._epg_data:
            text = CatchupManager.format_epg_entry(entry)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry)
            self._epg_list.addItem(item)

    def _on_epg_selected(self, item: QListWidgetItem):
        """Handle EPG entry selection — fills start/end times."""
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        start = entry.get("start", 0)
        stop = entry.get("stop", 0)
        try:
            start_dt = datetime.datetime.fromtimestamp(int(start))
            stop_dt = datetime.datetime.fromtimestamp(int(stop))
            self._start_dt.setDateTime(start_dt)
            self._end_dt.setDateTime(stop_dt)
        except (ValueError, OSError):
            pass
        desc = entry.get("description", "")
        title = entry.get("title", "")
        self._epg_info.setText(f"<b>{title}</b>\n{desc}")
        self._update_duration()

    def _update_duration(self):
        """Recalculate and display duration in seconds."""
        start = self._start_dt.dateTime().toPyDateTime()
        end = self._end_dt.dateTime().toPyDateTime()
        delta = end - start
        secs = int(delta.total_seconds())
        if secs < 0:
            self._duration_label.setText("⚠ Ende liegt vor Start!")
            self._duration_label.setStyleSheet(f"color: #ff4444; font-size: 11px;")
        else:
            hours, remainder = divmod(secs, 3600)
            minutes, seconds = divmod(remainder, 60)
            self._duration_label.setText(f"Dauer: {secs} Sekunden ({hours}h {minutes}m {seconds}s)")
            self._duration_label.setStyleSheet(f"color: {SMARTR_CYAN}; font-size: 11px;")

    def _get_duration_secs(self) -> int:
        """Return duration in seconds from the time selection."""
        start = self._start_dt.dateTime().toPyDateTime()
        end = self._end_dt.dateTime().toPyDateTime()
        delta = end - start
        return max(int(delta.total_seconds()), 0)

    def _generate_url(self):
        """Generate the catch-up URL from current inputs."""
        stream_id = self._stream_id_spin.value()
        start_dt = self._start_dt.dateTime().toPyDateTime()
        start_unix = CatchupManager.datetime_to_unix(start_dt)
        duration = self._get_duration_secs()
        if duration <= 0:
            QMessageBox.warning(self, "Ungültige Zeit", "Ende muss nach Start liegen.")
            return
        try:
            url = self._manager.build_catchup_url(stream_id, start_unix, duration)
        except ValueError as e:
            QMessageBox.critical(self, "Konfigurationsfehler", str(e))
            return
        self._url_preview.setText(url)
        return url

    def _launch_ffplay(self):
        """Generate URL and launch ffplay."""
        url = self._url_preview.text().strip()
        if not url:
            url = self._generate_url()
        if not url:
            return
        try:
            self._ffplay_process = self._manager.launch_ffplay(url)
            self.play_requested.emit(url)
            QMessageBox.information(self, "ffplay", "ffplay gestartet.\nURL:\n" + url[:80] + ("…" if len(url) > 80 else ""))
        except FileNotFoundError:
            QMessageBox.critical(self, "ffplay fehlt", "ffplay wurde nicht gefunden.\nBitte installieren: sudo apt install ffmpeg")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"ffplay konnte nicht gestartet werden:\n{e}")

    def _stop_ffplay(self):
        """Stop the running ffplay process if any."""
        if self._ffplay_process and self._ffplay_process.poll() is None:
            self._ffplay_process.terminate()
            try:
                self._ffplay_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ffplay_process.kill()
            self._ffplay_process = None

    def _on_close(self):
        """Clean up and close dialog."""
        self._stop_ffplay()
        self.accept()

    def closeEvent(self, event):
        self._stop_ffplay()
        super().closeEvent(event)


# ─── Module Entry Point (test) ─────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    manager = CatchupManager("http://example.com:8080", "user", "pass")
    sample_epg = [
        {"title": "Nachrichten", "start": int(time.time()) - 3600, "stop": int(time.time()) - 1800, "description": "Tägliche Nachrichten"},
        {"title": "Sport", "start": int(time.time()) - 1800, "stop": int(time.time()), "description": "Sportschau"},
        {"title": "Film", "start": int(time.time()), "stop": int(time.time()) + 5400, "description": "Spielfilm"},
    ]
    dialog = CatchupDialog(manager, stream_id=1, epg_data=sample_epg)
    dialog.exec_()
