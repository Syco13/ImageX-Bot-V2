# Discord Converter Bot

Ein leistungsstarker Discord-Bot zum Konvertieren von Dateien und Bildern in verschiedene Formate. Unterstützt alle Dateitypen und ermöglicht das gleichzeitige Konvertieren mehrerer Bilder.

## Funktionen
- **Unterstützt alle Dateiformate**: Wandelt jede hochgeladene Datei in das gewünschte Format um.
- **Mehrere Bilder auf einmal**: Lade mehrere Bilder hoch und konvertiere sie gleichzeitig.
- **Einfache Slash-Commands**: Intuitive Steuerung direkt in Discord.
- **Admin-Funktionen**: Protokolle anzeigen und den Bot bei Bedarf neu starten.

## Befehle
### Nutzer-Befehle
- `/convert [format]` – Konvertiert hochgeladene Bilder in das gewünschte Format.
- `/status` – Zeigt den aktuellen Status der Warteschlange.

### Admin-Befehle
- `/logs [Anzahl]` – Zeigt die letzten Logs (nur für Admins).
- `/restart` – Startet den Bot neu (nur für Admins).

## Installation
1. **Repository klonen**:
   ```bash
   git clone https://github.com/dein-github/discord-converter-bot.git
   ```
2. **Abhängigkeiten installieren**:
   ```bash
   cd discord-converter-bot
   pip install -r requirements.txt
   ```
3. **Bot konfigurieren**:
   - Erstelle eine `.env`-Datei und füge deinen Discord-Token hinzu:
     ```
     DISCORD_TOKEN=dein_bot_token
     ```
4. **Bot starten**:
   ```bash
   python bot.py
   ```

## Anforderungen
- Python 3.x
- Discord.py
- Image- und Datei-Handling-Bibliotheken (z. B. Pillow, ffmpeg)

## Mitwirken
Pull-Requests sind willkommen! Erstelle gerne ein Issue, wenn du Vorschläge oder Probleme hast.

## Lizenz
Dieses Projekt steht unter der **MIT-Lizenz**.

