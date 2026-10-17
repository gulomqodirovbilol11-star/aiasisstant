import os
import logging
from datetime import datetime, timedelta, timezone
from telethon import events, TelegramClient
from telethon.tl.types import User, Channel, Chat

from config import config
from database import Database
from ai_service import AIService

logger = logging.getLogger(__name__)


def register_command_handlers(client: TelegramClient, db: Database, ai_service: AIService, bot_client: TelegramClient = None):
    """
    Agentni boshqaruv buyruqlarini ro'yxatga olish.
    Buyruqlar Saved Messages ("me") orqali yoki Telegram Bot (MY_TELEGRAM_ID) orqali berilishi mumkin.
    """

    async def execute_command(event, text: str):
        if not text.startswith("/"):
            return

        tokens = text.split()
        cmd = tokens[0].lower()
        args = tokens[1:] if len(tokens) > 1 else []

        try:
            # =========================================================
            # 0. /help va /start
            # =========================================================
            if cmd in ("/help", "/start"):
                help_text = (
                    "🤖 <b>Telegram Shaxsiy AI Agent — To'liq Qo'llanma:</b>\n\n"
                    "🧠 <b>1. AI va Xulosalash (Gemini):</b>\n"
                    "├ <code>/digest</code> — Bugungi barcha xabarlar tahlili va konspekti\n"
                    "├ <code>/summarize @username</code> — Foydalanuvchi bilan yozishmalar xulosasi\n"
                    "└ <code>/reply_suggest @username</code> — Oxirgi xabarga 3 xil aqlli javob varianti\n\n"
                    "🗑 <b>2. O'chirilgan Xabarlar va Audit:</b>\n"
                    "├ <code>/deleted [soni]</code> — Oxirgi o'chirilgan xabarlar ro'yxati\n"
                    "├ <code>/deleted_by @username</code> — Aniq bir shaxs o'chirgan xabarlar\n"
                    "└ <code>/clear_history [kun]</code> — Bazadagi eski xabarlarni tozalash (standart 30 kun)\n\n"
                    "👤 <b>3. Kontaktlar va Profil Nazorati:</b>\n"
                    "├ <code>/whois @username</code> — Foydalanuvchi haqida to'liq dosye va statistika\n"
                    "├ <code>/chats</code> — Sizga eng ko'p yozgan odamlar reytingi (Top-10)\n"
                    "└ <code>/unread</code> — O'qilmagan qolib ketgan chat va kanallar\n\n"
                    "🛡 <b>4. Avtomatlashtirish va Xavfsizlik:</b>\n"
                    "├ <code>/autoreply on|off</code> — AI avtomatik javob berishini yoqish/o'chirish\n"
                    "├ <code>/autoreply prompt [matn]</code> — AI qanday javob berishi bo'yicha ko'rsatma berish\n"
                    "├ <code>/autoreply status</code> — Avtomatik javob holati va sozlamalarini ko'rish\n"
                    "├ <code>/silent on|off</code> — Tinchlik rejimi (faqat favqulodda xabarlar qoladi)\n"
                    "├ <code>/search [kalit so'z]</code> — Bazadagi barcha xabarlardan qidirish\n"
                    "├ <code>/blacklist add @user</code> — Qora ro'yxatga kiritish\n"
                    "├ <code>/blacklist remove @user</code> — Qora ro'yxatdan chiqarish\n"
                    "└ <code>/blacklist list</code> — Bloklangan akkauntlar ro'yxati\n\n"
                    "⚙️ <b>Qo'shimcha:</b>\n"
                    "├ <code>/status</code> — Tizim, baza, xotira va AI holati\n"
                    "└ <code>/send @user Xabar</code> — Profil nomingizdan xabar yuborish"
                )
                await event.reply(help_text, parse_mode="html")

            # =========================================================
            # 1. AI VA XULOSALASH BUYRUQLARI
            # =========================================================

            # /digest
            elif cmd == "/digest":
                status_msg = await event.reply("⏳ <i>Bugungi xabarlar to'planmoqda va Gemini AI tahlili boshlanmoqda...</i>", parse_mode="html")
                
                # Bugungi kun boshidan (yoki oxirgi 24 soat)
                today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                since = today_start.isoformat()
                messages = await db.get_messages_for_digest(since)
                
                # Agar bugun kam bo'lsa, oxirgi 24 soatni olamiz
                if len(messages) < 3:
                    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                    messages = await db.get_messages_for_digest(since)

                digest = await ai_service.generate_daily_digest(messages)
                
                header = (
                    f"📑 <b>AI KUNLIK HISOBOT (DIGEST)</b>\n"
                    f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n"
                    f"🕒 Vaqt: {datetime.now().strftime('%H:%M')} ({config.TIMEZONE})\n"
                    f"📊 Tahlil qilingan xabarlar soni: {len(messages)}\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                )
                
                full_response = header + digest
                if len(full_response) > 4000:
                    chunks = [full_response[i:i+3800] for i in range(0, len(full_response), 3800)]
                    await status_msg.edit(chunks[0], parse_mode="markdown")
                    for chunk in chunks[1:]:
                        await event.reply(chunk, parse_mode="markdown")
                else:
                    await status_msg.edit(full_response, parse_mode="markdown")

            # /summarize @username
            elif cmd == "/summarize":
                if not args:
                    await event.reply(
                        "⚠️ <b>Foydalanish:</b> <code>/summarize @username</code> yoki <code>/summarize [User_ID]</code>\n"
                        "<i>Misol: <code>/summarize @abror_dev</code></i>",
                        parse_mode="html"
                    )
                    return

                target = args[0].strip()
                status_msg = await event.reply(f"⏳ <i>{target} bilan yozishmalar tahlil qilinmoqda...</i>", parse_mode="html")

                dialog_msgs = await db.get_user_dialog_messages(target, limit=35)
                
                # Agar bazada kam bo'lsa, Telegram orqali jonli dialogdan ham olamiz
                if len(dialog_msgs) < 5:
                    try:
                        entity = await client.get_entity(target)
                        tg_messages = await client.get_messages(entity, limit=30)
                        temp_msgs = []
                        for m in reversed(tg_messages):
                            t = m.raw_text or ""
                            if t:
                                temp_msgs.append({
                                    "is_outgoing": bool(m.out),
                                    "sender_username": getattr(entity, "username", None),
                                    "sender_name": getattr(entity, "first_name", target),
                                    "text": t,
                                    "voice_transcript": None,
                                    "media_type": "media" if m.media else None,
                                    "date": m.date.isoformat() if m.date else ""
                                })
                        if len(temp_msgs) > len(dialog_msgs):
                            dialog_msgs = temp_msgs
                    except Exception as e:
                        logger.debug(f"Jonli get_messages olishda ogohlantirish: {e}")

                if not dialog_msgs:
                    await status_msg.edit(f"📭 <code>{target}</code> bilan hech qanday yozishma topilmadi.", parse_mode="html")
                    return

                summary = await ai_service.summarize_dialog(target, dialog_msgs)
                header = (
                    f"📋 <b>YOZISHMALAR XULOSASI: {target}</b>\n"
                    f"📊 Ko'rib chiqilgan xabarlar: {len(dialog_msgs)} ta\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                )
                full_res = header + summary
                await status_msg.edit(full_res[:4000], parse_mode="markdown")

            # /reply_suggest @username
            elif cmd == "/reply_suggest":
                if not args:
                    # Agar biror xabarga reply qilib yozilgan bo'lsa
                    reply_msg = await event.get_reply_message()
                    if reply_msg and reply_msg.text:
                        target = "Suhbatdosh"
                        last_message = reply_msg.text
                        history = []
                    else:
                        await event.reply(
                            "⚠️ <b>Foydalanish:</b> <code>/reply_suggest @username</code>\n"
                            "<i>Yoki biror xabarga javob (reply) qilib <code>/reply_suggest</code> deb yozing.</i>",
                            parse_mode="html"
                        )
                        return
                else:
                    target = args[0].strip()
                    status_msg = await event.reply(f"⏳ <i>{target} ning oxirgi xabari o'rganilmoqda...</i>", parse_mode="html")
                    
                    dialog_msgs = await db.get_user_dialog_messages(target, limit=15)
                    last_message = None
                    for m in reversed(dialog_msgs):
                        if not m.get("is_outgoing"):
                            last_message = m.get("voice_transcript") or m.get("text")
                            if last_message:
                                break

                    # Agar bazadan topilmasa Telegramdan olish
                    if not last_message:
                        try:
                            entity = await client.get_entity(target)
                            tg_msgs = await client.get_messages(entity, limit=10)
                            for m in tg_msgs:
                                if not m.out and m.raw_text:
                                    last_message = m.raw_text
                                    break
                        except Exception as e:
                            logger.debug(f"Entity olishda xato: {e}")

                    if not last_message:
                        await status_msg.edit(f"⚠️ <code>{target}</code> dan oxirgi kiruvchi xabar topilmadi.", parse_mode="html")
                        return

                    history = dialog_msgs

                res = await ai_service.suggest_replies(target, last_message, history)
                header = (
                    f"💡 <b>JAVOB VARIANTLARI ({target}):</b>\n"
                    f"📩 <i>Kelgan xabar:</i> \"{last_message[:120]}\"\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                )
                if 'status_msg' in locals():
                    await status_msg.edit(header + res, parse_mode="markdown")
                else:
                    await event.reply(header + res, parse_mode="markdown")

            # =========================================================
            # 2. O'CHIRILGAN XABARLAR VA AUDIT
            # =========================================================

            # /deleted [soni]
            elif cmd == "/deleted":
                limit = 5
                if args and args[0].isdigit():
                    limit = min(int(args[0]), 30)

                deleted_list = await db.get_recent_deleted_messages(limit=limit)
                if not deleted_list:
                    await event.reply("📭 Hozircha bazada o'chirilgan xabarlar qayd etilmagan.")
                    return

                result_lines = [f"🗑 <b>Oxirgi {len(deleted_list)} ta O'chirilgan Xabar:</b>\n"]
                for i, msg in enumerate(deleted_list, 1):
                    sender = f"@{msg['sender_username']}" if msg.get("sender_username") else (msg.get("sender_name") or "Noma'lum")
                    chat = msg.get("chat_title") or "Shaxsiy"
                    time_str = msg.get("date", "")[:16].replace("T", " ")
                    body = msg.get("voice_transcript") or msg.get("text") or (f"[{msg.get('media_type')} fayli]" if msg.get("media_type") else "[Matnsiz]")
                    result_lines.append(
                        f"{i}. <b>{sender}</b> ({chat}) — <i>{time_str}</i>\n"
                        f"   └ <code>{body[:140]}</code>\n"
                    )

                await event.reply("\n".join(result_lines), parse_mode="html")

            # /deleted_by @username
            elif cmd == "/deleted_by":
                if not args:
                    await event.reply("⚠️ <b>Foydalanish:</b> <code>/deleted_by @username</code>", parse_mode="html")
                    return

                target = args[0].strip()
                limit = 10
                if len(args) > 1 and args[1].isdigit():
                    limit = min(int(args[1]), 30)

                deleted_list = await db.get_deleted_messages_by_user(target, limit=limit)
                if not deleted_list:
                    await event.reply(f"📭 <code>{target}</code> tomonidan o'chirilgan xabarlar topilmadi.", parse_mode="html")
                    return

                result_lines = [f"🗑 <b>{target} tomonidan o'chirilgan xabarlar ({len(deleted_list)} ta):</b>\n"]
                for i, msg in enumerate(deleted_list, 1):
                    chat = msg.get("chat_title") or "Shaxsiy"
                    time_str = msg.get("date", "")[:16].replace("T", " ")
                    body = msg.get("voice_transcript") or msg.get("text") or (f"[{msg.get('media_type')} fayli]" if msg.get("media_type") else "[Matnsiz]")
                    result_lines.append(
                        f"{i}. <i>{time_str}</i> ({chat}):\n"
                        f"   └ <code>{body[:140]}</code>\n"
                    )

                await event.reply("\n".join(result_lines), parse_mode="html")

            # /clear_history [kun]
            elif cmd == "/clear_history":
                days = 30
                if args and args[0].isdigit():
                    days = int(args[0])

                del_count = await db.clear_old_messages(days=days)
                stats = await db.get_stats()
                res_text = (
                    f"🧹 <b>Tarix muvaffaqiyatli tozalandi!</b>\n\n"
                    f"├ <b>Muddat:</b> {days} kundan eski xabarlar\n"
                    f"├ <b>O'chirilgan yozuvlar soni:</b> {del_count} ta\n"
                    f"├ <b>Bazada qolgan jami xabarlar:</b> {stats['total_messages']}\n"
                    f"└ <b>Yangi baza hajmi:</b> {stats['db_size_mb']} MB"
                )
                await event.reply(res_text, parse_mode="html")

            # =========================================================
            # 3. KONTAKTLAR VA PROFIL NAZORATI
            # =========================================================

            # /whois @username
            elif cmd == "/whois":
                if not args:
                    await event.reply("⚠️ <b>Foydalanish:</b> <code>/whois @username</code> yoki <code>/whois [ID]</code>", parse_mode="html")
                    return

                target = args[0].strip()
                status_msg = await event.reply("🔍 <i>Ma'lumotlar qidirilmoqda...</i>", parse_mode="html")

                # Telegram orqali jonli profil ma'lumotlarini olish
                tg_user = None
                try:
                    tg_user = await client.get_entity(target)
                except Exception as e:
                    logger.debug(f"get_entity da xato: {e}")

                db_info = await db.get_user_stats(target)

                user_id = getattr(tg_user, "id", None) or (db_info.get("user_id") if db_info else None) or "Noma'lum"
                first_name = getattr(tg_user, "first_name", "") or ""
                last_name = getattr(tg_user, "last_name", "") or ""
                full_name = f"{first_name} {last_name}".strip() or (db_info.get("name") if db_info else "Noma'lum")
                username = getattr(tg_user, "username", None) or (db_info.get("username") if db_info else None)
                username_str = f"@{username}" if username else "Yo'q"
                phone = getattr(tg_user, "phone", None) or "Ko'rsatilmagan"

                first_seen = (db_info.get("first_seen") if db_info else None) or "Yozishma topilmadi"
                last_seen = (db_info.get("last_seen") if db_info else None) or "Yozishma topilmadi"
                if len(first_seen) >= 16:
                    first_seen = first_seen[:16].replace("T", " ")
                if len(last_seen) >= 16:
                    last_seen = last_seen[:16].replace("T", " ")

                incoming = db_info.get("incoming_count", 0) if db_info else 0
                outgoing = db_info.get("outgoing_count", 0) if db_info else 0
                deleted = db_info.get("deleted_count", 0) if db_info else 0
                total = incoming + outgoing

                info_text = (
                    f"👤 <b>Foydalanuvchi Dosyesi (WHOIS):</b>\n\n"
                    f"├ <b>Ism:</b> {full_name}\n"
                    f"├ <b>Username:</b> {username_str}\n"
                    f"├ <b>Telegram ID:</b> <code>{user_id}</code>\n"
                    f"├ <b>Telefon:</b> <code>+{phone}</code>\n"
                    f"├ <b>Birinchi yozishgan sana:</b> {first_seen}\n"
                    f"├ <b>Oxirgi yozishgan sana:</b> {last_seen}\n"
                    f"├ <b>Sizga yuborgan xabarlari:</b> {incoming} ta\n"
                    f"├ <b>Siz unga yozgan xabarlar:</b> {outgoing} ta\n"
                    f"├ <b>Jami yozishmalar soni:</b> {total} ta\n"
                    f"└ <b>O'chirilgan xabarlari soni:</b> {deleted} ta"
                )
                await status_msg.edit(info_text, parse_mode="html")

            # /chats
            elif cmd == "/chats":
                top_users = await db.get_top_chatted_users(limit=10)
                if not top_users:
                    await event.reply("📭 Hozircha bazada chatlar statistikasi mavjud emas.")
                    return

                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
                lines = ["📊 <b>Sizga Eng Ko'p Yozgan Kontaktlar (Top-10):</b>\n"]
                for i, u in enumerate(top_users):
                    rank = medals[i] if i < len(medals) else f"{i+1}."
                    name = u.get("sender_name") or "Noma'lum"
                    uname = f"(@{u['sender_username']})" if u.get("sender_username") else ""
                    cnt = u.get("msg_count", 0)
                    last_d = (u.get("last_activity") or "")[:10]
                    lines.append(f"{rank} <b>{name}</b> {uname}\n   └ 💬 <b>{cnt} ta xabar</b> | Oxirgi: <i>{last_d}</i>")

                await event.reply("\n".join(lines), parse_mode="html")

            # /unread
            elif cmd == "/unread":
                status_msg = await event.reply("🔍 <i>O'qilmagan xabarlar tekshirilmoqda...</i>", parse_mode="html")
                dialogs = await client.get_dialogs(limit=100)
                unread_list = [d for d in dialogs if d.unread_count > 0]

                if not unread_list:
                    await status_msg.edit("🎉 <b>Barcha xabarlar o'qilgan!</b> O'qilmagan shaxsiy chat yoki kanallar yo'q.", parse_mode="html")
                    return

                lines = [f"📬 <b>O'qilmagan Chatlar va Kanallar ({len(unread_list)} ta):</b>\n"]
                for i, d in enumerate(unread_list[:20], 1):
                    t = d.title or "Noma'lum chat"
                    cnt = d.unread_count
                    ctype = "👤 Shaxsiy" if d.is_user else ("📢 Kanal" if d.is_channel else "👥 Guruh")
                    last_msg_snippet = ""
                    if d.message and d.message.raw_text:
                        last_msg_snippet = f"\n   └ 💬 <i>{d.message.raw_text[:70]}</i>"
                    lines.append(f"{i}. {ctype} <b>{t}</b> — 🔴 <b>{cnt} ta yangi</b>{last_msg_snippet}")

                await status_msg.edit("\n".join(lines), parse_mode="html")

            # =========================================================
            # 4. AVTOMATLASHTIRISH VA XAVFSIZLIK
            # =========================================================

            # /autoreply on / off / status / prompt / resetprompt
            elif cmd == "/autoreply":
                sub = args[0].lower() if args else "status"

                if sub == "on":
                    await db.set_auto_reply_enabled(True)
                    await event.reply(
                        "🤖 <b>AI Avtomatik javob berish YOQILDI!</b>\n\n"
                        "Endi shaxsiy chatlardan kelgan yangi xabarlarga Gemini AI sizning shaxsiy yordamchingiz sifatida avtomatik javob qaytaradi.\n\n"
                        "💡 <i>Ko'rsatma o'rnatish: <code>/autoreply prompt [matn]</code></i>\n"
                        "⛔ <i>O'chirish uchun: <code>/autoreply off</code></i>",
                        parse_mode="html"
                    )
                elif sub == "off":
                    await db.set_auto_reply_enabled(False)
                    await event.reply(
                        "⛔ <b>AI Avtomatik javob berish O'CHIRILDI!</b>\n\n"
                        "Xabarlarga avtomatik javob berilmaydi.",
                        parse_mode="html"
                    )
                elif sub == "prompt":
                    if len(args) < 2:
                        await event.reply(
                            "⚠️ <b>Foydalanish:</b> <code>/autoreply prompt [ko'rsatma matni]</code>\n\n"
                            "<i>Misol:</i>\n"
                            "<code>/autoreply prompt Men dasturchiman, hozir bandman, shoshilinch bo'lmasa kechga javob beraman deb muloyim javob qaytar.</code>",
                            parse_mode="html"
                        )
                        return

                    new_prompt = " ".join(args[1:]).strip()
                    await db.set_auto_reply_prompt(new_prompt)
                    await event.reply(
                        f"✅ <b>AI uchun maxsus ko'rsatma (prompt) saqlandi!</b>\n\n"
                        f"📝 <b>Yangi yo'riqnoma:</b>\n"
                        f"<code>{new_prompt}</code>\n\n"
                        f"Standart holatga qaytarish uchun: <code>/autoreply resetprompt</code>",
                        parse_mode="html"
                    )
                elif sub == "resetprompt":
                    await db.set_auto_reply_prompt(None)
                    await event.reply(
                        "🔄 <b>AI ko'rsatmasi standart holatga qaytarildi.</b>\n"
                        "Endi AI umumiy aqlli shaxsiy yordamchi sifatida javob beradi.",
                        parse_mode="html"
                    )
                else:
                    is_on = await db.is_auto_reply_enabled()
                    state = "🟢 YOQILGAN (Faol)" if is_on else "🔴 O'CHIRILGAN"
                    custom_prompt = await db.get_auto_reply_prompt()
                    prompt_preview = f"<code>{custom_prompt}</code>" if custom_prompt else "<i>Standart shaxsiy yordamchi roli</i>"

                    status_msg = (
                        f"🤖 <b>AI Avtomatik Javob (Auto-Reply) Holati:</b>\n\n"
                        f"├ <b>Holat:</b> {state}\n"
                        f"├ <b>AI Modeli:</b> {ai_service.model_name}\n"
                        f"├ <b>Faqat shaxsiy chatlar:</b> {'Ha' if config.AUTO_REPLY_ONLY_PRIVATE else 'Barcha chatlar'}\n"
                        f"└ <b>Maxsus Yo'riqnoma (Prompt):</b>\n{prompt_preview}\n\n"
                        f"📌 <b>Boshqaruv buyruqlari:</b>\n"
                        f"• Yoqish: <code>/autoreply on</code>\n"
                        f"• O'chirish: <code>/autoreply off</code>\n"
                        f"• Ko'rsatma berish: <code>/autoreply prompt [matn]</code>\n"
                        f"• Standartga qaytarish: <code>/autoreply resetprompt</code>"
                    )
                    await event.reply(status_msg, parse_mode="html")

            # /silent on / /silent off
            elif cmd == "/silent":
                arg = args[0].lower() if args else ""
                if arg == "on":
                    await db.set_silent_mode(True)
                    await event.reply(
                        "🔕 <b>Tinchlik rejimi YOQILDI!</b>\n\n"
                        "Oddiy bildirishnomalar (yangi chatlar, o'chirilgan xabarlar, spam ogohlantirishlari) vaqtincha to'xtatildi.\n"
                        "🚨 <i>Faqat favqulodda shoshilinch (urgent) xabarlar yetkaziladi.</i>",
                        parse_mode="html"
                    )
                elif arg == "off":
                    await db.set_silent_mode(False)
                    await event.reply(
                        "🔔 <b>Tinchlik rejimi O'CHIRILDI!</b>\n\n"
                        "Barcha bildirishnomalar odatiy rejimda ishlashda davom etadi.",
                        parse_mode="html"
                    )
                else:
                    is_on = await db.is_silent_mode()
                    state = "🟢 YOQILGAN (Silent)" if is_on else "🔴 O'CHIRILGAN (Normal)"
                    await event.reply(
                        f"ℹ️ <b>Tinchlik rejimi holati:</b> {state}\n\n"
                        f"Yoqish uchun: <code>/silent on</code>\n"
                        f"O'chirish uchun: <code>/silent off</code>",
                        parse_mode="html"
                    )

            # /search [kalit so'z]
            elif cmd == "/search":
                if not args:
                    await event.reply(
                        "⚠️ <b>Foydalanish:</b> <code>/search [kalit so'z]</code>\n"
                        "<i>Misol: <code>/search parol</code> yoki <code>/search hisobot</code></i>",
                        parse_mode="html"
                    )
                    return

                query = " ".join(args).strip()
                status_msg = await event.reply(f"🔍 <i>\"{query}\" bo'yicha bazadan qidirilmoqda...</i>", parse_mode="html")

                found = await db.search_messages(query, limit=10)
                if not found:
                    await status_msg.edit(f"📭 <i>\"{query}\" so'rovi bo'yicha hech qanday xabar topilmadi.</i>", parse_mode="html")
                    return

                lines = [f"🔎 <b>Qidiruv natijalari: \"{query}\" ({len(found)} ta topildi):</b>\n"]
                for i, m in enumerate(found, 1):
                    sender = "Men" if m.get("is_outgoing") else (f"@{m.get('sender_username')}" if m.get("sender_username") else (m.get("sender_name") or "Noma'lum"))
                    chat = m.get("chat_title") or "Shaxsiy"
                    d_str = (m.get("date") or "")[:16].replace("T", " ")
                    body = m.get("voice_transcript") or m.get("text") or ""
                    # Qidirilgan so'zni qalin qilib ko'rsatish
                    body_snippet = body[:150].replace("\n", " ")
                    lines.append(
                        f"{i}. <b>{sender}</b> ({chat}) — <i>{d_str}</i>\n"
                        f"   └ <code>{body_snippet}</code>\n"
                    )

                await status_msg.edit("\n".join(lines), parse_mode="html")

            # /blacklist add|remove|list
            elif cmd == "/blacklist":
                sub = args[0].lower() if args else "list"
                
                if sub == "add":
                    if len(args) < 2:
                        await event.reply("⚠️ <b>Foydalanish:</b> <code>/blacklist add @username [sabab]</code>", parse_mode="html")
                        return

                    target = args[1].strip()
                    reason = " ".join(args[2:]).strip() if len(args) > 2 else "Foydalanuvchi tomonidan kiritildi"

                    # ID yoki username aniqlash
                    user_id = None
                    username = target.lstrip("@")
                    try:
                        ent = await client.get_entity(target)
                        if isinstance(ent, User):
                            user_id = ent.id
                            username = ent.username or username
                    except Exception:
                        if target.isdigit():
                            user_id = int(target)

                    ok, info = await db.add_to_blacklist(user_id=user_id, username=username, reason=reason)
                    if ok:
                        id_display = str(user_id) if user_id else "Noma'lum"
                        await event.reply(
                            f"🚫 <b>Akkaunt qora ro'yxatga kiritildi!</b>\n"
                            f"├ <b>Nishon:</b> {info}\n"
                            f"├ <b>ID:</b> <code>{id_display}</code>\n"
                            f"└ <b>Sabab:</b> {reason}\n\n"
                            f"<i>Endi agent bu akkaunt xabarlarini e'tiborsiz qoldiradi va bildirishnoma yubormaydi.</i>",
                            parse_mode="html"
                        )
                    else:
                        await event.reply(f"❌ Xatolik yuz berdi: <code>{info}</code>", parse_mode="html")

                elif sub == "remove":
                    if len(args) < 2:
                        await event.reply("⚠️ <b>Foydalanish:</b> <code>/blacklist remove @username</code>", parse_mode="html")
                        return

                    target = args[1].strip()
                    removed = await db.remove_from_blacklist(target)
                    if removed:
                        await event.reply(f"✅ <code>{target}</code> qora ro'yxatdan muvaffaqiyatli chiqarildi.", parse_mode="html")
                    else:
                        await event.reply(f"⚠️ <code>{target}</code> qora ro'yxatda topilmadi.", parse_mode="html")

                elif sub in ("list", "all"):
                    bl = await db.get_blacklist()
                    if not bl:
                        await event.reply("🟢 <b>Qora ro'yxat bo'sh!</b> Hech qanday akkaunt bloklanmagan.", parse_mode="html")
                        return

                    lines = [f"🚫 <b>Qora Ro'yxatdagi Akkauntlar ({len(bl)} ta):</b>\n"]
                    for i, item in enumerate(bl, 1):
                        u = f"@{item['username']}" if item.get("username") else f"ID:{item.get('user_id')}"
                        r = item.get("reason") or "Sababsiz"
                        d = (item.get("added_at") or "")[:10]
                        lines.append(f"{i}. <b>{u}</b> (Qo'shildi: {d})\n   └ Sabab: <i>{r}</i>")

                    await event.reply("\n".join(lines), parse_mode="html")

                else:
                    await event.reply(
                        "⚠️ <b>Noto'g'ri buyruq formati!</b>\n"
                        "├ <code>/blacklist add @username [sabab]</code>\n"
                        "├ <code>/blacklist remove @username</code>\n"
                        "└ <code>/blacklist list</code>",
                        parse_mode="html"
                    )

            # =========================================================
            # 5. TIZIM VA YUBORISH BUYRUQLARI
            # =========================================================

            # /status
            elif cmd == "/status":
                stats = await db.get_stats()
                ai_status = "🟢 Faol" if ai_service.client else "🔴 Ulanmagan (.env tekshiring)"
                silent_status = "🔕 Yoqilgan (Tinchlik)" if stats.get("silent_mode") else "🔔 O'chirilgan (Normal)"
                auto_reply_status = "🟢 Yoqilgan (Faol)" if stats.get("auto_reply_mode") else "🔴 O'chirilgan"

                status_text = (
                    "📊 <b>Agent Tizim Holati:</b>\n\n"
                    f"├ <b>AI Modeli:</b> {ai_service.model_name} ({ai_status})\n"
                    f"├ <b>AI Avto-javob (Auto-Reply):</b> {auto_reply_status}\n"
                    f"├ <b>Tinchlik rejimi (Silent):</b> {silent_status}\n"
                    f"├ <b>Jami qayd etilgan xabarlar:</b> {stats['total_messages']}\n"
                    f"├ <b>O'chirilgan xabarlar:</b> {stats['deleted_messages']}\n"
                    f"├ <b>Kuzatilgan kontaktlar:</b> {stats['total_users']}\n"
                    f"├ <b>Kuzatilgan chatlar:</b> {stats['total_chats']}\n"
                    f"├ <b>Qora ro'yxatdagi akkauntlar:</b> {stats['blacklisted_count']}\n"
                    f"├ <b>Ma'lumotlar bazasi hajmi:</b> {stats['db_size_mb']} MB\n"
                    f"└ <b>Kunlik Digest vaqti:</b> {config.DIGEST_TIME} ({config.TIMEZONE})"
                )
                await event.reply(status_text, parse_mode="html")

            # /send <target> <message>
            elif cmd == "/send":
                if len(args) < 2:
                    await event.reply(
                        "⚠️ <b>Noto'g'ri format!</b>\n"
                        "Foydalanish: <code>/send @username yoki chat_id Xabar matni</code>\n"
                        "Misol: <code>/send @abror_bek Assalomu alaykum, loyiha tayyormi?</code>",
                        parse_mode="html"
                    )
                    return

                target = args[0]
                content = " ".join(args[1:])

                try:
                    peer = int(target) if target.lstrip("-").isdigit() else target
                    sent = await client.send_message(peer, content)
                    await event.reply(
                        f"✅ <b>Xabar muvaffaqiyatli yuborildi!</b>\n"
                        f"├ <b>Qayerga:</b> <code>{target}</code>\n"
                        f"├ <b>Xabar ID:</b> <code>{sent.id}</code>\n"
                        f"└ <b>Matn:</b> {content}",
                        parse_mode="html"
                    )
                except Exception as e:
                    await event.reply(f"❌ <b>Xabar yuborishda xatolik:</b>\n<code>{e}</code>", parse_mode="html")

        except Exception as e:
            logger.error(f"Buyruq bajarishda xatolik ({cmd}): {e}", exc_info=True)
            try:
                await event.reply(f"❌ Xatolik yuz berdi: <code>{e}</code>", parse_mode="html")
            except Exception:
                pass

    # 1. Saved Messages orqali buyruqlarni tinglash (Userbot rejimida)
    @client.on(events.NewMessage(chats="me"))
    async def on_saved_message_command(event: events.NewMessage.Event):
        text = (event.raw_text or "").strip()
        if text.startswith("/"):
            await execute_command(event, text)

    # 2. Agar bot_client sozlangan bo'lsa, Telegram Bot orqali buyruqlarni tinglash
    if bot_client and config.MY_TELEGRAM_ID:
        @bot_client.on(events.NewMessage)
        async def on_bot_command(event: events.NewMessage.Event):
            if event.sender_id != config.MY_TELEGRAM_ID:
                return
            text = (event.raw_text or "").strip()
            if text.startswith("/"):
                await execute_command(event, text)
