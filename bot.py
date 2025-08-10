import os
import re
import json
import logging
from html import escape
from difflib import SequenceMatcher

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# ---------- CONFIG ----------
API_ID = int(os.environ.get("API_ID", "22768311"))      # <-- replace or use env
API_HASH = os.environ.get("API_HASH", "702d8884f48b42e865425391432b3794")  # <-- replace or use env
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # <-- replace or use env

DATA_FILE = "anime_names.json"
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel</b>"""
# ----------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def clean_title(filename: str) -> str:
    s = filename
    # drop leading bracket tags
    s = re.sub(r'^\[.*?\]\s*', '', s)
    s = re.sub(r'\.\w{2,4}$', '', s)  # drop ext if present
    # remove combined SxxExx like S01E07
    s = re.sub(r'[Ss](?:eason)?\s*0*\d{1,2}[Ee](?:p|pisode)?\s*0*\d{1,3}', ' ', s)
    # remove standalone season/episode tokens
    s = re.sub(r'[Ss](?:eason)?\s*0*\d{1,2}', ' ', s)
    s = re.sub(r'[Ee](?:p|pisode)?\s*0*\d{1,3}', ' ', s)
    # remove common release tags
    tags_pattern = r'\b(720p|1080p|2160p|480p|240p|144p|4k|HEVC|x265|x264|10bit|8bit|BluRay|BDRip|WEBRip|HDTV|HDRip|DVDRip|WEB-DL|Dual[\s-]*Audio|ESub|SUB|AAC|AC3|remux|rip|brrip|dub|dubbed)\b'
    s = re.sub(tags_pattern, ' ', s, flags=re.IGNORECASE)
    s = re.sub(r'\b\d{3,4}p\b', ' ', s, flags=re.IGNORECASE)
    s = re.sub(r'\b\d{1,4}bit\b', ' ', s, flags=re.IGNORECASE)
    s = re.sub(r'[_\.\-]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def extract_info(filename: str):
    # filename: without extension
    fn = filename
    season = re.search(r'[Ss](?:eason)?\s*0*(\d{1,2})(?=\D|$)', fn)
    sn = f"S{season.group(1).zfill(2)}" if season else "S01"
    episode = re.search(r'[Ee](?:p|pisode)?\s*0*(\d{1,3})(?=\D|$)', fn)
    ep = episode.group(1).zfill(2) if episode else "01"
    quality = re.search(r'(\d{3,4}p)\b', fn, re.IGNORECASE)
    quality_final = quality.group(1).lower() if quality else "480p"

    cleaned = clean_title(fn)
    name = None
    if cleaned and len(cleaned) > 1 and not re.fullmatch(r'\d+', cleaned):
        # check for similar existing name
        for n in anime_names:
            if similar(cleaned, n) >= 0.6:
                name = n
                break
        if not name:
            name = cleaned
            # persist learned name
            if name not in anime_names:
                anime_names.append(name)
                save_anime_names(anime_names)
    else:
        # fallback similarity match
        for n in anime_names:
            if similar(fn, n) >= 0.5:
                name = n
                break
    if not name:
        name = "Unknown Anime"
    return name, sn, ep, quality_final

# ---------------- Commands ----------------
@app.on_message(filters.command("start") & ~filters.me)
async def start(_, message: Message):
    await message.reply_text(
        "**👋 Welcome to the Auto Caption Bot!**\n\n"
        "Send an anime file and I'll repost it with a generated caption and remove the original (if permitted).\n\n"
        "Commands:\n"
        "/addanime <name>\n/delanime <name>\n/listanime\n/help"
    )

@app.on_message(filters.command("help") & ~filters.me)
async def help_cmd(_, message: Message):
    await message.reply_text("Commands: /addanime <name>, /delanime <name>, /listanime\nNote: In groups the bot needs admin 'Delete Messages' permission to remove originals.")

@app.on_message(filters.command("addanime") & ~filters.me)
async def add_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("❌ Usage: /addanime Anime Name")
    if name in anime_names:
        return await message.reply_text("⚠️ That name is already saved.")
    anime_names.append(name)
    save_anime_names(anime_names)
    await message.reply_text(f"✅ Added anime name: **{name}**")

@app.on_message(filters.command("delanime") & ~filters.me)
async def del_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("❌ Usage: /delanime Anime Name")
    try:
        anime_names.remove(name)
        save_anime_names(anime_names)
        await message.reply_text(f"🗑 Deleted anime: **{name}**")
    except ValueError:
        await message.reply_text("❌ Not found in saved names.")

@app.on_message(filters.command("listanime") & ~filters.me)
async def list_anime(_, message: Message):
    if not anime_names:
        return await message.reply_text("📭 No anime names saved yet.")
    txt = "📚 **Saved Anime Names:**\n" + "\n".join(f"• {escape(n)}" for n in anime_names)
    await message.reply_text(txt)

# ------- Main media handler -------
@app.on_message((filters.document | filters.video | filters.audio) & ~filters.me)
async def on_media(_, message: Message):
    # ignore messages from bots (copy will arrive from bot account)
    if message.from_user and message.from_user.is_bot:
        return

    media = message.document or message.video or message.audio
    if not media:
        return

    raw_name = getattr(media, "file_name", None) or (message.caption or "") or getattr(media, "file_unique_id", "file")
    filename = raw_name.rsplit(".", 1)[0]  # remove extension if present

    anime_name, sn, ep, quality = extract_info(filename)
    anime_name_safe = escape(anime_name)
    caption = DEFAULT_CAPTION.format(AnimeName=anime_name_safe, Sn=sn, Ep=ep, Quality=quality)

    try:
        new_msg = await message.copy(chat_id=message.chat.id, caption=caption, parse_mode=ParseMode.HTML)
        logger.info("Copied message with caption (id=%s)", getattr(new_msg, "message_id", None))
    except Exception as e:
        logger.exception("Failed to copy message: %s", e)
        return await message.reply_text("❌ Failed to apply caption (copy/send error).")

    # try to delete original (may fail if bot lacks permission; that's normal)
    try:
        await message.delete()
        logger.info("Deleted original message (id=%s)", getattr(message, "message_id", None))
    except Exception as e:
        logger.warning("Could not delete original message: %s", e)
        # notify only in groups/supergroups
        if message.chat.type in ("group", "supergroup", "channel"):
            await message.reply_text("⚠️ I couldn't delete the original message. Make me an admin with 'Delete Messages' permission if you want originals removed.")

if __name__ == "__main__":
    logger.info("Starting Auto Caption Bot...")
    app.run()
