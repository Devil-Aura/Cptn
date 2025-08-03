import os
import re
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = 22768311  # Replace with your API ID
API_HASH = "702d8884f48b42e865425391432b3794"  # Replace with your API HASH
BOT_TOKEN = ""  # Replace with your bot token
LOG_CHANNEL = -1002746159355  # Your anime names log channel ID

app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

anime_names = []

# Command to fetch anime names from the log channel
@app.on_message(filters.command("refreshanimes"))
async def refresh_animes(_, message: Message):
    global anime_names
    anime_names = []
    try:
        async for msg in app.get_chat_history(LOG_CHANNEL, limit=1000):
            if msg.text:
                anime_names.append(msg.text.strip().lower())
        await message.reply(f"✅ Refreshed {len(anime_names)} anime names from log channel.")
    except Exception as e:
        await message.reply(f"❌ Failed to fetch anime names: {e}")
        logger.error(f"Failed to fetch anime names: {e}")

# Function to parse filename details
def extract_info(filename: str):
    name = filename.rsplit('.', 1)[0]  # Remove file extension
    name = name.replace('_', ' ').replace('.', ' ')

    # Extract quality
    quality_match = re.search(r'(\d{3,4})[pP]', name)
    quality = quality_match.group(1).lower() + 'p' if quality_match else "unknown"
    if quality == '360p':
        quality = '480p'

    # Extract episode
    episode_match = re.search(r'[Ee]p?(\d{1,3})', name)
    episode = episode_match.group(1) if episode_match else "unknown"

    # Extract season with leading zero, default S01
    season_match = re.search(r'[Ss](\d{1,2})', name)
    if season_match:
        season = f"S{int(season_match.group(1)):02}"
    else:
        season = "S01"

    # Clean anime name by removing quality, season, episode, and common tags
    anime_title = name
    anime_title = re.sub(r'\b\d{3,4}[pP]\b', '', anime_title)
    anime_title = re.sub(r'[Ss]\d{1,2}', '', anime_title)
    anime_title = re.sub(r'[Ee]p?\d{1,3}', '', anime_title)
    anime_title = re.sub(r'\b(mp4|mkv|avi|flv|mov|mp3|web-dl|bluray|webrip|x264|h264|hevc|10bit|aac|dual|audio|dub)\b', '', anime_title, flags=re.IGNORECASE)
    anime_title = re.sub(r'[\W_]+', ' ', anime_title).strip()

    return anime_title.lower(), season, episode, quality

# Match anime name with log channel names
def match_anime_name(extracted_name):
    for name in anime_names:
        if name in extracted_name:
            return name.title()
    return extracted_name.title()

# Main handler: reply with file + caption
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_media(_, message: Message):
    try:
        media = message.document or message.video or message.audio
        if not media or not media.file_name:
            await message.reply("❌ Could not detect filename.")
            return

        anime_raw, season, episode, quality = extract_info(media.file_name)
        anime_name = match_anime_name(anime_raw)

        caption = f"""<b>➥ {anime_name} [{season}]
🎬 Episode - {episode}
🎧 Language - Hindi #Official
🔎 Quality : {quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

        # Re-send media with caption
        if message.document:
            await app.send_document(
                chat_id=message.chat.id,
                document=media.file_id,
                caption=caption,
                parse_mode="html"
            )
        elif message.video:
            await app.send_video(
                chat_id=message.chat.id,
                video=media.file_id,
                caption=caption,
                parse_mode="html"
            )
        elif message.audio:
            await app.send_audio(
                chat_id=message.chat.id,
                audio=media.file_id,
                caption=caption,
                parse_mode="html"
            )

        # Delete original message to avoid duplicates
        await message.delete()

    except RPCError as e:
        logger.error(f"Telegram API error: {e}")
        await message.reply(f"❌ Telegram API error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        await message.reply(f"❌ Unexpected error occurred.")

# Basic start command
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply("I am a private bot of @World_Fastest_Bots")

# Basic help command
@app.on_message(filters.command(["help", "help1"]) & filters.private)
async def help_cmd(_, message: Message):
    help_text = (
        "/refreshanimes - Fetch latest anime names from log channel\n"
        "Send me a video or document and I will caption it automatically."
    )
    await message.reply(help_text)

app.run()
