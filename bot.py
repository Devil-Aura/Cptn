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

# ---------- Regex helpers (precompiled) ----------

# Remove trailing multi-extensions: .mkv.mp4 etc.
RE_MULTI_EXT = re.compile(
    r"\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg)"
    r"(?:\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg))*$",
    re.IGNORECASE
)

# Bracketed tags to strip from the title
RE_BRACKETS = re.compile(r"(\[.*?\]|\(.*?\)|\{.*?\})")

# Normalization = turn separators into spaces and collapse
def _normalize(s: str) -> str:
    s = RE_MULTI_EXT.sub("", s)               # drop multi-extension
    s = s.replace("_", " ").replace(".", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

# Season/Episode patterns (searched on normalized string)
RE_SxxEyy     = re.compile(r"\bS(\d{1,2})\s*[.\- ]?\s*E(\d{1,3})\b", re.IGNORECASE)
RE_SEASON_EP  = re.compile(r"\bSeason\s*(\d{1,2})\s*(?:Episode|Ep)?\s*(\d{1,3})\b", re.IGNORECASE)
RE_EPISODE    = re.compile(r"\bEpisode\s*[-_. ]*(\d{1,3})\b", re.IGNORECASE)
RE_EP         = re.compile(r"\bEp\s*[-_. ]*(\d{1,3})\b", re.IGNORECASE)
RE_E          = re.compile(r"\bE\s*[-_. ]*(\d{1,3})\b", re.IGNORECASE)

# Very cautious trailing-number fallback (only if quality exists)
RE_TRAIL_NUM  = re.compile(r"(?:^|[\s])(\d{1,3})(?:\s*(?:v\d+|final|end))?\s*$", re.IGNORECASE)

# Quality patterns (searched on normalized string so `_360P` → ` 360P`)
RE_QUALITY_P  = re.compile(r"(?:^|[\s])(?:(2160|1440|1080|720|540|480|360|240))\s*[pP](?=$|[\s])")
RE_QUALITY_BARE = re.compile(r"(?:^|[\s])(?:(2160|1440|1080|720|540|480|360|240))(?:$|[\s])")

def _find_season_episode(norm: str):
    # Highest confidence first
    for rx in (RE_SxxEyy, RE_SEASON_EP):
        m = rx.search(norm)
        if m:
            s = f"S{int(m.group(1)):02d}"
            e = f"{int(m.group(2)):02d}"
            return s, e, m.start(), m.end()
    for rx in (RE_EPISODE, RE_EP, RE_E):
        m = rx.search(norm)
        if m:
            s = "S01"
            e = f"{int(m.group(1)):02d}"
            return s, e, m.start(), m.end()
    # If not found, try trailing number (we will only accept this later if quality exists too)
    m = RE_TRAIL_NUM.search(norm)
    if m:
        s = "S01"
        e = f"{int(m.group(1)):02d}"
        return s, e, m.start(1), m.end(1)
    return None

def _find_quality(norm: str):
    # Prefer explicit ####p
    m = RE_QUALITY_P.search(norm)
    if m:
        q = int(m.group(1))
        return q, m.start(1), m.end(1)  # return index of the number
    # Fallback: bare #### only (rare). Useful for patterns like "1080 x265" (discourage unless no p-form found).
    m2 = RE_QUALITY_BARE.search(norm)
    if m2:
        q = int(m2.group(1))
        return q, m2.start(1), m2.end(1)
    return None

def parse_filename(filename: str):
    """
    Robust parser:
      1) Normalize separators for reliable matching.
      2) Extract Season/Episode, then Quality.
      3) Build AnimeName as text before the earliest SE/Quality token,
         after removing bracketed tags, and cleanup.
      4) Convert 360p -> 480p, keep 'p' lowercase.
    Returns: (anime_name, season, episode, quality) or None.
    """
    if not filename:
        return None

    # Keep an original normalized view for pattern search
    norm = _normalize(filename)

    # Find SE & quality
    se = _find_season_episode(norm)           # (season, episode, start, end) or None
    q  = _find_quality(norm)                  # (q_int, start, end) or None

    if not q:
        # No quality → fail safely (don't guess)
        return None

    # If SE came only from trailing number, ensure we also have quality (we do) and that SE starts after any title text.
    if not se:
        return None

    season, episode, se_start, se_end = se
    q_val, q_start, q_end = q

    # Normalize quality string
    if q_val == 360:
        quality = "480p"
    else:
        quality = f"{q_val}p"

    # Where to cut the title: the earliest token among SE and quality
    cut_idx = min(se_start if se_start >= 0 else len(norm),
                  q_start if q_start >= 0 else len(norm))

    # Title slice (pre-tags removal)
    raw_title = norm[:cut_idx].strip()

    # Remove bracketed tags from that slice, then re-normalize
    title_no_tags = _normalize(RE_BRACKETS.sub(" ", raw_title))

    # Final cleanup: remove trailing separators
    anime_name = re.sub(r"[~|:/\\,.+–—\-]*$", "", title_no_tags).strip()

    if not anime_name:
        return None

    # Escape for HTML caption
    anime_name_safe = escape(anime_name)

    return anime_name_safe, season, episode, quality

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

<b>Supported Filename Examples:</b>
- [@Group] Anime Title S01E12 1080p HEVC.mkv
- Anime Title Season 1 Episode 07 [720p].mp4
- Anime Title Ep 05 (1080p) x265.mkv
- Death Note S01E01 [@CrunchyRollChannel]_360P SD.mp4
- Fairy Tail S04E05 [@CrunchyRollChannel]_360P SD.mp4"""
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)

# ----- Channel Handlers -----
@app.on_message(filters.channel & (filters.video | filters.document))
async def handle_media(_, message: Message):
    try:
        # Get filename
        filename = ""
        if message.video:
            filename = message.video.file_name or ""
        elif message.document:
            filename = message.document.file_name or ""
        if not filename:
            return

        logger.info(f"Processing file: {filename}")

        parsed = parse_filename(filename)
        if not parsed:
            logger.warning(f"Failed to parse filename: {filename}")
            try:
                await message.reply_text(
                    "❌ Caption parse failed.\n"
                    "Make sure filename includes: Season/Episode (e.g. S01E07 or Ep 07) and Quality (e.g. 480p/720p/1080p)."
                )
            except:
                pass
            return

        anime_name, season, episode, quality = parsed

        caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
        formatted_caption = caption.format(
            AnimeName=anime_name,
            Sn=season,
            Ep=episode,
            Quality=quality
        )

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

        # Try to delete original (optional)
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Couldn't delete original: {e}")

        logger.info(f"Processed {filename} successfully")

    except Exception as e:
        logger.exception("Error processing media")
        try:
            await message.reply_text(f"❌ Error processing file: {str(e)[:200]}")
        except:
            pass

# ----- Startup -----
if __name__ == "__main__":
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                anime_names = json.load(f)
    except Exception as e:
        logger.error(f"Error loading anime names: {e}")
        anime_names = []
    logger.info("Starting bot...")
    app.run()
