import os

# Discord Bot Token
TOKEN = os.getenv("MTM0NjA5MzMwMDM2MDQxNzM0MQ.GFqWag.RpO08hbYOCeZGyJ5fPEs-FikylbOFZmLaT3JlM")

# Bot Einstellungen
COMMAND_PREFIX = "/"  # Slash-Commands für modernen Discord-Support

# Unterstützte Bildformate (Upload & Ziel-Format)
ALLOWED_FORMATS = [
    "jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "ico", "svg",
    "psd", "ai", "eps", "pdf", "heic", "raw", "nef", "cr2", "orf", "arw",
    "dng", "rw2", "raf", "sr2", "pef", "x3f", "dds", "jp2", "jxr", "hdr",
    "exr", "pcx", "tga", "xcf", "indd", "cdr", "dwg", "skp"
]

# Maximale Anzahl an Dateien pro Anfrage
MAX_FILES_PER_REQUEST = 4
