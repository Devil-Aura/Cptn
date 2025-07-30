from pyrogram import Client, filters
from pyrogram.types import Message
import re

# ================== BOT CONFIG ==================
API_ID = 22768311            # Replace with your API ID
API_HASH = "702d8884f48b42e865425391432b3794" # Replace with your API HASH
BOT_TOKEN = ""  # Replace with your BOT TOKEN

# ================== DEFAULT CAPTION ==================
default_caption = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# In-memory storage for captions (resets on restart)
channel_captions = {}

# ================== BOT APP ==================
app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# ================== COMMANDS ==================

# /start (private)
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text("I am a private bot of @World_Fastest_Bots")


# /help1 (private)
@app.on_message(filters.command("help1") & filters.private)
async def help_cmd(_, message: Message):
    help_text = ("/setcaption - Set custom caption (Use in channel)\n"
                 "/showcaption - Show current caption\n"
                 "➜ Add me as admin in your channel with 'Post Messages' & 'Delete Messages' permission.")
    await message.reply_text(help_text)


# /setcaption (channel)
@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setcaption Your_Custom_Caption_With_Placeholders")

    custom_caption = message.text.split(" ", 1)[1]
    channel_captions[message.chat.id] = custom_caption
    await message.reply_text("✅ Custom caption set successfully (will reset on restart)!")


# /showcaption (channel)
@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    current_caption = channel_captions.get(message.chat.id, default_caption)
    await message.reply_text(f"**Current Caption Template:**\n\n{current_caption}")


# ================== AUTO CAPTION HANDLER ==================
@app.on_message(filters.channel & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    file_name = message.document.file_name if message.document else message.video.file_name

    # 1️⃣ Remove starting tags like [@ChannelName]
    clean_name = re.sub(r'^\[.*?\]\s*', '', file_name)

    # 2️⃣ Improved regex for extracting details
    match = re.search(
        r"(.+?)\s*(S\d+)?(E\d+)?\s*.*?(\d{3,4}p|x265|x264)?",
        clean_name,
        re.IGNORECASE
    )

    if not match:
        return

    AnimeName, Sn, Ep, Quality = match.groups()

    # Defaults if missing
    AnimeName = AnimeName.strip()
    Sn = Sn.upper() if Sn else "S01"
    Ep = Ep.replace("E", "") if Ep else "01"
    Quality = Quality if Quality else "Unknown"

    # Replace 360p → 480p
    Quality = Quality.replace("360p", "480p")

    # Select custom caption if set
    caption_template = channel_captions.get(message.chat.id, default_caption)

    caption_text = caption_template.format(
        AnimeName=AnimeName,
        Sn=Sn,
        Ep=Ep,
        Quality=Quality
    )

    # Repost with caption and delete original
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

        await message.delete()
    except Exception as e:
        await message.reply_text(f"❌ Error sending file: {e}")


# ================== RUN BOT ==================
app.run()
