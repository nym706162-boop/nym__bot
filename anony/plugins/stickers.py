from pyrogram import filters
from pyrogram.types import Message

from anony import app, db


# Custom filter to check sudo users safely
async def sudo_filter(_, __, message: Message):
    return message.from_user and message.from_user.id in app.sudoers


@app.on_message(filters.command(["setsticker", "setpack"]) & filters.create(sudo_filter))
async def set_global_pack_cmd(client, message: Message):
    pack_name = None

    if message.reply_to_message and message.reply_to_message.sticker:
        pack_name = message.reply_to_message.sticker.set_name

    elif len(message.command) > 1:
        raw_input = message.command[1].strip()
        if "t.me/addstickers/" in raw_input:
            pack_name = raw_input.split("t.me/addstickers/")[1].split()[0]
        else:
            pack_name = raw_input

    if not pack_name:
        return await message.reply_text(
            "👉 **Usage:** Reply to a sticker OR use `/setsticker <pack_name_or_link>`"
        )

    await db.set_sticker_pack("GLOBAL_STICKER_PACK", pack_name)
    await message.reply_text(
        f"✅ **Global Sticker Pack set for all groups:** <code>{pack_name}</code>"
    )
