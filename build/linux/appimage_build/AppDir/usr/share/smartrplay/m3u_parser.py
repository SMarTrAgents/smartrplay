#!/usr/bin/env python3
"""SMarTrPlay - M3U/M3U+ Playlist Parser"""

import re
import requests
from urllib.parse import unquote


class M3UParser:
    """Parser fuer M3U und M3U+ Playlists."""

    def __init__(self):
        self.channels = []

    def parse_url(self, url):
        """M3U Playlist von URL laden und parsen."""
        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "SMarTrPlay/1.0"
            })
            resp.raise_for_status()
            return self.parse_text(resp.text)
        except Exception as e:
            raise Exception(f"M3U URL Load Error: {e}")

    def parse_file(self, filepath):
        """M3U Playlist aus Datei laden und parsen."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return self.parse_text(f.read())
        except Exception as e:
            raise Exception(f"M3U File Load Error: {e}")

    def parse_text(self, text):
        """M3U/M3U+ Text parsen."""
        self.channels = []
        lines = text.strip().split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.startswith("#EXTM3U"):
                i += 1
                continue

            if line.startswith("#EXTINF"):
                channel = self._parse_extinf(line)
                # Naechste Zeile ist die URL
                if i + 1 < len(lines):
                    url_line = lines[i + 1].strip()
                    if url_line and not url_line.startswith("#"):
                        channel["url"] = url_line
                        # Type-Erkennung aus URL als Fallback
                        if channel.get("type", "live") == "live":
                            url_lower = url_line.lower()
                            if "/movie/" in url_lower:
                                channel["type"] = "vod"
                            elif "/series/" in url_lower:
                                channel["type"] = "series"
                        self.channels.append(channel)
                i += 2
            else:
                i += 1

        return self.channels

    def _parse_extinf(self, line):
        """EXTINF-Zeile parsen."""
        channel = {
            "name": "",
            "logo": "",
            "tvg_id": "",
            "tvg_name": "",
            "category": "",
            "type": "live",
        }

        # tvg-id
        m = re.search(r'tvg-id="([^"]*)"', line)
        if m:
            channel["tvg_id"] = m.group(1)

        # tvg-name
        m = re.search(r'tvg-name="([^"]*)"', line)
        if m:
            channel["tvg_name"] = m.group(1)

        # tvg-logo
        m = re.search(r'tvg-logo="([^"]*)"', line)
        if m:
            channel["logo"] = m.group(1)

        # group-title (category)
        m = re.search(r'group-title="([^"]*)"', line)
        if m:
            channel["category"] = m.group(1)

        # Type (VOD/Series/Live)
        m = re.search(r'type="([^"]*)"', line)
        if m:
            channel["type"] = m.group(1).lower()

        # Channel name (nach letztem Komma)
        # Format: #EXTINF:-1 tvg-id="..." ...,Channel Name
        comma_idx = line.rfind(",")
        if comma_idx != -1 and comma_idx < len(line) - 1:
            channel["name"] = line[comma_idx + 1:].strip()
        else:
            # Fallback: Name aus tvg-name
            channel["name"] = channel.get("tvg_name") or "Unknown"

        return channel

    def get_categories(self):
        """Kategorien aus geparsten Channels extrahieren."""
        cats = set()
        for ch in self.channels:
            if ch.get("category"):
                cats.add(ch["category"])
        return sorted(cats)
