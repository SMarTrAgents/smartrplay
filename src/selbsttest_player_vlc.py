#!/usr/bin/env python3
"""Selbsttest für das VLC-Backend von SMarTrPlay.

Der Test läuft ohne grafische Oberfläche: das Backend wird mit den
VLC-Ausgaben "--vout=dummy" und "--aout=dummy" erzeugt. Geprüft werden
die neun Pflichtpunkte aus dem Bauauftrag, jeder Punkt meldet OK oder
FEHLER mit seinem Messwert. Am Ende steht die Zeile
"ERGEBNIS: n/9 bestanden".
"""

import logging
import os
import subprocess
import sys
import time

# Backend aus dem gleichen Ordner importierbar machen, egal woher gestartet
HIER = os.path.dirname(os.path.abspath(__file__))
if HIER not in sys.path:
    sys.path.insert(0, HIER)

from player_vlc import VlcPlayerBackend

TESTMEDIUM = "/tmp/smartrplay_test.mp4"


class Selbsttest:
    """Hält das Backend und führt die neun Prüfungen der Reihe nach aus."""

    def __init__(self):
        self.backend = None
        self.spielbeginn = 0.0

    def pruefung1(self):
        """Testmedium erzeugen und für saubere Verhältnisse sorgen."""
        # VLC lädt Untertiteldateien mit gleichem Grundnamen automatisch.
        # Solche Reste früherer Läufe stören die Prüfung und werden entfernt.
        for restpfad in (
            TESTMEDIUM[: -len(".mp4")] + ".srt",
            TESTMEDIUM[: -len(".mp4")] + ".ass",
            TESTMEDIUM[: -len(".mp4")] + ".sub",
        ):
            if os.path.exists(restpfad):
                try:
                    os.remove(restpfad)
                except OSError:
                    pass
        befehl = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "testsrc=size=320x240:rate=10",
            "-t", "8",
            "-pix_fmt", "yuv420p",
            TESTMEDIUM,
            "-y",
        ]
        lauf = subprocess.run(befehl, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        groesse = os.path.getsize(TESTMEDIUM) if os.path.isfile(TESTMEDIUM) else 0
        ok = lauf.returncode == 0 and groesse > 0
        messwert = "Rückgabe %d, Dateigröße %d Bytes" % (lauf.returncode, groesse)
        return ok, messwert

    def pruefung2(self):
        """play() liefert True, get_state() meldet innerhalb von 5 s playing."""
        self.backend = VlcPlayerBackend(
            extra_args=["--vout=dummy", "--aout=dummy", "--avcodec-hw=none"]
        )
        gestartet = self.backend.play(TESTMEDIUM)
        beginn = time.time()
        zustand = self.backend.get_state()
        while time.time() - beginn < 5.0 and zustand != "playing":
            time.sleep(0.1)
            zustand = self.backend.get_state()
        vergangene = time.time() - beginn
        if zustand == "playing":
            self.spielbeginn = time.time()
        ok = gestartet and zustand == "playing"
        messwert = "play()=%s, Zustand '%s' nach %.1f s, Fehler: '%s'" % (
            gestartet, zustand, vergangene, self.backend.get_error()
        )
        return ok, messwert

    def pruefung3(self):
        """Nach 2 s ist die Position größer 0, die Dauer liegt zwischen 7 und 9."""
        gewartet = time.time() - self.spielbeginn
        if gewartet < 2.0:
            time.sleep(2.0 - gewartet)
        position, dauer = self.backend.get_position()
        ok = position > 0 and 7 <= dauer <= 9
        messwert = "Position %d s, Dauer %d s" % (position, dauer)
        return ok, messwert

    def pruefung4(self):
        """pause() pausiert, die Position steht über 1,5 s still."""
        position_vorher = self.backend.get_position()[0]
        self.backend.pause()
        pausiert = self.backend.is_paused()
        time.sleep(1.5)
        position_nachher = self.backend.get_position()[0]
        abweichung = abs(position_nachher - position_vorher)
        ok = pausiert and abweichung <= 1
        messwert = "is_paused()=%s, Position %d s -> %d s (Abweichung %d s)" % (
            pausiert, position_vorher, position_nachher, abweichung
        )
        return ok, messwert

    def pruefung5(self):
        """pause() erneut: is_paused() ist False, die Position läuft weiter."""
        self.backend.pause()
        # libvlc übernimmt das Weiterlaufen asynchron, kurz warten, dann messen
        time.sleep(0.2)
        laeuft_wieder = not self.backend.is_paused()
        position_vorher = self.backend.get_position()[0]
        time.sleep(1.3)
        position_nachher = self.backend.get_position()[0]
        ok = laeuft_wieder and position_nachher > position_vorher
        messwert = "is_paused()=%s, Position %d s -> %d s" % (
            self.backend.is_paused(), position_vorher, position_nachher
        )
        return ok, messwert

    def pruefung6(self):
        """seek_to(5) setzt die Position auf 4 bis 6 Sekunden."""
        self.backend.seek_to(5)
        beginn = time.time()
        position = self.backend.get_position()[0]
        while time.time() - beginn < 2.5 and not 4 <= position <= 6:
            time.sleep(0.1)
            position = self.backend.get_position()[0]
        vergangen = time.time() - beginn
        ok = 4 <= position <= 6
        messwert = "Position %d s nach %.1f s, spulbar=%s" % (
            position, vergangen, self.backend.is_seekable()
        )
        return ok, messwert

    def pruefung7(self):
        """set_volume(30), get_volume() liefert 30."""
        self.backend.set_volume(30)
        volumen = self.backend.get_volume()
        ok = volumen == 30
        messwert = "get_volume()=%d" % volumen
        return ok, messwert

    def pruefung8(self):
        """set_muted(True), is_muted() ist True."""
        self.backend.set_muted(True)
        stumm = self.backend.is_muted()
        ok = stumm is True
        messwert = "is_muted()=%s" % stumm
        return ok, messwert

    def pruefung9(self):
        """stop() beendet, release() läuft fehlerfrei durch."""
        self.backend.stop()
        laeuft = self.backend.is_running()
        freigabefehler = None
        try:
            self.backend.release()
        except Exception as fehler:
            freigabefehler = fehler
        fehlerfrei = freigabefehler is None
        ok = (not laeuft) and fehlerfrei
        if fehlerfrei:
            messwert = "is_running()=%s nach stop(), release() fehlerfrei" % laeuft
        else:
            messwert = "is_running()=%s nach stop(), release() Fehler: %s" % (
                laeuft, freigabefehler
            )
        return ok, messwert


def hauptprogramm():
    # Ausgabe auch in Umgebungen ohne UTF-8-Standardeinstellung sicherstellen
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    test = Selbsttest()
    pruefungen = [
        (1, "Testmedium erzeugt", test.pruefung1),
        (2, "play() True, Zustand playing innerhalb 5 s", test.pruefung2),
        (3, "Position > 0, Dauer 7 bis 9 s", test.pruefung3),
        (4, "pause() pausiert, Position steht still", test.pruefung4),
        (5, "pause() erneut: Wiedergabe läuft weiter", test.pruefung5),
        (6, "seek_to(5) landet bei 4 bis 6 s", test.pruefung6),
        (7, "set_volume(30), get_volume() = 30", test.pruefung7),
        (8, "set_muted(True), is_muted() = True", test.pruefung8),
        (9, "stop() beendet, release() fehlerfrei", test.pruefung9),
    ]

    print("SMarTrPlay Selbsttest für VlcPlayerBackend (kopflos, Dummy-Ausgaben)")
    print()
    bestanden = 0
    try:
        for nummer, beschreibung, funktion in pruefungen:
            try:
                ok, messwert = funktion()
            except Exception as fehler:
                ok, messwert = False, "Ausnahme: %s" % fehler
            if ok:
                bestanden += 1
            print("%-11s %-42s %-7s %s" % (
                "Prüfung %d" % nummer,
                beschreibung,
                "OK" if ok else "FEHLER",
                messwert,
            ))
    finally:
        # Auch bei einem Abbruch darf kein MediaPlayer übrig bleiben
        if test.backend is not None:
            try:
                test.backend.release()
            except Exception:
                pass

    print()
    print("ERGEBNIS: %d/9 bestanden" % bestanden)
    return 0 if bestanden == 9 else 1


if __name__ == "__main__":
    sys.exit(hauptprogramm())