# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import asyncio

from pyrogram import enums, errors, types

from anony import app, config, db, logger, queue, yt
from anony.helpers import utils


async def _wait_for_assistant_member(chat_id: int, assistant_id: int, retries: int = 10):
    """
    Wait until Telegram confirms that the assistant is a member of the chat.
    This prevents playback from starting before the join has propagated.
    """
    for attempt in range(retries):
        try:
            member = await app.get_chat_member(
                chat_id=chat_id,
                user_id=assistant_id,
            )

            if member.status not in [
                enums.ChatMemberStatus.BANNED,
                enums.ChatMemberStatus.RESTRICTED,
            ]:
                logger.info(
                    f"ASSISTANT READY | "
                    f"chat={chat_id} | "
                    f"assistant={assistant_id} | "
                    f"attempt={attempt + 1}"
                )
                return member

            return member

        except errors.UserNotParticipant:
            logger.info(
                f"WAITING ASSISTANT JOIN | "
                f"chat={chat_id} | "
                f"assistant={assistant_id} | "
                f"attempt={attempt + 1}/{retries}"
            )

        except errors.PeerIdInvalid:
            logger.info(
                f"WAITING PEER RESOLUTION | "
                f"chat={chat_id} | "
                f"assistant={assistant_id} | "
                f"attempt={attempt + 1}/{retries}"
            )

        except Exception as ex:
            logger.warning(
                f"MEMBER CHECK RETRY FAILED | "
                f"chat={chat_id} | "
                f"assistant={assistant_id} | "
                f"attempt={attempt + 1} | "
                f"error={ex}"
            )

        await asyncio.sleep(2)

    return None


def checkUB(play):
    async def wrapper(_, m: types.Message):
        if not m.from_user:
            return await m.reply_text(m.lang["play_user_invalid"])

        chat_id = m.chat.id

        if m.chat.type != enums.ChatType.SUPERGROUP:
            await m.reply_text(m.lang["play_chat_invalid"])
            return await app.leave_chat(chat_id)

        if not m.reply_to_message and (
            len(m.command) < 2
            or (len(m.command) == 2 and m.command[1] == "-f")
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

            # Get assistant client
            try:
                client = await db.get_client(chat_id)

            except Exception as ex:
                logger.error(
                    f"GET CLIENT FAILED | "
                    f"chat={chat_id} | "
                    f"error={ex}"
                )

                return await m.reply_text(
                    "❌ Failed to get assistant client.\n\n"
                    f"Chat ID: `{chat_id}`"
                )

            # Resolve assistant
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
                    f"chat={chat_id} | "
                    f"error={ex}"
                )

                return await m.reply_text(
                    "❌ Assistant session is not working.\n\n"
                    "Please check SESSION1 / SESSION2 / SESSION3."
                )

            assistant_id = assistant.id

            # -----------------------------------------------------
            # Check assistant membership
            # -----------------------------------------------------

            member = None

            try:
                member = await app.get_chat_member(
                    chat_id=chat_id,
                    user_id=assistant_id,
                )

                logger.info(
                    f"ASSISTANT MEMBER CHECK | "
                    f"chat={chat_id} | "
                    f"assistant={assistant_id} | "
                    f"status={member.status}"
                )

            except errors.PeerIdInvalid:
                logger.warning(
                    f"PEER_ID_INVALID | "
                    f"chat={chat_id} | "
                    f"assistant={assistant_id}"
                )

                # Let the assistant resolve the group.
                try:
                    await client.get_chat(chat_id)

                except Exception as ex:
                    logger.warning(
                        f"ASSISTANT CHAT RESOLVE FAILED | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id} | "
                        f"error={ex}"
                    )

                # Re-check after resolving.
                try:
                    member = await app.get_chat_member(
                        chat_id=chat_id,
                        user_id=assistant_id,
                    )

                except errors.UserNotParticipant:
                    member = None

                except errors.PeerIdInvalid:
                    member = None

                except Exception as ex:
                    logger.error(
                        f"MEMBER CHECK FAILED AFTER RESOLVE | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id} | "
                        f"error={ex}"
                    )
                    member = None

            except errors.UserNotParticipant:
                member = None

            except errors.ChatAdminRequired:
                return await m.reply_text(m.lang["admin_required"])

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

            # -----------------------------------------------------
            # Assistant is not in group -> join
            # -----------------------------------------------------

            if member is None:

                logger.info(
                    f"ASSISTANT NOT IN CHAT | "
                    f"chat={chat_id} | "
                    f"assistant={assistant_id}"
                )

                # Get invite link
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
                            f"chat={chat_id} | "
                            f"error={ex}"
                        )

                        return await m.reply_text(
                            m.lang["play_invite_error"].format(
                                type(ex).__name__
                            )
                        )

                umm = await m.reply_text(
                    m.lang["play_invite"].format(app.name)
                )

                await asyncio.sleep(1)

                # -------------------------------------------------
                # Join assistant
                # -------------------------------------------------

                try:
                    await client.join_chat(invite_link)

                    logger.info(
                        f"ASSISTANT JOIN REQUEST SUCCESS | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id}"
                    )

                except errors.UserAlreadyParticipant:
                    logger.info(
                        f"ASSISTANT ALREADY PARTICIPANT | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id}"
                    )

                except errors.InviteRequestSent:

                    logger.info(
                        f"ASSISTANT JOIN REQUEST SENT | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id}"
                    )

                    # Give Telegram time to register request.
                    await asyncio.sleep(2)

                    try:
                        await app.approve_chat_join_request(
                            chat_id=chat_id,
                            user_id=assistant_id,
                        )

                        logger.info(
                            f"ASSISTANT JOIN REQUEST APPROVED | "
                            f"chat={chat_id} | "
                            f"assistant={assistant_id}"
                        )

                    except errors.HideRequesterMissing:
                        pass

                    except errors.UserAlreadyParticipant:
                        pass

                    except Exception as ex:
                        logger.warning(
                            f"APPROVE JOIN FAILED | "
                            f"chat={chat_id} | "
                            f"assistant={assistant_id} | "
                            f"error={ex}"
                        )

                except errors.PeerIdInvalid as ex:

                    logger.error(
                        f"JOIN PEER INVALID | "
                        f"chat={chat_id} | "
                        f"assistant={assistant_id} | "
                        f"error={ex}"
                    )

                    return await umm.edit_text(
                        "❌ Telegram could not resolve the group for "
                        "the assistant.\n\n"
                        f"Chat ID: `{chat_id}`\n"
                        f"Assistant ID: `{assistant_id}`"
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

                # -------------------------------------------------
                # IMPORTANT:
                # Wait until Telegram confirms membership.
                # -------------------------------------------------

                member = await _wait_for_assistant_member(
                    chat_id=chat_id,
                    assistant_id=assistant_id,
                    retries=15,
                )

                if member is None:
                    try:
                        await umm.edit_text(
                            "❌ Assistant joined, but Telegram has not "
                            "confirmed the membership yet.\n\n"
                            "Please try `/play` again in a few seconds."
                        )
                    except Exception:
                        pass

                    return

                # Check banned/restricted state after joining
                if member.status in [
                    enums.ChatMemberStatus.BANNED,
                    enums.ChatMemberStatus.RESTRICTED,
                ]:

                    try:
                        await app.unban_chat_member(
                            chat_id=chat_id,
                            user_id=assistant_id,
                        )

                    except Exception:
                        try:
                            await umm.edit_text(
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
                        except Exception:
                            pass

                        return

                # Delete invitation message only after successful join.
                try:
                    await umm.delete()
                except Exception:
                    pass

            else:
                # -------------------------------------------------
                # Existing member
                # -------------------------------------------------

                if member.status in [
                    enums.ChatMemberStatus.BANNED,
                    enums.ChatMemberStatus.RESTRICTED,
                ]:

                    try:
                        await app.unban_chat_member(
                            chat_id=chat_id,
                            user_id=assistant_id,
                        )

                        # Wait for Telegram update.
                        await asyncio.sleep(2)

                    except Exception:
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

        # ---------------------------------------------------------
        # Delete command if enabled
        # ---------------------------------------------------------

        if await db.get_cmd_delete(chat_id):
            try:
                await m.delete()
            except Exception:
                pass

        # ---------------------------------------------------------
        # Start playback
        # ---------------------------------------------------------

        return await play(
            _,
            m,
            force,
            m3u8,
            video,
            url,
        )

    return wrapper
