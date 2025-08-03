from pyrogram import Client, filters
from pyrogram.types import Message
import os

API_ID = 22768311  # Replace with your own
API_HASH = "702d8884f48b42e865425391432b3794"
BOT_TOKEN = ""

app = Client("AnimeNameBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

ANIME_NAMES_FILE = "anime_names.txt"

def load_anime_names():
    if not os.path.exists(ANIME_NAMES_FILE):
        return []
    with open(ANIME_NAMES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def save_anime_names(names):
    with open(ANIME_NAMES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(names))

def add_anime_names(new_names):
    current_names = load_anime_names()
    for name in new_names:
        if name and name not in current_names:
            current_names.append(name)
    save_anime_names(current_names)
    return current_names

def delete_anime_name(name_to_delete):
    current_names = load_anime_names()
    updated = [name for name in current_names if name.lower() != name_to_delete.lower()]
    save_anime_names(updated)
    return updated

def match_anime_name(filename):
    anime_names = load_anime_names()
    filename_lower = filename.lower()
    best_match = ""
    max_length = 0
    for name in anime_names:
        cleaned = name.lower().replace("’", "'")
        if cleaned in filename_lower and len(cleaned) > max_length:
            best_match = name
            max_length = len(cleaned)
    return best_match if best_match else "Unknown"

@app.on_message(filters.command("adanimename") & filters.private)
async def add_names(client, message: Message):
    lines = message.text.split("\n")[1:]  # Remove command part
    if not lines:
        return await message.reply("❌ Please provide anime names after the command.")
    added = add_anime_names(lines)
    await message.reply(f"✅ Anime names added.\n\n📋 Total Saved Names:\n" + "\n".join(added))

@app.on_message(filters.command("delanimename") & filters.private)
async def delete_name(client, message: Message):
    try:
        name_to_delete = message.text.split(" ", 1)[1].strip()
    except IndexError:
        return await message.reply("❌ Usage: /delanimename <Anime Name>")
    
    updated = delete_anime_name(name_to_delete)
    await message.reply(f"✅ Deleted (if existed): `{name_to_delete}`\n\n📋 Updated List:\n" + "\n".join(updated))

@app.on_message(filters.command("matchanime") & filters.private)
async def match_command(client, message: Message):
    try:
        filename = message.text.split(" ", 1)[1].strip()
    except IndexError:
        return await message.reply("❌ Usage: /matchanime <File Name>")
    
    match = match_anime_name(filename)
    await message.reply(f"🎯 Matched Anime Name: `{match}`")

@app.on_message(filters.command("showanimenames") & filters.private)
async def show_all_names(client, message: Message):
    names = load_anime_names()
    if not names:
        return await message.reply("No anime names added yet.")
    await message.reply("📋 Saved Anime Names:\n" + "\n".join(names))

@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    await message.reply("👋 Hello! Use the following commands:\n\n"
                        "/adanimename - Add anime names (each in new line)\n"
                        "/delanimename <name> - Delete an anime name\n"
                        "/matchanime <file name> - Match file name to anime\n"
                        "/showanimenames - Show all saved anime names")

app.run()
