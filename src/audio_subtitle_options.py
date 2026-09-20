#!/usr/bin/env python3
"""SMarTrPlay - Audio/Subtitle Options Bar

Provides dropdowns for audio track selection, subtitle track selection,
and subtitle delay adjustment. Uses ffprobe to detect available tracks.
"""

import subprocess
import json
import logging
import threading
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QComboBox, QLabel, QSpinBox, QPushButton, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt

try:
    from theme import BG_DEEP, BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT_CYAN
except Exception:
    BG_DEEP = "#0a0e17"
    BG_CARD = "#111827"
    BORDER = "#1e2a3a"
    TEXT_PRIMARY = "#e2e8f0"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_MUTED = "#64748b"
    ACCENT_CYAN = "#06b6d4"

logger = logging.getLogger('SMarTrPlay.AudioSubtitle')


def probe_tracks(url, timeout=10):
    """Use ffprobe to detect audio and subtitle tracks.

    Returns (audio_tracks, subtitle_tracks) where each is a list of dicts:
        {"index": int, "codec": str, "language": str, "title": str}
    """
    audio_tracks = []
    subtitle_tracks = []
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-select_streams", "a:a",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            for s in data.get("streams", []):
                audio_tracks.append({
                    "index": s.get("index", 0),
                    "codec": s.get("codec_name", "unknown"),
                    "language": s.get("tags", {}).get("language", ""),
                    "title": s.get("tags", {}).get("title", ""),
                    "channels": s.get("channels", 2),
                })
    except Exception as e:
        logger.debug(f"ffprobe audio failed: {e}")

    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-select_streams", "s",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            for s in data.get("streams", []):
                subtitle_tracks.append({
                    "index": s.get("index", 0),
                    "codec": s.get("codec_name", "unknown"),
                    "language": s.get("tags", {}).get("language", ""),
                    "title": s.get("tags", {}).get("title", ""),
                })
    except Exception as e:
        logger.debug(f"ffprobe subtitle failed: {e}")

    return audio_tracks, subtitle_tracks


def probe_duration(url, timeout=10):
    """Use ffprobe to get stream duration in seconds (int). Returns 0 for live."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            dur = float(data.get("format", {}).get("duration", 0))
            return int(dur)
    except Exception as e:
        logger.debug(f"ffprobe duration failed: {e}")
    return 0


class AudioSubtitleBar(QFrame):
    """Audio and subtitle track selection bar.

    Signals:
        audio_track_changed(str)    - Selected audio track key (e.g. "0:mp2:deu")
        subtitle_changed(str)       - Selected subtitle key or "off"
        subtitle_delay_changed(int) - Subtitle delay in milliseconds
    """

    _tracks_ready = pyqtSignal(object)  # internal signal for thread-safe track population
    audio_track_changed = pyqtSignal(str)
    subtitle_changed = pyqtSignal(str)
    subtitle_delay_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_DEEP};
                border-top: 1px solid {BORDER};
            }}
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 600;
            }}
            QComboBox {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                min-width: 120px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                selection-background-color: {ACCENT_CYAN};
                border: 1px solid {BORDER};
            }}
            QSpinBox {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QPushButton {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #1a2332;
                border-color: {ACCENT_CYAN};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)

        # Audio track
        layout.addWidget(QLabel("Audio:"))
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("Standard", "default")
        self.audio_combo.currentIndexChanged.connect(self._on_audio_changed)
        layout.addWidget(self.audio_combo)

        # Subtitle track
        layout.addWidget(QLabel("UT:"))
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItem("Aus", "off")
        self.subtitle_combo.currentIndexChanged.connect(self._on_subtitle_changed)
        layout.addWidget(self.subtitle_combo)

        layout.addStretch()

        # Subtitle delay
        layout.addWidget(QLabel("UT-Verz\u00f6gerung:"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(-10000, 10000)
        self.delay_spin.setSingleStep(100)
        self.delay_spin.setValue(0)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setFixedWidth(100)
        self.delay_spin.valueChanged.connect(self.subtitle_delay_changed.emit)
        layout.addWidget(self.delay_spin)

        # Refresh button
        self.btn_refresh = QPushButton("\u21bb Spuren")
        self.btn_refresh.setToolTip("Audio- und Untertitelspuren neu erkennen")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        layout.addWidget(self.btn_refresh)

        # State
        self._current_url = None

        # Connect internal signal for thread-safe track population
        self._tracks_ready.connect(self._apply_tracks)

    def populate_tracks(self, url):
        """Probe the URL for audio/subtitle tracks and fill dropdowns.

        Runs ffprobe in a background thread to avoid blocking the UI.
        """
        self._current_url = url
        self.audio_combo.clear()
        self.subtitle_combo.clear()
        self.audio_combo.addItem("Lade...", "loading")
        self.subtitle_combo.addItem("Lade...", "loading")

        def _worker():
            audio_tracks, sub_tracks = probe_tracks(url)
            self._tracks_ready.emit((audio_tracks, sub_tracks))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _apply_tracks(self, tracks_data):
        """Slot connected to _tracks_ready signal - populates combos on UI thread."""
        audio_tracks, sub_tracks = tracks_data

        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        if not audio_tracks:
            self.audio_combo.addItem("Standard", "default")
        else:
            for tr in audio_tracks:
                label = tr.get("title") or tr.get("language") or f"Spur {tr['index']}"
                key = f"{tr['index']}:{tr.get('codec', '')}:{tr.get('language', '')}"
                self.audio_combo.addItem(label, key)
        self.audio_combo.blockSignals(False)

        self.subtitle_combo.blockSignals(True)
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("Aus", "off")
        if sub_tracks:
            for tr in sub_tracks:
                label = tr.get("title") or tr.get("language") or f"UT {tr['index']}"
                key = f"{tr['index']}:{tr.get('codec', '')}:{tr.get('language', '')}"
                self.subtitle_combo.addItem(label, key)
        self.subtitle_combo.blockSignals(False)

    # PyQt5 needs this registered for invokeMethod with custom type
    # Using value as tuple - need to register, but invokeMethod with 'value' arg
    # works if we use a simpler approach: just call directly from thread-safe signal

    def _on_audio_changed(self, idx):
        key = self.audio_combo.itemData(idx)
        if key and key != "loading":
            self.audio_track_changed.emit(str(key))

    def _on_subtitle_changed(self, idx):
        key = self.subtitle_combo.itemData(idx)
        if key and key != "loading":
            self.subtitle_changed.emit(str(key))

    def _on_refresh_clicked(self):
        if self._current_url:
            self.populate_tracks(self._current_url)

    def reset(self):
        """Reset to default state."""
        self.audio_combo.blockSignals(True)
        self.subtitle_combo.blockSignals(True)
        self.audio_combo.clear()
        self.audio_combo.addItem("Standard", "default")
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("Aus", "off")
        self.delay_spin.setValue(0)
        self.audio_combo.blockSignals(False)
        self.subtitle_combo.blockSignals(False)
        self._current_url = None

    def set_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        self.audio_combo.setEnabled(enabled)
        self.subtitle_combo.setEnabled(enabled)
        self.delay_spin.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
