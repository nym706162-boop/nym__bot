# Copyright (c) 2026 by nym
# Licensed under the MIT License.
# This file is part of nym

import os
import asyncio
import re
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from anony import app, config, db

# --- Admin IDs List Setup ---
owner_id = getattr(config, "OWNER_ID", int(os.getenv("OWNER_ID", "0")))
if isinstance(owner_id, int):
    owner_id_list = [owner_id]
else:
    owner_id_list = [int(owner_id)]

additional_env = os.getenv("ADDITIONAL_ADMINS", "")
additional_admins = []
if additional_env:
    for aid in additional_env.split(","):
        aid = aid.strip()
        if aid.isdigit():
            additional_admins.append(int(aid))

ADMINS = list(set(owner_id_list + additional_admins))

MSG_GRP_ID = getattr(config, "MSG_GRP_ID", int(os.getenv("MSG_GRP_ID", "0")))

SELECTED_CHATS = {}
BROADCAST_MODES = set()
LOGGER_REPLY_MAP = {}


# --- Auto-track/Update chats when bot interacts in groups ---
@app.on_message(filters.group & ~filters.service, group=6)
async def auto_track_chats(client, message: Message):
    if not message.chat:
        return
    chat_id = message.chat.id
    try:
        if hasattr(db, "add_served_chat"):
            await db.add_served_chat(chat_id)
        elif hasattr(db, "add_chat"):
            await db.add_chat(chat_id)
    except Exception:
        pass


# --- Feature: Forward replies/mentions to MSG_GRP_ID only ---
@app.on_message(filters.group & ~filters.service, group=7)
async def forward_bot_interactions(client, message: Message):
    if not message.chat or not MSG_GRP_ID:
        return

    is_reply_to_bot = (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.is_self
    )
    is_mentioned = message.mentioned

    if is_reply_to_bot or is_mentioned:
        try:
            chat_title = message.chat.title
            user_name = message.from_user.first_name if message.from_user else "Unknown"
            user_id = message.from_user.id if message.from_user else 0

            alert_text = (
                f"🔔 **New Reply / Mention in Group!**\n\n"
                f"📌 **Group:** {chat_title}\n"
                f"🆔 **Group ID:** `{message.chat.id}`\n"
                f"💬 **Msg ID:** `{message.id}`\n"
                f"👤 **User:** {user_name} (`{user_id}`)"
            )
            
            alert_msg = await client.send_message(MSG_GRP_ID, alert_text)
            forwarded = await message.forward(MSG_GRP_ID)
            
            LOGGER_REPLY_MAP[forwarded.id] = (message.chat.id, message.id)
            LOGGER_REPLY_MAP[alert_msg.id] = (message.chat.id, message.id)
        except Exception as e:
            print(f"Interaction Forward Error: {e}")


# --- Feature: Handle Admin Reply in MSG_GRP_ID ---
@app.on_message(filters.reply, group=8)
async def handle_logger_reply(client, message: Message):
    if message.chat.id != MSG_GRP_ID:
        return

    if not message.from_user or message.from_user.id not in ADMINS:
        return

    if message.text and message.text.startswith(("/", "!", ".")):
        return

    replied_msg = message.reply_to_message
    replied_msg_id = replied_msg.id
    
    chat_id = None
    original_msg_id = None

    if replied_msg_id in LOGGER_REPLY_MAP:
        chat_id, original_msg_id = LOGGER_REPLY_MAP[replied_msg_id]
    
    if not chat_id and replied_msg.text:
        match = re.search(r"(-100\d+|\-\d+)", replied_msg.text)
        if match:
            chat_id = int(match.group(1))
        msg_match = re.search(r"Msg ID:\s*`?(\d+)`?", replied_msg.text)
        if msg_match:
            original_msg_id = int(msg_match.group(1))

    if not chat_id:
        try:
            prev_msg = await client.get_messages(MSG_GRP_ID, replied_msg_id - 1)
            if prev_msg and prev_msg.text:
                match = re.search(r"(-100\d+|\-\d+)", prev_msg.text)
                if match:
                    chat_id = int(match.group(1))
                msg_match = re.search(r"Msg ID:\s*`?(\d+)`?", prev_msg.text)
                if msg_match:
                    original_msg_id = int(msg_match.group(1))
        except Exception as e:
            print(f"Fallback fetch error: {e}")

    if chat_id:
        try:
            if original_msg_id:
                sent_msg = await message.copy(chat_id=chat_id, reply_to_message_id=original_msg_id)
            else:
                sent_msg = await message.copy(chat_id=chat_id)
            
            LOGGER_REPLY_MAP[message.id] = (chat_id, sent_msg.id)
            await message.react("👍")
        except Exception as e:
            await message.reply_text(f"❌ Failed to send reply to group: {e}")
    else:
        await message.reply_text("❌ Could not detect target group ID from this message.")


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
            "✍️ Now, send any message, sticker, photo, or video to broadcast to **ALL groups**."
        )
        return await callback_query.answer()

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
        "✍️ Now, send the message, sticker, or photo you want to send to this group!"
    )
    await callback_query.answer()


# --- Listen for ANY message in Private Chat ---
@app.on_message(filters.private & ~filters.command(["chats", "chat", "start", "help"]))
async def handle_admin_private_messages(client, message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return

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
        status_msg = await message.reply_text("🚀 Broadcasting to all groups...")

        for chat in chats:
            chat_id = chat.get("chat_id") if isinstance(chat, dict) else chat
            try:
                await message.copy(chat_id)
                sent_count += 1
                await asyncio.sleep(0.2)
            except Exception:
                continue

        await status_msg.edit_text(f"✅ **Broadcast Complete!**\nSuccessfully sent to **{sent_count}** groups.")
        return

    if user_id in SELECTED_CHATS:
        chat_id = SELECTED_CHATS.pop(user_id)
        try:
            await message.copy(chat_id)
            await message.reply_text("✅ **Sent successfully to the group!** 👍")
        except Exception as e:
            await message.reply_text(f"❌ Failed to send: {e}")


# --- Method 1: Dynamic Sender via MSG_GRP_ID (With Auto-Tracking for Edit/Del) ---
@app.on_message(filters.chat(MSG_GRP_ID) & filters.text)
async def send_to_group_dynamic(client, message: Message):
    if message.reply_to_message:  
        return

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

        sent_msg = await client.send_message(chat_id=target, text=text_to_send)
        LOGGER_REPLY_MAP[message.id] = (sent_msg.chat.id, sent_msg.id)
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


# --- Feature: Edit Messages directly from MSG_GRP_ID ---
@app.on_message(
    filters.chat(MSG_GRP_ID) & filters.command(["edit", "ed"], prefixes=["/", "!", "."])
)
async def edit_outbound_message(client, message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return
    
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to your sent reply message to edit!")
    
    orig_msg_id = message.reply_to_message.id
    if orig_msg_id not in LOGGER_REPLY_MAP:
        return await message.reply_text("❌ Could not find target message mapping.")
    
    target_chat_id, target_msg_id = LOGGER_REPLY_MAP[orig_msg_id]
    
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply_text("❌ Please provide the new text. Example: `/edit New text`")
    
    new_text = args[1].strip()
    try:
        await client.edit_message_text(
            chat_id=target_chat_id,
            message_id=target_msg_id,
            text=new_text
        )
        await message.react("👍")
    except Exception as e:
        await message.reply_text(f"❌ Failed to edit in target group: {e}")


# --- Feature: Delete Messages directly from MSG_GRP_ID ---
@app.on_message(
    filters.chat(MSG_GRP_ID) & filters.command(["del", "delete", "remove"], prefixes=["/", "!", "."])
)
async def delete_outbound_message(client, message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return
    
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to your sent reply message or forwarded message to delete!")
    
    orig_msg_id = message.reply_to_message.id
    if orig_msg_id not in LOGGER_REPLY_MAP:
        return await message.reply_text("❌ Could not find target message mapping.")
    
    target_chat_id, target_msg_id = LOGGER_REPLY_MAP[orig_msg_id]
    
    try:
        await client.delete_messages(
            chat_id=target_chat_id,
            message_ids=target_msg_id
        )
        await message.react("👍")
        del LOGGER_REPLY_MAP[orig_msg_id]
    except Exception as e:
        await message.reply_text(f"❌ Failed to delete in target group: {e}")
