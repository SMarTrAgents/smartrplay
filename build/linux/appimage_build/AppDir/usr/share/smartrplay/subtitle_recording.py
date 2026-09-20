#!/usr/bin/env python3
"""SMarTrPlay - Subtitle & Recording Manager"""

import os
import subprocess
import signal
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSlider, QSpinBox, QGroupBox, QFormLayout,
    QLineEdit, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer


class SubtitleManager(QWidget):
    """Verwaltet Untertitel fuer den ffplay Player."""

    subtitle_changed = pyqtSignal(str)
    delay_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.subtitle_file = None
        self.delay_ms = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Untertitel")
        form = QFormLayout(group)

        self.file_label = QLabel("Keine Untertitel-Datei")
        form.addRow("Datei:", self.file_label)

        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Laden...")
        self.btn_load.clicked.connect(self._load_subtitle)
        self.btn_clear = QPushButton("Entfernen")
        self.btn_clear.clicked.connect(self._clear_subtitle)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_clear)
        form.addRow(btn_layout)

        self.delay_slider = QSlider(Qt.Horizontal)
        self.delay_slider.setRange(-30000, 30000)
        self.delay_slider.setValue(0)
        self.delay_slider.setSingleStep(100)
        self.delay_slider.valueChanged.connect(self._on_delay_change)
        self.delay_label = QLabel("0 ms")
        form.addRow("Verzoegerung:", self.delay_slider)
        form.addRow("", self.delay_label)

        layout.addWidget(group)

    def _load_subtitle(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Untertitel laden", "",
            "Untertitel (*.srt *.vtt *.ass *.ssa);;Alle Dateien (*)"
        )
        if path:
            self.subtitle_file = path
            name = os.path.basename(path)
            self.file_label.setText(name)
            self.subtitle_changed.emit(path)

    def _clear_subtitle(self):
        self.subtitle_file = None
        self.file_label.setText("Keine Untertitel-Datei")
        self.subtitle_changed.emit("")

    def _on_delay_change(self, value):
        self.delay_ms = value
        self.delay_label.setText(f"{value} ms")
        self.delay_changed.emit(value / 1000.0)

    def get_subtitle_args(self):
        """ffplay Argumente fuer Untertitel zurueckgeben."""
        args = []
        if self.subtitle_file:
            args.extend(["-sub", self.subtitle_file])
            if self.delay_ms != 0:
                args.extend(["-sub_delay", str(self.delay_ms / 1000.0)])
        return args


class RecordingManager(QWidget):
    """Nimmt Live-Streams mit ffmpeg auf."""

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal(str)
    duration_updated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.start_time = None
        self.output_file = None
        self.recording_dir = os.path.expanduser("~/SMarTrPlay/recordings")
        os.makedirs(self.recording_dir, exist_ok=True)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_duration)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Aufnahme")
        form = QFormLayout(group)

        self.url_input = QLineEdit(placeholderText="Stream URL")
        form.addRow("URL:", self.url_input)

        self.duration_label = QLabel("00:00:00")
        self.duration_label.setStyleSheet("font-family: monospace; font-size: 16px; font-weight: bold;")
        form.addRow("Dauer:", self.duration_label)

        self.status_label = QLabel("Bereit")
        form.addRow("Status:", self.status_label)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Aufnahme starten")
        self.btn_start.clicked.connect(self.start_recording)
        self.btn_stop = QPushButton("Aufnahme stoppen")
        self.btn_stop.clicked.connect(self.stop_recording)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        form.addRow(btn_layout)

        layout.addWidget(group)

    def start_recording(self, url=None):
        if url is None:
            url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Aufnahme", "Bitte Stream-URL eingeben.")
            return False

        self.stop_recording()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = os.path.join(self.recording_dir, f"recording_{timestamp}.mp4")

        cmd = [
            "ffmpeg",
            "-protocol_whitelist", "file,http,https,tcp,tls,pipe,udp,rtp",
            "-i", url,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",
            self.output_file
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            self.start_time = time.time()
            self.timer.start(1000)
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.status_label.setText("Aufnahme laeuft...")
            self.status_label.setStyleSheet("color: #10B981;")
            self.recording_started.emit()
            return True
        except Exception as e:
            QMessageBox.warning(self, "Aufnahme", f"Fehler: {e}")
            return False

    def stop_recording(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
                self.process.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except Exception:
                    try:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    except Exception:
                        pass
            self.process = None

        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText("Gestoppt")
        self.status_label.setStyleSheet("color: #9BA5B7;")

        if self.output_file:
            self.recording_stopped.emit(self.output_file)
            self.output_file = None

    def _update_duration(self):
        if self.start_time:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.duration_label.setText(duration)
            self.duration_updated.emit(duration)

    def is_recording(self):
        return self.process is not None and self.process.poll() is None

    def cleanup(self):
        self.stop_recording()
