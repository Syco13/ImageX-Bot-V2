import aiohttp
from PIL import Image
import io
import os
import subprocess
import logging
import tempfile
import time
import shutil
import asyncio
from typing import Optional, Tuple, List, Dict, Any
import mimetypes  # Standard-Bibliothek statt magic
import piexif  # für EXIF-Daten-Handling
import numpy as np  # für erweiterte Bildmanipulation

# Logger direkt ohne Import-Loop nutzen
logger = logging.getLogger("bot")

# ImageMagick für erweiterte Konvertierungen
IMAGEMAGICK_PATH = "/usr/bin/convert"  # Anpassen für Replit

# Temporäres Verzeichnis für Zwischendateien
TEMP_DIR = "/tmp/imagebot"
os.makedirs(TEMP_DIR, exist_ok=True)

# Maximale Bildgrößen
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_DIMENSIONS = (4000, 4000)      # 4000x4000 Pixel

# Qualitätseinstellungen für verschiedene Formate
QUALITY_SETTINGS = {
    "jpg": 90,
    "jpeg": 90,
    "webp": 85,
    "png": 9  # Komprimierungslevel für PNG
}

# Cache für bereits konvertierte Bilder (URL -> Format -> Bytes)
image_cache = {}
MAX_CACHE_SIZE = 50  # Maximale Anzahl an gecachten Bildern
cache_timestamps = {}  # Für LRU-Cache-Implementierung

# Statistiken für Leistungsüberwachung
conversion_stats = {
    "total_conversions": 0,
    "successful": 0,
    "failed": 0,
    "total_size_processed": 0,
    "avg_conversion_time": 0,
    "conversion_times": []
}

class ImageFormatError(Exception):
    """Fehler bei der Bildformat-Erkennung oder -Konvertierung"""
    pass

class ImageSizeError(Exception):
    """Fehler bei zu großen Bildern"""
    pass

class ImageQualityError(Exception):
    """Fehler bei der Bildqualitätsänderung"""
    pass

async def detect_image_format(file_bytes: io.BytesIO) -> str:
    """
    Erkennt das Format einer Bilddatei basierend auf den Bytes.
    
    Args:
        file_bytes: BytesIO-Objekt mit den Bilddaten
        
    Returns:
        str: Erkanntes Bildformat (lowercase)
        
    Raises:
        ImageFormatError: Wenn das Format nicht erkannt wurde
    """
    try:
        file_bytes.seek(0)
        
        # Dateiformat anhand der Magic Bytes erkennen
        # Die häufigsten Bildformate haben charakteristische Magic Bytes
        header = file_bytes.read(12)  # Ersten 12 Bytes für Formatidentifikation
        file_bytes.seek(0)
        
        # JPEG: FF D8 FF
        if header[0:3] == b'\xFF\xD8\xFF':
            return 'jpg'
        
        # PNG: 89 50 4E 47 0D 0A 1A 0A
        elif header[0:8] == b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A':
            return 'png'
        
        # GIF: 47 49 46 38
        elif header[0:4] == b'\x47\x49\x46\x38':
            return 'gif'
        
        # WEBP: 52 49 46 46 xx xx xx xx 57 45 42 50
        elif header[0:4] == b'\x52\x49\x46\x46' and header[8:12] == b'\x57\x45\x42\x50':
            return 'webp'
        
        # BMP: 42 4D
        elif header[0:2] == b'\x42\x4D':
            return 'bmp'
        
        # TIFF: 49 49 2A 00 or 4D 4D 00 2A
        elif header[0:4] == b'\x49\x49\x2A\x00' or header[0:4] == b'\x4D\x4D\x00\x2A':
            return 'tiff'
        
        # Alternativ mit PIL probieren
        file_bytes.seek(0)
        img = Image.open(file_bytes)
        file_bytes.seek(0)
        return img.format.lower()
            
    except Exception as e:
        logger.error(f"❌ Fehler bei der Formaterkennung: {e}")
        # Fallback: Versuche Erkennung mit PIL
        try:
            file_bytes.seek(0)
            img = Image.open(file_bytes)
            file_bytes.seek(0)
            if img.format:
                return img.format.lower()
        except:
            pass
            
        raise ImageFormatError(f"Format konnte nicht erkannt werden: {e}")

async def extract_metadata(img: Image.Image) -> Dict[str, Any]:
    """
    Extrahiert Metadaten aus einem Bild.
    
    Args:
        img: PIL Image-Objekt
        
    Returns:
        Dict: Metadaten des Bildes
    """
    metadata = {
        "dimensions": img.size,
        "mode": img.mode,
        "format": img.format,
        "exif": {}
    }
    
    # EXIF-Daten extrahieren, falls vorhanden
    try:
        if "exif" in img.info:
            exif_dict = piexif.load(img.info["exif"])
            # Vereinfachtes EXIF-Dictionary erstellen
            for ifd_name in exif_dict:
                if ifd_name == "thumbnail":
                    continue
                for tag_id in exif_dict[ifd_name]:
                    tag_value = exif_dict[ifd_name][tag_id]
                    if isinstance(tag_value, bytes):
                        # Bytes in lesbares Format umwandeln
                        try:
                            tag_value = tag_value.decode('utf-8', errors='replace')
                        except:
                            tag_value = str(tag_value)
                    metadata["exif"][f"{ifd_name}_{tag_id}"] = tag_value
    except Exception as e:
        logger.warning(f"⚠️ Fehler beim Extrahieren der EXIF-Daten: {e}")
    
    return metadata

async def preserve_metadata(source_img: Image.Image, target_img: Image.Image, target_format: str) -> Image.Image:
    """
    Überträgt Metadaten von einem Quellbild auf ein Zielbild.
    
    Args:
        source_img: Quell-Image-Objekt
        target_img: Ziel-Image-Objekt
        target_format: Zielformat
        
    Returns:
        Image.Image: Bild mit übertragenen Metadaten
    """
    # Nicht alle Formate unterstützen alle Metadaten
    metadata_compatible_formats = ["jpg", "jpeg", "tiff", "webp"]
    
    if target_format.lower() not in metadata_compatible_formats:
        return target_img
    
    # EXIF-Daten übertragen, falls vorhanden und Format unterstützt
    try:
        if "exif" in source_img.info and target_format.lower() in ["jpg", "jpeg", "tiff"]:
            exif_dict = piexif.load(source_img.info["exif"])
            exif_bytes = piexif.dump(exif_dict)
            target_img.info["exif"] = exif_bytes
    except Exception as e:
        logger.warning(f"⚠️ Fehler beim Übertragen der EXIF-Daten: {e}")
    
    # ICC-Profil übertragen, falls vorhanden
    if "icc_profile" in source_img.info:
        target_img.info["icc_profile"] = source_img.info["icc_profile"]
    
    return target_img

async def resize_if_needed(img: Image.Image, max_dimensions: Tuple[int, int] = MAX_DIMENSIONS) -> Image.Image:
    """
    Skaliert ein Bild, wenn es die maximalen Dimensionen überschreitet.
    
    Args:
        img: PIL Image-Objekt
        max_dimensions: Tuple mit maximaler Breite und Höhe
        
    Returns:
        Image.Image: Skaliertes Bild oder Original
    """
    width, height = img.size
    max_width, max_height = max_dimensions
    
    if width <= max_width and height <= max_height:
        return img
    
    # Seitenverhältnis beibehalten
    aspect_ratio = width / height
    
    if width > max_width:
        width = max_width
        height = int(width / aspect_ratio)
    
    if height > max_height:
        height = max_height
        width = int(height * aspect_ratio)
    
    logger.info(f"🔄 Bild wird auf {width}x{height} skaliert")
    return img.resize((width, height), Image.LANCZOS)

async def optimize_image(img: Image.Image, target_format: str) -> Image.Image:
    """
    Optimiert ein Bild für das Zielformat.
    
    Args:
        img: PIL Image-Objekt
        target_format: Zielformat
        
    Returns:
        Image.Image: Optimiertes Bild
    """
    # Format-spezifische Optimierungen
    if target_format.lower() in ["jpg", "jpeg"]:
        # JPG benötigt RGB-Format (kein Alpha)
        if img.mode in ['RGBA', 'LA'] or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
            img = background
    
    elif target_format.lower() == "png":
        # PNG optimieren durch Farbpalette für bestimmte Bilder
        if img.mode == 'RGBA' and not has_many_colors(img):
            try:
                img = img.quantize(colors=256, method=2)
            except Exception as e:
                logger.warning(f"⚠️ Fehler bei PNG-Optimierung: {e}")
    
    elif target_format.lower() == "gif":
        # GIF hat nur 256 Farben
        if img.mode != 'P':
            img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
    
    return img

async def update_cache(url: str, target_format: str, image_bytes: io.BytesIO) -> None:
    """
    Fügt ein konvertiertes Bild zum Cache hinzu.
    
    Args:
        url: Quell-URL des Bildes
        target_format: Zielformat
        image_bytes: BytesIO mit den Bilddaten
    """
    global image_cache, cache_timestamps
    
    # Alte Einträge entfernen, wenn Cache zu groß wird
    if len(image_cache) >= MAX_CACHE_SIZE:
        # Ältesten Eintrag entfernen (LRU)
        oldest_url = min(cache_timestamps, key=cache_timestamps.get)
        if oldest_url in image_cache:
            del image_cache[oldest_url]
            del cache_timestamps[oldest_url]
    
    # Neuen Eintrag hinzufügen
    if url not in image_cache:
        image_cache[url] = {}
    
    # Kopie der Bytes erstellen, um Speicherprobleme zu vermeiden
    image_bytes.seek(0)
    cached_bytes = io.BytesIO(image_bytes.read())
    image_bytes.seek(0)
    
    image_cache[url][target_format] = cached_bytes
    cache_timestamps[url] = time.time()

def get_cached_image(url: str, target_format: str) -> Optional[io.BytesIO]:
    """
    Holt ein Bild aus dem Cache, falls vorhanden.
    
    Args:
        url: Quell-URL des Bildes
        target_format: Zielformat
        
    Returns:
        Optional[io.BytesIO]: Cached Bild oder None
    """
    if url in image_cache and target_format in image_cache[url]:
        logger.info(f"🔄 Bild aus Cache geladen: {url} -> {target_format}")
        cache_timestamps[url] = time.time()  # Update timestamp
        
        # Kopie zurückgeben, um Speicherprobleme zu vermeiden
        cached_bytes = image_cache[url][target_format]
        cached_bytes.seek(0)
        result = io.BytesIO(cached_bytes.read())
        cached_bytes.seek(0)
        return result
    
    return None

def has_many_colors(img: Image.Image, sample_pixels: int = 1000) -> bool:
    """
    Prüft, ob ein Bild viele verschiedene Farben hat.
    
    Args:
        img: PIL Image-Objekt
        sample_pixels: Anzahl der zu prüfenden Pixel
        
    Returns:
        bool: True, wenn das Bild viele verschiedene Farben hat
    """
    # In Numpy-Array konvertieren und Stichprobe nehmen
    img_array = np.array(img)
    height, width = img_array.shape[:2]
    
    # Zufällige Pixel auswählen
    x_coords = np.random.randint(0, width, sample_pixels)
    y_coords = np.random.randint(0, height, sample_pixels)
    
    # Farben zählen
    colors = set()
    for i in range(sample_pixels):
        pixel = tuple(img_array[y_coords[i], x_coords[i]].tolist())
        colors.add(pixel)
    
    # Wenn mehr als 64 verschiedene Farben, dann "viele Farben"
    return len(colors) > 64

async def convert_with_imagemagick(input_path: str, output_path: str, target_format: str) -> bool:
    """
    Konvertiert ein Bild mit ImageMagick.
    
    Args:
        input_path: Pfad zur Eingabedatei
        output_path: Pfad zur Ausgabedatei
        target_format: Zielformat
        
    Returns:
        bool: True bei Erfolg, False bei Fehler
    """
    try:
        cmd = [IMAGEMAGICK_PATH]
        
        # Format-spezifische Parameter
        if target_format.lower() == "jpg" or target_format.lower() == "jpeg":
            quality = QUALITY_SETTINGS.get("jpg", 90)
            cmd.extend(["-quality", str(quality)])
        elif target_format.lower() == "png":
            cmd.extend(["-define", f"png:compression-level={QUALITY_SETTINGS.get('png', 9)}"])
        elif target_format.lower() == "webp":
            quality = QUALITY_SETTINGS.get("webp", 85)
            cmd.extend(["-quality", str(quality)])
        elif target_format.lower() == "dds":
            cmd.extend(["-define", "dds:compression=dxt5"])
        
        # Input und Output
        cmd.extend([input_path, output_path])
        
        # Prozess ausführen
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"❌ ImageMagick-Fehler: {stderr.decode()}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler bei ImageMagick-Konvertierung: {e}")
        return False

async def convert_image(image_url: str, target_format: str) -> Optional[io.BytesIO]:
    """
    Konvertiert ein Bild von einer URL in das angegebene Zielformat.
    
    Args:
        image_url: URL des zu konvertierenden Bildes
        target_format: Gewünschtes Zielformat
        
    Returns:
        Optional[io.BytesIO]: Bytes des konvertierten Bildes oder None bei Fehler
    """
    start_time = time.time()
    
    # Format bereinigen
    target_format = target_format.lower().strip().lstrip('.')
    
    # Aus Cache holen, falls vorhanden
    cached_image = get_cached_image(image_url, target_format)
    if cached_image:
        # Statistik aktualisieren
        conversion_stats["total_conversions"] += 1
        conversion_stats["successful"] += 1
        return cached_image
    
    try:
        # Bild herunterladen
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"❌ HTTP-Fehler: {response.status} beim Abrufen des Bildes")
                    conversion_stats["total_conversions"] += 1
                    conversion_stats["failed"] += 1
                    return None
                
                image_data = await response.read()
                
                # Größe prüfen
                if len(image_data) > MAX_IMAGE_SIZE:
                    logger.error(f"❌ Bild zu groß: {len(image_data) / 1024 / 1024:.2f} MB")
                    conversion_stats["total_conversions"] += 1
                    conversion_stats["failed"] += 1
                    raise ImageSizeError(f"Bild ist zu groß (max. {MAX_IMAGE_SIZE / 1024 / 1024} MB)")
                
                image_bytes = io.BytesIO(image_data)
                conversion_stats["total_size_processed"] += len(image_data)
        
        # Original-Format erkennen
        source_format = await detect_image_format(image_bytes)
        logger.info(f"🔍 Erkanntes Format: {source_format}, Zielformat: {target_format}")
        
        # Gleiche Formate direkt zurückgeben
        if source_format.lower() == target_format.lower():
            logger.info(f"✅ Quell- und Zielformat identisch: {target_format}")
            conversion_stats["total_conversions"] += 1
            conversion_stats["successful"] += 1
            await update_cache(image_url, target_format, image_bytes)
            return image_bytes
        
        # Tempdir für diese Konvertierung
        with tempfile.TemporaryDirectory(dir=TEMP_DIR) as temp_dir:
            # Bild öffnen
            image_bytes.seek(0)
            
            # Spezielle Formate mit ImageMagick verarbeiten
            if source_format.lower() in ["dds", "psd", "pdf", "ai", "eps"] or target_format.lower() in ["dds"]:
                # Temporäre Dateien
                input_path = os.path.join(temp_dir, f"input.{source_format}")
                output_path = os.path.join(temp_dir, f"output.{target_format}")
                
                # Eingabedatei speichern
                with open(input_path, "wb") as f:
                    f.write(image_bytes.getvalue())
                
                # Mit ImageMagick konvertieren
                success = await convert_with_imagemagick(input_path, output_path, target_format)
                
                if success and os.path.exists(output_path):
                    # Ergebnis zurückgeben
                    result = io.BytesIO()
                    with open(output_path, "rb") as f:
                        result.write(f.read())
                    
                    result.seek(0)
                    logger.info(f"✅ Erfolgreiche Konvertierung mit ImageMagick: {source_format} -> {target_format}")
                    conversion_stats["total_conversions"] += 1
                    conversion_stats["successful"] += 1
                    
                    # In Cache speichern
                    await update_cache(image_url, target_format, result)
                    
                    return result
                else:
                    logger.error(f"❌ ImageMagick-Konvertierung fehlgeschlagen: {source_format} -> {target_format}")
                    conversion_stats["total_conversions"] += 1
                    conversion_stats["failed"] += 1
                    return None
            
            # Standardkonvertierung mit PIL
            try:
                image_bytes.seek(0)
                img = Image.open(image_bytes)
                
                # Metadaten extrahieren
                metadata = await extract_metadata(img)
                logger.info(f"📊 Bildinfo: {img.format} {img.size} {img.mode}")
                
                # Bild bei Bedarf skalieren
                img = await resize_if_needed(img)
                
                # Bild für Zielformat optimieren
                img = await optimize_image(img, target_format)
                
                # Ergebnis speichern
                output_bytes = io.BytesIO()
                
                # Format-spezifische Speicheroptionen
                save_options = {}
                
                if target_format.lower() in ["jpg", "jpeg"]:
                    save_options["quality"] = QUALITY_SETTINGS.get("jpg", 90)
                    save_options["optimize"] = True
                elif target_format.lower() == "png":
                    save_options["optimize"] = True
                    save_options["compress_level"] = QUALITY_SETTINGS.get("png", 9)
                elif target_format.lower() == "webp":
                    save_options["quality"] = QUALITY_SETTINGS.get("webp", 85)
                    save_options["method"] = 6  # Bessere Kompression
                elif target_format.lower() == "gif":
                    save_options["optimize"] = True
                
                # Metadaten übertragen
                img = await preserve_metadata(img, img, target_format)
                
                # Bild speichern
                img.save(output_bytes, format=target_format.upper(), **save_options)
                output_bytes.seek(0)
                
                # Statistik aktualisieren
                conversion_stats["total_conversions"] += 1
                conversion_stats["successful"] += 1
                logger.info(f"✅ Erfolgreiche Konvertierung: {source_format} -> {target_format}")
                
                # In Cache speichern
                await update_cache(image_url, target_format, output_bytes)
                
                return output_bytes
                
            except Exception as e:
                logger.error(f"❌ PIL-Fehler bei der Konvertierung: {e}")
                conversion_stats["total_conversions"] += 1
                conversion_stats["failed"] += 1
                return None

    except aiohttp.ClientError as e:
        logger.error(f"❌ Netzwerkfehler: {e}")
        conversion_stats["total_conversions"] += 1
        conversion_stats["failed"] += 1
        return None
    except ImageFormatError as e:
        logger.error(f"❌ Formatfehler: {e}")
        conversion_stats["total_conversions"] += 1
        conversion_stats["failed"] += 1
        return None
    except ImageSizeError as e:
        logger.error(f"❌ Größenfehler: {e}")
        conversion_stats["total_conversions"] += 1
        conversion_stats["failed"] += 1
        return None
    except Exception as e:
        logger.error(f"❌ Unerwarteter Fehler: {e}")
        conversion_stats["total_conversions"] += 1
        conversion_stats["failed"] += 1
        return None
    finally:
        # Konversionszeit messen und statistik aktualisieren
        conversion_time = time.time() - start_time
        conversion_stats["conversion_times"].append(conversion_time)
        
        # Durchschnittliche Konversionszeit berechnen
        if conversion_stats["conversion_times"]:
            conversion_stats["avg_conversion_time"] = sum(conversion_stats["conversion_times"]) / len(conversion_stats["conversion_times"])
            # Maximum 100 Zeitwerte speichern
            if len(conversion_stats["conversion_times"]) > 100:
                conversion_stats["conversion_times"] = conversion_stats["conversion_times"][-100:]
        
        logger.info(f"⏱️ Konvertierung in {conversion_time:.2f}s abgeschlossen")

# Hilfsfunktion zur Überprüfung, ob ImageMagick verfügbar ist
async def check_imagemagick():
    """
    Überprüft, ob ImageMagick auf dem System installiert ist.
    
    Returns:
        bool: True, wenn ImageMagick verfügbar ist, sonst False
    """
    try:
        process = await asyncio.create_subprocess_exec(
            IMAGEMAGICK_PATH, "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            version = stdout.decode().splitlines()[0]
            logger.info(f"✅ ImageMagick gefunden: {version}")
            return True
        else:
            logger.warning("⚠️ ImageMagick nicht gefunden. DDS-Konvertierung wird nicht verfügbar sein.")
            return False
    except Exception:
        logger.warning("⚠️ ImageMagick nicht gefunden. DDS-Konvertierung wird nicht verfügbar sein.")
        return False

# Cache-Cleanup-Funktion
async def cleanup_cache():
    """Entfernt alte Einträge aus dem Cache."""
    global image_cache, cache_timestamps
    
    # Einträge, die älter als 30 Minuten sind, entfernen
    current_time = time.time()
    urls_to_remove = []
    
    for url, timestamp in cache_timestamps.items():
        if current_time - timestamp > 1800:  # 30 Minuten
            urls_to_remove.append(url)
    
    for url in urls_to_remove:
        if url in image_cache:
            del image_cache[url]
        del cache_timestamps[url]
    
    logger.info(f"🧹 Cache bereinigt: {len(urls_to_remove)} Einträge entfernt, {len(image_cache)} verbleibend")

# Statistikfunktion
def get_conversion_stats():
    """
    Gibt die aktuellen Konvertierungsstatistiken zurück.
    
    Returns:
        Dict: Statistiken über durchgeführte Konvertierungen
    """
    stats = conversion_stats.copy()
    stats["cache_size"] = len(image_cache)
    stats["avg_conversion_time_ms"] = stats["avg_conversion_time"] * 1000 if "avg_conversion_time" in stats else 0
    stats["success_rate"] = (stats["successful"] / stats["total_conversions"] * 100) if stats["total_conversions"] > 0 else 0
    stats["total_size_processed_mb"] = stats["total_size_processed"] / 1024 / 1024
    
    # Aktuelle Conversion Times entfernen (zu groß für Log/Anzeige)
    if "conversion_times" in stats:
        del stats["conversion_times"]
    
    return stats

# Initialisierungsfunktion
async def init_converter():
    """Initialisiert den Konverter und prüft Abhängigkeiten."""
    # ImageMagick Check
    has_imagemagick = await check_imagemagick()
    
    # Temp-Verzeichnis erstellen
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Alte Temp-Dateien bereinigen
    for item in os.listdir(TEMP_DIR):
        item_path = os.path.join(TEMP_DIR, item)
        try:
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            logger.warning(f"⚠️ Fehler beim Bereinigen von {item_path}: {e}")
    
    logger.info("🚀 Bild-Konverter initialisiert")
    return has_imagemagick