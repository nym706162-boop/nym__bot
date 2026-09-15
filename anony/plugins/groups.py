from pyrogram import filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from anony import app, config, db, userbot


# Check if user is Owner, Additional Admin, or Sudoer
def is_bot_admin(user_id: int) -> bool:
    # 1. Check OWNER_ID
    owner_id = getattr(config, "OWNER_ID", None)
    if isinstance(owner_id, (list, set, tuple)) and user_id in owner_id:
        return True
    elif user_id == owner_id:
        return True

    # 2. Check ADDITIONAL_ADMINS
    add_admins = getattr(config, "ADDITIONAL_ADMINS", [])
    if isinstance(add_admins, (list, set, tuple)) and user_id in add_admins:
        return True
    elif user_id == add_admins:
        return True

    # 3. Check App Sudoers
    if hasattr(app, "sudoers") and user_id in app.sudoers:
        return True

    return False


async def get_all_served_chats():
    chat_ids = set()

    # Method 1: Fetch from MongoDB directly
    try:
        mongo_db = getattr(db, "db", db)
        cols = await mongo_db.list_collection_names()
        for col_name in ["served_chats", "chats", "servedchats", "group_chats"]:
            if col_name in cols:
                async for doc in mongo_db[col_name].find():
                    cid = doc.get("chat_id") or doc.get("_id") or doc.get("chat")
                    if isinstance(cid, int) and cid < 0:
                        chat_ids.add(cid)
    except Exception:
        pass

    # Method 2: Fallback to Userbot Dialogs (Userbot can fetch dialogs)
    if not chat_ids and userbot:
        try:
            async for dialog in userbot.get_dialogs(limit=100):
                chat_type = str(dialog.chat.type).lower()
                if "group" in chat_type or "supergroup" in chat_type:
                    chat_ids.add(dialog.chat.id)
        except Exception:
            pass

    return list(chat_ids)


@app.on_message(filters.command(["groups", "servedchats", "chatlist"]))
async def list_groups_handler(_, message: types.Message):
    if not is_bot_admin(message.from_user.id):
        return await message.reply_text(
            "⚠️ This command can only be used by the Bot Owner and Admins."
        )

    sent = await message.reply_text("🔎 Fetching group list...")

    chat_ids = await get_all_served_chats()
    if not chat_ids:
        return await sent.edit_text("❌ The bot is not currently in any group.")

    buttons = []
    text = "<b>🤖 List of active groups:</b>\n\n"

    for count, chat_id in enumerate(chat_ids[:15], 1):
        try:
            chat_obj = await app.get_chat(chat_id)
            title = chat_obj.title
        except Exception:
            title = f"Group ({chat_id})"

        text += f"<b>{count}.</b> {title}\n"

        buttons.append([
            InlineKeyboardButton(
                text=f"❌ Leave: {title[:20]}",
                callback_data=f"leave_grp_{chat_id}",
            )
        ])

    reply_markup = InlineKeyboardMarkup(buttons)
    await sent.edit_text(text, reply_markup=reply_markup)


@app.on_callback_query(filters.regex(r"^leave_grp_(-?\d+)"))
async def leave_group_callback(_, query: types.CallbackQuery):
    if not is_bot_admin(query.from_user.id):
        return await query.answer(
            "⚠️ You are not authorized to perform this action.", show_alert=True
        )

    chat_id = int(query.data.split("_")[2])

    try:
        # Leave from both Bot and Userbot
        await app.leave_chat(chat_id)
        try:
            await userbot.leave_chat(chat_id)
        except Exception:
            pass

        # Cleanup from DB
        try:
            mongo_db = getattr(db, "db", db)
            cols = await mongo_db.list_collection_names()
            for col_name in ["served_chats", "chats", "servedchats"]:
                if col_name in cols:
                    await mongo_db[col_name].delete_many(
                        {"$or": [{"chat_id": chat_id}, {"_id": chat_id}]}
                    )
        except Exception:
            pass

        await query.answer(
            "✅ Bot successfully left the group!", show_alert=True
        )
        await query.message.edit_text(
            f"✅ Bot successfully left Group ID: <code>{chat_id}</code>"
        )
    except Exception as err:
        await query.answer(
            f"❌ Failed to leave group: {err}", show_alert=True
        )
