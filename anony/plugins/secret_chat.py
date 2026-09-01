from pyrogram import filters
from pyrogram.types import Message
from anony import app

# 1. Enter your Telegram User ID here
ADMIN_ID = 8998520545  # <--- Put your ID here

# 2. Enter your Bot's Logger Group ID here
LOGGER_GROUP_ID = -1004430211910  


# --- Method 1: Dynamic Logger (Username, Link, ID support & 👍 Reaction) ---
@app.on_message(filters.text & filters.chat(LOGGER_GROUP_ID))
async def send_to_group_dynamic(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text.strip()
    if not text:
        return
    
    if "/" in text:
        try:
            target_part, actual_message = text.split("/", 1)
            target_raw = target_part.strip()
            text_to_send = actual_message.strip()
            
            if not text_to_send:
                return
            
            # Parse target as a Link, Username, or ID
            if target_raw.startswith("https://t.me/"):
                target = target_raw.replace("https://t.me/", "").strip("@/")
            elif target_raw.startswith("t.me/"):
                target = target_raw.replace("t.me/", "").strip("@/")
            elif target_raw.lstrip("-").isdigit():
                target = int(target_raw)  # If it's a numeric group ID
            else:
                target = target_raw if target_raw.startswith("@") else f"@{target_raw}"  # If it's a username
            
            # Send the message to the target group
            await client.send_message(chat_id=target, text=text_to_send)
            
            # React with a thumbs up if successful
            await message.react("👍")
            
        except Exception as e:
            print(f"Logger Error: {e}")
            await message.reply_text(f"❌ Error: {e}")


# --- Method 2: Triggering via Command (!s / .s) ---
@app.on_message(filters.command(["s", "secret"], prefixes=["!", "."]) & ~filters.private)
async def reply_as_bot_command(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Extract the message text after the command (e.g., !s Hello everyone)
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
