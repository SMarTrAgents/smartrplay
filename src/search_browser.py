#!/usr/bin/python3
"""SMarTrPlay - Global Search Browser

Durchsucht alle Inhaltstypen: Live TV, VOD (Filme), Serien.
Funktioniert mit Xtream Codes API und M3U (SQLite).
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QWidget, QSplitter,
    QProgressBar, QComboBox, QMessageBox, QFrame
)
from PyQt5.QtGui import QPixmap, QIcon
import fadenpark


# === SMarTr Brand Colors ===
BG_DEEP = "#0A0F1E"
BG_CARD = "#121A2E"
BG_CARD_HOVER = "#1A2540"
BORDER = "#232D45"
TEXT_PRIMARY = "#F5F7FA"
TEXT_SECONDARY = "#9BA5B7"
ACCENT_CYAN = "#1bf1fb"
ACCENT_PURPLE = "#8D7CF6"
ACCENT_VIOLET = "#371689"
SUCCESS = "#10B981"
WARNING = "#F59E0B"

SEARCH_STYLE = f"""
QDialog {{
    background-color: {BG_DEEP};
    color: {TEXT_PRIMARY};
}}
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QLineEdit {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 16px;
}}
QLineEdit:focus {{
    border-color: {ACCENT_CYAN};
}}
QListWidget {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: 6px;
    margin: 2px;
}}
QListWidget::item:hover {{
    background-color: {BG_CARD_HOVER};
}}
QListWidget::item:selected {{
    background-color: {ACCENT_VIOLET};
    color: {TEXT_PRIMARY};
}}
QPushButton {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 14px;
}}
QPushButton:hover {{
    background-color: {BG_CARD_HOVER};
    border-color: {ACCENT_CYAN};
}}
QPushButton:pressed {{
    background-color: {ACCENT_VIOLET};
}}
QComboBox {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 12px;
}}
QProgressBar {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    color: {TEXT_PRIMARY};
}}
QProgressBar::chunk {{
    background-color: {ACCENT_CYAN};
    border-radius: 6px;
}}
QFrame {{
    background: transparent;
}}
"""


# ----------------------------------------------------------------------
# Thread-Entsorgung
# ----------------------------------------------------------------------

def thread_sicher_entsorgen(thread, ablage, wartezeit_ms=3000, name=""):
    """QThread sicher entsorgen. Leitet auf den zentralen Fadenpark weiter.

    Die frueher hier eingebaute Fassung hat einen noch laufenden Faden zwar in
    eine Liste gehaengt, ihn aber NICHT von seinem Elternfenster geloest. Da
    die Ladefaeden mit dem Fenster als Qt-Elternobjekt erzeugt werden, hat Qt
    sie beim Loeschen des Fensters trotzdem mitgerissen. Gemessen am
    19.09.2026 beim Providerwechsel waehrend eines laufenden Serienabrufs.
    Der Fadenpark nabelt den Faden ab und haelt ihn modulweit fest.
    Der Parameter ablage bleibt aus Vertraeglichkeitsgruenden erhalten.
    """
    fadenpark.entsorge_faden(thread, wartezeit_ms=wartezeit_ms, name=name)

class SearchWorker(QThread):
    """Sucht im Hintergrund across Live, VOD und Series."""
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.api = None
        self.config = None
        self.provider_id = None
        self.provider_type = None
        self.query = ""
        self._abbruch = False

    def cancel(self):
        """Abbruchflag setzen; die Suche endet nach dem laufenden Schritt.

        Der Faden ueberschreibt run() ohne exec_(), deshalb ist quit() bei
        ihm wirkungslos — nur dieses Abbruchflag wirkt.
        """
        self._abbruch = True

    def setup_xtream(self, api, query):
        self.api = api
        self.query = query
        self.provider_type = "xtream"

    def setup_m3u(self, config, provider_id, query):
        self.config = config
        self.provider_id = provider_id
        self.query = query
        self.provider_type = "m3u"

    def run(self):
        try:
            results = []
            if self._abbruch:
                # Bereits abgebrochen, bevor der Faden ueberhaupt startete
                self.results_ready.emit(results)
                return
            if self.provider_type == "xtream":
                results = self._search_xtream()
            else:
                results = self._search_m3u()
            self.results_ready.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _search_xtream(self):
        """Durchsucht Xtream API: Live, VOD, Series."""
        results = []
        q_lower = self.query.lower()

        # Live TV Streams
        try:
            self.progress.emit("Durchsuche Live TV...")
            live_streams = self.api.get_live_streams()
            for stream in live_streams:
                name = stream.get("name", "")
                if q_lower in name.lower():
                    results.append({
                        "type": "live",
                        "name": name,
                        "stream_id": stream.get("stream_id"),
                        "logo": stream.get("stream_icon", ""),
                        "category": stream.get("category_id", ""),
                        "url": None,
                    })
        except Exception:
            pass

        if self._abbruch:
            # Abgebrochen: weitere Suchschritte nicht mehr anfassen
            return results

        # VOD Streams (Filme)
        try:
            self.progress.emit("Durchsuche Filme (VOD)...")
            vod_streams = self.api.get_vod_streams()
            for stream in vod_streams:
                name = stream.get("name", "")
                if q_lower in name.lower():
                    results.append({
                        "type": "vod",
                        "name": name,
                        "stream_id": stream.get("stream_id"),
                        "logo": stream.get("stream_icon", ""),
                        "rating": stream.get("rating", ""),
                        "container_ext": stream.get("container_extension", "mp4"),
                        "url": None,
                    })
        except Exception:
            pass

        if self._abbruch:
            # Abgebrochen: weitere Suchschritte nicht mehr anfassen
            return results

        # Series
        try:
            self.progress.emit("Durchsuche Serien...")
            series_list = self.api.get_series()
            for series in series_list:
                name = series.get("name", "")
                if q_lower in name.lower():
                    results.append({
                        "type": "series",
                        "name": name,
                        "stream_id": series.get("series_id"),
                        "logo": series.get("cover", ""),
                        "rating": series.get("rating", ""),
                        "url": None,
                    })
        except Exception:
            pass

        return results

    def _search_m3u(self):
        """Durchsucht SQLite channels-Tabelle."""
        results = []
        if self._abbruch:
            return results
        q_lower = self.query.lower()
        channels = self.config.get_channels(
            provider_id=self.provider_id,
            search=self.query
        )
        for ch in channels:
            ch_type = ch[8] if len(ch) > 8 else "live"
            results.append({
                "type": ch_type,
                "name": ch[2],
                "stream_id": None,
                "logo": ch[4] if ch[4] else "",
                "url": ch[3],
                "category": ch[5] if ch[5] else "",
            })
        return results


class SearchBrowser(QDialog):
    """Globaler Such-Dialog fuer SMarTrPlay."""

    def __init__(self, provider_type="xtream", api=None, config=None,
                 provider_id=None, player=None, parent=None):
        super().__init__(parent)
        self.provider_type = provider_type
        self.api = api
        self.config = config
        self.provider_id = provider_id
        self.player = player
        self.results = []
        self.worker = None
        self._zombie_threads = []       # noch laufende Faeden, die spaeter aufgeraeumt werden
        self._letzte_aktivierung = 0.0  # Zeitschutz gegen doppelte Aktivierung

        self.setWindowTitle("SMarTrPlay - Globale Suche")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(SEARCH_STYLE)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_label = QLabel("Globale Suche")
        header_label.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {ACCENT_CYAN};"
        )
        layout.addWidget(header_label)

        sub_label = QLabel("Durchsucht Live TV, Filme (VOD) und Serien gleichzeitig.")
        sub_label.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        layout.addWidget(sub_label)

        # Suchfeld
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Suchbegriff eingeben und Enter druecken..."
        )
        self.search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_input)

        self.search_btn = QPushButton("Suchen")
        self.search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(self.search_btn)

        layout.addLayout(search_layout)

        # Filter Dropdown
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        filter_layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Alle", "Live TV", "Filme (VOD)", "Serien"])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_combo)

        filter_layout.addStretch()

        self.result_count_label = QLabel("0 Ergebnisse")
        self.result_count_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        filter_layout.addWidget(self.result_count_label)

        layout.addLayout(filter_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        # Ergebnis-Liste
        self.result_list = QListWidget()
        self.result_list.itemDoubleClicked.connect(self._on_result_double_click)
        # Zusaetzlich itemActivated verbinden, damit die Eingabetaste
        # dieselbe Aktion ausloest (Tastaturbedienung).
        self.result_list.itemActivated.connect(self._on_result_double_click)
        layout.addWidget(self.result_list)

        # Info Label
        self.info_label = QLabel(
            "Doppelklick auf Ergebnis zum Abspielen. "
            "Live TV = direkter Playback, VOD = direkter Playback, "
            "Serien = oeffnet Serien-Browser."
        )
        self.info_label.setStyleSheet(
            f"font-size: 12px; color: {TEXT_SECONDARY}; padding: 4px;"
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.play_btn = QPushButton("Abspielen")
        self.play_btn.clicked.connect(self._play_selected)
        btn_layout.addWidget(self.play_btn)

        self.close_btn = QPushButton("Schliessen")
        self.close_btn.clicked.connect(self._on_close_clicked)
        self._close_btn_anpassen()
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _ist_eingebettet(self):
        """Pruefen, ob dieser Dialog als Reiter-Widget eingebettet ist.

        Eingebettet bedeutet: kein eigenes Fenster. Die windowFlags-Pruefung
        allein genuegt nicht, weil Qt bei Widgets ohne Eltern das Fenster-Bit
        erzwingt; der Vergleich mit window() deckt auch diesen Fall ab.
        """
        if int(self.windowFlags() & Qt.Window) == 0:
            return True
        return self.window() is not self

    def _close_btn_anpassen(self):
        """Schliessen-Knopf im eingebetteten Zustand ausblenden.

        Als Reiter-Widget wuerde self.close() den gesamten Reiterinhalt
        verschwinden lassen, und er kommt nicht wieder. Als eigenstaendiges
        Fenster bleibt der Knopf wie bisher sichtbar.
        """
        eingebettet = self._ist_eingebettet()
        self.close_btn.setVisible(not eingebettet)

    def _on_close_clicked(self):
        """Schliessen-Knopf: nur als eigenstaendiges Fenster wirklich schliessen."""
        if self._ist_eingebettet():
            return
        self.close()

    def showEvent(self, event):
        """Beim Anzeigen erneut pruefen: main_window setzt die Fensterflags
        erst nach der Erzeugung dieses Dialogs."""
        super().showEvent(event)
        self._close_btn_anpassen()

    def _do_search(self):
        """Startet die Suche."""
        query = self.search_input.text().strip()
        if not query:
            return

        if len(query) < 2:
            QMessageBox.information(self, "Suche", "Mindestens 2 Zeichen eingeben.")
            return

        # UI aktualisieren
        self.result_list.clear()
        self.results = []
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)

        # Vorherigen Worker sicher entsorgen. Das bisherige wait() ohne
        # Zeitlimit hat die Oberflaeche bis zu 45 Sekunden eingefroren
        # (drei Xtream-Aufrufe mit je 15 Sekunden Zeitlimit). Die Signale
        # werden getrennt, damit ein noch laufender alter Worker die neue
        # Suche nicht mit veralteten Ergebnissen ueberschreibt.
        if self.worker:
            try:
                self.worker.results_ready.disconnect()
                self.worker.error_occurred.disconnect()
                self.worker.progress.disconnect()
            except (TypeError, RuntimeError):
                pass
            thread_sicher_entsorgen(
                self.worker, self._zombie_threads, name="SearchWorker"
            )

        self.worker = SearchWorker()
        if self.provider_type == "xtream" and self.api:
            self.worker.setup_xtream(self.api, query)
        elif self.config and self.provider_id:
            self.worker.setup_m3u(self.config, self.provider_id, query)
        else:
            self._search_finished([])
            return

        self.worker.results_ready.connect(self._search_finished)
        self.worker.error_occurred.connect(self._search_error)
        self.worker.progress.connect(self._search_progress)
        self.worker.start()

    def _search_progress(self, msg):
        self.progress_label.setText(msg)

    def _search_finished(self, results):
        self.results = results
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self._apply_filter()

    def _search_error(self, err):
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        QMessageBox.warning(self, "Suche", f"Fehler bei der Suche: {err}")

    def _apply_filter(self):
        """Filtert Ergebnisse nach Typ."""
        self.result_list.clear()
        filter_idx = self.filter_combo.currentIndex()

        type_filters = [None, "live", "vod", "series"]
        active_filter = type_filters[filter_idx]

        filtered = []
        for r in self.results:
            if active_filter is None or r["type"] == active_filter:
                filtered.append(r)

        for r in filtered:
            type_icon = self._type_icon(r["type"])
            rating = f" | Rating: {r.get('rating', '-')}" if r.get('rating') else ""
            item_text = f"{type_icon}  {r['name']}{rating}"
            item = QListWidgetItem(item_text)

            # Color by type
            if r["type"] == "live":
                item.setForeground(Qt.white)
            elif r["type"] == "vod":
                item.setForeground(Qt.cyan)
            elif r["type"] == "series":
                item.setForeground(Qt.magenta)

            item.setData(Qt.UserRole, r)
            self.result_list.addItem(item)

        count = len(filtered)
        total = len(self.results)
        if active_filter:
            self.result_count_label.setText(f"{count} von {total} Ergebnissen")
        else:
            self.result_count_label.setText(f"{count} Ergebnisse")

    def _type_icon(self, type_name):
        icons = {"live": "[TV]", "vod": "[FILM]", "series": "[SERIE]"}
        return icons.get(type_name, "[?]")

    def _on_result_double_click(self, item):
        self._play_item(item)

    def _play_selected(self):
        item = self.result_list.currentItem()
        if item:
            self._play_item(item)

    def _aktion_freigeben(self):
        """Zeitschutz gegen doppelte Aktivierung.

        Ein Doppelklick loest itemDoubleClicked und itemActivated praktisch
        gleichzeitig aus; ohne diesen Schutz wuerde die Wiedergabe doppelt
        starten. Der Abspielen-Knopf nutzt denselben Schutz.
        """
        jetzt = time.monotonic()
        if jetzt - self._letzte_aktivierung < 0.3:
            return False
        self._letzte_aktivierung = jetzt
        return True

    def _play_item(self, item):
        """Spielt ausgewaehltes Ergebnis ab (Doppelklick, Eingabetaste oder Knopf)."""
        if not self._aktion_freigeben():
            return
        r = item.data(Qt.UserRole)
        if not r:
            return

        rtype = r.get("type", "live")

        if rtype == "live":
            if r.get("url"):
                url = r["url"]
            elif self.api and r.get("stream_id"):
                url = self.api.get_stream_url(r["stream_id"], "live")
            else:
                QMessageBox.warning(self, "Playback", "Keine URL fuer diesen Kanal.")
                return
            self._start_playback(url)

        elif rtype == "vod":
            if self.api and r.get("stream_id"):
                ext = r.get("container_ext", "mp4")
                url = self.api.get_stream_url(r["stream_id"], "vod", ext)
                self._start_playback(url)
            elif r.get("url"):
                self._start_playback(r["url"])
            else:
                QMessageBox.warning(self, "Playback", "Keine URL fuer diesen Film.")

        elif rtype == "series":
            # Serie: Dialog schliessen, Parent muss Series Browser oeffnen
            QMessageBox.information(
                self, "Serie",
                f"Serie: {r['name']}\n\n"
                "Bitte oeffne den Serien-Browser ueber Ansicht > Serien durchsuchen "
                "um Episoden auszuwaehlen."
            )

    def _start_playback(self, url):
        if not url:
            QMessageBox.warning(self, "Playback", "Keine Stream-URL gefunden.")
            return

        if self.player:
            try:
                container = self.findChild(QWidget, "video_container")
                wid = 0
                if container:
                    wid = int(container.winId())
                else:
                    # Rueckfall: Der Objektname "video_container" wird
                    # nirgends vergeben, deshalb schlaegt findChild immer
                    # fehl und beim Abspielen aus der Suche erschien kein
                    # Bild. Wir suchen das Attribut am Elternfenster (nur
                    # lesend) und nutzen dessen Fensterkennung.
                    elternfenster = self.window()
                    video_container = getattr(
                        elternfenster, "video_container", None
                    )
                    if video_container is not None:
                        try:
                            wid = int(video_container.winId())
                        except (AttributeError, TypeError, RuntimeError):
                            wid = 0
                self.player.play(url, wid)
                self.status_bar_msg(f"Playback: {url[:60]}...")
            except Exception as e:
                QMessageBox.warning(self, "Playback", f"Fehler: {e}")
        else:
            QMessageBox.information(self, "Playback", f"URL: {url}")

    def status_bar_msg(self, msg):
        parent = self.parent()
        if parent and hasattr(parent, "status_bar"):
            parent.status_bar.showMessage(msg, 3000)

    def closeEvent(self, event):
        """Worker sicher entsorgen statt unbegrenzt zu warten."""
        thread_sicher_entsorgen(
            self.worker, self._zombie_threads, name="SearchWorker"
        )
        self.worker = None
        event.accept()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dialog = SearchBrowser()
    dialog.show()
    sys.exit(app.exec_())
