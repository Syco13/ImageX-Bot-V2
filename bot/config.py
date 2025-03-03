import os
import sys

# Umgebungsvariablen laden und prüfen
def get_env_var(name, default=None, required=False):
    """
    Liest eine Umgebungsvariable und gibt einen Fehler aus, wenn sie fehlt und required=True ist.
    
    Args:
        name (str): Name der Umgebungsvariable
        default: Standardwert, falls die Variable nicht existiert
        required (bool): Ob die Variable erforderlich ist
        
    Returns:
        Der Wert der Umgebungsvariable oder der Standardwert
    """
    value = os.getenv(name, default)
    if required and value is None:
        print(f"Fehler: Umgebungsvariable '{name}' ist nicht gesetzt!")
        sys.exit(1)
    return value

# Discord Bot Token (ERFORDERLICH)
TOKEN = get_env_var("DISCORD_TOKEN", required=True)

# Bot Einstellungen (optional mit Standardwerten)
COMMAND_PREFIX = get_env_var("COMMAND_PREFIX", "/")
DEBUG_MODE = get_env_var("DEBUG_MODE", "false").lower() == "true"

# Performance-Einstellungen
MAX_CONCURRENT_CONVERSIONS = int(get_env_var("MAX_CONCURRENT_CONVERSIONS", "4"))
CONVERSION_TIMEOUT = int(get_env_var("CONVERSION_TIMEOUT", "60"))  # Sekunden

# Liste ALLER bekannten Bildformate (Upload & Ziel-Format)
ALLOWED_FORMATS = [
    # Standard Web-Formate
    "jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "ico", "svg",
    
    # Professionelle Formate
    "psd", "ai", "eps", "pdf",
    
    # Kamera-Formate
    "heic", "raw", "nef", "cr2", "orf", "arw", "dng", "rw2", "raf", "sr2", "pef", "x3f",
    
    # Spezielle Formate
    "dds", "jp2", "jxr", "hdr", "exr", "pcx", "tga", "xcf", "indd", "cdr", "dwg", "skp"
]

# Gruppierte Formate für bessere Übersicht (zur Information)
FORMAT_GROUPS = {
    "Web": ["jpg", "jpeg", "png", "gif", "webp"],
    "Professionell": ["psd", "ai", "eps", "pdf", "tiff", "svg"],
    "Kamera": ["heic", "raw", "nef", "cr2", "dng"],
    "Spezial": ["dds", "hdr", "exr", "tga"]
}

# Maximale Anzahl an Dateien pro Anfrage
MAX_FILES_PER_REQUEST = int(get_env_var("MAX_FILES_PER_REQUEST", "4"))

# Maximale Bildgröße in MB (zum Schutz vor zu großen Uploads)
MAX_IMAGE_SIZE_MB = int(get_env_var("MAX_IMAGE_SIZE_MB", "8"))

# Pfad zu ImageMagick (kann je nach System variieren)
IMAGEMAGICK_PATH = get_env_var("IMAGEMAGICK_PATH", "/usr/bin/convert")

# Replit-spezifische Einstellungen
IS_REPLIT = get_env_var("REPL_ID", None) is not None
if IS_REPLIT:
    # Für Replit: Sicherstellen, dass der Bot aktiv bleibt
    KEEP_ALIVE = True
    # Replit Web-Server Port
    WEB_SERVER_PORT = int(get_env_var("PORT", "8080"))
    # Temporärer Ordner in Replit
    TEMP_DIR = "/tmp"
else:
    KEEP_ALIVE = False
    TEMP_DIR = "temp"
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)