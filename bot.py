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
BOT_TOKEN = ""  # <- put your token
DATA_FILE = "anime_names.json"

# Default Caption Template
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# In-Memory Storage
channel_captions = {}
anime_names = []

app = Client(
    "AutoCaptionBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ------------------ Regex helpers (precompiled) ------------------

# Remove trailing multi-extensions: .mkv.mp4 etc.
RE_MULTI_EXT = re.compile(
    r"\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg)"
    r"(?:\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg))*$",
    re.IGNORECASE
)

# Remove only leading bracketed groups like [@Channel] (repeatedly)
RE_LEADING_BRACKETS = re.compile(r"^\s*(?:\[[^\]]*\]|\([^\)]*\)|\{[^\}]*\})\s*")

# For title cleanup (remove whole bracketed chunks anywhere, only for final title polish)
RE_STRIP_BRACKETED_BLOCKS = re.compile(r"(\[.*?\]|\(.*?\)|\{.*?\})")

def _remove_leading_bracket_groups(s: str) -> str:
    # repeatedly remove bracketed groups only at the very start
    while True:
        m = RE_LEADING_BRACKETS.match(s)
        if not m:
            break
        s = s[m.end():]
    return s

def _strip_multi_extensions(name: str) -> str:
    return RE_MULTI_EXT.sub("", name)

def _strip_bracket_chars_keep_content(s: str) -> str:
    # turn "[480p]" -> " 480p ", "(Muse Dub)" -> " Muse Dub "
    return re.sub(r"[\[\]\(\)\{\}]", " ", s)

def _normalize_separators(s: str) -> str:
    # normalize separators -> spaces and collapse
    s = s.replace("_", " ").replace(".", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

# ---- Season/Episode patterns (searched on normalized + bracket-chars-stripped string) ----
RE_SxxEyy     = re.compile(r"\bS(\d{1,2})\s*[.\- ]?\s*E(\d{1,3})\b", re.IGNORECASE)
RE_SEASON_EP  = re.compile(r"\bSeason\s*(\d{1,2})\s*(?:Episode|Ep)?\s*(\d{1,3})\b", re.IGNORECASE)
RE_EPISODE    = re.compile(r"\bEpisode\s*[-_. ]*(\d{1,3})\b", re.IGNORECASE)
RE_EP         = re.compile(r"\bEp\s*[-_. ]*(\d{1,3})\b", re.IGNORECASE)
RE_E          = re.compile(r"\bE\s*[-_. ]*(\d{1,3})\b", re.IGNORECASE)

# (very cautious fallback; we only use it if SE not found, but we already require SE to exist)
RE_TRAIL_NUM  = re.compile(r"(?:^|[\s])(\d{1,3})(?:\s*(?:v\d+|final|end))?\s*$", re.IGNORECASE)

# ---- Quality patterns (searched on normalized + bracket-chars-stripped string) ----
RE_QUALITY_P    = re.compile(r"(?:^|[\s])(2160|1440|1080|720|540|480|360|240)\s*[pP](?:$|[\s])")
RE_QUALITY_BARE = re.compile(r"(?:^|[\s])(2160|1440|1080|720|540|480|360|240)(?:$|[\s])")

def _find_season_episode(work: str):
    # Highest confidence first
    for rx in (RE_SxxEyy, RE_SEASON_EP):
        m = rx.search(work)
        if m:
            s = f"S{int(m.group(1)):02d}"
            e = f"{int(m.group(2)):02d}"
            return s, e, m.start(), m.end()
    for rx in (RE_EPISODE, RE_EP, RE_E):
        m = rx.search(work)
        if m:
            s = "S01"
            e = f"{int(m.group(1)):02d}"
            return s, e, m.start(), m.end()
    # optional trailing-number fallback (not used unless absolutely needed)
    m = RE_TRAIL_NUM.search(work)
    if m:
        s = "S01"
        e = f"{int(m.group(1)):02d}"
        return s, e, m.start(1), m.end(1)
    return None

def _find_quality(work: str):
    m = RE_QUALITY_P.search(work)
    if m:
        q = int(m.group(1))
        return q, m.start(1), m.end(1)
    m2 = RE_QUALITY_BARE.search(work)
    if m2:
        q = int(m2.group(1))
        return q, m2.start(1), m2.end(1)
    return None

def parse_filename(filename: str):
    """
    Ultra-robust parser:
      1) Remove trailing multi-extensions.
      2) Remove leading bracketed groups (e.g., [@Group]).
      3) Strip ONLY bracket characters (keep inner content) and normalize separators to spaces.
      4) Extract Season/Episode, then Quality (accepts [480p], 360P SD, 1080p, etc.).
      5) Title is text BEFORE the earliest SE/Quality token in the 'work' string.
      6) Normalize quality: lowercase 'p'; 360p -> 480p.
    Returns (anime_name, season, episode, quality) or None if not confident.
    """
    if not filename:
        return None

    # base
    base = _strip_multi_extensions(filename)
    base = _remove_leading_bracket_groups(base)  # drop [@Channel] etc. ONLY at start

    # work string for detection: keep inner content of brackets, unify separators
    work = _normalize_separators(_strip_bracket_chars_keep_content(base))

    # Find Season/Episode
    se = _find_season_episode(work)
    if not se:
        return None
    season, episode, se_start, _ = se

    # Find Quality
    q = _find_quality(work)
    if not q:
        return None
    q_val, q_start, _ = q

    # Normalize quality string
    quality = "480p" if q_val == 360 else f"{q_val}p"

    # Choose earliest token index to cut title
    cut_idx = min(se_start if se_start >= 0 else len(work),
                  q_start if q_start >= 0 else len(work))

    raw_title = work[:cut_idx].strip()

    # Final title polish: remove any bracketed chunks that slipped, tidy separators
    # (work has no bracket chars, but we keep this for safety if upstream changes)
    title_clean = RE_STRIP_BRACKETED_BLOCKS.sub(" ", raw_title)
    title_clean = _normalize_separators(title_clean)

    # Drop stray leading handles like @Something (rare after step 2)
    title_clean = re.sub(r"^@\S+\s*", "", title_clean).strip()

    if not title_clean:
        return None

    anime_name_safe = escape(title_clean)
    return anime_name_safe, season, episode, quality

# ------------------ Commands ------------------

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

<b>Supported Filename Examples:</b>
- [@Group] Anime Title S01E12 [1080p] HEVC.mkv
- Anime Title Season 1 Episode 07 (720p).mp4
- Anime Title Ep 05 1080P x265.mkv
- Death Note S01E01 [@CrunchyRollChannel]_360P SD.mp4
- Fairy Tail S04E05 [@CrunchyRollChannel]_360P SD.mp4
- Dekin_no_Mogura_The_Earthbound_Mole_S01E07_[480p].mkv.mp4"""
    await message.reply_text(help_text, parse_mode=ParseMode.HTML)

# ------------------ Channel Handler ------------------

@app.on_message(filters.channel & (filters.video | filters.document))
async def handle_media(_, message: Message):
    try:
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

        # optional delete original
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

# ------------------ Startup ------------------

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

if __name__ == "__main__":
    load_anime_names()
    logger.info("Starting bot...")
    app.run()
