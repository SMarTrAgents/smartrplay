# -*- coding: utf-8 -*-
"""
SMarTrPlay Android TV — Video Player
Zwei Modi: Intent (externer Player) und ffpyplayer (Kivy Video Widget).
"""

import os
import subprocess

# Kivy imports nur fuer ffpyplayer Modus
try:
    from kivy.uix.video import Video
    from kivy.uix.widget import Widget
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.clock import Clock
    from kivy.metrics import dp
    KIVY_AVAILABLE = True
except Exception:
    KIVY_AVAILABLE = False
    Video = object
    Widget = object
    BoxLayout = object
    Button = object
    Label = object

# pyjnius fuer Android Intent
try:
    from jnius import autoclass, cast
    JNIUS_AVAILABLE = True
except Exception:
    JNIUS_AVAILABLE = False

# ffpyplayer
try:
    from ffpyplayer import ffpyplayer as ffp
    FFPYPLAYER_AVAILABLE = True
except Exception:
    FFPYPLAYER_AVAILABLE = False


# Android Klassen (nur auf Android verfuegbar)
if JNIUS_AVAILABLE:
    try:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        Context = autoclass("android.content.Context")
        PackageManager = autoclass("android.content.pm.PackageManager")
    except Exception:
        PythonActivity = None
        Intent = None
        Uri = None
        Context = None
        PackageManager = None
else:
    PythonActivity = None
    Intent = None
    Uri = None
    Context = None
    PackageManager = None


class VideoPlayer:
    """
    Video Player mit zwei Modi:
    a) Intent Mode: Oeffnet Stream URL in externem Android Player (VLC, MX Player)
    b) ffpyplayer Mode: Kivy Video Widget mit ffpyplayer
    """

    # Bekannte Player Packages
    PLAYER_PACKAGES = {
        "vlc": "org.videolan.vlc",
        "vlc_beta": "org.videolan.vlc.betav7neon",
        "mx_player": "com.mxtech.videoplayer.ad",
        "mx_player_pro": "com.mxtech.videoplayer.pro",
        "mx_player_legacy": "com.mxtech.videoplayer.adL",
        "exo_player": "com.google.android.exoplayer",
        "system": None,  # System Default Player
    }

    def __init__(self, mode="intent", player_widget=None):
        """
        Initialisiert den Video Player.

        Args:
            mode: 'intent' oder 'ffpyplayer'.
            player_widget: Kivy Video Widget fuer ffpyplayer Modus.
        """
        self.mode = mode
        self.player_widget = player_widget
        self.current_url = None
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
        self.duration = 0.0
        self._ffp_player = None

    def play(self, url, title=""):
        """
        Startet die Wiedergabe einer Stream-URL.

        Args:
            url: Stream-URL (z.B. HLS/m3u8, mp4, ts).
            title: Titel fuer Intent/Anzeige.
        """
        self.current_url = url
        if self.mode == "intent":
            return self._play_intent(url, title)
        elif self.mode == "ffpyplayer":
            return self._play_ffpyplayer(url)
        else:
            raise ValueError(f"Unbekannter Player Modus: {self.mode}")

    def stop(self):
        """Stoppt die Wiedergabe."""
        if self.mode == "intent":
            # Intent-Player kann nicht direkt gestoppt werden
            self.is_playing = False
            return True
        elif self.mode == "ffpyplayer":
            return self._stop_ffpyplayer()
        return False

    def pause(self):
        """Pausiert die Wiedergabe."""
        if self.mode == "ffpyplayer":
            if self._ffp_player:
                self._ffp_player.pause_player = True
                self.is_paused = True
                return True
        return False

    def resume(self):
        """Setzt die Wiedergabe fort."""
        if self.mode == "ffpyplayer":
            if self._ffp_player:
                self._ffp_player.pause_player = False
                self.is_paused = False
                return True
        return False

    def toggle_play_pause(self):
        """Schaltet zwischen Play und Pause um."""
        if self.is_paused:
            return self.resume()
        else:
            return self.pause()

    def seek_relative(self, seconds):
        """
        Spult relativ um +/- Sekunden.

        Args:
            seconds: +10 fuer 10s vor, -10 fuer 10s zurueck.
        """
        if self.mode == "ffpyplayer" and self._ffp_player:
            try:
                current = self._get_position()
                new_pos = max(0, current + seconds)
                self._ffp_player.seek_ratio = new_pos / max(1, self.duration)
                return True
            except Exception:
                return False
        return False

    def _get_position(self):
        """Gibt die aktuelle Position in Sekunden zurueck."""
        if self._ffp_player:
            try:
                return self._ffp_player.get_position() * self.duration
            except Exception:
                pass
        return self.position

    def get_duration(self):
        """Gibt die Gesamtdauer in Sekunden zurueck."""
        if self._ffp_player:
            try:
                return self._ffp_player.get_duration()
            except Exception:
                pass
        return self.duration

    # --- Intent Mode ---

    def _play_intent(self, url, title=""):
        """
        Oeffnet Stream URL in externem Android Player via Intent.

        Bevorzugt VLC, MX Player, oder System Player.
        """
        if not JNIUS_AVAILABLE or Intent is None:
            raise Exception("pyjnius nicht verfuegbar - Intent Modus nicht moeglich")

        try:
            intent = Intent(Intent.ACTION_VIEW)
            uri = Uri.parse(url)
            intent.setDataAndType(uri, "video/*")

            # Flags: Activity new task
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

            # Versuche spezifische Player zu nutzen
            player_launched = False

            for player_name, package in self.PLAYER_PACKAGES.items():
                if package is None:
                    continue
                try:
                    intent.setPackage(package)
                    PythonActivity.mActivity.startActivity(intent)
                    self.is_playing = True
                    player_launched = True
                    break
                except Exception:
                    continue

            # Fallback: System Default Player (no package set)
            if not player_launched:
                intent = Intent(Intent.ACTION_VIEW)
                uri = Uri.parse(url)
                intent.setDataAndType(uri, "video/*")
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                # Try chooser
                try:
                    chooser = Intent.createChooser(intent, "Player waehlen")
                    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    PythonActivity.mActivity.startActivity(chooser)
                    self.is_playing = True
                    player_launched = True
                except Exception:
                    # Last resort: direct
                    try:
                        PythonActivity.mActivity.startActivity(intent)
                        self.is_playing = True
                        player_launched = True
                    except Exception as e:
                        raise Exception(f"Kein Player gefunden: {e}")

            return player_launched

        except Exception as e:
            raise Exception(f"Intent Error: {e}")

    # --- ffpyplayer Mode ---

    def _play_ffpyplayer(self, url):
        """Startet Wiedergabe mit ffpyplayer/Kivy Video Widget."""
        if not KIVY_AVAILABLE:
            raise Exception("Kivy nicht verfuegbar")

        if self.player_widget:
            # Kivy Video Widget nutzen
            self.player_widget.state = "play"
            self.player_widget.source = url
            self.player_widget.options = {
                "eos": "loop",
            }
            self.is_playing = True
            self.is_paused = False
            return True
        elif FFPYPLAYER_AVAILABLE:
            # Direkter ffpyplayer (headless)
            try:
                self._ffp_player = ffp.MediaPlayer(
                    url,
                    ff_opts={
                        "an": False,
                        "paused": False,
                        "ss": 0,
                    },
                )
                self.is_playing = True
                self.is_paused = False
                return True
            except Exception as e:
                raise Exception(f"ffpyplayer Error: {e}")
        else:
            raise Exception("Weder Kivy Video Widget noch ffpyplayer verfuegbar")

    def _stop_ffpyplayer(self):
        """Stoppt ffpyplayer Wiedergabe."""
        if self.player_widget:
            self.player_widget.state = "stop"
            self.is_playing = False
            self.is_paused = False
            return True

        if self._ffp_player:
            try:
                self._ffp_player.close_player()
                self._ffp_player = None
            except Exception:
                pass
            self.is_playing = False
            self.is_paused = False
            return True

        return False

    # --- Player Detection ---

    @staticmethod
    def get_available_players():
        """
        Liste installierter Video Player auf dem Geraet.

        Returns:
            list: Liste von Dicts mit {name, package, installed}.
        """
        players = []

        if not JNIUS_AVAILABLE or PackageManager is None:
            # Desktop fallback: leere Liste
            for name, package in VideoPlayer.PLAYER_PACKAGES.items():
                players.append({
                    "name": name,
                    "package": package or "system",
                    "installed": False,
                })
            return players

        try:
            context = PythonActivity.mActivity.getApplicationContext()
            pm = context.getPackageManager()

            for name, package in VideoPlayer.PLAYER_PACKAGES.items():
                installed = False
                if package is None:
                    installed = True  # System player always available
                else:
                    try:
                        pm.getPackageInfo(package, PackageManager.GET_ACTIVITIES)
                        installed = True
                    except Exception:
                        installed = False

                players.append({
                    "name": name,
                    "package": package or "system",
                    "installed": installed,
                })
        except Exception:
            for name, package in VideoPlayer.PLAYER_PACKAGES.items():
                players.append({
                    "name": name,
                    "package": package or "system",
                    "installed": False,
                })

        return players

    # --- Cleanup ---

    def cleanup(self):
        """Raeumt den Player auf."""
        self.stop()
        if self._ffp_player:
            try:
                self._ffp_player.close_player()
            except Exception:
                pass
            self._ffp_player = None


# --- Kivy VideoPlayer Widget Wrapper ---

if KIVY_AVAILABLE:

    class FFVideoWidget(Widget):
        """Kivy Video Widget Wrapper fuer ffpyplayer Integration."""

        def __init__(self, **kwargs):
            kwargs.setdefault("size_hint", (1, 1))
            super().__init__(**kwargs)
            self._video = None
            self._url = None
            self._state = "stop"

        def load(self, url):
            """Laedt eine Stream URL."""
            self._url = url
            if self._video:
                self.remove_widget(self._video)

            self._video = Video(source=url, state=self._state, play=True)
            self._video.bind(position=self._on_position)
            self._video.bind(duration=self._on_duration)
            self._video.bind(eos=self._on_eos)
            self.add_widget(self._video)

        def play(self):
            """Startet Wiedergabe."""
            if self._video:
                self._video.state = "play"
                self._state = "play"

        def pause(self):
            """Pausiert Wiedergabe."""
            if self._video:
                self._video.state = "pause"
                self._state = "pause"

        def stop(self):
            """Stoppt Wiedergabe."""
            if self._video:
                self._video.state = "stop"
                self._state = "stop"

        def seek(self, seconds):
            """Spult zu einer Position (Sekunden)."""
            if self._video:
                self._video.seek(seconds / max(1, self._video.duration))

        def seek_relative(self, seconds):
            """Spult relativ +/- Sekunden."""
            if self._video:
                current = self._video.position
                new_pos = max(0, current + seconds)
                self.seek(new_pos)

        def _on_position(self, instance, value):
            pass

        def _on_duration(self, instance, value):
            pass

        def _on_eos(self, instance, value):
            """End of Stream Handler."""
            self._state = "stop"

else:

    class FFVideoWidget:
        """Stub fuer Desktop ohne Kivy."""

        def __init__(self, **kwargs):
            pass

        def load(self, url):
            pass

        def play(self):
            pass

        def pause(self):
            pass

        def stop(self):
            pass

        def seek(self, seconds):
            pass

        def seek_relative(self, Sseconds):
            pass
