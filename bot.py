#!/usr/bin/env python3
"""
Auto Caption Bot (full)
- Extracts quality (360p->480p only), season, episode, then cleans title.
- Applies caption on the file (copy) and deletes original (if permitted).
- Persists learned anime names to anime_names.json.
- Commands: /start, /help, /addanime, /delanime, /listanime, /debuglast
"""
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

# ---------- CONFIG ----------
API_ID = int(os.environ.get("API_ID", "22768311"))       # or set real value
API_HASH = os.environ.get("API_HASH", "702d8884f48b42e865425391432b3794")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = os.environ.get("DATA_FILE", "anime_names.json")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# Caption template (HTML safe — we'll escape dynamic parts)
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel</b>"""
# ----------------------------

# Logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Pyrogram client
app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory persistence
anime_names = []  # list[str]
last_parsed = None  # store last parsed info for /debuglast


# ---------- Persistence helpers ----------
def load_anime_names() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                logger.info("Loaded %d anime names", len(data))
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
        logger.debug("Saved %d anime names", len(names))
    except Exception:
        logger.exception("Failed to save anime names")


anime_names = load_anime_names()


# ---------- Utility helpers ----------
def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# Robust extractor: QUALITY first, then SEASON & EPISODE, then TITLE clean-up
def extract_info(raw_filename: str) -> Tuple[str, str, str, str]:
    """
    Returns (anime_name, season_str, episode_str, quality_str)
    raw_filename: filename or caption without extension OR with extension (we will strip ext).
    """
    global anime_names, last_parsed

    if not raw_filename:
        return "Unknown Anime", "S01", "01", "480p"

    # keep original for debug
    orig = raw_filename.strip()

    # remove trailing path pieces and extension
    # if someone sends "file.mkv" remove .mkv
    base = orig.rsplit("/", 1)[-1]
    base_no_ext = re.sub(r'\.[A-Za-z0-9]{1,6}$', '', base).strip()

    working = base_no_ext

    if DEBUG:
        logger.debug("extract_info: start raw='%s' base_no_ext='%s'", orig, base_no_ext)

    # Normalize separators to spaces (but keep bracketed groups for now)
    working = re.sub(r'[_\.\-]+', ' ', working)

    # ---------- 1) QUALITY (first)
    # detect explicit tokens and generic pattern
    quality_pattern = re.compile(r'(?i)\b(2160p|4k|1080p|720p|480p|360p|240p|144p|\d{3,4}p)\b')
    q_match = quality_pattern.search(working)
    quality = None
    if q_match:
        q_raw = q_match.group(1)
        q_low = q_raw.lower()
        # normalize 4k -> 2160p
        if q_low == "4k":
            quality = "2160p"
        else:
            quality = q_low
        # convert only 360p -> 480p per your requirement
        if quality == "360p":
            quality = "480p"
        # remove the matched quality token from working string to avoid interference
        working = re.sub(re.escape(q_match.group(0)), ' ', working, flags=re.IGNORECASE)
    else:
        # no quality token found -> default fallback (use 480p to match previous behaviour)
        quality = "480p"

    # ---------- 2) SEASON & EPISODE (second)
    season_num: Optional[int] = None
    episode_num: Optional[int] = None

    # Try patterns in order (combined first)
    # pattern A: S01E07, S01.E07, S01 E07, S01-E07, S01E07 (no sep)
    combined_patterns = [
        re.compile(r'(?i)\bS0*(\d{1,2})\s*[.\-_\s]*E0*(\d{1,3})\b'),
        re.compile(r'(?i)\bS0*(\d{1,2})E0*(\d{1,3})\b'),
    ]
    for pat in combined_patterns:
        m = pat.search(working)
        if m:
            season_num = int(m.group(1))
            episode_num = int(m.group(2))
            # remove matched text
            working = working[:m.start()] + ' ' + working[m.end():]
            break

    # pattern B: "Season 1 Episode 7" or "Season 1 Ep 7"
    if season_num is None:
        m = re.search(r'(?i)\bSeason[\s:.]*0*(\d{1,2})\b', working)
        if m:
            season_num = int(m.group(1))
            working = working[:m.start()] + ' ' + working[m.end():]

    if episode_num is None:
        m = re.search(r'(?i)\b(?:Episode|Ep)\b[\s:.]*0*(\d{1,3})\b', working)
        if m:
            episode_num = int(m.group(1))
            working = working[:m.start()] + ' ' + working[m.end():]

    # pattern C: standalone E07 or E 07 (sometimes)
    if episode_num is None:
        m = re.search(r'(?i)\bE0*(\d{1,3})\b', working)
        if m:
            episode_num = int(m.group(1))
            working = working[:m.start()] + ' ' + working[m.end():]

    # pattern D: standalone S01 (season only)
    if season_num is None:
        m = re.search(r'(?i)\bS0*(\d{1,2})\b', working)
        if m:
            season_num = int(m.group(1))
            working = working[:m.start()] + ' ' + working[m.end():]

    # fallbacks
    if season_num is None:
        season_num = 1
    if episode_num is None:
        episode_num = 1

    sn = f"S{season_num:02d}"
    ep = f"{episode_num:02d}"

    # ---------- 3) TITLE clean-up (after removing quality & S/E tokens)
    t = working

    # remove bracketed groups anywhere (e.g., [@CrunchyRollChannel], (Fansub))
    t = re.sub(r'[\[\(]\s*[@A-Za-z0-9_\- .:;!#&\'"()]+\s*[\]\)]', ' ', t)
    # remove leftover bracket artifacts just in case
    t = re.sub(r'[\[\]\(\)\{\}]', ' ', t)

    # remove typical release tags/words
    tags_pattern = re.compile(
        r'(?i)\b(HEVC|x265|x264|10bit|8bit|BluRay|BDRip|WEBRip|WEB[- ]?DL|WEBDL|HDTV|HDRip|DVDRip|Dual[\s-]*Audio|DualAudio|ESub|SUB|subs|subbed|AAC|AC3|remux|rip|brrip|dub|dubbed|proper|repack|extended)\b'
    )
    t = tags_pattern.sub(' ', t)

    # remove stray bitrate / codec numbers like "10bit" or "2.0" etc. (we already removed 10bit above)
    t = re.sub(r'\b\d{1,4}bit\b', ' ', t, flags=re.IGNORECASE)
    # remove leftover isolated tokens like "1080", "720" that are not part of p (but safer to remove p ones are handled)
    t = re.sub(r'\b\d{3,4}\b', ' ', t)

    # collapse separators and whitespace
    t = re.sub(r'[_\.\-]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()

    # If after cleaning the title is empty, fallback to original base name
    if not t:
        t = base_no_ext

    # Now try to match to saved names (reuse if similar)
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
            # persist learn
            if chosen_name not in anime_names:
                anime_names.append(chosen_name)
                try:
                    save_anime_names(anime_names)
                except Exception:
                    logger.exception("Error saving new anime name")
    else:
        # fallback: try matching raw base_no_ext to saved names
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

    # store last parsed info (for /debuglast)
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


# ---------- Commands ----------
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
    # present parse result nicely
    j = json.dumps(last_parsed, ensure_ascii=False, indent=2)
    # Keep message short; escape HTML
    await message.reply_text(f"<pre>{escape(j)}</pre>", parse_mode=ParseMode.HTML)


# ---------- Main media handler ----------
@app.on_message((filters.document | filters.video | filters.audio) & ~filters.me)
async def on_media(_, message: Message):
    # ignore bot-originated messages (avoid loops)
    if message.from_user and message.from_user.is_bot:
        if DEBUG:
            logger.debug("Ignored bot-originated message")
        return

    media = message.document or message.video or message.audio
    if not media:
        return

    # prefer file_name; fallback to caption; fallback to unique id
    raw_name = getattr(media, "file_name", None) or (message.caption or "")
    if not raw_name:
        raw_name = getattr(media, "file_unique_id", "unknown_file")

    # remove surrounding quotes sometimes present
    raw_name = raw_name.strip().strip('"').strip("'")

    # strip extension for parsing (extract_info handles it too)
    file_display_name = raw_name.rsplit(".", 1)[0]

    try:
        anime_name, sn, ep, quality = extract_info(file_display_name)
    except Exception as e:
        logger.exception("extract_info error: %s", e)
        anime_name, sn, ep, quality = "Unknown Anime", "S01", "01", "480p"

    # escape AnimeName for HTML
    anime_name_safe = escape(anime_name)

    caption = DEFAULT_CAPTION.format(AnimeName=anime_name_safe, Sn=sn, Ep=ep, Quality=quality)

    # copy message and apply caption (no re-upload)
    try:
        new_msg = await message.copy(chat_id=message.chat.id, caption=caption, parse_mode=ParseMode.HTML)
        logger.info("Copied message id=%s for file='%s'", getattr(new_msg, "message_id", None), raw_name)
    except Exception as e:
        logger.exception("Failed to copy message: %s", e)
        await message.reply_text("❌ Failed to apply caption (copy/send failed).")
        return

    # try to delete the original (may fail without permission)
    try:
        await message.delete()
        logger.info("Deleted original message id=%s", getattr(message, "message_id", None))
    except Exception as e:
        logger.warning("Could not delete original message: %s", e)
        # Only notify in groups/channels to avoid spam in private chats
        if message.chat.type in ("group", "supergroup", "channel"):
            try:
                await message.reply_text("⚠️ I couldn't delete the original. Give me 'Delete Messages' permission (make me admin) if you want originals removed.")
            except Exception:
                logger.debug("Couldn't send deletion warning message (suppressed).")


# ---------- start ----------
if __name__ == "__main__":
    logger.info("Starting Auto Caption Bot...")
    app.run()
