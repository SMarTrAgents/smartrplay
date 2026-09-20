#!/usr/bin/env python3
"""SMarTrPlay - Settings Dialog

QDialog mit SMarTr Brand Design fuer SMarTrPlay Einstellungen.
Verwendet Config-Klasse (config.py) fuer Settings-Speicherung.
"""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSlider,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QPushButton,
    QLabel,
    QGroupBox,
    QScrollArea,
    QFrame,
    QSpacerItem,
    QSizePolicy,
    QWidget,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from config import Config

# Brand Colors (aus theme.py)
BG_DEEP = "#0A0F1E"
BG_CARD = "#121A2E"
BG_CARD_HOVER = "#1A2540"
BORDER = "#232D45"
BORDER_LIGHT = "#2A3550"
TEXT_PRIMARY = "#F5F7FA"
TEXT_SECONDARY = "#9BA5B7"
TEXT_MUTED = "#6B7280"
ACCENT_CYAN = "#1bf1fb"
ACCENT_PURPLE = "#8D7CF6"
ACCENT_VIOLET = "#371689"
SUCCESS = "#10B981"

DIALOG_QSS = f"""
QDialog {{
    background-color: {BG_DEEP};
}}
QLabel {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 16px;
    padding: 20px 16px 16px 16px;
    color: {TEXT_SECONDARY};
    font-weight: 600;
    font-size: 13px;
    background-color: {BG_CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: {ACCENT_CYAN};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QSlider::groove:horizontal {{
    background: {BORDER};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT_CYAN};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_PURPLE};
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_VIOLET};
    border-radius: 3px;
}}
QSpinBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    min-width: 80px;
}}
QSpinBox:focus {{
    border: 1px solid {ACCENT_CYAN};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {BG_CARD_HOVER};
    border: none;
    width: 20px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {ACCENT_PURPLE};
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    spacing: 10px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    background-color: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT_VIOLET};
    border: 1px solid {ACCENT_PURPLE};
    image: none;
}}
QComboBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    min-width: 120px;
}}
QComboBox:hover {{
    border: 1px solid {ACCENT_PURPLE};
}}
QComboBox:focus {{
    border: 1px solid {ACCENT_CYAN};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_VIOLET};
    color: {TEXT_PRIMARY};
}}
QPushButton {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 24px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
    min-width: 80px;
}}
QPushButton:hover {{
    background-color: {BG_CARD_HOVER};
    border: 1px solid {ACCENT_PURPLE};
}}
QPushButton:pressed {{
    background-color: {ACCENT_VIOLET};
}}
QPushButton#saveBtn {{
    background-color: {ACCENT_VIOLET};
    border: none;
}}
QPushButton#saveBtn:hover {{
    background-color: {ACCENT_PURPLE};
}}
QLabel#settingsTitle {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 800;
}}
QLabel#settingsSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}
QLabel#sectionLabel {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}
QLabel#valueLabel {{
    color: {ACCENT_CYAN};
    font-size: 13px;
    font-weight: 600;
    min-width: 40px;
}}
QLabel#brandFooter {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}
QLabel#saveStatusLabel {{
    color: {SUCCESS};
    font-size: 13px;
    font-weight: 600;
    padding: 4px 8px;
}}
"""


class SettingsDialog(QDialog):
    """Settings Dialog fuer SMarTrPlay mit SMarTr Brand Design."""

    # Wird nach jedem erfolgreichen Speichern ausgesendet; eingebettet kann
    # das Hauptfenster darauf reagieren, ohne den Reiterinhalt zu schließen.
    einstellungen_gespeichert = pyqtSignal()

    # Setting keys
    KEY_VOLUME = "player_volume"
    KEY_HWDEC = "player_hwdec"
    KEY_CACHE_SECS = "player_cache_secs"
    KEY_REFRESH_HOURS = "playlist_refresh_hours"
    KEY_DEFAULT_PROVIDER = "default_provider"
    KEY_THEME = "theme"

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config if config is not None else Config()
        self.setWindowTitle("SMarTrPlay - Einstellungen")
        # Nur eine Mindestbreite und keine Mindesthoehe: eingebettet in einen
        # Reiter muss der Inhalt in den verfuegbaren Platz passen, sonst waeren
        # die unteren Knoepfe unerreichbar. Bei grosser Schrift scrollt die
        # eingebaute QScrollArea.
        self.setMinimumWidth(480)
        self.setStyleSheet(DIALOG_QSS)

        self._build_ui()
        self._load_settings()

        # Blendet die Speicher-Bestaetigung nach 2 Sekunden wieder aus
        self._bestaetigungstimer = QTimer(self)
        self._bestaetigungstimer.setSingleShot(True)
        self._bestaetigungstimer.timeout.connect(self.status_label.hide)

    def _build_ui(self):
        """UI aufbauen; der Inhalt liegt in einer QScrollArea, damit bei grosser Schrift gescrollt werden kann."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- Header ---
        title = QLabel("Einstellungen")
        title.setObjectName("settingsTitle")
        layout.addWidget(title)

        subtitle = QLabel("SMarTrPlay Player & Playlist Konfiguration")
        subtitle.setObjectName("settingsSubtitle")
        layout.addWidget(subtitle)

        layout.addItem(QSpacerItem(0, 8, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # --- Player Settings Group ---
        player_group = QGroupBox("PLAYER")
        player_layout = QFormLayout(player_group)
        player_layout.setSpacing(14)
        player_layout.setContentsMargins(16, 24, 16, 16)

        # 1) Player Volume Slider
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setSingleStep(1)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        volume_row = QHBoxLayout()
        volume_row.addWidget(self.volume_slider, 1)
        self.volume_value_label = QLabel("80")
        self.volume_value_label.setObjectName("valueLabel")
        self.volume_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        volume_row.addWidget(self.volume_value_label)

        volume_widget = QWidget()
        volume_widget.setLayout(volume_row)
        volume_section_label = QLabel("Lautstaerke")
        volume_section_label.setObjectName("sectionLabel")
        player_layout.addRow(volume_section_label, volume_widget)

        # 2) Hardware Decoding Checkbox
        self.hwdec_checkbox = QCheckBox("Hardware-Dekodierung aktivieren")
        self.hwdec_checkbox.setToolTip("GPU-beschleunigte Videodekodierung")
        hwdec_section_label = QLabel("HW-Dekodierung")
        hwdec_section_label.setObjectName("sectionLabel")
        player_layout.addRow(hwdec_section_label, self.hwdec_checkbox)

        # 3) Cache Seconds Spinbox
        self.cache_spinbox = QSpinBox()
        self.cache_spinbox.setRange(1, 60)
        self.cache_spinbox.setSuffix(" Sekunden")
        self.cache_spinbox.setToolTip("Stream-Cache-Dauer in Sekunden")
        cache_section_label = QLabel("Cache-Dauer")
        cache_section_label.setObjectName("sectionLabel")
        player_layout.addRow(cache_section_label, self.cache_spinbox)

        layout.addWidget(player_group)

        # --- Playlist Settings Group ---
        playlist_group = QGroupBox("PLAYLIST")
        playlist_layout = QFormLayout(playlist_group)
        playlist_layout.setSpacing(14)
        playlist_layout.setContentsMargins(16, 24, 16, 16)

        # 4) Auto-Refresh Playlist Hours Spinbox
        self.refresh_spinbox = QSpinBox()
        self.refresh_spinbox.setRange(1, 168)
        self.refresh_spinbox.setSuffix(" Stunden")
        self.refresh_spinbox.setToolTip("Automatische Playlist-Aktualisierung (1-168 Stunden)")
        refresh_section_label = QLabel("Auto-Refresh")
        refresh_section_label.setObjectName("sectionLabel")
        playlist_layout.addRow(refresh_section_label, self.refresh_spinbox)

        # 5) Default Provider ComboBox
        self.provider_combo = QComboBox()
        self.provider_combo.setToolTip("Standard-Provider fuer SMarTrPlay")
        self._populate_providers()
        provider_section_label = QLabel("Standard-Provider")
        provider_section_label.setObjectName("sectionLabel")
        playlist_layout.addRow(provider_section_label, self.provider_combo)

        layout.addWidget(playlist_group)

        # --- Appearance Settings Group ---
        appearance_group = QGroupBox("ERSCHEINUNGSBILD")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(14)
        appearance_layout.setContentsMargins(16, 24, 16, 16)

        # 6) Theme ComboBox (nur Dark verfuegbar)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.setItemData(1, 0, Qt.UserRole - 1)  # Light deaktivieren
        item_model = self.theme_combo.model()
        light_item = item_model.item(1)
        if light_item is not None:
            light_item.setEnabled(False)
        self.theme_combo.setToolTip("Nur Dark-Theme verfuegbar")
        theme_section_label = QLabel("Theme")
        theme_section_label.setObjectName("sectionLabel")
        appearance_layout.addRow(theme_section_label, self.theme_combo)

        layout.addWidget(appearance_group)

        # --- Spacer ---
        layout.addItem(QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # --- Footer Brand ---
        footer = QLabel("SMarTrPlay v1.0.0  |  SMarTrAgents")
        footer.setObjectName("brandFooter")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

        # Kurze Bestaetigung im Dialog selbst, nachdem eingebettet gespeichert wurde
        self.status_label = QLabel("✓ Einstellungen gespeichert")
        self.status_label.setObjectName("saveStatusLabel")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _populate_providers(self):
        """Provider-ComboBox aus Config fuellen."""
        self.provider_combo.clear()
        self.provider_combo.addItem("(Kein Provider)", 0)
        try:
            providers = self.config.get_providers()
            for p in providers:
                provider_id = p[0]
                provider_name = p[1]
                self.provider_combo.addItem(provider_name, provider_id)
        except Exception:
            pass

    def _load_settings(self):
        """Aktuelle Werte aus Config laden und UI setzen."""
        # 1) Volume
        vol = self.config.get_setting(self.KEY_VOLUME, Config.PLAYER_VOLUME)
        try:
            vol = int(vol)
        except (TypeError, ValueError):
            vol = Config.PLAYER_VOLUME
        vol = max(0, min(100, vol))
        self.volume_slider.setValue(vol)
        self.volume_value_label.setText(str(vol))

        # 2) Hardware Decoding
        hwdec = self.config.get_setting(self.KEY_HWDEC, Config.PLAYER_HWDEC)
        if isinstance(hwdec, str):
            hwdec = hwdec.lower() in ("true", "1", "yes")
        self.hwdec_checkbox.setChecked(bool(hwdec))

        # 3) Cache Seconds
        cache = self.config.get_setting(self.KEY_CACHE_SECS, Config.PLAYER_CACHE_SECS)
        try:
            cache = int(cache)
        except (TypeError, ValueError):
            cache = Config.PLAYER_CACHE_SECS
        cache = max(1, min(60, cache))
        self.cache_spinbox.setValue(cache)

        # 4) Refresh Hours
        refresh = self.config.get_setting(self.KEY_REFRESH_HOURS, Config.PLAYLIST_REFRESH_HOURS)
        try:
            refresh = int(refresh)
        except (TypeError, ValueError):
            refresh = Config.PLAYLIST_REFRESH_HOURS
        refresh = max(1, min(168, refresh))
        self.refresh_spinbox.setValue(refresh)

        # 5) Default Provider
        default_provider = self.config.get_setting(self.KEY_DEFAULT_PROVIDER, 0)
        try:
            default_provider = int(default_provider)
        except (TypeError, ValueError):
            default_provider = 0
        idx = self.provider_combo.findData(default_provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        else:
            self.provider_combo.setCurrentIndex(0)

        # 6) Theme (nur Dark)
        theme = self.config.get_setting(self.KEY_THEME, "dark")
        if theme == "light":
            theme = "dark"
        idx = self.theme_combo.findData(theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        else:
            self.theme_combo.setCurrentIndex(0)

    def _on_volume_changed(self, value):
        """Volume-Slider Aenderung anzeigen."""
        self.volume_value_label.setText(str(value))

    def _save_settings(self):
        """Settings in Config speichern."""
        self.config.set_setting(self.KEY_VOLUME, self.volume_slider.value())
        self.config.set_setting(self.KEY_HWDEC, self.hwdec_checkbox.isChecked())
        self.config.set_setting(self.KEY_CACHE_SECS, self.cache_spinbox.value())
        self.config.set_setting(self.KEY_REFRESH_HOURS, self.refresh_spinbox.value())
        self.config.set_setting(self.KEY_DEFAULT_PROVIDER, self.provider_combo.currentData())
        self.config.set_setting(self.KEY_THEME, self.theme_combo.currentData())

    def _ist_eingebettet(self):
        """True, wenn der Dialog kein eigenes Fenster ist (z. B. in einen Reiter eingebettet)."""
        return not bool(self.windowFlags() & Qt.Window)

    def showEvent(self, event):
        """Abbrechen-Knopf im eingebetteten Zustand ausblenden.

        Die Fensterflags stehen beim ersten Sichtbarwerden fest; eingebettet
        wuerde reject() den gesamten Reiterinhalt unsichtbar machen.
        """
        super().showEvent(event)
        self.cancel_btn.setVisible(not self._ist_eingebettet())

    def _on_cancel(self):
        """Abbrechen: nur als eigenstaendiges Fenster schliessen."""
        if not self._ist_eingebettet():
            self.reject()

    def _save_and_close(self):
        """Einstellungen speichern und Signal aussenden.

        Als eigenstaendiges Fenster wird der Dialog danach geschlossen (accept).
        Eingebettet bleibt er sichtbar und bestaetigt das Speichern im Dialog
        selbst, weil accept() den Reiterinhalt sonst verschwinden liesse.
        """
        self._save_settings()
        self.einstellungen_gespeichert.emit()
        if self._ist_eingebettet():
            self._zeige_bestaetigung()
        else:
            self.accept()

    def _zeige_bestaetigung(self):
        """Kurzen Bestaetigungshinweis anzeigen und nach 2 Sekunden ausblenden."""
        self.status_label.show()
        self._bestaetigungstimer.start(2000)

    def get_settings(self):
        """Aktuelle Settings als Dictionary zurueckgeben."""
        return {
            self.KEY_VOLUME: self.volume_slider.value(),
            self.KEY_HWDEC: self.hwdec_checkbox.isChecked(),
            self.KEY_CACHE_SECS: self.cache_spinbox.value(),
            self.KEY_REFRESH_HOURS: self.refresh_spinbox.value(),
            self.KEY_DEFAULT_PROVIDER: self.provider_combo.currentData(),
            self.KEY_THEME: self.theme_combo.currentData(),
        }


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = SettingsDialog()
    if dialog.exec_():
        print("Settings gespeichert:")
        for key, value in dialog.get_settings().items():
            print(f"  {key}: {value}")
    sys.exit(0)
