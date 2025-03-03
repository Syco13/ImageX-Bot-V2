import asyncio
import discord
def get_logger():
    from bot.logger import logger
    return logger

class ImageQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.processing = False

    async def add(self, ctx, image, target_format="png"):
        await self.queue.put((ctx, image, target_format))
        if not self.processing:
            self.processing = True
            asyncio.create_task(self.process_queue())

    async def process_queue(self):
        while not self.queue.empty():
            tasks = []
            for _ in range(min(4, self.queue.qsize())):
                tasks.append(self.queue.get())

            results = await asyncio.gather(*[self.handle_conversion(ctx, image, target_format) for ctx, image, target_format in tasks])

            for _ in range(len(results)):
                self.queue.task_done()

        self.processing = False

    async def handle_conversion(self, ctx, image, target_format):
        from bot.converter import convert_image  # Lazy Import nur innerhalb der Funktion!

        try:
            await ctx.send(f"⏳ `{image.filename}` wird nach `{target_format.upper()}` konvertiert...")
            image_bytes = await convert_image(image.url, target_format)

            if image_bytes:
                await ctx.send(file=discord.File(image_bytes, filename=f"converted.{target_format}"))
                get_logger().info("Eine Nachricht") (f"✅ `{image.filename}` wurde erfolgreich nach `{target_format.upper()}` konvertiert!")
            else:
                await ctx.send("❌ Fehler bei der Konvertierung.")
        except Exception as e:
            await ctx.send(f"❌ Fehler: {e}")
            logger.error(f"❌ Fehler in der Queue: {e}")
