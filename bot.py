import logging
import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Token & API keys
API_ID = 22768311      # replace with your api_id
API_HASH = "702d8884f48b42e865425391432b3794"  # replace with your api_hash
BOT_TOKEN = ""  # replace with your bot token

# Initialize bot
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ➤ Anime title finder using AniList API
async def get_anime_name_from_anilist(query: str) -> str:
    try:
        url = "https://graphql.anilist.co"
        query_payload = {
            "query": """
                query ($search: String) {
                  Media(search: $search, type: ANIME) {
                    title {
                      romaji
                    }
                  }
                }
            """,
            "variables": {
                "search": query
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=query_payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["data"]["Media"]["title"]["romaji"]
                else:
                    logger.error(f"AniList fetch error: {response.status}")
    except Exception as e:
        logger.error(f"Error fetching from AniList: {e}")
    return "Unknown Anime"

# ➤ File name parser
def parse_filename(filename: str):
    sn_match = re.search(r'S(\d+)', filename, re.IGNORECASE)
    ep_match = re.search(r'EP?(\d+)', filename, re.IGNORECASE)
    quality_match = re.search(r'(\d{3,4})[Pp]', filename)

    sn = f"Season {sn_match.group(1)}" if sn_match else "Unknown Season"
    ep = ep_match.group(1) if ep_match else "00"
    quality = quality_match.group(1) + "p" if quality_match else "480p"
    quality = "480p" if quality == "360p" else quality.lower()

    return sn, ep, quality

# ➤ Default Caption Template
DEFAULT_CAPTION_TEMPLATE = (
    "<b>➥ {AnimeName} [{Sn}]\n"
    "🎬 Episode - {Ep}\n"
    "🎧 Language - Hindi #Official\n"
    "🔎 Quality : {Quality}\n"
    "📡 Powered by :\n"
    "@CrunchyRollChannel.</b>"
)

# ➤ Media Handler
@app.on_message(filters.channel & (filters.video | filters.document | filters.photo))
async def media_handler(_, message: Message):
    try:
        if message.caption:
            filename = message.caption
        elif message.document and message.document.file_name:
            filename = message.document.file_name
        elif message.video and message.video.file_name:
            filename = message.video.file_name
        else:
            filename = "Unknown Filename"

        sn, ep, quality = parse_filename(filename)
        anime_name = await get_anime_name_from_anilist(filename)

        caption = DEFAULT_CAPTION_TEMPLATE.format(
            AnimeName=anime_name,
            Sn=sn,
            Ep=ep,
            Quality=quality
        )

        await message.copy(
            chat_id=message.chat.id,
            caption=caption,
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"Error sending media: {e}")

# ➤ Start Bot
app.run()
