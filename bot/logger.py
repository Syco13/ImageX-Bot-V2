import logging
import os
import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR = "Logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Log-Format mit Farben für die Konsole
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[94m',  # Blau
        'INFO': '\033[92m',   # Grün
        'WARNING': '\033[93m', # Gelb
        'ERROR': '\033[91m',  # Rot
        'CRITICAL': '\033[91m\033[1m',  # Fettgedruckt Rot
        'RESET': '\033[0m'    # Reset
    }
    
    def format(self, record):
        log_message = super().format(record)
        levelname = record.levelname
        if levelname in self.COLORS:
            return f"{self.COLORS[levelname]}{log_message}{self.COLORS['RESET']}"
        return log_message

# Log-Formate für Datei und Konsole
file_formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(name)s - %(message)s")
console_formatter = ColoredFormatter("%(asctime)s - [%(levelname)s] - %(name)s - %(message)s")

# Konsolen-Handler für Entwicklung
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
console_handler.setLevel(logging.INFO)

# Log-Dateien mit Rotation (max 5 MB, 3 Backups)
def setup_logger(name, filename, level=logging.INFO):
    """
    Erstellt einen Logger mit Datei- und Konsolenausgabe.
    
    Args:
        name (str): Name des Loggers
        filename (str): Dateiname für die Log-Datei
        level (int): Log-Level (Standard: INFO)
        
    Returns:
        logging.Logger: Konfigurierter Logger
    """
    # Datei-Handler
    file_handler = RotatingFileHandler(
        f"{LOG_DIR}/{filename}", 
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(level)
    
    # Logger konfigurieren
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Handler nur hinzufügen, wenn sie noch nicht existieren
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# Einzelne Log-Dateien
bot_logger = setup_logger("bot", "bot.log")
error_logger = setup_logger("errors", "errors.log")
conversion_logger = setup_logger("conversions", "conversions.log")

# Fehler-Logging mit automatischem Cleanup
def cleanup_old_logs(max_age_days=7, max_size_mb=10):
    """
    Bereinigt alte oder zu große Log-Dateien.
    
    Args:
        max_age_days (int): Maximales Alter der Logs in Tagen
        max_size_mb (int): Maximale Größe der Logs in MB
    """
    now = datetime.datetime.now()
    max_size_bytes = max_size_mb * 1024 * 1024
    
    for file in os.listdir(LOG_DIR):
        file_path = os.path.join(LOG_DIR, file)
        if os.path.isfile(file_path) and file.endswith(".log"):
            # Größenprüfung
            if os.path.getsize(file_path) > max_size_bytes:
                bot_logger.info(f"🧹 Zu große Log-Datei wird gelöscht: {file}")
                try:
                    os.remove(file_path)
                    continue
                except OSError as e:
                    bot_logger.error(f"❌ Fehler beim Löschen der Datei {file}: {e}")
            
            # Altersprüfung
            file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            file_age = (now - file_time).days
            
            if file_age > max_age_days:
                bot_logger.info(f"🧹 Alte Log-Datei wird gelöscht: {file} (Alter: {file_age} Tage)")
                try:
                    os.remove(file_path)
                except OSError as e:
                    bot_logger.error(f"❌ Fehler beim Löschen der Datei {file}: {e}")

# Cleanup starten
cleanup_old_logs()

# Globaler Logger, um ihn überall zu verwenden
logger = bot_logger

# Initialisierungsnachricht
logger.info("🔧 Logger erfolgreich initialisiert")