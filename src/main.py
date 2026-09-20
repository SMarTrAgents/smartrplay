#!/usr/bin/env python3
"""SMarTrPlay - Entry Point
SMarTrAgents IPTV Player for M3U, M3U+, Xtream Codes API
"""

import sys
import os
# resource gibt es nur auf Unix. Unter Windows wuerde der Import die
# Anwendung sofort beenden, deshalb wird er dort uebersprungen.
try:
    import resource
except ImportError:
    resource = None
import logging
import tempfile

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
def _protokollordner():
    """Liefert einen Ordner, in den wirklich geschrieben werden darf.

    Als AppImage oder als installiertes Windows-Programm liegt die Anwendung
    in einem schreibgeschuetzten Verzeichnis. Ein Protokollordner daneben
    laesst sich dort nicht anlegen, und die Anwendung startete gar nicht erst.
    Deshalb zuerst der Ordner des Nutzers, der auch die Datenbank traegt,
    und erst als Rueckfall ein temporaerer Ordner.
    """
    kandidaten = [
        os.path.join(os.path.expanduser('~'), 'SMarTrPlay', 'logs'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs'),
        os.path.join(tempfile.gettempdir(), 'SMarTrPlay-logs'),
    ]
    for ordner in kandidaten:
        try:
            os.makedirs(ordner, exist_ok=True)
            probe = os.path.join(ordner, '.schreibprobe')
            with open(probe, 'w') as f:
                f.write('ok')
            os.remove(probe)
            return ordner
        except OSError:
            continue
    return tempfile.gettempdir()


_log_dir = _protokollordner()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(_log_dir, 'smartrplay.log'))
    ]
)
logger = logging.getLogger('SMarTrPlay')


def increase_fd_limit():
    """Erhoehe File-Descriptor-Limit um EMFILE (Too many open files) zu verhindern.

    Unter Windows gibt es diese Grenze nicht, dort ist nichts zu tun.
    """
    if resource is None:
        return
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        new_soft = min(hard, 65536)
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
        logger.info(f"FD-Limit erhoeht: {soft} -> {new_soft} (hard: {hard})")
    except Exception as e:
        logger.warning(f"Konnte FD-Limit nicht erhoehen: {e}")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from main_window import MainWindow
from theme import apply_theme


def main():
    # File-Descriptor-Limit erhoehen (EMFILE Prevention)
    increase_fd_limit()

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
