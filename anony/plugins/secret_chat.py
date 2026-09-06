import os
from pyrogram import filters
from pyrogram.types import Message
from anony import app, config

ADMIN_ID = getattr(config, "OWNER_ID", int(os.getenv("OWNER_ID", "0")))
LOGGER_GROUP_ID = getattr(config, "LOGGER_ID", int(os.getenv("LOGGER_ID", "0")))


# --- Method 1: Dynamic Logger via Channel/Group ---
@app.on_message(filters.chat(LOGGER_GROUP_ID) & filters.text)
async def send_to_group_dynamic(client, message: Message):
    if message.from_user and message.from_user.id != ADMIN_ID:
        return

    text = message.text.strip()
    if not text or "/" not in text:
        return

    try:
        target_part, actual_message = text.split("/", 1)
        target_raw = target_part.strip()
        text_to_send = actual_message.strip()

        if not text_to_send:
            return

        if target_raw.startswith("https://t.me/"):
            target = target_raw.replace("https://t.me/", "").strip("@/")
        elif target_raw.startswith("t.me/"):
            target = target_raw.replace("t.me/", "").strip("@/")
        elif target_raw.lstrip("-").isdigit():
            target = int(target_raw)
        else:
            target = target_raw if target_raw.startswith("@") else f"@{target_raw}"

        await client.send_message(chat_id=target, text=text_to_send)
        await message.react("👍")

    except Exception as e:
        print(f"Logger Error: {e}")
        await message.reply_text(f"❌ Error: {e}")


# --- Method 2: Triggering via Command (!s / .s in Groups) ---
@app.on_message(
    filters.command(["s", "secret"], prefixes=["!", "."]) & ~filters.private
)
async def reply_as_bot_command(client, message: Message):
    if message.from_user and message.from_user.id != ADMIN_ID:
        return

    text_to_send = message.text.split(None, 1)
    if len(text_to_send) < 2:
        return

    actual_text = text_to_send[1].strip()
    if not actual_text:
        return

    try:
        await message.delete()
        if message.reply_to_message:
            await message.reply_to_message.reply_text(actual_text)
        else:
            await message.reply_text(actual_text)
    except Exception as e:
        print(f"Command Trigger Error: {e}")
