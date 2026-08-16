# -*- coding: utf-8 -*-
"""
SMarTrPlay Android TV — D-Pad Navigation Helper
Verwaltet Focus-Traversal zwischen Widgets fuer D-Pad Fernbedienung.
"""

from kivy.uix.widget import Widget
from kivy.uix.behaviors import FocusBehavior
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.core.window import Window
from kivy.metrics import dp

# SMarTr Brand Colors
COLOR_BG_DARK = (0.039, 0.059, 0.118, 1)       # #0A0F1E
COLOR_CYAN = (0.106, 0.945, 0.984, 1)          # #1bf1fb
COLOR_VIOLET = (0.553, 0.486, 0.961, 1)       # #8D7CF6
COLOR_CYAN_RGB = (0.106, 0.945, 0.984)
COLOR_VIOLET_RGB = (0.553, 0.486, 0.961)
COLOR_WHITE = (1, 1, 1, 1)
COLOR_DIM = (0.5, 0.5, 0.6, 1)


class DPadNavigator:
    """
    Verwaltet D-Pad Focus-Traversal zwischen Widgets auf einem Screen.

    Verwendet eine Liste von navigierbaren Widgets (focusable_widgets).
    Der Navigator trackt den aktuellen Focus-Index und navigiert
    mit D-Pad Events (up/down/left/right/enter/back/menu).
    """

    def __init__(self, screen=None):
        """
        Initialisiert den D-Pad Navigator.

        Args:
            screen: Der Screen dem der Navigator zugeordnet ist.
        """
        self.screen = screen
        self.focusable_widgets = []
        self.current_focus_index = 0
        self.back_callback = None
        self.menu_callback = None
        self.enter_callback = None
        self.media_key_callback = None

        # Grid-Layout Support: Anzahl Spalten fuer 2D-Navigation
        self.columns = 1

        # Keyboard Handler Bindung
        self._keyboard = None
        self._keybindings_bound = False

    def register_widget(self, widget):
        """Registriert ein Widget als D-Pad-navigierbar."""
        if widget not in self.focusable_widgets:
            self.focusable_widgets.append(widget)

    def unregister_widget(self, widget):
        """Entfernt ein Widget aus der Navigator-Liste."""
        if widget in self.focusable_widgets:
            self.focusable_widgets.remove(widget)

    def clear_widgets(self):
        """Leert die Widget-Liste."""
        self.focusable_widgets = []
        self.current_focus_index = 0

    def set_columns(self, columns):
        """Setzt die Anzahl Spalten fuer 2D-Navigation (Grid-Layout)."""
        self.columns = max(1, columns)

    def set_focus_index(self, index):
        """Setzt den Focus direkt auf einen Index."""
        if 0 <= index < len(self.focusable_widgets):
            self._remove_focus_highlight(self.current_focus_index)
            self.current_focus_index = index
            self._apply_focus_highlight()

    def auto_focus_first(self):
        """Setzt den Focus automatisch auf das erste Widget."""
        if self.focusable_widgets:
            self.current_focus_index = 0
            self._apply_focus_highlight()

    def focus_next(self):
        """Navigiert zum naechsten Widget (D-Pad down)."""
        if not self.focusable_widgets:
            return
        self._remove_focus_highlight(self.current_focus_index)
        self.current_focus_index = (self.current_focus_index + 1) % len(self.focusable_widgets)
        self._apply_focus_highlight()

    def focus_previous(self):
        """Navigiert zum vorherigen Widget (D-Pad up)."""
        if not self.focusable_widgets:
            return
        self._remove_focus_highlight(self.current_focus_index)
        self.current_focus_index = (self.current_focus_index - 1) % len(self.focusable_widgets)
        self._apply_focus_highlight()

    def focus_next_column(self):
        """Navigiert zur naechsten Spalte (D-Pad right) in Grid-Layouts."""
        if not self.focusable_widgets or self.columns <= 1:
            # Bei 1 Spalte: wie enter behandeln
            self.activate_current()
            return
        self._remove_focus_highlight(self.current_focus_index)
        new_index = self.current_focus_index + 1
        if new_index >= len(self.focusable_widgets):
            new_index = 0
        self.current_focus_index = new_index
        self._apply_focus_highlight()

    def focus_previous_column(self):
        """Navigiert zur vorherigen Spalte (D-Pad left) in Grid-Layouts."""
        if not self.focusable_widgets or self.columns <= 1:
            # Bei 1 Spalte: go back
            if self.back_callback:
                self.back_callback()
            return
        self._remove_focus_highlight(self.current_focus_index)
        new_index = self.current_focus_index - 1
        if new_index < 0:
            new_index = len(self.focusable_widgets) - 1
        self.current_focus_index = new_index
        self._apply_focus_highlight()

    def activate_current(self):
        """Aktiviert das aktuell fokussierte Widget (D-Pad enter)."""
        if not self.focusable_widgets:
            return
        widget = self.focusable_widgets[self.current_focus_index]
        if widget:
            # Button Press simulieren
            if hasattr(widget, "dispatch"):
                widget.dispatch("on_release")
            elif hasattr(widget, "trigger_action"):
                widget.trigger_action()
            # Custom enter callback
            if self.enter_callback:
                self.enter_callback(widget)

    def go_back(self):
        """Go back Aktion (D-Pad back)."""
        if self.back_callback:
            self.back_callback()

    def open_menu(self):
        """Oeffnet Menu/Settings (D-Pad menu)."""
        if self.menu_callback:
            self.menu_callback()

    def handle_media_key(self, action):
        """Behandelt Media Keys (playpause, stop)."""
        if self.media_key_callback:
            self.media_key_callback(action)

    # --- Focus Highlight ---

    def _apply_focus_highlight(self):
        """Wendet den Cyan Focus-Border auf das aktuell fokussierte Widget an."""
        if not self.focusable_widgets:
            return
        idx = self.current_focus_index
        if 0 <= idx < len(self.focusable_widgets):
            widget = self.focusable_widgets[idx]
            if widget is None:
                return
            # Focus highlight via Canvas Instructions
            widget.canvas.after.clear()
            with widget.canvas.after:
                Color(*COLOR_CYAN)
                RoundedRectangle(
                    pos=(widget.x + dp(2), widget.y + dp(2)),
                    size=(widget.width - dp(4), widget.height - dp(4)),
                    radius=[dp(6)],
                )
            # Ensure widget is visible (scroll to it if in scrollview)
            self._scroll_to_widget(widget)

    def _remove_focus_highlight(self, index=None):
        """Entfernt den Focus-Border."""
        if index is None:
            index = self.current_focus_index
        if not self.focusable_widgets or index < 0 or index >= len(self.focusable_widgets):
            return
        widget = self.focusable_widgets[index]
        if widget is not None:
            widget.canvas.after.clear()

    def _scroll_to_widget(self, widget):
        """Scrollt zum Widget, falls es in einem ScrollView liegt."""
        parent = widget.parent
        while parent:
            if parent.__class__.__name__ == "ScrollView":
                # Scroll-to logic: ensure widget is visible
                try:
                    scroll_y = 1.0 - (
                        (widget.y - parent.y) / (
                            parent.children[0].height - parent.height
                        )
                    ) if parent.children and parent.children[0].height > parent.height else 0
                    scroll_y = max(0, min(1, scroll_y))
                    parent.scroll_y = scroll_y
                except Exception:
                    pass
                break
            parent = parent.parent

    # --- Keyboard Handler ---

    def bind_keyboard(self, window=None):
        """Bindet Keyboard-Events an das Window fuer D-Pad Navigation."""
        if window is None:
            window = Window
        self._keyboard = window
        if not self._keybindings_bound:
            window.bind(
                on_keyboard=self._keyboard_handler
            )
            self._keybindings_bound = True

    def unbind_keyboard(self, window=None):
        """Entfernt Keyboard-Bindings."""
        if window is None:
            window = Window
        if self._keybindings_bound and self._keyboard:
            window.unbind(
                on_keyboard=self._keyboard_handler
            )
            self._keybindings_bound = False

    def _keyboard_handler(self, window, keycode=None, scancode=None, key=None, modifier=None, *args):
        """
        Mappt Keyboard/Android Key Codes zu Navigation Actions.

        Kivy on_keyboard liefert: (window, keycode1, keycode2, key_str, modifier)
        wobei keycode1 der int code und keycode2 der string name ist.
        """
        # Kivy liefert unterschiedlich je nach Version
        # on_keyboard(window, keycode, scancode, key, modifier) oder
        # on_keyboard(window, key_int, key_str, modifier)
        key_name = ""
        key_code = -1

        if args:
            # Kivy Standard: (window, key_int, key_str, modifier)
            if len(args) >= 2:
                key_code = args[0] if isinstance(args[0], int) else -1
                key_name = args[1] if isinstance(args[1], str) else ""
            elif len(args) >= 1 and isinstance(args[0], (int, str)):
                if isinstance(args[0], int):
                    key_code = args[0]
                else:
                    key_name = args[0]

        # Fallback: nutze keycode/scancode/key Parameter
        if key_code == -1 and keycode is not None:
            if isinstance(keycode, int):
                key_code = keycode
            elif isinstance(keycode, str):
                key_name = keycode
        if not key_name and scancode is not None and isinstance(scancode, str):
            key_name = scancode
        if not key_name and key is not None and isinstance(key, str):
            key_name = key

        # Normalisiere key_name
        if key_name:
            key_name = key_name.lower()

        # --- Key Mapping ---

        # D-Pad Up
        if key_name in ("up", "arrowup") or key_code in (17, 268):
            self.focus_previous()
            return True

        # D-Pad Down
        elif key_name in ("down", "arrowdown") or key_code in (18, 269):
            self.focus_next()
            return True

        # D-Pad Right
        elif key_name in ("right", "arrowright") or key_code in (19, 270):
            self.focus_next_column()
            return True

        # D-Pad Left
        elif key_name in ("left", "arrowleft") or key_code in (16, 271):
            self.focus_previous_column()
            return True

        # D-Pad Center / Enter
        elif key_name in ("enter", "return", "numpadenter", "space") or key_code in (13, 271, 32):
            self.activate_current()
            return True

        # Back / Escape
        elif key_name in ("escape", "backspace", "back") or key_code in (27, 8):
            self.go_back()
            return True

        # Menu Key
        elif key_name in ("menu", "m") or key_code in (82, 109):
            self.open_menu()
            return True

        # Media Play/Pause
        elif key_name in ("playpause", "play", "pause", "mediaplay", "mediapause") or key_code in (85, 135):
            self.handle_media_key("playpause")
            return True

        # Media Stop
        elif key_name in ("stop", "mediastop") or key_code in (86, 136):
            self.handle_media_key("stop")
            return True

        return False


# --- TVButton: Button mit Auto-Registrierung beim DPadNavigator ---

from kivy.uix.button import Button
from kivy.uix.label import Label


class TVButton(Button):
    """Grosser Button fuer TV-Bedienung mit D-Pad Support."""

    def __init__(self, navigator=None, **kwargs):
        """
        Args:
            navigator: DPadNavigator fuer Auto-Registrierung.
        """
        # Default TV-Button Groesse
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("width", dp(400))
        kwargs.setdefault("height", dp(60))
        kwargs.setdefault("font_size", dp(18))
        kwargs.setdefault("color", COLOR_WHITE)
        kwargs.setdefault("bold", True)

        # SMarTr Brand Styling
        bg_color = kwargs.pop("bg_color", (0.08, 0.12, 0.22, 1))
        self._bg_color = bg_color

        super().__init__(**kwargs)

        self.navigator = navigator
        if navigator:
            navigator.register_widget(self)

        # Background zeichnen
        self._draw_background()
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _draw_background(self):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._bg_color)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(8)],
            )

    def _update_canvas(self, *args):
        self._draw_background()


class TVLabel(Label):
    """Label im SMarTr Brand Design."""

    def __init__(self, **kwargs):
        kwargs.setdefault("color", COLOR_WHITE)
        kwargs.setdefault("font_size", dp(18))
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(40))
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("padding", (dp(20), 0))
        super().__init__(**kwargs)
