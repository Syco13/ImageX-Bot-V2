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
    logger.info(f"🚀 {bot.user} ist online! Bot-ID: {bot.user.id}")
    logger.debug(f"In {len(bot.guilds)} Servern aktiv")
    
    # Erweiterte Bot-Informationen
    for guild in bot.guilds:
        logger.debug(f"Server: {guild.name} (ID: {guild.id}) - {len(guild.members)} Mitglieder")
    
    await bot.tree.sync()
    logger.info("✅ Slash-Commands synchronisiert")
    
    await bot.change_presence(activity=discord.Game(name="ImageX 🔥 | /convert"))
    logger.info("✅ Status gesetzt: 'ImageX 🔥 | /convert'")
    
    logger.info("====================================")
    logger.info("🤖 Bot ist vollständig gestartet und bereit!")
    logger.info("====================================")
    
@bot.event
async def on_guild_join(guild):
    """Log wenn der Bot einem neuen Server beitritt"""
    logger.info(f"🔵 Bot ist neuem Server beigetreten: {guild.name} (ID: {guild.id}) - {len(guild.members)} Mitglieder")

@bot.event 
async def on_command_error(ctx, error):
    """Log für Command-Fehler"""
    from bot.logger import error_logger
    error_logger.error(f"Command-Fehler: {error} in {ctx.command if ctx.command else 'Unbekannter Befehl'}")
    error_logger.error(f"von {ctx.author} in {ctx.guild}/{ctx.channel}")
    
@bot.event
async def on_app_command_error(interaction, error):
    """Log für App-Command-Fehler (Slash-Commands)"""
    from bot.logger import error_logger
    command_name = interaction.command.name if interaction.command else "Unbekannt"
    error_logger.error(f"App-Command-Fehler: {error} in /{command_name}")
    error_logger.error(f"von {interaction.user} in {interaction.guild}/{interaction.channel}")
    
    # Versuche, eine schöne Fehlermeldung zu senden, falls möglich
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Fehler: {error}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Fehler: {error}", ephemeral=True)
    except:
        pass

@bot.tree.command(name="convert", description="Konvertiere Bilder in ein anderes Format")
@app_commands.describe(target_format="Das Zielformat (z.B. png, jpg, webp)")
async def convert(interaction: discord.Interaction, target_format: str):
    global last_request_time
    current_time = time.time()
    
    from bot.logger import log_command, command_logger as cmd_logger
    
    cmd_logger.info(f"Convert-Command ausgeführt von {interaction.user} in {interaction.guild.name if interaction.guild else 'DM'}")
    cmd_logger.debug(f"Parameter: target_format={target_format}")

    # Berechtigung prüfen
    if not interaction.user.guild_permissions.attach_files:
        cmd_logger.warning(f"❌ Berechtigungsfehler: {interaction.user} hat keine Berechtigung zum Hochladen von Dateien")
        await interaction.response.send_message("❌ **Du darfst keine Dateien hochladen!**", ephemeral=True)
        return

    # Rate-Limit Check
    if current_time - last_request_time < 5:
        wait_time = 5 - (current_time - last_request_time)
        cmd_logger.info(f"⏳ Rate-Limit für {interaction.user}: Muss noch {wait_time:.1f} Sekunden warten")
        await interaction.response.send_message(f"⏳ Bitte warte noch `{wait_time:.1f}` Sekunden.", ephemeral=True)
        return

    # Format prüfen
    if target_format.lower() not in ALLOWED_FORMATS:
        cmd_logger.warning(f"❌ Ungültiges Format: {target_format} von {interaction.user}")
        await interaction.response.send_message(f"❌ `{target_format}` ist kein unterstütztes Zielformat.", ephemeral=True)
        return
        
    # Wir müssen dem Benutzer erst antworten und dann nach Anhängen fragen
    cmd_logger.info(f"✅ {interaction.user} kann Bilder senden für {target_format}-Konvertierung")
    await interaction.response.send_message("⚠️ **Bitte sende jetzt die Bilder, die du konvertieren möchtest!**", ephemeral=True)
    
    # Funktion zum Sammeln der Anhänge
    def check(message):
        return message.author == interaction.user and message.attachments

    last_request_time = current_time
    
    try:
        # Warte auf die Nachricht mit Anhängen (Timeout nach 60 Sekunden)
        cmd_logger.debug(f"Warte auf Bilder von {interaction.user}...")
        message = await bot.wait_for('message', check=check, timeout=60.0)
        
        # Detaillierte Dateiinformationen loggen
        for attachment in message.attachments:
            cmd_logger.debug(f"Empfangen: {attachment.filename} ({attachment.size} Bytes, {attachment.content_type})")
        
        images = message.attachments[:MAX_FILES_PER_REQUEST]
        if len(message.attachments) > MAX_FILES_PER_REQUEST:
            cmd_logger.warning(f"⚠️ {interaction.user} hat zu viele Dateien gesendet. Nur {MAX_FILES_PER_REQUEST} werden verarbeitet.")
            await message.channel.send(f"⚠️ Es werden nur die ersten {MAX_FILES_PER_REQUEST} Bilder verarbeitet.")
            
        cmd_logger.info(f"Bilder von {interaction.user.name} erhalten: {len(images)}/{len(message.attachments)} Dateien")

        # Bilder in Warteschlange hinzufügen
        for i, image in enumerate(images):
            cmd_logger.debug(f"Füge Bild {i+1}/{len(images)} zur Queue hinzu: {image.filename}")
            await queue.add(message.channel, image, target_format)

        cmd_logger.info(f"✅ Alle {len(images)} Bilder zur Verarbeitung hinzugefügt für {interaction.user.name}")
        await message.channel.send(f"⏳ **Deine {len(images)} Bilder werden in `{target_format.upper()}` konvertiert...**")
        
        # Log-Command-Nutzung
        log_command("convert", interaction.user.name, interaction.guild, interaction.channel, 
                   status=f"started conversion of {len(images)} images to {target_format}")
        
    except asyncio.TimeoutError:
        # Wenn der Benutzer keine Bilder innerhalb der Zeitbeschränkung sendet
        cmd_logger.warning(f"⏳ Zeitüberschreitung für {interaction.user.name} - keine Bilder erhalten nach 60 Sekunden")
        follow_up = await interaction.original_response()
        await follow_up.edit(content="❌ **Zeitüberschreitung! Keine Bilder erhalten.**")
        
        # Log-Command-Nutzung für fehlgeschlagene Anfrage
        log_command("convert", interaction.user.name, interaction.guild, interaction.channel, 
                   status="timeout - no images received")

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