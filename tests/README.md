# Abnahmen / Acceptance runs

Diese Läufe messen am **laufenden Fenster**, nicht am Quelltext. Sie starten die Anwendung,
bedienen sie und prüfen, was dabei wirklich passiert.

These runs measure the **running window**, not the source. They start the application,
operate it and check what actually happens.

```bash
DISPLAY=:0 .venv/bin/python tests/abnahme.py               # 20 Prüfsätze
DISPLAY=:0 .venv/bin/python tests/abnahme-vollbild.py      # 19 Prüfsätze
DISPLAY=:0 .venv/bin/python tests/abnahme-suche.py         # 14 Prüfsätze
DISPLAY=:0 .venv/bin/python tests/abnahme-serienzappen.py  # 17 Prüfsätze
```

**Hinweis:** Die Läufe brauchen einen eingerichteten Anbieter in der Anwendung, weil sie
echte Wiedergabe messen. Ohne Anbieter melden sie das und brechen ab.

**Note:** The runs need a provider configured in the application because they measure real
playback. Without one they say so and stop.
