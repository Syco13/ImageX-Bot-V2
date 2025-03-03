import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time
import os
import sys

from bot.converter import convert_image
from bot.config import ALLOWED_FORMATS, MAX_FILES_PER_REQUEST
from bot.task_queue import ImageQueue

from bot.logger import bot_logger as logger  # Verhindert Import-Zirkel

queue = ImageQueue()

# Token sicher aus Environment-Variable lesen
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

last_request_time = 0

@bot.event
async def on_ready():
    logger.info(f"{bot.user} ist online!")
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game(name="ImageX 🔥 | /convert"))

@bot.tree.command(name="convert", description="Konvertiere Bilder in ein anderes Format")
@app_commands.describe(target_format="Das Zielformat (z.B. png, jpg, webp)")
async def convert(interaction: discord.Interaction, target_format: str):
    global last_request_time
    current_time = time.time()

    # Berechtigung prüfen
    if not interaction.user.guild_permissions.attach_files:
        await interaction.response.send_message("❌ **Du darfst keine Dateien hochladen!**", ephemeral=True)
        return

    # Rate-Limit Check
    if current_time - last_request_time < 5:
        await interaction.response.send_message(f"⏳ Bitte warte noch `{5 - (current_time - last_request_time):.1f}` Sekunden.", ephemeral=True)
        return

    # Wir müssen dem Benutzer erst antworten und dann nach Anhängen fragen
    await interaction.response.send_message("⚠️ **Bitte sende jetzt die Bilder, die du konvertieren möchtest!**", ephemeral=True)
    
    # Funktion zum Sammeln der Anhänge
    def check(message):
        return message.author == interaction.user and message.attachments
    
    # Format prüfen
    if target_format.lower() not in ALLOWED_FORMATS:
        await interaction.response.send_message(f"❌ `{target_format}` ist kein unterstütztes Zielformat.", ephemeral=True)
        return

    last_request_time = current_time
    
    try:
        # Warte auf die Nachricht mit Anhängen (Timeout nach 60 Sekunden)
        message = await bot.wait_for('message', check=check, timeout=60.0)
        images = message.attachments[:MAX_FILES_PER_REQUEST]
        logger.info(f"Bilder von {interaction.user.name} erhalten: {len(images)} Dateien")

        # Bilder in Warteschlange hinzufügen
        for image in images:
            await queue.add(message.channel, image, target_format)

        await message.channel.send(f"⏳ **Deine Bilder werden in `{target_format}` konvertiert...**", ephemeral=True)
    except asyncio.TimeoutError:
        # Wenn der Benutzer keine Bilder innerhalb der Zeitbeschränkung sendet
        follow_up = await interaction.original_response()
        await follow_up.edit(content="❌ **Zeitüberschreitung! Keine Bilder erhalten.**")
        logger.warning(f"Zeitüberschreitung für {interaction.user.name} - keine Bilder erhalten")

@bot.tree.command(name="status", description="Zeigt die aktuelle Warteschlange")
async def status(interaction: discord.Interaction):
    queue_size = queue.queue.qsize()
    processing_status = "✅ Läuft" if queue.processing else "⏳ Wartet auf Anfragen"

    embed = discord.Embed(title="📊 ImageX-Bot Status", color=discord.Color.blue())
    embed.add_field(name="🖼️ Wartende Bilder:", value=str(queue_size), inline=True)
    embed.add_field(name="⚙️ Verarbeitung:", value=processing_status, inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="logs", description="Zeigt die letzten Logs (Admin only)")
async def logs(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ **Du hast keine Berechtigung, die Logs zu sehen!**", ephemeral=True)
        return

    log_path = "Logs/bot.log"  # Fix: Logs statt logs
    if not os.path.exists(log_path):
        await interaction.response.send_message("🚫 **Es gibt noch keine Logs!**", ephemeral=True)
        return

    with open(log_path, "r") as log_file:
        log_lines = log_file.readlines()[-amount:]

    embed = discord.Embed(title="📜 Letzte Logs", color=discord.Color.dark_blue())
    embed.description = "\n".join([f"📝 `{line.strip()}`" for line in log_lines]) or "ℹ️ Keine Logs vorhanden."

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="restart", description="Startet den Bot neu (Admin only)")
async def restart(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ **Du hast keine Berechtigung, den Bot neu zu starten!**", ephemeral=True)
        return

    await interaction.response.send_message("♻️ **Neustart wird ausgeführt...**", ephemeral=True)
    logger.info("🔄 Bot wird neu gestartet!")

    # Sicherstellen, dass das aktuelle Python-Executable verwendet wird
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.tree.command(name="help", description="Zeigt eine Liste aller Befehle")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="ℹ️ **ImageX-Bot Hilfe**", color=discord.Color.green())
    embed.add_field(name="/convert [format]", value="Konvertiert hochgeladene Bilder in ein anderes Format.", inline=False)
    embed.add_field(name="/status", value="Zeigt den aktuellen Status der Warteschlange.", inline=False)
    embed.add_field(name="/logs [Anzahl]", value="Zeigt die letzten Logs (nur für Admins).", inline=False)
    embed.add_field(name="/restart", value="Startet den Bot neu (nur für Admins).", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Zeigt die Latenz des Bots an")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 **Pong!** Latenz: `{latency}ms`", ephemeral=True)

bot.run(TOKEN)