from pyrogram import Client, filters
from pyrogram.types import Message
import re
import difflib

# BOT CONFIG
API_ID = 22768311  # 🔁 Replace with your API_ID
API_HASH = "702d8884f48b42e865425391432b3794"  # 🔁 Replace with your API_HASH
BOT_TOKEN = ""  # 🔁 Replace with your BOT_TOKEN

# Default Caption Template
default_caption = """<b>➥ {AnimeName} [{Sn}]
🎬 Episode - {Ep}
🎧 Language - Hindi #Official
🔎 Quality : {Quality}
📡 Powered by :
@CrunchyRollChannel.</b>"""

# In-Memory Storage
channel_captions = {}  # channel-specific caption templates
anime_names = []       # global anime name list (resets on restart)

# Initialize Pyrogram Client
app = Client("AutoCaptionBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# START
@app.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply_text("👋 I am the fastest auto-caption bot by @World_Fastest_Bots!")


# HELP
@app.on_message(filters.command("help1"))
async def help_cmd(_, message: Message):
    help_text = (
        "**Available Commands:**\n\n"
        "/setcaption <caption> – Set custom caption (Use in channel)\n"
        "/showcaption – Show current caption\n"
        "/addanimename <Name> – Add an anime name\n"
        "/listanimename – List all added anime names\n"
        "/deleteanimename <Name> – Delete a specific anime name\n\n"
        "⚙️ Use me in your channel as admin with 'Post Messages' permission!"
    )
    await message.reply_text(help_text)


# SET CUSTOM CAPTION (Channel Only)
@app.on_message(filters.command("setcaption") & filters.channel)
async def set_caption(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage:\n/setcaption <Your Custom Caption>")

    custom_caption = message.text.split(" ", 1)[1]
    channel_captions[message.chat.id] = custom_caption
    await message.reply_text("✅ Custom caption set for this channel!")


# SHOW CURRENT CAPTION
@app.on_message(filters.command("showcaption") & filters.channel)
async def show_caption(_, message: Message):
    current_caption = channel_captions.get(message.chat.id, default_caption)
    await message.reply_text(f"**Current Caption Template:**\n\n{current_caption}")


# ADD ANIME NAME
@app.on_message(filters.command("addanimename"))
async def add_anime_name(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage:\n/addanimename <Anime Name>")

    anime_name = message.text.split(" ", 1)[1].strip()

    if anime_name in anime_names:
        return await message.reply_text("⚠️ Anime name already exists.")

    anime_names.append(anime_name)
    await message.reply_text(f"✅ Added anime name: `{anime_name}`")


# LIST ANIME NAMES
@app.on_message(filters.command("listanimename"))
async def list_anime_names(_, message: Message):
    if not anime_names:
        return await message.reply_text("📭 No anime names added yet.")

    reply_text = "**📺 Stored Anime Names:**\n\n"
    reply_text += "\n".join(f"{i+1}. {name}" for i, name in enumerate(anime_names))
    await message.reply_text(reply_text)


# DELETE ANIME NAME
@app.on_message(filters.command("deleteanimename"))
async def delete_anime_name(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage:\n/deleteanimename <Anime Name>")

    anime_name = message.text.split(" ", 1)[1].strip()

    if anime_name not in anime_names:
        return await message.reply_text("❌ Anime name not found.")

    anime_names.remove(anime_name)
    await message.reply_text(f"✅ Deleted anime name: `{anime_name}`")


# AUTO CAPTION ON FILE UPLOAD
@app.on_message(filters.channel & (filters.video | filters.document))
async def auto_caption(_, message: Message):
    file_name = None
    if message.document and message.document.file_name:
        file_name = message.document.file_name
    elif message.video and message.video.file_name:
        file_name = message.video.file_name

    if not file_name:
        return  # skip if no filename found

    # Try extracting: Name S01E05 720p
    match = re.search(r"(?:\[.*?\]\s*)?(.+?)\s(S\d+)(E\d+).*?(\d{3,4}p)", file_name, re.IGNORECASE)
    if not match:
        return  # filename doesn't match expected format

    raw_name, Sn, Ep, Quality = match.groups()
    Ep = Ep.replace("E", "")
    Quality = Quality.replace("360p", "480p")
    AnimeName = raw_name.strip()

    # Match against stored anime names
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
        await message.reply_text(f"❌ Error: {e}")


# Run the Bot
app.run()
