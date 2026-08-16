#!/usr/bin/env python3
"""SMarTrPlay - Entry Point
SMarTrAgents IPTV Player for M3U, M3U+, Xtream Codes API
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from main_window import MainWindow
from theme import apply_theme


def main():
    # High DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("SMarTrPlay")
    app.setApplicationDisplayName("SMarTrPlay - IPTV Player")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SMarTrAgents")

    # Apply SMarTr Brand Theme
    apply_theme(app)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Start event loop
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
