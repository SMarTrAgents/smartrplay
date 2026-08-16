#!/usr/bin/env python3
"""SMarTrPlay - Xtream Codes API Client"""

import requests



class XtreamAPI:
    """Client fuer Xtream Codes API."""

    def __init__(self, server_url, username, password):
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.base_url = f"{self.server_url}/player_api.php"
        self.params = {
            "username": username,
            "password": password,
        }

    def _request(self, action, extra_params=None):
        """API Request ausfuehren."""
        params = dict(self.params)
        params["action"] = action
        if extra_params:
            params.update(extra_params)

        try:
            resp = requests.get(self.base_url, params=params, timeout=30, headers={
                "User-Agent": "SMarTrPlay/1.0"
            })
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise Exception(f"Xtream API Error ({action}): {e}")

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
        """Live TV Kategorien abrufen."""
        return self._request("get_live_categories")

    def get_vod_categories(self):
        """VOD (Movies) Kategorien abrufen."""
        return self._request("get_vod_categories")

    def get_series_categories(self):
        """Series Kategorien abrufen."""
        return self._request("get_series_categories")

    def get_live_streams(self, category_id=None):
        """Live TV Streams abrufen."""
        params = {}
        if category_id:
            params["category_id"] = category_id
        return self._request("get_live_streams", params)

    def get_vod_streams(self, category_id=None):
        """VOD Streams abrufen."""
        params = {}
        if category_id:
            params["category_id"] = category_id
        return self._request("get_vod_streams", params)

    def get_series(self, category_id=None):
        """Series abrufen."""
        params = {}
        if category_id:
            params["category_id"] = category_id
        return self._request("get_series", params)

    def get_vod_info(self, vod_id):
        """VOD Info (inkl. Movie URL) abrufen."""
        return self._request("get_vod_info", {"vod_id": vod_id})

    def get_series_info(self, series_id):
        """Series Info (inkl. Episoden) abrufen."""
        return self._request("get_series_info", {"series_id": series_id})

    def get_epg(self, stream_id):
        """EPG fuer einen Live Stream abrufen."""
        return self._request("get_live_stream_epg", {"stream_id": stream_id})

    def get_short_epg(self, stream_id):
        """Kurzes EPG fuer einen Live Stream abrufen."""
        return self._request("get_short_epg", {"stream_id": stream_id})

    def get_stream_url(self, stream_id, stream_type="live", container_ext=None):
        """Stream URL generieren."""
        # Xtream Codes API path segments: live, movie, series
        path_map = {"live": "live", "vod": "movie", "series": "series"}
        path = path_map.get(stream_type, stream_type)

        if stream_type == "live":
            ext = container_ext or "m3u8"
        elif stream_type == "vod":
            ext = container_ext or "mp4"
        else:
            ext = container_ext or "mp4"
        return f"{self.server_url}/{path}/{self.username}/{self.password}/{stream_id}.{ext}"

    def get_all_channels(self):
        """Alle Channels (Live + VOD) als einheitliche Liste abrufen."""
        channels = []
        errors = []

        # Live TV
        try:
            live_cats = self.get_live_categories() or []
            for cat in live_cats:
                cat_id = cat.get("category_id")
                cat_name = cat.get("category_name", "Unknown")
                streams = self.get_live_streams(cat_id) or []
                for s in streams:
                    channels.append({
                        "name": s.get("name", ""),
                        "url": self.get_stream_url(s.get("stream_id"), "live"),
                        "logo": s.get("stream_icon", ""),
                        "category": cat_name,
                        "tvg_id": str(s.get("stream_id", "")),
                        "tvg_name": s.get("name", ""),
                        "type": "live",
                    })
        except Exception as e:
            errors.append(f"Live TV: {e}")

        # VOD (Movies)
        try:
            vod_cats = self.get_vod_categories() or []
            for cat in vod_cats:
                cat_id = cat.get("category_id")
                cat_name = cat.get("category_name", "Unknown")
                streams = self.get_vod_streams(cat_id) or []
                for s in streams:
                    channels.append({
                        "name": s.get("name", ""),
                        "url": self.get_stream_url(s.get("stream_id"), "vod", s.get("container_extension")),
                        "logo": s.get("stream_icon", ""),
                        "category": cat_name,
                        "tvg_id": str(s.get("stream_id", "")),
                        "tvg_name": s.get("name", ""),
                        "type": "vod",
                    })
        except Exception as e:
            errors.append(f"VOD: {e}")

        # Series
        try:
            series_cats = self.get_series_categories() or []
            for cat in series_cats:
                cat_id = cat.get("category_id")
                cat_name = cat.get("category_name", "Unknown")
                series_list = self.get_series(cat_id) or []
                for s in series_list:
                    channels.append({
                        "name": s.get("name", ""),
                        "url": self.get_stream_url(s.get("series_id"), "series"),
                        "logo": s.get("cover", ""),
                        "category": cat_name,
                        "tvg_id": str(s.get("series_id", "")),
                        "tvg_name": s.get("name", ""),
                        "type": "series",
                    })
        except Exception as e:
            errors.append(f"Series: {e}")

        if not channels and errors:
            raise Exception("Keine Channels geladen. Fehler: " + "; ".join(errors))

        return channels
