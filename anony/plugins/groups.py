from pyrogram import filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from anony import app, config
from anony.utils.database import get_served_chats, remove_served_chat


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


@app.on_message(filters.command(["groups", "servedchats", "chatlist"]))
async def list_groups_handler(_, message: types.Message):
    if not is_bot_admin(message.from_user.id):
        return await message.reply_text(
            "⚠️ This command can only be used by the Bot Owner and Admins."
        )

    sent = await message.reply_text("🔎 Fetching group list...")

    served_chats = await get_served_chats()
    if not served_chats:
        return await sent.edit_text("❌ The bot is not currently in any group.")

    buttons = []
    text = "<b>🤖 List of active groups:</b>\n\n"

    for count, chat in enumerate(served_chats, 1):
        chat_id = chat["chat_id"] if isinstance(chat, dict) else chat
        try:
            chat_obj = await app.get_chat(chat_id)
            title = chat_obj.title
        except Exception:
            title = f"Unknown Chat ({chat_id})"

        text += f"<b>{count}.</b> {title}\n"

        buttons.append([
            InlineKeyboardButton(
                text=f"❌ Leave: {title[:20]}",
                callback_data=f"leave_grp_{chat_id}",
            )
        ])

    reply_markup = InlineKeyboardMarkup(buttons[:15])
    await sent.edit_text(text, reply_markup=reply_markup)


@app.on_callback_query(filters.regex(r"^leave_grp_(-?\d+)"))
async def leave_group_callback(_, query: types.CallbackQuery):
    if not is_bot_admin(query.from_user.id):
        return await query.answer(
            "⚠️ You are not authorized to perform this action.", show_alert=True
        )

    chat_id = int(query.data.split("_")[2])

    try:
        await app.leave_chat(chat_id)
        await remove_served_chat(chat_id)

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
