import os

# Discord Bot Token
TOKEN = os.getenv("MTM0NjA5MzMwMDM2MDQxNzM0MQ.GrFxOT.EcVa3VVYKiJ24O_MAvyPsZ0Lc389Quw3LLAo9U")

# Bot Einstellungen
COMMAND_PREFIX = "/"  # Slash-Commands für modernen Discord-Support

# Liste ALLER bekannten Bildformate (Upload & Ziel-Format)
ALLOWED_FORMATS = [
    "jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "ico", "svg", "psd", "ai", "eps", "pdf",
    "heic", "raw", "nef", "cr2", "orf", "arw", "dng", "rw2", "raf", "sr2", "pef", "x3f", "dds",
    "jp2", "jxr", "hdr", "exr", "pcx", "tga", "xcf", "indd", "cdr", "dwg", "skp", "webp"
]

# Maximale Anzahl an Dateien pro Anfrage
MAX_FILES_PER_REQUEST = 4
