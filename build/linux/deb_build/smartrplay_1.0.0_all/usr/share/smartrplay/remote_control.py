#!/usr/bin/env python3
"""
SMarTrPlay v4 — remote_control.py
Web Remote Control Server + Widget.

Only Python stdlib + PyQt5. Compatible with /usr/bin/python3.
SMarTr Brand Design: #0A0F1E / #1bf1fb / #8D7CF6.
"""

import json
import threading
import socket
import secrets
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Optional, Any

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit
)
from PyQt5.QtGui import QFont

# ─── SMarTr Brand Design ───────────────────────────────────────────
SMARTR_BG       = "#0A0F1E"
SMARTR_BG_LIGHT = "#121831"
SMARTR_CYAN     = "#1bf1fb"
SMARTR_VIOLET   = "#8D7CF6"
SMARTR_TEXT     = "#E8ECF7"
SMARTR_TEXT_DIM = "#7A8299"

SMARTR_QSS = f"""
QWidget {{
    background-color: {SMARTR_BG};
    color: {SMARTR_TEXT};
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
}}
QLabel {{
    color: {SMARTR_TEXT};
}}
QPushButton {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_CYAN};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {SMARTR_VIOLET};
    color: {SMARTR_TEXT};
}}
QPushButton:pressed {{
    background-color: {SMARTR_CYAN};
    color: {SMARTR_BG};
}}
QPushButton:disabled {{
    color: {SMARTR_TEXT_DIM};
    border-color: {SMARTR_TEXT_DIM};
}}
QLineEdit {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 4px;
    padding: 6px;
}}
"""

# ─── Mobile Web UI (HTML/CSS/JS) ───────────────────────────────────

WEB_UI_HTML = r'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>SMarTrPlay Remote</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #0A0F1E;
    color: #E8ECF7;
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
}
.header {
    width: 100%;
    padding: 20px;
    text-align: center;
    background: linear-gradient(135deg, #0A0F1E 0%, #121831 100%);
    border-bottom: 2px solid #8D7CF6;
}
.header h1 {
    font-size: 22px;
    color: #1bf1fb;
    letter-spacing: 2px;
}
.header p {
    color: #7A8299;
    font-size: 12px;
    margin-top: 4px;
}
.controls {
    width: 100%;
    max-width: 400px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.section {
    background: #121831;
    border: 1px solid #8D7CF6;
    border-radius: 12px;
    padding: 16px;
}
.section-title {
    color: #1bf1fb;
    font-size: 14px;
    font-weight: bold;
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.btn-row {
    display: flex;
    gap: 12px;
    justify-content: center;
}
.btn {
    background: #121831;
    color: #1bf1fb;
    border: 2px solid #8D7CF6;
    border-radius: 10px;
    padding: 14px 24px;
    font-size: 18px;
    font-weight: bold;
    cursor: pointer;
    flex: 1;
    transition: all 0.2s;
}
.btn:hover {
    background: #8D7CF6;
    color: #E8ECF7;
}
.btn:active {
    background: #1bf1fb;
    color: #0A0F1E;
}
.btn-large {
    font-size: 28px;
    padding: 20px;
}
.volume-row {
    display: flex;
    align-items: center;
    gap: 12px;
}
.volume-slider {
    flex: 1;
    -webkit-appearance: none;
    height: 8px;
    background: #0A0F1E;
    border: 1px solid #8D7CF6;
    border-radius: 4px;
    outline: none;
}
.volume-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 24px;
    height: 24px;
    background: #1bf1fb;
    border-radius: 50%;
    cursor: pointer;
}
.volume-label {
    color: #1bf1fb;
    font-size: 16px;
    font-weight: bold;
    min-width: 40px;
    text-align: center;
}
.channel-list {
    max-height: 300px;
    overflow-y: auto;
}
.channel-item {
    background: #0A0F1E;
    color: #E8ECF7;
    border: 1px solid #8D7CF6;
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 8px;
    cursor: pointer;
    font-size: 16px;
    transition: all 0.2s;
}
.channel-item:hover {
    background: #8D7CF6;
    color: #E8ECF7;
}
.channel-item.active {
    background: #1bf1fb;
    color: #0A0F1E;
    font-weight: bold;
}
.status-bar {
    width: 100%;
    max-width: 400px;
    padding: 12px 20px;
    text-align: center;
}
#statusText {
    color: #7A8299;
    font-size: 12px;
}
.toast {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    background: #8D7CF6;
    color: #E8ECF7;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 14px;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
}
.toast.show { opacity: 1; }
</style>
</head>
<body>
<div class="header">
    <h1>SMarTrPlay Remote</h1>
    <p>Web Remote Control v4</p>
</div>
<div class="controls">
    <div class="section">
        <div class="section-title">Wiedergabe</div>
        <div class="btn-row">
            <button class="btn btn-large" onclick="sendCmd('play')">&#9654;</button>
            <button class="btn btn-large" onclick="sendCmd('pause')">&#10074;&#10074;</button>
            <button class="btn btn-large" onclick="sendCmd('stop')">&#9632;</button>
        </div>
    </div>
    <div class="section">
        <div class="section-title">Lautstaerke</div>
        <div class="volume-row">
            <button class="btn" onclick="adjustVol(-10)">&#8722;</button>
            <input type="range" class="volume-slider" id="volSlider" min="0" max="100" value="50" oninput="setVolume(this.value)">
            <button class="btn" onclick="adjustVol(10)">+</button>
            <span class="volume-label" id="volLabel">50</span>
        </div>
    </div>
    <div class="section">
        <div class="section-title">Kanaele</div>
        <div class="channel-list" id="channelList">
            <div style="color:#7A8299; text-align:center; padding:20px;">Kanaele werden geladen ...</div>
        </div>
    </div>
</div>
<div class="status-bar">
    <span id="statusText">Verbunden mit SMarTrPlay</span>
</div>
<div class="toast" id="toast"></div>
<script>
function showToast(msg) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(function() { t.classList.remove('show'); }, 2000);
}
function sendCmd(cmd) {
    fetch('/api/' + cmd, { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) { showToast(d.message || 'OK'); })
        .catch(function(e) { showToast('Fehler: ' + e); });
}
function setVolume(vol) {
    document.getElementById('volLabel').textContent = vol;
    fetch('/api/volume', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ volume: parseInt(vol) }) })
        .then(function(r) { return r.json(); })
        .catch(function(e) { showToast('Fehler: ' + e); });
}
function adjustVol(delta) {
    var slider = document.getElementById('volSlider');
    var vol = Math.max(0, Math.min(100, parseInt(slider.value) + delta));
    slider.value = vol;
    setVolume(vol);
}
function loadChannels() {
    fetch('/api/channels')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var list = document.getElementById('channelList');
            list.innerHTML = '';
            if (!data.channels || data.channels.length === 0) {
                list.innerHTML = '<div style="color:#7A8299; text-align:center; padding:20px;">Keine Kanaele verfuegbar</div>';
                return;
            }
            data.channels.forEach(function(ch) {
                var div = document.createElement('div');
                div.className = 'channel-item';
                div.textContent = ch.name;
                div.onclick = function() { switchChannel(ch.id); };
                list.appendChild(div);
            });
        })
        .catch(function(e) {
            document.getElementById('channelList').innerHTML = '<div style="color:#ff4444;">Fehler beim Laden</div>';
        });
}
function switchChannel(id) {
    fetch('/api/channel', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ channel_id: id }) })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            showToast('Kanal: ' + (d.message || id));
            loadStatus();
        })
        .catch(function(e) { showToast('Fehler: ' + e); });
}
function loadStatus() {
    fetch('/api/status')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var st = document.getElementById('statusText');
            st.textContent = 'Status: ' + (data.state || 'unknown') + ' | Kanal: ' + (data.channel || '-') + ' | Vol: ' + (data.volume || 0);
            if (data.volume !== undefined) {
                document.getElementById('volSlider').value = data.volume;
                document.getElementById('volLabel').textContent = data.volume;
            }
        })
        .catch(function(e) {});
}
loadChannels();
loadStatus();
setInterval(loadStatus, 5000);
</script>
</body>
</html>'''


# ─── Remote Control Server ─────────────────────────────────────────

class RemoteControlHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the remote control API."""

    # Class-level reference to the controller (set by RemoteControlServer)
    _controller: Optional['RemoteControlController'] = None
    _auth_token: str = ""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _check_auth(self) -> bool:
        """Validate auth token from query parameter or Authorization header."""
        if not self._auth_token:
            return True  # No token set = open mode (backward compat)
        # Check Authorization header
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            if token == self._auth_token:
                return True
        # Check query parameter ?token=...
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        token_list = params.get('token', [])
        if token_list and token_list[0] == self._auth_token:
            return True
        return False

    def _send_unauthorized(self):
        """Send 401 Unauthorized response."""
        body = json.dumps({"error": "Unauthorized"}).encode('utf-8')
        self.send_response(401)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests."""
        if not self._check_auth():
            self._send_unauthorized()
            return
        if self.path == '/' or self.path == '/index.html' or self.path.startswith('/?token=') or self.path.startswith('/index.html?token='):
            self._send_html(WEB_UI_HTML)
        elif self.path.startswith('/api/channels'):
            channels = self._get_channels()
            self._send_json({"channels": channels})
        elif self.path.startswith('/api/status'):
            status = self._get_status()
            self._send_json(status)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        if not self._check_auth():
            self._send_unauthorized()
            return
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8', errors='replace') if content_length else '{}'
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if self.path == '/api/play':
            self._controller_action('play')
            self._send_json({"message": "Wiedergabe gestartet", "state": "playing"})
        elif self.path == '/api/pause':
            self._controller_action('pause')
            self._send_json({"message": "Pause", "state": "paused"})
        elif self.path == '/api/stop':
            self._controller_action('stop')
            self._send_json({"message": "Stopp", "state": "stopped"})
        elif self.path == '/api/volume':
            vol = int(data.get('volume', 50))
            vol = max(0, min(100, vol))
            self._controller_action('volume', volume=vol)
            self._send_json({"message": f"Lautstaerke: {vol}%", "volume": vol})
        elif self.path == '/api/channel':
            ch_id = data.get('channel_id', 0)
            self._controller_action('channel', channel_id=ch_id)
            self._send_json({"message": f"Kanal gewechselt", "channel": ch_id})
        else:
            self._send_json({"error": "Not found"}, 404)

    def _controller_action(self, action: str, **kwargs):
        """Forward action to the controller if set."""
        if self._controller:
            self._controller.handle_action(action, **kwargs)

    def _get_channels(self) -> List[Dict[str, Any]]:
        """Get channel list from controller."""
        if self._controller:
            return self._controller.get_channels()
        return []

    def _get_status(self) -> Dict[str, Any]:
        """Get player status from controller."""
        if self._controller:
            return self._controller.get_status()
        return {"state": "unknown", "channel": "", "volume": 0}

    def _send_json(self, data: dict, code: int = 200):
        """Send a JSON response."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:*,http://127.0.0.1:*')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, code: int = 200):
        """Send an HTML response."""
        body = html.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RemoteControlController(QObject):
    """Bridge between the HTTP server and the PyQt5 player frontend.

    Emits pyqtSignals for each player action. The widget connects
    these signals to the actual player controls.
    """

    play_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    volume_requested = pyqtSignal(int)
    channel_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channels: List[Dict[str, Any]] = []
        self._current_channel: int = 0
        self._volume: int = 50
        self._state: str = "stopped"
        self._server: Optional['RemoteControlServer'] = None

    def set_server(self, server: 'RemoteControlServer'):
        """Set a reference to the RemoteControlServer for stop_server()."""
        self._server = server

    def stop_server(self):
        """Stop the associated HTTP server if one is set."""
        if self._server is not None:
            try:
                self._server.stop()
            except Exception:
                pass
            self._server = None

    def set_channels(self, channels: List[Dict[str, Any]]):
        """Update the channel list."""
        self._channels = channels

    def add_channel(self, channel_id: int, name: str, url: str = ""):
        """Add a single channel."""
        self._channels.append({"id": channel_id, "name": name, "url": url})

    def get_channels(self) -> List[Dict[str, Any]]:
        """Return current channel list."""
        return self._channels

    def get_status(self) -> Dict[str, Any]:
        """Return current player status."""
        ch_name = ""
        for ch in self._channels:
            if ch.get("id") == self._current_channel:
                ch_name = ch.get("name", "")
                break
        return {
            "state": self._state,
            "channel": ch_name,
            "channel_id": self._current_channel,
            "volume": self._volume,
        }

    def handle_action(self, action: str, **kwargs):
        """Handle an incoming API action and emit the corresponding signal."""
        if action == 'play':
            self._state = 'playing'
            self.play_requested.emit()
        elif action == 'pause':
            self._state = 'paused'
            self.pause_requested.emit()
        elif action == 'stop':
            self._state = 'stopped'
            self.stop_requested.emit()
        elif action == 'volume':
            self._volume = kwargs.get('volume', 50)
            self.volume_requested.emit(self._volume)
        elif action == 'channel':
            self._current_channel = kwargs.get('channel_id', 0)
            self._state = 'playing'
            self.channel_requested.emit(self._current_channel)


class RemoteControlServer:
    """Threaded HTTP server for the remote control web interface."""

    def __init__(self, port: int = 8420, controller: Optional[RemoteControlController] = None):
        self._port = port
        self._controller = controller or RemoteControlController()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._auth_token: str = secrets.token_hex(16)

    @property
    def auth_token(self) -> str:
        return self._auth_token

    @property
    def controller(self) -> RemoteControlController:
        return self._controller

    @property
    def port(self) -> int:
        return self._port

    def get_local_ip(self) -> str:
        """Determine the local network IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    def get_url(self) -> str:
        """Return the full URL the server is accessible at."""
        return f"http://{self.get_local_ip()}:{self._port}"

    def start(self):
        """Start the HTTP server in a background thread."""
        if self._server is not None:
            return  # Already running

        RemoteControlHandler._controller = self._controller
        RemoteControlHandler._auth_token = self._auth_token
        self._server = ThreadingHTTPServer(('0.0.0.0', self._port), RemoteControlHandler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the HTTP server."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None

    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self._server is not None


# ─── Remote Control Widget ──────────────────────────────────────────

class RemoteControlWidget(QWidget):
    """Widget for starting/stopping the web remote control server."""

    server_started = pyqtSignal(str)
    server_stopped = pyqtSignal()

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        if controller is not None:
            self._server = RemoteControlServer(port=8420, controller=controller)
            controller.set_server(self._server)
        else:
            self._server = RemoteControlServer(port=8420)
        self._init_ui()
        self.setStyleSheet(SMARTR_QSS)

    def start_server(self):
        """Start the remote control server (convenience method for external callers)."""
        self._on_start()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QLabel("📱  Web Remote Control")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet(f"color: {SMARTR_CYAN};")
        layout.addWidget(header)

        # Status
        self._status_label = QLabel("Server: gestoppt")
        self._status_label.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 12px;")
        layout.addWidget(self._status_label)

        # URL display
        self._url_label = QLabel("URL: —")
        self._url_label.setStyleSheet(
            f"color: {SMARTR_CYAN}; font-size: 13px; font-family: 'Courier', monospace;"
        )
        layout.addWidget(self._url_label)

        # QR hint
        self._qr_hint = QLabel(
            "Oeffne die URL auf deinem Smartphone\n"
            "um SMarTrPlay fernzusteuern."
        )
        self._qr_hint.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 11px;")
        self._qr_hint.setWordWrap(True)
        layout.addWidget(self._qr_hint)

        # Token display
        self._token_label = QLabel("Auth-Token: —")
        self._token_label.setStyleSheet(
            f"color: {SMARTR_VIOLET}; font-size: 11px; font-family: 'Courier', monospace;"
        )
        self._token_label.setWordWrap(True)
        layout.addWidget(self._token_label)

        # Buttons
        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("▶ Server starten")
        self._btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self._btn_start)

        self._btn_stop = QPushButton("⏹ Server stoppen")
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_stop.setEnabled(False)
        btn_row.addWidget(self._btn_stop)
        layout.addLayout(btn_row)

        # Port info
        port_label = QLabel("Port: 8420")
        port_label.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(port_label)

        layout.addStretch()

    @property
    def server(self) -> RemoteControlServer:
        """Expose the underlying server for channel/status configuration."""
        return self._server

    def _on_start(self):
        """Start the remote control server."""
        try:
            self._server.start()
            url = self._server.get_url()
            token = self._server.auth_token
            self._url_label.setText(f"URL: {url}")
            self._token_label.setText(f"Auth-Token: {token}")
            self._status_label.setText("Server: laeuft")
            self._status_label.setStyleSheet(f"color: {SMARTR_CYAN}; font-size: 12px;")
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self.server_started.emit(url)
        except Exception as e:
            self._status_label.setText(f"Fehler: {e}")
            self._status_label.setStyleSheet(f"color: #ff4444; font-size: 12px;")

    def _on_stop(self):
        """Stop the remote control server."""
        self._server.stop()
        self._url_label.setText("URL: —")
        self._status_label.setText("Server: gestoppt")
        self._status_label.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 12px;")
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self.server_stopped.emit()

    def closeEvent(self, event):
        if self._server.is_running():
            self._server.stop()
        super().closeEvent(event)


# ─── Module Entry Point (test) ─────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    widget = RemoteControlWidget()
    widget.setWindowTitle("SMarTrPlay — Remote Control")
    widget.resize(360, 280)
    widget.show()
    sys.exit(app.exec_())
