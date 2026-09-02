# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import random
from pathlib import Path

from pyrogram import filters, types

from anony import anon, app, config, db, lang, queue, tg, yt
from anony.helpers import buttons, utils
from anony.helpers._play import checkUB

# ── [ Sticker Pack Management Variables ] ──
CURRENT_STICKER_PACK = "AnimalsAnimated"

# Sudo කෙනෙකුට ටෙලිග්‍රෑම් එකෙන්ම ස්ටිකර් පැක් එක වෙනස් කිරීමට කමාන්ඩ් එක
@app.on_message(filters.command("setsticker") & filters.user(app.sudoers))
async def set_sticker_pack(_, message: types.Message):
    global CURRENT_STICKER_PACK
    if len(message.command) < 2:
        return await message.reply_text(
            f"⚡ **Current Sticker Pack:** `{CURRENT_STICKER_PACK}`\n\n"
            f"👉 **Usage:** `/setsticker <pack_name>`\n"
            f"(උදාහරණයක් ලෙස: `/setsticker AnimatedCats`)"
        )
    
    pack_name = message.command[1]
    try:
        st_set = await app.get_sticker_set(pack_name)
        if st_set:
            CURRENT_STICKER_PACK = pack_name
            await message.reply_text(f"✅ **Sticker pack successfully updated to:** `{pack_name}`")
        else:
            await message.reply_text("❌ එහෙම ස්ටිකර් පැක් එකක් හොයාගන්න නැහැ! නැවත පරීක්ෂා කරන්න.")
    except Exception as e:
        await message.reply_text(f"❌ Error: `{e}`")


def playlist_to_queue(chat_id: int, tracks: list) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {track.title}\n"
    text = text[:1948] + "</blockquote>"
    return text

@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    sent = await m.reply_text(m.lang["play_searching"])
    
    # ── [ Random Sticker Sender Feature ] ──
    try:
        global CURRENT_STICKER_PACK
        st_set = await app.get_sticker_set(CURRENT_STICKER_PACK)
        if st_set and st_set.stickers:
            random_sticker = random.choice(st_set.stickers)
            await app.send_sticker(chat_id=m.chat.id, sticker=random_sticker.file_id)
    except Exception:
        pass
    # ───────────────────────────────────────

    file = None
    mention = m.from_user.mention
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []

    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    elif m3u8:
        file = await tg.process_m3u8(url, sent.id, video)

    elif url:
        if "playlist" in url:
            await sent.edit_text(m.lang["playlist_fetch"])
            tracks = await yt.playlist(
                config.PLAYLIST_LIMIT, mention, url, video
            )

            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        else:
            file = await yt.search(url, sent.id, video=video)

        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        file = await yt.search(query, sent.id, video=video)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, sent.link, file.title, file.duration)

    file.user = mention
    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            # Cyberpunk Custom Layout for Queued Tracks
            cyber_queued_text = (
                f"🎶 **{config.MUSIC_BOT_NAME} TRACK QUEUED** ⚡\n\n"
                f"┏ 🔢 **Position:** `{position}`\n"
                f"┣ 🎧 **Track:** `{file.title}`\n"
                f"┣ ⏱️ **Duration:** `{file.duration}`\n"
                f"┣ 👤 **Requested By:** {m.from_user.mention}\n"
                f"┗ 🌐 **Source:** [YouTube]({file.url})"
            )
            await sent.edit_text(
                text=cyber_queued_text,
                reply_markup=buttons.play_queued(
                    m.chat.id, file.id, m.lang["play_now"]
                ),
                disable_web_page_preview=True,
            )
            if tracks:
                added = playlist_to_queue(m.chat.id, tracks)
                await app.send_message(
                    chat_id=m.chat.id,
                    text=m.lang["playlist_queued"].format(len(tracks)) + added,
                )
            return

    if not file.file_path:
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
        else:
            await sent.edit_text(m.lang["play_downloading"])
            file.file_path = await yt.download(file.id, video=video)

    await anon.play_media(chat_id=m.chat.id, message=sent, media=file)
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
    )
