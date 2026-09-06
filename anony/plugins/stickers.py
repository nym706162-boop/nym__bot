from pyrogram import filters
from pyrogram.types import Message
from anony import app, db


@app.on_message(filters.command(["setpack", "addpack"]) & ~filters.private)
async def set_pack_cmd(client, message: Message):
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
            "Reply to a sticker or provide a sticker pack link."
        )

    await db.set_sticker_pack(message.chat.id, pack_name)
    await message.reply_text(f"Sticker pack saved: {pack_name}")


@app.on_message(filters.command(["delpack", "rmpack"]) & ~filters.private)
async def del_pack_cmd(client, message: Message):
    await db.del_sticker_pack(message.chat.id)
    await message.reply_text("Sticker pack removed.")
