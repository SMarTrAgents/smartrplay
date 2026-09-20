"""Vollbildbedienung fuer SMarTrPlay.

Das Videobild liegt in einem eingebetteten X11-Fenster, in das libvlc direkt
malt. Ein gewoehnliches Qt-Kindwidget wuerde davon verdeckt. Deshalb sind
Bedienleiste und Zappliste EIGENE rahmenlose Fenster, die ueber dem Video
schweben. Der Besitzer hat eine Sehschwaeche: grosse Knoepfe, grosse Schrift.
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSlider,
    QListWidget, QListWidgetItem, QLineEdit, QFrame,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

KNOPF = 64
SCHRIFT = 20


def _knopf(zeichen, hinweis, breit=False):
    b = QPushButton(zeichen)
    b.setFixedSize(KNOPF * (2 if breit else 1), KNOPF)
    b.setToolTip(hinweis)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    b.setStyleSheet(
        "QPushButton{background:rgba(24,28,36,220);color:#e8eef8;border:2px solid #3a4léer;"
        "border-radius:10px;font-size:26px;font-weight:700;}"
        "QPushButton:hover{background:rgba(0,180,216,235);color:#08121f;}"
        "QPushButton:pressed{background:#00b4d8;}".replace("#3a4léer", "#3a4658")
    )
    return b


def _zeit(sek):
    sek = max(0, int(sek))
    return f"{sek//3600}:{(sek%3600)//60:02d}:{sek%60:02d}" if sek >= 3600 else f"{sek//60}:{sek%60:02d}"


class VollbildLeiste(QWidget):
    """Schwebende Bedienleiste am unteren Bildrand im Vollbild."""

    beenden = pyqtSignal()
    pause_um = pyqtSignal()
    stopp = pyqtSignal()
    springen = pyqtSignal(int)
    suchen_zu = pyqtSignal(int)
    stumm_um = pyqtSignal()
    lautstaerke = pyqtSignal(int)
    zappliste_um = pyqtSignal()
    kanal_weiter = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._schiebt = False

        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(18, 12, 18, 14)
        aussen.setSpacing(10)

        self.position = QSlider(Qt.Horizontal)
        self.position.setFixedHeight(34)
        self.position.setRange(0, 0)
        self.position.setFocusPolicy(Qt.NoFocus)
        self.position.setStyleSheet(
            "QSlider::groove:horizontal{height:12px;background:#22303f;border-radius:6px;}"
            "QSlider::sub-page:horizontal{background:#00b4d8;border-radius:6px;}"
            "QSlider::handle:horizontal{background:#e8eef8;width:26px;height:26px;"
            "margin:-7px 0;border-radius:13px;}"
        )
        self.position.sliderPressed.connect(self._griff_an)
        self.position.sliderReleased.connect(self._griff_los)
        aussen.addWidget(self.position)

        reihe = QHBoxLayout()
        reihe.setSpacing(12)

        self.b_zurueck = _knopf("⏪", "10 Sekunden zurueck (Pfeil links)")
        self.b_pause = _knopf("⏸", "Pause und weiter (Leertaste)")
        self.b_vor = _knopf("⏩", "10 Sekunden vor (Pfeil rechts)")
        self.b_stopp = _knopf("⏹", "Wiedergabe beenden")
        self.b_zurueck.clicked.connect(lambda: self.springen.emit(-10))
        self.b_vor.clicked.connect(lambda: self.springen.emit(10))
        self.b_pause.clicked.connect(self.pause_um.emit)
        self.b_stopp.clicked.connect(self.stopp.emit)
        for b in (self.b_zurueck, self.b_pause, self.b_vor, self.b_stopp):
            reihe.addWidget(b)

        self.zeit = QLabel("0:00 / 0:00")
        self.zeit.setStyleSheet(f"color:#e8eef8;font-size:{SCHRIFT}px;font-weight:700;padding:0 10px;")
        reihe.addWidget(self.zeit)

        self.titel = QLabel("")
        self.titel.setStyleSheet(f"color:#9fb3c8;font-size:{SCHRIFT}px;")
        self.titel.setMinimumWidth(120)
        reihe.addWidget(self.titel, stretch=1)

        self.b_kanal_ab = _knopf("▲", "Ein Kanal zurueck (Pfeil hoch)")
        self.b_kanal_auf = _knopf("▼", "Ein Kanal weiter (Pfeil runter)")
        self.b_kanal_ab.clicked.connect(lambda: self.kanal_weiter.emit(-1))
        self.b_kanal_auf.clicked.connect(lambda: self.kanal_weiter.emit(1))
        reihe.addWidget(self.b_kanal_ab)
        reihe.addWidget(self.b_kanal_auf)

        self.b_liste = _knopf("☰", "Kanalliste zum Zappen ein und aus (Taste L)")
        self.b_liste.clicked.connect(self.zappliste_um.emit)
        reihe.addWidget(self.b_liste)

        self.b_stumm = _knopf("\U0001f50a", "Stumm schalten (Taste M)")
        self.b_stumm.clicked.connect(self.stumm_um.emit)
        reihe.addWidget(self.b_stumm)

        self.regler = QSlider(Qt.Horizontal)
        self.regler.setFixedWidth(180)
        self.regler.setRange(0, 100)
        self.regler.setFocusPolicy(Qt.NoFocus)
        self.regler.setStyleSheet(
            "QSlider::groove:horizontal{height:10px;background:#22303f;border-radius:5px;}"
            "QSlider::sub-page:horizontal{background:#00b4d8;border-radius:5px;}"
            "QSlider::handle:horizontal{background:#e8eef8;width:24px;height:24px;"
            "margin:-7px 0;border-radius:12px;}"
        )
        self.regler.valueChanged.connect(self.lautstaerke.emit)
        reihe.addWidget(self.regler)

        self.b_beenden = _knopf("⤡", "Vollbild verlassen (Doppelklick, Escape oder F)")
        self.b_beenden.clicked.connect(self.beenden.emit)
        reihe.addWidget(self.b_beenden)

        aussen.addLayout(reihe)
        self.setStyleSheet("QWidget{background:rgba(10,14,20,205);border-radius:16px;}")

    def _griff_an(self):
        self._schiebt = True

    def _griff_los(self):
        self._schiebt = False
        self.suchen_zu.emit(self.position.value())

    def stand(self, jetzt, dauer, spielt, stumm, laut, titel):
        if not self._schiebt:
            self.position.setRange(0, max(0, int(dauer)))
            self.position.setValue(max(0, int(jetzt)))
            self.position.setEnabled(dauer > 0)
        self.zeit.setText(f"{_zeit(jetzt)} / {_zeit(dauer)}" if dauer > 0 else _zeit(jetzt))
        self.b_pause.setText("▶" if not spielt else "⏸")
        self.b_stumm.setText("\U0001f507" if stumm else "\U0001f50a")
        if not self.regler.isSliderDown() and self.regler.value() != int(laut):
            self.regler.blockSignals(True)
            self.regler.setValue(int(laut))
            self.regler.blockSignals(False)
        if titel and self.titel.text() != titel:
            self.titel.setText(titel[:60])

    def platziere(self, rahmen):
        breite = max(900, int(rahmen.width() * 0.92))
        hoehe = 130
        self.setFixedSize(breite, hoehe)
        self.move(rahmen.x() + (rahmen.width() - breite) // 2, rahmen.y() + rahmen.height() - hoehe - 40)


class ZappListe(QWidget):
    """Schwebende Kanalliste am linken Rand. Das Bild laeuft dabei weiter."""

    gewaehlt = pyqtSignal(int)
    schliessen = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._zeilen = []

        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(14, 14, 14, 14)
        aussen.setSpacing(10)

        kopf = QLabel("ZAPPEN")
        kopf.setStyleSheet("color:#00b4d8;font-size:18px;font-weight:800;letter-spacing:2px;")
        aussen.addWidget(kopf)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Kanal suchen")
        self.filter.setFixedHeight(46)
        self.filter.setStyleSheet(
            "QLineEdit{background:#16202c;color:#e8eef8;border:2px solid #3a4658;"
            f"border-radius:10px;padding:6px 12px;font-size:{SCHRIFT}px;}}"
        )
        self.filter.textChanged.connect(self._filtern)
        aussen.addWidget(self.filter)

        self.liste = QListWidget()
        self.liste.setStyleSheet(
            "QListWidget{background:rgba(12,18,26,235);color:#e8eef8;border:2px solid #3a4658;"
            f"border-radius:10px;font-size:{SCHRIFT}px;}}"
            "QListWidget::item{padding:12px 10px;}"
            "QListWidget::item:selected{background:#00b4d8;color:#08121f;}"
            "QScrollBar:vertical{width:22px;background:#16202c;}"
            "QScrollBar::handle:vertical{background:#4a5a6e;border-radius:11px;min-height:40px;}"
        )
        self.liste.itemActivated.connect(self._waehlen)
        self.liste.itemClicked.connect(self._waehlen)
        aussen.addWidget(self.liste, stretch=1)

        hinweis = QLabel("Enter schaltet um, Escape schliesst")
        hinweis.setStyleSheet("color:#9fb3c8;font-size:15px;")
        aussen.addWidget(hinweis)

        self.setStyleSheet("QWidget{background:rgba(10,14,20,225);border-radius:16px;}")

    def fuellen(self, namen, aktiv=-1):
        self._zeilen = list(namen)
        self._filtern(self.filter.text())
        if 0 <= aktiv < self.liste.count():
            self.liste.setCurrentRow(aktiv)
            self.liste.scrollToItem(self.liste.currentItem())

    def _filtern(self, text):
        text = (text or "").strip().lower()
        self.liste.clear()
        for i, name in enumerate(self._zeilen):
            if not text or text in name.lower():
                eintrag = QListWidgetItem(name)
                eintrag.setData(Qt.UserRole, i)
                self.liste.addItem(eintrag)

    def _waehlen(self, eintrag):
        if eintrag is not None:
            self.gewaehlt.emit(int(eintrag.data(Qt.UserRole)))

    def keyPressEvent(self, ereignis):
        if ereignis.key() == Qt.Key_Escape:
            self.schliessen.emit()
            return
        super().keyPressEvent(ereignis)

    def platziere(self, rahmen):
        breite = min(480, max(360, int(rahmen.width() * 0.28)))
        hoehe = int(rahmen.height() * 0.72)
        self.setFixedSize(breite, hoehe)
        self.move(rahmen.x() + 40, rahmen.y() + 40)
