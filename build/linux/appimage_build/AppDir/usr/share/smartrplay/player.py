#!/usr/bin/env python3
"""SMarTrPlay - Video Player Backend (ffplay subprocess)"""

import subprocess
import os
import signal
import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal, QTimer


class PlayerBackend:
    """ffplay subprocess wrapper fuer Video-Playback."""

    def __init__(self):
        self.process = None
        self.current_url = None
        self.volume = 80
        self.is_playing = False

    def play(self, url, window_id=None):
        """Stream URL abspielen. Optional in ein Qt Fenster eingebettet."""
        self.stop()
        self.current_url = url

        cmd = [
            "ffplay",
            "-nostats",
            "-loglevel", "warning",
            "-volume", str(self.volume),
            "-infbuf",
            "-x", "960",
            "-y", "540",
            "-noborder",
            "-protocol_whitelist", "file,http,https,tcp,tls,pipe,udp,rtp",
        ]

        if window_id:
            cmd.extend(["-wid", str(window_id)])

        cmd.append(url)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            self.is_playing = True
            return True
        except Exception as e:
            print(f"Player Error: {e}")
            self.is_playing = False
            return False

    def stop(self):
        """Playback stoppen."""
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except Exception:
                try:
                    self.process.terminate()
                except Exception:
                    pass
            self.process = None
        self.is_playing = False
        self.current_url = None

    def pause(self):
        """Pause/Toggle (Sende Space-Taste an ffplay)."""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(b" ")
                self.process.stdin.flush()
            except Exception:
                pass

    def seek(self, seconds):
        """Vor/Zurueck springen."""
        if self.process and self.process.poll() is None:
            try:
                if seconds > 0:
                    self.process.stdin.write(b"\x1b[C")
                else:
                    self.process.stdin.write(b"\x1b[D")
                self.process.stdin.flush()
            except Exception:
                pass

    def seek_relative(self, seconds):
        """Seek forward/backward by relative seconds (sends arrow key to ffplay).

        ffplay keyboard: Right arrow = +10s, Left arrow = -10s.
        """
        self.seek(seconds)

    def set_volume(self, volume):
        """Lautstaerke setzen (0-100)."""
        self.volume = max(0, min(100, volume))

    def mute(self):
        """Mute toggle."""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(b"m")
                self.process.stdin.flush()
            except Exception:
                pass

    def is_running(self):
        """Pruefen ob ffplay noch laeuft."""
        if self.process:
            return self.process.poll() is None
        return False

    def get_errors(self):
        """Fehler-Output von ffplay abrufen."""
        if self.process and self.process.stderr:
            try:
                return self.process.stderr.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
        return ""

    def play_youtube(self, url):
        """YouTube Video abspielen (mit yt-dlp als Input, xdg-open Fallback)."""
        self.stop()
        self.current_url = url

        cmd = [
            "ffplay",
            "-nostats",
            "-loglevel", "warning",
            "-volume", str(self.volume),
            "-x", "960",
            "-y", "540",
            "-noborder",
            "-protocol_whitelist", "file,http,https,tcp,tls,pipe",
        ]

        # yt-dlp pipe
        try:
            ytdl = subprocess.Popen(
                ["yt-dlp", "-o", "-", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            cmd.append("pipe:0")
            self.process = subprocess.Popen(
                cmd,
                stdin=ytdl.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            ytdl.stdout.close()
            self.is_playing = True
            return True
        except Exception as e:
            print(f"YouTube Player Error: {e}")
            # Fallback 1: direkter URL-Versuch
            if not self.play(url):
                # Fallback 2: im Browser oeffnen
                print("YouTube: yt-dlp fehlgeschlagen, oeffne im Browser")
                try:
                    subprocess.Popen(["xdg-open", url],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return True
                except Exception as e2:
                    print(f"YouTube Browser Fallback Error: {e2}")
                    return False
            return True

    def open_netflix(self, url):
        """Netflix Deep Link im Browser oeffnen."""
        try:
            subprocess.Popen(["xdg-open", url],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"Netflix Open Error: {e}")
            return False
