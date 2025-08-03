import re
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
API_ID = 22768311
API_HASH = "702d8884f48b42e865425391432b3794"
BOT_TOKEN = ""

bot = Client("anime_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory anime list
anime_names = set()

# Default caption format
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# Start command
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "👋 Welcome to Anime Uploader Bot!\nUse /help1 to see available commands.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Help", callback_data="help1")],
            [InlineKeyboardButton("Join Channel", url="https://t.me/CrunchyRollChannel")]
        ])
    )

# Help command
@bot.on_message(filters.command("help1"))
async def help1(client, message):
    help_text = (
        "**📘 Help Menu:**\n\n"
        "`/addanime Anime Name` – Add anime name to memory\n"
        "`/deleteanime Anime Name` – Delete anime name from memory\n"
        "`/listanimes` – Show all added anime names\n\n"
        "Just send a video and the bot will auto-caption it using the filename."
    )
    await message.reply(help_text)

# Add anime command
@bot.on_message(filters.command("addanime"))
async def add_anime(client, message):
    try:
        name = message.text.split(" ", 1)[1].strip()
        anime_names.add(name)
        await message.reply(f"✅ Added anime: `{name}`")
    except:
        await message.reply("⚠️ Usage: /addanime Anime Name")

# Delete anime command
@bot.on_message(filters.command("deleteanime"))
async def delete_anime(client, message):
    try:
        name = message.text.split(" ", 1)[1].strip()
        anime_names.discard(name)
        await message.reply(f"❌ Removed anime: `{name}`")
    except:
        await message.reply("⚠️ Usage: /deleteanime Anime Name")

# List all added anime names
@bot.on_message(filters.command("listanimes"))
async def list_animes(client, message):
    if not anime_names:
        await message.reply("⚠️ No anime names added yet.")
    else:
        await message.reply("🎥 Anime Names:\n\n" + "\n".join(f"• {a}" for a in anime_names))

# Helper function to match partial names (50%+)
def match_anime_from_filename(filename):
    filename_lower = filename.lower()
    for anime in anime_names:
        anime_lower = anime.lower()
        if anime_lower in filename_lower:
            return anime
        elif len(anime_lower) >= 4:
            matches = sum(1 for word in anime_lower.split() if word in filename_lower)
            ratio = matches / len(anime_lower.split())
            if ratio >= 0.5:
                return anime
    return "Unknown Anime"

# Parse details from filename
def extract_info(filename):
    name = match_anime_from_filename(filename)

    season_match = re.search(r"[Ss](\d{1,2})", filename)
    ep_match = re.search(r"[Ee](\d{1,3})", filename)
    quality_match = re.search(r"(?:^|[^a-zA-Z])((?:360|480|720|1080|2k|4k)[pP])", filename)

    season = f"S{season_match.group(1).zfill(2)}" if season_match else "S01"
    episode = ep_match.group(1) if ep_match else "1"
    quality = quality_match.group(1) if quality_match else "Unknown"

    return name, episode, season, quality

# Handle videos
@bot.on_message(filters.video)
async def video_handler(client, message: Message):
    try:
        file_name = message.video.file_name or ""
        anime, ep, sn, quality = extract_info(file_name)

        caption = DEFAULT_CAPTION.format(AnimeName=anime, Ep=ep, Sn=sn, Quality=quality)

        await message.reply_video(
            video=message.video.file_id,
            caption=caption,
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"Error in video_handler: {e}")
        await message.reply("❌ Failed to send video with caption.")

# Callback for Help button
@bot.on_callback_query(filters.regex("help1"))
async def help_cb(client, callback_query):
    await callback_query.message.edit_text(
        "**📘 Help Menu:**\n\n"
        "`/addanime Anime Name` – Add anime name to memory\n"
        "`/deleteanime Anime Name` – Delete anime name from memory\n"
        "`/listanimes` – Show all added anime names\n\n"
        "Just send a video and the bot will auto-caption it using the filename.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Back", callback_data="start")]
        ])
    )

@bot.on_callback_query(filters.regex("start"))
async def start_cb(client, callback_query):
    await callback_query.message.edit_text(
        "👋 Welcome to Anime Uploader Bot!\nUse /help1 to see available commands.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Help", callback_data="help1")],
            [InlineKeyboardButton("Join Channel", url="https://t.me/CrunchyRollChannel")]
        ])
    )

bot.run()
