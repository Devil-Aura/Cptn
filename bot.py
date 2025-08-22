#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import random
import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from html import escape
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

# ================================
# CONFIG — fill these or use env
# ================================
API_ID = int(os.environ.get("API_ID", "22768311"))
API_HASH = os.environ.get("API_HASH", "702d8884f48b42e865425391432b3794")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Secret login code (case-insensitive, extra spaces ignored)
SECRET_CODE_CANONICAL = "mai kaam chor hu"

# Persist access here
ACCESS_DB_FILE = "access_db.json"

# Caption template (HTML)
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# Funny lines
OVERWORK_LINES = [
    "Mai aur nahi kar sakta, thak gya hu 😭",
    "Aur nahi hoga mujhse 😩",
    "Ab meri jaan loge kya? 💀",
    "Bas ho gaya, mujhe chain do 😴"
]
IDLE_LINES = [
    "Oye kaha gaye ho? Kaam nahi karna kya? 😒",
    "Yaar bore ho raha hu, kuch kaam do 💼",
    "Kaam choro kaam karo 😡",
    "Hello hello, mujhe bhool gaye kya? 🤔"
]

# Overwork thresholds
OVERWORK_WINDOW = 60           # seconds
OVERWORK_THRESHOLD = 8         # messages per chat per window to trigger a quip
OVERWORK_COOLDOWN = 120        # seconds between quips per chat

# Idle nudges
IDLE_CHECK_EVERY = 300         # seconds
IDLE_THRESHOLD = 900           # if no activity for this long, may nudge
IDLE_CHANCE = 0.35             # 35% chance to send when threshold met

# ================================
# Logging
# ================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("PrivateFunnyCaptionBot")

# ================================
# Storage (access + activity)
# ================================
access_db = {
    "users": [],   # user_ids that logged in via PM
    "chats": []    # chat_ids (groups/channels) logged in via /login inside them
}
users_logged: set[int] = set()
chats_logged: set[int] = set()

# recent activity tracking per chat for overwork & idle
recent_msgs: dict[int, deque] = defaultdict(lambda: deque(maxlen=500))  # timestamps
last_quip_at: dict[int, datetime] = {}       # last time we sent an overwork quip
last_activity: dict[int, datetime] = {}      # last activity in a chat

# ================================
# App
# ================================
app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================================
# Helpers: Access DB
# ================================
def load_access_db() -> None:
    global access_db, users_logged, chats_logged
    if os.path.exists(ACCESS_DB_FILE):
        try:
            with open(ACCESS_DB_FILE, "r", encoding="utf-8") as f:
                access_db = json.load(f)
            users_logged = set(access_db.get("users", []))
            chats_logged = set(access_db.get("chats", []))
            log.info(f"Access DB loaded: {len(users_logged)} users, {len(chats_logged)} chats.")
        except Exception:
            log.exception("Failed to load access DB; starting fresh.")
            access_db = {"users": [], "chats": []}
            users_logged, chats_logged = set(), set()
    else:
        access_db = {"users": [], "chats": []}
        users_logged, chats_logged = set(), set()

def save_access_db() -> None:
    try:
        access_db["users"] = sorted(users_logged)
        access_db["chats"] = sorted(chats_logged)
        with open(ACCESS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(access_db, f, ensure_ascii=False, indent=2)
    except Exception:
        log.exception("Failed to save access DB.")

def normalize_code(text: str) -> str:
    # Lowercase, collapse multiple spaces
    return re.sub(r"\s+", " ", text.strip().lower())

def has_access(message: Message) -> bool:
    if message.chat.type in ("group", "supergroup", "channel"):
        return message.chat.id in chats_logged
    # private
    uid = message.from_user.id if message.from_user else None
    return bool(uid) and uid in users_logged

def mark_activity(chat_id: int) -> None:
    now = datetime.utcnow()
    last_activity[chat_id] = now
    dq = recent_msgs[chat_id]
    dq.append(now.timestamp())

def maybe_send_overwork_quip(chat_id: int) -> Optional[str]:
    # Count messages in window
    now_ts = datetime.utcnow().timestamp()
    dq = recent_msgs[chat_id]
    # Drop old timestamps
    while dq and now_ts - dq[0] > OVERWORK_WINDOW:
        dq.popleft()
    if len(dq) >= OVERWORK_THRESHOLD:
        last = last_quip_at.get(chat_id)
        if not last or (datetime.utcnow() - last).total_seconds() >= OVERWORK_COOLDOWN:
            last_quip_at[chat_id] = datetime.utcnow()
            return random.choice(OVERWORK_LINES)
    return None

async def idle_nudger():
    await app.wait_until_ready()
    while True:
        await asyncio.sleep(IDLE_CHECK_EVERY)
        now = datetime.utcnow()
        for chat_id in list(chats_logged):
            last = last_activity.get(chat_id)
            if not last:
                continue
            if (now - last).total_seconds() >= IDLE_THRESHOLD:
                if random.random() < IDLE_CHANCE:
                    try:
                        await app.send_message(chat_id, random.choice(IDLE_LINES))
                        # avoid spamming: move activity forward a bit
                        last_activity[chat_id] = now - timedelta(seconds=IDLE_THRESHOLD // 2)
                    except Exception:
                        # ignore send failures (e.g., removed perms)
                        pass

# ================================
# Filename Parser (Ultra Robust)
# ================================
RE_MULTI_EXT = re.compile(
    r"(?:\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg|m2ts|3gp|rmvb))"
    r"(?:\.(?:mkv|mp4|avi|mov|flv|webm|wmv|m4v|ts|mpg|mpeg|m2ts|3gp|rmvb))*$",
    re.IGNORECASE
)
RE_LEADING_BRACKETS = re.compile(r"^\s*(?:\[[^\]]*\]|\([^\)]*\)|\{[^\}]*\})\s*")
RE_BRACKETED_BLOCK = re.compile(r"(\[[^\]]*\]|\([^\)]*\)|\{[^\}]*\})")
RE_MULTI_SEP = re.compile(r"[_\.\-]+")
RE_MULTI_SPACE = re.compile(r"\s+")

RE_SXXEYY   = re.compile(r"\bS(\d{1,2})\s*[._\-\s]*E(\d{1,3})\b", re.IGNORECASE)
RE_MINUS_E  = re.compile(r"(?:^|[\s\-_\.])[Ee](\d{1,4})(?:$|[\s\-_\.])")   # "- E226" etc.
RE_SEASON_EP= re.compile(r"\bSeason\s*(\d{1,2})\s*(?:Episode|Ep)?\s*(\d{1,3})\b", re.IGNORECASE)
RE_EPISODE  = re.compile(r"\bEpisode\s*[:\.\-\s_]*?(\d{1,3})\b", re.IGNORECASE)
RE_EP       = re.compile(r"\bEp\s*[:\.\-\s_]*?(\d{1,3})\b", re.IGNORECASE)
RE_E        = re.compile(r"\bE\s*[:\.\-\s_]*?(\d{1,3})\b", re.IGNORECASE)
RE_PARENS   = re.compile(r"\(\s*(\d{1,4})\s*\)")

RE_QUALITY  = re.compile(r"\b(2160|1440|1080|720|540|480|360|240)\s*[pP]?\b")

TRAILING_JUNK = re.compile(
    r"(?:\b(?:dub|dubbed|hindi|eng(?:lish)?|dual(?:[\s\-_]audio)?|multi(?:[\s\-_]audio)?|fhd|sd|hd|bluray|blu[-\s]?ray|b[dr]rip|webrip|hdrip|hevc|x265|x264|10bit|8bit|esub|e-sub|subs?|subtitle|raw|dd\s*\d\.\d|aac|mp3|sample|part\d*|v\d+)\b[\s\-\:_]*)+$",
    re.IGNORECASE
)

def _remove_trailing_ext(s: str) -> str:
    return RE_MULTI_EXT.sub("", s).strip()

def _remove_leading_groups(s: str) -> str:
    # repeatedly remove only at start
    while True:
        m = RE_LEADING_BRACKETS.match(s)
        if not m:
            break
        s = s[m.end():]
    return s.strip()

def _normalize_detect(s: str) -> str:
    # keep contents, remove bracket chars, unify separators
    s2 = re.sub(r"[\[\]\(\)\{\}]", " ", s)
    s2 = RE_MULTI_SEP.sub(" ", s2)
    s2 = RE_MULTI_SPACE.sub(" ", s2)
    return s2.strip()

def _normalize_title(s: str) -> str:
    s2 = RE_BRACKETED_BLOCK.sub(" ", s)
    s2 = RE_MULTI_SEP.sub(" ", s2)
    s2 = RE_MULTI_SPACE.sub(" ", s2)
    return s2.strip()

def _strip_trailing_junk(s: str) -> str:
    prev = None
    out = s.strip()
    while prev != out:
        prev = out
        out = TRAILING_JUNK.sub("", out).strip()
    return out

def parse_filename(filename: str) -> Optional[Tuple[str, str, str, str]]:
    if not filename:
        return None

    # base cleanup
    base = _remove_trailing_ext(filename)
    base = _remove_leading_groups(base)

    work = _normalize_detect(base)
    title_pool = _normalize_title(base)

    # ---- Season/Episode
    season, episode = None, None
    cut_pos_candidates = []

    m = RE_SXXEYY.search(work)
    if m:
        season = f"S{int(m.group(1)):02d}"
        episode = f"{int(m.group(2)):02d}"
        cut_pos_candidates.append(m.start())
    else:
        m2 = RE_SEASON_EP.search(work)
        if m2:
            season = f"S{int(m2.group(1)):02d}"
            episode = f"{int(m2.group(2)):02d}"
            cut_pos_candidates.append(m2.start())
        else:
            # Accept "- E226" variant
            mE = RE_MINUS_E.search(work)
            if mE:
                season = "S01"
                episode = f"{int(mE.group(1)):02d}"
                cut_pos_candidates.append(mE.start())
            else:
                for rx in (RE_EPISODE, RE_EP, RE_E):
                    mm = rx.search(work)
                    if mm:
                        season = "S01"
                        episode = f"{int(mm.group(1)):02d}"
                        cut_pos_candidates.append(mm.start())
                        break
                else:
                    m3 = RE_PARENS.search(work)  # fallback (227)
                    if m3:
                        season = "S01"
                        episode = f"{int(m3.group(1)):02d}"
                        cut_pos_candidates.append(m3.start())

    if not episode:
        return None

    # ---- Quality
    qm = RE_QUALITY.search(work)
    if not qm:
        return None
    q_val = int(qm.group(1))
    quality = "480p" if q_val == 360 else f"{q_val}p"
    cut_pos_candidates.append(qm.start())

    # ---- Build anime title from title_pool up to earliest token
    cut_idx = min(cut_pos_candidates) if cut_pos_candidates else len(title_pool)
    raw_title = title_pool[:cut_idx].strip()

    # polish
    raw_title = _strip_trailing_junk(raw_title)
    raw_title = re.sub(r"^@\S+\s*", "", raw_title).strip()
    raw_title = raw_title.strip(" -_:|,")
    raw_title = RE_MULTI_SPACE.sub(" ", raw_title).strip()

    if not raw_title:
        return None

    anime_name = escape(raw_title)
    return anime_name, season, episode, quality

# ================================
# Access Guard Decorator
# ================================
def guard_access(handler):
    async def wrapper(client: Client, message: Message):
        chat = message.chat
        uid = message.from_user.id if message.from_user else None
        allowed = has_access(message)
        if not allowed:
            # Minimal, non-leaky response
            if chat.type in ("group", "supergroup", "channel"):
                await message.reply("🔒 Private Bot: Pehle login karo.\n`/login Mai Kaam chor hu`", quote=True)
            else:
                await message.reply("🔒 Private Bot: Pehle login karo.\n`/login Mai Kaam chor hu`", quote=True)
            return
        # mark activity & maybe quip
        mark_activity(chat.id)
        out = await handler(client, message)
        # overwork check (per chat)
        quip = maybe_send_overwork_quip(chat.id)
        if quip:
            try:
                await app.send_message(chat.id, quip)
            except Exception:
                pass
        return out
    return wrapper

# ================================
# Commands
# ================================
@app.on_message(filters.command("start") & ~filters.forwarded)
async def start_cmd(_, m: Message):
    await m.reply_text(
        "👋 <b>Private Auto-Caption Bot</b>\n\n"
        "Use <code>/login Mai Kaam chor hu</code> to unlock.\n"
        "Add me to your <i>group/channel</i> and run the same command there for one-time access.\n\n"
        "After that, just post videos/documents — I’ll detect Anime Name, Season, Episode & Quality.",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("help") & ~filters.forwarded)
async def help_cmd(_, m: Message):
    await m.reply_text(
        "<b>Help</b>\n"
        "• <code>/login Mai Kaam chor hu</code> — unlock access (PM/group/channel)\n"
        "• Post or forward media (video/document) with filename — I’ll caption it.\n\n"
        "Quality rules: 360p → 480p, others unchanged; <i>p</i> is lowercase.\n"
        "Examples I handle:\n"
        "• [@Group]_Anime_Name_S01E07_[480p].mkv.mp4\n"
        "• Naruto Shippuden - E226 [1080p BD x265 10bit Multi Audio].mkv\n"
        "• I Was Reincarnated as the 7th Prince S01E08 480p BluRay.mkv",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("login") & ~filters.forwarded)
async def login_cmd(_, m: Message):
    # Extract code after /login (handle "/login Mai Kaam Chor Hu")
    text = m.text or ""
    parts = text.split(None, 1)
    code = normalize_code(parts[1]) if len(parts) > 1 else ""
    if code != SECRET_CODE_CANONICAL:
        await m.reply_text("❌ Wrong code! Sahi code bolo: <code>Mai Kaam chor hu</code>", parse_mode=ParseMode.HTML)
        return

    if m.chat.type in ("group", "supergroup", "channel"):
        chats_logged.add(m.chat.id)
        save_access_db()
        await m.reply_text("✅ Login successful for this chat! Ab bot kaam karega.")
    else:
        if not m.from_user:
            await m.reply_text("❌ Can't verify user.")
            return
        users_logged.add(m.from_user.id)
        save_access_db()
        await m.reply_text("✅ Login successful! Ab bot kaam karega.")

@app.on_message(filters.command("status") & ~filters.forwarded)
@guard_access
async def status_cmd(_, m: Message):
    await m.reply_text("✅ Access active. Main taiyaar hu! ⚙️")

# ================================
# Media Handlers (Channel/Groups/PM)
# ================================
@app.on_message((filters.video | filters.document) & ~filters.forwarded)
@guard_access
async def media_handler(_, m: Message):
    filename = ""
    if m.video and m.video.file_name:
        filename = m.video.file_name
    elif m.document and m.document.file_name:
        filename = m.document.file_name

    if not filename:
        return

    parsed = parse_filename(filename)
    if not parsed:
        # stay quiet about structure specifics; just minimal info
        await m.reply_text("❌ Caption parse failed. Filename me Season/Episode & Quality hona chahiye.")
        return

    anime_name, season, episode, quality = parsed
    caption = DEFAULT_CAPTION.format(
        AnimeName=anime_name,
        Sn=season,
        Ep=episode,
        Quality=quality
    )

    try:
        if m.video:
            await m.reply_video(m.video.file_id, caption=caption, parse_mode=ParseMode.HTML)
        else:
            await m.reply_document(m.document.file_id, caption=caption, parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("Failed to send captioned media.")

    # Optional: try deleting the original to avoid duplicates (won't error if missing perms)
    try:
        await m.delete()
    except Exception:
        pass

# ================================
# Text Handler (for testing via PM/Group)
# ================================
@app.on_message(filters.text & ~filters.command(["start", "help", "login", "status"]) & ~filters.forwarded)
@guard_access
async def text_filename_test(_, m: Message):
    text = (m.text or "").strip()
    if not text:
        return
    parsed = parse_filename(text)
    if not parsed:
        await m.reply_text("❌ Parse failed. Please include Season/Episode & Quality in filename.")
        return
    anime_name, season, episode, quality = parsed
    await m.reply_text(
        f"🎬 <b>{anime_name}</b>\n"
        f"📺 <code>{season}</code> • <b>Ep {int(episode):02d}</b>\n"
        f"🎥 <code>{quality}</code>",
        parse_mode=ParseMode.HTML
    )

# ================================
# Startup
# ================================
@app.on_raw_update()
async def _track_activity(_, __):
    # This dummy listener ensures the client is "ready" for idle_nudger
    return

async def main():
    load_access_db()
    await app.start()
    # background idle nudger
    asyncio.get_event_loop().create_task(idle_nudger())
    log.info("✅ Bot started. Waiting for files...")
    await app.idle()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
