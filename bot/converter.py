from PIL import Image
import io
import requests
import os
import logging
import time
import sys
import traceback
import cv2
import numpy as np
from rembg import remove

# Logger direkt ohne Import-Loop nutzen
logger = logging.getLogger("conversions")

async def convert_image(image_url, target_format, remove_bg=False, resize=None):
    start_time = time.time()
    try:
        logger.debug(f"Starte Verarbeitung von {image_url} zu {target_format} (remove_bg={remove_bg}, resize={resize})")
        response = requests.get(image_url)

        if response.status_code != 200:
            logger.error(f"❌ HTTP-Fehler: {response.status_code} beim Abrufen von {image_url}")
            return None

        image_bytes = io.BytesIO(response.content)
        logger.debug(f"Bild heruntergeladen: {len(response.content)} Bytes")

        # Bild öffnen
        img = Image.open(image_bytes)
        
        # Hintergrund entfernen wenn gewünscht
        if remove_bg:
            logger.debug("Entferne Hintergrund mit rembg...")
            img_data = img.convert("RGBA")
            img_data_bytes = io.BytesIO()
            img_data.save(img_data_bytes, format="PNG")
            img_data_bytes.seek(0)
            
            # Hintergrund entfernen
            result = remove(img_data_bytes.getvalue())
            img = Image.open(io.BytesIO(result))
            logger.debug("Hintergrund erfolgreich entfernt")
            
        # Größe ändern wenn angegeben
        if resize:
            try:
                width, height = resize
                logger.debug(f"Ändere Bildgröße auf {width}x{height}...")
                img = img.resize((width, height), Image.LANCZOS)
                logger.debug(f"Bildgröße erfolgreich auf {width}x{height} geändert")
            except Exception as e:
                logger.error(f"Fehler bei der Größenänderung: {e}")
        
        # Ausgabe vorbereiten
        output_bytes = io.BytesIO()

        if target_format.lower() == "dds":
            # Alternativer Weg für DDS: Mit CV2 arbeiten und dann Pillow
            logger.debug("DDS-Konvertierung wird mit OpenCV vorbereitet...")

            # Temporäre Datei für die Zwischenkonvertierung
            input_path = "/tmp/input.png"
            output_path = "/tmp/output.png"  # Wir konvertieren zu PNG als Ersatz

            try:
                # Speichere als PNG für OpenCV
                img = Image.open(image_bytes)
                img.save(input_path, format="PNG")
                logger.debug(f"Temporäre PNG-Datei gespeichert: {input_path}")

                # Nutze OpenCV für erweiterte Bildverarbeitung
                cv_img = cv2.imread(input_path)
                if cv_img is None:
                    raise Exception("OpenCV konnte das Bild nicht lesen")

                # Erhalte die Bildabmessungen
                height, width = cv_img.shape[:2]
                logger.debug(f"Bild Größe: {width}x{height}")

                # DDS unterstützt oft Bilder mit Abmessungen als Zweierpotenzen
                # Wir konvertieren aber zu PNG, also kein Problem
                cv2.imwrite(output_path, cv_img)
                logger.debug(f"Bild mit OpenCV verarbeitet und gespeichert: {output_path}")

                # Lade das Ergebnis und gib es zurück
                with open(output_path, "rb") as f:
                    output_bytes.write(f.read())

                # Lösche temporäre Dateien
                os.remove(input_path)
                os.remove(output_path)
                logger.debug("Temporäre Dateien gelöscht")

                # Setze Dateizeiger zurück
                output_bytes.seek(0)

                # DDS ist nicht verfügbar, gib stattdessen eine PNG zurück
                logger.warning("⚠️ DDS-Format nicht unterstützt. Stattdessen PNG zurückgegeben.")

                elapsed_time = time.time() - start_time
                logger.info(f"✅ Erfolgreiche Ersatzkonvertierung zu PNG in {elapsed_time:.2f} Sekunden")
                return output_bytes

            except Exception as e:
                logger.error(f"❌ Fehler bei der OpenCV-Verarbeitung: {e}")

                # Fallback zu PNG
                logger.warning("⚠️ Fallback: Erstelle PNG anstelle von DDS")
                img = Image.open(image_bytes)
                fallback_output = io.BytesIO()
                img.save(fallback_output, format="PNG")
                fallback_output.seek(0)
                logger.info("✅ Fallback-Konvertierung zu PNG erfolgreich")
                return fallback_output
        else:
            # Standardkonvertierung mit Pillow
            logger.debug(f"Standard-Konvertierung zu {target_format.upper()} wird durchgeführt...")
            img = Image.open(image_bytes)
            img.save(output_bytes, format=target_format.upper())
            logger.debug(f"Konvertierung zu {target_format.upper()} erfolgreich")

            output_bytes.seek(0)
            elapsed_time = time.time() - start_time
            logger.info(f"✅ Erfolgreiche Konvertierung zu {target_format} in {elapsed_time:.2f} Sekunden")
            return output_bytes

    except Exception as e:
        elapsed_time = time.time() - start_time
        error_type = type(e).__name__
        logger.error(f"❌ {error_type} bei der Konvertierung: {e} (nach {elapsed_time:.2f} Sekunden)")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None