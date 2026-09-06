# Copyright (c) 2026 by nym
# Licensed under the MIT License.
# This file is part of nym

from pyrogram import filters
from pyrogram.types import Message

from anony import app, db, lang, yt, queue
from anony.core.calls import TgCall
from anony.helpers import Media, Track, utils

pytgcalls = TgCall()

@app.on_message(filters.command(["radio", "livestream"]))
async def radio_stream(_, message: Message):
    _lang = await lang.get_lang(message.chat.id)
    
    if len(message.command) < 2:
        return await message.reply_text(_lang.get("error_no_query", "Please provide a radio stream URL or name!"))

    query = message.text.split(None, 1)[1]
    chat_id = message.chat.id
    user = message.from_user.mention

    msg = await message.reply_text(_lang.get("processing", "Processing radio stream..."))

    is_direct = query.startswith("http") and not ("youtube.com" in query or "youtu.be" in query)
    
    if is_direct:
        media = Media(
            id=utils.generate_id(),
            title="Live Radio Stream",
            duration="Live",
            duration_sec=0,
            url=query,
            file_path=query,
            user=user,
            video=False,
        )
    else:
        track = await yt.search(query, message.id, video=False)
        if not track:
            return await msg.edit_text(_lang.get("error_no_result", "No live radio or stream found!"))
        
        stream_url = await yt.get_stream_url(track.id)
        if not stream_url:
            return await msg.edit_text(_lang.get("error_no_file", "Failed to fetch stream URL."))

        media = Media(
            id=track.id,
            title=track.title,
            duration="Live",
            duration_sec=0,
            url=track.url,
            file_path=stream_url,
            user=user,
            video=False,
        )

    queue.set(chat_id, media)
    await pytgcalls.play_media(chat_id, msg, media)
