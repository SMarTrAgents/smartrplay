#!/usr/bin/env python3
"""Abnahme: Serienfolgen laufen in der Videoflaeche und sind im Vollbild zappbar.
Aufruf: DISPLAY=:0 .venv/bin/python abnahme-serienzappen.py
"""
import time
import sys, os
# Pfade relativ zum Projekt, damit der Lauf in jedem Klon funktioniert.
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, 'src'))
# Pfade relativ zum Projekt, damit der Lauf in jedem Klon funktioniert.
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
from PyQt5.QtWidgets import QApplication, QListWidgetItem
from PyQt5.QtCore import Qt

ok = fail = 0
def pruef(name, bed, mess=""):
    global ok, fail
    print(f"{'OK    ' if bed else 'FEHLER'} {name:54s} {mess}", flush=True)
    if bed: ok += 1
    else: fail += 1

def warte(app, s):
    e = time.time() + s
    while time.time() < e:
        app.processEvents(); time.sleep(0.02)

from theme import apply_theme
from xtream_api import XtreamAPI
import main_window as mw
import series_browser

app = QApplication(sys.argv)
apply_theme(app)
fenster = mw.MainWindow()
fenster.show()
warte(app, 3)

p = fenster.config.get_provider(fenster.config.get_providers()[0][0])
api = XtreamAPI(p[3], p[4], p[5])
info = api.get_series_info(72)              # |EN| Stan Lee, Staffel 1 mit 10 Folgen
staffel = sorted((info.get("episodes") or {}).keys())[0]
folgen_roh = info["episodes"][staffel]
pruef("Testserie hat mehrere Folgen", len(folgen_roh) >= 3, f"{len(folgen_roh)} Folgen")

def url_fuer(f):
    return f"{api.server_url}/series/{api.username}/{api.password}/{f['id']}.{f.get('container_extension','mp4')}"

reihe = [{"titel": f"F{f.get('episode_num')} {f.get('title','')}"[:40], "url": url_fuer(f)}
         for f in folgen_roh]

# --- Folge in der Videoflaeche starten ---
erfolg = fenster.spiele_in_videoflaeche(reihe[0]["url"], reihe[0]["titel"], reihe, 0)
warte(app, 8)
pruef("Folge startet in der Videoflaeche", erfolg and fenster.player.is_running(),
      f"Zustand {fenster.player.get_state()}")
pos1 = fenster.player.get_position()[0]
pruef("Folge laeuft wirklich", pos1 > 0, f"Position {pos1} s")
pruef("Staffel ist zum Zappen gemerkt", len(fenster._folgenreihe) == len(reihe),
      f"{len(fenster._folgenreihe)} Folgen, Nummer {fenster._folgen_index}")
pruef("Titel steht in der Kopfzeile", reihe[0]["titel"][:12] in fenster.now_playing_label.text(),
      fenster.now_playing_label.text()[:44])

# --- Vollbild ---
fenster._vollbild_an()
warte(app, 3)
pruef("Vollbild mit laufender Folge", fenster.isFullScreen() and fenster.player.is_running())
pruef("Bedienleiste zeigt den Folgentitel",
      fenster._vollbild_leiste is not None and fenster._vollbild_leiste.titel.text() != "",
      fenster._vollbild_leiste.titel.text()[:40] if fenster._vollbild_leiste else "fehlt")

# --- Zappliste zeigt die Folgen, nicht die Kanaele ---
fenster._zappliste_umschalten()
warte(app, 2)
zapp = fenster._zappliste
pruef("Zappliste zeigt die Folgen der Staffel",
      zapp is not None and zapp.liste.count() == len(reihe),
      f"{zapp.liste.count() if zapp else 0} Zeilen, erste: {zapp.liste.item(0).text()[:30] if zapp and zapp.liste.count() else ''}")

# --- eine Folge weiter ---
titel_vor = fenster.now_playing_label.text()
fenster._zappe_um(1)
warte(app, 8)
pruef("Pfeil runter schaltet eine Folge weiter",
      fenster._folgen_index == 1 and fenster.now_playing_label.text() != titel_vor,
      f"Nummer {fenster._folgen_index}: {fenster.now_playing_label.text()[:40]}")
pruef("Die naechste Folge spielt", fenster.player.is_running(),
      f"Zustand {fenster.player.get_state()}, Position {fenster.player.get_position()[0]} s")
pruef("Vollbild bleibt beim Folgenwechsel", fenster.isFullScreen())

# --- eine Folge zurueck ---
fenster._zappe_um(-1)
warte(app, 8)
pruef("Pfeil hoch schaltet eine Folge zurueck", fenster._folgen_index == 0,
      f"Nummer {fenster._folgen_index}")

# --- Grenze der Staffel ---
fenster._zappe_um(-1)
warte(app, 2)
pruef("Vor der ersten Folge ist Schluss", fenster._folgen_index == 0,
      fenster.status_bar.currentMessage()[:44])

# --- direkte Auswahl aus der Zappliste ---
fenster._zappe_zu(2)
warte(app, 8)
pruef("Auswahl aus der Zappliste springt zur Folge", fenster._folgen_index == 2,
      f"Nummer {fenster._folgen_index}: {fenster.now_playing_label.text()[:36]}")

fenster._vollbild_aus()
warte(app, 2)

# --- Ein Kanal beendet die Staffel ---
gefunden = False
warte(app, 2)   # der Liste Zeit lassen, falls ein Ladefaden sie gerade fuellt
for i in range(min(400, fenster.channel_list.count())):
    e = fenster.channel_list.item(i)
    if e is None or e.data(Qt.UserRole) is None:
        continue
    z = fenster.config.get_channel(e.data(Qt.UserRole))
    if not z or (len(z) > 8 and z[8] == "series"):
        continue
    fenster.channel_list.setCurrentRow(i)
    fenster._play_channel(e)
    gefunden = True
    break
warte(app, 6)
pruef("Ein Kanal loest die Staffel ab",
      gefunden and not fenster._folgenreihe,
      f"Kanal gefunden: {gefunden}, Folgenreihe leer: {not fenster._folgenreihe}, "
      f"Zeilen in der Liste: {fenster.channel_list.count()}")

# --- Verdrahtung im Serienbrowser ---
quelle = open(os.path.join(WURZEL, 'src', 'series_browser.py'), encoding='utf-8').read()
pruef("Serienbrowser ruft die Videoflaeche auf",
      "spiele_in_videoflaeche" in quelle and "_staffel_als_reihe" in quelle)
pruef("Hauptfenster bietet die Videoflaeche an",
      hasattr(fenster, "spiele_in_videoflaeche") and hasattr(fenster, "_spiele_folge"))

api.close()
fenster.close()
warte(app, 2)
print(f"\nERGEBNIS: {ok} bestanden, {fail} gescheitert")
sys.exit(1 if fail else 0)
