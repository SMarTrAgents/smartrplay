#!/usr/bin/env python3
"""SMarTrPlay - Xtream Codes API Client (Optimized v3)

Optimierungen gegenueber v2:
- Eine Sitzung (requests.Session) mit Verbindungswiederverwendung fuer alle Abrufe
- 8s Timeout pro Abruf mit genau einer Wiederholung bei Zeitueberschreitung oder Verbindungsfehler
- Parallele Kategorienabrufe (hoechstens 8 gleichzeitig) in allen lazy-Methoden
- Abbruchpruefung von aussen ueber setze_abbruchpruefung(funktion)
- Sperrliste fuer Kategorien mit wiederholten Zeitueberschreitungen
- Lazy Loading: Kategorien zuerst, Streams bei Auswahl
- Progress Callbacks fuer UI-Feedback
- Pagination Support (max 500 pro Call)
- get_all_channels() bleibt fuer Backward-Kompatibilitaet
"""

import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

import requests

logger = logging.getLogger('SMarTrPlay.XtreamAPI')

API_TIMEOUT = 8
# Inhaltsabrufe brauchen deutlich mehr Geduld als Kategorienlisten. Gemessen am
# 19.09.2026 an einem echten Xtream-Anschluss mit eigener Kennung:
# get_series_categories 0,3 s, get_vod_streams gesamt 2,5 s, get_series gesamt
# 16,8 s (37623 Eintraege, 25 MB), eine einzelne Serienkategorie 12,6 bis 13,8 s.
# Mit der kurzen Frist von 8 s lief JEDE Serienkategorie in die
# Zeitueberschreitung, landete nach zwei Versuchen in der Sperrliste, und der
# Serienreiter blieb leer. Deshalb eine eigene, lange Frist fuer Inhalte.
INHALT_TIMEOUT = 45
# Diese Abrufe liefern Inhalte und bekommen die lange Frist.
INHALTS_ACTIONS = {"get_series", "get_vod_streams", "get_live_streams",
                   "get_series_info", "get_vod_info"}
MAX_CHANNELS_PER_CALL = 500
MAX_PARALLEL_ABRUFE = 4   # Gemessen: bei 8 drosselt der Anbieter und antwortet mit 404
WIEDERHOLUNG_WARTEZEIT = 0.5


class XtreamTimeoutException(Exception):
    """Zeitueberschreitung eines Abrufs; nur intern benutzt, damit die Sperrliste tote Kategorien erkennen kann."""


class XtreamAPI:
    """Client fuer Xtream Codes API (Optimized v3)."""

    def __init__(self, server_url, username, password):
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.base_url = f"{self.server_url}/player_api.php"
        self.params = {
            "username": username,
            "password": password,
        }
        # Eine Sitzung fuer alle Abrufe, damit bestehende Verbindungen wiederverwendet werden.
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SMarTrPlay/2.0"})
        # Sperre dafuer, dass der Fortschrittsrueckruf nur aus einem Faden gerufen wird.
        self._fortschritt_schloss = threading.Lock()
        # Abbruchpruefung von aussen; None bedeutet, es wird nie abgebrochen.
        self._abbruch_pruefung = None
        # Kategorien, die zweimal hintereinander eine Zeitueberschreitung hatten.
        self._tote_kategorien = set()
        self._timeout_zaehler = {}

    def close(self):
        """Schliesst die Sitzung und gibt die gehaltenen Verbindungen frei."""
        try:
            self._session.close()
        except Exception:
            logger.exception("Sitzung lies sich nicht schliessen")

    def setze_abbruchpruefung(self, funktion):
        """Setzt eine Funktion ohne Argumente, die True liefert, wenn abgebrochen werden soll."""
        self._abbruch_pruefung = funktion

    def _soll_abbrechen(self):
        """Liefert True, wenn eine gesetzte Abbruchpruefung Abbruch verlangt."""
        pruefung = self._abbruch_pruefung
        if pruefung is None:
            return False
        try:
            return bool(pruefung())
        except Exception:
            logger.exception("Abbruchpruefung hat einen Fehler geliefert")
            return False

    def _zeitueberschreitung_vermerken(self, schluessel):
        """Zaehlt Zeitueberschreitungen je Kategorie; zwei in Folge sperren die Kategorie fuer die Sitzung."""
        zaehler = self._timeout_zaehler.get(schluessel, 0) + 1
        self._timeout_zaehler[schluessel] = zaehler
        if zaehler >= 2 and schluessel not in self._tote_kategorien:
            self._tote_kategorien.add(schluessel)
            logger.warning(f"Kategorie {schluessel} wegen zwei Zeitueberschreitungen hintereinander fuer diese Sitzung gesperrt")

    def _request(self, action, extra_params=None, sperrschluessel=None, zeitlimit=None):
        """Fuehrt einen Abruf ueber die Sitzung aus, mit einer Wiederholung.

        Die Frist richtet sich nach der Art des Abrufs: Kategorienlisten und
        Anmeldung sollen schnell scheitern (API_TIMEOUT), Inhaltsabrufe duerfen
        dauern (INHALT_TIMEOUT). Mit zeitlimit laesst sich das ueberschreiben.
        """
        params = dict(self.params)
        if action:
            params["action"] = action
        if extra_params:
            params.update(extra_params)
        frist = zeitlimit if zeitlimit is not None else (
            INHALT_TIMEOUT if action in INHALTS_ACTIONS else API_TIMEOUT)
        versuch = 0
        while True:
            resp = None
            try:
                resp = self._session.get(self.base_url, params=params, timeout=frist)
                resp.raise_for_status()
                daten = resp.json()
                if sperrschluessel is not None:
                    # Nach einem erfolgreichen Abruf gilt eine vorherige Zeitueberschreitung nicht mehr als Folgefehler.
                    self._timeout_zaehler.pop(sperrschluessel, None)
                return daten
            except requests.exceptions.Timeout:
                if sperrschluessel is not None:
                    self._zeitueberschreitung_vermerken(sperrschluessel)
                versuch += 1
                if versuch > 1:
                    raise XtreamTimeoutException(f"Xtream API Timeout ({action}): Server antwortet nicht innerhalb {frist}s")
                time.sleep(WIEDERHOLUNG_WARTEZEIT)
            except requests.exceptions.ConnectionError as e:
                versuch += 1
                if versuch > 1:
                    raise Exception(f"Xtream API Verbindungsfehler ({action}): {e}")
                time.sleep(WIEDERHOLUNG_WARTEZEIT)
            except requests.exceptions.HTTPError as e:
                # Gemessen am 19.09.2026: Der Anbieter antwortet bei zu vielen
                # gleichzeitigen Abrufen mit 404 oder 429, obwohl die Kategorie
                # existiert. Einzeln abgerufen liefert dieselbe Kategorie Daten.
                # Solche Drosselungsantworten werden deshalb wiederholt, mit
                # wachsender Wartezeit. Ein echter, dauerhafter Fehler faellt
                # nach dem zweiten Versuch durch.
                code = getattr(getattr(e, 'response', None), 'status_code', 0)
                versuch += 1
                if code in (404, 429, 500, 502, 503, 504) and versuch <= 2:
                    time.sleep(WIEDERHOLUNG_WARTEZEIT * versuch * 2)
                    continue
                raise Exception(f"Xtream API Error ({action}): {e}")
            except Exception as e:
                # Alle uebrigen Fehler werden nicht wiederholt.
                raise Exception(f"Xtream API Error ({action}): {e}")
            finally:
                if resp is not None:
                    resp.close()

    def authenticate(self):
        """Server-Authentifizierung pruefen."""
        try:
            data = self._request("")
            if data and "user_info" in data:
                return data
            return None
        except Exception:
            return None

    def get_live_categories(self):
        return self._request("get_live_categories")

    def get_vod_categories(self):
        return self._request("get_vod_categories")

    def get_series_categories(self):
        return self._request("get_series_categories")

    def get_live_streams(self, category_id=None):
        params = {}
        if category_id:
            params["category_id"] = category_id
        return self._request("get_live_streams", params)

    def get_vod_streams(self, category_id=None):
        params = {}
        if category_id:
            params["category_id"] = category_id
        return self._request("get_vod_streams", params)

    def get_series(self, category_id=None):
        params = {}
        if category_id:
            params["category_id"] = category_id
        return self._request("get_series", params)

    def get_vod_info(self, vod_id):
        return self._request("get_vod_info", {"vod_id": vod_id})

    def get_series_info(self, series_id):
        return self._request("get_series_info", {"series_id": series_id})

    def get_epg(self, stream_id):
        return self._request("get_live_stream_epg", {"stream_id": stream_id})

    def get_short_epg(self, stream_id):
        return self._request("get_short_epg", {"stream_id": stream_id})

    def get_stream_url(self, stream_id, stream_type="live", container_ext=None):
        path_map = {"live": "live", "vod": "movie", "series": "series"}
        path = path_map.get(stream_type, stream_type)
        if stream_type == "live":
            ext = container_ext or "ts"
        elif stream_type == "vod":
            ext = container_ext or "mp4"
        else:
            ext = container_ext or "mp4"
        return f"{self.server_url}/{path}/{self.username}/{self.password}/{stream_id}.{ext}"

    def _lade_eine_kategorie(self, kategorie, action, baue_kanal):
        """Laedt eine einzelne Kategorie im Arbeitsfaden. Liefert (Name, Kanaele, Fehlertext oder None, wegen Abbruch uebersprungen)."""
        cat_id = kategorie.get("category_id")
        cat_name = kategorie.get("category_name", "Unknown")
        # Abbruchpruefung direkt vor dem Netzabruf.
        if self._soll_abbrechen():
            return (cat_name, [], None, True)
        schluessel = f"{action}:{cat_id}"
        if schluessel in self._tote_kategorien:
            logger.debug(f"Kategorie {cat_name} ist gesperrt und wird uebersprungen")
            return (cat_name, [], None, False)
        try:
            eintraege = self._request(action, {"category_id": cat_id}, sperrschluessel=schluessel) or []
        except Exception as fehler:
            return (cat_name, [], str(fehler), False)
        kanaele = [baue_kanal(s, cat_name) for s in eintraege[:MAX_CHANNELS_PER_CALL]]
        return (cat_name, kanaele, None, False)

    @staticmethod
    def _sammelkategorie(name, titel):
        """Ersatzkategorie fuer Eintraege, die der Anbieter keiner Kategorie nennt.

        Die Namen tragen fast immer ein Sprachkuerzel in senkrechten Strichen,
        zum Beispiel "|IT| 4 Blocks". Danach wird sortiert, sonst landet der
        Eintrag in einer gemeinsamen Sammlung.
        """
        text = (name or "").strip()
        if text.startswith("|"):
            ende = text.find("|", 1)
            if 1 < ende <= 8:
                kuerzel = text[1:ende].strip().upper()
                if kuerzel:
                    return f"Weitere {titel} ({kuerzel})"
        return f"Weitere {titel}"

    def _versuche_gesamtabruf(self, inhalts_action, kategorien, baue_kanal,
                              titel, progress_callback=None):
        """Versucht, den gesamten Bestand in einem einzigen Abruf zu holen.

        Liefert die fertige Kanalliste oder None, wenn der Weg nicht geht.
        None bedeutet fuer den Aufrufer: bitte wie bisher ueber die Kategorien
        laden. Der Kategoriename wird ueber die category_id zugeordnet, damit
        die Einteilung in der Oberflaeche dieselbe bleibt.
        """
        if self._soll_abbrechen():
            return None

        namen = {}
        for k in kategorien or []:
            try:
                namen[str(k.get("category_id"))] = k.get("category_name", "")
            except Exception:
                pass

        try:
            if progress_callback:
                with self._fortschritt_schloss:
                    progress_callback(f"Lade {titel} in einem Zug...", 1, 3)
            alle = self._request(inhalts_action)
        except Exception as e:
            logger.info(f"{titel}: Gesamtabruf nicht moeglich ({e}), weiche auf Einzelabrufe aus")
            return None

        if not isinstance(alle, list) or not alle:
            logger.info(f"{titel}: Gesamtabruf lieferte nichts Verwertbares, weiche auf Einzelabrufe aus")
            return None

        # Gemessen am 19.09.2026: Die Kategorienliste des Anbieters nennt 49
        # Kennungen, im Serienbestand stecken aber 207. Fuer 22037 von 37623
        # Serien gibt es also gar keinen Kategorienamen. Ohne Ersatznamen waeren
        # sie ueber die Kategorien unerreichbar. Sie bekommen deshalb eine
        # Sammelkategorie, nach Sprachkuerzel aus dem Namen getrennt.
        kanaele = []
        unbekannt = 0
        for eintrag in alle:
            try:
                cat_name = namen.get(str(eintrag.get("category_id")), "")
                if not cat_name:
                    cat_name = self._sammelkategorie(eintrag.get("name", ""), titel)
                    unbekannt += 1
                kanaele.append(baue_kanal(eintrag, cat_name))
            except Exception:
                continue
        if unbekannt:
            logger.info(f"{titel}: {unbekannt} Eintraege ohne bekannte Kategorie, "
                        f"in Sammelkategorien einsortiert")

        if not kanaele:
            return None

        logger.info(f"{titel}: {len(kanaele)} Eintraege ueber den Gesamtabruf geladen")
        if progress_callback:
            with self._fortschritt_schloss:
                progress_callback(f"{titel}: {len(kanaele)} geladen", 3, 3)
        return kanaele

    def _lade_kategorien_parallel(self, kategorien_action, inhalts_action, baue_kanal,
                                   titel, leer_meldung, progress_callback=None, kategorie_fertig=None):
        """Gemeinsame Lademaschinerie der drei lazy-Methoden: parallel, abbrechbar, mit Sperrliste."""
        channels = []
        errors = []
        try:
            # Abbruchpruefung direkt vor dem ersten Netzabruf (Kategorienliste).
            if self._soll_abbrechen():
                logger.info("Abruf auf Wunsch abgebrochen nach 0 Kategorien")
                return channels
            if progress_callback:
                with self._fortschritt_schloss:
                    progress_callback(f"Lade {titel} Kategorien...", 0, 3)
            kategorien = self._request(kategorien_action) or []
            gesamt = len(kategorien)

            # Schnellweg zuerst: die meisten Anbieter liefern den gesamten
            # Bestand in EINEM Abruf. Gemessen am 19.09.2026 an einem echten
            # Anschluss: Live 5459 Eintraege in 1,0 Sekunde gegenueber 23,7
            # Sekunden ueber 96 Einzelabrufe, Filme 38478 Eintraege in 19,8
            # Sekunden. Klappt der Gesamtabruf nicht, wird wie bisher parallel
            # ueber die Kategorien geladen.
            schnell = self._versuche_gesamtabruf(inhalts_action, kategorien,
                                                 baue_kanal, titel, progress_callback)
            if schnell is not None:
                return schnell

            ergebnisse = {}
            abbruch_erkannt = False
            if gesamt:
                with ThreadPoolExecutor(max_workers=MAX_PARALLEL_ABRUFE) as pool:
                    laufend = {}
                    naechste = 0

                    def nachschieben():
                        """Reicht die naechste Kategorie ein, solange ein Faden frei ist und kein Abbruchwuenscht besteht."""
                        nonlocal naechste
                        while (naechste < gesamt
                               and len(laufend) < MAX_PARALLEL_ABRUFE
                               and not abbruch_erkannt
                               and not self._soll_abbrechen()):
                            laufend[pool.submit(self._lade_eine_kategorie, kategorien[naechste],
                                                inhalts_action, baue_kanal)] = naechste
                            naechste += 1

                    nachschieben()
                    while laufend:
                        # Abbruchpruefung am Anfang jeder Schleifenrunde; laufende Abrufe laufen zu Ende.
                        if not abbruch_erkannt and self._soll_abbrechen():
                            abbruch_erkannt = True
                        # Notbremse: antwortet der Anbieter bei der Mehrheit der
                        # Kategorien gar nicht, hat weiteres Warten keinen Sinn.
                        # Gemessen am 19.09.2026: bei den Serien liefen 48 von 49
                        # Kategorien in Zeitueberschreitungen, der Lauf dauerte
                        # dadurch 205 Sekunden fuer 226 Eintraege.
                        if (not abbruch_erkannt and gesamt >= 6
                                and len(self._tote_kategorien) > gesamt // 2):
                            logger.warning(
                                f"{titel}: mehr als die Haelfte der Kategorien antwortet nicht "
                                f"({len(self._tote_kategorien)} von {gesamt}), Abruf wird beendet"
                            )
                            abbruch_erkannt = True
                        erledigt, _ = wait(laufend, return_when=FIRST_COMPLETED)
                        for zukunft in erledigt:
                            index = laufend.pop(zukunft)
                            cat_name, kanaele, fehler, abgebrochen = zukunft.result()
                            ergebnisse[index] = kanaele
                            if fehler is not None:
                                errors.append(f"{titel} {cat_name}: {fehler}")
                                logger.warning(f"{titel} {cat_name} laden fehlgeschlagen: {fehler}")
                            if progress_callback:
                                with self._fortschritt_schloss:
                                    progress_callback(f"Lade {titel}: {cat_name} ({len(ergebnisse)}/{gesamt})",
                                                      len(ergebnisse), gesamt)
                            if kategorie_fertig is not None and not abgebrochen:
                                with self._fortschritt_schloss:
                                    kategorie_fertig(cat_name, len(kanaele), gesamt)
                        nachschieben()
            if abbruch_erkannt:
                logger.info(f"Abruf auf Wunsch abgebrochen nach {len(ergebnisse)} Kategorien")
            # Ergebnisse in der Reihenfolge der Kategorien zusammensetzen.
            for index in sorted(ergebnisse):
                channels.extend(ergebnisse[index])
        except Exception as e:
            errors.append(f"{titel} Kategorien: {e}")
            logger.error(f"{titel} Kategorien laden fehlgeschlagen: {e}")
        if not channels and errors:
            # Nach einem Abbruch von aussen ist ein leeres Ergebnis kein Fehler.
            # Der Nutzer hat weitergeschaltet, eine Fehlermeldung waere falsch.
            if self._soll_abbrechen():
                logger.info(f"{titel}: Abruf wurde abgebrochen, kein Ergebnis und keine Meldung")
                return channels
            raise Exception(leer_meldung + "; ".join(errors))
        return channels

    def get_live_channels_lazy(self, progress_callback=None, kategorie_fertig=None):
        """Laedt nur Live TV Kategorien und Streams (fuer erstes schnelles Laden)."""

        def baue_kanal(s, cat_name):
            return {
                "name": s.get("name", ""),
                "url": self.get_stream_url(s.get("stream_id"), "live"),
                "logo": s.get("stream_icon", ""),
                "category": cat_name,
                "tvg_id": str(s.get("stream_id", "")),
                "tvg_name": s.get("name", ""),
                "type": "live",
            }

        return self._lade_kategorien_parallel("get_live_categories", "get_live_streams", baue_kanal,
                                              "Live TV", "Keine Live TV Channels geladen. Fehler: ",
                                              progress_callback=progress_callback, kategorie_fertig=kategorie_fertig)

    def get_vod_channels_lazy(self, progress_callback=None, kategorie_fertig=None):
        """Laedt VOD (Filme) Kategorien und Streams (lazy, bei Auswahl)."""

        def baue_kanal(s, cat_name):
            return {
                "name": s.get("name", ""),
                "url": self.get_stream_url(s.get("stream_id"), "vod", s.get("container_extension")),
                "logo": s.get("stream_icon", ""),
                "category": cat_name,
                "tvg_id": str(s.get("stream_id", "")),
                "tvg_name": s.get("name", ""),
                "type": "vod",
            }

        return self._lade_kategorien_parallel("get_vod_categories", "get_vod_streams", baue_kanal,
                                              "VOD", "Keine VOD Channels geladen. Fehler: ",
                                              progress_callback=progress_callback, kategorie_fertig=kategorie_fertig)

    def get_series_channels_lazy(self, progress_callback=None, kategorie_fertig=None):
        """Laedt Serien Kategorien und Streams (lazy, bei Auswahl)."""

        def baue_kanal(s, cat_name):
            return {
                "name": s.get("name", ""),
                "url": self.get_stream_url(s.get("series_id"), "series"),
                "logo": s.get("cover", ""),
                "category": cat_name,
                "tvg_id": str(s.get("series_id", "")),
                "tvg_name": s.get("name", ""),
                "type": "series",
            }

        return self._lade_kategorien_parallel("get_series_categories", "get_series", baue_kanal,
                                              "Serien", "Keine Serien Channels geladen. Fehler: ",
                                              progress_callback=progress_callback, kategorie_fertig=kategorie_fertig)

    def get_all_categories(self, progress_callback=None):
        """Laedt nur Kategorien (Live, VOD, Series) - sehr schnell (3 API-Calls)."""
        categories = {"live": [], "vod": [], "series": []}
        try:
            if progress_callback:
                progress_callback("Lade Live TV Kategorien...", 1, 3)
            categories["live"] = self.get_live_categories() or []
        except Exception as e:
            logger.warning(f"Live TV Kategorien: {e}")
        try:
            if progress_callback:
                progress_callback("Lade VOD Kategorien...", 2, 3)
            categories["vod"] = self.get_vod_categories() or []
        except Exception as e:
            logger.warning(f"VOD Kategorien: {e}")
        try:
            if progress_callback:
                progress_callback("Lade Serien Kategorien...", 3, 3)
            categories["series"] = self.get_series_categories() or []
        except Exception as e:
            logger.warning(f"Serien Kategorien: {e}")
        return categories

    def get_all_channels(self, progress_callback=None):
        """Alle Channels (Live + VOD + Series) als einheitliche Liste abrufen.
        Verwendet intern die lazy-Loading-Methoden fuer bessere Performance.
        """
        channels = []
        errors = []
        try:
            live_channels = self.get_live_channels_lazy(progress_callback)
            channels.extend(live_channels)
        except Exception as e:
            errors.append(f"Live TV: {e}")
        try:
            vod_channels = self.get_vod_channels_lazy(progress_callback)
            channels.extend(vod_channels)
        except Exception as e:
            errors.append(f"VOD: {e}")
        try:
            series_channels = self.get_series_channels_lazy(progress_callback)
            channels.extend(series_channels)
        except Exception as e:
            errors.append(f"Series: {e}")
        if not channels and errors:
            raise Exception("Keine Channels geladen. Fehler: " + "; ".join(errors))
        return channels
