import discord
from discord import app_commands
from discord.ext import commands
from bot.queue import queue
from bot.logger import logger
from bot.config import ALLOWED_FORMATS, MAX_FILES_PER_REQUEST
import time
import os
import sys

TOKEN = "DEIN_BOT_TOKEN"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

last_request_time = 0

@bot.event
async def on_ready():
    logger.info(f"{bot.user} ist online!")
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game(name="ImageX 🔥 | /convert"))

@bot.tree.command(name="convert", description="Konvertiere Bilder in ein anderes Format")
async def convert(interaction: discord.Interaction, target_format: str):
    global last_request_time
    current_time = time.time()

    if not interaction.user.guild_permissions.attach_files:
        await interaction.response.send_message("❌ **Du darfst keine Dateien hochladen!**", ephemeral=True)
        return

    if current_time - last_request_time < 5:  # 5 Sekunden Global-Rate-Limit
        await interaction.response.send_message(f"⏳ Bitte warte noch `{5 - (current_time - last_request_time):.1f}` Sekunden.", ephemeral=True)
        return

    if not interaction.message.attachments:
        await interaction.response.send_message("⚠️ **Bitte lade mindestens eine Datei hoch!**", ephemeral=True)
        return

    images = interaction.message.attachments[:MAX_FILES_PER_REQUEST]

    if target_format.lower() not in ALLOWED_FORMATS:
        await interaction.response.send_message(f"❌ `{target_format}` ist kein unterstütztes Zielformat.", ephemeral=True)
        return

    last_request_time = current_time

    for image in images:
        await queue.add(interaction, image, target_format)

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
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ **Du hast keine Berechtigung, die Logs zu sehen!**", ephemeral=True)
        return

    with open("logs/bot.log", "r") as log_file:
        log_lines = log_file.readlines()[-amount:]

    embed = discord.Embed(title="📜 Letzte Logs", color=discord.Color.dark_blue())
    embed.description = "\n".join([f"📝 `{line.strip()}`" for line in log_lines])

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="restart", description="Startet den Bot neu (Admin only)")
async def restart(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ **Du hast keine Berechtigung, den Bot neu zu starten!**", ephemeral=True)
        return

    await interaction.response.send_message("♻️ **Neustart wird ausgeführt...**", ephemeral=True)
    logger.info("🔄 Bot wird neu gestartet!")
    os.execv(sys.executable, ['python'] + sys.argv)

bot.run(TOKEN)
