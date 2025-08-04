from pyrogram import Client, filters
from pyrogram.types import Message
import re
import difflib

# BOT CONFIG
API_ID = 22768311  # replace with your actual API_ID
API_HASH = "702d8884f48b42e865425391432b3794"  # replace with your API_HASH
BOT_TOKEN = ""  # replace with your BOT_TOKEN

# Default Caption Template
default_caption = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# In-Memory Storage
channel_captions = {}  # for per-channel custom captions
anime_names = []       # global list of added anime names (resets on restart)

# Initialize Pyrogram Client
app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# START COMMAND
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message: Message):
    await message.reply_text("I am a private bot of @World_Fastest_Bots")


# HELP COMMAND
@app.on_message(filters.command("help1") & filters.private)
async def help_cmd(_, message: Message):
    help_text = (
        "**Available Commands:**\n\n"
        "/setcaption <caption> – Set custom caption (Use in channel)\n"
        "/showcaption – Show current caption\n"
        "/addanimename <Name> – Add an anime name\n"
        "/listanimename – List all added anime names\n"
        "/deleteanimename <Name> – Delete a specific anime name\n\n"
        "➜ Add me as admin in your channel with 'Post Messages' permission."
    )
    await message.reply_text(help_text)


# SET CUSTOM CAPTION (Channel Only)
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


# ADD ANIME NAME
@app.on_message(filters.command("addanimename") & filters.private)
async def add_anime_name(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /addanimename <Anime Name>")
    
    anime_name = message.text.split(" ", 1)[1].strip()
    
    if anime_name in anime_names:
        return await message.reply_text("❗ Anime name already exists.")
    
    anime_names.append(anime_name)
    await message.reply_text(f"✅ Anime name added: `{anime_name}`")


# LIST ANIME NAMES
@app.on_message(filters.command("listanimename") & filters.private)
async def list_anime_names(_, message: Message):
    if not anime_names:
        return await message.reply_text("No anime names added yet.")
    
    reply_text = "**📺 Stored Anime Names:**\n\n"
    reply_text += "\n".join(f"{i+1}. {name}" for i, name in enumerate(anime_names))
    await message.reply_text(reply_text)


# DELETE ANIME NAME
@app.on_message(filters.command("deleteanimename") & filters.private)
async def delete_anime_name(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /deleteanimename <Anime Name>")
    
    anime_name = message.text.split(" ", 1)[1].strip()
    
    if anime_name not in anime_names:
        return await message.reply_text("❌ Anime name not found.")
    
    anime_names.remove(anime_name)
    await message.reply_text(f"✅ Anime name deleted: `{anime_name}`")


# AUTO CAPTION HANDLER (Channels Only)
@app.on_message(filters.channel & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    file_name = message.document.file_name if message.document else message.video.file_name

    # Extract basic details using regex
    match = re.search(r"(?:\[.*?\]\s*)?(.+?)\s(S\d+)(E\d+).*?(\d{3,4}p)", file_name, re.IGNORECASE)
    if not match:
        return  # skip if not matched

    raw_name, Sn, Ep, Quality = match.groups()
    Ep = Ep.replace("E", "")
    Quality = Quality.replace("360p", "480p")
    AnimeName = raw_name.strip()

    # Fuzzy match with stored anime names
    def get_best_match(name, stored_list):
        best_ratio = 0
        best_match = None
        for stored_name in stored_list:
            ratio = difflib.SequenceMatcher(None, name.lower(), stored_name.lower()).ratio()
            if 0.5 <= ratio <= 0.8 and ratio > best_ratio:
                best_ratio = ratio
                best_match = stored_name
        return best_match

    matched_name = get_best_match(AnimeName, anime_names)
    if matched_name:
        AnimeName = matched_name

    # Use custom or default caption
    caption_template = channel_captions.get(message.chat.id, default_caption)

    caption_text = caption_template.format(
        AnimeName=AnimeName,
        Sn=Sn.upper(),
        Ep=Ep,
        Quality=Quality
    )

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


# RUN THE BOT
app.run()
