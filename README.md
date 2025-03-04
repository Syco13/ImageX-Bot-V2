# ImageX Bot - Discord Image Converter

ImageX Bot is a powerful Discord bot that allows users to convert images between different formats directly within a Discord server. The bot supports multiple image formats, queue-based processing, and utilizes ImageMagick for enhanced conversions.

## Features

- Convert images between numerous formats (JPG, PNG, GIF, WEBP, etc.).
- Supports professional formats like PSD, AI, and PDF.
- Queue-based processing for efficient image handling.
- Metadata preservation and EXIF data transfer.
- Rate-limiting to prevent abuse.
- Error handling and logging.
- Slash commands for easy interaction.

## Supported Formats

The bot can handle a variety of image formats, including:
- **Web formats**: JPG, JPEG, PNG, GIF, BMP, WEBP
- **Professional formats**: PSD, AI, EPS, PDF, TIFF, SVG
- **Camera RAW formats**: HEIC, RAW, NEF, CR2, DNG, ARW
- **Special formats**: DDS, HDR, EXR, TGA

## Installation

### Requirements
- Python 3.8+
- Discord.py
- Pillow (PIL)
- ImageMagick (for advanced conversions)
- Additional dependencies from `requirements.txt`

### Setup

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/imagex-bot.git
   cd imagex-bot
   ```

2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```sh
   export DISCORD_TOKEN=your-bot-token
   export COMMAND_PREFIX="/"
   ```

4. Run the bot:
   ```sh
   python main.py
   ```

## Usage

### Commands

- `/convert <format>` - Convert an uploaded image to a specified format.
- `/formats` - Display a list of supported formats.
- `/status` - Check the bot's current queue and system status.
- `/logs` - Retrieve recent logs (Admin only).
- `/restart` - Restart the bot (Admin only).
- `/ping` - Check bot latency.
- `/stats` - View bot statistics.

### Example
To convert an image to PNG:
1. Use `/convert png` and upload an image.
2. The bot processes the image and returns the converted file.

## Configuration

The `config.py` file allows customization of:
- Maximum concurrent conversions
- Allowed file formats
- Image size limits
- Debug mode
- ImageMagick path settings

## Logging

The bot logs events using a rotating file logger in the `Logs` directory, tracking:
- Bot operations (`bot.log`)
- Conversion attempts (`conversions.log`)
- Errors (`errors.log`)

## Contributing

Contributions are welcome! Feel free to submit issues, feature requests, or pull requests to improve the bot.

## License

This project is licensed under the MIT License.

## Credits

Developed by Syco.

## Contact
For support or inquiries, join our Discord server or check out our GitHub repository: [GitHub Repository](https://github.com/yourusername/imagex-bot)

