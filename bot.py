from pyrogram import Client, filters
from pyrogram.types import Message
import re
import json
import os
from html import escape

# BOT CONFIG
API_ID = 22768311
API_HASH = "702d8884f48b42e865425391432b3794"
BOT_TOKEN = ""
DATA_FILE = "anime_names.json"

# Default Caption Template
default_caption = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# In-Memory Storage for Custom Captions (per channel)
channel_captions = {}

app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Load anime names from file
def load_anime_names():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# Save anime names to file
def save_anime_names(names):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False, indent=2)

# START COMMAND
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text("I am a private bot of @World_Fastest_Bots")

# HELP COMMAND
@app.on_message(filters.command("help") & filters.private)
async def help_cmd(_, message: Message):
    help_text = ("<b>Available Commands:</b>\n\n"
                 "/setcaption - Set custom caption (Use in channel)\n"
                 "/showcaption - Show current caption\n"
                 "/addanime - Add anime to database\n"
                 "/deleteanime - Remove anime from database\n"
                 "/listanime - List all saved anime\n\n"
                 "➜ Add me as admin in your channel with 'Post Messages' permission.")
    await message.reply_text(help_text)

# ADD ANIME COMMAND
@app.on_message(filters.command("addanime") & filters.private)
async def add_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /addanime <Anime Name>")
    
    anime_names = load_anime_names()
    if name in anime_names:
        return await message.reply_text("⚠️ Anime already exists!")
    
    anime_names.append(name)
    save_anime_names(anime_names)
    await message.reply_text(f"✅ Added: {escape(name)}")

# DELETE ANIME COMMAND
@app.on_message(filters.command(["deleteanime", "delanime"]) & filters.private)
async def delete_anime(_, message: Message):
    try:
        name = message.text.split(None, 1)[1].strip()
    except IndexError:
        return await message.reply_text("Usage: /deleteanime <Anime Name>")
    
    anime_names = load_anime_names()
    try:
        anime_names.remove(name)
        save_anime_names(anime_names)
        await message.reply_text(f"🗑 Deleted: {escape(name)}")
    except ValueError:
        await message.reply_text("❌ Anime not found in database!")

# LIST ANIME COMMAND
@app.on_message(filters.command("listanime") & filters.private)
async def list_anime(_, message: Message):
    anime_names = load_anime_names()
    if not anime_names:
        return await message.reply_text("No anime in database yet!")
    
    text = "📚 Saved Anime:\n\n" + "\n".join(f"• {escape(name)}" for name in sorted(anime_names))
    # Split long messages to avoid Telegram's length limit
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part)
    else:
        await message.reply_text(text)

# SET CUSTOM CAPTION (Channel only)
@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setcaption Your_Custom_Caption_With_Placeholders")

    custom_caption = message.text.split(" ", 1)[1]
    channel_captions[message.chat.id] = custom_caption
    await message.reply_text("✅ Custom caption set successfully!")

# SHOW CURRENT CAPTION
@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    current_caption = channel_captions.get(message.chat.id, default_caption)
    await message.reply_text(f"<b>Current Caption Template:</b>\n\n{current_caption}")

# AUTO CAPTION (Channels only)
@app.on_message(filters.channel & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name
    else:
        return

    # Extract details using regex
    match = re.search(r"(?:\[.*?\]\s*)?(.+?)\s(S\d+)(E\d+).*?(\d{3,4}p)", file_name, re.IGNORECASE)
    if not match:
        return

    AnimeName, Sn, Ep, Quality = match.groups()
    Ep = Ep.replace("E", "")

    # Replace 360p with 480p in captions
    Quality = Quality.replace("360p", "480p")

    # Get custom caption or default
    caption_template = channel_captions.get(message.chat.id, default_caption)

    caption_text = caption_template.format(
        AnimeName=AnimeName.strip(),
        Sn=Sn.upper(),
        Ep=Ep,
        Quality=Quality
    )

    try:
        # Repost the file with the caption and delete original
        if message.document:
            await message.reply_document(
                document=message.document.file_id,
                caption=caption_text,
                parse_mode="HTML"
            )
        else:
            await message.reply_video(
                video=message.video.file_id,
                caption=caption_text,
                parse_mode="HTML"
            )

        await message.delete()
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

app.run()
