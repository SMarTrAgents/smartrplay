#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
SMarTrPlay v4 — Mini Player
Frameless always-on-top 480x270px Mini Player mit ffplay -wid Embedding.
SMarTr Brand Design: #0A0F1E / #1bf1fb / #8D7CF6
"""

import subprocess
import os
import signal

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QComboBox, QLabel, QSizeGrip, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QSize, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QIcon


# ─── SMarTr Brand Colors ───
BG_DARK = "#0A0F1E"
BG_PANEL = "#151B2E"
ACCENT_CYAN = "#1bf1fb"
ACCENT_PURPLE = "#8D7CF6"
TEXT_WHITE = "#FFFFFF"
TEXT_DIM = "#8B8FA3"

SMARTR_QSS = f"""
QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_WHITE};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 12px;
}}
QPushButton {{
    background-color: #1A2040;
    border: 1px solid #2A3454;
    border-radius: 4px;
    padding: 4px 10px;
    color: {TEXT_WHITE};
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: #252D52;
    border: 1px solid {ACCENT_CYAN};
}}
QPushButton:pressed {{
    background-color: {ACCENT_PURPLE};
}}
QSlider::groove:horizontal {{
    background: #2A3454;
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT_CYAN};
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_CYAN};
    border-radius: 2px;
}}
QComboBox {{
    background-color: {BG_PANEL};
    border: 1px solid #2A3454;
    border-radius: 4px;
    padding: 3px 8px;
    color: {TEXT_WHITE};
    min-height: 24px;
}}
QComboBox:hover {{
    border: 1px solid {ACCENT_CYAN};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid #2A3454;
    selection-background-color: {ACCENT_PURPLE};
}}
QLabel {{
    color: {TEXT_DIM};
}}
"""


class MiniPlayer(QWidget):
    """480x270px always-on-top frameless Mini Player mit ffplay -wid."""

    channel_changed = pyqtSignal(str)
    stopped = pyqtSignal()

    MIN_W = 480
    MIN_H = 270
    SNAP_THRESHOLD = 20  # Pixel für Snap-to-Edge

    def __init__(self, ffplay_path="ffplay", backend=None, parent=None):
        super().__init__(parent)
        self.ffplay_path = ffplay_path
        self.backend = backend
        self.ffplay_proc = None
        self._is_playing = False
        self._volume = 60
        self._channels = []
        self._current_channel = None
        self._drag_offset = QPoint()
        self._dragging = False

        self._init_ui()
        self._init_window()

    def _init_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.resize(self.MIN_W, self.MIN_H)
        self.setStyleSheet(SMARTR_QSS)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ─── Video Container (für ffplay -wid) ───
        self.video_container = QWidget(self)
        self.video_container.setStyleSheet(f"background-color: #000000;")
        self.video_container.setMinimumHeight(200)
        layout.addWidget(self.video_container, 1)

        # ─── Control Bar ───
        ctrl_widget = QWidget(self)
        ctrl_widget.setStyleSheet(f"background-color: {BG_PANEL};")
        ctrl_widget.setFixedHeight(44)
        ctrl_layout = QHBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(6, 4, 6, 4)
        ctrl_layout.setSpacing(6)

        # Play/Pause
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(30, 30)
        self.btn_play.setToolTip("Play / Pause")
        self.btn_play.clicked.connect(self.toggle_play)
        ctrl_layout.addWidget(self.btn_play)

        # Stop
        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setFixedSize(30, 30)
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.clicked.connect(self.stop)
        ctrl_layout.addWidget(self.btn_stop)

        # Volume
        self.vol_label = QLabel("🔊")
        ctrl_layout.addWidget(self.vol_label)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self._volume)
        self.vol_slider.setFixedWidth(70)
        self.vol_slider.setToolTip("Lautstärke")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        ctrl_layout.addWidget(self.vol_slider)

        ctrl_layout.addSpacing(8)

        # Channel Dropdown
        self.lbl_channel = QLabel("CH:")
        ctrl_layout.addWidget(self.lbl_channel)

        self.combo_channels = QComboBox()
        self.combo_channels.setMinimumWidth(140)
        self.combo_channels.currentIndexChanged.connect(self._on_channel_selected)
        ctrl_layout.addWidget(self.combo_channels, 1)

        # Resize grip
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        ctrl_layout.addWidget(self.grip)

        layout.addWidget(ctrl_widget)

    # ─── Video Playback (ffplay) ───

    def get_video_wid(self):
        """Gibt die Window-ID des Video-Containers zurück."""
        return int(self.video_container.winId())

    def play(self, url=None):
        """Startet ffplay mit -wid Embedding in den Video-Container."""
        if url is None:
            url = self._current_channel
        if not url:
            return

        self.stop_ffplay()

        wid = self.get_video_wid()
        cmd = [
            self.ffplay_path,
            "-wid", str(wid),
            "-volume", str(self._volume / 100.0),
            "-noborder",
            "-alwaysontop",
            "-loglevel", "quiet",
            "-protocol_whitelist", "file,http,https,tcp,tls,pipe,udp,rtp",
            "-x", str(self.video_container.width()),
            "-y", str(self.video_container.height()),
            url
        ]
        try:
            self.ffplay_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            self._is_playing = True
            self.btn_play.setText("⏸")
        except FileNotFoundError:
            self._is_playing = False
            self.btn_play.setText("▶")

    def stop_ffplay(self):
        """Beendet den ffplay-Prozess."""
        if self.ffplay_proc and self.ffplay_proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.ffplay_proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        self.ffplay_proc = None

    def toggle_play(self):
        if self._is_playing:
            self.stop_ffplay()
            self._is_playing = False
            self.btn_play.setText("▶")
        else:
            self.play()

    def stop(self):
        self.stop_ffplay()
        self._is_playing = False
        self.btn_play.setText("▶")
        self.stopped.emit()

    def start_video(self, url):
        """Start video playback from a URL (convenience wrapper for play())."""
        self.play(url)

    def stop_video(self):
        """Stop video playback (convenience wrapper for stop())."""
        self.stop()

    def _on_volume_changed(self, val):
        self._volume = val
        if self._volume == 0:
            self.vol_label.setText("🔇")
        elif self._volume < 50:
            self.vol_label.setText("🔉")
        else:
            self.vol_label.setText("🔊")

    # ─── Channel Management ───

    def set_channels(self, channels):
        """channels = Liste von (name, url) Tupeln."""
        self._channels = list(channels)
        self.combo_channels.blockSignals(True)
        self.combo_channels.clear()
        for name, _ in self._channels:
            self.combo_channels.addItem(name)
        self.combo_channels.blockSignals(False)
        if self._channels:
            self.combo_channels.setCurrentIndex(0)
            self._current_channel = self._channels[0][1]

    def _on_channel_selected(self, index):
        if 0 <= index < len(self._channels):
            name, url = self._channels[index]
            self._current_channel = url
            self.channel_changed.emit(name)
            if self._is_playing:
                self.play(url)

    def get_current_channel(self):
        return self._current_channel

    # ─── Drag-to-Move ───

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPos() - self._drag_offset
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self._snap_to_edge()
            event.accept()

    def _snap_to_edge(self):
        """Snap-to-Edge: Wenn Fenster nah am Bildschirmrand, ausrichten."""
        screen = self.screen().availableGeometry() if self.screen() else None
        if not screen:
            screen = self.geometry()

        pos = self.pos()
        w = self.width()
        h = self.height()

        # Links
        if abs(pos.x() - screen.left()) < self.SNAP_THRESHOLD:
            pos.setX(screen.left())
        # Rechts
        elif abs((pos.x() + w) - screen.right()) < self.SNAP_THRESHOLD:
            pos.setX(screen.right() - w)
        # Oben
        if abs(pos.y() - screen.top()) < self.SNAP_THRESHOLD:
            pos.setY(screen.top())
        # Unten
        elif abs((pos.y() + h) - screen.bottom()) < self.SNAP_THRESHOLD:
            pos.setY(screen.bottom() - h)

        self.move(pos)

    # ─── Context Menu ───

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(SMARTR_QSS)

        act_close = QAction("Schließen", menu)
        act_close.triggered.connect(self.close)
        menu.addAction(act_close)

        act_topmost = QAction("Always-on-Top", menu)
        act_topmost.setCheckable(True)
        act_topmost.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        act_topmost.triggered.connect(self._toggle_topmost)
        menu.addAction(act_topmost)

        menu.exec_(event.globalPos())

    def _toggle_topmost(self, checked):
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    # ─── Cleanup ───

    def closeEvent(self, event):
        self.stop_ffplay()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # ffplay würde bei Resize neu gestartet werden müssen — optional
        pass


# ─── Self-Test ───
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyleSheet(SMARTR_QSS)
    player = MiniPlayer()
    player.set_channels([
        ("Demo TV", "http://example.com/stream1"),
        ("Test Channel", "http://example.com/stream2"),
    ])
    player.show()
    sys.exit(app.exec_())
