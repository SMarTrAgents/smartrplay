# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spezifikation fuer SMarTrPlay unter Windows.

Gebuendelt werden Python, PyQt5, python-vlc und die Quellmodule aus src/.
Die VLC-Bibliothek selbst wird NICHT mitgeliefert: der Installer setzt eine
vorhandene VLC-Installation voraus und bietet sie bei Bedarf zum Download an.
Das haelt die Datei klein und vermeidet Lizenzfragen mit den VLC-Plugins.
"""
import os

projekt = os.path.abspath(os.path.join(os.getcwd()))
quellen = os.path.join(projekt, 'src')

a = Analysis(
    [os.path.join(quellen, 'main.py')],
    pathex=[quellen],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.QtNetwork',
        'vlc', 'requests', 'sqlite3',
        # Module aus src/, die erst zur Laufzeit geladen werden
        'main_window', 'theme', 'player_vlc', 'vollbild', 'video_controls',
        'xtream_api', 'config', 'epg', 'epg_timeline', 'vod_browser',
        'series_browser', 'search_browser', 'settings_dialog', 'fadenpark',
        'm3u_parser', 'mini_player', 'pip', 'catchup', 'multi_profile',
        'audio_subtitle_options', 'auto_refresh', 'subtitle_recording',
        'debug_server',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy'],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='SMarTrPlay',
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon=os.path.join(projekt, 'build', 'windows', 'smartrplay.ico')
         if os.path.exists(os.path.join(projekt, 'build', 'windows', 'smartrplay.ico')) else None,
)
