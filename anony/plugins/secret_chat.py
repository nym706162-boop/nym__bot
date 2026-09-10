import os
import asyncio
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from anony import app, config, db

# --- Admin IDs List Setup ---
owner_id = getattr(config, "OWNER_ID", int(os.getenv("OWNER_ID", "0")))
if isinstance(owner_id, int):
    owner_id_list = [owner_id]
else:
    owner_id_list = [int(owner_id)]

# Read ADDITIONAL_ADMINS from the environment variables
additional_env = os.getenv("ADDITIONAL_ADMINS", "")
additional_admins = []
if additional_env:
    for aid in additional_env.split(","):
        aid = aid.strip()
        if aid.isdigit():
            additional_admins.append(int(aid))

# Combine all admin IDs
ADMINS = list(set(owner_id_list + additional_admins))

LOGGER_GROUP_ID = getattr(config, "LOGGER_ID", int(os.getenv("LOGGER_ID", "0")))

# Temporary storage to keep track of admin states
SELECTED_CHATS = {}
BROADCAST_MODES = set()


# --- Feature: List all chats and Send All button in Bot Private Chat ---
@app.on_message(filters.command(["chats", "chat"]) & filters.private)
async def list_chats_for_selection(client, message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return

    chats = []
    try:
        if hasattr(db, "get_served_chats"):
            chats = await db.get_served_chats()
        elif hasattr(db, "get_chats"):
            chats = await db.get_chats()
    except Exception as e:
        print(f"DB Fetch Error: {e}")

    if not chats:
        return await message.reply_text("❌ No groups found in the database.")

    # Top button for Send All
    keyboard = [
        [InlineKeyboardButton("📢 Send All Groups", callback_data="trigger_send_all")]
    ]

    for chat in chats:
        chat_id = chat.get("chat_id") if isinstance(chat, dict) else chat
        try:
            chat_info = await client.get_chat(chat_id)
            chat_title = chat_info.title
            keyboard.append(
                [InlineKeyboardButton(chat_title, callback_data=f"select_chat_{chat_id}")]
            )
        except Exception:
            continue

    await message.reply_text(
        "📋 **Select a group below or click 'Send All Groups':**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# --- Handle Callbacks (Single Chat or Broadcast All) ---
@app.on_callback_query(filters.regex("^(select_chat_|trigger_send_all)"))
async def chat_selection_callback(client, callback_query: CallbackQuery):
    if not callback_query.from_user or callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("You are not authorized!", show_alert=True)

    user_id = callback_query.from_user.id

    if callback_query.data == "trigger_send_all":
        BROADCAST_MODES.add(user_id)
        if user_id in SELECTED_CHATS:
            del SELECTED_CHATS[user_id]

        await callback_query.message.edit_text(
            "📢 **Broadcast Mode Activated!**\n\n"
            "✍️ Now, simply type and send the message you want to broadcast to **ALL groups**."
        )
        return await callback_query.answer()

    # If a specific chat is selected
    chat_id = int(callback_query.data.split("_")[2])
    SELECTED_CHATS[user_id] = chat_id
    if user_id in BROADCAST_MODES:
        BROADCAST_MODES.remove(user_id)

    try:
        chat_info = await client.get_chat(chat_id)
        chat_name = chat_info.title
    except Exception:
        chat_name = str(chat_id)

    await callback_query.message.edit_text(
        f"✅ Selected Group: **{chat_name}** (`{chat_id}`)\n\n"
        "✍️ Now, simply type and send the message you want to send to this group!"
    )
    await callback_query.answer()


# --- Listen for text messages in Private Chat after selection or broadcast trigger ---
@app.on_message(filters.private & ~filters.command(["chats", "chat", "start", "help"]))
async def handle_admin_private_messages(client, message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return

    text_to_send = message.text.strip()
    if not text_to_send:
        return await message.reply_text("❌ Please send a valid text message.")

    # 1. Handle Broadcast All Mode
    if user_id in BROADCAST_MODES:
        BROADCAST_MODES.remove(user_id)
        
        chats = []
        try:
            if hasattr(db, "get_served_chats"):
                chats = await db.get_served_chats()
            elif hasattr(db, "get_chats"):
                chats = await db.get_chats()
        except Exception as e:
            return await message.reply_text(f"❌ Database error: {e}")

        if not chats:
            return await message.reply_text("❌ No groups found in the database.")

        sent_count = 0
        status_msg = await message.reply_text("🚀 Broadcasting message to all groups...")

        for chat in chats:
            chat_id = chat.get("chat_id") if isinstance(chat, dict) else chat
            try:
                await client.send_message(chat_id=chat_id, text=text_to_send)
                sent_count += 1
                await asyncio.sleep(0.2)
            except Exception:
                continue

        await status_msg.edit_text(f"✅ **Broadcast Complete!**\nSuccessfully sent to **{sent_count}** groups.")
        return

    # 2. Handle Single Selected Chat Mode
    if user_id in SELECTED_CHATS:
        chat_id = SELECTED_CHATS.pop(user_id)
        try:
            await client.send_message(chat_id=chat_id, text=text_to_send)
            await message.reply_text("✅ **Message sent successfully to the group!** 👍")
        except Exception as e:
            await message.reply_text(f"❌ Failed to send message: {e}")


# --- Method 1: Dynamic Logger via Channel/Group ---
@app.on_message(filters.chat(LOGGER_GROUP_ID) & filters.text)
async def send_to_group_dynamic(client, message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
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
    if not message.from_user or message.from_user.id not in ADMINS:
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
