from pyrogram import filters
from pyrogram.types import Message
from anony import app

# 1. Enter your Telegram User ID here
ADMIN_ID = 8998520545  # <--- Put your ID here

# 2. Enter your Bot's Logger Group ID here (The private group where you type messages)
LOGGER_GROUP_ID = -1004430211910  


# --- Method 1: Smart Logger Group Controller ---
@app.on_message(filters.text & filters.chat(LOGGER_GROUP_ID))
async def smart_logger_handler(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text.strip()
    if not text:
        return
    
    # 1. Broadcast to all groups at once (Type as: "all / your message")
    if text.lower().startswith("all /"):
        actual_message = text[5:].strip()
        if not actual_message:
            return
        
        success_count = 0
        async for dialog in client.get_dialogs():
            if dialog.chat.type in ["group", "supergroup"]:
                try:
                    await client.send_message(chat_id=dialog.chat.id, text=actual_message)
                    success_count += 1
                except Exception:
                    pass
        
        await message.reply_text(f"✅ Success! The bot sent the message to {success_count} groups.")
        return

    # 2. Send to a specific group only (Type as: "group_id / your message")
    if "/" in text:
        try:
            target_id_str, actual_message = text.split("/", 1)
            target_group_id = int(target_id_str.strip())
            text_to_send = actual_message.strip()
            
            await client.send_message(chat_id=target_group_id, text=text_to_send)
            await message.react("👍")
        except Exception as e:
            print(f"Single Group Error: {e}")


# --- Method 2: Triggering via '!' and Replying in Target Groups ---
@app.on_message(filters.text & ~filters.private & filters.regex(r"^!"))
async def reply_as_bot(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text_to_send = message.text[1:].strip()
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
