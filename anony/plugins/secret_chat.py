from pyrogram import filters
from pyrogram.types import Message
from anony import app

# Replace this with your actual Telegram User ID
ADMIN_ID = 8998520545  # <--- Put your ID here

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
        print(f"Error: {e}")
