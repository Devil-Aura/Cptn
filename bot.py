import re
import logging
from difflib import SequenceMatcher
from pyrogram import Client, filters
from pyrogram.types import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIG
API_ID = 22768311  # Replace with your actual API ID
API_HASH = "702d8884f48b42e865425391432b3794"  # Replace with your actual API HASH
BOT_TOKEN = ""  # Replace with your actual BOT TOKEN

# Default caption format
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# Create bot client
app = Client("anime_caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Store anime names temporarily
anime_names = []

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_closest_anime_name(filename: str):
    best_match = None
    best_ratio = 0.0
    for name in anime_names:
        ratio = similar(filename, name)
        if ratio >= 0.5 and ratio > best_ratio:
            best_ratio = ratio
            best_match = name
    return best_match

def extract_info_from_filename(filename: str):
    filename = filename.lower()

    # Patterns
    season_match = re.search(r's(?:eason)?[_\s]?(0?\d{1,2})', filename)
    episode_match = re.search(r'e(?:pisode)?[_\s]?(0?\d{1,3})', filename)
    quality_match = re.search(r'[_\s\-]([0-9]{3,4}p)', filename)

    sn = f"S{season_match.group(1).zfill(2)}" if season_match else "S01"
    ep = episode_match.group(1).zfill(2) if episode_match else "01"
    quality = quality_match.group(1).lower() if quality_match else "480p"

    anime_name = find_closest_anime_name(filename)
    if not anime_name:
        anime_name = "Unknown Anime"

    return anime_name, sn, ep, quality

@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "**👋 Welcome to the Anime Caption Bot!**\n\n"
        "➤ Add anime names using `/addanime Solo Leveling`\n"
        "➤ Send a file and I'll auto-generate a caption.\n"
        "➤ Use `/help1` for all commands."
    )

@app.on_message(filters.command("help1"))
async def help_cmd(_, message: Message):
    await message.reply_text(
        "**🛠 Bot Commands:**\n\n"
        "`/addanime <name>` – Add an anime name\n"
        "`/delanime <name>` – Delete an anime name\n"
        "`/listanime` – View added anime names\n"
        "`/start` – Show welcome message\n"
        "Just send any anime episode file and I’ll auto-caption it!"
    )

@app.on_message(filters.command("addanime"))
async def add_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply("❌ Usage: `/addanime <anime name>`")

    anime_names.append(name)
    await message.reply(f"✅ Anime name added: **{name}**")

@app.on_message(filters.command("delanime"))
async def del_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply("❌ Usage: `/delanime <anime name>`")

    try:
        anime_names.remove(name)
        await message.reply(f"🗑️ Anime name deleted: **{name}**")
    except ValueError:
        await message.reply("❌ Anime name not found!")

@app.on_message(filters.command("listanime"))
async def list_animes(_, message: Message):
    if not anime_names:
        return await message.reply("📭 No anime names added yet.")
    await message.reply("📜 **Anime Names List:**\n\n" + "\n".join(f"• {name}" for name in anime_names))

@app.on_message(filters.document | filters.video | filters.audio)
async def caption_generator(_, message: Message):
    media = message.document or message.video or message.audio
    if not media or not media.file_name:
        return

    filename = media.file_name
    anime_name, sn, ep, quality = extract_info_from_filename(filename)

    caption = DEFAULT_CAPTION.format(AnimeName=anime_name, Sn=sn, Ep=ep, Quality=quality)
    await message.reply(caption)

if __name__ == "__main__":
    app.run()
