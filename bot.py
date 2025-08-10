from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import re
import json
import os
from html import escape
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# BOT CONFIG
API_ID = 22768311
API_HASH = "702d8884f48b42e865425391432b3794"
BOT_TOKEN = ""  # Replace with your actual token
DATA_FILE = "anime_names.json"

# Default Caption Template
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel</b>"""

# In-Memory Storage
channel_captions = {}
anime_names = []

app = Client(
    "AutoCaptionBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ----- Helper Functions -----
def load_anime_names():
    global anime_names
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                anime_names = json.load(f)
                logger.info(f"Loaded {len(anime_names)} anime names")
        else:
            anime_names = []
    except Exception as e:
        logger.error(f"Error loading anime names: {e}")
        anime_names = []

def save_anime_names():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(anime_names, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(anime_names)} anime names")
    except Exception as e:
        logger.error(f"Error saving anime names: {e}")

def parse_filename(filename):
    """Improved filename parser that handles various formats"""
    # Remove channel name if present
    clean_name = re.sub(r'\[@?\w+\s*\w*\]', '', filename, flags=re.IGNORECASE)
    
    # Try multiple patterns to extract info
    patterns = [
        r"(?:.*?)(.+?)\s+(S\d+)(?:E|Ep|EP|_)(\d+).*?(\d{3,4})p",  # S01E01 1080p
        r"(?:.*?)(.+?)\s+-\s+(\d+)\s+\((\d{3,4})p\)",              # Name - 01 (1080p)
        r"(?:.*?)(.+?)\s+(\d+)\.(\d{3,4})p",                       # Name 01.1080p
        r"(?:.*?)(.+?)\s+Episode\s+(\d+)\s+(\d{3,4})p"             # Name Episode 01 1080p
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            if len(match.groups()) == 4:
                anime_name, season, episode, quality = match.groups()
                season = season.upper()
            else:
                anime_name, episode, quality = match.groups()
                season = "S01"  # Default season
            
            # Clean quality (convert 360p to 480p and make 'p' lowercase)
            quality = quality.lower()
            if quality == "360p":
                quality = "480p"
            else:
                quality = f"{quality}p" if not quality.endswith("p") else quality
            
            # Clean anime name
            anime_name = re.sub(r'[_\-.]+', ' ', anime_name).strip()
            
            return anime_name, season, episode, quality
    
    return None

# ----- Command Handlers -----
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text(
        "🤖 <b>Auto Caption Bot</b>\n\n"
        "I automatically add captions to anime videos in channels.\n\n"
        "Add me to your channel as admin with:\n"
        "- Post Messages permission\n"
        "- Delete Messages permission (optional)\n\n"
        "Use /help for commands",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(_, message: Message):
    help_text = """<b>Available Commands:</b>

<b>Channel Commands:</b>
/setcaption - Set custom caption template
/showcaption - Show current caption

<b>Anime Database:</b>
/addanime - Add new anime title
/deleteanime - Remove anime title
/listanime - List all anime titles

<b>Supported Filename Formats:</b>
- AnimeName S01E01 1080p.mkv
- [Group] Anime Name - 01 (720p).mp4
- Anime.Name.Episode.01.480p.mkv
- Anime Name Episode 01 360p.mp4"""
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)

# ... [keep all other command handlers the same as previous version] ...

# ----- Channel Handlers -----
@app.on_message(filters.channel & (filters.video | filters.document))
async def handle_media(_, message: Message):
    try:
        # Get filename
        if message.video:
            filename = message.video.file_name or ""
        elif message.document:
            filename = message.document.file_name or ""
        else:
            return
        
        logger.info(f"Processing file: {filename}")
        
        # Parse filename
        parsed = parse_filename(filename)
        if not parsed:
            logger.warning(f"Failed to parse filename: {filename}")
            return
        
        anime_name, season, episode, quality = parsed
        
        # Get caption template
        caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
        formatted_caption = caption.format(
            AnimeName=anime_name,
            Sn=season,
            Ep=episode,
            Quality=quality
        )
        
        # Repost with caption
        if message.video:
            await message.reply_video(
                message.video.file_id,
                caption=formatted_caption,
                parse_mode=ParseMode.HTML
            )
        else:
            await message.reply_document(
                message.document.file_id,
                caption=formatted_caption,
                parse_mode=ParseMode.HTML
            )
        
        # Try to delete original
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Couldn't delete original: {e}")
        
        logger.info(f"Processed {filename} successfully")
        
    except Exception as e:
        logger.error(f"Error processing media: {e}")
        try:
            await message.reply_text(f"❌ Error processing file: {str(e)[:100]}")
        except:
            pass

# ----- Startup -----
if __name__ == "__main__":
    load_anime_names()
    logger.info("Starting bot...")
    app.run()
