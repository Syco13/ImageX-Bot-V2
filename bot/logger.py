import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = "Logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Farbiges Log-Format für Konsole
class ColoredFormatter(logging.Formatter):
    """Farbiger Log-Formatter für die Konsole"""
    
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

# Log-Formate
file_format = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s")
console_format = ColoredFormatter("%(asctime)s - [%(levelname)s] - %(message)s")

# Log-Dateien mit Rotation (max 5 MB, 3 Backups)
def setup_logger(name, filename, console_output=True):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Datei-Handler
    file_handler = RotatingFileHandler(f"{LOG_DIR}/{filename}", maxBytes=5*1024*1024, backupCount=3)
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Konsolen-Handler (nur einmal hinzufügen)
    if console_output and not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    return logger

# Einzelne Log-Dateien
bot_logger = setup_logger("bot", "bot.log")
error_logger = setup_logger("errors", "errors.log")
conversion_logger = setup_logger("conversions", "conversions.log")

# Fehler-Logging mit automatischem Cleanup
def cleanup_old_logs():
    for file in os.listdir(LOG_DIR):
        file_path = os.path.join(LOG_DIR, file)
        if os.path.isfile(file_path) and file.endswith(".log"):
            if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10 MB Limit
                os.remove(file_path)

# Cleanup starten
cleanup_old_logs()

# Startup-Nachricht
bot_logger.info(f"===== Bot-Logger gestartet am {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} =====")

# Globaler Logger, um ihn überall zu verwenden
logger = bot_logger

