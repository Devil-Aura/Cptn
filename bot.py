import re
import logging
import requests
from functools import lru_cache
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== Configuration =====
class Config:
    BOT_TOKEN = "YOUR_BOT_TOKEN"
    DEFAULT_LANGUAGE = "Hindi #Official"
    MAL_CLIENT_ID = "2683e006d6116b8611c50c1dbe20a1a1"
    MAX_RETRIES = 3
    CACHE_SIZE = 100

# ===== Services =====
class MALService:
    BASE_URL = "https://api.myanimelist.net/v2"
    
    @classmethod
    @lru_cache(maxsize=Config.CACHE_SIZE)
    def get_anime_info(cls, query):
        try:
            response = requests.get(
                f"{cls.BASE_URL}/anime",
                headers={'X-MAL-CLIENT-ID': Config.MAL_CLIENT_ID},
                params={'q': query, 'limit': 1, 'fields': 'title'},
                timeout=10
            )
            data = response.json()
            if data.get('data'):
                return data['data'][0]['node']['title']
            return query
        except Exception as e:
            logger.error(f"MAL API Error: {e}")
            return query

class JikanService:
    BASE_URL = "https://api.jikan.moe/v4"
    
    @classmethod
    @lru_cache(maxsize=Config.CACHE_SIZE)
    def get_anime_info(cls, query):
        try:
            response = requests.get(
                f"{cls.BASE_URL}/anime",
                params={'q': query, 'limit': 1},
                timeout=10
            )
            data = response.json()
            if data.get('data'):
                return data['data'][0]['title']
            return query
        except Exception as e:
            logger.error(f"Jikan Error: {e}")
            return query

# ===== Parser =====
class FilenameParser:
    @staticmethod
    def parse(filename):
        try:
            clean_name = re.sub(r'\.[^.]*$', '', filename)
            clean_name = re.sub(r'\[@\w+\]', '', clean_name)
            clean_name = re.sub(r'[_\[\]()]', ' ', clean_name).strip()
            
            # Extract quality
            quality = re.search(r'(\d{3,4}p|HD|WEB-DL)', clean_name, re.I)
            quality = quality.group(1) if quality else "Unknown"
            
            # Extract episode info
            ep_match = re.search(r'S(\d+)E(\d+)', clean_name, re.I) or \
                      re.search(r'(\d+)x(\d+)', clean_name) or \
                      re.search(r'Episode\s*(\d+)', clean_name, re.I)
            
            if ep_match:
                if len(ep_match.groups()) > 1:
                    season = ep_match.group(1)
                    episode = ep_match.group(2)
                else:
                    season = "01"
                    episode = ep_match.group(1)
            else:
                season = "01"
                episode = "01"
            
            anime_name = clean_name[:ep_match.start()].strip() if ep_match else clean_name
            anime_name = re.sub(r'\b(480p|720p|1080p|HD)\b', '', anime_name, flags=re.I).strip()
            
            return {
                'anime_name': anime_name,
                'season': season.zfill(2),
                'episode': episode.zfill(2),
                'quality': quality
            }
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None

# ===== Caption Generator =====
def generate_caption(metadata, channel_username):
    return f"""<b>➥ {metadata['anime_name']} [S{metadata['season']}]</b>
<b>🎬 Episode - {metadata['episode']}</b>
<b>🎧 Language - {Config.DEFAULT_LANGUAGE}</b>
<b>🔎 Quality : {metadata['quality']}</b>
<b>📡 Powered by : {channel_username}</b>"""

# ===== Handler =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message:
            return

        media = message.video or message.document
        if not media or not media.file_name:
            return

        logger.info(f"Processing in {message.chat.title}: {media.file_name}")
        
        # Get channel username
        channel_username = f"@{message.chat.username}" if message.chat.username else message.chat.title
        
        # Parse metadata
        metadata = FilenameParser.parse(media.file_name)
        if not metadata:
            return
            
        # Get anime name
        for attempt in range(Config.MAX_RETRIES):
            try:
                metadata['anime_name'] = MALService.get_anime_info(metadata['anime_name']) or \
                                      JikanService.get_anime_info(metadata['anime_name'])
                break
            except Exception as e:
                if attempt == Config.MAX_RETRIES - 1:
                    logger.error(f"Name lookup failed: {e}")
        
        # Generate caption
        caption = generate_caption(metadata, channel_username)
        
        # Delete and repost
        await message.delete()
        if message.video:
            await context.bot.send_video(
                chat_id=message.chat.id,
                video=media.file_id,
                caption=caption,
                parse_mode='HTML'
            )
        else:
            await context.bot.send_document(
                chat_id=message.chat.id,
                document=media.file_id,
                caption=caption,
                parse_mode='HTML'
            )
            
        logger.info(f"Reposted in {message.chat.title}")
        
    except Exception as e:
        logger.error(f"Error: {e}")

# ===== Main =====
def main():
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Handle videos/documents in any channel
    application.add_handler(MessageHandler(
        filters.ChatType.CHANNEL & (filters.VIDEO | filters.Document.ALL),
        handle_message
    ))
    
    application.run_polling()
    logger.info("Bot is ready for all channels!")

if __name__ == '__main__':
    main()
