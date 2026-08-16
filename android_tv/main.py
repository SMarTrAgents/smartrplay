# -*- coding: utf-8 -*-
"""
SMarTrPlay Android TV — Main Entry Point
Kivy App mit ScreenManager fuer Android TV D-Pad Navigation.
"""

import os
import sys

# Sicherstellen, dass das aktuelle Verzeichnis im Path ist
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.config import Config as KivyConfig

# SMarTr Brand Colors
BG_DARK = (0.039, 0.059, 0.118, 1)
ACCENT_CYAN = (0.106, 0.945, 0.984, 1)
ACCENT_VIOLET = (0.553, 0.486, 0.961, 1)

# Kivy Konfiguration fuer Android TV
KivyConfig.set("graphics", "width", "1280")
KivyConfig.set("graphics", "height", "720")
KivyConfig.set("graphics", "resizable", "True")
KivyConfig.set("input", "mouse", "mouse")
KivyConfig.set("kivy", "keyboard_mode", "systemanddock")

# Screens importieren
from screens import (
    ProviderSetupScreen,
    CategoryScreen,
    ChannelListScreen,
    VideoScreen,
    SettingsScreen,
)
from config_android import ConfigManager


class SMarTrPlayTV(App):
    """SMarTrPlay Android TV App — Kivy Entry Point."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # App State
        self.xtream_client = None
        self.m3u_parser = None
        self.m3u_entries = None
        self.current_provider_name = None
        self.current_category = None
        self.current_channel = None

        # Config Manager — user_data_dir wird in build() gesetzt
        self.config = None

        # ScreenManager
        self.sm = None

    def build(self):
        """Baut die App auf und gibt den ScreenManager zurueck."""
        # Config Manager mit App user_data_dir initialisieren
        data_dir = self.user_data_dir if hasattr(self, "user_data_dir") else os.path.expanduser("~/.smartrplay")
        self.config = ConfigManager(data_dir=data_dir)

        # ScreenManager
        self.sm = ScreenManager()

        # Screens erstellen
        self.provider_screen = ProviderSetupScreen(name="provider_setup")
        self.category_screen = CategoryScreen(name="category")
        self.channel_list_screen = ChannelListScreen(name="channel_list")
        self.video_screen = VideoScreen(name="video")
        self.settings_screen = SettingsScreen(name="settings")

        # App-Referenz setzen
        self.provider_screen.set_app(self)
        self.category_screen.set_app(self)
        self.channel_list_screen.set_app(self)
        self.video_screen.set_app(self)
        self.settings_screen.set_app(self)

        # Screens hinzufuegen
        self.sm.add_widget(self.provider_screen)
        self.sm.add_widget(self.category_screen)
        self.sm.add_widget(self.channel_list_screen)
        self.sm.add_widget(self.video_screen)
        self.sm.add_widget(self.settings_screen)

        # Background color setzen
        with self.sm.canvas.before:
            Color(*BG_DARK)
            Rectangle(pos=self.sm.pos, size=self.sm.size)
        self.sm.bind(pos=self._update_bg, size=self._update_bg)

        # Window Background
        Window.clearcolor = BG_DARK

        # Check fuer gespeicherten Provider -> auto-connect
        self._check_saved_provider()

        return self.sm

    def _update_bg(self, *args):
        """Aktualisiert den Hintergrund des ScreenManagers."""
        self.sm.canvas.before.clear()
        with self.sm.canvas.before:
            Color(*BG_DARK)
            Rectangle(pos=self.sm.pos, size=self.sm.size)

    def _check_saved_provider(self):
        """Prueft, ob ein gespeicherter Provider existiert und verbindet automatisch."""
        if not self.config:
            return

        last_provider_name = self.config.get_last_provider()
        if not last_provider_name:
            return

        provider = self.config.get_provider_by_name(last_provider_name)
        if not provider:
            return

        p_type = provider.get("type", "xtream")

        if p_type == "xtream":
            server = provider.get("server_url", "")
            username = provider.get("username", "")
            password = provider.get("password", "")

            if server and username and password:
                # Im Hintergrund verbinden
                from kivy.clock import Clock
                Clock.schedule_once(
                    lambda dt: self._auto_connect_xtream(server, username, password, last_provider_name),
                    0.5,
                )
        elif p_type == "m3u":
            # M3U: Eintraege neu laden
            url = provider.get("server_url", "")
            if url:
                from kivy.clock import Clock
                Clock.schedule_once(
                    lambda dt: self._auto_connect_m3u(url, last_provider_name),
                    0.5,
                )

    def _auto_connect_xtream(self, server, username, password, name):
        """Verbindet automatisch mit einem gespeicherten Xtream Provider."""
        try:
            from xtream_client import XtreamClient
            client = XtreamClient(server, username, password)
            client.authenticate()

            self.xtream_client = client
            self.current_provider_name = name

            # Direkt zum CategoryScreen
            self.go_to_category_screen()
        except Exception:
            # Bei Fehler zum Provider Setup
            self.sm.current = "provider_setup"

    def _auto_connect_m3u(self, url, name):
        """Verbindet automatisch mit einem gespeicherten M3U Provider."""
        try:
            from m3u_parser_android import M3UParser
            parser = M3UParser()
            entries = parser.parse_url(url)

            self.m3u_parser = parser
            self.m3u_entries = entries
            self.current_provider_name = name

            self.go_to_category_screen()
        except Exception:
            self.sm.current = "provider_setup"

    # --- Navigation Methods ---

    def go_to_provider_setup(self):
        """Wechselt zum Provider Setup Screen."""
        self.sm.current = "provider_setup"

    def go_to_category_screen(self):
        """Wechselt zum Category Screen und laedt Kategorien."""
        self.sm.current = "category"
        self.category_screen.load_categories()

    def go_to_channel_list(self):
        """Wechselt zur Channel List und laedt Streams."""
        self.sm.current = "channel_list"
        self.channel_list_screen.load_channels()

    def go_to_video_screen(self):
        """Wechselt zum Video Screen und startet Wiedergabe."""
        self.sm.current = "video"
        self.video_screen.load_stream()

    def go_to_settings(self):
        """Wechselt zum Settings Screen."""
        self.sm.current = "settings"

    def on_stop(self):
        """Wird aufgerufen, wenn die App geschlossen wird."""
        # Video Player cleanup
        if hasattr(self, "video_screen") and self.video_screen.video_player:
            self.video_screen.video_player.cleanup()

    def on_pause(self):
        """Android Lifecycle: App wird pausiert."""
        return True

    def on_resume(self):
        """Android Lifecycle: App wird fortgesetzt."""
        pass


# --- Entry Point ---

if __name__ == "__main__":
    app = SMarTrPlayTV()
    app.run()
