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
IMAGEMAGICK_PATH = "/usr/bin/convert"  # Anpassen, falls nötig

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
            img.save(input_path, format="PNG")  # Speichern als temporäres PNG
            logger.debug(f"Temporäre PNG-Datei gespeichert: {input_path}")
            
            result = subprocess.run([IMAGEMAGICK_PATH, input_path, output_path], 
                                  check=True, 
                                  capture_output=True,
                                  text=True)
            logger.debug(f"ImageMagick Ausgabe: {result.stdout}")
            
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
