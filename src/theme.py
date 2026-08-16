#!/usr/bin/env python3
"""SMarTrPlay - SMarTr Brand Theme"""

from PyQt5.QtGui import QFont, QFontDatabase, QColor, QPalette, QLinearGradient, QBrush, QPixmap
from PyQt5.QtCore import Qt, QMargins

# Brand Colors
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
WARNING = "#F59E0B"
ERROR = "#EF4444"


def get_font():
    """Inter Font oder Fallback."""
    font_id = QFontDatabase.addApplicationFont("Inter")
    if font_id == -1:
        # Try system Inter
        font_id = QFontDatabase.addApplicationFont("/usr/share/fonts/inter/Inter-Regular.ttf")
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            return QFont(families[0])
    return QFont("DejaVu Sans")


def apply_theme(app):
    """SMarTr Brand Theme auf QApplication anwenden."""
    font = get_font()
    font.setPointSize(11)
    app.setFont(font)

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG_DEEP))
    palette.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(BG_CARD))
    palette.setColor(QPalette.AlternateBase, QColor(BG_CARD_HOVER))
    palette.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(BG_CARD))
    palette.setColor(QPalette.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(ACCENT_VIOLET))
    palette.setColor(QPalette.HighlightedText, QColor(TEXT_PRIMARY))
    app.setPalette(palette)

    app.setStyleSheet(QSS)


QSS = f"""
* {{
    font-family: 'Inter', 'DejaVu Sans', sans-serif;
}}

QMainWindow, QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT_PRIMARY};
}}

QMenuBar {{
    background-color: {BG_DEEP};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 4px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 6px 16px;
    border-radius: 6px;
}}

QMenuBar::item:selected {{
    background-color: {BG_CARD_HOVER};
}}

QMenu {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 24px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background-color: {BG_CARD_HOVER};
}}

QScrollBar:vertical {{
    background: {BG_DEEP};
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT_PURPLE};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {BG_DEEP};
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_PURPLE};
}}

QListWidget {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    padding: 10px 12px;
    border-radius: 6px;
    color: {TEXT_SECONDARY};
}}

QListWidget::item:selected {{
    background-color: {ACCENT_VIOLET};
    color: {TEXT_PRIMARY};
}}

QListWidget::item:hover {{
    background-color: {BG_CARD_HOVER};
}}

QLineEdit {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 14px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QLineEdit:focus {{
    border: 1px solid {ACCENT_CYAN};
}}

QPushButton {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 20px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {BG_CARD_HOVER};
    border: 1px solid {ACCENT_PURPLE};
}}

QPushButton:pressed {{
    background-color: {ACCENT_VIOLET};
}}

QPushButton#primaryBtn {{
    background-color: {ACCENT_VIOLET};
    border: none;
}}

QPushButton#primaryBtn:hover {{
    background-color: {ACCENT_PURPLE};
}}

QLabel#headerTitle {{
    color: {TEXT_PRIMARY};
    font-size: 22px;
    font-weight: 800;
}}

QLabel#headerSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

QLabel#sidebarTitle {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 8px 12px 4px 12px;
}}

QLabel#channelName {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
}}

QLabel#channelCategory {{
    color: {TEXT_MUTED};
    font-size: 10px;
}}

QSplitter::handle {{
    background-color: {BORDER};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

QToolBar {{
    background-color: {BG_DEEP};
    border-bottom: 1px solid {BORDER};
    spacing: 8px;
    padding: 6px;
}}

QStatusBar {{
    background-color: {BG_DEEP};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG_CARD};
}}

QTabBar::tab {{
    background: {BG_DEEP};
    color: {TEXT_SECONDARY};
    padding: 8px 20px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:selected {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
}}

QComboBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    color: {TEXT_PRIMARY};
}}

QComboBox:hover {{
    border: 1px solid {ACCENT_PURPLE};
}}

QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_VIOLET};
}}

QDialog {{
    background-color: {BG_CARD};
}}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    color: {TEXT_SECONDARY};
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT_CYAN};
}}

QProgressBar {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    height: 18px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT_VIOLET};
    border-radius: 5px;
}}

QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    padding: 4px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    background-color: {BG_CARD};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT_VIOLET};
    border: 1px solid {ACCENT_PURPLE};
}}

QSlider::groove:horizontal {{
    background: {BG_DEEP};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {ACCENT_PURPLE};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {ACCENT_CYAN};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {BG_DEEP};
    color: {TEXT_SECONDARY};
    padding: 6px 10px;
    border: 1px solid {BORDER};
    font-weight: 600;
}}

QTableView, QTreeView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
}}

QTableView::item:selected, QTreeView::item:selected {{
    background-color: {ACCENT_VIOLET};
}}

QTableView::item:hover, QTreeView::item:hover {{
    background-color: {BG_CARD_HOVER};
}}
"""
