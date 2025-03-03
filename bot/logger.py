import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "Logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Log-Format
log_format = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s")

# Log-Dateien mit Rotation (max 5 MB, 3 Backups)
def setup_logger(name, filename):
    handler = RotatingFileHandler(f"{LOG_DIR}/{filename}", maxBytes=5*1024*1024, backupCount=3)
    handler.setFormatter(log_format)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
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

# Globaler Logger, um ihn überall zu verwenden
logger = bot_logger

