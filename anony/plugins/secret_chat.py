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


# --- Smart Recursive Mapping Finder (Survives Restarts for Old Messages) ---
async def find_mapping_recursive(client, msg: Message):
    current = msg
    for _ in range(12):  # Trace back up to 12 replies deep
        if not current:
            break
        
        # 1. Check in RAM dictionary
        if current.id in LOGGER_REPLY_MAP:
            return LOGGER_REPLY_MAP[current.id]
        
        # 2. Extract from current message text if header is present
        if current.text:
            chat_match = re.search(r"(-100\d+|\-\d+)", current.text)
            msg_match = re.search(r"Msg ID:\s*`?(\d+)`?", current.text)
            if chat_match and msg_match:
                return {
                    "chat_id": int(chat_match.group(1)),
                    "user_msg_id": int(msg_match.group(1)),
                    "bot_msg_id": None
                }
        
        # 3. Fallback for forwarded messages after restart: Check adjacent alert header (id - 1)
        try:
            prev_msg = await client.get_messages(current.chat.id, current.id - 1)
            if prev_msg and prev_msg.text:
                chat_match = re.search(r"(-100\d+|\-\d+)", prev_msg.text)
                msg_match = re.search(r"Msg ID:\s*`?(\d+)`?", prev_msg.text)
                if chat_match and msg_match:
                    return {
                        "chat_id": int(chat_match.group(1)),
                        "user_msg_id": int(msg_match.group(1)),
                        "bot_msg_id": None
                    }
        except Exception:
            pass

        # 4. Fallback check for adjacent message (id + 1)
        try:
            next_msg = await client.get_messages(current.chat.id, current.id + 1)
            if next_msg and next_msg.text:
                chat_match = re.search(r"(-100\d+|\-\d+)", next_msg.text)
                msg_match = re.search(r"Msg ID:\s*`?(\d+)`?", next_msg.text)
                if chat_match and msg_match:
                    return {
                        "chat_id": int(chat_match.group(1)),
                        "user_msg_id": int(msg_match.group(1)),
                        "bot_msg_id": None
                    }
        except Exception:
            pass

        # 5. Move up the Telegram reply chain
        if current.reply_to_message:
            current = current.reply_to_message
        elif current.reply_to_message_id:
            try:
                current = await client.get_messages(current.chat.id, current.reply_to_message_id)
            except Exception:
                break
        else:
            break

    return None


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
            
            map_data = {
                "chat_id": message.chat.id,
                "user_msg_id": message.id,
                "bot_msg_id": None
            }
            LOGGER_REPLY_MAP[forwarded.id] = map_data
            LOGGER_REPLY_MAP[alert_msg.id] = map_data
        except Exception as e:
            print(f"Interaction Forward Error: {e}")


# --- Feature: Handle Admin Reply in MSG_GRP_ID ---
@app.on_message(filters.chat(MSG_GRP_ID) & filters.reply, group=8)
async def handle_logger_reply(client, message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return

    if message.text and message.text.startswith(("/", "!", ".")):
        return

    map_data = await find_mapping_recursive(client, message.reply_to_message)
    
    if map_data and map_data.get("chat_id"):
        chat_id = map_data["chat_id"]
        user_msg_id = map_data.get("user_msg_id")
        
        try:
            if user_msg_id:
                sent_msg = await message.copy(chat_id=chat_id, reply_to_message_id=user_msg_id)
            else:
                sent_msg = await message.copy(chat_id=chat_id)
            
            # Record map data for nested replies/edits/deletes
            LOGGER_REPLY_MAP[message.id] = {
                "chat_id": chat_id,
                "user_msg_id": user_msg_id,
                "bot_msg_id": sent_msg.id
            }
            await message.react("👍")
        except Exception as e:
            await message.reply_text(f"❌ Failed to send reply to group: {e}")
    else:
        await message.reply_text("❌ Could not detect target group/message ID.")


# --- Feature: Edit Bot Messages directly from MSG_GRP_ID ---
@app.on_message(
    filters.chat(MSG_GRP_ID) & filters.command(["edit", "ed"], prefixes=["/", "!", "."])
)
async def edit_outbound_message(client, message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return
    
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to the message you want to edit!")
    
    map_data = await find_mapping_recursive(client, message.reply_to_message)
    
    if not map_data or not map_data.get("bot_msg_id"):
        return await message.reply_text("❌ You can only edit messages sent by the bot.")
    
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply_text("❌ Please provide the new text. Example: `/edit New text`")
    
    new_text = args[1].strip()
    try:
        await client.edit_message_text(
            chat_id=map_data["chat_id"],
            message_id=map_data["bot_msg_id"],
            text=new_text
        )
        await message.react("👍")
    except Exception as e:
        await message.reply_text(f"❌ Failed to edit: {e}")


# --- Feature: Delete Messages (Bot Msg or User Msg) directly from MSG_GRP_ID ---
@app.on_message(
    filters.chat(MSG_GRP_ID) & filters.command(["del", "delete", "remove"], prefixes=["/", "!", "."])
)
async def delete_outbound_message(client, message: Message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return
    
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to the message you want to delete!")
    
    map_data = await find_mapping_recursive(client, message.reply_to_message)
    
    if not map_data or not map_data.get("chat_id"):
        return await message.reply_text("❌ Could not find the target group for deletion.")
    
    # Priority: bot_msg_id first (if replying to admin response), fallback to user_msg_id
    target_msg_id = map_data.get("bot_msg_id") or map_data.get("user_msg_id")
    
    if not target_msg_id:
        return await message.reply_text("❌ Could not find the target message ID for deletion.")
    
    try:
        await client.delete_messages(
            chat_id=map_data["chat_id"],
            message_ids=target_msg_id
        )
        await message.react("👍")
    except Exception as e:
        await message.reply_text(f"❌ Failed to delete: {e}")


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

    keyboard = [[InlineKeyboardButton("📢 Send All Groups", callback_data="trigger_send_all")]]

    for chat in chats:
        chat_id = chat.get("chat_id") if isinstance(chat, dict) else chat
        try:
            chat_info = await client.get_chat(chat_id)
            keyboard.append([InlineKeyboardButton(chat_info.title, callback_data=f"select_chat_{chat_id}")])
        except Exception:
            continue

    await message.reply_text("📋 **Select a group or broadcast:**", reply_markup=InlineKeyboardMarkup(keyboard))


# --- Handle Private Callbacks & Broadcast ---
@app.on_callback_query(filters.regex("^(select_chat_|trigger_send_all)"))
async def chat_selection_callback(client, callback_query: CallbackQuery):
    if not callback_query.from_user or callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("Unauthorized!", show_alert=True)

    user_id = callback_query.from_user.id

    if callback_query.data == "trigger_send_all":
        BROADCAST_MODES.add(user_id)
        SELECTED_CHATS.pop(user_id, None)
        await callback_query.message.edit_text("📢 **Broadcast Mode Active!** Send your message now.")
        return await callback_query.answer()

    chat_id = int(callback_query.data.split("_")[2])
    SELECTED_CHATS[user_id] = chat_id
    BROADCAST_MODES.discard(user_id)

    try:
        chat_info = await client.get_chat(chat_id)
        chat_name = chat_info.title
    except Exception:
        chat_name = str(chat_id)

    await callback_query.message.edit_text(f"✅ Selected: **{chat_name}** (`{chat_id}`). Send your message now!")
    await callback_query.answer()


@app.on_message(filters.private & ~filters.command(["chats", "chat", "start", "help"]))
async def handle_admin_private_messages(client, message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return

    if user_id in BROADCAST_MODES:
        BROADCAST_MODES.remove(user_id)
        chats = await db.get_served_chats() if hasattr(db, "get_served_chats") else await db.get_chats()
        sent_count = 0
        status_msg = await message.reply_text("🚀 Broadcasting...")
        for chat in chats:
            cid = chat.get("chat_id") if isinstance(chat, dict) else chat
            try:
                await message.copy(cid)
                sent_count += 1
                await asyncio.sleep(0.2)
            except Exception:
                continue
        return await status_msg.edit_text(f"✅ Broadcast complete: Sent to **{sent_count}** groups.")

    if user_id in SELECTED_CHATS:
        chat_id = SELECTED_CHATS.pop(user_id)
        try:
            await message.copy(chat_id)
            await message.reply_text("✅ Sent successfully to the group!")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")
