# -*- coding: utf-8 -*-
"""
SMarTrPlay Android TV — M3U Parser
Angepasst fuer Android: Verwendet urllib statt requests.
URL-basierte Type-Erkennung (/movie/ -> vod, /series/ -> series).
"""

import re
import urllib.request
import urllib.error


class M3UParser:
    """Parser fuer M3U/M3U8 Playlists — Android-kompatibel."""

    # Regex fuer #EXTINF Zeilen
    EXTINF_RE = re.compile(
        r'#EXTINF:(?P<duration>-?\d+)'
        r'(?:.*?tvg-name="(?P<tvg_name>[^"]*)")?'
        r'(?:.*?tvg-id="(?P<tvg_id>[^"]*)")?'
        r'(?:.*?tvg-logo="(?P<tvg_logo>[^"]*)")?'
        r'(?:.*?group-title="(?P<group_title>[^"]*)")?'
        r',(?P<name>.*)'
    )

    def parse_url(self, url, timeout=15):
        """
        Laedt eine M3U-Playlist von einer URL und parst sie.

        Args:
            url: URL zur M3U-Datei.
            timeout: Timeout in Sekunden.

        Returns:
            list: Liste von Dicts mit {name, url, logo, category, type}.
        """
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "SMarTrPlay/1.0 (Android TV)",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            return self.parse_text(content)
        except urllib.error.URLError as e:
            raise Exception(f"M3U URL Error: {e.reason}")
        except Exception as e:
            raise Exception(f"M3U Parse Error: {e}")

    def parse_file(self, filepath):
        """
        Parst eine lokale M3U-Datei.

        Args:
            filepath: Pfad zur M3U-Datei.

        Returns:
            list: Liste von Dicts.
        """
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return self.parse_text(content)

    def parse_text(self, content):
        """
        Parst M3U-Textinhalt in eine Liste von Eintraegen.

        Args:
            content: M3U-Textinhalt.

        Returns:
            list: Liste von Dicts mit {name, url, logo, category, type}.
        """
        entries = []
        lines = content.strip().splitlines()

        current_entry = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF"):
                current_entry = self._parse_extinf(line)
            elif line.startswith("#EXTGRP"):
                # Group title als Fallback
                if current_entry is not None:
                    grp = line.replace("#EXTGRP:", "").strip().strip('"')
                    if not current_entry.get("category"):
                        current_entry["category"] = grp
            elif line.startswith("#"):
                # Andere Direktiven ignorieren
                continue
            elif not line.startswith("#"):
                # Das ist eine URL-Zeile
                if current_entry is not None:
                    current_entry["url"] = line
                    current_entry["type"] = self._detect_type(line)
                    entries.append(current_entry)
                    current_entry = None
                else:
                    # URL ohne EXTINF — trotzdem aufnehmen
                    entry = {
                        "name": line.split("/")[-1] if "/" in line else line,
                        "url": line,
                        "logo": "",
                        "category": "Ohne Kategorie",
                        "type": self._detect_type(line),
                    }
                    entries.append(entry)

        return entries

    def _parse_extinf(self, line):
        """
        Parst eine #EXTINF Zeile.

        Returns:
            dict: Eintrag mit name, logo, category.
        """
        match = self.EXTINF_RE.match(line)
        entry = {
            "name": "Unbekannt",
            "url": "",
            "logo": "",
            "category": "",
            "type": "live",
        }

        if match:
            entry["name"] = match.group("name").strip() if match.group("name") else "Unbekannt"
            entry["logo"] = match.group("tvg_logo") or ""
            entry["category"] = match.group("group_title") or "Ohne Kategorie"
        else:
            # Fallback: einfaches Parsing nach dem Komma
            if "," in line:
                name_part = line.split(",", 1)[1].strip()
                entry["name"] = name_part

        return entry

    def _detect_type(self, url):
        """
        Erkennt den Stream-Typ anhand der URL.

        Args:
            url: Stream-URL.

        Returns:
            str: 'live', 'vod', oder 'series'.
        """
        url_lower = url.lower()

        # Xtream-basierte Erkennung
        if "/movie/" in url_lower:
            return "vod"
        elif "/series/" in url_lower:
            return "series"
        elif "/live/" in url_lower:
            return "live"

        # Dateierweiterung-basierte Erkennung
        if url_lower.endswith(".mp4") or url_lower.endswith(".mkv") or url_lower.endswith(".avi"):
            return "vod"
        elif url_lower.endswith(".m3u8") or "/hls/" in url_lower:
            return "live"

        # Default: Live-TV
        return "live"

    def group_by_category(self, entries):
        """
        Gruppiert Eintraege nach Kategorie.

        Args:
            entries: Liste von Eintrag-Dicts.

        Returns:
            dict: {category_name: [entries]}
        """
        groups = {}
        for entry in entries:
            cat = entry.get("category", "Ohne Kategorie")
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(entry)
        return groups

    def filter_by_type(self, entries, stream_type):
        """
        Filtert Eintraege nach Stream-Typ.

        Args:
            entries: Liste von Eintrag-Dicts.
            stream_type: 'live', 'vod', oder 'series'.

        Returns:
            list: Gefilterte Eintraege.
        """
        return [e for e in entries if e.get("type") == stream_type]
