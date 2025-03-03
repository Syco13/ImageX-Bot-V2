import asyncio
import discord
import time
from typing import Tuple, List, Any
import os

def get_logger():
    from bot.logger import logger
    return logger

class ImageQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.processing = False
        self.max_concurrent_tasks = 4
        self.processing_times = []  # Track processing times for performance monitoring
        self.processed_count = 0
        self.failed_count = 0
        self.last_error = None
        self.max_retries = 2  # Number of retries for failed conversions
        
    async def add(self, interaction, image, target_format="png"):
        """Add an image to the processing queue"""
        task_id = f"task_{int(time.time())}_{self.queue.qsize()}"
        await self.queue.put((interaction, image, target_format, task_id, 0))  # 0 = retry count
        
        # Start processing if not already running
        if not self.processing:
            self.processing = True
            asyncio.create_task(self.process_queue())
            get_logger().info(f"🚀 Queue processor started with {self.queue.qsize()} items")
        
        return task_id
    
    async def get_status(self):
        """Return current status information about the queue"""
        avg_time = sum(self.processing_times[-10:]) / max(len(self.processing_times[-10:]), 1) if self.processing_times else 0
        
        return {
            "queue_size": self.queue.qsize(),
            "processing": self.processing,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "average_processing_time": round(avg_time, 2),
            "last_error": str(self.last_error) if self.last_error else None
        }

    async def process_queue(self):
        """Process all items in the queue"""
        try:
            while not self.queue.empty():
                # Process up to max_concurrent_tasks images simultaneously
                batch_size = min(self.max_concurrent_tasks, self.queue.qsize())
                tasks = []
                task_data = []
                
                for _ in range(batch_size):
                    data = await self.queue.get()
                    task_data.append(data)
                    tasks.append(self.handle_conversion(*data))
                
                # Process batch of tasks concurrently
                start_time = time.time()
                results = await asyncio.gather(*tasks, return_exceptions=True)
                batch_time = time.time() - start_time
                
                # Record processing time
                if batch_time > 0:
                    self.processing_times.append(batch_time / batch_size)
                    # Keep only the last 100 processing times
                    if len(self.processing_times) > 100:
                        self.processing_times = self.processing_times[-100:]
                
                # Handle results
                for i, result in enumerate(results):
                    interaction, image, target_format, task_id, retry_count = task_data[i]
                    
                    if isinstance(result, Exception):
                        # Handle failed conversion
                        self.last_error = result
                        get_logger().error(f"❌ Task {task_id} failed: {result}")
                        
                        # Retry if under max retries
                        if retry_count < self.max_retries:
                            get_logger().info(f"🔄 Retrying task {task_id} (attempt {retry_count+1})")
                            await self.queue.put((interaction, image, target_format, task_id, retry_count + 1))
                        else:
                            self.failed_count += 1
                            try:
                                await interaction.followup.send(f"❌ Konvertierung von `{image.filename}` nach `{target_format}` fehlgeschlagen nach {self.max_retries+1} Versuchen.")
                            except Exception as e:
                                get_logger().error(f"📤 Konnte Fehlermeldung nicht senden: {e}")
                    else:
                        # Successful conversion
                        self.processed_count += 1
                
                    # Mark task as done
                    self.queue.task_done()
                
                # Prevent CPU overload with very small delay
                await asyncio.sleep(0.1)
                
            # Queue is empty, update processing status
            self.processing = False
            get_logger().info(f"✅ Queue processor finished. Processed: {self.processed_count}, Failed: {self.failed_count}")
            
        except Exception as e:
            # Catch any unexpected errors in queue processing
            self.processing = False
            self.last_error = e
            get_logger().error(f"💥 Unexpected error in queue processor: {e}")
            
            # Try to restart queue processing
            if not self.queue.empty():
                self.processing = True
                asyncio.create_task(self.process_queue())

    async def handle_conversion(self, interaction, image, target_format, task_id, retry_count):
        """Process a single image conversion"""
        from bot.converter import convert_image
        get_logger().info(f"🔄 Processing task {task_id}: Converting {image.filename} to {target_format}")
        
        try:
            # Inform user about processing (first attempt only)
            if retry_count == 0:
                try:
                    await interaction.followup.send(f"⏳ `{image.filename}` wird nach `{target_format.upper()}` konvertiert...")
                except Exception as e:
                    get_logger().error(f"📤 Fehler beim Senden der Statusnachricht: {e}")
            
            # Check if file is too large
            if image.size > 8 * 1024 * 1024:  # 8 MB limit
                await interaction.followup.send(f"❌ Die Datei `{image.filename}` ist zu groß (max. 8 MB).")
                return
                
            # Perform conversion
            start_time = time.time()
            image_bytes = await convert_image(image.url, target_format)
            conversion_time = time.time() - start_time
            
            if image_bytes:
                # Build filename that preserves original name but changes extension
                original_name = os.path.splitext(image.filename)[0]
                new_filename = f"{original_name}.{target_format}"
                
                # Send converted file
                await interaction.followup.send(
                    f"✅ Konvertierung erfolgreich ({conversion_time:.1f}s)",
                    file=discord.File(image_bytes, filename=new_filename)
                )
                get_logger().info(f"✅ Task {task_id} erfolgreich: `{image.filename}` → `{new_filename}` ({conversion_time:.1f}s)")
                return True
            else:
                raise Exception("Konvertierung fehlgeschlagen - keine Ausgabedaten")
                
        except Exception as e:
            get_logger().error(f"❌ Fehler bei Task {task_id} (Versuch {retry_count+1}): {e}")
            # Only notify user on final retry
            if retry_count >= self.max_retries:
                try:
                    await interaction.followup.send(f"❌ Fehler bei der Konvertierung von `{image.filename}`: {e}")
                except Exception as send_error:
                    get_logger().error(f"📤 Konnte Fehlermeldung nicht senden: {send_error}")
            raise e  # Re-raise so retry logic can handle it