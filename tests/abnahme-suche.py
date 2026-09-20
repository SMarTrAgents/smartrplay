#!/usr/bin/env python3
"""Abnahme: Serienladen und Mastersuche ueber alle Kategorien.
Aufruf: DISPLAY=:0 .venv/bin/python abnahme-suche.py
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
from PyQt5.QtWidgets import QApplication
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

from config import Config
from xtream_api import XtreamAPI, API_TIMEOUT, INHALT_TIMEOUT
import vod_browser, series_browser

app = QApplication(sys.argv)
c = Config(); p = c.get_provider(c.get_providers()[0][0])
api = XtreamAPI(p[3], p[4], p[5])

pruef("Kurze Frist fuer Listen, lange fuer Inhalte",
      API_TIMEOUT <= 10 < INHALT_TIMEOUT, f"{API_TIMEOUT}s / {INHALT_TIMEOUT}s")

# --- Serien laden ---
t0 = time.time()
serien = api.get_series_channels_lazy()
dauer = time.time() - t0
pruef("Serien laden ueberhaupt", len(serien) > 30000, f"{len(serien)} Eintraege in {dauer:.1f}s")
pruef("Serien laden schneller als eine Minute", dauer < 60, f"{dauer:.1f}s")
ohne = sum(1 for x in serien if not x.get("category"))
pruef("Jede Serie hat eine Kategorie", ohne == 0, f"{ohne} ohne Kategorie")
kats = {x["category"] for x in serien}
sammel = {k for k in kats if k.startswith("Weitere")}
pruef("Sammelkategorien fuer unbenannte Kennungen", len(sammel) > 0,
      f"{len(kats)} Kategorien, davon {len(sammel)} Sammlungen")

# --- Mastersuche Filme ---
vb = vod_browser.VodBrowser(api, None)
vb.show(); warte(app, 2)
pruef("Filmsuche kennt den Gesamtbestand noch nicht", vb._gesamtbestand is None)
vb.search_field.setText("breaking")
warte(app, 1)
pruef("Filmsuche wartet auf das Ende der Eingabe", vb._gesamtbestand is None,
      "Entprellung greift")
t0 = time.time()
while vb._gesamtbestand is None and time.time() - t0 < 90:
    warte(app, 0.5)
warte(app, 2)
pruef("Filmsuche holt den Gesamtbestand", vb._gesamtbestand is not None,
      f"{len(vb._gesamtbestand or [])} Filme in {time.time()-t0:.1f}s")
treffer_film = vb.movie_list.count()
pruef("Filmsuche findet ueber alle Kategorien", treffer_film > 0,
      f"{treffer_film} Treffer, Meldung: {vb.status_label.text()[:46]}")
pruef("Filmtreffer sind gedeckelt", treffer_film <= vod_browser.MAX_TREFFER_SUCHE,
      f"{treffer_film} <= {vod_browser.MAX_TREFFER_SUCHE}")
vb.search_field.setText("")
warte(app, 2)
pruef("Leeres Suchfeld kehrt zur Kategorie zurueck",
      "Treffer" not in vb.status_label.text(), vb.status_label.text()[:46])
vb.close(); warte(app, 1)

# --- Mastersuche Serien ---
sb = series_browser.SeriesBrowser(api, None)
sb.show(); warte(app, 3)
sb.search_field.setText("breaking")
t0 = time.time()
while sb._gesamtbestand is None and time.time() - t0 < 120:
    warte(app, 0.5)
warte(app, 2)
pruef("Seriensuche holt den Gesamtbestand", sb._gesamtbestand is not None,
      f"{len(sb._gesamtbestand or [])} Serien in {time.time()-t0:.1f}s")
treffer_serie = sb.series_list.count()
pruef("Seriensuche findet ueber alle Kategorien", treffer_serie > 0,
      f"{treffer_serie} Treffer, Meldung: {sb.status_label.text()[:46]}")
# Gegenprobe: ein Titel aus einer Kategorie, die der Anbieter gar nicht nennt
fremd = next((e["name"] for e in (sb._gesamtbestand or [])
              if e.get("name", "").startswith("|IT|")), None)
if fremd:
    sb.search_field.setText(fremd[5:25].strip())
    warte(app, 2)
    pruef("Seriensuche erreicht unbenannte Kategorien", sb.series_list.count() > 0,
          f"gesucht: {fremd[:34]}")
else:
    pruef("Seriensuche erreicht unbenannte Kategorien", False, "kein Beispiel gefunden")
sb.close(); warte(app, 1)
api.close()
print(f"\nERGEBNIS: {ok} bestanden, {fail} gescheitert")
sys.exit(1 if fail else 0)
