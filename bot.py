#!/usr/bin/env python3
import os
import re
import json
import logging
from html import escape
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AutoCaptionBot")

# -----------------------
# Bot config (set env or replace)
# -----------------------
API_ID = int(os.environ.get("API_ID", "22768311"))
API_HASH = os.environ.get("API_HASH", "702d8884f48b42e865425391432b3794")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

DATA_FILE = "anime_names.json"   # optional DB file if you want to expand later

DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# in-memory storage for per-channel caption templates (optional)
channel_captions = {}

app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# -----------------------
# Parsing helpers / regex
# -----------------------
# common video extensions (multi ext at end)
RE_MULTI_EXT = re.compile(
    r"(?:\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg|m2ts|3gp|rmvb))(?:\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg))*$",
    re.IGNORECASE
)

# remove repeated leading bracketed groups like [@CrunchyRoll] (multiple)
RE_LEADING_BRACKETS = re.compile(r"^\s*(?:\[[^\]]*\]|\([^\)]*\)|\{[^\}]*\})\s*")

# bracketed-blocks (to remove entirely from title)
RE_BRACKETED_BLOCK = re.compile(r"(\[[^\]]*\]|\([^\)]*\)|\{[^\}]*\})")

# patterns to normalize separators
RE_MULTI_SEP = re.compile(r"[_\.\-]+")
RE_MULTI_SPACE = re.compile(r"\s+")

# Season / Episode patterns (searched on a normalized detection string)
RE_SXXEYY = re.compile(r"\bS(\d{1,2})\s*[._\-\s]*E(\d{1,3})\b", re.IGNORECASE)
RE_SEASON_EP = re.compile(r"\bSeason\s*(\d{1,2})\s*(?:Episode|Ep)?\s*(\d{1,3})\b", re.IGNORECASE)
RE_EPISODE = re.compile(r"\bEpisode\s*[:\.\-\s_]*?(\d{1,3})\b", re.IGNORECASE)
RE_EP = re.compile(r"\bEp\s*[:\.\-\s_]*?(\d{1,3})\b", re.IGNORECASE)
RE_E = re.compile(r"\bE\s*[:\.\-\s_]*?(\d{1,3})\b", re.IGNORECASE)
# parenthetical number like (227) — fallback ONLY when no SxxEyy or Ep found
RE_PARENS_NUM = re.compile(r"\(\s*(\d{1,4})\s*\)")

# Quality detection (detects after separators too)
RE_QUALITY = re.compile(r"\b(2160|1440|1080|720|540|480|360|240)\s*[pP]?\b")

# trailing junk words to remove from final title (common tags)
TRAILING_JUNK = re.compile(
    r"(?:\b(?:dub|dubbed|hindi|eng(?:lish)?|dual(?:[\s\-_]audio)?|multi(?:[\s\-_]audio)?|fhd|sd|bluray|blu[-\s]?ray|bdrip|brrip|webrip|hevc|x265|x264|10bit|8bit|esub|e-sub|sub|subtitle|raw|cd1|cd2|part|sample|mp4|mkv|v2)\b[\s\-\:_]*)+$",
    re.IGNORECASE
)


def _remove_trailing_extensions(s: str) -> str:
    return RE_MULTI_EXT.sub("", s).strip()


def _remove_leading_bracket_groups(s: str) -> str:
    # repeatedly remove leading bracketed chunks: [..] (..) {..}
    while True:
        m = RE_LEADING_BRACKETS.match(s)
        if not m:
            break
        s = s[m.end():]
    return s.strip()


def _normalize_for_detection(s: str) -> str:
    """
    Replace bracket characters with spaces (keep inner content),
    unify separators to single spaces.
    This string is used to search for token patterns (SxxEyy, quality, etc.).
    """
    s2 = re.sub(r"[\[\]\(\)\{\}]", " ", s)     # remove bracket characters but keep their contents
    s2 = RE_MULTI_SEP.sub(" ", s2)
    s2 = RE_MULTI_SPACE.sub(" ", s2)
    return s2.strip()


def _normalize_for_title(s: str) -> str:
    """
    Remove whole bracketed blocks (and their contents) for final title extraction.
    Also unify separators.
    """
    s2 = RE_BRACKETED_BLOCK.sub(" ", s)
    s2 = RE_MULTI_SEP.sub(" ", s2)
    s2 = RE_MULTI_SPACE.sub(" ", s2)
    return s2.strip()


def _strip_trailing_junk(title: str) -> str:
    # remove trailing junk tokens like "in Hindi", "BluRay" etc.
    prev = None
    t = title.strip()
    while prev != t:
        prev = t
        t = TRAILING_JUNK.sub("", t).strip()
    return t


def parse_filename(filename: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Best-effort parser.
    Returns (anime_name_html_escaped, season_str 'Sxx', episode_str 'yy', quality like '480p')
    or None if parser cannot reliably find both episode and quality.
    """
    if not filename or not filename.strip():
        return None

    original = filename.strip()

    # 1) remove trailing multi extensions (.mkv.mp4 etc)
    base = _remove_trailing_extensions(original)

    # 2) remove repeated leading bracketed groups like [@CrunchyRollChannel]
    base = _remove_leading_bracket_groups(base)

    # 3) Detection string (keeps bracket contents) and Title string (removes bracketed blocks)
    work = _normalize_for_detection(base)    # used for searching tokens
    title_pool = _normalize_for_title(base)  # used for final anime title extraction

    # Defensive lower for searches
    work_l = work.lower()
    title_pool_l = title_pool.lower()

    # -------------------------
    # Extract Season / Episode
    # -------------------------
    season = None
    episode = None
    se_pos = None

    m = RE_SXXEYY.search(work)
    if m:
        season = f"S{int(m.group(1)):02d}"
        episode = f"{int(m.group(2)):02d}"
        se_pos = m.start()
    else:
        m = RE_SEASON_EP.search(work)
        if m:
            season = f"S{int(m.group(1)):02d}"
            episode = f"{int(m.group(2)):02d}"
            se_pos = m.start()
        else:
            # Ep/Episode/E patterns (no season explicit)
            for rx in (RE_EPISODE, RE_EP, RE_E):
                m = rx.search(work)
                if m:
                    season = "S01"
                    episode = f"{int(m.group(1)):02d}"
                    se_pos = m.start()
                    break
            else:
                # last-resort: parenthetical number like (227) — use only as fallback
                m = RE_PARENS_NUM.search(work)
                if m:
                    season = "S01"
                    episode = f"{int(m.group(1)):02d}"
                    se_pos = m.start()

    # If we couldn't find episode, bail (we require episode + quality for safe captioning)
    if not episode:
        logger.debug(f"parse_filename: no episode found in '{original}' (work='{work}')")
        return None

    # -------------------------
    # Extract Quality
    # -------------------------
    qm = RE_QUALITY.search(work)
    if not qm:
        logger.debug(f"parse_filename: no quality found in '{original}' (work='{work}')")
        return None
    q_val = int(qm.group(1))
    q_pos = qm.start()

    # normalize quality string
    quality = "480p" if q_val == 360 else f"{q_val}p"

    # -------------------------
    # Determine cut index for anime title
    # -------------------------
    # Prefer to cut using a match in the cleaned title (title_pool). Try to find SE token on title_pool first,
    # otherwise quality token. If none found, try to find the matched substring from work in title_pool.
    cut_idx = None

    # helper: search regex on a given string and return start if found
    def _first_match_start(rx, s):
        mm = rx.search(s)
        return mm.start() if mm else None

    # Try to find SxxEyy / season-episode on title_pool
    for rx in (RE_SXXEYY, RE_SEASON_EP, RE_EPISODE, RE_EP, RE_E):
        idx = _first_match_start(rx, title_pool)
        if idx is not None:
            cut_idx = idx
            break

    # If not found, try to find quality on title_pool
    if cut_idx is None:
        qm_clean = RE_QUALITY.search(title_pool)
        if qm_clean:
            cut_idx = qm_clean.start()

    # If still none, attempt substring mapping: take the token text from work and find in title_pool
    if cut_idx is None:
        # text of the token (prefer SE token from work, otherwise quality)
        token_text = None
        se_token = None
        if se_pos is not None:
            # attempt to get the matched substring from work for se
            se_m_work = RE_SXXEYY.search(work) or RE_SEASON_EP.search(work) or RE_EPISODE.search(work) or RE_EP.search(work) or RE_E.search(work) or RE_PARENS_NUM.search(work)
            if se_m_work:
                se_token = se_m_work.group(0)
        if se_token:
            token_text = re.sub(r"[\[\]\(\)\{\}]", " ", se_token).strip()
            try_pos = title_pool_l.find(token_text.lower())
            if try_pos != -1:
                cut_idx = try_pos
        if cut_idx is None:
            # try quality token text
            q_token = qm.group(0)
            q_text = re.sub(r"[\[\]\(\)\{\}]", " ", q_token).strip()
            try_pos = title_pool_l.find(q_text.lower())
            if try_pos != -1:
                cut_idx = try_pos

    # Final fallback: if nothing to cut on, take the entire title_pool as title (but we'll strip trailing junk later)
    if cut_idx is None:
        cut_idx = len(title_pool)

    # slice title_pool up to cut_idx
    anime_title_raw = title_pool[:cut_idx].strip()

    # If empty (rare), as last-ditch attempt try using the portion of 'work' before quality or se (whichever earlier)
    if not anime_title_raw:
        # choose earliest of se_pos and q_pos
        earliest = None
        for p in (se_pos, q_pos):
            if p is None:
                continue
            if earliest is None or p < earliest:
                earliest = p
        if earliest is None:
            anime_title_raw = title_pool
        else:
            # map earliest char index in work to a rough split in title_pool by finding the token there
            # fallback to entire title_pool if mapping isn't possible
            anime_title_raw = title_pool

    # Clean up title: remove bracketed blocks that may remain, strip trailing junk tokens
    anime_title_raw = RE_BRACKETED_BLOCK.sub(" ", anime_title_raw)
    anime_title_raw = RE_MULTI_SPACE.sub(" ", anime_title_raw).strip()
    anime_title_raw = _strip_trailing_junk(anime_title_raw)

    # remove stray leading handles like "@CrunchyRoll" that slipped (rare)
    anime_title_raw = re.sub(r"^@[\w\-\_]+\s*", "", anime_title_raw).strip()

    if not anime_title_raw:
        # if title becomes empty after cleaning, abort to avoid producing a wrong caption
        logger.debug("parse_filename: cleaned anime title empty; aborting parse.")
        return None

    # final normalization: collapse repeated spaces, strip punctuation at ends
    anime_title_raw = anime_title_raw.strip(" -_:.|,")
    anime_title_raw = RE_MULTI_SPACE.sub(" ", anime_title_raw).strip()

    # escape for HTML caption
    anime_title_safe = escape(anime_title_raw)

    return anime_title_safe, season, episode, quality


# -----------------------
# Bot Handlers
# -----------------------
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text(
        "🤖 <b>Auto Caption Bot</b>\n\n"
        "I automatically add captions (anime name, season/episode & quality) to posted videos/documents.\n\n"
        "Add me to a channel as admin with Post Messages permission.\n\n"
        "This bot auto-detects many messy filename formats (S01E02, Ep 03, (226), [480p], 1080p HEVC, etc.).",
        parse_mode=ParseMode.HTML
    )


@app.on_message(filters.command("help") & filters.private)
async def help_cmd(_, message: Message):
    await message.reply_text(
        "<b>How it works</b>\n"
        "- When a channel posts a video/document, the bot reads its filename and tries to extract:\n"
        "  • Anime name\n"
        "  • Season (Sxx)\n"
        "  • Episode (yy)\n"
        "  • Quality (480p/720p/1080p — 360p → 480p)\n\n"
        "The parser is very flexible and handles many messy formats. If the file truly cannot be parsed, the bot will skip it silently (no spam).",
        parse_mode=ParseMode.HTML
    )


@app.on_message(filters.channel & (filters.video | filters.document))
async def channel_media_handler(_, message: Message):
    # Extract filename (video or document)
    filename = ""
    if message.video:
        filename = message.video.file_name or ""
    elif message.document:
        filename = message.document.file_name or ""
    if not filename:
        logger.info("No filename available; skipping.")
        return

    logger.info(f"Received file: {filename}")

    parsed = parse_filename(filename)
    if not parsed:
        # Fail silently in-channel to avoid spam; just log for debugging
        logger.warning(f"Failed to parse filename: {filename}")
        return

    anime_name, season, episode, quality = parsed

    # build caption (can be customized per channel in channel_captions)
    caption_template = channel_captions.get(message.chat.id, DEFAULT_CAPTION)
    try:
        caption_text = caption_template.format(
            AnimeName=anime_name,
            Sn=season,
            Ep=episode,
            Quality=quality
        )
    except Exception as e:
        # fallback simple caption in case template is corrupted
        logger.exception("Caption template formatting failed; using fallback caption.")
        caption_text = f"<b>{anime_name} [{season}]\nEpisode - {episode}\nQuality - {quality}</b>"

    # re-post the same media with caption
    try:
        if message.video:
            await message.reply_video(
                message.video.file_id,
                caption=caption_text,
                parse_mode=ParseMode.HTML
            )
        else:
            await message.reply_document(
                message.document.file_id,
                caption=caption_text,
                parse_mode=ParseMode.HTML
            )
    except Exception:
        logger.exception("Failed to repost media with caption.")
        return

    # optional: try to delete original message to avoid duplicates (will silently fail if bot lacks perms)
    try:
        await message.delete()
    except Exception:
        logger.debug("Couldn't delete the original message (missing permission or other error).")


# -----------------------
# Optional simple CLI helpers to load/save anime_names for future use
# -----------------------
def load_anime_names():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Loaded anime names DB with {len(data)} entries")
                return data
    except Exception:
        logger.exception("Failed to load anime names DB")
    return []


if __name__ == "__main__":
    # load any optional DB (not required)
    _ = load_anime_names()

    logger.info("Starting AutoCaptionBot...")
    app.run()
