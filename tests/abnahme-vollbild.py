#!/usr/bin/env python3
"""Abnahme der Vollbildbedienung: bedient das echte Fenster und misst.
Aufruf: DISPLAY=:0 .venv/bin/python abnahme-vollbild.py
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
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest

ok = fail = 0
def pruef(name, bedingung, mess=""):
    global ok, fail
    print(f"{'OK    ' if bedingung else 'FEHLER'} {name:52s} {mess}", flush=True)
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
fenster = mw.MainWindow()
fenster.show()
warte(app, 3)

pruef("Vollbildknopf in der festen Leiste", hasattr(fenster.video_controls, "btn_vollbild"),
      fenster.video_controls.btn_vollbild.toolTip()[:40] if hasattr(fenster.video_controls, "btn_vollbild") else "fehlt")

# Kanal starten, damit ein echtes Bild laeuft
gestartet = False
for i in range(min(120, fenster.channel_list.count())):
    eintrag = fenster.channel_list.item(i)
    if eintrag is None:
        continue
    kennung = eintrag.data(Qt.UserRole)
    if kennung is None:
        continue
    # Serien lassen sich nicht direkt abspielen, sie oeffnen den Serienbrowser.
    zeile = fenster.config.get_channel(kennung)
    if not zeile or (len(zeile) > 8 and zeile[8] == "series"):
        continue
    fenster.channel_list.setCurrentRow(i)
    fenster._play_channel(eintrag)
    gestartet = True
    break
warte(app, 6)
laeuft = fenster.player.is_running() if gestartet else False
pos_vor = fenster.player.get_position()[0] if laeuft else 0
pruef("Ein Kanal laeuft vor dem Wechsel", laeuft, f"Position {pos_vor} s")

# --- Doppelklick auf das Videobild schaltet ins Vollbild ---
mitte = QPoint(fenster.video_container.width() // 2, fenster.video_container.height() // 2)
QTest.mouseDClick(fenster.video_container, Qt.LeftButton, Qt.NoModifier, mitte)
warte(app, 2)
pruef("Doppelklick schaltet ins Vollbild", fenster.isFullScreen() and fenster._vollbild_aktiv,
      f"Vollbild={fenster.isFullScreen()}")
pruef("Kanalreiter im Vollbild verborgen", not fenster.content_tabs.isVisible())
pruef("Videobild im Vollbild sichtbar", fenster.video_container.isVisible(),
      f"{fenster.video_container.width()}x{fenster.video_container.height()}")

leiste = fenster._vollbild_leiste
pruef("Schwebende Bedienleiste sichtbar", leiste is not None and leiste.isVisible(),
      f"{leiste.width()}x{leiste.height()}" if leiste else "fehlt")
if leiste is not None:
    knoepfe = ["b_pause", "b_zurueck", "b_vor", "b_stopp", "b_stumm", "b_liste",
               "b_kanal_auf", "b_kanal_ab", "b_beenden"]
    fehlend = [k for k in knoepfe if not hasattr(leiste, k)]
    pruef("Alle neun Bedienknoepfe vorhanden", not fehlend, f"fehlen: {fehlend or 'keine'}")
    gross = leiste.b_pause.height() >= 48
    pruef("Knoepfe gross genug (Sehschwaeche)", gross, f"{leiste.b_pause.width()}x{leiste.b_pause.height()} px")

# --- Bild laeuft im Vollbild weiter ---
warte(app, 4)
pos_voll = fenster.player.get_position()[0] if fenster.player.is_running() else -1
pruef("Bild laeuft im Vollbild weiter", pos_voll > pos_vor, f"{pos_vor} s -> {pos_voll} s")

# --- Zappliste oeffnen und umschalten ---
fenster._zappliste_umschalten()
warte(app, 2)
zapp = fenster._zappliste
pruef("Zappliste ueber dem Bild offen", zapp is not None and zapp.isVisible(),
      f"{zapp.liste.count()} Kanaele" if zapp else "fehlt")

kanal_vor = fenster.channel_list.currentRow()
fenster._zappe_um(1)
warte(app, 6)
kanal_nach = fenster.channel_list.currentRow()
pruef("Zappen wechselt den Kanal", kanal_nach != kanal_vor, f"Zeile {kanal_vor} -> {kanal_nach}")
pruef("Vollbild bleibt beim Zappen bestehen", fenster.isFullScreen() and fenster._vollbild_aktiv)
pruef("Bild spielt nach dem Zappen", fenster.player.is_running(),
      f"Zustand {fenster.player.get_state()}")

# --- Tastatur ---
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtCore import QEvent as QEv
vor_stumm = fenster.player.is_muted()
fenster.keyPressEvent(QKeyEvent(QEv.KeyPress, Qt.Key_M, Qt.NoModifier))
warte(app, 1)
pruef("Taste M schaltet stumm", fenster.player.is_muted() != vor_stumm,
      f"{vor_stumm} -> {fenster.player.is_muted()}")
fenster.keyPressEvent(QKeyEvent(QEv.KeyPress, Qt.Key_M, Qt.NoModifier))
warte(app, 1)

# --- Doppelklick fuehrt zurueck in die kleine Wiedergabe ---
pos_vor_rueck = fenster.player.get_position()[0]
QTest.mouseDClick(fenster.video_container, Qt.LeftButton, Qt.NoModifier, mitte)
warte(app, 3)
pruef("Doppelklick fuehrt zurueck zur kleinen Wiedergabe",
      (not fenster.isFullScreen()) and (not fenster._vollbild_aktiv))
pruef("Kanalreiter wieder sichtbar", fenster.content_tabs.isVisible())
pruef("Schwebende Leiste wieder verborgen",
      fenster._vollbild_leiste is None or not fenster._vollbild_leiste.isVisible())
warte(app, 3)
pos_nach_rueck = fenster.player.get_position()[0] if fenster.player.is_running() else -1
pruef("Bild laeuft nach der Rueckkehr weiter", pos_nach_rueck > pos_vor_rueck,
      f"{pos_vor_rueck} s -> {pos_nach_rueck} s")

# --- Escape und F11 ---
fenster.keyPressEvent(QKeyEvent(QEv.KeyPress, Qt.Key_F11, Qt.NoModifier))
warte(app, 2)
im_voll = fenster.isFullScreen()
fenster.keyPressEvent(QKeyEvent(QEv.KeyPress, Qt.Key_Escape, Qt.NoModifier))
warte(app, 2)
pruef("F11 hinein, Escape hinaus", im_voll and not fenster.isFullScreen(),
      f"F11={im_voll}, danach={fenster.isFullScreen()}")

fenster.close()
warte(app, 2)
print(f"\nERGEBNIS: {ok} bestanden, {fail} gescheitert")
sys.exit(1 if fail else 0)
