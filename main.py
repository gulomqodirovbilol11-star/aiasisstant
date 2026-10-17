import os
import sys
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient

from config import config
from database import Database
from ai_service import AIService
from scheduler import setup_scheduler
from handlers.messages import register_message_handlers
from handlers.deleted import register_deleted_handlers
from handlers.actions import register_action_handlers
from handlers.commands import register_command_handlers


# Render talab qiladigan HTTP Health-Check serveri
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

    def log_message(self, format, *args):
        # HTTP serverning ortiqcha so'rov loglarini o'chirib turish uchun
        pass


def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


# Loglash sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s : %(message)s",
    handlers=[
        logging.FileHandler("agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MyAIAgent")


async def main():
    logger.info("==========================================")
    logger.info(" Telegram Shaxsiy AI Agent — Ishga tushmoqda")
    logger.info("==========================================")

    # 0. Render uchun veb-serverni fonda ishga tushirish
    web_thread = threading.Thread(target=run_health_check_server, daemon=True)
    web_thread.start()
    port = os.environ.get("PORT", 8080)
    logger.info(f"Render uchun Health-check serveri {port}-portda ishga tushdi.")

    # 1. API kalitlarini tekshirish
    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
        logger.error(
            "\n❌ XATOLIK: Telegram API ma'lumotlari topilmadi!\n"
            "Iltimos, '.env' faylini oching va quyidagi ma'lumotlarni kiriting:\n"
            "TELEGRAM_API_ID=...\n"
            "TELEGRAM_API_HASH=...\n"
            "Ma'lumotlarni https://my.telegram.org/ dan olishingiz mumkin.\n"
        )
        sys.exit(1)

    # 2. Papkalarni yaratish
    config.ensure_directories()

    # 3. Ma'lumotlar bazasini ishga tushirish
    logger.info(f"Baza yuklanmoqda: {config.DATABASE_PATH}")
    db = Database(config.DATABASE_PATH)
    await db.init_db()
    logger.info("Ma'lumotlar bazasi tayyor.")

    # 4. Gemini AI xizmatini ulash
    logger.info(f"AI Service ishga tushirilmoqda (Model: {config.GEMINI_MODEL})...")
    ai_service = AIService(
        api_key=config.GEMINI_API_KEY,
        model_name=config.GEMINI_MODEL,
        urgency_keywords=config.urgency_keywords_list
    )

    # 5. Telegram mijozlarini sozlash
    logger.info("Telegramga ulanish jarayoni boshlandi...")
    user_client = TelegramClient(
        config.TELEGRAM_SESSION_NAME,
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH
    )

    bot_client = None
    if config.BOT_TOKEN:
        bot_client = TelegramClient(
            "bot_session",
            config.TELEGRAM_API_ID,
            config.TELEGRAM_API_HASH
        )

    # 6. Hodisa ishlovchilarini (Handlers) ro'yxatga olish
    register_message_handlers(user_client, db, ai_service, bot_client)
    register_deleted_handlers(user_client, db, bot_client)
    register_action_handlers(user_client, db, bot_client)
    register_command_handlers(user_client, db, ai_service, bot_client)

    # 7. Rejalashtiruvchini (Scheduler) sozlash
    scheduler = setup_scheduler(user_client, db, ai_service)
    scheduler.start()
    logger.info(f"Vazifalar rejalashtiruvchisi ishga tushdi (Digest vaqti: {config.DIGEST_TIME}).")

    # 8. Telegram mijozlarini ishga tushirish
    await user_client.start()
    me = await user_client.get_me()
    uname = f"(@{me.username})" if me.username else ""
    logger.info(f"Muvaffaqiyatli ulandi! Akkaunt: {me.first_name} {uname} [ID: {me.id}]")

    tasks = [user_client.run_until_disconnected()]

    if bot_client:
        try:
            await bot_client.start(bot_token=config.BOT_TOKEN)
            bot_me = await bot_client.get_me()
            logger.info(f"Boshqaruv boti ulandi: @{bot_me.username} [ID: {bot_me.id}]")
            tasks.append(bot_client.run_until_disconnected())
        except Exception as e:
            logger.warning(f"Botni ishga tushirishda ogohlantirish: {e}")

    logger.info("Agent faol va barcha buyruqlarni tinglamoqda. To'xtatish uchun Ctrl+C bosing.")

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Agent xizmati to'xtatildi.")
    finally:
        scheduler.shutdown(wait=False)
        await user_client.disconnect()
        if bot_client:
            await bot_client.disconnect()
        logger.info("Dastur to'liq yakunlandi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDastur foydalanuvchi tomonidan to'xtatildi.")