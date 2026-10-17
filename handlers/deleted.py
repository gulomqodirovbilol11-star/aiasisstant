import os
import logging
from telethon import events, TelegramClient
from telethon.tl.types import User

from config import config
from database import Database

logger = logging.getLogger(__name__)


def register_deleted_handlers(client: TelegramClient, db: Database, bot_client: TelegramClient = None):

    async def notify_user(message_text: str, parse_mode: str = "html", file_path: str = None):
        """O'chirilgan xabarni Saved Messages yoki Bot orqali bildirish."""
        try:
            if file_path and os.path.exists(file_path):
                await client.send_file("me", file=file_path, caption=message_text, parse_mode=parse_mode)
            else:
                await client.send_message("me", message_text, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(f"Saved Messages'ga o'chirilgan xabar yuborishda xato: {e}")

        if bot_client and config.MY_TELEGRAM_ID:
            try:
                if file_path and os.path.exists(file_path):
                    await bot_client.send_file(config.MY_TELEGRAM_ID, file=file_path, caption=message_text, parse_mode=parse_mode)
                else:
                    await bot_client.send_message(config.MY_TELEGRAM_ID, message_text, parse_mode=parse_mode)
            except Exception as e:
                logger.debug(f"Bot orqali o'chirilgan xabar yuborishda xato: {e}")

    @client.on(events.MessageDeleted)
    async def on_message_deleted(event: events.MessageDeleted.Event):
        if not config.ENABLE_DELETED_MESSAGE_ALERT:
            return

        try:
            deleted_ids = event.deleted_ids
            if not deleted_ids:
                return

            chat_id = event.chat_id
            deleted_messages = await db.find_and_mark_deleted(deleted_ids, chat_id=chat_id)

            # Tinchlik rejimi tekshiruvi: silent on bo'lsa ogohlantirish yuborilmaydi (lekin bazada saqlanadi)
            is_silent = await db.is_silent_mode()
            if is_silent:
                return

            for msg in deleted_messages:
                # O'zimiz o'chirgan xabarlar bo'lsa xabar berish shart emas
                if msg.get("is_outgoing"):
                    continue

                sender_id = msg.get("sender_id")
                sender_username = msg.get("sender_username")

                # Qora ro'yxat tekshiruvi
                if await db.is_blacklisted(sender_id, sender_username):
                    continue

                sender_name = msg.get("sender_name") or "Noma'lum"
                sender_str = f"@{sender_username} ({sender_name})" if sender_username else sender_name
                chat_title = msg.get("chat_title") or "Shaxsiy chat"
                date_str = msg.get("date", "")[:19].replace("T", " ")

                body_text = msg.get("text") or ""
                voice_transcript = msg.get("voice_transcript")
                media_path = msg.get("media_path")
                media_type = msg.get("media_type")

                if voice_transcript:
                    content_display = f"🎤 <i>[Ovozli xabar matni]:</i>\n{voice_transcript}"
                elif body_text:
                    content_display = body_text
                elif media_type:
                    content_display = f"📎 <i>[{media_type.capitalize()} fayli yuborilgan va o'chirilgan]</i>"
                else:
                    content_display = "<i>[Bo'sh xabar yoki noma'lum format]</i>"

                alert = (
                    f"⚠️ <b>O'chirilgan Xabar:</b>\n\n"
                    f"👤 <b>Kimdan:</b> {sender_str}\n"
                    f"💬 <b>Chat:</b> {chat_title}\n"
                    f"🕒 <b>Yuborilgan vaqt:</b> {date_str}\n"
                    f"📝 <b>Matn:</b>\n{content_display}"
                )

                # Agar media saqlab qolingan bo'lsa, fayli bilan birga yuboramiz
                await notify_user(alert, parse_mode="html", file_path=media_path)

        except Exception as e:
            logger.error(f"MessageDeleted qayta ishlashda xatolik: {e}", exc_info=True)
