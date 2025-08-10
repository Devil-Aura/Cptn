#!/usr/bin/env python3
import os
import re
import json
import logging
from html import escape
from typing import Tuple

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# -------- CONFIG --------
API_ID = int(os.environ.get("API_ID", "22768311"))
API_HASH = os.environ.get("API_HASH", "702d8884f48b42e865425391432b3794")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "anime_names.json"
DEBUG = os.environ.get("DEBUG", "0") == "1"

DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel</b>"""
# ------------------------

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

anime_names = []
last_parsed = None
channel_captions = {}

def load_anime_names():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load anime names")
        return []

def save_anime_names(names):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(names, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("Failed to save anime names")

anime_names = load_anime_names()

def extract_info(filename: str) -> Tuple[str, str, str, str]:
    global last_parsed
    
    # Remove extension
    clean_name = re.sub(r'\.[^.]+$', '', filename)
    
    # Extract quality first (most reliable pattern)
    quality = "480p"
    quality_match = re.search(r'(?i)(2160p|4k|1080p|720p|480p|360p)', clean_name)
    if quality_match:
        q = quality_match.group(1).lower()
        quality = "2160p" if q == "4k" else q
        quality = "480p" if q == "360p" else quality
    
    # Extract season and episode
    season = "01"
    episode = "01"
    
    # Try SXXEXX pattern first
    ep_match = re.search(r'(?i)S(\d{1,2})E(\d{1,3})', clean_name)
    if ep_match:
        season = ep_match.group(1).zfill(2)
        episode = ep_match.group(2).zfill(2)
    else:
        # Try separate SXX and EXX patterns
        s_match = re.search(r'(?i)S(\d{1,2})', clean_name)
        if s_match:
            season = s_match.group(1).zfill(2)
        
        e_match = re.search(r'(?i)E(\d{1,3})', clean_name)
        if e_match:
            episode = e_match.group(1).zfill(2)
        else:
            # Try standalone episode number
            e_match = re.search(r'(?i)(?:^|[ ._-])(\d{1,3})(?:$|[ ._-])', clean_name)
            if e_match:
                episode = e_match.group(1).zfill(2)
    
    # Extract anime name by removing all metadata
    anime_name = clean_name
    patterns_to_remove = [
        r'(?i)\[@CrunchyRollChannel\]',
        r'(?i)S\d{1,2}E\d{1,3}',
        r'(?i)S\d{1,2}',
        r'(?i)E\d{1,3}',
        r'(?i)\d{1,3}(?:$|[ ._-])',
        r'(?i)(2160p|4k|1080p|720p|480p|360p)',
        r'(?i)(HEVC|x265|x264|10bit|8bit|BluRay|BDRip|WEBRip|WEB[- ]?DL|WEBDL|HDTV|HDRip|DVDRip)',
        r'(?i)(Dual[\s-]*Audio|DualAudio|ESub|SUB|subs|subbed|AAC|AC3|remux|rip|brrip|dub|dubbed|proper|repack|extended)',
        r'\[.*?\]',
        r'\(.*?\)',
        r'[_.-]{2,}',
    ]
    
    for pattern in patterns_to_remove:
        anime_name = re.sub(pattern, ' ', anime_name)
    
    anime_name = re.sub(r'\s+', ' ', anime_name).strip()
    
    # Store parsed data for debugging
    last_parsed = {
        "filename": filename,
        "anime_name": anime_name,
        "season": season,
        "episode": episode,
        "quality": quality
    }
    
    return anime_name, f"S{season}", episode, quality

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("I'm an auto-caption bot for anime files")

@app.on_message(filters.command("debuglast"))
async def debug_last(client, message):
    if last_parsed:
        await message.reply_text(f"<pre>{escape(str(last_parsed))}</pre>", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text("No file parsed yet")

@app.on_message((filters.document | filters.video | filters.audio) & ~filters.me)
async def handle_media(client, message):
    media = message.document or message.video or message.audio
    if not media or not media.file_name:
        return
    
    try:
        anime_name, sn, ep, quality = extract_info(media.file_name)
        
        # Get custom caption or use default
        caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
        formatted_caption = caption.format(
            AnimeName=escape(anime_name),
            Sn=sn,
            Ep=ep,
            Quality=quality
        )
        
        # Resend with caption
        await message.copy(
            chat_id=message.chat.id,
            caption=formatted_caption,
            parse_mode=ParseMode.HTML
        )
        
        # Delete original if possible
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Couldn't delete original: {e}")
            
    except Exception as e:
        logger.error(f"Error processing media: {e}")
        await message.reply_text(f"Error processing file: {e}")

if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()
