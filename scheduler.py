import os
import time
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telethon import TelegramClient

from config import config
from database import Database
from ai_service import AIService

logger = logging.getLogger(__name__)


async def run_daily_digest(client: TelegramClient, db: Database, ai_service: AIService):
    """Har kungi rejalashtirilgan AI Digest hisobotini tayyorlash va yuborish."""
    try:
        logger.info("Rejalashtirilgan kunlik AI Digest jarayoni boshlandi...")
        
        # So'nggi 24 soatlik xabarlar
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        messages = await db.get_messages_for_digest(since)

        if not messages:
            await client.send_message(
                "me",
                f"📑 <b>Kunlik AI Digest ({datetime.now().strftime('%d.%m.%Y')}):</b>\n"
                "So'nggi 24 soat ichida qayd etilgan yangi kiruvchi xabarlar topilmadi.",
                parse_mode="html"
            )
            return

        digest = await ai_service.generate_daily_digest(messages)

        header = (
            f"📑 <b>KUNLIK SUN'IY INTELLEKT XULOSASI (AI DIGEST)</b>\n"
            f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n"
            f"🕒 Vaqt: {datetime.now().strftime('%H:%M')} ({config.TIMEZONE})\n"
            f"📊 Jami tahlil qilingan xabarlar: {len(messages)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        full_message = header + digest

        if len(full_message) > 4000:
            chunks = [full_message[i:i+3800] for i in range(0, len(full_message), 3800)]
            for chunk in chunks:
                await client.send_message("me", chunk, parse_mode="markdown")
        else:
            await client.send_message("me", full_message, parse_mode="markdown")

        logger.info("Kunlik AI Digest muvaffaqiyatli yuborildi.")

    except Exception as e:
        logger.error(f"Kunlik AI Digest yuborishda xatolik: {e}", exc_info=True)
        try:
            await client.send_message("me", f"❌ <b>Kunlik Digest xatosi:</b> <code>{e}</code>", parse_mode="html")
        except Exception:
            pass


async def cleanup_old_media():
    """30 kundan eski media fayllarni diskdan tozalash."""
    try:
        media_dir = config.MEDIA_STORAGE_DIR
        if not os.path.exists(media_dir):
            return

        now = time.time()
        cutoff_days = 30
        cutoff_seconds = now - (cutoff_days * 86400)

        cleaned_count = 0
        for fname in os.listdir(media_dir):
            if fname.startswith("."):
                continue
            fpath = os.path.join(media_dir, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff_seconds:
                os.remove(fpath)
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info(f"Diskni tozalash: {cleaned_count} ta eski media fayl o'chirildi.")
    except Exception as e:
        logger.warning(f"Media fayllarni tozalashda xatolik: {e}")


def setup_scheduler(client: TelegramClient, db: Database, ai_service: AIService) -> AsyncIOScheduler:
    """APScheduler ni sozlash va ishga tushirish."""
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

    hour, minute = config.digest_hour_minute
    logger.info(f"AI Digest har kuni soat {hour:02d}:{minute:02d} ({config.TIMEZONE}) ga rejalashtirildi.")

    # Kunlik AI Digest
    scheduler.add_job(
        run_daily_digest,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
        args=[client, db, ai_service],
        id="daily_ai_digest",
        replace_existing=True
    )

    # Haftalik eski media fayllarni tozalash (har yakshanba 03:00 da)
    scheduler.add_job(
        cleanup_old_media,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=config.TIMEZONE),
        id="weekly_media_cleanup",
        replace_existing=True
    )

    return scheduler
