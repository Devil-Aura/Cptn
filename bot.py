import re
import logging
import asyncio
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message

# === CONFIGURATION ===
API_ID = 22768311  # your api id here
API_HASH = "702d8884f48b42e865425391432b3794"  # your api hash here
BOT_TOKEN = ""  # your bot token here

app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# === Default Caption Template ===
DEFAULT_CAPTION = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# === AniList Query function with correct headers ===
async def get_anime_title(filename: str) -> str:
    cleaned = re.sub(r'[\[\]()_.-]', ' ', filename)
    cleaned = re.sub(r'\d{3,4}[pP]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title {
          english
          romaji
          native
        }
      }
    }
    '''
    variables = {"search": cleaned}

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://graphql.anilist.co",
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            media = data.get("data", {}).get("Media")
            if media:
                return (
                    media["title"].get("english")
                    or media["title"].get("romaji")
                    or media["title"].get("native")
                    or cleaned
                )
            else:
                return cleaned
        except Exception as e:
            logging.error(f"AniList fetch error: {e}")
            return cleaned

# === Extract season, episode, quality ===
def extract_sn_ep_quality(filename: str):
    sn_match = re.search(r'(S\d{1,2})', filename, re.IGNORECASE)
    ep_match = re.search(r'(E\d{1,3})', filename, re.IGNORECASE)
    quality_match = re.search(r'(\d{3,4})[pP]', filename)

    Sn = sn_match.group(1).upper() if sn_match else "S01"
    Ep = ep_match.group(1).upper().replace("E", "") if ep_match else "01"

    if quality_match:
        q = quality_match.group(1)
        if q == "360":
            q = "480"
        Quality = f"{q.lower()}p"
    else:
        Quality = "480p"

    return Sn, Ep, Quality

# === Main handler ===
@app.on_message(filters.video | filters.document)
async def auto_caption(client: Client, message: Message):
    media = message.video or message.document
    if not media or not media.file_name:
        return

    filename = media.file_name

    anime_title = await get_anime_title(filename)
    Sn, Ep, Quality = extract_sn_ep_quality(filename)

    caption_text = DEFAULT_CAPTION.format(AnimeName=anime_title.strip(), Sn=Sn, Ep=Ep, Quality=Quality)

    try:
        if message.video:
            await message.reply_video(
                video=media.file_id,
                caption=caption_text,
                parse_mode="html"
            )
        else:
            await message.reply_document(
                document=media.file_id,
                caption=caption_text,
                parse_mode="html"
            )
    except Exception as e:
        logging.error(f"Error sending media: {e}")
        await message.reply(f"❌ Error sending file: {e}")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
