#!/usr/bin/env python3
"""SMarTrPlay - Auto-Refresh Manager fuer Playlists."""

import time
import threading
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer


class AutoRefreshManager(QObject):
    """Aktualisiert Playlists periodisch im Hintergrund."""

    refresh_started = pyqtSignal()
    refresh_success = pyqtSignal(dict)
    refresh_error = pyqtSignal(str)
    refresh_progress = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.interval_hours = 24
        self.enabled = False
        self._thread = None
        self._running = False
        self._lock = threading.Lock()

    def set_interval(self, hours):
        self.interval_hours = max(1, min(168, hours))
        if self._running:
            self.restart()

    def start(self):
        if self._running:
            return
        self.enabled = True
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.status_changed.emit("Auto-Refresh aktiv")

    def stop(self):
        self._running = False
        self.enabled = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self.status_changed.emit("Auto-Refresh gestoppt")

    def restart(self):
        self.stop()
        self.start()

    def trigger_now(self):
        self.refresh_progress.emit("Manueller Refresh ausgeloest")
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _run_loop(self):
        while self._running:
            self._do_refresh()
            wait_seconds = self.interval_hours * 3600
            for _ in range(wait_seconds):
                if not self._running:
                    break
                time.sleep(1)

    def _do_refresh(self):
        with self._lock:
            self.refresh_started.emit()
            self.refresh_progress.emit("Aktualisiere Playlists...")

            try:
                from config import Config
                from m3u_parser import M3UParser
                from xtream_api import XtreamAPI

                config = Config()
                providers = config.get_providers()
                total_channels = 0

                for p in providers:
                    pid, name, ptype, url, username = p
                    full = config.get_provider(pid)
                    password = full[5] if full else None

                    self.refresh_progress.emit(f"Lade: {name}...")

                    if ptype == "m3u" and url:
                        parser = M3UParser()
                        channels = parser.parse_url(url)
                    elif ptype == "xtream" and url and username and password:
                        api = XtreamAPI(url, username, password)
                        channels = api.get_all_channels()
                    else:
                        continue

                    config.add_channels(pid, channels)
                    total_channels += len(channels)

                result = {"providers": len(providers), "channels": total_channels}
                self.refresh_success.emit(result)
                self.refresh_progress.emit(f"Fertig: {total_channels} Kanaele")

            except Exception as e:
                self.refresh_error.emit(str(e))
                self.refresh_progress.emit(f"Fehler: {e}")


def create_auto_refresh_manager(interval_hours=24, parent=None):
    mgr = AutoRefreshManager(parent)
    mgr.interval_hours = interval_hours
    return mgr


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QLabel
    app = QApplication(sys.argv)
    mgr = AutoRefreshManager()
    mgr.refresh_progress.connect(lambda msg: print(f"[Progress] {msg}"))
    mgr.refresh_success.connect(lambda d: print(f"[Success] {d}"))
    mgr.refresh_error.connect(lambda e: print(f"[Error] {e}"))
    mgr.trigger_now()
    QTimer.singleShot(5000, app.quit)
    app.exec_()
