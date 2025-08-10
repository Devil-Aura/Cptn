#!/usr/bin/env python3
import os
import re
import json
import logging
from html import escape
from difflib import SequenceMatcher
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

# ---------- DB LOAD / SAVE ----------
def load_anime_names() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                logger.info(f"Loaded {len(data)} anime names")
                return data
    except Exception:
        logger.exception("Failed to load anime names file")
    return []

def save_anime_names(names: list):
    try:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(names, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)
        logger.debug(f"Saved {len(names)} anime names")
    except Exception:
        logger.exception("Failed to save anime names")

anime_names = load_anime_names()

# ---------- UTILS ----------
def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_info(raw_filename: str) -> Tuple[str, str, str, str]:
    global anime_names, last_parsed

    orig = raw_filename.strip()

    # More flexible regex:
    # Captures: Anime Name, Season (optional), Episode (optional), Quality (optional)
    match = re.search(
        r"(?:\[.*?\]\s*)?(.+?)(?:[\s._-]+S?(\d{1,2}))?(?:[ ._-]*E?(\d{1,3}))?.*?(2160p|4k|1080p|720p|480p|360p)?",
        orig,
        re.IGNORECASE
    )

    if match:
        anime_raw, season_num, ep_num, quality = match.groups()

        # Normalize season
        if not season_num or season_num == "0":
            season_num = "1"
        season_num = f"S{int(season_num):02d}"

        # Normalize episode
        if not ep_num:
            ep_num = "??"  # Unknown episode instead of forcing 01
        else:
            ep_num = f"{int(ep_num):02d}"

        # Normalize quality
        quality = (quality or "480p").lower()
        quality = "2160p" if quality == "4k" else quality
        quality = quality.replace("360p", "480p")

        # Clean anime name
        clean = re.sub(r'[_\-.]+', ' ', anime_raw).strip()

        # Match closest saved anime name
        best_ratio, best_name = 0.0, None
        for n in anime_names:
            ratio = similar(clean, n)
            if ratio > best_ratio:
                best_ratio, best_name = ratio, n

        chosen_name = best_name if best_ratio >= 0.6 else clean

        if chosen_name not in anime_names:
            anime_names.append(chosen_name)
            save_anime_names(anime_names)

        last_parsed = {
            "filename": orig,
            "anime_name": chosen_name,
            "season": season_num,
            "episode": ep_num,
            "quality": quality
        }

        return chosen_name, season_num, ep_num, quality

    # Fallback if regex completely fails
    return "Unknown Anime", "S01", "??", "480p"

# ---------- COMMANDS ----------
@app.on_message(filters.command("start") & ~filters.me)
async def cmd_start(client, message: Message):
    await message.reply_text(
        "**👋 Welcome to Auto Caption Bot**\n\n"
        "Send anime video/audio/document files, I'll repost with captions automatically.\n\n"
        "Commands:\n"
        "/addanime <name> - Add anime name manually\n"
        "/delanime <name> - Delete anime name\n"
        "/listanime - List saved anime names\n"
        "/debuglast - Show last file parsing debug info\n"
        "/help - Show this help"
    )

@app.on_message(filters.command("help") & ~filters.me)
async def cmd_help(client, message: Message):
    await message.reply_text(
        "How I work:\n"
        "1) Extract QUALITY first (only 360p → 480p conversion).\n"
        "2) Extract SEASON & EPISODE (handles missing ones).\n"
        "3) Clean and learn ANIME NAME.\n\n"
        "Make me admin with Delete Messages permission to remove originals."
    )

@app.on_message(filters.command("addanime") & ~filters.me)
async def cmd_addanime(client, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /addanime <Anime Name>")
    if not name:
        return await message.reply_text("Anime name cannot be empty.")
    if name in anime_names:
        return await message.reply_text("Anime name already exists.")
    anime_names.append(name)
    save_anime_names(anime_names)
    await message.reply_text(f"✅ Added: {escape(name)}")

@app.on_message(filters.command("delanime") & ~filters.me)
async def cmd_delanime(client, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /delanime <Anime Name>")
    try:
        anime_names.remove(name)
        save_anime_names(anime_names)
        await message.reply_text(f"🗑 Deleted: {escape(name)}")
    except ValueError:
        await message.reply_text("Anime name not found in list.")

@app.on_message(filters.command("listanime") & ~filters.me)
async def cmd_listanime(client, message: Message):
    if not anime_names:
        return await message.reply_text("No saved anime names.")
    txt = "📚 Saved Anime Names:\n" + "\n".join(f"• {escape(n)}" for n in anime_names)
    await message.reply_text(txt)

@app.on_message(filters.command("debuglast") & ~filters.me)
async def cmd_debuglast(client, message: Message):
    global last_parsed
    if not last_parsed:
        return await message.reply_text("No file parsed yet.")
    await message.reply_text(f"<pre>{escape(json.dumps(last_parsed, indent=2, ensure_ascii=False))}</pre>", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setcaption Your_Custom_Caption_With_Placeholders")
    custom_caption = message.text.split(" ", 1)[1]
    channel_captions[message.chat.id] = custom_caption
    await message.reply_text("✅ Custom caption set successfully!")

@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    current_caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
    await message.reply_text(f"**Current Caption Template:**\n\n{current_caption}")

# ---------- MEDIA HANDLER ----------
@app.on_message((filters.document | filters.video | filters.audio) & ~filters.me)
async def on_media(client, message: Message):
    media = message.document or message.video or message.audio
    if not media or not media.file_name:
        return

    full_filename = media.file_name

    try:
        anime_name, sn, ep, quality = extract_info(full_filename)
    except Exception as e:
        logger.exception("extract_info error: %s", e)
        anime_name, sn, ep, quality = "Unknown Anime", "S01", "??", "480p"

    caption_template = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
    caption = caption_template.format(
        AnimeName=escape(anime_name),
        Sn=sn,
        Ep=ep,
        Quality=quality
    )

    try:
        new_msg = await message.copy(
            chat_id=message.chat.id,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to copy message with caption: {e}")
        return

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete original message: {e}")

# ---------- START BOT ----------
if __name__ == "__main__":
    logger.info("Starting Auto Caption Bot...")
    app.run()
