# Discord Converter Bot

A powerful Discord bot for converting files and images into different formats. Supports all file types and allows multiple images to be converted at once.

## Features

**Note:** Currently, the bot only supports German for command responses, help messages, and other interactions.
- **Supports all file formats**: Converts any uploaded file to the desired format.
- **Multiple images at once**: Upload multiple images and convert them simultaneously.
- **Simple slash commands**: Intuitive control directly in Discord.
- **Admin functions**: View logs and restart the bot when needed.

## Commands
### User Commands
- `/convert [format]` – Converts uploaded images to the desired format.
- `/status` – Displays the current status of the queue.

### Admin Commands
- `/logs [amount]` – Displays the latest logs (admins only).
- `/restart` – Restarts the bot (admins only).

## Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-github/discord-converter-bot.git
   ```
2. **Install dependencies**:
   ```bash
   cd discord-converter-bot
   pip install -r requirements.txt
   ```
3. **Configure the bot**:
   - Create a `.env` file and add your Discord token:
     ```
     DISCORD_TOKEN=your_bot_token
     ```
4. **Start the bot**:
   ```bash
   python bot.py
   ```

## Requirements
- Python 3.x
- Discord.py
- Image and file handling libraries (e.g., Pillow, ffmpeg)

## Contributing
Pull requests are welcome! Feel free to create an issue if you have suggestions or encounter problems.

## License
This project is licensed under the **MIT License**.

