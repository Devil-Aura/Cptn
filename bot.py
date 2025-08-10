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

<b>How to use:</b>
1. Add me to your channel as admin
2. Upload anime videos with filename format:
   <code>AnimeName S01E01 1080p.mp4</code>
3. I'll automatically add captions"""
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("addanime") & filters.private)
async def add_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
        if not name:
            raise ValueError("Empty name")
        
        if name in anime_names:
            await message.reply_text(f"⚠️ <b>{escape(name)}</b> already exists!", parse_mode=ParseMode.HTML)
            return
        
        anime_names.append(name)
        save_anime_names()
        await message.reply_text(f"✅ Added: <b>{escape(name)}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply_text("❌ Usage: /addanime <Anime Name>")
        logger.error(f"Add anime error: {e}")

@app.on_message(filters.command(["deleteanime", "delanime"]) & filters.private)
async def delete_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
        if not name:
            raise ValueError("Empty name")
        
        if name in anime_names:
            anime_names.remove(name)
            save_anime_names()
            await message.reply_text(f"🗑 Deleted: <b>{escape(name)}</b>", parse_mode=ParseMode.HTML)
        else:
            await message.reply_text(f"❌ <b>{escape(name)}</b> not found!", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply_text("❌ Usage: /deleteanime <Anime Name>")
        logger.error(f"Delete anime error: {e}")

@app.on_message(filters.command("listanime") & filters.private)
async def list_anime(_, message: Message):
    if not anime_names:
        await message.reply_text("📭 Anime database is empty!")
        return
    
    text = "📚 <b>Saved Anime Titles:</b>\n\n" + "\n".join(
        f"• {escape(name)}" for name in sorted(anime_names)
    )
    
    # Split long messages
    for i in range(0, len(text), 4000):
        await message.reply_text(
            text[i:i+4000],
            parse_mode=ParseMode.HTML
        )

# ----- Channel Handlers -----
@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("❌ Usage: /setcaption <caption_template>")
            return
        
        caption = message.text.split(None, 1)[1]
        channel_captions[message.chat.id] = caption
        await message.reply_text("✅ Custom caption set successfully!")
        logger.info(f"Set caption for channel {message.chat.id}")
    except Exception as e:
        logger.error(f"Set caption error: {e}")

@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
    await message.reply_text(
        f"<b>Current Caption Template:</b>\n\n{caption}",
        parse_mode=ParseMode.HTML
    )

@app.on_message(
    filters.channel & 
    (filters.video | filters.document) &
    ~filters.edited
)
async def handle_media(_, message: Message):
    try:
        # Get filename
        if message.video:
            filename = message.video.file_name
        elif message.document:
            filename = message.document.file_name
        else:
            return
        
        if not filename:
            logger.warning(f"No filename in message {message.id}")
            return
        
        logger.info(f"Processing file: {filename}")
        
        # Extract metadata
        match = re.search(
            r"(?:\[.*?\]\s*)?(.+?)\s+(S\d+)(E\d+).*?(\d{3,4}p)",
            filename,
            re.IGNORECASE
        )
        
        if not match:
            logger.warning(f"Failed to parse filename: {filename}")
            return
        
        anime_name, season, episode, quality = match.groups()
        episode = episode.replace("E", "")
        quality = quality.replace("360p", "480p")
        
        # Get caption template
        caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
        formatted_caption = caption.format(
            AnimeName=anime_name.strip(),
            Sn=season.upper(),
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
            await message.reply_text(f"❌ Error: {str(e)}")
        except:
            pass

# ----- Startup -----
if __name__ == "__main__":
    load_anime_names()
    logger.info("Starting bot...")
    app.run()
