from PIL import Image
import io
import requests
import os
import subprocess
import logging

# Logger direkt ohne Import-Loop nutzen
logger = logging.getLogger("bot")

# ImageMagick für DDS-Support nutzen
IMAGEMAGICK_PATH = "/usr/bin/convert"  # Anpassen, falls nötig

async def convert_image(image_url, target_format):
    try:
        response = requests.get(image_url)
        image_bytes = io.BytesIO(response.content)
        img = Image.open(image_bytes)

        output_bytes = io.BytesIO()

        if target_format.lower() == "dds":
            input_path = "/tmp/input.png"
            output_path = "/tmp/output.dds"
            img.save(input_path, format="PNG")  # Speichern als temporäres PNG
            subprocess.run([IMAGEMAGICK_PATH, input_path, output_path], check=True)
            with open(output_path, "rb") as f:
                output_bytes.write(f.read())
            os.remove(input_path)
            os.remove(output_path)
        else:
            img.save(output_bytes, format=target_format.upper())

        output_bytes.seek(0)
        logger.info(f"✅ Erfolgreiche Konvertierung: {target_format}")
        return output_bytes

    except Exception as e:
        logger.error(f"❌ Fehler bei der Konvertierung: {e}")
        return Nonern None
