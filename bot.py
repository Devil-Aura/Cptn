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
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
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
    """Advanced filename parser that handles complex patterns"""
    if not filename:
        return None
    
    # Remove common tags and brackets
    clean_name = re.sub(r'\[.*?\]|\(.*?\)|@\w+', '', filename)
    
    # Try multiple patterns in order of priority
    patterns = [
        # Pattern 1: Standard SXXEXX with quality
        r"(.*?)\s*(?:S|Season\s*)(\d+)(?:\s*E|Ep|Episode\s*)(\d+).*?(\d{3,4}(?:p|P))",
        # Pattern 2: Episode XX with quality
        r"(.*?)\s*(?:Ep|Episode\s*)(\d+).*?(\d{3,4}(?:p|P))",
        # Pattern 3: Just quality at end
        r"(.*?)\s*(\d{3,4}(?:p|P))\b"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 4:
                anime_name, season, episode, quality = groups
                season = f"S{int(season):02d}"
            elif len(groups) == 3:
                anime_name, episode, quality = groups
                season = "S01"  # Default season
            elif len(groups) == 2:
                anime_name, quality = groups
                season = "S01"
                episode = "01"    # Default episode
            
            # Clean extracted values
            anime_name = re.sub(r'[_\-.]+', ' ', anime_name).strip()
            episode = f"{int(episode):02d}" if episode else "01"
            
            # Process quality (convert 360p to 480p and lowercase p)
            quality = quality.lower()
            if quality == "360p":
                quality = "480p"
            elif not quality.endswith("p"):
                quality = f"{quality}p"
            
            return anime_name, season, episode, quality
    
    return None

# ----- Command Handlers -----
# [Keep all your existing command handlers unchanged]
# ...

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
        
        logger.info(f"Successfully processed: {filename}")
        
    except Exception as e:
        logger.error(f"Error processing media: {e}")
        try:
            await message.reply_text(f"❌ Error: {str(e)[:100]}")
        except:
            pass

# ----- Startup -----
if __name__ == "__main__":
    load_anime_names()
    logger.info("Starting bot...")
    app.run()
