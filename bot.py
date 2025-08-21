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

# ------------------ Robust filename parsing ------------------

# Precompile regexes
RE_MULTI_EXT = re.compile(r"\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg)(?:\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg))*$", re.IGNORECASE)

# Quality tokens like 2160p, 1080p, 720p, 480p, 360p (p can be missing or upper)
RE_QUALITY = re.compile(r"\b(2160|1440|1080|720|540|480|360|240)\s*[pP]\b")
RE_QUALITY_BARE = re.compile(r"\b(2160|1440|1080|720|540|480|360|240)\b")

# Season/Episode patterns
RE_SxxEyy = re.compile(r"\bS(\d{1,2})[ ._-]*E(\d{1,3})\b", re.IGNORECASE)
RE_SEASON_EPISODE = re.compile(r"\bSeason\s*(\d{1,2})\s*(?:Episode|Ep)?\s*(\d{1,3})\b", re.IGNORECASE)
RE_EP_LONG = re.compile(r"\bEpisode\s*[-_ ]*(\d{1,3})\b", re.IGNORECASE)
RE_EP_SHORT = re.compile(r"\bEp\s*[-_ ]*(\d{1,3})\b", re.IGNORECASE)
RE_E_ONLY  = re.compile(r"\bE\s*[-_ ]*(\d{1,3})\b", re.IGNORECASE)

# Strict fallback for plain trailing number as episode (to avoid titles like "86" being mistaken)
RE_TRAILING_EP = re.compile(r"(?:^|[\s\-_\.])(\d{1,3})(?:\s*(?:v\d+|final|end))?\s*$", re.IGNORECASE)

# Bracket pairs to strip as tags when building the display name
RE_BRACKETS = re.compile(r"(\[.*?\]|\(.*?\)|\{.*?\})")

def _strip_multi_extensions(name: str) -> str:
    return RE_MULTI_EXT.sub("", name)

def _normalize_separators(s: str) -> str:
    s = s.replace("_", " ").replace(".", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def _find_quality(original: str) -> tuple | None:
    # First try classic ####p
    m = RE_QUALITY.search(original)
    if m:
        q = int(m.group(1))
        return (q, m.start(), m.end())
    # Then a bare number token that is followed by " SD/HD/…"? We avoid false positives;
    # only use bare number if there is no ####p anywhere.
    m2 = RE_QUALITY_BARE.search(original)
    if m2:
        q = int(m2.group(1))
        # Require that around it there are hints like p-less with tags (e.g., "360P SD" becomes 360 found by RE_QUALITY above).
        # Since this is a fallback, we still accept it because user examples include "360P SD" which RE_QUALITY would catch.
        return (q, m2.start(), m2.end())
    return None

def _find_season_episode(original: str):
    # Ordered by confidence
    for rx in (RE_SxxEyy, RE_SEASON_EPISODE):
        m = rx.search(original)
        if m:
            season = f"S{int(m.group(1)):02d}"
            episode = f"{int(m.group(2)):02d}"
            return season, episode, m.start(), m.end()
    for rx in (RE_EP_LONG, RE_EP_SHORT, RE_E_ONLY):
        m = rx.search(original)
        if m:
            season = "S01"
            episode = f"{int(m.group(1)):02d}"
            return season, episode, m.start(), m.end()
    # Very strict fallback: last short number token near the end
    m = RE_TRAILING_EP.search(_normalize_separators(_strip_multi_extensions(original)))
    if m:
        season = "S01"
        episode = f"{int(m.group(1)):02d}"
        # We don't have precise positions on original here; return -1 markers
        return season, episode, -1, -1
    return None

def parse_filename(filename: str):
    """
    Flexible parser for messy anime filenames.
    Returns: (anime_name, season, episode, quality) or None if not confident.
    """
    if not filename:
        return None

    # Work on a copy without multi-extensions
    base = _strip_multi_extensions(filename)

    # Detect quality (from original text, including brackets)
    qinfo = _find_quality(base)
    quality_val = None
    if qinfo:
        quality_val = qinfo[0]  # integer like 1080

    # Detect season/episode (from original text, including brackets)
    seinfo = _find_season_episode(base)
    if not seinfo:
        # Can't confidently find episode → don't guess
        return None
    season, episode, se_start, se_end = seinfo

    # Normalize quality string
    if quality_val is not None:
        if quality_val == 360:
            quality_str = "480p"   # convert 360p → 480p
        else:
            quality_str = f"{quality_val}p"
    else:
        # If quality is missing, we *could* default or fail. Safer: fail to avoid wrong captions.
        return None

    # Build clean string to extract the title
    cleaned = RE_BRACKETS.sub(" ", base)              # drop [group] (tags) {extra}
    cleaned = _normalize_separators(cleaned)

    # Try to locate the same SE pattern on cleaned to cut the title precisely
    cut_idx = None
    for rx in (RE_SxxEyy, RE_SEASON_EPISODE, RE_EP_LONG, RE_EP_SHORT, RE_E_ONLY):
        m = rx.search(cleaned)
        if m:
            cut_idx = m.start()
            break

    if cut_idx is None and qinfo:
        # If SE token vanished due to cleanup, cut by quality position in cleaned
        # Re-find quality on cleaned text
        m_q = RE_QUALITY.search(cleaned) or RE_QUALITY_BARE.search(cleaned)
        if m_q:
            cut_idx = m_q.start()

    # Fallback: if still None, cut by where the trailing number begins (rare)
    if cut_idx is None:
        m_tr = RE_TRAILING_EP.search(cleaned)
        if m_tr:
            cut_idx = m_tr.start(1)

    # If still None (very rare), give up to avoid mixing fields
    if cut_idx is None:
        return None

    title = cleaned[:cut_idx].strip()
    # Remove common trailing separators
    title = re.sub(r"[~|:/\\,.+–—\-]*$", "", title).strip()

    # Extra safety: if title got empty due to aggressive tags, try to recover from original
    if not title:
        # Take everything before the first SE match in the original, then clean it
        if se_start not in (-1, None):
            rough = _normalize_separators(RE_BRACKETS.sub(" ", base[:se_start]))
            title = re.sub(r"[~|:/\\,.+–—\-]*$", "", rough).strip()

    if not title:
        # Still empty → fail safely
        return None

    # Escape for HTML caption
    title_safe = escape(title)

    return title_safe, season, episode, quality_str

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
- AnimeName S01E01 1080p.mkv
- [Group] Anime Name - 01 (720p).mp4
- Anime.Name.Episode.01.480p.mkv
- Anime Name Ep 07 [1080p] x265.mkv
- Welcome to the Outcast's Restaurant! S01E08 [@CrunchyRollChannel]_360P SD"""
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)

# ----- Channel Handlers -----
@app.on_message(filters.channel & (filters.video | filters.document))
async def handle_media(_, message: Message):
    try:
        # Get filename
        if message.video:
            filename = message.video.file_name or ""
        elif message.document:
            filename = message.document.file_name or ""
        else:
            return

        logger.info(f"Processing file: {filename}")

        # Parse filename
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

        # Get caption template
        caption = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
        formatted_caption = caption.format(
            AnimeName=anime_name,
            Sn=season,
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
        logger.exception("Error processing media")
        try:
            await message.reply_text(f"❌ Error processing file: {str(e)[:200]}")
        except:
            pass

# ----- Startup -----
if __name__ == "__main__":
    load_anime_names()
    logger.info("Starting bot...")
    app.run()
