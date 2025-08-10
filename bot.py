import os
import re
import json
import logging
from html import escape
from difflib import SequenceMatcher

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# -------- CONFIG ----------
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

# Extracts quality first, then season/episode, then builds cleaned title for anime name
def extract_info(filename: str):
    fn_raw = (filename or "").strip()
    fn = fn_raw  # keep original for extraction
    if DEBUG:
        logger.debug("extract_info: raw filename='%s'", fn_raw)

    # 1) Quality first (so quality detection isn't affected by cleaning)
    # Recognize specific tokens first, then generic \d{3,4}p, and 4k -> 2160p
    q_m = re.search(r'(?i)\b(2160p|1080p|720p|480p|360p|240p|144p)\b', fn)
    if not q_m:
        q_m = re.search(r'(?i)\b(\d{3,4}p)\b', fn)
    if not q_m:
        q_m = re.search(r'(?i)\b4k\b', fn)
    quality = q_m.group(1).lower() if q_m else None
    if quality == "4k":
        quality = "2160p"
    # Convert 360p -> 480p only (per your request)
    if quality == "360p":
        quality = "480p"
    if not quality:
        quality = "480p"  # fallback default

    # 2) Season & Episode (robust matching)
    season_num = None
    ep_num = None

    # Combined patterns (S01E07, S01.E07, S01 E07 etc.)
    combined = re.search(r'(?i)S0*(\d{1,2})\s*[^A-Za-z0-9]{0,3}E0*(\d{1,3})', fn)
    if combined:
        season_num = int(combined.group(1))
        ep_num = int(combined.group(2))
    else:
        # Season X Episode Y
        se = re.search(r'(?i)Season[\s._-]*0*(\d{1,2}).{0,12}?Episode[\s._-]*0*(\d{1,3})', fn)
        if se:
            season_num = int(se.group(1))
            ep_num = int(se.group(2))
        else:
            # standalone Episode / Ep / E
            ep_m = re.search(r'(?i)\b(?:Ep|E|Episode)[\s._-]*0*(\d{1,3})\b', fn)
            sn_m = re.search(r'(?i)\b(?:S|Season)[\s._-]*0*(\d{1,2})\b', fn)
            if ep_m:
                ep_num = int(ep_m.group(1))
            if sn_m:
                season_num = int(sn_m.group(1))

    # final fallbacks
    if season_num is None:
        season_num = 1
    if ep_num is None:
        ep_num = 1

    sn = f"S{season_num:02d}"
    ep = f"{ep_num:02d}"

    # 3) Build cleaned title (remove leading bracket tags, quality tokens, S/E tokens, release tags)
    t = fn

    # remove leading bracket tags like [@CrunchyRollChannel]
    t = re.sub(r'^\[.*?\]\s*', '', t)

    # remove quality token we detected (safe removal)
    if quality:
        t = re.sub(re.escape(quality), ' ', t, flags=re.IGNORECASE)

    # remove combined SxxEyy and Season/Episode/Ep tokens
    t = re.sub(r'(?i)S0*\d{1,2}\s*[^A-Za-z0-9]{0,3}E0*\d{1,3}', ' ', t)
    t = re.sub(r'(?i)Season[\s._-]*\d{1,2}[\s,._-]*Episode[\s._-]*\d{1,3}', ' ', t)
    t = re.sub(r'(?i)\b(?:Ep|E|Episode)[\s._-]*0*\d{1,3}\b', ' ', t)
    t = re.sub(r'(?i)\b(?:S|Season)[\s._-]*0*\d{1,2}\b', ' ', t)

    # remove common release tags (HEVC, x265, BluRay, Dual Audio, ESub, 10bit etc.)
    tags_pattern = r'(?i)\b(720p|1080p|2160p|4k|HEVC|x265|x264|10bit|8bit|BluRay|BDRip|WEBRip|HDTV|HDRip|DVDRip|WEB[- ]?DL|WEBDL|Dual[\s-]*Audio|ESub|SUB|AAC|AC3|remux|rip|brrip|dub|dubbed)\b'
    t = re.sub(tags_pattern, ' ', t)

    # remove file extension remnants and separators
    t = re.sub(r'\.\w{2,5}$', '', t)
    t = re.sub(r'[_\.\-]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()

    if DEBUG:
        logger.debug("Parsed -> quality:%s season:%s episode:%s title_candidate:'%s'", quality, sn, ep, t)

    # 4) Match cleaned title against saved names or persist new name
    name = None
    if t and not re.fullmatch(r'\d+', t):
        best_ratio = 0.0
        best_name = None
        for n in anime_names:
            r = similar(t, n)
            if r > best_ratio:
                best_ratio = r
                best_name = n
        # if good match, reuse saved name; otherwise learn new
        if best_ratio >= 0.60:
            name = best_name
        else:
            name = t
            if name not in anime_names:
                anime_names.append(name)
                save_anime_names(anime_names)
    else:
        # fallback: try matching whole filename to saved names
        best_ratio = 0.0
        best_name = None
        for n in anime_names:
            r = similar(fn_raw, n)
            if r > best_ratio:
                best_ratio = r
                best_name = n
        if best_ratio >= 0.5 and best_name:
            name = best_name
        else:
            name = "Unknown Anime"

    return name, sn, ep, quality

# ---------------- Commands ----------------
@app.on_message(filters.command("start") & ~filters.me)
async def start(_, message: Message):
    await message.reply_text(
        "**👋 Auto Caption Bot**\nSend an anime file and I'll repost it with a generated caption (and remove the original if I can).\nCommands: /addanime, /delanime, /listanime\nSet DEBUG=1 to get parsing logs."
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

# ---------------- Main media handler ----------------
@app.on_message((filters.document | filters.video | filters.audio) & ~filters.me)
async def on_media(_, message: Message):
    # ignore bot-originated messages to prevent loops
    if message.from_user and message.from_user.is_bot:
        return

    media = message.document or message.video or message.audio
    if not media:
        return

    # prefer actual file_name, fallback to caption if missing
    raw_name = getattr(media, "file_name", None) or (message.caption or "")
    filename = raw_name.rsplit(".", 1)[0]

    # extract in requested order (quality, S/E, name)
    anime_name, sn, ep, quality = extract_info(filename)
    if DEBUG:
        logger.debug("on_media: raw_name='%s' -> name='%s' sn=%s ep=%s quality=%s", raw_name, anime_name, sn, ep, quality)

    anime_name_safe = escape(anime_name)
    caption = DEFAULT_CAPTION.format(AnimeName=anime_name_safe, Sn=sn, Ep=ep, Quality=quality)

    # copy message with caption (preserves file, no re-upload)
    try:
        new_msg = await message.copy(chat_id=message.chat.id, caption=caption, parse_mode=ParseMode.HTML)
        logger.info("Copied message id=%s", getattr(new_msg, "message_id", None))
    except Exception as e:
        logger.exception("Failed to copy message: %s", e)
        return await message.reply_text("❌ Failed to apply caption (copy/send error).")

    # delete original if possible (requires permission in groups)
    try:
        await message.delete()
        logger.info("Deleted original message id=%s", getattr(message, "message_id", None))
    except Exception as e:
        logger.warning("Could not delete original: %s", e)
        if message.chat.type in ("group", "supergroup", "channel"):
            await message.reply_text("⚠️ I couldn't delete the original. Make me an admin with 'Delete Messages' permission.")

if __name__ == "__main__":
    logger.info("Starting Auto Caption Bot...")
    app.run()
