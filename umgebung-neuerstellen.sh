#!/usr/bin/env bash
# Baut die Projektumgebung von SMarTrPlay neu auf.
# Sie traegt python-vlc; ohne sie faellt der Player auf das alte ffplay
# zurueck und die Bedienknoepfe wirken nicht.
set -e
PROJEKT="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$PROJEKT"
echo "Baue Umgebung in $PROJEKT/.venv"
rm -rf .venv
/usr/bin/python3.12 -m venv --system-site-packages .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet python-vlc
echo "Pruefe:"
.venv/bin/python -c "import vlc, PyQt5.QtCore as c; print('  python-vlc', vlc.__version__, '| Qt', c.QT_VERSION_STR)"
echo "Selbsttest des Players:"
.venv/bin/python src/selbsttest_player_vlc.py 2>/dev/null | tail -2
echo "Fertig. Starten mit: systemctl --user start smartrplay"
