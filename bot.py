from pyrogram import Client, filters
from pyrogram.types import Message
import re

# BOT CONFIG
API_ID = 22768311
API_HASH = "702d8884f48b42e865425391432b3794"
BOT_TOKEN = ""

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

# START COMMAND (only works in private)
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text("I am a private bot of @World_Fastest_Bots")

# HELP COMMAND (only works in private)
@app.on_message(filters.command("help1") & filters.private)
async def help_cmd(_, message: Message):
    help_text = ("/setcaption - Set custom caption (Use in channel)\n"
                 "/showcaption - Show current caption\n"
                 "➜ Add me as admin in your channel with 'Post Messages' permission.")
    await message.reply_text(help_text)

# SET CUSTOM CAPTION (only works when sent by channel creator/admin)
@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setcaption Your_Custom_Caption_With_Placeholders")

    custom_caption = message.text.split(" ", 1)[1]
    channel_captions[message.chat.id] = custom_caption
    await message.reply_text("✅ Custom caption set successfully (will reset on restart)!")

# SHOW CURRENT CAPTION
@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    current_caption = channel_captions.get(message.chat.id, default_caption)
    await message.reply_text(f"**Current Caption Template:**\n\n{current_caption}")

# AUTO CAPTION (works only in channels)
@app.on_message(filters.channel & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    file_name = message.document.file_name if message.document else message.video.file_name

    # Extract details using regex
    match = re.search(r"(?:\[.*?\]\s*)?(.+?)\s(S\d+)(E\d+).*?(\d{3,4}p)", file_name, re.IGNORECASE)
    if not match:
        return

    AnimeName, Sn, Ep, Quality = match.groups()
    Ep = Ep.replace("E", "")

    # Get custom caption or default
    caption_template = channel_captions.get(message.chat.id, default_caption)

    caption_text = caption_template.format(
        AnimeName=AnimeName.strip(),
        Sn=Sn.upper(),
        Ep=Ep,
        Quality=Quality
    )

    # Repost the file with the caption (and delete original)
    try:
        if message.document:
            await app.send_document(
                chat_id=message.chat.id,
                document=message.document.file_id,
                caption=caption_text
            )
        else:
            await app.send_video(
                chat_id=message.chat.id,
                video=message.video.file_id,
                caption=caption_text
            )

        await message.delete()  # Delete the original message
    except Exception as e:
        await message.reply_text(f"❌ Error sending file: {e}")

app.run()
