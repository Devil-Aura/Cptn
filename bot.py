import re
import logging
from difflib import SequenceMatcher
from pyrogram import Client, filters
from pyrogram.types import Message

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
API_ID = 22768311  # Your API ID
API_HASH = "702d8884f48b42e865425391432b3794"  # Your API Hash
BOT_TOKEN = ""  # Your Bot Token

# Default caption template
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel</b>"""

# Bot Client
app = Client(
    "caption_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Temporary in-memory anime names list
anime_names = []

# Similarity check
def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# Find closest anime name from list
def find_closest_anime_name(filename: str):
    filename_clean = re.sub(r"[^a-zA-Z0-9 ]", " ", filename).lower()
    best_match = None
    best_ratio = 0.0
    for name in anime_names:
        name_clean = re.sub(r"[^a-zA-Z0-9 ]", " ", name).lower()
        ratio = similar(filename_clean, name_clean)
        if ratio >= 0.5 and ratio > best_ratio:
            best_ratio = ratio
            best_match = name
    return best_match

# Extract season, episode, quality & anime name
def extract_info(filename: str):
    # Remove special chars and extension
    clean_name = re.sub(r"[_\-.]", " ", filename)

    # Season
    season = re.search(r'[Ss](?:eason)?\s?(0?\d{1,2})', filename)
    sn = f"S{season.group(1).zfill(2)}" if season else "S01"

    # Episode
    episode = re.search(r'[Ee](?:p|pisode)?\s?(0?\d{1,3})', filename)
    ep = episode.group(1).zfill(2) if episode else "01"

    # Quality
    quality = re.search(r'(\d{3,4}[pP])', filename)
    quality_final = quality.group(1).lower() if quality else "480p"

    # Try to match existing anime name
    existing_name = find_closest_anime_name(filename)
    if existing_name:
        name = existing_name
    else:
        # Auto-learn anime name by removing season/episode/quality parts
        name = re.sub(r'[Ss](?:eason)?\s?\d{1,2}', '', clean_name)
        name = re.sub(r'[Ee](?:p|pisode)?\s?\d{1,3}', '', name)
        name = re.sub(r'\d{3,4}[pP]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        if name and name not in anime_names:
            anime_names.append(name)  # Save for future use

    return name or "Unknown Anime", sn, ep, quality_final

# Commands
@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "**👋 Welcome to the Anime Caption Bot!**\n\n"
        "➤ Just send any anime episode file and I'll generate captions automatically.\n"
        "➤ I now **auto-learn** anime names from filenames!\n"
        "➤ You can still manage names with `/addanime`, `/delanime`, `/listanime`."
    )

@app.on_message(filters.command("help1"))
async def help1(_, message: Message):
    await message.reply_text(
        "**📜 Bot Commands:**\n"
        "`/addanime Anime Name` – Add an anime name manually\n"
        "`/delanime Anime Name` – Delete an anime name\n"
        "`/listanime` – View added anime names\n"
        "`/start` – Show welcome"
    )

@app.on_message(filters.command("addanime"))
async def add_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply("❌ Use: `/addanime Anime Name`")
    anime_names.append(name)
    await message.reply(f"✅ Added anime name: **{name}**")

@app.on_message(filters.command("delanime"))
async def del_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply("❌ Use: `/delanime Anime Name`")
    try:
        anime_names.remove(name)
        await message.reply(f"🗑 Deleted anime: **{name}**")
    except ValueError:
        await message.reply("❌ Not found in list.")

@app.on_message(filters.command("listanime"))
async def list_anime(_, message: Message):
    if not anime_names:
        return await message.reply("📭 No anime names added.")
    await message.reply("📚 **Anime List:**\n" + "\n".join(f"• {name}" for name in anime_names))

# Auto-caption files
@app.on_message(filters.document | filters.video | filters.audio)
async def on_file(_, message: Message):
    media = message.document or message.video or message.audio
    if not media or not media.file_name:
        return

    filename = media.file_name.rsplit(".", 1)[0]  # Remove extension
    anime_name, sn, ep, quality = extract_info(filename)

    caption = DEFAULT_CAPTION.format(
        AnimeName=anime_name,
        Sn=sn,
        Ep=ep,
        Quality=quality
    )

    await message.reply(caption, parse_mode="html")  # ✅ HTML parse mode fixed

if __name__ == "__main__":
    app.run()
