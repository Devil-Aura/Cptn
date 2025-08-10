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
BOT_TOKEN = ""
DATA_FILE = "anime_names.json"
BIG_ANIME_FILE = "big_anime_names.json"  # New file for big anime names

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
big_anime_names = []  # For complex/long anime names

app = Client(
    "AutoCaptionBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ----- Helper Functions -----
def load_data():
    global anime_names, big_anime_names
    try:
        # Load regular anime names
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                anime_names = json.load(f)
        
        # Load big anime names
        if os.path.exists(BIG_ANIME_FILE):
            with open(BIG_ANIME_FILE, "r", encoding="utf-8") as f:
                big_anime_names = json.load(f)
                
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        anime_names = []
        big_anime_names = []

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(anime_names, f, ensure_ascii=False, indent=2)
        with open(BIG_ANIME_FILE, "w", encoding="utf-8") as f:
            json.dump(big_anime_names, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def parse_standard_filename(filename):
    """Parser for normal filenames"""
    match = re.search(
        r"(.*?)\s*(?:S|Season\s*)(\d+)(?:\s*E|Ep|Episode\s*)(\d+).*?(\d{3,4})p?", 
        filename,
        re.IGNORECASE
    )
    if match:
        anime_name, season, episode, quality = match.groups()
        anime_name = re.sub(r'[_\-.]+', ' ', anime_name).strip()
        season = f"S{int(season):02d}"
        episode = f"{int(episode):02d}"
        quality = "480p" if quality.lower() == "360" or quality.lower() == "360p" else f"{quality.lower()}p"
        return anime_name, season, episode, quality
    return None

def parse_big_filename(filename):
    """Special parser for complex/long filenames"""
    # Try to match against known big anime names
    for anime in big_anime_names:
        if anime.lower() in filename.lower():
            # Extract season/episode/quality
            match = re.search(
                r"(?:S|Season\s*)(\d+)(?:\s*E|Ep|Episode\s*)(\d+).*?(\d{3,4})p?",
                filename,
                re.IGNORECASE
            )
            if match:
                season, episode, quality = match.groups()
                season = f"S{int(season):02d}"
                episode = f"{int(episode):02d}"
                quality = "480p" if quality.lower() in ["360", "360p"] else f"{quality.lower()}p"
                return anime, season, episode, quality
    
    # Fallback extraction if no match found
    match = re.search(
        r"(?:S|Season\s*)(\d+)(?:\s*E|Ep|Episode\s*)(\d+).*?(\d{3,4})p?",
        filename,
        re.IGNORECASE
    )
    if match:
        season, episode, quality = match.groups()
        # Try to extract anime name by removing known patterns
        anime_name = re.sub(
            r'\[.*?\]|\(.*?\)|@\w+|S\d+E\d+|\d{3,4}p?|HEVC|10bit|BluRay|Dual Audio|ESub|WEB-DL|HD',
            '',
            filename,
            flags=re.IGNORECASE
        )
        anime_name = re.sub(r'[_\-.]+', ' ', anime_name).strip()
        season = f"S{int(season):02d}"
        episode = f"{int(episode):02d}"
        quality = "480p" if quality.lower() in ["360", "360p"] else f"{quality.lower()}p"
        return anime_name, season, episode, quality
    
    return None

# ----- Command Handlers -----
@app.on_message(filters.command("addbiganime") & filters.private)
async def add_big_anime(_, message: Message):
    """Add a complex anime name to special list"""
    try:
        name = message.text.split(None, 1)[1].strip()
        if not name:
            raise ValueError("Empty name")
        
        if name in big_anime_names:
            await message.reply_text(f"⚠️ Already in big anime list: {escape(name)}")
            return
        
        big_anime_names.append(name)
        save_data()
        await message.reply_text(f"✅ Added big anime: {escape(name)}")
    except Exception as e:
        await message.reply_text("❌ Usage: /addbiganime <Anime Name>")
        logger.error(f"Add big anime error: {e}")

# [Keep all other command handlers...]

# ----- Media Handler -----
@app.on_message(filters.channel & (filters.video | filters.document))
async def handle_media(_, message: Message):
    try:
        filename = message.video.file_name if message.video else message.document.file_name
        if not filename:
            return
        
        logger.info(f"Processing: {filename}")
        
        # First try standard parser
        parsed = parse_standard_filename(filename)
        
        # If standard parser fails, try big filename parser
        if not parsed:
            parsed = parse_big_filename(filename)
            if parsed:
                logger.info(f"Used big filename parser for: {filename}")
        
        if not parsed:
            logger.warning(f"Failed to parse: {filename}")
            return
        
        anime_name, season, episode, quality = parsed
        
        # Send with caption
        caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION).format(
            AnimeName=anime_name,
            Sn=season,
            Ep=episode,
            Quality=quality
        )
        
        if message.video:
            await message.reply_video(
                message.video.file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        else:
            await message.reply_document(
                message.document.file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
            
        try:
            await message.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Media handler error: {e}")

# ----- Startup -----
if __name__ == "__main__":
    load_data()
    logger.info("Starting bot...")
    app.run()
