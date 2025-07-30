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

# In-Memory Storage for Custom Captions
group_captions = {}

app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# START
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text("I am a private bot of @World_Fastest_Bots")

# HELP
@app.on_message(filters.command("help1"))
async def help_cmd(_, message: Message):
    help_text = ("/setcaption - Custom caption\n"
                 "/showcaption - Show current caption\n"
                 "/addgroup - Add the bot in group and send /addgroup in that group")
    await message.reply_text(help_text)

# SET CUSTOM CAPTION
@app.on_message(filters.command("setcaption") & filters.group)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setcaption Your_Custom_Caption_With_Placeholders")

    custom_caption = message.text.split(" ", 1)[1]
    group_captions[message.chat.id] = custom_caption
    await message.reply_text("✅ Custom caption set successfully (will reset on restart)!")

# SHOW CURRENT CAPTION
@app.on_message(filters.command("showcaption") & filters.group)
async def show_caption(_, message: Message):
    current_caption = group_captions.get(message.chat.id, default_caption)
    await message.reply_text(f"**Current Caption Template:**\n\n{current_caption}")

# AUTO CAPTION
@app.on_message(filters.group & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    file_name = message.document.file_name if message.document else message.video.file_name

    # Extract details using regex
    match = re.search(r"(?:\[.*?\]\s*)?(.+?)\s(S\d+)(E\d+).*?(\d{3,4}p)", file_name, re.IGNORECASE)
    if not match:
        return

    AnimeName, Sn, Ep, Quality = match.groups()
    Ep = Ep.replace("E", "")

    # Check if custom caption exists for this group
    caption_template = group_captions.get(message.chat.id, default_caption)

    # Format the caption
    caption_text = caption_template.format(
        AnimeName=AnimeName.strip(),
        Sn=Sn.upper(),
        Ep=Ep,
        Quality=Quality
    )

    try:
        await message.edit_caption(caption_text)
    except:
        await message.reply_text("❌ I don't have permission to edit captions. Please give me 'Edit Messages' permission.")

app.run()
