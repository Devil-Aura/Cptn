import re
import logging
import json
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
API_ID = 22768311  # Replace with your API ID
API_HASH = "702d8884f48b42e865425391432b3794"  # Replace with your API HASH
BOT_TOKEN = ""  # Replace with your bot token
STORAGE_FILE = "anime_bot_data.json"
DEFAULT_LANGUAGE = "Hindi #Official"
POWERED_BY = "@CrunchyRollChannel"

# Data storage structure
bot_data = {
    "custom_names": {},  # {"pattern": "correct_name"}
    "channel_captions": {},  # {chat_id: "caption_template"}
    "default_caption": """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - {Language}
🔎 Quality : {Quality}
📡 Powered by : 
{PoweredBy}</b>"""
}

# Load saved data
if os.path.exists(STORAGE_FILE):
    try:
        with open(STORAGE_FILE, "r") as f:
            saved_data = json.load(f)
            bot_data.update(saved_data)
    except Exception as e:
        logger.error(f"Error loading data: {e}")

def save_data():
    with open(STORAGE_FILE, "w") as f:
        json.dump(bot_data, f)

app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ===== COMMAND HANDLERS =====
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text(
        "🤖 Anime Auto-Caption Bot\n\n"
        "Add me to your channel as admin with:\n"
        "- Delete Messages\n"
        "- Post Messages\n\n"
        "Use /help for commands"
    )

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(_, message: Message):
    help_text = (
        "📝 <b>Available Commands</b>:\n\n"
        "<b>For Channels</b>:\n"
        "/setcaption - Set custom caption template\n"
        "/showcaption - Show current caption\n\n"
        "<b>Anime Name Management</b>:\n"
        "/addname - Add custom anime name mapping\n"
        "/removename - Remove a mapping\n"
        "/listnames - Show all saved names\n\n"
        "Placeholders: {AnimeName}, {Sn}, {Ep}, {Quality}, {Language}, {PoweredBy}"
    )
    await message.reply_text(help_text)

@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setcaption Your_Caption_Template")
    
    bot_data["channel_captions"][message.chat.id] = message.text.split(" ", 1)[1]
    save_data()
    await message.reply_text("✅ Caption template updated!")

@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    caption = bot_data["channel_captions"].get(
        message.chat.id,
        bot_data["default_caption"]
    )
    await message.reply_text(f"📝 Current caption template:\n\n{caption}")

@app.on_message(filters.command("addname") & filters.private)
async def add_name(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: /addname filename_pattern anime_name")
    
    pattern = ' '.join(message.command[1:-1]).lower()
    name = message.command[-1]
    bot_data["custom_names"][pattern] = name
    save_data()
    await message.reply_text(f"✅ Added: '{pattern}' → '{name}'")

@app.on_message(filters.command("removename") & filters.private)
async def remove_name(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /removename filename_pattern")
    
    pattern = ' '.join(message.command[1:]).lower()
    if pattern in bot_data["custom_names"]:
        del bot_data["custom_names"][pattern]
        save_data()
        await message.reply_text(f"✅ Removed: '{pattern}'")
    else:
        await message.reply_text("❌ Pattern not found")

@app.on_message(filters.command("listnames") & filters.private)
async def list_names(_, message: Message):
    if not bot_data["custom_names"]:
        return await message.reply_text("No custom names saved yet")
    
    names_list = "\n".join(
        f"• {pattern} → {name}"
        for pattern, name in bot_data["custom_names"].items()
    )
    await message.reply_text(f"📝 Saved anime names:\n\n{names_list}")

# ===== AUTO CAPTION FUNCTION =====
def parse_filename(filename: str) -> Optional[Dict[str, str]]:
    try:
        # Clean filename
        clean_name = re.sub(r'\.[^.]*$', '', filename)  # Remove extension
        clean_name = re.sub(r'\[@\w+\]', '', clean_name)  # Remove channel tags
        clean_name = re.sub(r'[_\[\]]', ' ', clean_name).strip()  # Clean special chars
        
        # Check for custom names first
        for pattern, name in bot_data["custom_names"].items():
            if pattern.lower() in clean_name.lower():
                clean_name = name
                break
        
        # Extract quality (improved pattern)
        quality_match = re.search(
            r'(\d{3,4}p|HD|FHD|WEB[- ]?DL|BluRay|HEVC|10bit)',
            clean_name, re.I
        )
        quality = quality_match.group(1) if quality_match else "Unknown"
        
        # Extract season and episode (robust pattern)
        ep_match = re.search(
            r'(?:S|Season\s*)(\d+).*?(?:E|Episode\s*)(\d+)|(\d+)x(\d+)',
            clean_name, re.I
        )
        
        if ep_match:
            season = ep_match.group(1) or ep_match.group(3) or "01"
            episode = ep_match.group(2) or ep_match.group(4) or "01"
        else:
            # Fallback for files without clear season/episode
            season = "01"
            ep_match = re.search(r'\b(\d{2})\b', clean_name)
            episode = ep_match.group(1) if ep_match else "01"
        
        # Extract anime name
        anime_name = clean_name
        if ep_match:
            anime_name = clean_name[:ep_match.start()].strip()
        
        # Clean anime name
        anime_name = re.sub(
            r'\b(480p|720p|1080p|HD|FHD|WEB[- ]?DL|BluRay|HEVC|10bit)\b',
            '', anime_name, flags=re.I
        ).strip()
        
        return {
            'AnimeName': anime_name,
            'Sn': f"S{season.zfill(2)}",
            'Ep': episode.zfill(2),
            'Quality': quality,
            'Language': DEFAULT_LANGUAGE,
            'PoweredBy': POWERED_BY
        }
    except Exception as e:
        logger.error(f"Parse error in {filename}: {e}")
        return None

@app.on_message(filters.channel & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    try:
        file_name = message.document.file_name if message.document else message.video.file_name
        if not file_name:
            return

        # Parse metadata
        metadata = parse_filename(file_name)
        if not metadata:
            return

        # Get caption template
        caption_template = bot_data["channel_captions"].get(
            message.chat.id,
            bot_data["default_caption"]
        )

        # Format caption
        caption = caption_template.format(**metadata)
        
        # Delete original and repost
        await message.delete()
        if message.document:
            await message.reply_document(
                message.document.file_id,
                caption=caption
            )
        else:
            await message.reply_video(
                message.video.file_id,
                caption=caption
            )
            
        logger.info(f"Processed: {file_name}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

# ===== MAIN =====
if __name__ == '__main__':
    logger.info("Starting bot...")
    app.run()
