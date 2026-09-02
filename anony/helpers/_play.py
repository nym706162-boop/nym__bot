# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import asyncio

from pyrogram import enums, errors, types

from anony import app, config, db, logger, queue, yt
from anony.helpers import utils


def checkUB(play):
    async def wrapper(_, m: types.Message):
        if not m.from_user:
            return await m.reply_text(m.lang["play_user_invalid"])

        chat_id = m.chat.id

        if m.chat.type != enums.ChatType.SUPERGROUP:
            await m.reply_text(m.lang["play_chat_invalid"])
            return await app.leave_chat(chat_id)

        if not m.reply_to_message and (
            len(m.command) < 2 or
            (len(m.command) == 2 and m.command[1] == "-f")
        ):
            return await m.reply_text(m.lang["play_usage"])

        if len(queue.get_queue(chat_id)) >= config.QUEUE_LIMIT:
            return await m.reply_text(
                m.lang["play_queue_full"].format(config.QUEUE_LIMIT)
            )

        force = m.command[0].endswith("force") or (
            len(m.command) > 1 and "-f" in m.command[1]
        )

        video = m.command[0][0] == "v" and config.VIDEO_PLAY

        url = utils.get_url(m)

        if url and yt.invalid(url):
            return await m.reply_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

        m3u8 = url and not yt.valid(url)

        play_mode = await db.get_play_mode(chat_id)

        if play_mode or force:
            adminlist = await db.get_admins(chat_id)

            if (
                m.from_user.id not in adminlist
                and not await db.is_auth(chat_id, m.from_user.id)
                and m.from_user.id not in app.sudoers
            ):
                return await m.reply_text(m.lang["play_admin"])

        # ---------------------------------------------------------
        # Assistant / Userbot check
        # ---------------------------------------------------------

        if chat_id not in db.active_calls:

            try:
                client = await db.get_client(chat_id)

            except Exception as ex:
                logger.error(
                    f"GET CLIENT FAILED | chat={chat_id} | error={ex}"
                )
                return await m.reply_text(
                    "❌ Failed to get assistant client.\n\n"
                    f"Chat ID: `{chat_id}`"
                )

            # -----------------------------------------------------
            # Resolve assistant session
            # -----------------------------------------------------

            try:
                assistant = await client.get_me()

                logger.info(
                    f"ASSISTANT RESOLVED | "
                    f"chat={chat_id} | "
                    f"id={assistant.id} | "
                    f"username={assistant.username}"
                )

            except Exception as ex:
                logger.error(
                    f"ASSISTANT SESSION ERROR | "
                    f"chat={chat_id} | error={ex}"
                )

                return await m.reply_text(
                    "❌ Assistant session is not working.\n\n"
                    "Please check SESSION1 / SESSION2 / SESSION3."
                )

            assistant_id = assistant.id

            # -----------------------------------------------------
            # Check assistant membership
            # -----------------------------------------------------

            try:
                member = await app.get_chat_member(
                    chat_id=chat_id,
                    user_id=assistant_id
                )

                logger.info(
                    f"ASSISTANT MEMBER CHECK | "
                    f"chat={chat_id} | "
                    f"assistant={assistant_id} | "
                    f"status={member.status}"
                )

                if member.status in [
                    enums.ChatMemberStatus.BANNED,
                    enums.ChatMemberStatus.RESTRICTED,
                ]:

                    try:
                        await app.unban_chat_member(
                            chat_id=chat_id,
                            user_id=assistant_id
                        )

                        logger.info(
                            f"ASSISTANT UNBANNED | "
                            f"chat={chat_id} | "
                            f"assistant={assistant_id}"
                        )

                    except Exception as ex:
                        logger.error(
                            f"ASSISTANT UNBAN FAILED | "
                            f"chat={chat_id} | "
                            f"assistant={assistant_id} | "
                            f"error={ex}"
                        )

                        return await m.reply_text(
                            m.lang["play_banned"].format(
                                app.name,
                                assistant_id,
                                assistant.mention,
                                (
                                    f"@{assistant.username}"
                                    if assistant.username
                                    else None
                                ),
                            )
                        )

            # -----------------------------------------------------
            # Peer ID invalid
            # -----------------------------------------------------

            except errors.PeerIdInvalid:

                logger.warning(
                    f"PEER_ID_INVALID | "
                    f"chat={chat_id} | "
                    f"assistant={assistant_id}"
                )

                # Try resolving the group through the assistant
                try:
                    await client.get_chat(chat_id)

                    logger.info(
                        f"ASSISTANT CHAT RESOLVED | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id}"
                    )

                except Exception as ex:

                    logger.error(
                        f"ASSISTANT CANNOT RESOLVE CHAT | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id} | "
                        f"error={ex}"
                    )

                    return await m.reply_text(
                        "❌ Telegram cannot resolve this group.\n\n"
                        f"Chat ID: `{chat_id}`\n"
                        f"Assistant ID: `{assistant_id}`\n\n"
                        "Add the assistant account to this group "
                        "and try again."
                    )

                # Try member check again
                try:
                    member = await app.get_chat_member(
                        chat_id=chat_id,
                        user_id=assistant_id
                    )

                except errors.PeerIdInvalid:

                    logger.error(
                        f"PEER STILL INVALID | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id}"
                    )

                    return await m.reply_text(
                        "❌ Assistant is not known to Telegram in "
                        "this group.\n\n"
                        f"Assistant ID: `{assistant_id}`\n"
                        f"Chat ID: `{chat_id}`\n\n"
                        "Add the assistant account to the group "
                        "manually, then try /play again."
                    )

            # -----------------------------------------------------
            # Assistant is not a participant
            # -----------------------------------------------------

            except errors.UserNotParticipant:

                if m.chat.username:
                    invite_link = m.chat.username

                else:
                    try:
                        chat = await app.get_chat(chat_id)

                        invite_link = chat.invite_link

                        if not invite_link:
                            invite_link = await app.export_chat_invite_link(
                                chat_id
                            )

                    except errors.ChatAdminRequired:
                        return await m.reply_text(
                            m.lang["admin_required"]
                        )

                    except Exception as ex:
                        logger.error(
                            f"GET INVITE LINK FAILED | "
                            f"chat={chat_id} | error={ex}"
                        )

                        return await m.reply_text(
                            m.lang["play_invite_error"].format(
                                type(ex).__name__
                            )
                        )

                umm = await m.reply_text(
                    m.lang["play_invite"].format(app.name)
                )

                await asyncio.sleep(2)

                try:
                    await client.join_chat(invite_link)

                except errors.UserAlreadyParticipant:
                    pass

                except errors.InviteRequestSent:

                    await asyncio.sleep(2)

                    try:
                        await app.approve_chat_join_request(
                            chat_id,
                            assistant_id
                        )

                    except errors.HideRequesterMissing:
                        pass

                    except Exception as ex:
                        logger.error(
                            f"APPROVE JOIN FAILED | "
                            f"chat={chat_id} | "
                            f"assistant={assistant_id} | "
                            f"error={ex}"
                        )

                        return await umm.edit_text(
                            m.lang["play_invite_error"].format(
                                type(ex).__name__
                            )
                        )

                except Exception as ex:

                    logger.error(
                        f"JOIN CHAT FAILED | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id} | "
                        f"error={ex}"
                    )

                    return await umm.edit_text(
                        m.lang["play_invite_error"].format(
                            type(ex).__name__
                        )
                    )

                await umm.delete()

            # -----------------------------------------------------
            # Chat admin required
            # -----------------------------------------------------

            except errors.ChatAdminRequired:
                return await m.reply_text(
                    m.lang["admin_required"]
                )

            # -----------------------------------------------------
            # Other Telegram errors
            # -----------------------------------------------------

            except Exception as ex:

                logger.error(
                    f"ASSISTANT MEMBER CHECK FAILED | "
                    f"chat={chat_id} | "
                    f"assistant={assistant_id} | "
                    f"error={ex}"
                )

                return await m.reply_text(
                    f"❌ Assistant check failed.\n\n"
                    f"`{type(ex).__name__}: {ex}`"
                )

        # ---------------------------------------------------------
        # Delete command if enabled
        # ---------------------------------------------------------

        if await db.get_cmd_delete(chat_id):
            try:
                await m.delete()
            except Exception:
                pass

        return await play(_, m, force, m3u8, video, url)

    return wrapper
