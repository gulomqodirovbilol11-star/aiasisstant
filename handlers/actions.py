import os
import logging
from telethon import events, TelegramClient
from telethon.tl.types import User, Channel, Chat

from config import config
from database import Database

logger = logging.getLogger(__name__)


def register_action_handlers(client: TelegramClient, db: Database, bot_client: TelegramClient = None):

    async def notify_user(message_text: str, parse_mode: str = "html"):
        try:
            await client.send_message("me", message_text, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(f"Saved Messages'ga yuborishda xato: {e}")

        if bot_client and config.MY_TELEGRAM_ID:
            try:
                await bot_client.send_message(config.MY_TELEGRAM_ID, message_text, parse_mode=parse_mode)
            except Exception as e:
                logger.debug(f"Bot orqali yuborishda xato: {e}")

    @client.on(events.ChatAction)
    async def on_chat_action(event: events.ChatAction.Event):
        if not config.ENABLE_NEW_CHAT_ALERT:
            return

        try:
            me = await client.get_me()
            chat = await event.get_chat()
            chat_title = getattr(chat, "title", "Guruh/Kanal")
            chat_id = event.chat_id

            # O'zimiz qo'shilganimiz yoki kimdir bizni qo'shgan holat
            is_me_added = False
            adder_name = "Noma'lum"

            if event.user_added:
                added_users = await event.get_users()
                for user in added_users:
                    if user.id == me.id:
                        is_me_added = True
                        break

            if event.user_joined and event.user_id == me.id:
                is_me_added = True

            if is_me_added:
                try:
                    adder = await event.get_added_by()
                    if adder:
                        adder_username = f"@{adder.username}" if adder.username else ""
                        adder_name = f"{adder.first_name or ''} {adder.last_name or ''}".strip() or adder_username
                except Exception:
                    pass

                chat_type = "Kanal" if (isinstance(chat, Channel) and chat.broadcast) else "Guruh"

                # Bazaga chatni saqlash
                await db.upsert_chat(
                    chat_id=chat_id,
                    title=chat_title,
                    username=getattr(chat, "username", None),
                    chat_type=chat_type.lower()
                )

                # Tinchlik rejimi tekshiruvi: silent on bo'lsa yangi guruh xabarnomasi yuborilmaydi
                if await db.is_silent_mode():
                    return

                alert = (
                    f"📢 <b>Yangi {chat_type}ga Qo'shildingiz:</b>\n\n"
                    f"├ <b>Nomi:</b> {chat_title}\n"
                    f"├ <b>ID:</b> <code>{chat_id}</code>\n"
                    f"├ <b>Qo'shgan shaxs:</b> {adder_name}\n"
                    f"└ <b>Havola:</b> @{chat.username if getattr(chat, 'username', None) else 'mavjud emas'}"
                )
                await notify_user(alert, parse_mode="html")

        except Exception as e:
            logger.error(f"ChatAction qayta ishlashda xatolik: {e}", exc_info=True)
