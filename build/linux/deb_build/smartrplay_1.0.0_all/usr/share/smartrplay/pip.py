#!/usr/bin/python3
"""
SMarTrPlay — Picture-in-Picture (PiP) Window
============================================
Kompaktes, frameless always-on-top PiP-Fenster (320x180px) mit
ffplay -wid Video-Embedding, Drag-and-Dock, SMarTr Brand Design
(Dark Mode, Cyan/Violet Akzente) und Close-Button.

Abhaengigkeiten: PyQt5, ffplay (ffmpeg), player.py (PlayerBackend)

Verwendung:
    from pip import PIPWindow
    pip = PIPWindow(backend, parent=None)
    pip.show()
    pip.start_video("rtsp://stream-url")

Author: SmarterCEO (SMartrAgents)
Datum: 2026-08-05
"""

import sys
import subprocess
import os
import signal

from PyQt5.QtWidgets import (
    QWidget,
    QApplication,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)
from PyQt5.QtCore import (
    Qt,
    QPoint,
    QSize,
    pyqtSignal,
    QProcess,
    QTimer,
)
from PyQt5.QtGui import (
    QFont,
    QIcon,
    QCursor,
    QPainter,
    QColor,
    QLinearGradient,
)

try:
    from player import PlayerBackend
except ImportError:
    PlayerBackend = None


BG_DARK = "#0d1117"
BG_PANEL = "#161b22"
ACCENT_CYAN = "#00d9ff"
ACCENT_VIOLET = "#a855f7"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"


class PIPWindow(QWidget):
    """Picture-in-Picture Overlay-Fenster."""

    closed = pyqtSignal()

    WINDOW_WIDTH = 320
    WINDOW_HEIGHT = 180
    HEADER_HEIGHT = 24

    def __init__(self, backend=None, parent=None):
        super().__init__(parent)

        self._backend = backend
        self._ffplay_proc = None
        self._qprocess = None
        self._drag_offset = QPoint()
        self._dragging = False

        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        self.setFixedSize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._header = QWidget(self)
        self._header.setFixedHeight(self.HEADER_HEIGHT)
        self._header.setGeometry(0, 0, self.WINDOW_WIDTH, self.HEADER_HEIGHT)

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 0, 4, 0)
        header_layout.setSpacing(4)

        self._label_pip = QLabel("PiP")
        self._label_pip.setObjectName("headerLabel")
        self._label_pip.setFixedHeight(self.HEADER_HEIGHT)
        header_layout.addWidget(self._label_pip)

        header_layout.addStretch()

        self._btn_close = QPushButton("X")
        self._btn_close.setObjectName("closeButton")
        self._btn_close.setFixedSize(22, 18)
        self._btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_close.setToolTip("PiP schliessen")
        self._btn_close.clicked.connect(self._on_close)
        header_layout.addWidget(self._btn_close)

        self._video_container = QWidget(self)
        self._video_container.setObjectName("videoContainer")
        self._video_container.setGeometry(
            0, self.HEADER_HEIGHT,
            self.WINDOW_WIDTH, self.WINDOW_HEIGHT - self.HEADER_HEIGHT,
        )
        self._video_container.setAttribute(Qt.WA_NativeWindow, True)
        self._video_container.setAttribute(Qt.WA_PaintOnScreen, True)
        self._video_container.setAttribute(Qt.WA_OpaquePaintEvent, True)

        self._video_placeholder = QLabel(self._video_container)
        self._video_placeholder.setAlignment(Qt.AlignCenter)
        self._video_placeholder.setText("Kein Video-Signal")
        self._video_placeholder.setGeometry(
            0, 0, self.WINDOW_WIDTH, self.WINDOW_HEIGHT - self.HEADER_HEIGHT,
        )

    def _apply_style(self):
        self.setStyleSheet(
            f"""
            PIPWindow {{
                background-color: {BG_DARK};
                border: 1px solid {ACCENT_CYAN};
                border-radius: 6px;
            }}
            QWidget {{
                background-color: {BG_PANEL};
            }}
            QLabel#headerLabel {{
                color: {ACCENT_CYAN};
                font-size: 11px;
                font-weight: bold;
                font-family: "DejaVu Sans", sans-serif;
                background-color: transparent;
            }}
            QPushButton#closeButton {{
                color: {TEXT_SECONDARY};
                background-color: transparent;
                border: none;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton#closeButton:hover {{
                color: {BG_DARK};
                background-color: {ACCENT_VIOLET};
            }}
            QPushButton#closeButton:pressed {{
                color: {BG_DARK};
                background-color: {ACCENT_CYAN};
            }}
            QWidget#videoContainer {{
                background-color: #000000;
                border: none;
            }}
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: 10px;
                font-family: "DejaVu Sans", sans-serif;
                background-color: transparent;
            }}
            """
        )

    def start_video(self, source, extra_args=None):
        self.stop_video()
        win_id = int(self._video_container.winId())
        if win_id == 0:
            print("[PiP] Fehler: Keine Window-ID")
            return False

        self._video_placeholder.hide()

        cmd = [
            "ffplay", "-wid", str(win_id),
            "-noborder", "-nostats", "-loglevel", "quiet",
            "-x", str(self.WINDOW_WIDTH),
            "-y", str(self.WINDOW_HEIGHT - self.HEADER_HEIGHT),
            "-protocol_whitelist", "file,http,https,tcp,tls,pipe,udp,rtp",
            "-an", "-fast", source,
        ]
        if extra_args:
            cmd.extend(extra_args)

        self._qprocess = QProcess(self)
        self._qprocess.setProcessChannelMode(QProcess.MergedChannels)
        self._qprocess.errorOccurred.connect(self._on_ffplay_error)
        self._qprocess.finished.connect(self._on_ffplay_finished)
        self._qprocess.start(cmd[0], cmd[1:])

        if not self._qprocess.waitForStarted(3000):
            self._qprocess = None
            try:
                self._ffplay_proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, preexec_fn=os.setsid,
                )
            except FileNotFoundError:
                self._video_placeholder.setText("ffplay nicht gefunden")
                self._video_placeholder.show()
                return False
        return True

    def stop_video(self):
        if self._qprocess is not None:
            try:
                if self._qprocess.state() != QProcess.NotRunning:
                    self._qprocess.terminate()
                    if not self._qprocess.waitForFinished(2000):
                        self._qprocess.kill()
            except Exception:
                pass
            self._qprocess = None

        if self._ffplay_proc is not None:
            try:
                os.killpg(os.getpgid(self._ffplay_proc.pid), signal.SIGTERM)
                self._ffplay_proc.wait(timeout=2)
            except Exception:
                try:
                    os.killpg(os.getpgid(self._ffplay_proc.pid), signal.SIGKILL)
                except Exception:
                    pass
            self._ffplay_proc = None
        self._video_placeholder.show()

    def redirect_from_backend(self, source=None):
        if source is None and self._backend is not None:
            try:
                source = self._backend.current_url
            except AttributeError:
                return False
        if source:
            return self.start_video(source)
        return False

    def _on_ffplay_error(self, error):
        self._video_placeholder.setText(f"Fehler: ffplay")
        self._video_placeholder.show()

    def _on_ffplay_finished(self, exit_code, exit_status):
        self._qprocess = None
        self._video_placeholder.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.pos().y() <= self.HEADER_HEIGHT:
                self._dragging = True
                self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._dock_to_edge()
            event.accept()
        else:
            event.ignore()

    def _dock_to_edge(self):
        snap_threshold = 20
        pos = self.pos()
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        new_x, new_y = pos.x(), pos.y()
        if abs(pos.x() - geo.left()) < snap_threshold:
            new_x = geo.left()
        elif abs((pos.x() + self.width()) - geo.right()) < snap_threshold:
            new_x = geo.right() - self.width()
        if abs(pos.y() - geo.top()) < snap_threshold:
            new_y = geo.top()
        elif abs((pos.y() + self.height()) - geo.bottom()) < snap_threshold:
            new_y = geo.bottom() - self.height()
        self.move(new_x, new_y)

    def _on_close(self):
        self.stop_video()
        self.closed.emit()
        self.hide()

    def closeEvent(self, event):
        self.stop_video()
        self.closed.emit()
        event.accept()

    def get_window_id(self):
        return int(self._video_container.winId())

    def set_backend(self, backend):
        self._backend = backend

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(BG_DARK))
        gradient.setColorAt(1, QColor("#0a0e14"))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)
        painter.setPen(QColor(ACCENT_CYAN))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)
        painter.setPen(QColor(ACCENT_VIOLET))
        painter.drawLine(1, self.HEADER_HEIGHT, self.width() - 2, self.HEADER_HEIGHT)
        painter.fillRect(1, 1, self.width() - 2, self.HEADER_HEIGHT - 1, QColor(BG_PANEL))
        painter.end()

    def resizeEvent(self, event):
        self._video_container.setGeometry(0, self.HEADER_HEIGHT, self.width(), self.height() - self.HEADER_HEIGHT)
        self._video_placeholder.setGeometry(0, 0, self.width(), self.height() - self.HEADER_HEIGHT)
        super().resizeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pip = PIPWindow(backend=None)
    pip.move(100, 100)
    pip.show()
    if len(sys.argv) > 1:
        pip.start_video(sys.argv[1])
    sys.exit(app.exec_())
