#!/usr/bin/env python3
"""SMarTrPlay - HTTP Debug & Diagnostic Server

Liefert Live-Status und Diagnose-Endpunkte fuer die SMarTrPlay Desktop-App.
Laeuft thread-safe in einem eigenen Thread auf Port 8421.
"""

import os
import sys
import time
import json
import re
import secrets
import threading
import logging
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from config import Config

logger = logging.getLogger('SMarTrPlay.DebugServer')

# ── Maskierung von Zugangsdaten ───────────────────────────────────────

# Zugangsdaten im Pfad des Xtream-Musters: http://server:80/typ/BENUTZER/KENNWORT/nummer
_MUSTER_XTREAM_PFAD = re.compile(r'^(https?://[^/\s]+/[^/\s]+/)[^/\s]+/[^/\s]+(/.*)?$')
# Zugangsdaten als Abfrageparameter: username=..., password=...
_MUSTER_QUERY_BENUTZER = re.compile(r'(?i)(username=)[^&\s]+')
_MUSTER_QUERY_KENNWORT = re.compile(r'(?i)(password=)[^&\s]+')
# Kurzform für Protokollzeilen: user=..., pass=...
_MUSTER_QUERY_USER = re.compile(r'(?i)(user=)[^&\s]+')
_MUSTER_QUERY_PASS = re.compile(r'(?i)(pass=)[^&\s]+')
# Zugangsdaten vor dem @-Zeichen (zum Beispiel http://BENUTZER:KENNWORT@server/)
_MUSTER_URL_ZUGANG = re.compile(r'(?i)^(https?://)[^/@\s]+:[^/@\s]+@')


def adresse_maskieren(url):
    """Entfernt Zugangsdaten aus einer Adresse, bevor sie ausgegeben wird.

    Erkennt das Xtream-Muster mit Benutzer und Kennwort im Pfad sowie
    Benutzer und Kennwort als Abfrageparameter (username=, password=),
    dazu die Kurzform user= für Protokollzeilen und Zugangsdaten vor dem
    @-Zeichen. Alle gefundenen Zugangsdaten werden durch das Wort GEHEIM
    ersetzt, der Rest der Adresse bleibt unverändert.
    """
    if not isinstance(url, str) or not url:
        return url
    ergebnis = url
    ergebnis = _MUSTER_URL_ZUGANG.sub(r'\g<1>GEHEIM:GEHEIM@', ergebnis)
    ergebnis = _MUSTER_QUERY_BENUTZER.sub(r'\g<1>GEHEIM', ergebnis)
    ergebnis = _MUSTER_QUERY_KENNWORT.sub(r'\g<1>GEHEIM', ergebnis)
    ergebnis = _MUSTER_QUERY_USER.sub(r'\g<1>GEHEIM', ergebnis)
    ergebnis = _MUSTER_QUERY_PASS.sub(r'\g<1>GEHEIM', ergebnis)
    ergebnis = _MUSTER_XTREAM_PFAD.sub(r'\g<1>GEHEIM/GEHEIM\g<2>', ergebnis)
    return ergebnis


# SMarTr Brand Colors
BG_DEEP = "#0A0F1E"
BG_CARD = "#121A2E"
BG_CARD_HOVER = "#1A2540"
BORDER = "#232D45"
ACCENT_CYAN = "#1bf1fb"
ACCENT_PURPLE = "#8D7CF6"
ACCENT_VIOLET = "#371689"
TEXT_PRIMARY = "#F5F7FA"
TEXT_SECONDARY = "#9BA5B7"
TEXT_MUTED = "#6B7280"
COLOR_SUCCESS = "#10B981"
COLOR_WARNING = "#F59E0B"
COLOR_ERROR = "#EF4444"


def _html_page(title, body):
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - SMarTrPlay Debug</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background-color:{BG_DEEP}; color:{TEXT_PRIMARY};
    font-family:'Inter','DejaVu Sans',sans-serif; padding:24px; line-height:1.6; }}
  h1 {{ font-size:24px; font-weight:800; color:{ACCENT_CYAN}; margin-bottom:8px; }}
  h2 {{ font-size:18px; font-weight:700; color:{ACCENT_PURPLE};
    margin-top:24px; margin-bottom:8px; border-bottom:1px solid {BORDER}; padding-bottom:6px; }}
  .header {{ display:flex; align-items:center; gap:12px; margin-bottom:24px; }}
  .logo {{ font-size:22px; font-weight:800; color:{TEXT_PRIMARY}; }}
  .badge {{ background:{ACCENT_VIOLET}; color:{TEXT_PRIMARY};
    padding:2px 10px; border-radius:6px; font-size:11px; font-weight:600; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:16px; }}
  th {{ text-align:left; padding:10px 14px; background-color:{BG_CARD};
    color:{ACCENT_CYAN}; font-size:12px; font-weight:700;
    letter-spacing:0.5px; border-bottom:2px solid {BORDER}; }}
  td {{ padding:8px 14px; background-color:{BG_CARD};
    color:{TEXT_SECONDARY}; font-size:13px; border-bottom:1px solid {BORDER}; }}
  tr:hover td {{ background-color:{BG_CARD_HOVER}; }}
  .card {{ background-color:{BG_CARD}; border:1px solid {BORDER};
    border-radius:10px; padding:16px 20px; margin-bottom:16px; }}
  .stat {{ display:inline-block; margin-right:32px; }}
  .stat-label {{ font-size:11px; color:{TEXT_MUTED};
    text-transform:uppercase; letter-spacing:1px; }}
  .stat-value {{ font-size:28px; font-weight:800; color:{ACCENT_CYAN}; }}
  .stat-value.warn {{ color:{COLOR_WARNING}; }}
  .stat-value.error {{ color:{COLOR_ERROR}; }}
  .stat-value.ok {{ color:{COLOR_SUCCESS}; }}
  code, pre {{ background-color:{BG_CARD}; border:1px solid {BORDER};
    border-radius:6px; padding:12px; font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;
    font-size:12px; color:{TEXT_SECONDARY}; overflow-x:auto; white-space:pre-wrap; }}
  a {{ color:{ACCENT_CYAN}; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .endpoints {{ list-style:none; }}
  .endpoints li {{ padding:6px 0; }}
  .method {{ display:inline-block; min-width:48px;
    padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700; text-align:center; }}
  .method.GET {{ background:{COLOR_SUCCESS}; color:#fff; }}
  .method.POST {{ background:{ACCENT_PURPLE}; color:#fff; }}
  .footer {{ margin-top:32px; padding-top:16px;
    border-top:1px solid {BORDER}; font-size:11px; color:{TEXT_MUTED}; }}
</style>
</head>
<body>
  <div class="header">
    <span class="logo">SMarTrPlay</span>
    <span class="badge">Debug Server :8421</span>
  </div>
  {body}
  <div class="footer">SMarTrPlay Debug Server - SMarTrAgents &copy; 2026 - Port 8421</div>
</body>
</html>"""


class DebugHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler fuer SMarTrPlay Debug Endpunkte."""

    @property
    def cfg(self):
        return self.server.app_config

    @property
    def start_time(self):
        return self.server.start_time

    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str, ensure_ascii=False).encode('utf-8')
        self._send(status, 'application/json; charset=utf-8', body)

    def _send_html(self, html, status=200):
        body = html.encode('utf-8')
        self._send(status, 'text/html; charset=utf-8', body)

    def _client_lokal(self):
        """True, wenn die Anfrage vom selben Rechner kommt (Loopback)."""
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _token_ok(self):
        """Prüft den Kopfzeilenwert X-SMARTrPlay-Token gegen das Zugangswort.

        Der Abgleich läuft über secrets.compare_digest, damit das
        Zugangswort nicht über Antwortzeiten erratbar ist.
        """
        wort = self.headers.get('X-SMARTrPlay-Token')
        if not wort:
            return False
        erwartet = getattr(self.server, 'zugangswort', '')
        return secrets.compare_digest(str(wort), str(erwartet))

    def _get_fd_count(self):
        try:
            return len(os.listdir('/proc/self/fd'))
        except Exception:
            return -1

    def _get_ram_usage(self):
        try:
            with open('/proc/self/status', 'r') as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                if line.startswith('VmRSS'):
                    info['rss_kb'] = int(line.split(':')[1].strip().split()[0])
                elif line.startswith('VmSize'):
                    info['vsize_kb'] = int(line.split(':')[1].strip().split()[0])
                elif line.startswith('VmPeak'):
                    info['peak_kb'] = int(line.split(':')[1].strip().split()[0])
            return info
        except Exception:
            return {}

    def _get_uptime(self):
        return time.time() - self.start_time

    def _format_uptime(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}h {m}m {s}s"

    def _get_log_lines(self, n=50):
        log_path = os.path.join(str(Config.LOG_DIR), 'smartrplay.log')
        try:
            with open(log_path, 'r') as f:
                lines = f.readlines()
            return [line.strip() for line in lines[-n:]]
        except FileNotFoundError:
            return [f"Log-Datei nicht gefunden: {log_path}"]
        except Exception as e:
            return [f"Fehler beim Lesen der Logs: {e}"]

    def _test_stream_ffprobe(self, url):
        try:
            # Zweite Prüfung, falls diese Funktion von einer anderen Stelle
            # aufgerufen wird: nur http und https, keine Adresse mit
            # führendem Bindestrich, sonst liest ffprobe sie als Option.
            if not isinstance(url, str) or url.startswith('-') or not (url.startswith('http://') or url.startswith('https://')):
                return {'playable': False, 'error': 'Adresse abgelehnt: nur http:// oder https:// erlaubt'}
            # Protokollgrenze: ffprobe darf nur HTTP(S) öffnen, damit keine
            # lokalen Dateien oder anderen Protokolle gelesen werden können.
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
                   '-show_streams', '-show_format', '-timeout', '10',
                   '-protocol_whitelist', 'http,https,tcp,tls', url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    streams = data.get('streams', [])
                    fmt = data.get('format', {})
                    return {
                        'playable': True,
                        'streams': len(streams),
                        'format': fmt.get('format_name', 'unknown'),
                        'duration': fmt.get('duration', 'unknown'),
                        'bitrate': fmt.get('bit_rate', 'unknown'),
                    }
                except json.JSONDecodeError:
                    return {'playable': True, 'raw': result.stdout[:500]}
            else:
                return {
                    'playable': False,
                    'error': result.stderr.strip()[:500] if result.stderr else 'Unknown error',
                    'returncode': result.returncode
                }
        except FileNotFoundError:
            return {'playable': False, 'error': 'ffprobe nicht installiert'}
        except subprocess.TimeoutExpired:
            return {'playable': False, 'error': 'Timeout (10s)'}
        except Exception as e:
            return {'playable': False, 'error': str(e)}

    def do_GET(self):
        # Zweiter Riegel: Die Bindung liegt auf 127.0.0.1, hier wird die
        # Herkunft noch einmal geprüft, damit auch bei einer späteren
        # Änderung der Bindung keine fremde Anfrage verarbeitet wird.
        if not self._client_lokal():
            self._send_json({'error': 'Zugriff verweigert: nur vom selben Rechner erlaubt'}, 403)
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        params = parse_qs(parsed.query)
        # Endpunkte mit Innenansichten nur mit dem Zugangswort vom Start.
        # /test_stream prüft zuerst die Adresse (Antwort 400) und danach
        # sein Zugangswort innerhalb des Handlers.
        if path in ('/logs', '/fds', '/threads') and not self._token_ok():
            self._send_json({'error': 'Zugangswort fehlt oder ist falsch'}, 403)
            return
        try:
            if path in ('/', '/index'):
                self._handle_index()
            elif path == '/status':
                self._handle_status()
            elif path == '/providers':
                self._handle_providers()
            elif path == '/categories':
                self._handle_categories(params)
            elif path == '/channels':
                self._handle_channels(params)
            elif path == '/test_stream':
                self._handle_test_stream(params)
            elif path == '/logs':
                self._handle_logs(params)
            elif path == '/fds':
                self._handle_fds()
            elif path == '/threads':
                self._handle_threads()
            else:
                self._send_json({'error': f'Endpoint nicht gefunden: {path}'}, 404)
        except Exception as e:
            logger.error(f"GET {path} Fehler: {e}", exc_info=True)
            self._send_json({'error': str(e)}, 500)

    def do_POST(self):
        # Zweiter Riegel: Die Bindung liegt auf 127.0.0.1, hier wird die
        # Herkunft noch einmal geprüft, damit auch bei einer späteren
        # Änderung der Bindung keine fremde Anfrage verarbeitet wird.
        if not self._client_lokal():
            self._send_json({'error': 'Zugriff verweigert: nur vom selben Rechner erlaubt'}, 403)
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        try:
            if path == '/restart':
                self._handle_restart()
            else:
                self._send_json({'error': f'POST-Endpoint nicht gefunden: {path}'}, 404)
        except Exception as e:
            logger.error(f"POST {path} Fehler: {e}", exc_info=True)
            self._send_json({'error': str(e)}, 500)

    # ── Endpunkte ────────────────────────────────────────────────────

    def _handle_index(self):
        endpoints = [
            ('GET', '/status', 'App-Status (PID, FDs, RAM, Uptime)'),
            ('GET', '/providers', 'Alle gespeicherten Provider'),
            ('GET', '/categories?type=live', 'Live TV Kategorien'),
            ('GET', '/categories?type=vod', 'VOD Kategorien'),
            ('GET', '/categories?type=series', 'Serien Kategorien'),
            ('GET', '/channels?type=live&category_id=X', 'Live Kanaele einer Kategorie'),
            ('GET', '/channels?type=vod&category_id=X', 'VOD Eintraege'),
            ('GET', '/channels?type=series&category_id=X', 'Serien'),
            ('GET', '/test_stream?url=X', 'Stream-URL mit ffprobe testen'),
            ('GET', '/logs', 'Letzte 50 Log-Zeilen'),
            ('GET', '/fds', 'Anzahl offener File-Descriptors'),
            ('GET', '/threads', 'Anzahl aktiver Threads'),
            ('POST', '/restart', 'App neu starten (os.execv)'),
        ]
        rows = ""
        for method, ep, desc in endpoints:
            href = ep if '?' not in ep and method == 'GET' else '#'
            rows += f'<li><span class="method {method}">{method}</span> <a href="{href}">{ep}</a> &mdash; {desc}</li>\n'
        body = f"""
  <h1>Debug Server &mdash; Endpunkte</h1>
  <p style="color:{TEXT_SECONDARY};">SMarTrPlay HTTP-Diagnose-Server auf Port 8421</p>
  <ul class="endpoints">{rows}
  </ul>
  <h2>Quick Stats</h2>
  <div class="card">
    <div class="stat"><div class="stat-label">PID</div><div class="stat-value">{os.getpid()}</div></div>
    <div class="stat"><div class="stat-label">FDs</div><div class="stat-value">{self._get_fd_count()}</div></div>
    <div class="stat"><div class="stat-label">Threads</div><div class="stat-value">{threading.active_count()}</div></div>
    <div class="stat"><div class="stat-label">Uptime</div><div class="stat-value" style="font-size:20px;">{self._format_uptime(self._get_uptime())}</div></div>
  </div>"""
        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Endpunkte - SMarTrPlay Debug</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background-color:{BG_DEEP}; color:{TEXT_PRIMARY};
    font-family:'Inter','DejaVu Sans',sans-serif; padding:24px; line-height:1.6; }}
  h1 {{ font-size:24px; font-weight:800; color:{ACCENT_CYAN}; margin-bottom:8px; }}
  h2 {{ font-size:18px; font-weight:700; color:{ACCENT_PURPLE};
    margin-top:24px; margin-bottom:8px; border-bottom:1px solid {BORDER}; padding-bottom:6px; }}
  .header {{ display:flex; align-items:center; gap:12px; margin-bottom:24px; }}
  .logo {{ font-size:22px; font-weight:800; color:{TEXT_PRIMARY}; }}
  .badge {{ background:{ACCENT_VIOLET}; color:{TEXT_PRIMARY};
    padding:2px 10px; border-radius:6px; font-size:11px; font-weight:600; }}
  .card {{ background-color:{BG_CARD}; border:1px solid {BORDER};
    border-radius:10px; padding:16px 20px; margin-bottom:16px; }}
  .stat {{ display:inline-block; margin-right:32px; }}
  .stat-label {{ font-size:11px; color:{TEXT_MUTED}; text-transform:uppercase; letter-spacing:1px; }}
  .stat-value {{ font-size:28px; font-weight:800; color:{ACCENT_CYAN}; }}
  a {{ color:{ACCENT_CYAN}; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .endpoints {{ list-style:none; }}
  .endpoints li {{ padding:6px 0; }}
  .method {{ display:inline-block; min-width:48px;
    padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700; text-align:center; }}
  .method.GET {{ background:{COLOR_SUCCESS}; color:#fff; }}
  .method.POST {{ background:{ACCENT_PURPLE}; color:#fff; }}
  .footer {{ margin-top:32px; padding-top:16px;
    border-top:1px solid {BORDER}; font-size:11px; color:{TEXT_MUTED}; }}
</style>
</head>
<body>
  <div class="header"><span class="logo">SMarTrPlay</span><span class="badge">Debug Server :8421</span></div>
  {body}
  <div class="footer">SMarTrPlay Debug Server - SMarTrAgents &copy; 2026 - Port 8421</div>
</body>
</html>"""
        self._send_html(html)

    def _handle_status(self):
        fd_count = self._get_fd_count()
        ram = self._get_ram_usage()
        uptime = self._get_uptime()
        data = {
            'pid': os.getpid(),
            'fds': fd_count,
            'ram': ram,
            'uptime_seconds': round(uptime, 1),
            'uptime_human': self._format_uptime(uptime),
            'threads': threading.active_count(),
            'timestamp': datetime.now().isoformat(),
        }
        fd_class = 'ok'
        if fd_count > 800: fd_class = 'warn'
        if fd_count > 950: fd_class = 'error'
        body = f"""
  <h1>App-Status</h1>
  <div class="card">
    <div class="stat"><div class="stat-label">PID</div><div class="stat-value">{data['pid']}</div></div>
    <div class="stat"><div class="stat-label">File Descriptors</div><div class="stat-value {fd_class}">{fd_count}</div></div>
    <div class="stat"><div class="stat-label">Threads</div><div class="stat-value">{data['threads']}</div></div>
    <div class="stat"><div class="stat-label">Uptime</div><div class="stat-value" style="font-size:20px;">{data['uptime_human']}</div></div>
  </div>
  <h2>Speicher (RAM)</h2>
  <table>
    <tr><th>Metric</th><th>Wert (KB)</th></tr>
    <tr><td>RSS (Resident Set)</td><td>{ram.get('rss_kb', 'N/A')}</td></tr>
    <tr><td>Virtual Size</td><td>{ram.get('vsize_kb', 'N/A')}</td></tr>
    <tr><td>Peak</td><td>{ram.get('peak_kb', 'N/A')}</td></tr>
  </table>
  <h2>JSON</h2>
  <pre>{json.dumps(data, indent=2)}</pre>"""
        self._send_html(_html_page('Status', body))

    def _handle_providers(self):
        providers = self.cfg.get_providers()
        data = []
        for p in providers:
            data.append({
                'id': p[0], 'name': p[1], 'type': p[2],
                # Zugangsdaten niemals im Klartext ausgeben, deshalb werden
                # Adresse und Benutzername maskiert.
                'url': adresse_maskieren(p[3]),
                'username': 'GEHEIM' if (len(p) > 4 and p[4]) else None,
            })
        rows = ""
        for p in data:
            rows += f"<tr><td>{p['id']}</td><td>{p['name']}</td><td>{p['type']}</td><td>{p['url'] or ''}</td><td>{p['username'] or ''}</td></tr>\n"
        body = f"""
  <h1>Provider ({len(data)})</h1>
  <table>
    <tr><th>ID</th><th>Name</th><th>Type</th><th>URL</th><th>Username</th></tr>
    {rows}
  </table>
  <h2>JSON</h2>
  <pre>{json.dumps(data, indent=2)}</pre>"""
        self._send_html(_html_page('Provider', body))

    def _handle_categories(self, params):
        cat_type = params.get('type', [None])[0]
        cats = self.cfg.get_categories(type=cat_type) if cat_type else self.cfg.get_categories()
        data = {'type': cat_type or 'all', 'count': len(cats), 'categories': cats}
        rows = ""
        for i, cat in enumerate(cats):
            rows += f"<tr><td>{i+1}</td><td>{cat}</td></tr>\n"
        body = f"""
  <h1>Kategorien (Type: {cat_type or 'all'}) &mdash; {len(cats)} Stueck</h1>
  <table>
    <tr><th>#</th><th>Kategorie</th></tr>
    {rows}
  </table>
  <h2>JSON</h2>
  <pre>{json.dumps(data, indent=2)}</pre>"""
        self._send_html(_html_page('Kategorien', body))

    def _handle_channels(self, params):
        ch_type = params.get('type', [None])[0]
        cat = params.get('category_id', [None])[0]
        # category_id in der URL entspricht 'category' in der DB
        channels = self.cfg.get_channels(type=ch_type, category=cat)
        gesamt = len(channels)
        # Hartes Limit: höchstens 500 Einträge je Anfrage, damit die
        # Zugangsdaten des Abos nicht in einer riesigen Antwort landen.
        # Der Parameter limit darf die Zahl nur verkleinern, niemals über
        # 500 erhöhen.
        limit = 500
        limit_roh = params.get('limit', [None])[0]
        if limit_roh is not None:
            try:
                limit = max(1, min(int(limit_roh), 500))
            except (TypeError, ValueError):
                limit = 500
        data = []
        for ch in channels[:limit]:
            data.append({
                'id': ch[0], 'provider_id': ch[1], 'name': ch[2],
                # Zugangsdaten stehen in jeder Stream-Adresse, deshalb wird
                # jede ausgegebene Adresse maskiert.
                'url': adresse_maskieren(ch[3]), 'logo': adresse_maskieren(ch[4]), 'category': ch[5],
                'tvg_id': ch[6], 'tvg_name': ch[7], 'type': ch[8],
            })
        geliefert = len(data)
        rows = ""
        for ch in data:
            rows += f"<tr><td>{ch['id']}</td><td>{ch['name']}</td><td>{ch['type']}</td><td>{ch['category']}</td><td>{ch['url'][:80] if ch['url'] else ''}</td></tr>\n"
        json_data = {'gesamt': gesamt, 'geliefert': geliefert, 'kanaele': data}
        body = f"""
  <h1>Kanaele (Type: {ch_type or 'all'}, Kategorie: {cat or 'all'}) &mdash; {geliefert} von {gesamt} Stueck</h1>
  <table>
    <tr><th>ID</th><th>Name</th><th>Type</th><th>Kategorie</th><th>URL</th></tr>
    {rows}
  </table>
  <h2>JSON</h2>
  <pre>{json.dumps(json_data, indent=2)}</pre>"""
        self._send_html(_html_page('Kanaele', body))

    def _handle_test_stream(self, params):
        url = params.get('url', [None])[0]
        if not url:
            self._send_json({'error': 'Parameter url= erforderlich'}, 400)
            return
        # Eine Adresse mit führendem Bindestrich wird abgelehnt, sonst
        # könnte ffprobe sie als Befehlszeilenoption lesen.
        if url.startswith('-'):
            self._send_json({'error': 'Adresse beginnt mit einem Bindestrich und wird abgelehnt'}, 400)
            return
        # Nur Adressen mit http:// oder https:// sind erlaubt, damit keine
        # lokalen Dateien oder anderen Protokolle geöffnet werden können.
        if not (url.startswith('http://') or url.startswith('https://')):
            self._send_json({'error': 'Nur Adressen mit http:// oder https:// sind erlaubt'}, 400)
            return
        # Das ffprobe-Ergebnis ist eine Innenansicht, deshalb steht dieser
        # Endpunkt zusätzlich hinter dem Zugangswort. Eine unzulässige
        # Adresse wird vorher mit 400 abgelehnt, ohne Innenansicht.
        if not self._token_ok():
            self._send_json({'error': 'Zugangswort fehlt oder ist falsch'}, 403)
            return
        result = self._test_stream_ffprobe(url)
        playable = result.get('playable', False)
        status_class = 'ok' if playable else 'error'
        status_text = 'ABSPIELBAR' if playable else 'NICHT ABSPIELBAR'
        body = f"""
  <h1>Stream-Test</h1>
  <div class="card">
    <p><strong>URL:</strong> <code>{url}</code></p>
    <p><strong>Status:</strong> <span class="stat-value {status_class}" style="font-size:16px;">{status_text}</span></p>
  </div>
  <h2>Details</h2>
  <pre>{json.dumps(result, indent=2)}</pre>"""
        self._send_html(_html_page('Stream-Test', body))

    def _handle_logs(self, params):
        n = int(params.get('n', ['50'])[0])
        n = min(n, 500)
        # Jede Protokollzeile kann Zugangsdaten enthalten, deshalb wird
        # jede ausgegebene Zeile maskiert, auch das Muster user=...
        lines = [adresse_maskieren(zeile) for zeile in self._get_log_lines(n)]
        log_html = "\n".join(lines)
        body = f"""
  <h1>Logs (letzte {len(lines)} Zeilen)</h1>
  <pre>{log_html}</pre>"""
        self._send_html(_html_page('Logs', body))

    def _handle_fds(self):
        fd_count = self._get_fd_count()
        data = {'fds': fd_count, 'pid': os.getpid()}
        fd_class = 'ok'
        if fd_count > 800: fd_class = 'warn'
        if fd_count > 950: fd_class = 'error'
        body = f"""
  <h1>File Descriptors</h1>
  <div class="card">
    <div class="stat"><div class="stat-label">Offene FDs</div><div class="stat-value {fd_class}">{fd_count}</div></div>
    <div class="stat"><div class="stat-label">PID</div><div class="stat-value">{os.getpid()}</div></div>
  </div>
  <h2>JSON</h2>
  <pre>{json.dumps(data, indent=2)}</pre>"""
        self._send_html(_html_page('File Descriptors', body))

    def _handle_threads(self):
        count = threading.active_count()
        data = {'active_threads': count}
        # Thread-Liste
        threads_info = []
        for t in threading.enumerate():
            threads_info.append({'name': t.name, 'daemon': t.daemon, 'alive': t.is_alive()})
        data['threads'] = threads_info
        rows = ""
        for t in threads_info:
            d = 'daemon' if t['daemon'] else 'main'
            a = 'alive' if t['alive'] else 'dead'
            rows += f"<tr><td>{t['name']}</td><td>{d}</td><td>{a}</td></tr>\n"
        body = f"""
  <h1>Threads ({count} aktiv)</h1>
  <table>
    <tr><th>Name</th><th>Typ</th><th>Status</th></tr>
    {rows}
  </table>
  <h2>JSON</h2>
  <pre>{json.dumps(data, indent=2)}</pre>"""
        self._send_html(_html_page('Threads', body))

    def _handle_restart(self):
        # Der Neustart darf nur mit dem beim Start erzeugten Zugangswort
        # ausgelöst werden, sonst könnte jeder im Netz die Anwendung neu
        # starten. Ohne passendes Wort: Antwort 403.
        if not self._token_ok():
            self._send_json({'error': 'Neustart verweigert: Zugangswort fehlt oder ist falsch'}, 403)
            return
        self._send_json({'message': 'App wird neu gestartet...', 'pid': os.getpid()})
        logger.warning('Neustart durch Debug-Server angefordert (POST /restart)')
        # Kurz warten damit Response gesendet wird
        threading.Timer(1.0, self._do_restart).start()

    def _do_restart(self):
        """App neu starten via os.execv."""
        python = sys.executable
        os.execv(python, [python] + sys.argv)

    def log_message(self, format, *args):
        """Logging fuer HTTP-Requests."""
        logger.info(f"{self.client_address[0]} - {format % args}")


# ── DebugServer ──────────────────────────────────────────────────────

class DebugServer:
    """Thread-safe HTTP Debug Server fuer SMarTrPlay.

    Laeuft in einem eigenen Thread und liefert Diagnose-Endpunkte
    auf dem angegebenen Port (Default: 8421).
    """

    def __init__(self, port=8421, config=None):
        self.port = port
        self.config = config or Config()
        # Zugangswort für den Neustart und die Endpunkte mit
        # Innenansichten. Es wird beim Start einmalig im Protokoll
        # hinterlegt, damit der Besitzer es dort nachlesen kann.
        self.zugangswort = secrets.token_urlsafe(16)
        self._zugangswort_im_protokoll = False
        self._server = None
        self._thread = None
        self._running = False
        self.start_time = time.time()

    def start(self):
        """Startet den Debug-Server in einem Hintergrund-Thread."""
        if self._running:
            logger.warning("Debug-Server laeuft bereits")
            return
        try:
            # Bindung nur auf die Loopback-Adresse: Der Diagnoseserver gibt
            # Zugangsdaten des IPTV-Abos und Innenansichten des Prozesses
            # preis und hat keine Anmeldung. Auf 0.0.0.0 wäre all das von
            # jedem Gerät im Netz abrufbar, deshalb ist der Server
            # ausschließlich vom selben Rechner erreichbar.
            self._server = HTTPServer(('127.0.0.1', self.port), DebugHandler)
            self._server.app_config = self.config
            self._server.start_time = self.start_time
            self._server.zugangswort = self.zugangswort
            self._server.timeout = 1
            self._thread = threading.Thread(
                target=self._serve_loop,
                name='DebugServerThread',
                daemon=True
            )
            self._running = True
            self._thread.start()
            # Zugangswort genau einmal beim Start ins Protokoll schreiben,
            # damit der Besitzer es aus dem Protokoll lesen kann.
            if not self._zugangswort_im_protokoll:
                logger.info(f"Debug-Server Zugangswort für geschützte Endpunkte und Neustart: {self.zugangswort}")
                self._zugangswort_im_protokoll = True
            logger.info(f"Debug-Server gestartet auf Port {self.port}")
        except OSError as e:
            logger.error(f"Debug-Server konnte nicht starten (Port {self.port}): {e}")
            self._running = False
        except Exception as e:
            logger.error(f"Debug-Server Fehler: {e}", exc_info=True)
            self._running = False

    def _serve_loop(self):
        """HTTP-Server Loop (non-blocking poll)."""
        while self._running:
            try:
                self._server.handle_request()
            except Exception as e:
                if self._running:
                    logger.error(f"Debug-Server handle_request Fehler: {e}")

    def stop(self):
        """Stoppt den Debug-Server sauber."""
        if not self._running:
            return
        self._running = False
        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3)
            if self._server:
                self._server.server_close()
            logger.info("Debug-Server gestoppt")
        except Exception as e:
            logger.error(f"Debug-Server Stop Fehler: {e}")
        finally:
            self._server = None
            self._thread = None

    def is_running(self):
        """Gibt True zurueck wenn der Server aktiv ist."""
        return self._running
