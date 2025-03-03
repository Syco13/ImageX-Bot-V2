import asyncio
import discord
import os
from datetime import datetime
import logging

def get_logger():
    from bot.logger import logger
    return logger

import asyncio
import discord
import time
import logging
from datetime import datetime

class ImageQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.processing = False
        self.logger = logging.getLogger("queue")
        self.stats = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "start_time": None
        }

    async def add(self, ctx, image, target_format="png", remove_bg=False, resize=None):
        queue_size = self.queue.qsize()
        self.logger.info(f"Bild zur Queue hinzugefügt: {image.filename} ({target_format}) von {ctx.author if hasattr(ctx, 'author') else 'Unbekannt'}")
        self.logger.debug(f"Queue-Größe vor Hinzufügen: {queue_size}")

        await self.queue.put((ctx, image, target_format, remove_bg, resize))

        if not self.processing:
            self.logger.info("Queue-Verarbeitung wird gestartet")
            self.processing = True
            self.stats["start_time"] = datetime.now()
            asyncio.create_task(self.process_queue())
        else:
            self.logger.debug(f"Queue-Verarbeitung läuft bereits, Position in der Warteschlange: {queue_size + 1}")

    async def process_queue(self):
        self.logger.info(f"Queue-Verarbeitung gestartet, {self.queue.qsize()} Bilder in der Warteschlange")

        while not self.queue.empty():
            start_batch = time.time()
            batch_size = min(4, self.queue.qsize())
            self.logger.info(f"Verarbeite Batch mit {batch_size} Bildern")

            tasks = []
            for i in range(batch_size):
                task = await self.queue.get()
                self.logger.debug(f"Task {i+1} aus Queue entnommen: {task[1].filename}")
                tasks.append(task)

            # Now tasks contains tuples of (ctx, image, target_format, remove_bg, resize)
            self.logger.debug(f"Starte parallele Konvertierung von {len(tasks)} Bildern")
            results = await asyncio.gather(
                *[self.handle_conversion(ctx, image, target_format, remove_bg, resize) 
                  for ctx, image, target_format, remove_bg, resize in tasks],
                return_exceptions=True
            )

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Unbehandelte Exception in Task {i+1}: {result}")
                    self.stats["failed"] += 1
                else:
                    self.queue.task_done()
                    self.stats["processed"] += 1
                    if result:
                        self.stats["successful"] += 1
                    else:
                        self.stats["failed"] += 1

            batch_time = time.time() - start_batch
            self.logger.info(f"Batch-Verarbeitung abgeschlossen in {batch_time:.2f} Sekunden")
            self.logger.info(f"Queue-Statistik: {self.stats['processed']} verarbeitet, "
                           f"{self.stats['successful']} erfolgreich, {self.stats['failed']} fehlgeschlagen")

        total_time = (datetime.now() - self.stats["start_time"]).total_seconds() if self.stats["start_time"] else 0
        self.logger.info(f"Queue-Verarbeitung beendet nach {total_time:.2f} Sekunden")
        self.processing = False

    async def handle_conversion(self, ctx, image, target_format, remove_bg=False, resize=None):
        from bot.converter import convert_image
        from bot.logger import log_conversion

        start_time = time.time()
        self.logger.debug(f"Verarbeitung gestartet: {image.filename} zu {target_format}, remove_bg={remove_bg}, resize={resize}")
        user = ctx.author if hasattr(ctx, 'author') else 'Unbekannt'

        try:
            operations = []
            if remove_bg:
                operations.append("Hintergrundentfernung")
            if resize:
                operations.append(f"Größenänderung auf {resize[0]}x{resize[1]}")
            operations.append(f"Konvertierung zu {target_format.upper()}")
            
            operation_text = ", ".join(operations)
            
            self.logger.info(f"Verarbeite: `{image.filename}` → {operation_text}")
            await ctx.send(f"⏳ `{image.filename}` wird bearbeitet: {operation_text}...")

            conversion_start = time.time()
            image_bytes = await convert_image(image.url, target_format, remove_bg, resize)
            conversion_time = time.time() - conversion_start

            if image_bytes:
                file_size = len(image_bytes.getvalue())
                self.logger.info(f"✅ Verarbeitung erfolgreich: {image.filename} ({file_size} Bytes in {conversion_time:.2f}s)")

                filename, file_extension = os.path.splitext(image.filename)
                await ctx.send(file=discord.File(image_bytes, filename=f"{filename}.{target_format}"))
                log_conversion(user, image.filename, target_format, success=True)
                return True
            else:
                self.logger.error(f"❌ Konvertierung fehlgeschlagen: {image.filename} → {target_format.upper()} (nach {conversion_time:.2f}s)")
                await ctx.send("❌ Fehler bei der Konvertierung.")
                log_conversion(user, image.filename, target_format, success=False)
                return False
        except discord.HTTPException as e:
            self.logger.error(f"❌ Discord HTTP-Fehler: {e.status} - {e.code}: {e.text}")
            await ctx.send(f"❌ Discord-Fehler: Datei konnte nicht gesendet werden (möglicherweise zu groß).")
            return False
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.logger.error(f"❌ Fehler in der Queue: {type(e).__name__}: {e}")
            self.logger.error(f"Traceback: {error_trace}")

            # Benutzerfreundliche Fehlermeldung
            await ctx.send(f"❌ Fehler: {e}")
            return False