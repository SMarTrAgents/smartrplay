#!/usr/bin/env python3
"""Abnahme fuer SMarTrPlay: bedient die fertige Anwendung und misst das Verhalten.
Aufruf: DISPLAY=:0 .venv/bin/python tests/abnahme.py
"""
import sys, os, time, sqlite3
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

# Pfade relativ zum Projekt, damit der Lauf in jedem Klon funktioniert.
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, 'src'))

from PyQt5.QtWidgets import QApplication, QScrollArea, QListWidget
from PyQt5.QtCore import Qt, QTimer

ok = fail = 0
def pruef(name, bedingung, mess=""):
    global ok, fail
    print(f"{'OK    ' if bedingung else 'FEHLER'} {name:54s} {mess}", flush=True)
    if bedingung: ok += 1
    else: fail += 1

def warte(app, sekunden):
    ende = time.time() + sekunden
    while time.time() < ende:
        app.processEvents()
        time.sleep(0.02)

from theme import apply_theme
import main_window as mw

app = QApplication(sys.argv)
apply_theme(app)
t0 = time.perf_counter()
fenster = mw.MainWindow()
fenster.show()
warte(app, 3)
pruef("Fenster startet", fenster.isVisible(), f"{(time.perf_counter()-t0):.1f} s bis sichtbar")

# 1 Player
pruef("Player ist das VLC-Backend", type(fenster.player).__name__ == "VlcPlayerBackend",
      type(fenster.player).__name__)
pruef("Alte doppelte Bedienleiste entfernt", not hasattr(fenster, 'btn_play'),
      "btn_play " + ("weg" if not hasattr(fenster,'btn_play') else "NOCH DA"))
pruef("Stummknopf hat ein Signal", hasattr(fenster.video_controls, 'mute_clicked'))
pruef("Videoflaeche traegt ihren Namen",
      fenster.video_container.objectName() == "video_container",
      fenster.video_container.objectName())

# 2 Bildlaufflaechen
flaechen = fenster.findChildren(QScrollArea)
pruef("Bildlaufflaechen vorhanden", len(flaechen) >= 4, f"{len(flaechen)} QScrollArea")
listen = fenster.findChildren(QListWidget)
aus = [l for l in listen if l.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff]
pruef("Keine Liste mit abgeschalteter Bildlaufleiste", len(aus) == 0,
      f"{len(listen)} Listen, {len(aus)} ohne Leiste")

# 3 Schriftgroesse
g_vorher = app.font().pointSize()
import theme
theme.setze_schriftgroesse(app, g_vorher + 4)
g_nachher = app.font().pointSize()
pruef("Schrift laesst sich vergroessern", g_nachher == g_vorher + 4, f"{g_vorher} -> {g_nachher}")
theme.setze_schriftgroesse(app, g_vorher)

# 4 Suche mit Zeitpuffer
zaehler = {'n': 0}
echt = fenster._update_channels
def gezaehlt(*a, **k):
    zaehler['n'] += 1
    return echt(*a, **k)
fenster._update_channels = gezaehlt
for zeichen in "sport":
    fenster.search_bar.setText(fenster.search_bar.text() + zeichen)
    warte(app, 0.05)
warte(app, 1.2)
pruef("Suche laeuft nur einmal statt fuenfmal", zaehler['n'] <= 1, f"{zaehler['n']} Suchlaeufe bei 5 Tastendruecken")
fenster.search_bar.setText("")
warte(app, 1.0)
fenster._update_channels = echt

# 5 Liste gedeckelt und schnell
warte(app, 1.0)
anzahl = fenster.channel_list.count()
pruef("Liste ist gedeckelt", 0 < anzahl <= 2001, f"{anzahl} Zeilen in der Liste")

# 6 Echte Wiedergabe eines echten Kanals
con = sqlite3.connect(os.path.join(os.path.expanduser('~'), 'SMarTrPlay', 'smartrplay.db'))
zeile = con.execute("SELECT id, name, url FROM channels WHERE type='live' AND url LIKE 'http%' LIMIT 1").fetchone()
con.close()
if zeile:
    kid, name, url = zeile
    wid = int(fenster.video_container.winId())
    gestartet = fenster.player.play(url, window_id=wid)
    warte(app, 6)
    zustand = fenster.player.get_state()
    pos1, dauer = fenster.player.get_position()
    pruef("Kanal spielt", gestartet and zustand in ("playing", "buffering"), f"Zustand {zustand}, Fehler '{fenster.player.get_error()}'")
    warte(app, 3)
    pos2, _ = fenster.player.get_position()
    pruef("Position laeuft mit", pos2 >= pos1, f"{pos1} s -> {pos2} s")
    # Pause
    fenster.player.set_paused(True); warte(app, 2)
    p1, _ = fenster.player.get_position(); warte(app, 2); p2, _ = fenster.player.get_position()
    pruef("Pause haelt das Bild an", fenster.player.is_paused() and abs(p2-p1) <= 1, f"{p1} s -> {p2} s, pausiert={fenster.player.is_paused()}")
    fenster.player.set_paused(False); warte(app, 2)
    pruef("Weiter laeuft ohne Neustart", not fenster.player.is_paused(), f"Position {fenster.player.get_position()[0]} s")
    # Lautstaerke und stumm
    fenster.player.set_volume(35); warte(app, 0.5)
    pruef("Lautstaerke wirkt", fenster.player.get_volume() == 35, f"{fenster.player.get_volume()}")
    fenster.player.set_muted(True); warte(app, 0.5)
    pruef("Stumm wirkt", fenster.player.is_muted(), f"stumm={fenster.player.is_muted()}")
    fenster.player.set_muted(False)
    # Tonspuren
    spuren = fenster.player.get_audio_tracks()
    pruef("Tonspuren werden gemeldet", isinstance(spuren, list), f"{len(spuren)} Spuren: {[s[1] for s in spuren][:3]}")
    fenster.player.stop()
    pruef("Stopp beendet die Wiedergabe", not fenster.player.is_running())
else:
    print("WARNUNG: kein Live-Kanal in der Datenbank, Wiedergabeproben uebersprungen")

# 7 Providerwechsel: nur wenn nicht abgeschaltet (sonst eigener Lauf mit absturztest.py)
import os as _os
if _os.environ.get('OHNE_PROVIDERWECHSEL'):
    print("HINWEIS Providerwechsel wird separat geprueft (absturztest.py)")
else:
    try:
        if fenster.provider_combo.count() > 0:
            for i in range(min(2, fenster.provider_combo.count())):
                fenster.provider_combo.setCurrentIndex(i)
                warte(app, 1.5)
            for reiter in range(fenster.content_tabs.count()):
                fenster.content_tabs.setCurrentIndex(reiter)
                warte(app, 1.0)
            fenster.provider_combo.setCurrentIndex(0)
            warte(app, 2)
        pruef("Providerwechsel und Reiterwechsel ohne Absturz", True, "durchlaufen")
    except Exception as e:
        pruef("Providerwechsel und Reiterwechsel ohne Absturz", False, f"{type(e).__name__}: {e}")

# 8 Sauberes Beenden
try:
    fenster.close()
    warte(app, 3)
    pruef("Fenster schliesst sauber", True)
except Exception as e:
    pruef("Fenster schliesst sauber", False, f"{type(e).__name__}: {e}")

print(f"\nERGEBNIS: {ok} bestanden, {fail} gescheitert")
sys.exit(0 if fail == 0 else 1)
