"""
ImageX Bot - Ein Discord-Bot zur Bildkonvertierung

Dieses Paket enthält alle Komponenten des ImageX Bots, einschließlich
Konfiguration, Bildkonvertierung, Task-Queuing und Logging.
"""

__version__ = "1.0.0"
__author__ = "Your Name"

# Grundlegende Importe
from .config import ALLOWED_FORMATS, MAX_FILES_PER_REQUEST
from .task_queue import ImageQueue
from .converter import convert_image, check_imagemagick
from .logger import logger

# Versionsinformationen und Bot-Identität
BOT_NAME = "ImageX"
BOT_DESCRIPTION = "Ein Discord-Bot zur Bildkonvertierung zwischen verschiedenen Formaten"

# Bot-Identität für Anzeige
BOT_IDENTITY = {
    "name": BOT_NAME,
    "version": __version__,
    "description": BOT_DESCRIPTION
}

# Setup-Funktion zum einfachen Initialisieren des Bots
def setup_bot():
    from .config import TOKEN
    if not TOKEN:
        logger.critical("❌ DISCORD_TOKEN nicht gefunden!")
        return None
        
    logger.info(f"🚀 {BOT_NAME} v{__version__} wird initialisiert...")
    return True