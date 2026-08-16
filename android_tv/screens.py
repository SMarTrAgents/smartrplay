# -*- coding: utf-8 -*-
"""
SMarTrPlay Android TV — Screens
Alle Screen-Klassen fuer die Kivy Android TV App.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder

from dpad_nav import DPadNavigator, TVButton, TVLabel, COLOR_BG_DARK, COLOR_CYAN, COLOR_VIOLET, COLOR_WHITE, COLOR_DIM
from xtream_client import XtreamClient
from m3u_parser_android import M3UParser
from config_android import ConfigManager
from video_player import VideoPlayer


# --- Brand Colors as Kivy Tuples ---
BG_DARK = (0.039, 0.059, 0.118, 1)
BG_CARD = (0.07, 0.10, 0.18, 1)
BG_BUTTON = (0.08, 0.12, 0.22, 1)
BG_BUTTON_HOVER = (0.12, 0.16, 0.28, 1)
ACCENT_CYAN = (0.106, 0.945, 0.984, 1)
ACCENT_VIOLET = (0.553, 0.486, 0.961, 1)
TEXT_WHITE = (1, 1, 1, 1)
TEXT_DIM = (0.5, 0.5, 0.6, 1)
TEXT_CYAN = (0.106, 0.945, 0.984, 1)
ERROR_RED = (0.9, 0.2, 0.2, 1)
SUCCESS_GREEN = (0.2, 0.8, 0.3, 1)


class BaseScreen(Screen):
    """Basis-Screen mit SMarTr Brand Design und D-Pad Navigation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.navigator = DPadNavigator(screen=self)
        self.app = None
        self.config = None

        # Background
        with self.canvas.before:
            Color(*BG_DARK)
            Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Main Layout
        self.main_layout = BoxLayout(orientation="vertical", padding=dp(40), spacing=dp(20))
        self.add_widget(self.main_layout)

        # Bind keyboard on enter
        self.bind(on_enter=self._on_screen_enter)
        self.bind(on_leave=self._on_screen_leave)

    def _update_bg(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*BG_DARK)
            Rectangle(pos=self.pos, size=self.size)

    def _on_screen_enter(self, *args):
        """Wird aufgerufen, wenn der Screen aktiv wird."""
        self.navigator.bind_keyboard()
        self.navigator.auto_focus_first()

    def _on_screen_leave(self, *args):
        """Wird aufgerufen, wenn der Screen verlassen wird."""
        self.navigator.unbind_keyboard()

    def set_app(self, app):
        """Setzt die App-Referenz fuer Screen-Wechsel."""
        self.app = app
        self.config = app.config if app else None

    def show_message(self, title, message, color=TEXT_WHITE):
        """Zeigt eine Popup-Nachricht."""
        content = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(20))
        lbl = Label(
            text=message,
            color=color,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(80),
            halign="center",
            valign="middle",
        )
        lbl.bind(width=lambda s, w: s.setter("text_size")(s, (w, None)))
        content.add_widget(lbl)

        btn = TVButton(
            text="OK",
            navigator=None,
            size_hint=(None, None),
            width=dp(200),
            height=dp(60),
            pos_hint={"center_x": 0.5},
            bg_color=BG_BUTTON,
        )
        content.add_widget(btn)

        popup = Popup(
            title=title,
            title_color=ACCENT_CYAN[:3],
            title_size=dp(20),
            content=content,
            size_hint=(0.7, 0.4),
            auto_dismiss=True,
            background_color=BG_DARK,
            separator_color=ACCENT_CYAN,
        )
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def show_loading(self, message="Laden..."):
        """Zeigt ein Loading-Popup."""
        content = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(20))
        lbl = Label(text=message, color=TEXT_WHITE, font_size=dp(18))
        content.add_widget(lbl)
        pb = ProgressBar(size_hint_y=None, height=dp(10))
        content.add_widget(pb)

        self._loading_popup = Popup(
            title="Bitte warten",
            title_color=ACCENT_CYAN[:3],
            title_size=dp(20),
            content=content,
            size_hint=(0.6, 0.3),
            auto_dismiss=False,
            background_color=BG_DARK,
            separator_color=ACCENT_CYAN,
        )
        self._loading_popup.open()

    def dismiss_loading(self):
        """Schliesst das Loading-Popup."""
        if hasattr(self, "_loading_popup"):
            self._loading_popup.dismiss()
            del self._loading_popup

    def build_content(self):
        """Wird von Subklassen ueberschrieben, um den Screen-Inhalt zu bauen."""
        pass

    def refresh_nav(self):
        """Aktualisiert den Navigator nach Widget-Aenderungen."""
        self.navigator.auto_focus_first()


class ProviderSetupScreen(BaseScreen):
    """Screen zur Provider-Einrichtung (Xtream/M3U)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "provider_setup"
        self.build_content()

    def build_content(self):
        self.navigator.clear_widgets()
        self.main_layout.clear_widgets()

        # Header
        header = TVLabel(
            text="SMarTrPlay — Provider einrichten",
            font_size=dp(28),
            color=ACCENT_CYAN,
            size_hint_y=None,
            height=dp(60),
            bold=True,
        )
        self.main_layout.add_widget(header)

        # Spacer
        self.main_layout.add_widget(Widget(size_hint_y=None, height=dp(20)))

        # Form Fields
        form = BoxLayout(orientation="vertical", spacing=dp(15), size_hint_y=None)
        form.height = dp(400)

        # Server URL
        lbl_server = TVLabel(text="Server URL:", font_size=dp(18), color=TEXT_DIM, height=dp(30))
        form.add_widget(lbl_server)
        self.input_server = TextInput(
            hint_text="http://dein-server.com:8080",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(60),
            background_color=BG_CARD,
            foreground_color=TEXT_WHITE,
            cursor_color=ACCENT_CYAN,
            padding=(dp(15), dp(15)),
        )
        form.add_widget(self.input_server)
        self.navigator.register_widget(self.input_server)

        # Username
        lbl_user = TVLabel(text="Benutzername:", font_size=dp(18), color=TEXT_DIM, height=dp(30))
        form.add_widget(lbl_user)
        self.input_username = TextInput(
            hint_text="Benutzername",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(60),
            background_color=BG_CARD,
            foreground_color=TEXT_WHITE,
            cursor_color=ACCENT_CYAN,
            padding=(dp(15), dp(15)),
        )
        form.add_widget(self.input_username)
        self.navigator.register_widget(self.input_username)

        # Password
        lbl_pass = TVLabel(text="Passwort:", font_size=dp(18), color=TEXT_DIM, height=dp(30))
        form.add_widget(lbl_pass)
        self.input_password = TextInput(
            hint_text="Passwort",
            password=True,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(60),
            background_color=BG_CARD,
            foreground_color=TEXT_WHITE,
            cursor_color=ACCENT_CYAN,
            padding=(dp(15), dp(15)),
        )
        form.add_widget(self.input_password)
        self.navigator.register_widget(self.input_password)

        # Provider Name
        lbl_name = TVLabel(text="Provider Name:", font_size=dp(18), color=TEXT_DIM, height=dp(30))
        form.add_widget(lbl_name)
        self.input_name = TextInput(
            hint_text="z.B. Mein Provider",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(60),
            background_color=BG_CARD,
            foreground_color=TEXT_WHITE,
            cursor_color=ACCENT_CYAN,
            padding=(dp(15), dp(15)),
        )
        form.add_widget(self.input_name)
        self.navigator.register_widget(self.input_name)

        self.main_layout.add_widget(form)

        # Spacer
        self.main_layout.add_widget(Widget(size_hint_y=None, height=dp(20)))

        # Buttons
        btn_layout = BoxLayout(orientation="horizontal", spacing=dp(20), size_hint_y=None, height=dp(70))

        self.btn_connect = TVButton(
            text="Verbinden",
            navigator=self.navigator,
            width=dp(300),
            height=dp(60),
            bg_color=(0.08, 0.30, 0.25, 1),
        )
        self.btn_connect.bind(on_release=self.on_connect)
        btn_layout.add_widget(self.btn_connect)

        self.btn_m3u = TVButton(
            text="M3U Import (URL)",
            navigator=self.navigator,
            width=dp(300),
            height=dp(60),
            bg_color=(0.12, 0.10, 0.30, 1),
        )
        self.btn_m3u.bind(on_release=self.on_m3u_import)
        btn_layout.add_widget(self.btn_m3u)

        self.main_layout.add_widget(btn_layout)

        # Spacer / Status
        self.status_label = Label(
            text="",
            color=TEXT_DIM,
            font_size=dp(16),
            size_hint_y=None,
            height=dp(40),
        )
        self.main_layout.add_widget(self.status_label)

        # Back callback
        self.navigator.back_callback = lambda: self.app.stop()

    def on_connect(self, *args):
        """Verbindet sich mit dem Xtream-Server."""
        server = self.input_server.text.strip()
        username = self.input_username.text.strip()
        password = self.input_password.text.strip()
        name = self.input_name.text.strip() or "Provider"

        if not server or not username or not password:
            self.status_label.color = ERROR_RED
            self.status_label.text = "Bitte alle Felder ausfuellen!"
            return

        self.status_label.color = TEXT_CYAN
        self.status_label.text = "Verbinde..."
        self.show_loading("Verbinde mit Server...")

        # Async Verbindung in naechstem Frame
        Clock.schedule_once(lambda dt: self._do_connect(server, username, password, name), 0.5)

    def _do_connect(self, server, username, password, name):
        """Fuehrt die Verbindung asynchron aus."""
        try:
            client = XtreamClient(server, username, password)
            user_info = client.authenticate()

            # Provider speichern
            if self.config:
                self.config.add_provider(name, server, username, password, "xtream")
                self.config.set_last_provider(name)

            # Im App speichern
            if self.app:
                self.app.xtream_client = client
                self.app.current_provider_name = name

            self.dismiss_loading()
            self.status_label.color = SUCCESS_GREEN
            self.status_label.text = "Erfolgreich verbunden!"

            # Zum CategoryScreen wechseln
            if self.app:
                self.app.go_to_category_screen()

        except Exception as e:
            self.dismiss_loading()
            self.status_label.color = ERROR_RED
            self.status_label.text = f"Fehler: {e}"

    def on_m3u_import(self, *args):
        """Oeffnet M3U URL Input Dialog."""
        content = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(15))
        lbl = Label(text="M3U URL eingeben:", color=TEXT_WHITE, font_size=dp(18))
        content.add_widget(lbl)
        url_input = TextInput(
            hint_text="http://dein-server.com/playlist.m3u",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(60),
            background_color=BG_CARD,
            foreground_color=TEXT_WHITE,
        )
        content.add_widget(url_input)
        name_input = TextInput(
            hint_text="Provider Name",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(60),
            background_color=BG_CARD,
            foreground_color=TEXT_WHITE,
        )
        content.add_widget(name_input)

        btn_layout = BoxLayout(orientation="horizontal", spacing=dp(15), size_hint_y=None, height=dp(60))
        btn_ok = TVButton(text="Import", navigator=None, width=dp(200), height=dp(60), bg_color=(0.08, 0.30, 0.25, 1))
        btn_cancel = TVButton(text="Abbrechen", navigator=None, width=dp(200), height=dp(60), bg_color=BG_BUTTON)
        btn_layout.add_widget(btn_ok)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)

        popup = Popup(
            title="M3U Import",
            title_color=ACCENT_CYAN[:3],
            title_size=dp(20),
            content=content,
            size_hint=(0.8, 0.5),
            auto_dismiss=True,
            background_color=BG_DARK,
            separator_color=ACCENT_CYAN,
        )
        btn_cancel.bind(on_release=popup.dismiss)
        btn_ok.bind(
            on_release=lambda *a: self._do_m3u_import(
                url_input.text.strip(), name_input.text.strip() or "M3U Provider", popup
            )
        )
        popup.open()

    def _do_m3u_import(self, url, name, popup):
        """Importiert M3U Playlist."""
        popup.dismiss()
        if not url:
            self.status_label.color = ERROR_RED
            self.status_label.text = "Keine URL eingegeben!"
            return

        self.status_label.color = TEXT_CYAN
        self.status_label.text = "Importiere M3U..."
        self.show_loading("Importiere M3U Playlist...")

        Clock.schedule_once(lambda dt: self._parse_m3u(url, name), 0.5)

    def _parse_m3u(self, url, name):
        """Parst M3U im Hintergrund."""
        try:
            parser = M3UParser()
            entries = parser.parse_url(url)

            if not entries:
                raise Exception("M3U Playlist ist leer oder ungueltig")

            # Provider speichern
            if self.config:
                self.config.add_provider(name, url, "", "", "m3u")
                self.config.set_last_provider(name)

            if self.app:
                self.app.m3u_entries = entries
                self.app.m3u_parser = parser
                self.app.current_provider_name = name

            self.dismiss_loading()
            self.status_label.color = SUCCESS_GREEN
            self.status_label.text = f"{len(entries)} Eintraege importiert!"

            if self.app:
                self.app.go_to_category_screen()

        except Exception as e:
            self.dismiss_loading()
            self.status_label.color = ERROR_RED
            self.status_label.text = f"Fehler: {e}"


class CategoryScreen(BaseScreen):
    """Screen mit Kategorien-Liste."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "category"
        self.categories = []
        self.category_buttons = []
        self.build_content()

    def build_content(self):
        self.navigator.clear_widgets()
        self.main_layout.clear_widgets()
        self.category_buttons = []

        # Header
        header_text = "SMarTrPlay"
        if self.app and hasattr(self.app, "current_provider_name"):
            header_text += f" — {self.app.current_provider_name}"

        header = TVLabel(
            text=header_text,
            font_size=dp(28),
            color=ACCENT_CYAN,
            size_hint_y=None,
            height=dp(60),
            bold=True,
        )
        self.main_layout.add_widget(header)

        # Subheader
        subheader = TVLabel(
            text="Kategorie waehlen",
            font_size=dp(20),
            color=TEXT_DIM,
            size_hint_y=None,
            height=dp(40),
        )
        self.main_layout.add_widget(subheader)

        # Spacer
        self.main_layout.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # Category List (Scrollable)
        scroll = ScrollView(size_hint=(1, 1))
        self.category_list = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.category_list.bind(
            minimum_height=self.category_list.setter("height")
        )
        scroll.add_widget(self.category_list)
        self.main_layout.add_widget(scroll)

        # Loading label
        self.loading_label = Label(
            text="Lade Kategorien...",
            color=TEXT_DIM,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(40),
        )
        self.category_list.add_widget(self.loading_label)

        # Footer hints
        footer = TVLabel(
            text="D-Pad: Up/Down = Navigieren | Enter = Auswaehlen | Left = Zurueck",
            font_size=dp(14),
            color=TEXT_DIM,
            size_hint_y=None,
            height=dp(30),
        )
        self.main_layout.add_widget(footer)

        # Back callback
        self.navigator.back_callback = lambda: self.app.go_to_provider_setup()
        # Menu callback
        self.navigator.menu_callback = lambda: self.app.go_to_settings()

    def load_categories(self):
        """Laedt Kategorien vom Provider."""
        self.loading_label.text = "Lade Kategorien..."

        if self.app and self.app.m3u_entries:
            # M3U Mode
            Clock.schedule_once(lambda dt: self._load_m3u_categories(), 0.3)
        elif self.app and self.app.xtream_client:
            # Xtream Mode
            Clock.schedule_once(lambda dt: self._load_xtream_categories(), 0.3)
        else:
            self.loading_label.text = "Kein Provider verbunden!"
            self.loading_label.color = ERROR_RED

    def _load_xtream_categories(self):
        """Laedt Xtream Kategorien."""
        try:
            client = self.app.xtream_client
            categories = client.get_all_categories()
            self.categories = categories
            self._populate_category_list()
        except Exception as e:
            self.loading_label.text = f"Fehler: {e}"
            self.loading_label.color = ERROR_RED

    def _load_m3u_categories(self):
        """Laedt M3U Kategorien."""
        try:
            parser = self.app.m3u_parser
            entries = self.app.m3u_entries
            groups = parser.group_by_category(entries)

            self.categories = []
            for cat_name, cat_entries in groups.items():
                self.categories.append({
                    "category_id": cat_name,
                    "category_name": cat_name,
                    "type": "m3u",
                    "entries": cat_entries,
                })

            self._populate_category_list()
        except Exception as e:
            self.loading_label.text = f"Fehler: {e}"
            self.loading_label.color = ERROR_RED

    def _populate_category_list(self):
        """Fuellt die Kategorie-Liste mit Buttons."""
        self.category_list.clear_widgets()
        self.navigator.clear_widgets()
        self.category_buttons = []

        if not self.categories:
            self.loading_label = Label(
                text="Keine Kategorien gefunden.",
                color=ERROR_RED,
                font_size=dp(18),
                size_hint_y=None,
                height=dp(50),
            )
            self.category_list.add_widget(self.loading_label)
            return

        for cat in self.categories:
            cat_name = cat.get("category_name", "Unbekannt")
            cat_type = cat.get("type", "")
            cat_id = cat.get("category_id", "")

            # Type Icon
            type_icon = ""
            if cat_type == "live":
                type_icon = "[TV] "
            elif cat_type == "vod":
                type_icon = "[FILM] "
            elif cat_type == "series":
                type_icon = "[SERIE] "
            elif cat_type == "m3u":
                type_icon = "[M3U] "

            btn = TVButton(
                text=f"{type_icon}{cat_name}",
                navigator=self.navigator,
                width=dp(800),
                height=dp(60),
                bg_color=BG_BUTTON,
            )
            btn.cat_data = cat
            btn.bind(on_release=self.on_category_select)
            self.category_buttons.append(btn)
            self.category_list.add_widget(btn)

        # Auto-focus first
        self.navigator.auto_focus_first()

    def on_category_select(self, button):
        """Wird aufgerufen, wenn eine Kategorie ausgewaehlt wird."""
        cat_data = button.cat_data
        if self.app:
            self.app.current_category = cat_data
            self.app.go_to_channel_list()


class ChannelListScreen(BaseScreen):
    """Screen mit Kanal/Film/Serien-Liste."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "channel_list"
        self.channels = []
        self.channel_buttons = []
        self.search_visible = False
        self.build_content()

    def build_content(self):
        self.navigator.clear_widgets()
        self.main_layout.clear_widgets()
        self.channel_buttons = []

        # Header
        header_text = "SMarTrPlay"
        if self.app and self.app.current_category:
            header_text += f" — {self.app.current_category.get('category_name', '')}"

        header = TVLabel(
            text=header_text,
            font_size=dp(24),
            color=ACCENT_CYAN,
            size_hint_y=None,
            height=dp(50),
            bold=True,
        )
        self.main_layout.add_widget(header)

        # Search bar (hidden by default)
        self.search_input = TextInput(
            hint_text="Suchen...",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(0),
            background_color=BG_CARD,
            foreground_color=TEXT_WHITE,
            opacity=0,
        )
        self.search_input.bind(text=self.on_search_text)
        self.main_layout.add_widget(self.search_input)

        # Channel list (scrollable)
        scroll = ScrollView(size_hint=(1, 1))
        self.channel_list = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.channel_list.bind(
            minimum_height=self.channel_list.setter("height")
        )
        scroll.add_widget(self.channel_list)
        self.main_layout.add_widget(scroll)

        # Loading label
        self.loading_label = Label(
            text="Lade Eintraege...",
            color=TEXT_DIM,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(40),
        )
        self.channel_list.add_widget(self.loading_label)

        # Footer hints
        footer = TVLabel(
            text="D-Pad: Up/Down = Navigieren | Enter = Abspielen | Left = Zurueck | Menu = Suchen",
            font_size=dp(14),
            color=TEXT_DIM,
            size_hint_y=None,
            height=dp(30),
        )
        self.main_layout.add_widget(footer)

        # Back callback
        self.navigator.back_callback = lambda: self.app.go_to_category_screen()
        # Menu callback = search toggle
        self.navigator.menu_callback = self.toggle_search

    def load_channels(self):
        """Laedt Kanaele/Filme/Serien fuer die aktuelle Kategorie."""
        self.loading_label.text = "Lade Eintraege..."
        self.loading_label.color = TEXT_DIM

        if not self.app or not self.app.current_category:
            self.loading_label.text = "Keine Kategorie ausgewaehlt!"
            return

        cat = self.app.current_category
        cat_type = cat.get("type", "")
        cat_id = cat.get("category_id", "")

        if cat_type == "m3u":
            # M3U entries direkt aus Kategorie
            self.channels = cat.get("entries", [])
            self._populate_channel_list()
        elif self.app.xtream_client:
            # Xtream API call
            Clock.schedule_once(lambda dt: self._load_xtream_streams(cat_id, cat_type), 0.3)
        else:
            self.loading_label.text = "Kein Provider verbunden!"

    def _load_xtream_streams(self, cat_id, cat_type):
        """Laedt Xtream Streams fuer eine Kategorie."""
        try:
            client = self.app.xtream_client

            if cat_id == "__live__":
                streams = client.get_live_streams()
            elif cat_id == "__vod__":
                streams = client.get_vod_streams()
            elif cat_id == "__series__":
                streams = client.get_series()
            else:
                streams = client.get_streams_by_category(cat_id, cat_type)

            self.channels = streams
            self._populate_channel_list()
        except Exception as e:
            self.loading_label.text = f"Fehler: {e}"
            self.loading_label.color = ERROR_RED

    def _populate_channel_list(self):
        """Fuellt die Kanal-Liste mit Buttons."""
        self.channel_list.clear_widgets()
        self.navigator.clear_widgets()
        self.channel_buttons = []

        if not self.channels:
            self.loading_label = Label(
                text="Keine Eintraege gefunden.",
                color=ERROR_RED,
                font_size=dp(18),
                size_hint_y=None,
                height=dp(50),
            )
            self.channel_list.add_widget(self.loading_label)
            return

        for channel in self.channels:
            name = channel.get("name", "Unbekannt")
            stream_type = channel.get("type", "")

            # Type Icon bestimmen
            if stream_type == "live" or "stream_type" in channel and channel.get("stream_type") == "live":
                icon = "[TV] "
            elif stream_type == "vod" or "stream_type" in channel and channel.get("stream_type") == "movie":
                icon = "[FILM] "
            elif stream_type == "series":
                icon = "[SERIE] "
            else:
                # Xtream detection
                st = channel.get("stream_type", "")
                if st == "live":
                    icon = "[TV] "
                elif st == "movie":
                    icon = "[FILM] "
                else:
                    icon = "[?] "

            btn = TVButton(
                text=f"{icon}{name}",
                navigator=self.navigator,
                width=dp(900),
                height=dp(55),
                bg_color=BG_BUTTON,
            )
            btn.channel_data = channel
            btn.bind(on_release=self.on_channel_select)
            self.channel_buttons.append(btn)
            self.channel_list.add_widget(btn)

        self.navigator.auto_focus_first()

    def on_channel_select(self, button):
        """Wird aufgerufen, wenn ein Kanal/Film/Serie ausgewaehlt wird."""
        channel = button.channel_data
        if self.app:
            self.app.current_channel = channel
            self.app.go_to_video_screen()

    def toggle_search(self, *args):
        """Schaltet die Suchleiste ein/aus."""
        if self.search_input.opacity == 0:
            self.search_input.height = dp(60)
            self.search_input.opacity = 1
            self.search_input.focus = True
            self.search_visible = True
        else:
            self.search_input.height = dp(0)
            self.search_input.opacity = 0
            self.search_input.focus = False
            self.search_input.text = ""
            self.search_visible = False
            self._populate_channel_list()

    def on_search_text(self, instance, value):
        """Filtert die Kanal-Liste nach Suchbegriff."""
        if not self.search_visible or not value:
            return

        query = value.lower().strip()
        filtered = [c for c in self.channels if query in c.get("name", "").lower()]

        # Temporaer channels setzen und neu aufbauen
        original_channels = self.channels
        self.channels = filtered
        self._populate_channel_list()
        self.channels = original_channels


class VideoScreen(BaseScreen):
    """Screen fuer Video-Wiedergabe."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "video"
        self.video_player = None
        self.stream_url = None
        self.current_channel_data = None
        self.build_content()

    def build_content(self):
        self.navigator.clear_widgets()
        self.main_layout.clear_widgets()

        # Header
        header = TVLabel(
            text="SMarTrPlay — Wiedergabe",
            font_size=dp(24),
            color=ACCENT_CYAN,
            size_hint_y=None,
            height=dp(50),
            bold=True,
        )
        self.main_layout.add_widget(header)

        # Title label
        self.title_label = TVLabel(
            text="Kein Stream geladen",
            font_size=dp(22),
            color=TEXT_WHITE,
            size_hint_y=None,
            height=dp(50),
        )
        self.main_layout.add_widget(self.title_label)

        # Status label
        self.status_label = Label(
            text="",
            color=TEXT_DIM,
            font_size=dp(16),
            size_hint_y=None,
            height=dp(30),
        )
        self.main_layout.add_widget(self.status_label)

        # Video area placeholder
        self.video_area = Widget(size_hint=(1, 1))
        self.main_layout.add_widget(self.video_area)

        # Spacer
        self.main_layout.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # Control buttons
        controls = BoxLayout(orientation="horizontal", spacing=dp(20), size_hint_y=None, height=dp(70))

        self.btn_play = TVButton(
            text="Play/Pause",
            navigator=self.navigator,
            width=dp(250),
            height=dp(60),
            bg_color=(0.08, 0.30, 0.25, 1),
        )
        self.btn_play.bind(on_release=self.on_play_pause)
        controls.add_widget(self.btn_play)

        self.btn_stop = TVButton(
            text="Stop",
            navigator=self.navigator,
            width=dp(250),
            height=dp(60),
            bg_color=(0.30, 0.08, 0.08, 1),
        )
        self.btn_stop.bind(on_release=self.on_stop)
        controls.add_widget(self.btn_stop)

        self.btn_back = TVButton(
            text="Zurueck",
            navigator=self.navigator,
            width=dp(250),
            height=dp(60),
            bg_color=BG_BUTTON,
        )
        self.btn_back.bind(on_release=self.on_back)
        controls.add_widget(self.btn_back)

        self.main_layout.add_widget(controls)

        # Seek hint
        seek_hint = TVLabel(
            text="D-Pad: Left/Right = -10s/+10s | Play/Pause = Wiedergabe | Back = Zurueck",
            font_size=dp(14),
            color=TEXT_DIM,
            size_hint_y=None,
            height=dp(30),
        )
        self.main_layout.add_widget(seek_hint)

        # Back callback
        self.navigator.back_callback = self.on_back
        # Media keys
        self.navigator.media_key_callback = self.handle_media_key
        # Enter = play/pause
        self.navigator.enter_callback = lambda w: self.on_play_pause()

    def load_stream(self):
        """Laedt den aktuellen Stream."""
        if not self.app or not self.app.current_channel:
            self.title_label.text = "Kein Stream ausgewaehlt"
            return

        channel = self.app.current_channel
        self.current_channel_data = channel
        name = channel.get("name", "Unbekannt")
        self.title_label.text = name

        # Stream URL bestimmen
        stream_url = None

        if "url" in channel:
            # M3U entry
            stream_url = channel["url"]
        elif self.app.xtream_client:
            # Xtream stream
            stream_id = channel.get("stream_id", "")
            stream_type = channel.get("type", channel.get("stream_type", "live"))
            container_ext = channel.get("container_extension", "ts")

            if stream_type == "movie":
                stream_type = "vod"

            try:
                stream_url = self.app.xtream_client.get_stream_url(
                    stream_id, stream_type, container_ext
                )
            except Exception as e:
                self.status_label.color = ERROR_RED
                self.status_label.text = f"URL Fehler: {e}"
                return

        if not stream_url:
            self.status_label.color = ERROR_RED
            self.status_label.text = "Keine Stream-URL gefunden!"
            return

        self.stream_url = stream_url
        self.status_label.color = TEXT_CYAN
        self.status_label.text = f"Stream: {stream_url[:60]}..."

        # Video Player initialisieren
        player_mode = "intent"
        if self.config:
            settings = self.config.get_settings()
            player_mode = settings.get("default_player", "intent")

        self.video_player = VideoPlayer(mode=player_mode)

        # Stream abspielen
        try:
            self.video_player.play(stream_url, title=name)
            self.status_label.color = SUCCESS_GREEN
            self.status_label.text = "Wiedergabe gestartet"
        except Exception as e:
            self.status_label.color = ERROR_RED
            self.status_label.text = f"Wiedergabe-Fehler: {e}"

    def on_play_pause(self, *args):
        """Play/Pause Toggle."""
        if self.video_player:
            self.video_player.toggle_play_pause()
            if self.video_player.is_paused:
                self.status_label.color = TEXT_CYAN
                self.status_label.text = "Pausiert"
            else:
                self.status_label.color = SUCCESS_GREEN
                self.status_label.text = "Wiedergabe"

    def on_stop(self, *args):
        """Stoppt Wiedergabe."""
        if self.video_player:
            self.video_player.stop()
            self.status_label.color = TEXT_DIM
            self.status_label.text = "Gestoppt"

    def on_back(self, *args):
        """Zurueck zur Kanal-Liste."""
        if self.video_player:
            self.video_player.stop()
        if self.app:
            self.app.go_to_channel_list()

    def handle_media_key(self, action):
        """Behandelt Media Keys vom D-Pad."""
        if action == "playpause":
            self.on_play_pause()
        elif action == "stop":
            self.on_stop()

    def _on_screen_leave(self, *args):
        """Cleanup beim Verlassen."""
        super()._on_screen_leave(*args)
        if self.video_player:
            self.video_player.cleanup()


class SettingsScreen(BaseScreen):
    """Screen fuer Einstellungen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "settings"
        self.provider_buttons = []
        self.build_content()

    def build_content(self):
        self.navigator.clear_widgets()
        self.main_layout.clear_widgets()
        self.provider_buttons = []

        # Header
        header = TVLabel(
            text="SMarTrPlay — Einstellungen",
            font_size=dp(28),
            color=ACCENT_CYAN,
            size_hint_y=None,
            height=dp(60),
            bold=True,
        )
        self.main_layout.add_widget(header)

        # Spacer
        self.main_layout.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # Scrollable content
        scroll = ScrollView(size_hint=(1, 1))
        content = BoxLayout(orientation="vertical", spacing=dp(15), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # --- Default Player Section ---
        lbl_player = TVLabel(
            text="Default Player:",
            font_size=dp(20),
            color=ACCENT_VIOLET,
            height=dp(40),
        )
        content.add_widget(lbl_player)

        self.btn_player_intent = TVButton(
            text="Externer Player (Intent / VLC / MX Player)",
            navigator=self.navigator,
            width=dp(800),
            height=dp(60),
            bg_color=BG_BUTTON,
        )
        self.btn_player_intent.bind(on_release=lambda *a: self.set_player("intent"))
        content.add_widget(self.btn_player_intent)

        self.btn_player_ffp = TVButton(
            text="Integrierter Player (ffpyplayer)",
            navigator=self.navigator,
            width=dp(800),
            height=dp(60),
            bg_color=BG_BUTTON,
        )
        self.btn_player_ffp.bind(on_release=lambda *a: self.set_player("ffpyplayer"))
        content.add_widget(self.btn_player_ffp)

        # --- Provider Section ---
        content.add_widget(Widget(size_hint_y=None, height=dp(20)))
        lbl_providers = TVLabel(
            text="Provider verwalten:",
            font_size=dp(20),
            color=ACCENT_VIOLET,
            height=dp(40),
        )
        content.add_widget(lbl_providers)

        # Provider Liste
        if self.config:
            providers = self.config.get_providers()
            if providers:
                for p in providers:
                    p_name = p.get("name", "Unbekannt")
                    p_type = p.get("type", "xtream")
                    btn = TVButton(
                        text=f"{p_name} ({p_type})  [Loeschen]",
                        navigator=self.navigator,
                        width=dp(800),
                        height=dp(60),
                        bg_color=(0.30, 0.08, 0.08, 1),
                    )
                    btn.provider_name = p_name
                    btn.bind(on_release=self.on_delete_provider)
                    self.provider_buttons.append(btn)
                    content.add_widget(btn)
            else:
                no_providers = TVLabel(
                    text="Keine Provider gespeichert.",
                    color=TEXT_DIM,
                    height=dp(40),
                )
                content.add_widget(no_providers)

        # Add new provider button
        btn_add = TVButton(
            text="+ Neuen Provider hinzufuegen",
            navigator=self.navigator,
            width=dp(800),
            height=dp(60),
            bg_color=(0.08, 0.30, 0.25, 1),
        )
        btn_add.bind(on_release=lambda *a: self.app.go_to_provider_setup())
        content.add_widget(btn_add)

        # --- Cache Section ---
        content.add_widget(Widget(size_hint_y=None, height=dp(20)))
        lbl_cache = TVLabel(
            text="Cache:",
            font_size=dp(20),
            color=ACCENT_VIOLET,
            height=dp(40),
        )
        content.add_widget(lbl_cache)

        self.btn_cache_toggle = TVButton(
            text="Cache: An/Aus",
            navigator=self.navigator,
            width=dp(800),
            height=dp(60),
            bg_color=BG_BUTTON,
        )
        self.btn_cache_toggle.bind(on_release=self.on_toggle_cache)
        content.add_widget(self.btn_cache_toggle)

        self.btn_cache_clear = TVButton(
            text="Cache loeschen",
            navigator=self.navigator,
            width=dp(800),
            height=dp(60),
            bg_color=(0.30, 0.16, 0.08, 1),
        )
        self.btn_cache_clear.bind(on_release=self.on_clear_cache)
        content.add_widget(self.btn_cache_clear)

        # --- About Section ---
        content.add_widget(Widget(size_hint_y=None, height=dp(20)))
        lbl_about = TVLabel(
            text="Ueber:",
            font_size=dp(20),
            color=ACCENT_VIOLET,
            height=dp(40),
        )
        content.add_widget(lbl_about)

        about_label = Label(
            text="SMarTrPlay v1.0\nsmartragents.ai\nAndroid TV Edition",
            color=TEXT_DIM,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(80),
            halign="center",
        )
        about_label.bind(width=lambda s, w: s.setter("text_size")(s, (w, None)))
        content.add_widget(about_label)

        scroll.add_widget(content)
        self.main_layout.add_widget(scroll)

        # Footer
        footer = TVLabel(
            text="D-Pad: Up/Down = Navigieren | Enter = Auswaehlen | Back = Zurueck",
            font_size=dp(14),
            color=TEXT_DIM,
            height=dp(30),
        )
        self.main_layout.add_widget(footer)

        # Back callback
        self.navigator.back_callback = lambda: self.app.go_to_category_screen()

    def set_player(self, mode):
        """Setzt den Default Player."""
        if self.config:
            self.config.set_setting("default_player", mode)
            self.show_message("Einstellung", f"Default Player: {mode}", color=SUCCESS_GREEN)

    def on_delete_provider(self, button):
        """Loescht einen Provider."""
        name = button.provider_name
        if self.config:
            self.config.delete_provider(name)
            self.show_message("Provider", f"'{name}' wurde entfernt.", color=SUCCESS_GREEN)
            self.build_content()
            self.navigator.auto_focus_first()

    def on_toggle_cache(self, *args):
        """Schaltet Cache an/aus."""
        if self.config:
            settings = self.config.get_settings()
            current = settings.get("cache_enabled", True)
            self.config.set_setting("cache_enabled", not current)
            state = "An" if not current else "Aus"
            self.show_message("Cache", f"Cache: {state}", color=SUCCESS_GREEN)

    def on_clear_cache(self, *args):
        """Loescht den Cache."""
        self.show_message("Cache", "Cache wurde geloescht.", color=SUCCESS_GREEN)

    def _on_screen_enter(self, *args):
        """Rebuild content on enter to refresh provider list."""
        self.build_content()
        super()._on_screen_enter(*args)
