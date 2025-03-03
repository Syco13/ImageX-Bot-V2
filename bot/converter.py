from PIL import Image
import io
import requests
import os
import subprocess
import logging
import time
import sys
import traceback

# Logger direkt ohne Import-Loop nutzen
logger = logging.getLogger("conversions")

# ImageMagick für DDS-Support nutzen
try:
    # Versuche, den Pfad von ImageMagick zu finden
    IMAGEMAGICK_PATH = subprocess.check_output(["which", "convert"]).decode().strip()
    logger.info(f"ImageMagick gefunden: {IMAGEMAGICK_PATH}")
except:
    # Fallback-Pfade für verschiedene Umgebungen
    possible_paths = [
        "/usr/bin/convert",
        "/usr/local/bin/convert",
        "/home/runner/.local/bin/convert",
        "convert"  # Versuche einfach den Befehl ohne Pfad
    ]
    
    for path in possible_paths:
        try:
            subprocess.run([path, "--version"], capture_output=True, check=False)
            IMAGEMAGICK_PATH = path
            logger.info(f"ImageMagick gefunden unter Fallback-Pfad: {IMAGEMAGICK_PATH}")
            break
        except:
            continue
    else:
        IMAGEMAGICK_PATH = "convert"  # Fallback auf einfachen Befehl
        logger.warning("⚠️ ImageMagick-Pfad konnte nicht gefunden werden, verwende Fallback 'convert'")

async def convert_image(image_url, target_format):
    start_time = time.time()
    try:
        logger.debug(f"Starte Konvertierung von {image_url} zu {target_format}")
        response = requests.get(image_url)
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP-Fehler: {response.status_code} beim Abrufen von {image_url}")
            return None
            
        image_bytes = io.BytesIO(response.content)
        logger.debug(f"Bild heruntergeladen: {len(response.content)} Bytes")
        
        img = Image.open(image_bytes)
        logger.debug(f"Bildformat erkannt: {img.format}, Größe: {img.size}, Modus: {img.mode}")

        output_bytes = io.BytesIO()

        if target_format.lower() == "dds":
            logger.debug("DDS-Konvertierung mit ImageMagick wird durchgeführt...")
            input_path = "/tmp/input.png"
            output_path = "/tmp/output.dds"
            
            try:
                img.save(input_path, format="PNG")  # Speichern als temporäres PNG
                logger.debug(f"Temporäre PNG-Datei gespeichert: {input_path}")
                
                result = subprocess.run([IMAGEMAGICK_PATH, input_path, output_path], 
                                      check=True, 
                                      capture_output=True,
                                      text=True)
                logger.debug(f"ImageMagick Ausgabe: {result.stdout}")
            except FileNotFoundError as e:
                logger.error(f"❌ ImageMagick nicht gefunden: {e}")
                logger.error(f"Pfad, der verwendet wurde: {IMAGEMAGICK_PATH}")
                return None
            except Exception as e:
                logger.error(f"❌ Fehler bei der DDS-Konvertierung: {e}")
                return None
            
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.debug(f"DDS-Datei erzeugt: {output_path}, Größe: {file_size} Bytes")
                with open(output_path, "rb") as f:
                    output_bytes.write(f.read())
                os.remove(input_path)
                os.remove(output_path)
                logger.debug("Temporäre Dateien gelöscht")
            else:
                logger.error(f"❌ DDS-Datei konnte nicht erstellt werden")
                return None
        else:
            logger.debug(f"Standard-Konvertierung zu {target_format.upper()} wird durchgeführt...")
            img.save(output_bytes, format=target_format.upper())
            logger.debug(f"Konvertierung zu {target_format.upper()} erfolgreich")

        output_bytes.seek(0)
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Erfolgreiche Konvertierung zu {target_format} in {elapsed_time:.2f} Sekunden")
        return output_bytes

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ ImageMagick Fehler: {e}")
        logger.error(f"Fehlerdetails: {e.stderr}")
        return None
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_type = type(e).__name__
        logger.error(f"❌ {error_type} bei der Konvertierung: {e} (nach {elapsed_time:.2f} Sekunden)")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None
