from pyrogram import filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from anony import app, config, db


# Fail-safe admin check (Handles both int and string IDs)
def is_bot_admin(user_id: int) -> bool:
    if not user_id:
        return False

    user_str = str(user_id)

    # 1. Check OWNER_ID
    owner_id = getattr(config, "OWNER_ID", None)
    if owner_id:
        if isinstance(owner_id, (list, set, tuple)):
            if user_id in owner_id or user_str in [str(x) for x in owner_id]:
                return True
        elif user_str == str(owner_id):
            return True

    # 2. Check ADDITIONAL_ADMINS
    add_admins = getattr(config, "ADDITIONAL_ADMINS", [])
    if add_admins:
        if isinstance(add_admins, (list, set, tuple)):
            if user_id in add_admins or user_str in [str(x) for x in add_admins]:
                return True
        elif user_str == str(add_admins):
            return True

    # 3. Check App Sudoers
    sudoers = getattr(app, "sudoers", set())
    if user_id in sudoers or user_str in [str(x) for x in sudoers]:
        return True

    return False


async def fetch_groups_safely():
    chat_ids = set()
    try:
        mongo_db = getattr(db, "db", db)
        for col_name in ["served_chats", "chats", "servedchats", "group_chats"]:
            try:
                collection = getattr(mongo_db, col_name, None)
                if collection is not None:
                    async for doc in collection.find():
                        cid = doc.get("chat_id") or doc.get("_id") or doc.get("chat")
                        if isinstance(cid, int) and cid < 0:
                            chat_ids.add(cid)
            except Exception:
                continue
    except Exception:
        pass
    return list(chat_ids)


@app.on_message(filters.command(["groups", "servedchats", "chatlist"]))
async def list_groups_handler(_, message: types.Message):
    if not message.from_user:
        return

    if not is_bot_admin(message.from_user.id):
        return await message.reply_text(
            "⚠️ This command can only be used by the Bot Owner and Admins."
        )

    sent = await message.reply_text("🔎 Fetching group list...")

    try:
        chat_ids = await fetch_groups_safely()
        if not chat_ids:
            return await sent.edit_text("❌ The bot is not currently in any group (Database is empty).")

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
    except Exception as e:
        await sent.edit_text(f"❌ Error: {e}")


@app.on_callback_query(filters.regex(r"^leave_grp_(-?\d+)"))
async def leave_group_callback(_, query: types.CallbackQuery):
    if not query.from_user or not is_bot_admin(query.from_user.id):
        return await query.answer(
            "⚠️ You are not authorized to perform this action.", show_alert=True
        )

    chat_id = int(query.data.split("_")[2])

    try:
        await app.leave_chat(chat_id)

        try:
            mongo_db = getattr(db, "db", db)
            for col_name in ["served_chats", "chats", "servedchats"]:
                collection = getattr(mongo_db, col_name, None)
                if collection is not None:
                    await collection.delete_many({"$or": [{"chat_id": chat_id}, {"_id": chat_id}]})
        except Exception:
            pass

        await query.answer("✅ Bot successfully left the group!", show_alert=True)
        await query.message.edit_text(
            f"✅ Bot successfully left Group ID: <code>{chat_id}</code>"
        )
    except Exception as err:
        await query.answer(
            f"❌ Failed to leave group: {err}", show_alert=True
        )
