#!/usr/bin/env python3
"""SMarTrPlay - VLC Player Backend (libvlc über python-vlc).

Ersetzt das ffplay-Unterprozess-Backend aus player.py. ffplay liest Tasten
nur aus seinem eigenen SDL-Fenster, deshalb waren Pause, Spulen, Stummschalten
und Lautstärke über die Standardeingabe wirkungslos. Dieses Backend steuert
libvlc direkt: jeder Befehl wirkt sofort auf die laufende Wiedergabe, und
Position sowie Dauer sind abfragbar.
"""

import logging
import os
import subprocess

import vlc

logger = logging.getLogger('SMarTrPlay')

# Argumente für die einzige vlc.Instance dieses Backends.
#
# Bewusst NICHT gesetzt: "--no-xlib".
# Begründung: play() bettet das Videobild per set_xwindow() in ein Qt-Fenster
# ein. Dafür braucht der X11-Videotreiber von libvlc eine eigene Xlib-Verbindung.
# Mit "--no-xlib" kann libvlc das Fremdfenster nicht übernehmen, das eingebettete
# Qt-Fenster bleibt schwarz. Im Einbettungstest mit Xvfb wurde nachgewiesen:
# ohne "--no-xlib" rendert libvlc in das Qt-Fenster, mit "--no-xlib" schlägt
# das Einbetten fehl. Der kopflose Selbsttest mit Dummy-Ausgaben läuft mit
# beiden Varianten, für die grafische Anwendung ist nur die Variante ohne
# "--no-xlib" brauchbar.
#
# "--quiet": libvlc schreibt keine Meldungen auf die Konsole, Fehler laufen
#            über self.last_error und das Protokoll.
# "--network-caching=3000": 3000 Millisekunden Netzpuffer, vorgeschrieben für
#            IPTV-Streams, damit schwankende Quellen nicht sofort abreißen.
# "--no-video-title-show": der Medientitel wird nicht ins laufende Bild gezeichnet.
VLC_ARGS = (
    "--quiet",
    "--network-caching=3000",
    "--no-video-title-show",
)


class VlcPlayerBackend:
    """Wiedergabe-Backend auf Basis einer einzelnen vlc.Instance.

    Eine Instanz, ein MediaPlayer, keine Threads und keine Hintergrundprozesse.
    Jede öffentliche Methode fängt ihre Ausnahmen ab; nach außen fliegt nie
    eine Ausnahme. Fehler landen in self.last_error, im Protokoll und sind
    über get_error() abfragbar.
    """

    def __init__(self, extra_args=None):
        """Backend anlegen und den MediaPlayer erzeugen.

        extra_args ist optional und nur für Tests gedacht (der kopflose
        Selbsttest übergibt "--vout=dummy" und "--aout=dummy", damit keine
        grafische Oberfläche nötig ist). Ohne Argument verhält sich der
        Konstruktor genau wie in der Pflicht-Schnittstelle vorgeschrieben.
        """
        # Von außen lesbare Eigenschaften
        self.current_url = None
        self.volume = 80
        self.is_playing = False
        self.last_error = ""

        # Interner Zustand
        self._muted = False
        self._pause_requested = False
        self._released = False
        self._window_id = None
        self._subtitle_file = None
        self._ytdl_process = None
        self._ytdl_pipe_read = None
        self.instance = None
        self.player = None
        try:
            argumente = list(VLC_ARGS)
            if extra_args:
                argumente.extend(str(a) for a in extra_args)
            self.instance = vlc.Instance(*argumente)
            if not self.instance:
                raise RuntimeError("vlc.Instance konnte nicht erzeugt werden")
            self.player = self.instance.media_player_new()
            if not self.player:
                raise RuntimeError("MediaPlayer konnte nicht erzeugt werden")
        except Exception as fehler:
            self.instance = None
            self.player = None
            self.last_error = "VLC-Initialisierung fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)

    # ------------------------------------------------------------------
    # Wiedergabe steuern
    # ------------------------------------------------------------------

    def play(self, url, window_id=None):
        """Medium laden und abspielen.

        window_id ist eine X11-Fenster-ID (int) aus Qt winId(). Ist sie
        gesetzt, wird das Videobild mit set_xwindow() in dieses Fenster
        eingebettet. Der Netzpuffer steht über die Instanz-Argumente auf
        3000 Millisekunden. Bei einem Fehler wird False geliefert und
        self.last_error gesetzt.
        """
        if self._released:
            self.last_error = "Backend wurde bereits freigegeben"
            logger.error(self.last_error)
            return False
        try:
            if self.player is None:
                self.last_error = "Kein MediaPlayer vorhanden, play() abgelehnt"
                logger.error(self.last_error)
                return False
            if not url:
                self.last_error = "play() ohne URL aufgerufen"
                logger.error(self.last_error)
                return False

            self.stop()
            self.current_url = str(url)
            if window_id is not None and int(window_id) != 0:
                self._window_id = int(window_id)

            medium = None
            try:
                medium = self.instance.media_new(self.current_url)
                # Gemerkte Untertiteldatei einmalig an dieses Medium hängen
                if self._subtitle_file and os.path.isfile(self._subtitle_file):
                    medium.add_option(":sub-file=%s" % self._subtitle_file)
                    self._subtitle_file = None
                self.player.set_media(medium)
            finally:
                if medium is not None:
                    medium.release()

            if self._window_id is not None:
                self.player.set_xwindow(self._window_id)
                # Qt soll Eingaben behalten, sonst schluckt das eingebettete
                # libvlc-Fenster Tastatur und Maus und die Bedienelemente
                # der Anwendung wären tot.
                try:
                    self.player.video_set_key_input(False)
                    self.player.video_set_mouse_input(False)
                except Exception:
                    pass

            # Gespeicherte Lautstärke und Stummschaltung sofort anwenden,
            # damit der neue Stream mit den erwarteten Werten startet.
            try:
                self.player.audio_set_volume(self.volume)
                self.player.audio_set_mute(self._muted)
            except Exception:
                # Ohne aktive Audiospur lehnt libvlc das Setzen ab; die Werte
                # bleiben gemerkt und gelten für den Stream, sobald Ton da ist.
                pass

            rueckgabe = self.player.play()
            if rueckgabe != 0:
                self.last_error = "libvlc hat die Wiedergabe abgelehnt (Rückgabe %s)" % rueckgabe
                logger.error(self.last_error)
                self.current_url = None
                return False
            self.is_playing = True
            self._pause_requested = False
            self.last_error = ""
            return True
        except Exception as fehler:
            self.last_error = "play() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
            return False

    def stop(self):
        """Wiedergabe anhalten, yt-dlp-Rohr schließen und Medium entladen."""
        if self._released:
            return
        try:
            self._ytdl_beenden()
            if self.player is not None:
                self.player.stop()
        except Exception as fehler:
            self.last_error = "stop() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
        self.is_playing = False
        self._pause_requested = False
        self.current_url = None

    def pause(self):
        """Zwischen Pause und Weiter umschalten, ohne die Wiedergabe neu zu starten."""
        self.set_paused(not self.is_paused())

    def set_paused(self, paused):
        """Pausezustand setzen (True = Pause, False = Weiter)."""
        if self._released:
            return
        try:
            if self.player is None:
                return
            self.player.set_pause(1 if paused else 0)
            # libvlc übernimmt den Befehl asynchron; die Absicht wird gemerkt,
            # damit is_paused() direkt nach dem Aufruf bereits das Ziel meldet.
            self._pause_requested = bool(paused) and self.is_playing
        except Exception as fehler:
            self.last_error = "set_paused() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)

    def is_paused(self):
        """True, solange die Wiedergabe pausiert ist."""
        try:
            if self.player is None:
                return False
            zustand = self.player.get_state()
            if zustand == vlc.State.Paused:
                return True
            # Während der Umschaltphase (Öffnen, Puffern, Spielen) gilt die
            # gemerkte Absicht, bis libvlc den Zustand übernommen hat.
            if self._pause_requested and zustand in (
                vlc.State.Playing,
                vlc.State.Buffering,
                vlc.State.Opening,
            ):
                return True
            return False
        except Exception as fehler:
            logger.debug("is_paused() fehlgeschlagen: %s", fehler)
            return False

    def seek_relative(self, seconds):
        """Relativ spulen, negative Werte spulen zurück. Nur bei spulbarem Medium."""
        try:
            if self.player is None or not self.is_seekable():
                return
            jetzt_ms = self.player.get_time()
            ziel_ms = max(0, int(jetzt_ms) + int(seconds) * 1000)
            self.player.set_time(ziel_ms)
        except Exception as fehler:
            self.last_error = "seek_relative() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)

    def seek_to(self, seconds):
        """Absolut auf ganze Sekunden springen. Nur bei spulbarem Medium."""
        try:
            if self.player is None or not self.is_seekable():
                return
            self.player.set_time(max(0, int(seconds)) * 1000)
        except Exception as fehler:
            self.last_error = "seek_to() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)

    def is_seekable(self):
        """True, wenn das aktuelle Medium spulbar ist (Live-Streams sind es nicht)."""
        try:
            if self.player is None:
                return False
            return self.player.is_seekable() == 1
        except Exception as fehler:
            logger.debug("is_seekable() fehlgeschlagen: %s", fehler)
            return False

    def get_position(self):
        """(Position in ganzen Sekunden, Dauer in ganzen Sekunden).

        Bei Live-Streams oder unbekannter Dauer ist die Dauer 0.
        """
        try:
            if self.player is None:
                return (0, 0)
            position_ms = self.player.get_time()
            dauer_ms = self.player.get_length()
            position = int(position_ms) // 1000 if position_ms and position_ms > 0 else 0
            dauer = int(dauer_ms) // 1000 if dauer_ms and dauer_ms > 0 else 0
            return (position, dauer)
        except Exception as fehler:
            logger.debug("get_position() fehlgeschlagen: %s", fehler)
            return (0, 0)

    # ------------------------------------------------------------------
    # Ton
    # ------------------------------------------------------------------

    def set_volume(self, volume):
        """Lautstärke 0 bis 100 setzen, wirkt sofort auf die laufende Wiedergabe."""
        try:
            wert = max(0, min(100, int(volume)))
        except (TypeError, ValueError):
            return
        self.volume = wert
        try:
            if self.player is not None:
                self.player.audio_set_volume(wert)
        except Exception as fehler:
            # Ohne aktive Audiospur nimmt libvlc den Wert nicht an; er bleibt
            # gemerkt und wird beim nächsten play() erneut angewendet.
            logger.debug("audio_set_volume fehlgeschlagen: %s", fehler)

    def get_volume(self):
        """Gemerkte Lautstärke 0 bis 100, deckungsgleich mit dem an libvlc übergebenen Wert."""
        return self.volume

    def mute(self):
        """Stummschaltung umschalten."""
        self.set_muted(not self.is_muted())

    def set_muted(self, muted):
        """True = stumm schalten, False = Ton einschalten."""
        self._muted = bool(muted)
        try:
            if self.player is not None:
                self.player.audio_set_mute(self._muted)
        except Exception as fehler:
            logger.debug("audio_set_mute fehlgeschlagen: %s", fehler)

    def is_muted(self):
        """True, wenn die Wiedergabe stummgeschaltet ist."""
        return self._muted

    def is_running(self):
        """True, solange tatsächlich abgespielt oder pausiert wird."""
        try:
            if self.player is None or self._released or not self.is_playing:
                return False
            zustand = self.player.get_state()
            return zustand in (
                vlc.State.Playing,
                vlc.State.Paused,
                vlc.State.Opening,
                vlc.State.Buffering,
            )
        except Exception as fehler:
            logger.debug("is_running() fehlgeschlagen: %s", fehler)
            return False

    # ------------------------------------------------------------------
    # Tonspuren und Untertitel
    # ------------------------------------------------------------------

    def get_audio_tracks(self):
        """Verfügbare Tonspuren als Liste von (id, Name)."""
        try:
            if self.player is None:
                return []
            beschreibung = self.player.audio_get_track_description()
            ergebnis = []
            for spur_id, name in beschreibung or []:
                if int(spur_id) == -1:
                    continue  # libvlc-Eintrag "Disable" ist keine echte Tonspur
                ergebnis.append((int(spur_id), self._spurname(name)))
            return ergebnis
        except Exception as fehler:
            logger.debug("get_audio_tracks() fehlgeschlagen: %s", fehler)
            return []

    def set_audio_track(self, track_id):
        """Tonspur wählen. Liefert False, wenn libvlc die Spur nicht annimmt."""
        try:
            if self.player is None:
                return False
            rueckgabe = self.player.audio_set_track(int(track_id))
            if rueckgabe == 0:
                return True
            self.last_error = "Tonspur %s nicht wählbar (Rückgabe %s)" % (track_id, rueckgabe)
            logger.error(self.last_error)
            return False
        except Exception as fehler:
            self.last_error = "set_audio_track() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
            return False

    def get_subtitle_tracks(self):
        """Verfügbare Untertitelspuren als Liste von (id, Name). id -1 bedeutet aus."""
        try:
            if self.player is None:
                return []
            beschreibung = self.player.video_get_spu_description()
            ergebnis = []
            for spur_id, name in beschreibung or []:
                if int(spur_id) == -1:
                    ergebnis.append((-1, "Aus"))
                else:
                    ergebnis.append((int(spur_id), self._spurname(name)))
            if not any(spuren_id == -1 for spuren_id, _ in ergebnis):
                # Der Ausschalter gehört auch dann in die Liste, wenn libvlc
                # ihn gerade nicht meldet.
                ergebnis.insert(0, (-1, "Aus"))
            return ergebnis
        except Exception as fehler:
            logger.debug("get_subtitle_tracks() fehlgeschlagen: %s", fehler)
            return []

    def set_subtitle_track(self, track_id):
        """Untertitelspur wählen, -1 schaltet die Untertitel aus."""
        try:
            if self.player is None:
                return False
            rueckgabe = self.player.video_set_spu(int(track_id))
            if rueckgabe == 0:
                return True
            self.last_error = "Untertitelspur %s nicht wählbar (Rückgabe %s)" % (track_id, rueckgabe)
            logger.error(self.last_error)
            return False
        except Exception as fehler:
            self.last_error = "set_subtitle_track() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
            return False

    def set_subtitle_file(self, path):
        """Untertiteldatei laden.

        Läuft gerade ein Medium, wird die Datei sofort an die laufende
        Wiedergabe gehängt. Ist noch nichts geladen, wird der Pfad gemerkt
        und beim nächsten play() als Option angehängt.
        """
        try:
            if not path or not os.path.isfile(path):
                self.last_error = "Untertiteldatei fehlt: %s" % path
                logger.error(self.last_error)
                return False
            self._subtitle_file = os.path.abspath(path)
            if self.player is None:
                return True
            medium = None
            try:
                medium = self.player.get_media()
            except Exception:
                medium = None
            if medium is None:
                # Es ist kein Medium geladen, der Pfad gilt für den nächsten Start.
                return True
            try:
                adresse = "file://%s" % self._subtitle_file
                rueckgabe = vlc.libvlc_media_player_add_slave(
                    self.player, 0, adresse.encode("utf-8"), True
                )
            finally:
                medium.release()
            if rueckgabe == 0:
                # Sofort aktiv, ein erneutes Anhängen beim nächsten play()
                # derselben Quelle ist nicht nötig.
                self._subtitle_file = None
                return True
            # Hot-Anhängen fehlgeschlagen; der gemerkte Pfad greift beim
            # nächsten play() über die Option :sub-file=.
            self.last_error = "libvlc hat die Untertiteldatei nicht angenommen (Rückgabe %s)" % rueckgabe
            logger.error(self.last_error)
            return False
        except Exception as fehler:
            self.last_error = "set_subtitle_file() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
            return False

    def set_subtitle_delay(self, delay_ms):
        """Untertitel-Versatz in Millisekunden setzen."""
        try:
            if self.player is None:
                return
            self.player.video_set_spu_delay(int(delay_ms))
        except Exception as fehler:
            self.last_error = "set_subtitle_delay() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)

    # ------------------------------------------------------------------
    # Zustand und Fehler
    # ------------------------------------------------------------------

    def get_error(self):
        """Letzte Fehlermeldung oder leerer String."""
        return self.last_error

    def get_state(self):
        """Zustand als Text: playing, paused, stopped, ended, error oder buffering."""
        try:
            if self.player is None or self._released:
                return "stopped"
            zustand = self.player.get_state()
            if zustand == vlc.State.Playing:
                return "playing"
            if zustand == vlc.State.Paused:
                return "paused"
            if zustand == vlc.State.Ended:
                return "ended"
            if zustand == vlc.State.Error:
                return "error"
            if zustand in (vlc.State.Opening, vlc.State.Buffering):
                return "buffering"
            # Nichts Besonderes und Gestoppt laufen beide auf stopped hinaus.
            return "stopped"
        except Exception as fehler:
            logger.debug("get_state() fehlgeschlagen: %s", fehler)
            return "stopped"

    def release(self):
        """Alles freigeben, für das Programmende. Darf mehrfach aufgerufen werden."""
        if self._released:
            return
        self._released = True
        self.is_playing = False
        self.current_url = None
        self._pause_requested = False
        try:
            self._ytdl_beenden()
        except Exception as fehler:
            logger.error("yt-dlp-Bereinigung fehlgeschlagen: %s", fehler)
        try:
            if self.player is not None:
                try:
                    self.player.stop()
                except Exception as fehler:
                    logger.debug("stop() vor der Freigabe fehlgeschlagen: %s", fehler)
                try:
                    medium = self.player.get_media()
                    if medium is not None:
                        medium.release()
                except Exception:
                    pass
                self.player.release()
                self.player = None
        except Exception as fehler:
            self.last_error = "Player-Freigabe fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
        try:
            if self.instance is not None:
                self.instance.release()
                self.instance = None
        except Exception as fehler:
            self.last_error = "Instanz-Freigabe fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)

    # ------------------------------------------------------------------
    # YouTube und Netflix
    # ------------------------------------------------------------------

    def play_youtube(self, url):
        """YouTube abspielen: yt-dlp schreibt den Stream nach stdout, libvlc liest die Pipe.

        Schlägt das fehl (yt-dlp fehlt oder lehnt die Adresse ab), wird der
        Link mit xdg-open an den Browser übergeben.
        """
        if self._released:
            self.last_error = "Backend wurde bereits freigegeben"
            logger.error(self.last_error)
            return False
        prozess = None
        lese_fd = None
        try:
            if not url:
                self.last_error = "play_youtube() ohne URL aufgerufen"
                logger.error(self.last_error)
                return False
            self.stop()
            lese_fd, schreib_fd = os.pipe()
            try:
                prozess = subprocess.Popen(
                    ["yt-dlp", "--no-playlist", "-o", "-", str(url)],
                    stdout=schreib_fd,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except Exception as fehler:
                self.last_error = "yt-dlp nicht startbar: %s" % fehler
                logger.error(self.last_error)
                os.close(schreib_fd)
                os.close(lese_fd)
                return self._extern_oeffnen(url)
            # Nur yt-dlp hält die Schreibseite offen; im Elternprozess schließen,
            # damit libvlc das Datenende erkennt, sobald yt-dlp endet.
            os.close(schreib_fd)
            # play() ruft zuerst stop() und beendet damit nur noch ein altes
            # yt-dlp-Rohr; das neue Prozessobjekt wird erst nach Erfolg gemerkt.
            if self.play("fd://%d" % lese_fd):
                self._ytdl_process = prozess
                self._ytdl_pipe_read = lese_fd
                return True
            self._prozess_beenden(prozess)
            os.close(lese_fd)
            return self._extern_oeffnen(url)
        except Exception as fehler:
            self.last_error = "play_youtube() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
            if prozess is not None:
                self._prozess_beenden(prozess)
            if lese_fd is not None:
                try:
                    os.close(lese_fd)
                except OSError:
                    pass
            return self._extern_oeffnen(url)

    def open_netflix(self, url):
        """Netflix-Link im Standardbrowser öffnen (DRM-Inhalte kann libvlc nicht abspielen)."""
        try:
            if not url:
                self.last_error = "open_netflix() ohne URL aufgerufen"
                logger.error(self.last_error)
                return False
            return self._extern_oeffnen(url)
        except Exception as fehler:
            self.last_error = "open_netflix() fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
            return False

    # ------------------------------------------------------------------
    # Interne Hilfsfunktionen
    # ------------------------------------------------------------------

    @staticmethod
    def _spurname(name):
        """Spurname von libvlc (Bytes) in lesbaren Text wandeln."""
        if isinstance(name, bytes):
            return name.decode("utf-8", "replace")
        return str(name)

    def _ytdl_beenden(self):
        """Laufenden yt-dlp-Prozess beenden und das Lese-Ende der Pipe schließen."""
        prozess = self._ytdl_process
        self._ytdl_process = None
        if prozess is not None:
            self._prozess_beenden(prozess)
        lese_fd = self._ytdl_pipe_read
        self._ytdl_pipe_read = None
        if lese_fd is not None:
            try:
                os.close(lese_fd)
            except OSError:
                pass

    @staticmethod
    def _prozess_beenden(prozess):
        """Prozess höflich beenden und nach kurzer Frist erzwungen abschließen."""
        try:
            prozess.terminate()
        except Exception:
            pass
        try:
            prozess.wait(timeout=0.2)
            return
        except Exception:
            pass
        try:
            prozess.kill()
            prozess.wait(timeout=0.2)
        except Exception:
            pass

    def _extern_oeffnen(self, url):
        """Adresse mit xdg-open an den Browser übergeben."""
        try:
            subprocess.Popen(
                ["xdg-open", str(url)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            self.current_url = str(url)
            return True
        except Exception as fehler:
            self.last_error = "xdg-open fehlgeschlagen: %s" % fehler
            logger.error(self.last_error)
            return False