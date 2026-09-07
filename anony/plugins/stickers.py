import random
import aiohttp
from pyrogram import filters
from pyrogram.types import Message
from anony import app, db, config

# Custom filter to check sudo users safely
async def sudo_filter(_, __, message: Message):
    return message.from_user and message.from_user.id in app.sudoers

@app.on_message(filters.command(["setsticker", "setpack"]) & filters.create(sudo_filter))
async def set_global_pack_cmd(client, message: Message):
    pack_name = None

    if message.reply_to_message and message.reply_to_message.sticker:
        pack_name = message.reply_to_message.sticker.set_name

    elif len(message.command) > 1:
        raw_input = message.command[1].strip()
        if "t.me/addstickers/" in raw_input:
            pack_name = raw_input.split("t.me/addstickers/")[1].split()[0]
        else:
            pack_name = raw_input

    if not pack_name:
        return await message.reply_text(
            "👉 **Usage:** Reply to a sticker OR use `/setsticker <pack_name_or_link>`"
        )

    await db.set_sticker_pack("GLOBAL_STICKER_PACK", pack_name)
    await message.reply_text(
        f"✅ **Global Sticker Pack set for all groups:** <code>{pack_name}</code>"
    )

# Function to fetch sticker pack using HTTP GET Request with Debug Logs
async def send_random_sticker(message: Message):
    print("DEBUG: ---> send_random_sticker function called successfully!")
    try:
        pack_name = "sanymaaa"
        
        if pack_name:
            url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getStickerSet?name={pack_name}"
            print(f"DEBUG: Requesting Telegram API URL: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    print(f"DEBUG: API Response Status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"DEBUG: API JSON Data ok: {data.get('ok')}")
                        if data.get("ok"):
                            stickers = data["result"]["set"]["stickers"]
                            if stickers:
                                random_sticker = random.choice(stickers)
                                print(f"DEBUG: Found {len(stickers)} stickers. Sending random sticker...")
                                await message.reply_sticker(random_sticker["file_id"])
                                return True

        # Fallback sticker
        fallback_sticker = "CAACAgIAAxkBA4oboGqeUVaHn8lD3WpSPjClVsBf4P30AAJqfAACU3FoS6q_wIFF9mmDPQQ"
        print("DEBUG: API fetch failed or empty. Sending fallback sticker...")
        await message.reply_sticker(fallback_sticker)
        return True

    except Exception as e:
        print(f"DEBUG EXCEPTION in send_random_sticker: {e}")
    return False
