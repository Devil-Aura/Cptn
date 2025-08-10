#!/usr/bin/env python3
import os
import re
import json
import logging
from html import escape
from difflib import SequenceMatcher
from typing import Tuple, Optional

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# -------------------- CONFIG --------------------
API_ID = int(os.environ.get("API_ID", "22768311"))       # Your API ID
API_HASH = os.environ.get("API_HASH", "702d8884f48b42e865425391432b3794")   # Your API Hash
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")# Your Bot Token
DATA_FILE = os.environ.get("DATA_FILE", "anime_names.json")
DEBUG = os.environ.get("DEBUG", "0") == "1"

DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel</b>"""
# ------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

anime_names = []
last_parsed = None  # For /debuglast command

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

def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_info(raw_filename: str) -> Tuple[str, str, str, str]:
    global anime_names, last_parsed

    if not raw_filename:
        return "Unknown Anime", "S01", "01", "480p"

    orig = raw_filename.strip()

    # 1) Extract Quality first from full filename (including extension)
    quality_pattern = re.compile(r'(?i)\b(2160p|4k|1080p|720p|480p|360p|240p|144p|\d{3,4}p)\b')
    q_match = quality_pattern.search(orig)
    quality = None
    if q_match:
        q_raw = q_match.group(1).lower()
        if q_raw == "4k":
            quality = "2160p"
        elif q_raw == "360p":
            quality = "480p"  # only convert 360p to 480p
        else:
            quality = q_raw
    else:
        quality = "480p"

    # 2) Extract Season & Episode from full filename (including extension)
    season_num: Optional[int] = None
    episode_num: Optional[int] = None

    combined_patterns = [
        re.compile(r'(?i)S0*(\d{1,2})[ ._\-]*E0*(\d{1,3})'),  # S01E07 or S01 E07 or S01-E07
    ]
    for pat in combined_patterns:
        m = pat.search(orig)
        if m:
            season_num = int(m.group(1))
            episode_num = int(m.group(2))
            break

    if season_num is None:
        m = re.search(r'(?i)Season[ .:_-]*0*(\d{1,2})', orig)
        if m:
            season_num = int(m.group(1))

    if episode_num is None:
        m = re.search(r'(?i)(?:Episode|Ep)[ .:_-]*0*(\d{1,3})', orig)
        if m:
            episode_num = int(m.group(1))

    if episode_num is None:
        m = re.search(r'(?i)E0*(\d{1,3})', orig)
        if m:
            episode_num = int(m.group(1))

    if season_num is None:
        m = re.search(r'(?i)S0*(\d{1,2})', orig)
        if m:
            season_num = int(m.group(1))

    if season_num is None:
        season_num = 1
    if episode_num is None:
        episode_num = 1

    sn = f"S{season_num:02d}"
    ep = f"{episode_num:02d}"

    # 3) For anime name, remove extension now (only last dot + ext)
    base_no_ext = re.sub(r'\.[A-Za-z0-9]{1,6}$', '', orig)

    # 4) Clean anime name by removing quality, season, episode info, tags, brackets etc.
    working = base_no_ext

    # Remove quality (already detected)
    working = re.sub(r'(?i)\b(2160p|4k|1080p|720p|480p|360p|240p|144p|\d{3,4}p)\b', ' ', working)

    # Remove season/episode patterns to clean title
    working = re.sub(r'(?i)S0*\d{1,2}[ ._\-]*E0*\d{1,3}', ' ', working)
    working = re.sub(r'(?i)Season[ .:_-]*0*\d{1,2}', ' ', working)
    working = re.sub(r'(?i)(Episode|Ep)[ .:_-]*0*\d{1,3}', ' ', working)
    working = re.sub(r'(?i)E0*\d{1,3}', ' ', working)
    working = re.sub(r'(?i)S0*\d{1,2}', ' ', working)

    # Remove bracketed groups e.g. [@CrunchyRollChannel], (Fansub)
    working = re.sub(r'[\[\(][^\]\)]+[\]\)]', ' ', working)

    # Remove common tags like HEVC, BluRay, Dual Audio etc.
    tags_pattern = re.compile(
        r'(?i)\b(HEVC|x265|x264|10bit|8bit|BluRay|BDRip|WEBRip|WEB[- ]?DL|WEBDL|HDTV|HDRip|DVDRip|Dual[\s-]*Audio|DualAudio|ESub|SUB|subs|subbed|AAC|AC3|remux|rip|brrip|dub|dubbed|proper|repack|extended)\b'
    )
    working = tags_pattern.sub(' ', working)

    # Remove stray digits and bitrates
    working = re.sub(r'\b\d{1,4}bit\b', ' ', working, flags=re.IGNORECASE)
    working = re.sub(r'\b\d{3,4}\b', ' ', working)

    # Clean extra spaces and underscores/dashes
    working = re.sub(r'[_\.\-]+', ' ', working)
    working = re.sub(r'\s+', ' ', working).strip()

    # Use cleaned working string as title candidate
    t = working if working else base_no_ext

    # Match closest anime name from saved list
    chosen_name = None
    if t and not re.fullmatch(r'\d+', t):
        best_ratio = 0.0
        best_name = None
        for n in anime_names:
            r = similar(t, n)
            if r > best_ratio:
                best_ratio = r
                best_name = n
        if best_ratio >= 0.60:
            chosen_name = best_name
        else:
            chosen_name = t
            if chosen_name not in anime_names:
                anime_names.append(chosen_name)
                try:
                    save_anime_names(anime_names)
                except Exception:
                    logger.exception("Error saving new anime name")
    else:
        # fallback to best match from full filename
        best_ratio = 0.0
        best_name = None
        for n in anime_names:
            r = similar(base_no_ext, n)
            if r > best_ratio:
                best_ratio = r
                best_name = n
        if best_ratio >= 0.5 and best_name:
            chosen_name = best_name
        else:
            chosen_name = "Unknown Anime"

    last_parsed = {
        "raw": orig,
        "base_no_ext": base_no_ext,
        "detected_quality": quality,
        "season": sn,
        "episode": ep,
        "title_candidate": t,
        "chosen_name": chosen_name
    }

    if DEBUG:
        logger.debug("Parsed file -> %s", json.dumps(last_parsed, ensure_ascii=False, indent=2))

    return chosen_name, sn, ep, quality


@app.on_message(filters.command("start") & ~filters.me)
async def cmd_start(_, message: Message):
    await message.reply_text(
        "**👋 Welcome to Auto Caption Bot**\n\n"
        "Send any anime file (video/document/audio) and I'll repost it with a generated caption (and remove the original if I can).\n\n"
        "Commands:\n"
        "/addanime <name> - Add a name manually\n"
        "/delanime <name> - Delete a name\n"
        "/listanime - Show saved names\n"
        "/debuglast - Show parsing of last processed file (debug)\n"
        "/help - Show help"
    )


@app.on_message(filters.command("help") & ~filters.me)
async def cmd_help(_, message: Message):
    await message.reply_text(
        "How I work:\n"
        "1) I detect QUALITY first (only convert 360p→480p).\n"
        "2) I detect SEASON & EPISODE next.\n"
        "3) I clean and learn the ANIME NAME.\n\n"
        "Make me group admin with 'Delete Messages' if you want originals removed automatically.\n"
        "Use DEBUG=1 env var to enable debug logs."
    )


@app.on_message(filters.command("addanime") & ~filters.me)
async def cmd_addanime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /addanime <Anime Name>")
    if not name:
        return await message.reply_text("Name is empty.")
    if name in anime_names:
        return await message.reply_text("Name already exists.")
    anime_names.append(name)
    save_anime_names(anime_names)
    await message.reply_text(f"✅ Added: {escape(name)}")


@app.on_message(filters.command("delanime") & ~filters.me)
async def cmd_delanime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /delanime <Anime Name>")
    try:
        anime_names.remove(name)
        save_anime_names(anime_names)
        await message.reply_text(f"🗑 Deleted: {escape(name)}")
    except ValueError:
        await message.reply_text("Name not found in saved list.")


@app.on_message(filters.command("listanime") & ~filters.me)
async def cmd_listanime(_, message: Message):
    if not anime_names:
        return await message.reply_text("No saved anime names yet.")
    txt = "📚 Saved Anime Names:\n" + "\n".join(f"• {escape(n)}" for n in anime_names)
    await message.reply_text(txt)


@app.on_message(filters.command("debuglast") & ~filters.me)
async def cmd_debuglast(_, message: Message):
    if last_parsed is None:
        return await message.reply_text("No file parsed yet.")
    j = json.dumps(last_parsed, ensure_ascii=False, indent=2)
    await message.reply_text(f"<pre>{escape(j)}</pre>", parse_mode=ParseMode.HTML)


@app.on_message((filters.document | filters.video | filters.audio) & ~filters.me)
async def on_media(_, message: Message):
    if message.from_user and message.from_user.is_bot:
        if DEBUG:
            logger.debug("Ignoring bot message from another bot")
        return

    media = message.document or message.video or message.audio
    if not media:
        return

    raw_name = getattr(media, "file_name", None) or (message.caption or "")
    if not raw_name:
        raw_name = getattr(media, "file_unique_id", "unknown_file")

    # Use full filename including extension for extraction
    try:
        anime_name, sn, ep, quality = extract_info(raw_name)
    except Exception as e:
        logger.exception("extract_info error: %s", e)
        anime_name, sn, ep, quality = "Unknown Anime", "S01", "01", "480p"

    anime_name_safe = escape(anime_name)

    caption = DEFAULT_CAPTION.format(AnimeName=anime_name_safe, Sn=sn, Ep=ep, Quality=quality)

    try:
        # Copy file with caption
        new_msg = await message.copy(
            chat_id=message.chat.id,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to copy message with caption: {e}")
        return

    try:
        # Delete original message if bot has rights
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete original message: {e}")

if __name__ == "__main__":
    logger.info("Starting Caption Bot...")
    app.run()
