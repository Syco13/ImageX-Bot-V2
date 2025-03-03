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
    logger.info(f"🟢 {bot.user} ist online!")
    logger.info(f"🔄 Befehle werden synchronisiert...")
    await bot.tree.sync()
    logger.info(f"✅ Befehle erfolgreich synchronisiert")
    await bot.change_presence(activity=discord.Game(name="ImageX 🔥 | /convert"))
    logger.info(f"👀 Bot-Status wurde aktualisiert: 'ImageX 🔥 | /convert'")

@bot.tree.command(name="convert", description="Konvertiere Bilder in ein anderes Format")
async def convert(interaction: discord.Interaction, target_format: str):
    global last_request_time
    current_time = time.time()
    
    logger.info(f"🖼️ /convert Befehl von {interaction.user.name} (ID: {interaction.user.id}) - Format: {target_format}")

    # Berechtigung prüfen
    if not interaction.user.guild_permissions.attach_files:
        logger.warning(f"❌ Berechtigung verweigert für {interaction.user.name} (ID: {interaction.user.id})")
        await interaction.response.send_message("❌ **Du darfst keine Dateien hochladen!**", ephemeral=True)
        return

    # Rate-Limit Check
    if current_time - last_request_time < 5:
        wait_time = 5 - (current_time - last_request_time)
        logger.info(f"⏳ Rate-Limit für {interaction.user.name} - Muss {wait_time:.1f}s warten")
        await interaction.response.send_message(f"⏳ Bitte warte noch `{wait_time:.1f}` Sekunden.", ephemeral=True)
        return

    # Anhänge prüfen
    if not interaction.attachments:
        logger.info(f"⚠️ Keine Dateien von {interaction.user.name} hochgeladen")
        await interaction.response.send_message("⚠️ **Bitte lade mindestens eine Datei hoch!**", ephemeral=True)
        return

    images = interaction.attachments[:MAX_FILES_PER_REQUEST]
    logger.info(f"📂 {len(images)} Bilder von {interaction.user.name} empfangen")

    # Format prüfen
    if target_format.lower() not in ALLOWED_FORMATS:
        logger.warning(f"❌ Ungültiges Format '{target_format}' von {interaction.user.name}")
        await interaction.response.send_message(f"❌ `{target_format}` ist kein unterstütztes Zielformat.", ephemeral=True)
        return

    last_request_time = current_time

    # Bilder in Warteschlange hinzufügen
    for i, image in enumerate(images):
        logger.info(f"➕ Bild {i+1}/{len(images)} zur Warteschlange hinzugefügt: {image.filename}")
        await queue.add(interaction, image, target_format)

    logger.info(f"✅ Konvertierungsauftrag für {interaction.user.name} akzeptiert: {len(images)} Bilder nach {target_format}")
    await interaction.response.send_message(f"⏳ **Deine Bilder werden in `{target_format}` konvertiert...**", ephemeral=True)

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
    logger.info(f"📋 /logs Befehl von {interaction.user.name} (ID: {interaction.user.id}) - Anzahl: {amount}")
    
    if not interaction.user.guild_permissions.administrator:
        logger.warning(f"⛔ Admin-Berechtigung verweigert für {interaction.user.name} beim Versuch, Logs anzuzeigen")
        await interaction.response.send_message("❌ **Du hast keine Berechtigung, die Logs zu sehen!**", ephemeral=True)
        return

    log_path = "Logs/bot.log"
    if not os.path.exists(log_path):
        logger.warning(f"🔍 Log-Datei nicht gefunden: {log_path}")
        await interaction.response.send_message("🚫 **Es gibt noch keine Logs!**", ephemeral=True)
        return

    logger.info(f"📖 {interaction.user.name} ruft die letzten {amount} Logs ab")
    with open(log_path, "r") as log_file:
        log_lines = log_file.readlines()[-amount:]

    embed = discord.Embed(title="📜 Letzte Logs", color=discord.Color.dark_blue())
    embed.description = "\n".join([f"📝 `{line.strip()}`" for line in log_lines]) or "ℹ️ Keine Logs vorhanden."

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"✅ Logs erfolgreich an {interaction.user.name} gesendet")

@bot.tree.command(name="restart", description="Startet den Bot neu (Admin only)")
async def restart(interaction: discord.Interaction):
    logger.info(f"🔄 /restart Befehl von {interaction.user.name} (ID: {interaction.user.id})")
    
    if not interaction.user.guild_permissions.administrator:
        logger.warning(f"⛔ Admin-Berechtigung verweigert für {interaction.user.name} beim Versuch, Bot neu zu starten")
        await interaction.response.send_message("❌ **Du hast keine Berechtigung, den Bot neu zu starten!**", ephemeral=True)
        return

    logger.info(f"🔄 Bot-Neustart initiiert von {interaction.user.name}")
    await interaction.response.send_message("♻️ **Neustart wird ausgeführt...**", ephemeral=True)
    logger.info("🔄 Bot wird jetzt neu gestartet...")

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
