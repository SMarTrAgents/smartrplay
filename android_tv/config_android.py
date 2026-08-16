# -*- coding: utf-8 -*-
"""
SMarTrPlay Android TV — Config Manager
Speichert Provider und Settings als JSON unter app user_data_dir.
Kein SQLite auf Android noetig.
"""

import os
import json


class ConfigManager:
    """Verwaltet Provider-Konfiguration und App-Settings als JSON."""

    DEFAULT_SETTINGS = {
        "default_player": "intent",
        "cache_enabled": True,
        "cache_duration_hours": 24,
        "volume": 80,
        "subtitle_enabled": False,
    }

    def __init__(self, data_dir=None):
        """
        Initialisiert den ConfigManager.

        Args:
            data_dir: Verzeichnis fuer Konfigurationsdateien.
                      Auf Android: App user_data_dir.
                      Auf Desktop: Fallback unter ~/.smartrplay/
        """
        if data_dir is None:
            # Fallback fuer Desktop-Tests
            home = os.path.expanduser("~")
            data_dir = os.path.join(home, ".smartrplay")

        self.data_dir = data_dir
        self.providers_file = os.path.join(data_dir, "providers.json")
        self.settings_file = os.path.join(data_dir, "settings.json")
        self.last_provider_file = os.path.join(data_dir, "last_provider.json")

        self._ensure_dir()

    def _ensure_dir(self):
        """Stellt sicher, dass das Datenverzeichnis existiert."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    # --- Provider Management ---

    def get_providers(self):
        """
        Gibt alle gespeicherten Provider zurueck.

        Returns:
            list: Liste von Provider-Dicts.
        """
        if not os.path.exists(self.providers_file):
            return []
        try:
            with open(self.providers_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except (json.JSONDecodeError, IOError):
            return []

    def add_provider(self, name, server_url, username, password, provider_type="xtream"):
        """
        Fuegt einen neuen Provider hinzu oder aktualisiert einen bestehenden.

        Args:
            name: Anzeigename des Providers.
            server_url: URL des Xtream-Servers.
            username: Xtream Benutzername.
            password: Xtream Passwort.
            provider_type: 'xtream' oder 'm3u'.

        Returns:
            dict: Der hinzugefuegte Provider.
        """
        providers = self.get_providers()

        provider = {
            "name": name,
            "server_url": server_url,
            "username": username,
            "password": password,
            "type": provider_type,
        }

        # Pruefen, ob Provider bereits existiert (Update statt Duplikat)
        updated = False
        for i, p in enumerate(providers):
            if p.get("name") == name or (
                p.get("server_url") == server_url
                and p.get("username") == username
            ):
                providers[i] = provider
                updated = True
                break

        if not updated:
            providers.append(provider)

        self._save_providers(providers)
        return provider

    def delete_provider(self, name):
        """
        Entfernt einen Provider anhand seines Namens.

        Args:
            name: Name des zu entfernenden Providers.

        Returns:
            bool: True wenn entfernt, False wenn nicht gefunden.
        """
        providers = self.get_providers()
        original_len = len(providers)
        providers = [p for p in providers if p.get("name") != name]

        if len(providers) < original_len:
            self._save_providers(providers)
            # Wenn geloeschter Provider der letzte war, auch zuruecksetzen
            last = self.get_last_provider()
            if last == name:
                self.set_last_provider(None)
            return True
        return False

    def get_provider_by_name(self, name):
        """
        Sucht einen Provider anhand seines Namens.

        Returns:
            dict oder None.
        """
        for p in self.get_providers():
            if p.get("name") == name:
                return p
        return None

    def _save_providers(self, providers):
        """Speichert die Provider-Liste als JSON."""
        with open(self.providers_file, "w", encoding="utf-8") as f:
            json.dump(providers, f, indent=2, ensure_ascii=False)

    # --- Last Provider ---

    def get_last_provider(self):
        """Gibt den Namen des zuletzt verwendeten Providers zurueck."""
        if not os.path.exists(self.last_provider_file):
            return None
        try:
            with open(self.last_provider_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_provider")
        except (json.JSONDecodeError, IOError):
            return None

    def set_last_provider(self, name):
        """Setzt den zuletzt verwendeten Provider."""
        data = {"last_provider": name}
        with open(self.last_provider_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # --- Settings Management ---

    def get_settings(self):
        """
        Gibt die aktuellen Settings zurueck, gemergt mit Defaults.

        Returns:
            dict: Settings.
        """
        settings = dict(self.DEFAULT_SETTINGS)
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        settings.update(saved)
            except (json.JSONDecodeError, IOError):
                pass
        return settings

    def set_setting(self, key, value):
        """
        Setzt einen einzelnen Setting-Wert.

        Args:
            key: Setting-Key.
            value: Setting-Value.
        """
        settings = self.get_settings()
        settings[key] = value
        self._save_settings(settings)

    def _save_settings(self, settings):
        """Speichert die Settings als JSON."""
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

    def reset_settings(self):
        """Setzt alle Settings auf Default-Werte zurueck."""
        self._save_settings(dict(self.DEFAULT_SETTINGS))
