import os
import re
import json
import logging
from html import escape
from difflib import SequenceMatcher

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# --------- CONFIG ----------
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
# --------------------------

logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------- persistence ----------
def load_anime_names():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
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

# ---------- utilities ----------
def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# Clean leading bracket tags and extension
def strip_leading_tags_and_ext(s: str) -> str:
    s = s.strip()
    # drop leading bracket tags like [@CrunchyRollChannel]
    s = re.sub(r'^\[.*?\]\s*', '', s)
    # drop trailing extension if somehow present
    s = re.sub(r'\.\w{2,5}$', '', s)
    return s.strip()

def extract_info(filename: str):
    """
    Returns (name, season_str, episode_str, quality_str)
    filename: without path (may include extension)
    """
    fn_orig = filename or ""
    fn = strip_leading_tags_and_ext(fn_orig)
    if DEBUG:
        logger.debug("extract_info: raw='%s' stripped='%s'", fn_orig, fn)

    # 1) try combined SxxEyy (often best)
    combined = re.search(r'(?i)S0*(\d{1,2})\s*[^A-Za-z0-9]*E0*(\d{1,3})', fn)
    if combined:
        season_num = int(combined.group(1))
        ep_num = int(combined.group(2))
    else:
        # 2) try "Season 1 Episode 7"
        se = re.search(r'(?i)Season[\s._-]*0*(\d{1,2}).{0,10}?Episode[\s._-]*0*(\d{1,3})', fn)
        if se:
            season_num = int(se.group(1))
            ep_num = int(se.group(2))
        else:
            # 3) standalone episode or season tokens:
            ep_m = re.search(r'(?i)(?:E|Ep|Episode)[\s._-]*0*(\d{1,3})', fn)
            sn_m = re.search(r'(?i)S(?:eason)?[\s._-]*0*(\d{1,2})', fn)
            if ep_m:
                ep_num = int(ep_m.group(1))
            else:
                ep_num = None
            if sn_m:
                season_num = int(sn_m.group(1))
            else:
                season_num = None

    # default fallback
    if not season_num:
        season_num = 1
    if not ep_num:
        ep_num = 1

    sn = f"S{season_num:02d}"
    ep = f"{ep_num:02d}"

    # Quality: check common tokens first, then generic \d{3,4}p, then 4k
    q_m = re.search(r'(?i)\b(2160p|1080p|720p|480p|360p|240p|144p)\b', fn)
    if not q_m:
        q_m = re.search(r'(?i)\b(\d{3,4}p)\b', fn)
    if not q_m:
        q_m = re.search(r'(?i)\b(4k)\b', fn)
    quality = q_m.group(1).lower() if q_m else "480p"
    if quality == "4k":
        quality = "2160p"

    # Build a cleaned title by removing season/episode/quality + release tags
    t = fn
    # remove combined patterns like S01E07
    t = re.sub(r'(?i)S0*\d{1,2}\s*[^A-Za-z0-9]*E0*\d{1,3}', ' ', t)
    t = re.sub(r'(?i)Season[\s._-]*\d{1,2}[\s,._-]*Episode[\s._-]*\d{1,3}', ' ', t)
    t = re.sub(r'(?i)(?:E|Ep|Episode)[\s._-]*0*\d{1,3}', ' ', t)
    t = re.sub(r'(?i)S(?:eason)?[\s._-]*0*\d{1,2}', ' ', t)

    # release tags
    tags_pattern = r'(?i)\b(720p|1080p|2160p|4k|HEVC|x265|x264|10bit|8bit|BluRay|BDRip|WEBRip|HDTV|HDRip|DVDRip|WEB-DL|WEBDL|Dual[\s-]*Audio|ESub|SUB|AAC|AC3|remux|rip|brrip|dub|dubbed)\b'
    t = re.sub(tags_pattern, ' ', t)
    t = re.sub(r'[_\.\-]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()

    if DEBUG:
        logger.debug("extract_info: title-candidate='%s' season=%s episode=%s quality=%s", t, sn, ep, quality)

    # Try to match cleaned title against saved names (similarity threshold)
    name = None
    if t and not re.fullmatch(r'\d+', t):
        best_ratio = 0.0
        for n in anime_names:
            r = similar(t, n)
            if r > best_ratio:
                best_ratio = r
                name = n
        # require moderate similarity to use existing saved name
        if best_ratio >= 0.60:
            name = name
        else:
            name = t
            # persist learned name (avoid duplicates)
            if name not in anime_names:
                anime_names.append(name)
                save_anime_names(anime_names)
    else:
        # fallback: try matching the whole filename to saved names
        best_ratio = 0.0
        for n in anime_names:
            r = similar(fn, n)
            if r > best_ratio:
                best_ratio = r
                name = n
        if best_ratio < 0.5 or not name:
            name = "Unknown Anime"

    return name, sn, ep, quality

# ---------------- commands ----------------
@app.on_message(filters.command("start") & ~filters.me)
async def start(_, message: Message):
    await message.reply_text(
        "**👋 Welcome!**\nSend an anime file and I'll repost it with a generated caption and remove the original (if allowed).\nCommands: /addanime, /delanime, /listanime"
    )

@app.on_message(filters.command("addanime") & ~filters.me)
async def add_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /addanime <Anime Name>")
    if name in anime_names:
        return await message.reply_text("That name is already saved.")
    anime_names.append(name)
    save_anime_names(anime_names)
    await message.reply_text(f"Added: {escape(name)}")

@app.on_message(filters.command("delanime") & ~filters.me)
async def del_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /delanime <Anime Name>")
    try:
        anime_names.remove(name)
        save_anime_names(anime_names)
        await message.reply_text(f"Deleted: {escape(name)}")
    except ValueError:
        await message.reply_text("Name not found.")

@app.on_message(filters.command("listanime") & ~filters.me)
async def list_anime(_, message: Message):
    if not anime_names:
        return await message.reply_text("No saved anime names.")
    txt = "Saved names:\n" + "\n".join(f"• {escape(n)}" for n in anime_names)
    await message.reply_text(txt)

# ---------------- main media handler ----------------
@app.on_message((filters.document | filters.video | filters.audio) & ~filters.me)
async def on_media(_, message: Message):
    # protect against bot messages
    if message.from_user and message.from_user.is_bot:
        return

    media = message.document or message.video or message.audio
    if not media:
        return

    # get filename (fallback to caption)
    raw_name = getattr(media, "file_name", None) or (message.caption or "")
    filename = raw_name.rsplit(".", 1)[0]

    # extract
    anime_name, sn, ep, quality = extract_info(filename)
    if DEBUG:
        logger.debug("on_media: filename='%s' -> name='%s' sn=%s ep=%s quality=%s", filename, anime_name, sn, ep, quality)

    anime_name_safe = escape(anime_name)
    caption = DEFAULT_CAPTION.format(AnimeName=anime_name_safe, Sn=sn, Ep=ep, Quality=quality)

    # copy message with caption (preserves file, no re-upload)
    try:
        new_msg = await message.copy(chat_id=message.chat.id, caption=caption, parse_mode=ParseMode.HTML)
        logger.info("Copied message id=%s", getattr(new_msg, "message_id", None))
    except Exception as e:
        logger.exception("Failed to copy message: %s", e)
        return await message.reply_text("Failed to apply caption.")

    # try delete original (requires bot permission in groups)
    try:
        await message.delete()
        logger.info("Deleted original msg id=%s", getattr(message, "message_id", None))
    except Exception as e:
        logger.warning("Could not delete original: %s", e)
        # only warn in groups/channels
        if message.chat.type in ("group", "supergroup", "channel"):
            await message.reply_text("⚠️ I couldn't delete the original. Please give me Delete permission (make me admin).")

if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()
