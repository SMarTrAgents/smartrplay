#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
SMarTrPlay v4 — EPG Timeline
Horizontale Timeline mit Stunden-Raster, farbigen Programm-Blocks und Jetzt-Linie.
SMarTr Brand Design: #0A0F1E / #1bf1fb / #8D7CF6
"""

from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton,
    QLabel, QDialog, QGridLayout, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QPixmap, QLinearGradient,
    QFontMetrics
)


# ─── SMarTr Brand Colors ───
BG_DARK = "#0A0F1E"
BG_PANEL = "#151B2E"
BG_ROW = "#10()F1E".replace("()","")
ACCENT_CYAN = "#1bf1fb"
ACCENT_PURPLE = "#8D7CF6"
TEXT_WHITE = "#FFFFFF"
TEXT_DIM = "#8B8FA3"
GRID_COLOR = "#1E2640"

# Program block colors (rotated by index)
PROG_COLORS = [
    QColor("#1a4a5e"),
    QColor("#2d3a6e"),
    QColor("#4a2d6e"),
    QColor("#1e5e4a"),
    QColor("#6e4a2d"),
    QColor("#2d6e5e"),
]

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
    padding: 5px 12px;
    color: {TEXT_WHITE};
}}
QPushButton:hover {{
    background-color: #252D52;
    border: 1px solid {ACCENT_CYAN};
}}
QPushButton:pressed {{
    background-color: {ACCENT_PURPLE};
}}
QScrollArea {{
    background-color: {BG_DARK};
    border: none;
}}
QLabel {{
    color: {TEXT_DIM};
}}
QDialog {{
    background-color: {BG_DARK};
}}
"""


class ProgramDetailDialog(QDialog):
    """Dialog mit Programm-Details."""

    def __init__(self, program, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Programm-Details")
        self.setMinimumWidth(400)
        self.setStyleSheet(SMARTR_QSS)

        layout = QGridLayout(self)

        title_label = QLabel(program.get("title", "Unbekannt"))
        title_label.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label, 0, 0, 1, 2)

        start = program.get("start", "")
        end = program.get("end", "")
        layout.addWidget(QLabel("Zeit:"), 1, 0)
        layout.addWidget(QLabel(f"{start} - {end}"), 1, 1)

        channel = program.get("channel", "")
        layout.addWidget(QLabel("Kanal:"), 2, 0)
        ch_label = QLabel(channel)
        ch_label.setStyleSheet(f"color: {TEXT_WHITE};")
        layout.addWidget(ch_label, 2, 1)

        desc = program.get("description", "Keine Beschreibung verfügbar.")
        layout.addWidget(QLabel("Beschreibung:"), 3, 0)
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {TEXT_WHITE};")
        desc_label.setMaximumWidth(360)
        layout.addWidget(desc_label, 3, 1)

        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, 4, 0, 1, 2, Qt.AlignCenter)


class EpgTimelineWidget(QWidget):
    """Horizontale Timeline mit Stunden-Raster und farbigen Programm-Blocks."""

    program_clicked = pyqtSignal(dict)

    HOUR_WIDTH = 180        # Pixel pro Stunde
    ROW_HEIGHT = 56          # Pixel pro Kanal-Reihe
    HEADER_HEIGHT = 30       # Höhe der Stunden-Skalierung
    CHANNEL_NAME_WIDTH = 120 # Breite der Kanal-Namen-Spalte
    SNAP_MINUTES = 30        # Snap-Intervall für Scroll

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SMARTR_QSS)
        self.setMinimumHeight(400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._channels = []       # [{"name": "RTL", "id": "rtl"}, ...]
        self._epg_data = {}       # {channel_id: [{start_dt, end_dt, title, ...}, ...]}
        self._program_rects = []  # [(QRect, program_dict), ...]
        self._scroll_x = 0
        self._scroll_y = 0
        self._view_start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
        self._hours_visible = 6
        self._now_timer = QTimer(self)
        self._now_timer.timeout.connect(self.update)
        self._now_timer.start(60000)  # Jede Minute neu zeichnen für Now-Linie

    # ─── Public API ───

    def set_channels(self, channels):
        """channels = [{"name": str, "id": str}, ...]"""
        self._channels = list(channels)
        self.update()

    def set_epg_data(self, epg_data):
        """epg_data = {channel_id: [{start, end, title, description, ...}, ...]}
        start/end als ISO-String oder datetime."""
        self._epg_data = {}
        for ch_id, programs in epg_data.items():
            parsed = []
            for p in programs:
                prog = dict(p)
                if isinstance(prog.get("start"), str):
                    prog["start_dt"] = self._parse_dt(prog["start"])
                else:
                    prog["start_dt"] = prog.get("start")
                if isinstance(prog.get("end"), str):
                    prog["end_dt"] = self._parse_dt(prog["end"])
                else:
                    prog["end_dt"] = prog.get("end")
                parsed.append(prog)
            self._epg_data[ch_id] = parsed
        self.update()

    def scroll_to_now(self):
        """Scrollt zur aktuellen Zeit."""
        now = datetime.now()
        self._view_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        self.update()

    def scroll_hours(self, delta_hours):
        """Scrollt um delta_hours Stunden."""
        self._view_start += timedelta(hours=delta_hours)
        self.update()

    # ─── Parsing ───

    @staticmethod
    def _parse_dt(dt_str):
        """Parse ISO-Format oder 'YYYY-MM-DD HH:MM:SS'."""
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(dt_str, fmt)
            except (ValueError, TypeError):
                continue
        try:
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return datetime.now()

    # ─── Geometry Helpers ───

    def _total_width(self):
        return self._hours_visible * self.HOUR_WIDTH + self.CHANNEL_NAME_WIDTH

    def _total_height(self):
        return self.HEADER_HEIGHT + len(self._channels) * self.ROW_HEIGHT

    def _time_to_x(self, dt):
        """Konvertiert datetime → X-Pixel im Content-Bereich."""
        delta = (dt - self._view_start).total_seconds() / 3600.0
        return self.CHANNEL_NAME_WIDTH + int(delta * self.HOUR_WIDTH)

    def _x_to_time(self, x):
        """Konvertiert X-Pixel → datetime."""
        hours = (x - self.CHANNEL_NAME_WIDTH) / self.HOUR_WIDTH
        return self._view_start + timedelta(hours=hours)

    # ─── Painting ───

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Hintergrund
        painter.fillRect(0, 0, w, h, QColor(BG_DARK))

        self._program_rects = []

        # Stunden-Skalierung (Header)
        self._draw_header(painter, w)

        # Kanal-Zeilen
        for i, ch in enumerate(self._channels):
            y = self.HEADER_HEIGHT + i * self.ROW_HEIGHT
            self._draw_channel_row(painter, ch, y, w, i)

        # Stunden-Raster (vertikale Linien)
        self._draw_grid(painter, w, h)

        # Jetzt-Linie
        self._draw_now_line(painter, w, h)

        painter.end()

    def _draw_header(self, painter, width):
        """Zeichnet die Stunden-Skala oben."""
        painter.fillRect(0, 0, width, self.HEADER_HEIGHT, QColor(BG_PANEL))

        # Trennlinie unten
        pen = QPen(QColor(GRID_COLOR), 1)
        painter.setPen(pen)
        painter.drawLine(0, self.HEADER_HEIGHT, width, self.HEADER_HEIGHT)

        # Kanal-Namen-Spalte Header
        painter.fillRect(0, 0, self.CHANNEL_NAME_WIDTH, self.HEADER_HEIGHT, QColor(BG_PANEL))
        painter.setPen(QColor(TEXT_DIM))
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.drawText(QRect(4, 0, self.CHANNEL_NAME_WIDTH - 8, self.HEADER_HEIGHT),
                         Qt.AlignVCenter | Qt.AlignLeft, "Kanal")

        # Stunden-Beschriftung
        for hour in range(self._hours_visible + 1):
            dt = self._view_start + timedelta(hours=hour)
            x = self.CHANNEL_NAME_WIDTH + hour * self.HOUR_WIDTH
            if x > width:
                break
            label = dt.strftime("%H:00")
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(QRect(x + 4, 0, 80, self.HEADER_HEIGHT),
                             Qt.AlignVCenter | Qt.AlignLeft, label)

            # Datum nur bei erster Stunde
            if hour == 0:
                date_label = dt.strftime("%a %d.%m.")
                painter.setPen(QColor(ACCENT_CYAN))
                painter.drawText(QRect(x + 4, 2, 80, 14),
                                 Qt.AlignTop | Qt.AlignLeft, date_label)

    def _draw_channel_row(self, painter, channel, y, width, row_idx=0):
        """Zeichnet eine Kanal-Zeile mit Program-Blocks."""
        row_rect = QRect(0, y, width, self.ROW_HEIGHT)

        # Zeilen-Hintergrund (alternierend)
        bg = QColor("#0E1322") if row_idx % 2 == 0 else QColor("#121A2E")
        painter.fillRect(row_rect, bg)

        # Kanal-Name
        painter.fillRect(0, y, self.CHANNEL_NAME_WIDTH, self.ROW_HEIGHT, QColor(BG_PANEL))
        pen = QPen(QColor(GRID_COLOR), 1)
        painter.setPen(pen)
        painter.drawLine(self.CHANNEL_NAME_WIDTH, y, self.CHANNEL_NAME_WIDTH, y + self.ROW_HEIGHT)

        painter.setPen(QColor(TEXT_WHITE))
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)
        ch_name = channel.get("name", "?")
        elided = fm.elidedText(ch_name, Qt.ElideRight, self.CHANNEL_NAME_WIDTH - 16)
        painter.drawText(QRect(8, y, self.CHANNEL_NAME_WIDTH - 12, self.ROW_HEIGHT),
                         Qt.AlignVCenter | Qt.AlignLeft, elided)

        # Trennlinie unten
        painter.setPen(QPen(QColor(GRID_COLOR), 1))
        painter.drawLine(0, y + self.ROW_HEIGHT, width, y + self.ROW_HEIGHT)

        # Programm-Blocks
        programs = self._epg_data.get(channel.get("id"), [])
        for idx, prog in enumerate(programs):
            start_dt = prog.get("start_dt")
            end_dt = prog.get("end_dt")
            if not start_dt or not end_dt:
                continue

            x1 = self._time_to_x(start_dt)
            x2 = self._time_to_x(end_dt)

            # Nur sichtbare Blocks zeichnen
            if x2 < self.CHANNEL_NAME_WIDTH or x1 > width:
                continue

            x1 = max(x1, self.CHANNEL_NAME_WIDTH)
            x2 = min(x2, width)
            block_w = x2 - x1
            if block_w < 2:
                continue

            block_rect = QRect(x1, y + 3, block_w, self.ROW_HEIGHT - 6)
            color = PROG_COLORS[idx % len(PROG_COLORS)]

            # Block-Hintergrund mit Verlauf
            gradient = QLinearGradient(block_rect.topLeft(), block_rect.bottomLeft())
            gradient.setColorAt(0, color.lighter(130))
            gradient.setColorAt(1, color)
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(color.darker(150), 1))
            painter.drawRoundedRect(block_rect, 4, 4)

            # Programm-Titel
            painter.setPen(QColor(TEXT_WHITE))
            font = QFont("Segoe UI", 9)
            painter.setFont(font)
            fm = QFontMetrics(font)
            title = prog.get("title", "")
            elided = fm.elidedText(title, Qt.ElideRight, block_w - 12)
            painter.drawText(block_rect.adjusted(6, 2, -4, -2),
                             Qt.AlignVCenter | Qt.AlignLeft, elided)

            # Zeit-Label unten (wenn Platz)
            if block_w > 100:
                time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
                painter.setPen(QColor(TEXT_DIM))
                font_small = QFont("Segoe UI", 7)
                painter.setFont(font_small)
                painter.drawText(block_rect.adjusted(6, block_rect.height() - 18, -4, -2),
                                 Qt.AlignBottom | Qt.AlignLeft, time_str)

            # Für Klick-Detection speichern
            self._program_rects.append((block_rect, {**prog, "channel": channel.get("name", "")}))

    def _draw_grid(self, painter, width, height):
        """Zeichnet vertikale Stunden-Raster-Linien."""
        pen = QPen(QColor(GRID_COLOR), 1, Qt.DashLine)
        painter.setPen(pen)

        for hour in range(self._hours_visible + 1):
            x = self.CHANNEL_NAME_WIDTH + hour * self.HOUR_WIDTH
            if x > width:
                break
            painter.drawLine(x, self.HEADER_HEIGHT, x, height)

    def _draw_now_line(self, painter, width, height):
        """Zeichnet die vertikale Jetzt-Linie (cyan → rot Gradient)."""
        now = datetime.now()
        x = self._time_to_x(now)

        if x < self.CHANNEL_NAME_WIDTH or x > width:
            return

        # Linie
        pen = QPen(QColor(ACCENT_CYAN), 2)
        painter.setPen(pen)
        painter.drawLine(x, self.HEADER_HEIGHT, x, height)

        # Marker oben (Dreieck)
        tri_size = 8
        points = [
            QPoint(x - tri_size, self.HEADER_HEIGHT),
            QPoint(x + tri_size, self.HEADER_HEIGHT),
            QPoint(x, self.HEADER_HEIGHT + tri_size),
        ]
        from PyQt5.QtGui import QPolygon
        painter.setBrush(QBrush(QColor(ACCENT_CYAN)))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygon(points))

        # Jetzt-Label
        painter.setPen(QColor(ACCENT_CYAN))
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRect(x + 6, self.HEADER_HEIGHT + 4, 60, 20),
                        Qt.AlignLeft | Qt.AlignVCenter, "JETZT")

        # Roter Akzentpunkt
        painter.setBrush(QBrush(QColor("#FF4444")))
        painter.drawEllipse(QPoint(x, self.HEADER_HEIGHT + tri_size + 2), 3, 3)

    # ─── Mouse / Scroll ───

    def wheelEvent(self, event):
        """Horizontal scrollen mit Shift, vertikal normal."""
        if event.modifiers() & Qt.ShiftModifier:
            delta = event.angleDelta().y() / 120
            self.scroll_hours(-delta)
        else:
            self._scroll_y += event.angleDelta().y()
            self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            for rect, prog in self._program_rects:
                if rect.contains(pos):
                    self.program_clicked.emit(prog)
                    dlg = ProgramDetailDialog(prog, self)
                    dlg.exec_()
                    return
            event.accept()

    # ─── Self-Contained Scroll Support ───

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.scroll_hours(-1)
        elif event.key() == Qt.Key_Right:
            self.scroll_hours(1)
        elif event.key() == Qt.Key_Home:
            self.scroll_to_now()
        else:
            super().keyPressEvent(event)


class EpgScrollArea(QScrollArea):
    """ScrollArea-Wrapper für EpgTimelineWidget mit horizontal/vertikal Scroll."""

    def __init__(self, timeline_widget, parent=None):
        super().__init__(parent)
        self.timeline = timeline_widget
        self.setWidget(timeline_widget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet(SMARTR_QSS)


class EpgContainer(QWidget):
    """Vollständiges EPG-Widget mit Toolbar + ScrollArea."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(SMARTR_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {BG_PANEL};")
        toolbar.setFixedHeight(36)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        title = QLabel("📋 EPG Timeline")
        title.setStyleSheet(f"color: {ACCENT_CYAN}; font-weight: bold; font-size: 13px;")
        tb_layout.addWidget(title)
        tb_layout.addStretch()

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(30, 28)
        self.btn_prev.setToolTip("Eine Stunde zurück")
        self.btn_prev.clicked.connect(lambda: self.timeline.scroll_hours(-1))
        tb_layout.addWidget(self.btn_prev)

        self.btn_now = QPushButton("Jetzt")
        self.btn_now.setFixedHeight(28)
        self.btn_now.setToolTip("Zur aktuellen Zeit springen")
        self.btn_now.clicked.connect(self.timeline.scroll_to_now)
        tb_layout.addWidget(self.btn_now)

        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(30, 28)
        self.btn_next.setToolTip("Eine Stunde vor")
        self.btn_next.clicked.connect(lambda: self.timeline.scroll_hours(1))
        tb_layout.addWidget(self.btn_next)

        layout.addWidget(toolbar)

        # Timeline
        self.timeline = EpgTimelineWidget()
        self.scroll_area = EpgScrollArea(self.timeline, self)
        layout.addWidget(self.scroll_area, 1)

    def set_channels(self, channels):
        self.timeline.set_channels(channels)

    def set_epg_data(self, epg_data):
        self.timeline.set_epg_data(epg_data)


# ─── Self-Test ───
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyleSheet(SMARTR_QSS)

    container = EpgContainer()
    container.set_channels([
        {"name": "RTL", "id": "rtl"},
        {"name": "ARD", "id": "ard"},
        {"name": "ZDF", "id": "zdf"},
        {"name": "Pro7", "id": "pro7"},
    ])

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    test_epg = {
        "rtl": [
            {"start": (now - timedelta(hours=1)).isoformat(), "end": now.isoformat(), "title": "RTL Aktuell", "description": "Nachrichten"},
            {"start": now.isoformat(), "end": (now + timedelta(hours=1, minutes=30)).isoformat(), "title": "Wer wird Millionär", "description": "Quizshow mit Günther Jauch"},
            {"start": (now + timedelta(hours=1, minutes=30)).isoformat(), "end": (now + timedelta(hours=3)).isoformat(), "title": "CSI: Miami", "description": "Krimi-Serie"},
        ],
        "ard": [
            {"start": (now - timedelta(minutes=30)).isoformat(), "end": (now + timedelta(hours=1)).isoformat(), "title": "Tagesschau", "description": "Nachrichten der ARD"},
            {"start": (now + timedelta(hours=1)).isoformat(), "end": (now + timedelta(hours=2)).isoformat(), "title": "Tatort", "description": "Sonntagskrimi"},
        ],
        "zdf": [
            {"start": now.isoformat(), "end": (now + timedelta(minutes=45)).isoformat(), "title": "heute", "description": "ZDF Nachrichten"},
            {"start": (now + timedelta(minutes=45)).isoformat(), "end": (now + timedelta(hours=2)).isoformat(), "title": "SOKO Stuttgart", "description": "Serie"},
        ],
        "pro7": [
            {"start": (now - timedelta(hours=2)).isoformat(), "end": now.isoformat(), "title": "The Big Bang Theory", "description": "Sitcom"},
            {"start": now.isoformat(), "end": (now + timedelta(minutes=30)).isoformat(), "title": "Galileo", "description": "Wissensmagazin"},
            {"start": (now + timedelta(minutes=30)).isoformat(), "end": (now + timedelta(hours=2)).isoformat(), "title": "Die Simpsons", "description": "Animation"},
        ],
    }
    container.set_epg_data(test_epg)
    container.resize(800, 400)
    container.show()
    sys.exit(app.exec_())
