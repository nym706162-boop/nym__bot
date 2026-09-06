import random
from pathlib import Path

from pyrogram import filters, types

from anony import anon, app, config, db, lang, queue, tg, yt
from anony.helpers import buttons, utils
from anony.helpers._play import checkUB


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
    # ── [ Global Sticker Pack Trigger - Top Priority ] ──
    try:
        pack_name = await db.get_sticker_pack("GLOBAL_STICKER_PACK")
        print(f"DEBUG: Retrieved Pack Name from DB -> {pack_name}")

        if pack_name:
            try:
                sticker_set = await app.get_sticker_set(pack_name)
                if sticker_set and getattr(sticker_set, "stickers", None):
                    random_sticker = random.choice(sticker_set.stickers)
                    await m.reply_sticker(random_sticker.file_id)
            except Exception as st_err:
                print(f"DEBUG: Falling back to direct sticker ID/Link -> {st_err}")
                await m.reply_sticker(pack_name)
        else:
            print("DEBUG: No pack_name found in Database!")
    except Exception as e:
        print(f"DEBUG Sticker Error: {e}")
    # ───────────────────────────────────────────────────

    sent = await m.reply_text(m.lang["play_searching"])

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

    # Check Database for cached audio file_id before downloading
    if hasattr(db, "get_audio_cache") and hasattr(file, "id"):
        cached_file_id = await db.get_audio_cache(file.id)
        if cached_file_id:
            file.file_id = cached_file_id
            print(f"DEBUG: Track loaded from Database Cache! ID: {cached_file_id}")

    if getattr(file, "duration_sec", 0) > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, sent.link, getattr(file, "title", "Track"), getattr(file, "duration", "00:00"))

    file.user = mention
    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            cyber_queued_text = (
                f"✨ <b>{config.MUSIC_BOT_NAME} • TRACK ADDED</b>\n"
                f"────────────────────────\n"
                f"📌 <b>Position :</b> <code>#{position}</code>\n"
                f"🎵 <b>Track    :</b> <a href='{getattr(file, 'url', '')}'>{getattr(file, 'title', 'Track')}</a>\n"
                f"⏳ <b>Duration :</b> <code>{getattr(file, 'duration', '00:00')}</code>\n"
                f"👤 <b>Requested:</b> {m.from_user.mention}\n"
                f"📡 <b>Source   :</b> <code>YouTube</code>\n"
                f"────────────────────────"
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

    # Download logic execution
    if not getattr(file, "file_path", None) and not getattr(file, "file_id", None):
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
        else:
            await sent.edit_text(m.lang["play_downloading"])
            file.file_path = await yt.download(file.id, video=video)

    cyber_playing_text = (
        f"🎶 <b>{config.MUSIC_BOT_NAME} • NOW PLAYING</b>\n"
        f"────────────────────────\n"
        f"🎵 <b>Track    :</b> <a href='{getattr(file, 'url', '')}'>{getattr(file, 'title', 'Track')}</a>\n"
        f"⏳ <b>Duration :</b> <code>{getattr(file, 'duration', '00:00')}</code>\n"
        f"👤 <b>Requested:</b> {mention}\n"
        f"📡 <b>Source   :</b> <code>YouTube</code>\n"
        f"────────────────────────"
    )
    sent.text = cyber_playing_text

    # Call to play media
    played_media = await anon.play_media(chat_id=m.chat.id, message=sent, media=file)

    # Check Telegram file_id and save to Database
    file_id_to_save = getattr(file, "file_id", None) or getattr(played_media, "file_id", None)

    if hasattr(db, "set_audio_cache") and file_id_to_save and getattr(file, "id", None):
        try:
            await db.set_audio_cache(file.id, file_id_to_save)
            print(f"DEBUG: Saved to DB Cache successfully! Vid ID: {file.id} -> File ID: {file_id_to_save}")
        except Exception as cache_err:
            print(f"Cache Warning: {cache_err}")

    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
    )
