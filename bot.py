import logging
import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = 22768311
API_HASH = "702d8884f48b42e865425391432b3794"
BOT_TOKEN = ""

app = Client("EpisodeSortBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Default caption
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# AniList API function
async def fetch_anilist_title(query: str) -> str:
    url = "https://graphql.anilist.co"
    query_data = {
        "query": '''
            query ($search: String) {
                Media(search: $search, type: ANIME) {
                    title {
                        romaji
                    }
                }
            }
        ''',
        "variables": {"search": query}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=query_data) as resp:
                if resp.status != 200:
                    logger.error(f"AniList fetch error: {resp.status}")
                    return query
                data = await resp.json()
                return data["data"]["Media"]["title"]["romaji"]
    except Exception as e:
        logger.error(f"AniList fetch error: {e}")
        return query

# Sort function
@app.on_message(filters.channel & filters.media)
async def sort_episode(client: Client, message: Message):
    try:
        file_name = message.document.file_name if message.document else \
                    message.video.file_name if message.video else \
                    message.caption

        if not file_name:
            return

        # Normalize 360p to 480p and lowercase "P"
        file_name = file_name.replace("360P", "480p").replace("360p", "480p").replace("P", "p")

        # Parse episode
        episode_match = re.search(r"[Ee]p(?:isode)?[\s._-]*([0-9]+)", file_name)
        ep = episode_match.group(1) if episode_match else "1"

        # Parse season
        season_match = re.search(r"[Ss]eason[\s._-]*([0-9]+)", file_name)
        sn = f"Season {season_match.group(1)}" if season_match else "Season 1"

        # Parse quality
        quality_match = re.search(r"(\d{3,4}p)", file_name)
        quality = quality_match.group(1).lower() if quality_match else "480p"

        # Get anime name
        name_cleaned = re.sub(r"[\s._-]*(ep|episode|season)[\s._-]*\d+", "", file_name, flags=re.I)
        name_cleaned = re.sub(r"\[.*?\]|\(.*?\)|\{.*?\}", "", name_cleaned)
        name_cleaned = re.sub(r"[\s._-]+", " ", name_cleaned).strip()

        anime_name = await fetch_anilist_title(name_cleaned)

        caption = DEFAULT_CAPTION.format(AnimeName=anime_name, Sn=sn, Ep=ep, Quality=quality)

        await message.copy(chat_id=message.chat.id, caption=caption, parse_mode="html")

    except Exception as e:
        logger.error(f"Error sending media: {e}")

app.run()
