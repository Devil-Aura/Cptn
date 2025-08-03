from pyrogram import Client, filters
from pyrogram.types import Message
import re
import httpx
import asyncio

# BOT CONFIG
API_ID = 22768311
API_HASH = "702d8884f48b42e865425391432b3794"
BOT_TOKEN = ""

# Default caption template
default_caption = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

channel_captions = {}
title_cache = {}  # Cache raw_name -> corrected title

app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def fetch_title(name: str) -> str:
    name = name.strip()
    if not name:
        return name
    if name in title_cache:
        return title_cache[name]

    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { english romaji }
      }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post("https://graphql.anilist.co",
                                     json={"query": query, "variables": {"search": name}})
        data = resp.json().get("data", {}).get("Media")
        if data:
            title = data["title"].get("english") or data["title"].get("romaji") or name
        else:
            title = name
    except Exception:
        title = name

    title_cache[name] = title
    return title

@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setcaption Your caption with {AnimeName}, {Sn}, {Ep}, {Quality}")
    channel_captions[message.chat.id] = message.text.split(" ", 1)[1]
    await message.reply_text("✅ Caption set (will reset on restart).")

@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    cap = channel_captions.get(message.chat.id, default_caption)
    await message.reply_text(f"**Current template:**\n\n{cap}")

@app.on_message(filters.channel & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    fname = message.document.file_name if message.document else message.video.file_name

    clean = re.sub(r'^[\[\(].*?[\]\)]\s*', '', fname)

    m = re.search(r"(.+?)[\s\[\(\-_]+S?(\d{1,2})[xEx\-]?E?(\d{1,2}).*?(\d{3,4}p)?",
                  clean, re.IGNORECASE)
    if not m:
        return

    raw_name, sn_raw, ep_raw, q = m.groups()
    sn = f"S{int(sn_raw):02d}"
    ep = f"{int(ep_raw):02d}"
    quality = (q.lower() if q else "unknown").replace("360p", "480p")

    raw_name = raw_name.strip().rstrip('._-')
    anime = await fetch_title(raw_name)

    cap_tmpl = channel_captions.get(message.chat.id, default_caption)
    caption = cap_tmpl.format(AnimeName=anime, Sn=sn, Ep=ep, Quality=quality)

    try:
        if message.document:
            await app.send_document(chat_id=message.chat.id,
                                     document=message.document.file_id,
                                     caption=caption)
        else:
            await app.send_video(chat_id=message.chat.id,
                                 video=message.video.file_id,
                                 caption=caption)
        await message.delete()
    except Exception as e:
        await message.reply_text(f"❌ Error reposting: {e}")

app.run()
