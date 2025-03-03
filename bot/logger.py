
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = "Logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Farbiges Log-Format für Konsole mit zusätzlichen Informationen
class ColoredFormatter(logging.Formatter):
    """Erweiterter farbiger Log-Formatter für die Konsole mit mehr Details"""
    
    COLORS = {
        'DEBUG': '\033[94m',     # Blau
        'INFO': '\033[92m',      # Grün
        'WARNING': '\033[93m',   # Gelb
        'ERROR': '\033[91m',     # Rot
        'CRITICAL': '\033[91m\033[1m',  # Fett-Rot
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        log_message = super().format(record)
        levelname = record.levelname
        if levelname in self.COLORS:
            log_message = f"{self.COLORS[levelname]}{log_message}{self.COLORS['RESET']}"
        return log_message

# Erweiterte Log-Formate mit mehr Details
file_format = logging.Formatter("%(asctime)s - [%(levelname)s] - %(name)s - %(funcName)s:%(lineno)d - %(message)s")
console_format = ColoredFormatter("%(asctime)s - [%(levelname)s] - %(name)s - %(funcName)s:%(lineno)d - %(message)s")

# Log-Dateien mit Rotation (max 5 MB, 3 Backups)
def setup_logger(name, filename, console_output=True, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Bestehende Handler entfernen, um Duplikate zu vermeiden
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Datei-Handler
    file_handler = RotatingFileHandler(f"{LOG_DIR}/{filename}", maxBytes=5*1024*1024, backupCount=3)
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Konsolen-Handler (nur einmal hinzufügen)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    return logger

# Debug-Level für mehr Details in der Konsole
logging_level = logging.DEBUG

# Einzelne Log-Dateien mit erweiterten Details
bot_logger = setup_logger("bot", "bot.log", level=logging_level)
error_logger = setup_logger("errors", "errors.log", level=logging_level)
conversion_logger = setup_logger("conversions", "conversions.log", level=logging_level)

# Detaillierte Aktivitätslogger für verschiedene Bereiche
command_logger = setup_logger("commands", "commands.log", level=logging_level)
queue_logger = setup_logger("queue", "queue.log", level=logging_level)

# Fehler-Logging mit automatischem Cleanup
def cleanup_old_logs():
    for file in os.listdir(LOG_DIR):
        file_path = os.path.join(LOG_DIR, file)
        if os.path.isfile(file_path) and file.endswith(".log"):
            if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10 MB Limit
                os.remove(file_path)
                bot_logger.info(f"Log-Datei {file} wurde automatisch bereinigt")

# Cleanup starten
cleanup_old_logs()

# Startup-Nachricht mit mehr Details
bot_logger.info(f"===== ImageX-Bot gestartet am {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} =====")
bot_logger.debug(f"Log-Level: {logging_level}")
bot_logger.debug(f"Pfad: {os.getcwd()}")
bot_logger.debug(f"Python Version: {sys.version}")

# Globaler Logger, um ihn überall zu verwenden
logger = bot_logger

def log_command(command_name, user, guild=None, channel=None, status="executed"):
    """Hilfsfunktion zum Loggen von Befehlsnutzung"""
    guild_name = guild.name if guild else "DM"
    channel_name = channel.name if channel else "DM"
    command_logger.info(f"Command '{command_name}' {status} by {user} in {guild_name}/{channel_name}")

def log_conversion(user, source_file, target_format, success=True):
    """Hilfsfunktion zum Loggen von Konvertierungen"""
    status = "erfolgreich" if success else "fehlgeschlagen"
    conversion_logger.info(f"Konvertierung {status}: {source_file} -> {target_format} für {user}")
