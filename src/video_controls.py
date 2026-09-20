#!/usr/bin/env python3
"""SMarTrPlay - Video Controls Bar (Play/Stop, Seek, 10s, Volume, Mute)"""

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QSlider, QLabel, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont


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


def _fmt_time(seconds: int) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class VideoControlsBar(QFrame):
    """Video control bar with play/stop, seek slider, 10s skip, volume.

    Signals:
        play_clicked()       - Play/Pause button clicked
        stop_clicked()       - Stop button clicked
        seek_10s_back()      - Seek 10 seconds backward
        seek_10s_forward()   - Seek 10 seconds forward
        seek_changed(int)    - User dragged seek slider to position (seconds)
        volume_changed(int)  - Volume slider changed (0-100)
        mute_clicked()       - Mute button clicked
    """

    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    seek_10s_back = pyqtSignal()
    seek_10s_forward = pyqtSignal()
    seek_changed = pyqtSignal(int)
    volume_changed = pyqtSignal(int)
    mute_clicked = pyqtSignal()
    vollbild_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_DEEP};
                border-top: 1px solid {BORDER};
            }}
            QPushButton {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #1a2332;
                border-color: {ACCENT_CYAN};
            }}
            QPushButton:pressed {{
                background-color: #0d1320;
            }}
            QPushButton:disabled {{
                color: {TEXT_MUTED};
                border-color: {BORDER};
            }}
            QSlider::groove:horizontal {{
                background: {BG_CARD};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT_CYAN};
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT_CYAN};
                border-radius: 3px;
            }}
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: 12px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        # Play/Pause
        self.btn_play = QPushButton("\u25b6")
        self.btn_play.setFixedSize(36, 32)
        self.btn_play.setToolTip("Play / Pause")
        self.btn_play.clicked.connect(self.play_clicked.emit)
        layout.addWidget(self.btn_play)

        # Stop
        self.btn_stop = QPushButton("\u23f9")
        self.btn_stop.setFixedSize(36, 32)
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self.btn_stop)

        # Seek -10s
        self.btn_back10 = QPushButton("\u23ea 10s")
        self.btn_back10.setFixedHeight(32)
        self.btn_back10.setToolTip("10 Sekunden zur\u00fcck")
        self.btn_back10.clicked.connect(self.seek_10s_back.emit)
        layout.addWidget(self.btn_back10)

        # Seek slider
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        # Beim Greifen des Griffs beginnt das Ziehen: Positionsanzeige
        # einfrieren, bis der Griff wieder losgelassen wird.
        self.seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek)
        self.seek_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.seek_slider, stretch=1)

        # Seek +10s
        self.btn_fwd10 = QPushButton("10s \u23e9")
        self.btn_fwd10.setFixedHeight(32)
        self.btn_fwd10.setToolTip("10 Sekunden vorw\u00e4rts")
        self.btn_fwd10.clicked.connect(self.seek_10s_forward.emit)
        layout.addWidget(self.btn_fwd10)

        # Time label
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(120)
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)

        # Volume — der Stummknopf meldet den Klick über mute_clicked,
        # die Oberfläche schaltet den Player stumm und ruft set_muted().
        self.btn_mute = QPushButton("\U0001f50a")
        self.btn_mute.setFixedSize(36, 32)
        self.btn_mute.setToolTip("Stumm")
        self.btn_mute.setCheckable(True)
        self.btn_mute.clicked.connect(self.mute_clicked.emit)
        layout.addWidget(self.btn_mute)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setToolTip("Lautst\u00e4rke")
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        layout.addWidget(self.volume_slider)

        # Vollbild: sichtbarer Weg neben Doppelklick und F11.
        self.btn_vollbild = QPushButton("\u26f6")
        self.btn_vollbild.setFixedSize(44, 32)
        self.btn_vollbild.setToolTip("Vollbild (Doppelklick auf das Bild oder F11)")
        self.btn_vollbild.clicked.connect(self.vollbild_clicked.emit)
        layout.addWidget(self.btn_vollbild)

        # Internal state
        self._duration = 0
        self._position = 0
        self._is_playing = False
        self._seeking = False
        self._muted = False

    # --- public API ---

    def set_position(self, current: int, duration: int):
        """Update slider position and time label (called from timer)."""
        self._position = max(0, current)
        self._duration = max(0, duration)
        if not self._seeking:
            self.seek_slider.blockSignals(True)
            if duration > 0:
                self.seek_slider.setRange(0, duration)
                self.seek_slider.setValue(self._position)
            else:
                # Live stream - no duration, slider shows elapsed only
                self.seek_slider.setRange(0, 0)
            self.seek_slider.blockSignals(False)
        if self._duration > 0:
            self.time_label.setText(f"{_fmt_time(self._position)} / {_fmt_time(self._duration)}")
        else:
            # Live ohne Dauer: nur die verstrichene Zeit anzeigen
            self.time_label.setText(_fmt_time(self._position))

    def set_playing(self, is_playing: bool):
        """Update play/pause button icon."""
        self._is_playing = is_playing
        self.btn_play.setText("\u23f8" if is_playing else "\u25b6")
        self.seek_slider.setEnabled(True)

    def set_volume(self, volume: int):
        """Set volume slider value (0-100) without emitting signal."""
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(max(0, min(100, volume)))
        self.volume_slider.blockSignals(False)

    def set_muted(self, stumm: bool):
        """Stummschaltzustand setzen: Knopfdruck und Lautsprechersymbol.

        stumm True zeigt den durchgestrichenen Lautsprecher, False den
        normalen Lautsprecher. Das betrifft nur die Anzeige; der Klick
        selbst läuft über mute_clicked bei der Oberfläche.
        """
        self._muted = bool(stumm)
        self.btn_mute.setChecked(self._muted)
        self.btn_mute.setText("\U0001f507" if self._muted else "\U0001f50a")

    def set_seekable(self, spulbar: bool):
        """Spulbalken und beide Zehnsekundenknöpfe freigeben oder ausgrauen."""
        self.btn_back10.setEnabled(spulbar)
        self.btn_fwd10.setEnabled(spulbar)
        self.seek_slider.setEnabled(spulbar)

    def reset(self):
        """Reset to initial state."""
        self._position = 0
        self._duration = 0
        self._is_playing = False
        self._seeking = False
        self.btn_play.setText("\u25b6")
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setValue(0)
        self.seek_slider.setEnabled(False)
        self.time_label.setText("00:00 / 00:00")

    def set_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        self.btn_play.setEnabled(enabled)
        self.btn_stop.setEnabled(enabled)
        self.btn_back10.setEnabled(enabled)
        self.btn_fwd10.setEnabled(enabled)
        self.seek_slider.setEnabled(enabled)
        if not enabled:
            self.volume_slider.setEnabled(False)
        else:
            self.volume_slider.setEnabled(True)

    # --- internal ---

    def _on_slider_pressed(self):
        """Griff des Spulbalkens ergriffen — Positionsanzeige einfrieren.

        Erst sliderReleased hebt das Flag wieder auf; bis dahin überschreibt
        der Sekundentakt die gezogene Position nicht mehr.
        """
        self._seeking = True

    def _on_seek(self):
        """User released seek slider - emit seek_changed."""
        pos = self.seek_slider.value()
        self._seeking = False
        self.seek_changed.emit(pos)
