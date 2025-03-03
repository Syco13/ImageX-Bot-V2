import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time
import os
import sys
import traceback
from typing import List, Optional
import io
import platform
import datetime
import random
import psutil  # You might need to add this to your dependencies

from bot.converter import convert_image
from bot.config import ALLOWED_FORMATS, MAX_FILES_PER_REQUEST
from bot.task_queue import ImageQueue
from bot.logger import bot_logger as logger

# Optional keep_alive import (will be added later)
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive():
        logger.warning("⚠️ keep_alive module not found, skipping...")

# Create the conversion queue
queue = ImageQueue()

# Safely read token from environment variable
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    logger.error("❌ DISCORD_TOKEN not found! Please set the environment variable.")
    sys.exit(1)

# Discord Intents and Bot initialization
intents = discord.Intents.default()
intents.message_content = True  # Enables reading message content

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

# Rate limiting for users
user_cooldowns = {}
COOLDOWN_TIME = 5  # Seconds between requests

# Global statistics
start_time = time.time()
conversion_count = 0
error_count = 0
last_errors = []

# Available commands and their descriptions for the help page
commands_info = {
    "convert": "Convert images to another format",
    "formats": "Show all supported image formats",
    "status": "Show current queue and bot status",
    "logs": "Show recent logs (admin only)",
    "restart": "Restart the bot (admin only)",
    "help": "Show this help page",
    "ping": "Show bot latency",
    "stats": "Show bot usage statistics",
    "info": "Show information about the bot"
}

# Helper function for rate limiting
def check_cooldown(user_id):
    current_time = time.time()
    if user_id in user_cooldowns:
        time_diff = current_time - user_cooldowns[user_id]
        if time_diff < COOLDOWN_TIME:
            return False, COOLDOWN_TIME - time_diff
    user_cooldowns[user_id] = current_time
    return True, 0

# Helper function for permission checking
def has_permission(interaction, permission_name="attach_files"):
    """Check if a user has the specified permission"""
    if not interaction.guild:
        return True  # Always allow in DMs
        
    permission = getattr(interaction.user.guild_permissions, permission_name, None)
    if permission is None:
        return False
    return permission

# Bot Events
@bot.event
async def on_ready():
    """Event when the bot starts"""
    logger.info(f"🚀 {bot.user} is online!")
    
    # Register slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ {len(synced)} slash commands synchronized")
    except Exception as e:
        logger.error(f"❌ Error synchronizing slash commands: {e}")
    
    # Set status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="converting images | /help"
        )
    )
    
    # Start keep-alive for Replit
    keep_alive()
    
    logger.info(f"ℹ️ Bot running on Discord.py v{discord.__version__}")
    logger.info(f"ℹ️ Python version: {platform.python_version()}")
    logger.info(f"ℹ️ System: {platform.system()} {platform.release()}")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.CommandNotFound):
        return
    
    error_msg = str(error)
    logger.error(f"❌ Command error: {error_msg}")
    
    # Save error
    global error_count
    error_count += 1
    last_errors.append((time.time(), error_msg))
    
    # Keep only the last 10 errors
    if len(last_errors) > 10:
        last_errors.pop(0)
    
    # Report error to the user
    await ctx.send(f"❌ **Error:** {error_msg}", ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for slash commands"""
    error_msg = str(error)
    
    # Unwrap CommandInvokeError
    if isinstance(error, app_commands.errors.CommandInvokeError):
        error = error.original
        error_msg = str(error)
    
    # Log error
    logger.error(f"❌ Slash command error: {error_msg}")
    logger.error(f"Details: {traceback.format_exc()}")
    
    # Save error
    global error_count
    error_count += 1
    last_errors.append((time.time(), error_msg))
    
    # Keep only the last 10 errors
    if len(last_errors) > 10:
        last_errors.pop(0)
    
    # Send to user
    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"❌ **Error:** {error_msg}", 
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            f"❌ **Error:** {error_msg}", 
            ephemeral=True
        )

# Commands for image conversion
@bot.tree.command(name="convert", description="Convert images to another format")
@app_commands.describe(
    target_format="The target format for conversion",
    file1="First file to convert",
    file2="Second file to convert (optional)",
    file3="Third file to convert (optional)",
    file4="Fourth file to convert (optional)"
)
async def convert(
    interaction: discord.Interaction, 
    target_format: str,
    file1: discord.Attachment,
    file2: Optional[discord.Attachment] = None,
    file3: Optional[discord.Attachment] = None,
    file4: Optional[discord.Attachment] = None
):
    """Convert images to another format"""
    # Check rate limiting
    can_proceed, wait_time = check_cooldown(interaction.user.id)
    if not can_proceed:
        await interaction.response.send_message(
            f"⏳ Please wait `{wait_time:.1f}` more seconds.", 
            ephemeral=True
        )
        return

    # Check permissions
    if not has_permission(interaction, "attach_files"):
        await interaction.response.send_message(
            "❌ **You don't have permission to upload files!**", 
            ephemeral=True
        )
        return

    # Check format
    target_format = target_format.lower().strip(".")
    if target_format not in ALLOWED_FORMATS:
        formats_list = ", ".join([f"`{f}`" for f in ALLOWED_FORMATS[:10]]) + f" and {len(ALLOWED_FORMATS)-10} more"
        await interaction.response.send_message(
            f"❌ `{target_format}` is not a supported target format.\n"
            f"Supported formats: {formats_list}\n"
            f"Use `/formats` for a complete list.", 
            ephemeral=True
        )
        return

    # Collect files
    files = [f for f in [file1, file2, file3, file4] if f is not None]
    
    # Check if there are any files
    if not files:
        await interaction.response.send_message(
            "⚠️ **Please upload at least one file!**", 
            ephemeral=True
        )
        return
        
    # Check number of files
    if len(files) > MAX_FILES_PER_REQUEST:
        await interaction.response.send_message(
            f"⚠️ Maximum {MAX_FILES_PER_REQUEST} files per request allowed. Additional files will be ignored.", 
            ephemeral=True
        )
        files = files[:MAX_FILES_PER_REQUEST]

    # Send initial response (will be updated later with followup.send)
    await interaction.response.send_message(
        f"⏳ **Processing {len(files)} {'file' if len(files) == 1 else 'files'} for conversion to `{target_format}`...**", 
        ephemeral=False  # Visible to everyone so others can see the bot is working
    )
    
    # Update global stats
    global conversion_count
    conversion_count += len(files)

    # Queue conversion tasks
    task_ids = []
    for image in files:
        # Check file extension
        if not any(image.filename.lower().endswith(f".{ext}") for ext in ALLOWED_FORMATS):
            await interaction.followup.send(
                f"⚠️ `{image.filename}` has an unknown format and will be skipped.",
                ephemeral=True
            )
            continue
            
        # Add to queue
        task_id = await queue.add(interaction, image, target_format)
        task_ids.append(task_id)
    
    logger.info(f"✅ {len(task_ids)} conversions from {interaction.user} ({interaction.user.id}) added to queue")

# Information commands
@bot.tree.command(name="formats", description="Show all supported image formats")
async def formats(interaction: discord.Interaction):
    """Show all supported image formats"""
    # Split formats into categories
    common_formats = ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"]
    special_formats = ["ico", "svg", "dds", "heic", "jp2"]
    pro_formats = ["psd", "ai", "eps", "pdf", "raw"]
    camera_formats = ["nef", "cr2", "orf", "arw", "dng", "rw2", "raf", "sr2", "pef", "x3f"]
    other_formats = [f for f in ALLOWED_FORMATS if f not in common_formats + special_formats + pro_formats + camera_formats]
    
    embed = discord.Embed(
        title="📋 Supported Image Formats",
        description="These formats can be used as source and target formats:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📸 Commonly Used",
        value=" • " + "\n • ".join(common_formats),
        inline=True
    )
    
    embed.add_field(
        name="🔧 Special Formats",
        value=" • " + "\n • ".join(special_formats),
        inline=True
    )
    
    embed.add_field(
        name="👨‍💻 Professional Formats",
        value=" • " + "\n • ".join(pro_formats),
        inline=True
    )
    
    embed.add_field(
        name="📷 Camera RAW",
        value=" • " + "\n • ".join(camera_formats),
        inline=True
    )
    
    if other_formats:
        embed.add_field(
            name="🔍 Other Formats",
            value=" • " + "\n • ".join(other_formats),
            inline=True
        )
    
    embed.set_footer(text="Use /convert to convert images")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="status", description="Show current queue and bot status")
async def status(interaction: discord.Interaction):
    """Show current queue and bot status"""
    # Get queue status
    queue_status = await queue.get_status()
    
    # Calculate uptime
    uptime = time.time() - start_time
    days, remainder = divmod(uptime, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
    
    # System resources
    memory_usage = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
    
    # Create status embed
    embed = discord.Embed(
        title="📊 ImageX Bot Status", 
        color=discord.Color.blue(),
        description=f"Bot running since: `{uptime_str}`"
    )
    
    # Queue status
    embed.add_field(
        name="🖼️ Conversion Queue:",
        value=f"• Waiting images: `{queue_status['queue_size']}`\n"
              f"• Current status: `{'✅ Active' if queue_status['processing'] else '⏲️ Ready'}`\n"
              f"• Average processing time: `{queue_status['average_processing_time']}s`",
        inline=False
    )
    
    # Performance statistics
    embed.add_field(
        name="📈 Statistics:",
        value=f"• Successfully converted: `{queue_status['processed_count']}`\n"
              f"• Failed conversions: `{queue_status['failed_count']}`\n"
              f"• Total requests: `{conversion_count}`",
        inline=True
    )
    
    # System status
    embed.add_field(
        name="⚙️ System:",
        value=f"• RAM usage: `{memory_usage:.1f} MB`\n"
              f"• Errors: `{error_count}`\n"
              f"• Discord API latency: `{bot.latency*1000:.1f}ms`",
        inline=True
    )
    
    # Last error, if any
    if queue_status['last_error']:
        embed.add_field(
            name="⚠️ Last Error:",
            value=f"```{queue_status['last_error'][:200]}```",
            inline=False
        )
    
    embed.set_footer(text=f"ImageX v1.0 | {len(bot.guilds)} Servers")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="logs", description="Show recent logs (admin only)")
@app_commands.describe(amount="Number of log lines to show")
async def logs(interaction: discord.Interaction, amount: int = 10):
    """Show recent logs (admin only)"""
    if not has_permission(interaction, "administrator"):
        await interaction.response.send_message(
            "❌ **You don't have permission to view logs!**", 
            ephemeral=True
        )
        return

    # Validate logs
    log_path = "Logs/bot.log"
    if not os.path.exists(log_path):
        await interaction.response.send_message(
            "🚫 **No logs exist yet!**", 
            ephemeral=True
        )
        return

    # Read logs (with error handling)
    try:
        with open(log_path, "r", encoding="utf-8") as log_file:
            log_lines = log_file.readlines()
            log_lines = log_lines[-min(amount, len(log_lines)):]  # Only the last X lines
    except Exception as e:
        await interaction.response.send_message(
            f"❌ **Error reading logs:** `{e}`", 
            ephemeral=True
        )
        return

    # Split logs into chunks (Discord has a 2000 character limit)
    chunks = []
    current_chunk = ""
    
    for line in log_lines:
        line = line.strip()
        if len(current_chunk) + len(line) + 6 > 1900:  # Leave space for ```log ... ```
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += "\n" + line if current_chunk else line
    
    if current_chunk:
        chunks.append(current_chunk)
    
    # Send logs
    await interaction.response.send_message(f"📜 **Last {len(log_lines)} logs:**", ephemeral=True)
    
    for i, chunk in enumerate(chunks):
        await interaction.followup.send(f"```log\n{chunk}```", ephemeral=True)

@bot.tree.command(name="restart", description="Restart the bot (admin only)")
async def restart(interaction: discord.Interaction):
    """Restart the bot (admin only)"""
    if not has_permission(interaction, "administrator"):
        await interaction.response.send_message(
            "❌ **You don't have permission to restart the bot!**", 
            ephemeral=True
        )
        return

    await interaction.response.send_message("♻️ **Executing restart...**", ephemeral=True)
    logger.info("🔄 Bot is restarting!")

    # Try to complete current conversions
    if not queue.queue.empty():
        await interaction.followup.send(
            f"⏳ Waiting for completion of {queue.queue.qsize()} conversions...",
            ephemeral=True
        )
        # Wait maximum 30 seconds
        try:
            await asyncio.wait_for(queue.queue.join(), timeout=30)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "⚠️ Timeout waiting for conversions. Restarting anyway...",
                ephemeral=True
            )

    # Make sure the current Python executable is used
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.tree.command(name="help", description="Show a list of all commands")
async def help_command(interaction: discord.Interaction):
    """Show a list of all commands"""
    embed = discord.Embed(
        title="ℹ️ **ImageX Bot Help**", 
        color=discord.Color.green(),
        description="This bot converts images to various formats.\n"
                    "Here's a list of all available commands:"
    )
    
    # Commands for normal users
    user_commands = ["convert", "formats", "status", "help", "ping", "info", "stats"]
    admin_commands = ["logs", "restart"]
    
    # Show commands for normal users
    for cmd in user_commands:
        if cmd in commands_info:
            embed.add_field(
                name=f"/{cmd}", 
                value=commands_info[cmd], 
                inline=False
            )
    
    # Show admin commands
    embed.add_field(
        name="🔒 Admin Commands", 
        value="\n".join([f"• `/{cmd}` - {commands_info[cmd]}" for cmd in admin_commands]),
        inline=False
    )
    
    # Add example
    embed.add_field(
        name="📝 Example", 
        value="1. Use `/convert jpg` and upload an image\n"
              "2. The bot converts the image to JPG format\n"
              "3. Use `/formats` to see all supported formats",
        inline=False
    )
    
    embed.set_footer(text="ImageX v1.0 | Made with ❤️")
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.tree.command(name="ping", description="Show bot latency")
async def ping(interaction: discord.Interaction):
    """Show bot latency"""
    # Websocket latency
    ws_latency = round(bot.latency * 1000)
    
    # Measure message latency
    start_time = time.time()
    await interaction.response.send_message("🏓 **Pong!** Measuring latency...", ephemeral=True)
    
    # Edit message to show measured latency
    end_time = time.time()
    message_latency = round((end_time - start_time) * 1000)
    
    await interaction.edit_original_response(
        content=f"🏓 **Pong!**\n"
               f"• API Latency: `{ws_latency}ms`\n"
               f"• Message Latency: `{message_latency}ms`"
    )

@bot.tree.command(name="stats", description="Show bot usage statistics")
async def stats(interaction: discord.Interaction):
    """Show bot usage statistics"""
    # Get queue status
    queue_status = await queue.get_status()
    
    # Calculate uptime
    uptime = time.time() - start_time
    days, remainder = divmod(uptime, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
    
    # Create stats embed
    embed = discord.Embed(
        title="📊 ImageX Bot Statistics",
        color=discord.Color.gold(),
        description=f"Bot has been running for `{uptime_str}`"
    )
    
    # Usage statistics
    embed.add_field(
        name="📈 Usage Stats",
        value=f"• Processed images: `{queue_status['processed_count']}`\n"
              f"• Failed conversions: `{queue_status['failed_count']}`\n"
              f"• Total requests: `{conversion_count}`\n"
              f"• Avg. processing time: `{queue_status['average_processing_time']}s`",
        inline=True
    )
    
    # Server statistics
    embed.add_field(
        name="🌐 Server Stats",
        value=f"• Servers: `{len(bot.guilds)}`\n"
              f"• Users reached: `{sum(guild.member_count for guild in bot.guilds)}`\n"
              f"• API Latency: `{bot.latency*1000:.1f}ms`",
        inline=True
    )
    
    # System statistics
    cpu_percent = psutil.cpu_percent()
    memory_usage = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
    
    embed.add_field(
        name="⚙️ System Stats",
        value=f"• CPU usage: `{cpu_percent}%`\n"
              f"• Memory usage: `{memory_usage:.1f} MB`\n"
              f"• Python: `{platform.python_version()}`\n"
              f"• Discord.py: `{discord.__version__}`",
        inline=False
    )
    
    embed.set_footer(text=f"ImageX v1.0 | {datetime.datetime.now().strftime('%Y-%m-%d')}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="info", description="Show information about the bot")
async def info(interaction: discord.Interaction):
    """Show information about the bot"""
    embed = discord.Embed(
        title="ℹ️ About ImageX Bot",
        description="ImageX is a powerful image conversion bot for Discord!",
        color=discord.Color.blue()
    )
    
    # Add bot information
    embed.add_field(
        name="🤖 Bot Information",
        value=f"• Name: `ImageX`\n"
              f"• Version: `1.0`\n"
              f"• Library: `Discord.py {discord.__version__}`\n"
              f"• Uptime: `{format_uptime(time.time() - start_time)}`",
        inline=True
    )
    
    # Add features
    embed.add_field(
        name="✨ Features",
        value="• Convert images between many formats\n"
              "• Support for professional formats\n"
              "• Batch conversion\n"
              "• Fast processing queue",
        inline=True
    )
    
    # Add usage information
    embed.add_field(
        name="📋 Usage",
        value="Use `/convert [format]` and upload up to 4 images!\n"
              "For example: `/convert png` to convert to PNG\n"
              "Check `/formats` for all supported formats",
        inline=False
    )
    
    # Add invite link and support info
    embed.add_field(
        name="🔗 Links",
        value="• [Invite Bot](https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=34816&scope=bot%20applications.commands)\n"
              "• [Support Server](https://discord.gg/your-support-server)\n"
              "• [GitHub Repository](https://github.com/yourusername/imagex-bot)",
        inline=False
    )
    
    embed.set_footer(text="Made with ❤️ | ImageX Bot")
    
    # Set bot avatar as thumbnail if available
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

# Helper function to format uptime
def format_uptime(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{int(days)}d")
    if hours > 0 or days > 0:
        parts.append(f"{int(hours)}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{int(minutes)}m")
    parts.append(f"{int(seconds)}s")
    
    return " ".join(parts)

# Run the bot
if __name__ == "__main__":
    try:
        logger.info("🚀 Starting ImageX Bot...")
        bot.run(TOKEN)
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)