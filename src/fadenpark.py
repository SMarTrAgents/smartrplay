#!/usr/bin/env python3
"""SMarTrPlay - Fadenpark: sichere Entsorgung laufender Hintergrundfaeden.

Warum es diese Datei gibt
-------------------------
Die Ladefaeden dieser Anwendung ueberschreiben run() ohne exec_(). Damit ist
quit() bei ihnen wirkungslos, nur ein Abbruchflag wirkt. Wer einen solchen
Faden mit deleteLater() entfernt, waehrend er noch laeuft, bekommt den harten
Abbruch "QThread: Destroyed while thread is still running".

Es reicht aber NICHT, den Faden nur in einer Liste des eigenen Fensters zu
halten. Die Faeden werden mit dem Fenster als Qt-Elternobjekt erzeugt
(zum Beispiel SeriesLoaderThread(api, category_id, self)). Wird das Fenster
danach geloescht, reisst Qt jedes laufende Kind mit in den Tod, ganz gleich
welche Liste die Referenz noch haelt. Gemessen am 19.09.2026: der
SeriesLoaderThread lief nach einem Providerwechsel weiter, waehrend sein
Serienfenster entfernt wurde, und genau dort brach die Anwendung ab.

Deshalb wird ein Faden, der sich nicht rechtzeitig beenden laesst, hier
abgenabelt (setParent(None)) und in einer modulweiten Liste geparkt, die
jedes einzelne Fenster ueberlebt. Erst wenn er von sich aus fertig ist,
wird er geloescht und aus der Liste genommen.
"""

import logging

logger = logging.getLogger('SMarTrPlay')

# Modulweite Ablage. Sie ueberlebt jedes Fenster und jeden Reiter.
_GEPARKTE_FAEDEN = []


def parke_faden(thread, name=""):
    """Einen noch laufenden Faden abnabeln und bis zu seinem Ende aufheben."""
    try:
        # Vom sterbenden Elternfenster loesen, sonst nimmt Qt ihn mit.
        if thread.parent() is not None:
            thread.setParent(None)
    except Exception as e:
        logger.warning(f"Faden '{name}' liess sich nicht abnabeln: {e}")

    if thread not in _GEPARKTE_FAEDEN:
        _GEPARKTE_FAEDEN.append(thread)

    def _aufraeumen():
        try:
            if thread in _GEPARKTE_FAEDEN:
                _GEPARKTE_FAEDEN.remove(thread)
            thread.deleteLater()
            logger.info(f"Geparkter Faden '{name}' ist fertig und wurde entfernt")
        except Exception as e:
            logger.warning(f"Geparkter Faden '{name}' liess sich nicht entfernen: {e}")

    try:
        thread.finished.connect(_aufraeumen)
    except Exception as e:
        logger.warning(f"Faden '{name}': finished nicht verbindbar: {e}")

    logger.warning(
        f"Faden '{name}' endete nicht rechtzeitig, wurde abgenabelt und geparkt "
        f"({len(_GEPARKTE_FAEDEN)} geparkt)"
    )


def entsorge_faden(thread, wartezeit_ms=3000, name=""):
    """Einen QThread sicher entsorgen.

    Reihenfolge: Abbruchflag setzen, begrenzt warten, dann entweder loeschen
    oder abnabeln und parken. Wirft nie eine Ausnahme nach aussen.
    """
    if thread is None:
        return

    try:
        if hasattr(thread, "cancel"):
            try:
                thread.cancel()
            except Exception:
                pass

        if thread.isRunning():
            if thread.wait(wartezeit_ms):
                thread.deleteLater()
            else:
                parke_faden(thread, name)
        else:
            thread.deleteLater()
    except RuntimeError:
        # Das zugrunde liegende Qt-Objekt ist bereits weg. Nichts zu tun.
        pass
    except Exception as e:
        logger.warning(f"Faden '{name}' liess sich nicht entsorgen: {e}")


def anzahl_geparkt():
    """Wie viele Faeden gerade geparkt sind. Fuer Pruefungen und Diagnose."""
    return len(_GEPARKTE_FAEDEN)


def warte_auf_geparkte(gesamt_ms=3000):
    """Beim Beenden der Anwendung begrenzt auf die geparkten Faeden warten.

    Gibt die Anzahl der Faeden zurueck, die danach noch laufen. Auf sie wird
    nicht laenger gewartet, sie sind abgenabelt und koennen niemanden mehr
    mit in den Tod reissen.
    """
    if not _GEPARKTE_FAEDEN:
        return 0

    rest_ms = max(0, int(gesamt_ms))
    for thread in list(_GEPARKTE_FAEDEN):
        if rest_ms <= 0:
            break
        try:
            if thread.isRunning():
                anteil = rest_ms
                if thread.wait(anteil):
                    rest_ms = max(0, rest_ms - 50)
                else:
                    rest_ms = 0
        except RuntimeError:
            pass
        except Exception:
            pass

    laufen_noch = 0
    for thread in list(_GEPARKTE_FAEDEN):
        try:
            if thread.isRunning():
                laufen_noch += 1
        except Exception:
            pass
    if laufen_noch:
        logger.info(f"{laufen_noch} geparkte Faeden laufen beim Beenden noch, sie sind abgenabelt")
    return laufen_noch
