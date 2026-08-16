# -*- coding: utf-8 -*-
"""
SMarTrPlay Android TV — Xtream API Client
Angepasst fuer Android: Verwendet urllib statt requests.
Keine externen Dependencies.
"""

import json
import urllib.request
import urllib.parse
import urllib.error


class XtreamClient:
    """Xtream Codes API Client fuer Android TV."""

    def __init__(self, server_url, username, password):
        """
        Initialisiert den Xtream Client.

        Args:
            server_url: Basis-URL des Xtream-Servers (ohne trailing /).
            username: Xtream Benutzername.
            password: Xtream Passwort.
        """
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.authenticated = False
        self.user_info = None
        self.server_info = None

    def _build_url(self, action, **params):
        """Baut eine Xtream API URL mit Parametern."""
        base = f"{self.server_url}/player_api.php"
        query_params = {
            "username": self.username,
            "password": self.password,
        }
        if action:
            query_params["action"] = action
        query_params.update(params)
        return f"{base}?{urllib.parse.urlencode(query_params)}"

    def _fetch(self, url, timeout=15):
        """
        Fuehrt einen HTTP-GET Request aus und gibt JSON zurueck.

        Args:
            url: Die vollstaendige URL.
            timeout: Timeout in Sekunden.

        Returns:
            dict oder list: Geparste JSON-Antwort.

        Raises:
            Exception bei Netzwerk- oder Parse-Fehlern.
        """
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "SMarTrPlay/1.0 (Android TV)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8", errors="replace")
                if not data:
                    return []
                return json.loads(data)
        except urllib.error.HTTPError as e:
            raise Exception(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(f"URL Error: {e.reason}")
        except json.JSONDecodeError as e:
            raise Exception(f"JSON Parse Error: {e}")

    # --- Authentication ---

    def authenticate(self):
        """
        Authentifiziert sich am Xtream Server.

        Returns:
            dict: user_info bei Erfolg.

        Raises:
            Exception bei Auth-Fehler.
        """
        url = self._build_url(action=None)
        data = self._fetch(url)

        if not data or not isinstance(data, dict):
            raise Exception("Ungueltige Server-Antwort")

        user_info = data.get("user_info", {})
        server_info = data.get("server_info", {})

        auth_status = int(user_info.get("auth", 0))
        status = user_info.get("status", "")

        if auth_status == 0 or status == "Banned" or status == "Disabled":
            raise Exception(
                f"Authentifizierung fehlgeschlagen (status={status}, auth={auth_status})"
            )

        self.authenticated = True
        self.user_info = user_info
        self.server_info = server_info
        return user_info

    # --- Categories ---

    def get_live_categories(self):
        """Gibt Live-TV Kategorien zurueck."""
        url = self._build_url(action="get_live_categories")
        data = self._fetch(url)
        return data if isinstance(data, list) else []

    def get_vod_categories(self):
        """Gibt VOD (Film) Kategorien zurueck."""
        url = self._build_url(action="get_vod_categories")
        data = self._fetch(url)
        return data if isinstance(data, list) else []

    def get_series_categories(self):
        """Gibt Serien-Kategorien zurueck."""
        url = self._build_url(action="get_series_categories")
        data = self._fetch(url)
        return data if isinstance(data, list) else []

    # --- Streams ---

    def get_live_streams(self, category_id=None):
        """
        Gibt Live-TV Streams zurueck.

        Args:
            category_id: Optional Kategorie-Filter.
        """
        params = {}
        if category_id is not None:
            params["category_id"] = category_id
        url = self._build_url(action="get_live_streams", **params)
        data = self._fetch(url)
        return data if isinstance(data, list) else []

    def get_vod_streams(self, category_id=None):
        """
        Gibt VOD (Filme) Streams zurueck.

        Args:
            category_id: Optional Kategorie-Filter.
        """
        params = {}
        if category_id is not None:
            params["category_id"] = category_id
        url = self._build_url(action="get_vod_streams", **params)
        data = self._fetch(url)
        return data if isinstance(data, list) else []

    def get_series(self, category_id=None):
        """
        Gibt Serien zurueck.

        Args:
            category_id: Optional Kategorie-Filter.
        """
        params = {}
        if category_id is not None:
            params["category_id"] = category_id
        url = self._build_url(action="get_series", **params)
        data = self._fetch(url)
        return data if isinstance(data, list) else []

    # --- Stream URLs ---

    def get_stream_url(self, stream_id, stream_type, container_ext="ts"):
        """
        Baut die Stream-URL fuer einen Stream zusammen.

        Args:
            stream_id: ID des Streams.
            stream_type: 'live', 'vod', oder 'series'.
            container_ext: Container-Erweiterung (z.B. 'ts', 'm3u8', 'mp4').

        Returns:
            str: Stream-URL.
        """
        if stream_type == "live":
            return f"{self.server_url}/live/{self.username}/{self.password}/{stream_id}.{container_ext}"
        elif stream_type == "vod":
            return f"{self.server_url}/movie/{self.username}/{self.password}/{stream_id}.{container_ext}"
        elif stream_type == "series":
            return f"{self.server_url}/series/{self.username}/{self.password}/{stream_id}.{container_ext}"
        else:
            raise ValueError(f"Unbekannter stream_type: {stream_type}")

    # --- Info ---

    def get_vod_info(self, vod_id):
        """
        Gibt VOD-Info fuer einen Film zurueck.

        Args:
            vod_id: VOD ID.

        Returns:
            dict: Movie-Info mit stream_url, info, etc.
        """
        url = self._build_url(action="get_vod_info", vod_id=vod_id)
        data = self._fetch(url)
        return data if isinstance(data, dict) else {}

    def get_series_info(self, series_id):
        """
        Gibt Serien-Info zurueck (inkl. Episoden).

        Args:
            series_id: Series ID.

        Returns:
            dict: Serien-Info mit Episoden.
        """
        url = self._build_url(action="get_series_info", series_id=series_id)
        data = self._fetch(url)
        return data if isinstance(data, dict) else {}

    # --- Convenience ---

    def get_all_categories(self):
        """
        Gibt alle Kategorien kombiniert zurueck.

        Returns:
            list: Kategorien mit type-Attribut.
        """
        categories = []

        # Hauptkategorien
        categories.append({"category_id": "__live__", "category_name": "Live TV", "type": "live"})
        categories.append({"category_id": "__vod__", "category_name": "Filme (VOD)", "type": "vod"})
        categories.append({"category_id": "__series__", "category_name": "Serien", "type": "series"})

        # Live Sub-Kategorien
        try:
            live_cats = self.get_live_categories()
            for cat in live_cats:
                cat["type"] = "live"
                cat["category_id"] = f"live_{cat.get('category_id', '')}"
                categories.append(cat)
        except Exception:
            pass

        # VOD Sub-Kategorien
        try:
            vod_cats = self.get_vod_categories()
            for cat in vod_cats:
                cat["type"] = "vod"
                cat["category_id"] = f"vod_{cat.get('category_id', '')}"
                categories.append(cat)
        except Exception:
            pass

        # Series Sub-Kategorien
        try:
            series_cats = self.get_series_categories()
            for cat in series_cats:
                cat["type"] = "series"
                cat["category_id"] = f"series_{cat.get('category_id', '')}"
                categories.append(cat)
        except Exception:
            pass

        return categories

    def get_streams_by_category(self, category_id, cat_type):
        """
        Holt Streams fuer eine Kategorie basierend auf dem Typ.

        Args:
            category_id: Die Kategorie-ID (ohne Prefix).
            cat_type: 'live', 'vod', oder 'series'.

        Returns:
            list: Stream-Liste.
        """
        if cat_type == "live":
            if category_id == "__live__":
                return self.get_live_streams()
            # Remove prefix
            cat_id = category_id.replace("live_", "")
            return self.get_live_streams(category_id=cat_id)
        elif cat_type == "vod":
            if category_id == "__vod__":
                return self.get_vod_streams()
            cat_id = category_id.replace("vod_", "")
            return self.get_vod_streams(category_id=cat_id)
        elif cat_type == "series":
            if category_id == "__series__":
                return self.get_series()
            cat_id = category_id.replace("series_", "")
            return self.get_series(category_id=cat_id)
        return []
