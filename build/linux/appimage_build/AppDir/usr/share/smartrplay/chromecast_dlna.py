#!/usr/bin/env python3
"""
SMarTrPlay v4 — chromecast_dlna.py
DLNA/UPnP Discovery & Chromecast-style Casting Widget.

Only Python stdlib + PyQt5. Compatible with /usr/bin/python3.
SMarTr Brand Design: #0A0F1E / #1bf1fb / #8D7CF6.
"""

import socket
import threading
import time
import struct
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QLineEdit, QComboBox, QMessageBox
)
from PyQt5.QtGui import QFont, QColor

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
QListWidget {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background-color: {SMARTR_VIOLET};
    color: {SMARTR_TEXT};
}}
QLineEdit {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 4px;
    padding: 6px;
}}
QComboBox {{
    background-color: {SMARTR_BG_LIGHT};
    color: {SMARTR_TEXT};
    border: 1px solid {SMARTR_VIOLET};
    border-radius: 4px;
    padding: 6px;
}}
"""

# ─── SSDP / UPnP Constants ─────────────────────────────────────────
SSDP_ADDR  = "239.255.255.250"
SSDP_PORT  = 1900
SSDP_MSEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 3\r\n"
    "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
    "\r\n"
)

AV_TRANSPORT_NS = "urn:schemas-upnp-org:service:AVTransport:1"

# ─── Data Model ────────────────────────────────────────────────────

@dataclass
class DLNADevice:
    """Represents a discovered DLNA/UPnP MediaRenderer device."""
    name: str = ""
    ip: str = ""
    port: int = 0
    control_url: str = ""
    location: str = ""
    friendly_name: str = ""
    manufacturer: str = ""
    model_name: str = ""

    def __str__(self) -> str:
        return f"{self.friendly_name or self.name} ({self.ip}:{self.port})"


# ─── DLNA Discovery (SSDP) ─────────────────────────────────────────

class DLNADiscovery(QObject):
    """Discovers DLNA MediaRenderer devices via SSDP M-SEARCH."""

    devices_found = pyqtSignal(list)
    discovery_finished = pyqtSignal()

    def __init__(self, timeout: int = 5):
        super().__init__()
        self._timeout = timeout

    def discover(self) -> List[DLNADevice]:
        """Send SSDP M-SEARCH and return list of discovered devices."""
        devices = []
        seen_locations = set()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self._timeout)

        try:
            sock.sendto(SSDP_MSEARCH.encode("utf-8"), (SSDP_ADDR, SSDP_PORT))
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                    response = data.decode("utf-8", errors="replace")
                    location = self._parse_ssdp_header(response, "LOCATION")
                    if not location or location in seen_locations:
                        continue
                    seen_locations.add(location)
                    device = self._fetch_device_description(location)
                    if device:
                        devices.append(device)
                        self.devices_found.emit([device])
                except socket.timeout:
                    break
        except Exception:
            pass
        finally:
            sock.close()

        self.discovery_finished.emit()
        return devices

    @staticmethod
    def _parse_ssdp_header(response: str, header_name: str) -> str:
        """Extract a header value from an SSDP HTTP response."""
        lines = response.split("\r\n")
        for line in lines:
            if line.lower().startswith(header_name.lower() + ":"):
                return line.split(":", 1)[1].strip()
        return ""

    @staticmethod
    def _fetch_device_description(location: str) -> Optional[DLNADevice]:
        """Fetch and parse device description XML from LOCATION URL."""
        try:
            req = urllib.request.Request(location, headers={"User-Agent": "SMarTrPlay/4.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                xml_data = resp.read().decode("utf-8", errors="replace")
        except Exception:
            return None

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return None

        # Strip namespace helper
        def local_tag(tag: str) -> str:
            return tag.split("}")[-1] if "}" in tag else tag

        device_elem = None
        for elem in root.iter():
            if local_tag(elem.tag) == "device":
                device_elem = elem
                break
        if device_elem is None:
            return None

        def get_child(parent, name: str) -> str:
            for child in parent:
                if local_tag(child.tag) == name:
                    return (child.text or "").strip()
            return ""

        friendly = get_child(device_elem, "friendlyName")
        manufacturer = get_child(device_elem, "manufacturer")
        model = get_child(device_elem, "modelName")

        # Parse URLBase
        url_base = get_child(root, "URLBase")
        if not url_base:
            url_base = location.rsplit("/", 1)[0] + "/"
        parsed = urllib.parse.urlparse(location)
        ip = parsed.hostname or ""
        port = parsed.port or 80

        # Find AVTransport control URL
        control_url = ""
        for svc in device_elem.iter():
            if local_tag(svc.tag) == "service":
                stype = get_child(svc, "serviceType")
                curl = get_child(svc, "controlURL")
                if AV_TRANSPORT_NS in stype and curl:
                    if curl.startswith("http"):
                        control_url = curl
                    else:
                        control_url = urllib.parse.urljoin(url_base, curl)
                    break

        if not control_url:
            return None

        return DLNADevice(
            name=friendly or "Unknown",
            ip=ip,
            port=port,
            control_url=control_url,
            location=location,
            friendly_name=friendly,
            manufacturer=manufacturer,
            model_name=model,
        )


class DiscoveryThread(QThread):
    """Background thread for SSDP discovery to keep UI responsive."""
    device_found = pyqtSignal(object)
    finished_signal = pyqtSignal(list)

    def __init__(self, timeout: int = 5):
        super().__init__()
        self._timeout = timeout
        self._discovery = DLNADiscovery(timeout)
        self._discovery.devices_found.connect(
            lambda devs: [self.device_found.emit(d) for d in devs]
        )

    def run(self):
        devices = self._discovery.discover()
        self.finished_signal.emit(devices)


# ─── DLNA Renderer (SOAP AVTransport) ──────────────────────────────

class DLNARenderer:
    """Sends SOAP commands to a DLNA MediaRenderer via AVTransport service."""

    def __init__(self, device: DLNADevice):
        self.device = device

    def _soap_request(self, action: str, body_xml: str) -> str:
        """Build and send a SOAP request to the AVTransport control URL."""
        soap_envelope = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
            ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            f'<s:Body><u:{action} xmlns:u="{AV_TRANSPORT_NS}">{body_xml}</u:{action}></s:Body>'
            '</s:Envelope>'
        )
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{AV_TRANSPORT_NS}#{action}"',
            "User-Agent": "SMarTrPlay/4.0",
        }
        data = soap_envelope.encode("utf-8")
        req = urllib.request.Request(self.device.control_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            return f"ERROR: {e}"

    def set_media(self, url: str, mime_type: str = "video/mp4") -> str:
        """Set a media URI on the renderer (SetMedia / SetAVTransportURI)."""
        escaped_url = url.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        meta = (
            '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
            ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
            ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
            f'<item id="1" parentID="0" restricted="1">'
            f'<dc:title>SMarTrPlay Stream</dc:title>'
            f'<upnp:class>object.item.videoItem</upnp:class>'
            f'<res protocolInfo="http-get:*:{mime_type}:*">{escaped_url}</res>'
            '</item></DIDL-Lite>'
        )
        body = (
            '<InstanceID>0</InstanceID>'
            f'<CurrentURI>{escaped_url}</CurrentURI>'
            f'<CurrentURIMetaData>{meta}</CurrentURIMetaData>'
        )
        return self._soap_request("SetAVTransportURI", body)

    def play(self) -> str:
        """Send Play command."""
        return self._soap_request("Play", '<InstanceID>0</InstanceID><Speed>1</Speed>')

    def stop(self) -> str:
        """Send Stop command."""
        return self._soap_request("Stop", '<InstanceID>0</InstanceID>')

    def pause(self) -> str:
        """Send Pause command."""
        return self._soap_request("Pause", '<InstanceID>0</InstanceID>')

    def seek(self, target: str) -> str:
        """Send Seek command. target format: HH:MM:SS or REL_TIME."""
        body = f'<InstanceID>0</InstanceID><Unit>REL_TIME</Unit><Target>{target}</Target>'
        return self._soap_request("Seek", body)

    def get_position(self) -> str:
        """Query current position info."""
        return self._soap_request("GetPositionInfo", '<InstanceID>0</InstanceID>')

    def get_transport_info(self) -> str:
        """Query current transport state."""
        return self._soap_request("GetTransportInfo", '<InstanceID>0</InstanceID>')


# ─── Cast Widget ───────────────────────────────────────────────────

class CastWidget(QWidget):
    """Widget for DLNA device discovery and casting control."""

    cast_requested = pyqtSignal(str)  # emits stream URL when user wants to cast
    play_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices: List[DLNADevice] = []
        self._renderer: Optional[DLNARenderer] = None
        self._discovery_thread: Optional[DiscoveryThread] = None
        self._init_ui()
        self.setStyleSheet(SMARTR_QSS)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QLabel("🖥️  DLNA / Cast")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet(f"color: {SMARTR_CYAN};")
        layout.addWidget(header)

        # Device list
        self._device_list = QListWidget()
        self._device_list.setMinimumHeight(140)
        layout.addWidget(self._device_list)

        # Stream URL input
        url_label = QLabel("Stream URL:")
        url_label.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(url_label)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("http://…/stream.m3u8 oder .mp4")
        layout.addWidget(self._url_input)

        # MIME type selector
        mime_label = QLabel("Format:")
        mime_label.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(mime_label)

        self._mime_combo = QComboBox()
        self._mime_combo.addItems([
            "video/mp4", "video/x-matroska", "video/x-msvideo",
            "audio/mpeg", "audio/mp4", "application/x-mpegURL",
        ])
        layout.addWidget(self._mime_combo)

        # Buttons
        btn_row1 = QHBoxLayout()
        self._btn_refresh = QPushButton("🔄 Refresh")
        self._btn_refresh.clicked.connect(self._on_refresh)
        btn_row1.addWidget(self._btn_refresh)

        self._btn_cast = QPushButton("📡 Cast")
        self._btn_cast.clicked.connect(self._on_cast)
        btn_row1.addWidget(self._btn_cast)
        layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self._btn_play = QPushButton("▶ Play")
        self._btn_play.clicked.connect(self._on_play)
        btn_row2.addWidget(self._btn_play)

        self._btn_stop = QPushButton("⏹ Stop")
        self._btn_stop.clicked.connect(self._on_stop)
        btn_row2.addWidget(self._btn_stop)
        layout.addLayout(btn_row2)

        btn_row3 = QHBoxLayout()
        self._btn_pause = QPushButton("⏸ Pause")
        self._btn_pause.clicked.connect(self._on_pause)
        btn_row3.addWidget(self._btn_pause)

        self._btn_seek = QPushButton("⏩ Seek")
        self._btn_seek.clicked.connect(self._on_seek)
        btn_row3.addWidget(self._btn_seek)
        layout.addLayout(btn_row3)

        # Seek input
        self._seek_input = QLineEdit()
        self._seek_input.setPlaceholderText("HH:MM:SS")
        layout.addWidget(self._seek_input)

        # Status label
        self._status_label = QLabel("Bereit. Auf Refresh klicken, um Geräte zu suchen.")
        self._status_label.setStyleSheet(f"color: {SMARTR_TEXT_DIM}; font-size: 11px;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _on_refresh(self):
        """Start SSDP device discovery in background thread."""
        self._device_list.clear()
        self._devices.clear()
        self._status_label.setText("Suche DLNA-Geräte …")
        self._btn_refresh.setEnabled(False)

        self._discovery_thread = DiscoveryThread(timeout=5)
        self._discovery_thread.device_found.connect(self._on_device_found)
        self._discovery_thread.finished_signal.connect(self._on_discovery_done)
        self._discovery_thread.start()

    def _on_device_found(self, device: DLNADevice):
        """Add a newly discovered device to the list."""
        self._devices.append(device)
        item = QListWidgetItem(str(device))
        item.setData(Qt.UserRole, len(self._devices) - 1)
        self._device_list.addItem(item)

    def _on_discovery_done(self, devices: list):
        """Discovery complete callback."""
        self._btn_refresh.setEnabled(True)
        count = len(self._devices)
        if count == 0:
            self._status_label.setText("Keine DLNA-Geräte gefunden.")
        else:
            self._status_label.setText(f"{count} DLNA-Gerät(e) gefunden.")

    def _get_selected_device(self) -> Optional[DLNADevice]:
        """Return the currently selected DLNA device or None."""
        row = self._device_list.currentRow()
        if row < 0 or row >= len(self._devices):
            QMessageBox.warning(self, "Kein Gerät", "Bitte zuerst ein DLNA-Gerät auswählen.")
            return None
        return self._devices[row]

    def _on_cast(self):
        """Cast the stream URL to the selected device."""
        device = self._get_selected_device()
        if not device:
            return
        url = self._url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Keine URL", "Bitte eine Stream-URL eingeben.")
            return
        mime = self._mime_combo.currentText()
        self._renderer = DLNARenderer(device)
        self._status_label.setText(f"Caste zu {device.friendly_name} …")
        result = self._renderer.set_media(url, mime)
        if "ERROR" in result:
            self._status_label.setText(f"Fehler: {result}")
        else:
            # Auto-play after setting media
            play_result = self._renderer.play()
            if "ERROR" not in play_result:
                self._status_label.setText(f"Wird auf {device.friendly_name} wiedergegeben.")
                self.cast_requested.emit(url)
            else:
                self._status_label.setText(f"SetMedia OK, aber Play-Fehler: {play_result}")

    def _on_play(self):
        if self._renderer:
            result = self._renderer.play()
            self._status_label.setText(f"Play: {result}" if "ERROR" in result else "Wiedergabe gestartet.")
            self.play_requested.emit()
        else:
            QMessageBox.information(self, "Kein Gerät", "Zuerst Cast verwenden.")

    def _on_stop(self):
        if self._renderer:
            result = self._renderer.stop()
            self._status_label.setText(f"Stop: {result}" if "ERROR" in result else "Wiedergabe gestoppt.")
            self.stop_requested.emit()
        else:
            QMessageBox.information(self, "Kein Gerät", "Zuerst Cast verwenden.")

    def _on_pause(self):
        if self._renderer:
            result = self._renderer.pause()
            self._status_label.setText(f"Pause: {result}" if "ERROR" in result else "Pause.")
        else:
            QMessageBox.information(self, "Kein Gerät", "Zuerst Cast verwenden.")

    def _on_seek(self):
        if self._renderer:
            target = self._seek_input.text().strip()
            if not target:
                QMessageBox.warning(self, "Kein Seek-Target", "Bitte HH:MM:SS eingeben.")
                return
            result = self._renderer.seek(target)
            self._status_label.setText(f"Seek: {result}" if "ERROR" in result else f"Gesprungen zu {target}.")
        else:
            QMessageBox.information(self, "Kein Gerät", "Zuerst Cast verwenden.")

    def closeEvent(self, event):
        if self._discovery_thread and self._discovery_thread.isRunning():
            self._discovery_thread.quit()
            self._discovery_thread.wait(2000)
        super().closeEvent(event)


# ─── Module Entry Point (test) ─────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    widget = CastWidget()
    widget.setWindowTitle("SMarTrPlay — DLNA / Cast")
    widget.resize(420, 520)
    widget.show()
    sys.exit(app.exec_())
