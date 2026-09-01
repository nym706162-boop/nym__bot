from pyrogram import filters
from pyrogram.types import Message
from anony import app

# 1. Enter your Telegram User ID here
ADMIN_ID = 8998520545  # <--- Put your ID here

# 2. Enter your Bot's Logger Group ID here
LOGGER_GROUP_ID = -1004430211910  


# --- Method 1: Send to a Specific Group from Logger Group ---
@app.on_message(filters.text & filters.chat(LOGGER_GROUP_ID))
async def send_to_group(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text.strip()
    if not text:
        return
    
    if "/" in text:
        try:
            target_id_str, actual_message = text.split("/", 1)
            target_group_id = int(target_id_str.strip())
            text_to_send = actual_message.strip()
            
            await client.send_message(chat_id=target_group_id, text=text_to_send)
            await message.react("👍")
        except Exception as e:
            print(f"Logger Error: {e}")


# --- Method 2: Triggering via '!' (Safe Python Text Check) ---
@app.on_message(filters.text & ~filters.private)
async def reply_as_bot(client, message: Message):
    # Check if the sender is the admin
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text
    # Check if the message starts with '!'
    if not text or not text.startswith("!"):
        return
    
    text_to_send = text[1:].strip()
    if not text_to_send:
        return
    
    try:
        await message.delete()
        if message.reply_to_message:
            await message.reply_to_message.reply_text(text_to_send)
        else:
            await message.reply_text(text_to_send)
    except Exception as e:
        print(f"Trigger Error: {e}")
