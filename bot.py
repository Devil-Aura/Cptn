import re
import logging
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
import requests
from functools import lru_cache

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = ""
DEFAULT_LANGUAGE = "Hindi #Official"  # Changed to English
CHANNEL_USERNAME = "@CrunchyRollChannel"  # Fixed channel username

@lru_cache(maxsize=100)
def get_anime_name(query):
    try:
        response = requests.get(
            "https://api.jikan.moe/v4/anime",
            params={'q': query, 'limit': 1},
            timeout=5
        )
        data = response.json()
        if data.get('data'):
            return data['data'][0]['title']
        return query
    except Exception:
        return query

def parse_filename(filename):
    try:
        # Clean filename
        clean_name = re.sub(r'\.[^.]*$', '', filename)  # Remove extension
        clean_name = re.sub(r'\[@\w+\]', '', clean_name)  # Remove [@channel]
        clean_name = re.sub(r'[_\[\]]', ' ', clean_name).strip()  # Clean special chars
        
        # Extract quality (improved pattern)
        quality_match = re.search(r'(\d{3,4}p|HD|FHD|WEB[- ]?DL|BluRay|HEVC|10bit)', clean_name, re.I)
        quality = quality_match.group(1) if quality_match else "Unknown"
        
        # Extract season and episode (improved pattern)
        ep_match = re.search(r'S(\d+)E(\d+)', clean_name, re.I) or \
                  re.search(r'(\d+)x(\d+)', clean_name) or \
                  re.search(r'Episode\s*(\d+)', clean_name, re.I) or \
                  re.search(r'\bS(\d+)\b.*?\bE(\d+)\b', clean_name, re.I)
        
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
        
        # Extract anime name (everything before season/episode)
        anime_name = clean_name[:ep_match.start()].strip() if ep_match else clean_name
        anime_name = re.sub(r'\b(480p|720p|1080p|HD|FHD|WEB-DL|BluRay)\b', '', anime_name, flags=re.I).strip()
        
        return {
            'anime_name': anime_name,
            'season': season.zfill(2),
            'episode': episode.zfill(2),
            'quality': quality
        }
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None

def generate_caption(metadata):
    return f"""<b>➥ {metadata['anime_name']} [S{metadata['season']}]</b>
<b>🎬 Episode - {metadata['episode']}</b>
<b>🎧 Language - {DEFAULT_LANGUAGE}</b>
<b>🔎 Quality : {metadata['quality']}</b>
<b>📡 Powered by : 
{CHANNEL_USERNAME}</b>"""

def handle_message(update: Update, context: CallbackContext):
    try:
        message = update.channel_post
        if not message:
            return

        media = message.video or message.document
        if not media or not media.file_name:
            return

        logger.info(f"Processing: {media.file_name}")
        
        # Parse metadata
        metadata = parse_filename(media.file_name)
        if not metadata:
            return
            
        # Get the original English name from filename (no API call)
        # If you want to use Jikan API, uncomment next line:
        # metadata['anime_name'] = get_anime_name(metadata['anime_name']) or metadata['anime_name']
        
        # Generate caption
        caption = generate_caption(metadata)
        
        # Delete and repost quickly
        context.bot.delete_message(
            chat_id=message.chat.id,
            message_id=message.message_id
        )
        
        if message.video:
            context.bot.send_video(
                chat_id=message.chat.id,
                video=media.file_id,
                caption=caption,
                parse_mode='HTML'
            )
        else:
            context.bot.send_document(
                chat_id=message.chat.id,
                document=media.file_id,
                caption=caption,
                parse_mode='HTML'
            )
            
        logger.info("Media reposted with caption")
        
    except Exception as e:
        logger.error(f"Error: {e}")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(MessageHandler(
        Filters.chat_type.channel & (Filters.video | Filters.document),
        handle_message
    ))
    
    updater.start_polling()
    logger.info("Bot is ready!")
    updater.idle()

if __name__ == '__main__':
    main()
