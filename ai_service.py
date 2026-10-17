import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, api_key: str, model_name: str = "gemini-3.8-flash", urgency_keywords: Optional[List[str]] = None):
        self.api_key = (api_key or "").strip()
        self.model_name = model_name or "gemini-3.8-flash"
        self.urgency_keywords = [k.lower() for k in (urgency_keywords or [])]
        self.client = None
        self._init_client()

    def _init_client(self) -> None:
        """Gemini clientini sozlash."""
        if not self.api_key or self.api_key.startswith("your_") or "sizning_" in self.api_key:
            logger.warning("GEMINI_API_KEY kiritilmagan yoki noto'g'ri. AI funksiyalari vaqtincha cheklangan.")
            return

        try:
            # Yangi google-genai SDK orqali ulanish
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Google GenAI client muvaffaqiyatli yuklandi.")
        except Exception as e:
            logger.warning(f"google-genai orqali ulanishda xato ({e}), google.generativeai tekshirilmoqda...")
            try:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=self.api_key)
                self.client = "legacy"
                logger.info("Google GenerativeAI (legacy) muvaffaqiyatli sozlandi.")
            except Exception as e2:
                logger.error(f"Gemini kutubxonasini ishga tushirib bo'lmadi: {e2}")
                self.client = None

    async def generate_daily_digest(self, messages: List[Dict[str, Any]]) -> str:
        """
        Bazadagi so'nggi xabarlarni tahlil qilib, kunlik xulosa (AI Digest) tayyorlaydi.
        """
        if not messages:
            return "📭 So'nggi vaqt oralig'ida tahlil qilish uchun yangi xabarlar topilmadi."

        if not self.client:
            return "⚠️ Gemini API kaliti sozlanmagan. Iltimos, .env faylida GEMINI_API_KEY ni to'g'rilang."

        # Xabarlarni qulay matn shakliga keltirish
        formatted_messages = []
        for msg in messages:
            sender = msg.get("sender_username") or msg.get("sender_name") or f"ID:{msg.get('sender_id')}"
            chat = msg.get("chat_title") or "Shaxsiy chat"
            text = msg.get("text") or ""
            if msg.get("voice_transcript"):
                text += f" [Ovozli xabar transkripsiyasi: {msg.get('voice_transcript')}]"
            elif msg.get("media_type"):
                text += f" [{msg.get('media_type')} fayli yuborilgan]"
            
            date = msg.get("date", "")[:16].replace("T", " ")
            formatted_messages.append(f"[{date}] Kimdan: {sender} | Chat: {chat}\nXabar: {text}\n---")

        full_content = "\n".join(formatted_messages)

        prompt = f"""
Siz Telegram akkaunt egasining shaxsiy aqlli yordamchisisiz.
Quyida foydalanuvchining shaxsiy va guruh yozishmalaridagi so'nggi xabarlar keltirilgan:

{full_content}

Iltimos, ushbu xabarlar asosida o'zbek tilida tartibli, aniq va ixcham Kunlik AI Xulosa (Daily Digest) tayyorlang.
Javobingizni faqat quyidagi 3 bo'limga ajratib bering:

🚨 1. O'TA MUHIM:
(Shoshilinch e'tibor, pul, to'lov, kod, muhim ish masalasi yoki tezkor javob kutayotgan shaxslar. Kim yozganini @username yoki ism bilan ko'rsating)

📌 2. UMUMIY XULOSALAR:
(Guruhlar, kanallar va shaxsiy chatlardagi asosiy mavzular va yangiliklarning qisqacha mazmuni)

💡 3. E'TIBORDAN CHETDA QOLGANLAR:
(Oddiy, kundalik, salom-alik yoki ikkinchi darajali xabarlar qisqa formatda)

Qoidalar:
- Faqat berilgan xabarlarga tayaning, xomxayol qilmang.
- Foydalanuvchi vaqtini tejaydigan professional va tushunarli uslubda yozing.
"""

        try:
            return await self._call_gemini(prompt)
        except Exception as e:
            logger.error(f"AI Digest yaratishda xatolik: {e}")
            return f"❌ AI Digest tayyorlashda xatolik yuz berdi: {e}"

    async def summarize_dialog(self, user_info: str, messages: List[Dict[str, Any]]) -> str:
        """
        Aniq bir foydalanuvchi bilan bo'lgan yozishmalarni tahlil qilib xulosa berish (/summarize).
        """
        if not messages:
            return f"📭 {user_info} bilan yozishmalar bazada topilmadi."

        if not self.client:
            return "⚠️ Gemini API kaliti sozlanmagan (.env faylini tekshiring)."

        formatted_dialog = []
        for msg in messages:
            sender = "Men" if msg.get("is_outgoing") else (msg.get("sender_username") or msg.get("sender_name") or user_info)
            body = msg.get("voice_transcript") or msg.get("text") or (f"[{msg.get('media_type')} fayli]" if msg.get("media_type") else "")
            date_str = msg.get("date", "")[:16].replace("T", " ")
            if body:
                formatted_dialog.append(f"[{date_str}] {sender}: {body}")

        dialog_text = "\n".join(formatted_dialog)

        prompt = f"""
Siz Telegram shaxsiy foydalanuvchisining sun'iy intellekt yordamchisisiz.
Quyida foydalanuvchining {user_info} bilan bo'lib o'tgan so'nggi yozishmalari keltirilgan:

{dialog_text}

Iltimos, ushbu yozishmalarni diqqat bilan o'rganib, quyidagi formatda o'zbek tilida aniq, tushunarli va professional xulosa tayyorlang:

🎯 **ASOSIY MAVZU VA MAQSAD:**
(Suhbat nima haqida ketmoqda, suhbatdosh nima maqsadda yozgan)

📌 **MUHIM NUQTALAR VA KELISHUVLAR:**
(Muhokama qilingan asosiy faktlar, shartlar, sanalar yoki vazifalar)

⏳ **HOZIRGI STATUS VA KEYINGI QADAM:**
(Javob kutilayotgan savollar, keyingi rejalar)

Qoidalar:
- Faqat berilgan suhbatga tayaning.
- Qisqa, lo'nda va o'qishga qulay formatda yozing.
"""
        try:
            return await self._call_gemini(prompt)
        except Exception as e:
            logger.error(f"Xulosa yaratishda xato: {e}")
            return f"❌ Xulosa yaratishda xatolik yuz berdi: {e}"

    async def suggest_replies(self, user_info: str, last_message: str, recent_history: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Oxirgi kelgan xabarga qarab mos va muloyim javob variantlarini tayyorlash (/reply_suggest).
        """
        if not last_message:
            return f"⚠️ {user_info} dan oxirgi matnli xabar topilmadi."

        if not self.client:
            return "⚠️ Gemini API kaliti sozlanmagan (.env faylini tekshiring)."

        context_str = ""
        if recent_history:
            lines = []
            for m in recent_history[-6:]:
                s = "Men" if m.get("is_outgoing") else user_info
                t = m.get("voice_transcript") or m.get("text") or ""
                if t:
                    lines.append(f"{s}: {t}")
            if lines:
                context_str = "Suhbatning oldingi qisqa konteksti:\n" + "\n".join(lines) + "\n\n"

        prompt = f"""
Siz Telegram akkaunt egasining aqlli yordamchisisiz.
{context_str}Suhbatdosh ({user_info}) oxirgi marta quyidagi xabarni yubordi:
"{last_message}"

Foydalanuvchi nomidan unga javob qaytarish uchun 3 xil uslubda, tabiiy, muloyim va professional o'zbek tilida javob variantlarini tuzib bering:

1️⃣ **Ijobiy / Rozilik:**
(Taklifni qabul qilish yoki tasdiqlash)

2️⃣ **Muloyim rad etish / Keyinroqqa qoldirish:**
(Hozir bandlik yoki keyinroq javob berishini tushuntirish)

3️⃣ **Qisqa / Aniqlovchi savol:**
(Vaziyatni oydinlashtirish uchun ixcham javob)

Qoidalar:
- Javoblar insoniy va tabiiy bo'lsin.
- Matnlar nusxalashga qulay ajratilsin.
"""
        try:
            return await self._call_gemini(prompt)
        except Exception as e:
            logger.error(f"Javob tavsiyasi yaratishda xato: {e}")
            return f"❌ Javob variantlarini tayyorlashda xatolik: {e}"

    async def check_urgency(self, text: str, sender_info: str) -> Tuple[bool, str]:
        """
        Xabarning shoshilinch ekanligini baholash (tezkor ogohlantirish uchun).
        """
        if not text:
            return False, ""

        text_lower = text.lower()
        matched_keywords = [kw for kw in self.urgency_keywords if kw in text_lower]

        # Agar kalit so'zlar topilsa yoki matn qisqa bo'lsa, tezkor filtrlash
        if matched_keywords:
            reason = f"Kalit so'zlar aniqlandi: {', '.join(matched_keywords)}"
            return True, reason

        # Agar Gemini ulangan bo'lsa va matnda shubhali kontekst bo'lsa
        if self.client and len(text.strip()) > 15:
            prompt = f"""
Quyidagi Telegram xabarini shoshilinchlik nuqtai nazaridan baholang:
Yuboruvchi: {sender_info}
Matn: "{text}"

Bu xabar shoshilinch e'tibor talab qiladimi (masalan, favqulodda vaziyat, pul/bank xabari, tasdiqlash kodi, shoshilinch taklif)?
Javobni quyidagi formatda bering:
URGENT: YES yoki NO
REASON: Bir jumla bilan sababi (o'zbekcha)
"""
            try:
                res = await self._call_gemini(prompt)
                if "URGENT: YES" in res.upper():
                    reason_line = ""
                    for line in res.splitlines():
                        if line.upper().startswith("REASON:"):
                            reason_line = line.split(":", 1)[1].strip()
                    return True, reason_line or "AI tomonidan shoshilinch deb baholandi"
            except Exception as e:
                logger.debug(f"Urgency AI tekshiruvida xato: {e}")

        return False, ""

    async def transcribe_voice(self, file_path: str) -> Optional[str]:
        """
        Ovozli xabar (voice note / audio) ni Gemini yordamida matnga aylantirish.
        """
        if not self.client or not os.path.exists(file_path):
            return None

        prompt = (
            "Ushbu ovozli xabarni matnga o'giring (transkripsiya qiling). "
            "Faqat aytilgan gaplarni o'zbek, rus yoki ingliz tilida asliga muvofiq yozing. "
            "Hech qanday kirish yoki qo'shimcha so'z qo'shmang."
        )

        candidate_models = [self.model_name]
        for m in ["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]:
            if m not in candidate_models:
                candidate_models.append(m)

        uploaded = None
        try:
            if hasattr(self.client, "files"):
                uploaded = self.client.files.upload(file=file_path)
                for model in candidate_models:
                    try:
                        response = self.client.models.generate_content(
                            model=model,
                            contents=[uploaded, prompt]
                        )
                        if response and response.text:
                            return response.text.strip()
                    except Exception as model_err:
                        logger.warning(f"Model {model} transkripsiyasida xato ({model_err}), keyingisi tekshirilmoqda...")
                        continue
            elif self.client == "legacy":
                import google.generativeai as legacy_genai
                uploaded = legacy_genai.upload_file(path=file_path)
                for model in candidate_models:
                    try:
                        m_obj = legacy_genai.GenerativeModel(model)
                        response = m_obj.generate_content([uploaded, prompt])
                        if response and response.text:
                            return response.text.strip()
                    except Exception as model_err:
                        logger.warning(f"Legacy model {model} transkripsiyasida xato: {model_err}")
                        continue
        except Exception as e:
            logger.error(f"Ovozli xabarni transkripsiya qilishda xatolik: {e}")
        finally:
            if uploaded and hasattr(self.client, "files") and hasattr(uploaded, "name"):
                try:
                    self.client.files.delete(name=uploaded.name)
                except Exception:
                    pass

        return None

    async def check_spam(self, text: str, sender_info: str) -> Tuple[bool, str]:
        """
        Spam, reklama yoki firibgarlik xabarlarini aniqlash.
        """
        if not text or not self.client:
            return False, ""

        prompt = f"""
Telegramdagi ushbu xabar spam, reklama, kazino yoki firibgarlik (scam) ekanligini aniqlang:
Yuboruvchi: {sender_info}
Matn: "{text}"

Javob formati:
SPAM: YES yoki NO
REASON: Sababi (o'zbekcha qisqa)
"""
        try:
            res = await self._call_gemini(prompt)
            if "SPAM: YES" in res.upper():
                reason = ""
                for line in res.splitlines():
                    if line.upper().startswith("REASON:"):
                        reason = line.split(":", 1)[1].strip()
                return True, reason or "Spam deb baholandi"
        except Exception as e:
            logger.debug(f"Spam tekshiruvida xatolik: {e}")

        return False, ""

    async def generate_auto_reply(
        self,
        sender_name: str,
        message_text: str = "",
        context: Optional[List[Dict[str, Any]]] = None,
        custom_instructions: Optional[str] = None,
        owner_name: str = "",
        media_path: Optional[str] = None
    ) -> str:
        """
        Foydalanuvchining shaxsiy chatiga kelgan xabarga (matn yoki ovozli xabar)
        AI orqali avtomatik aqlli javob qaytarish.
        """
        if not self.client:
            return ""

        if not message_text and (not media_path or not os.path.exists(media_path)):
            return ""

        context_str = ""
        if context:
            lines = []
            for m in context[-6:]:
                s = "Men" if m.get("is_outgoing") else (m.get("sender_name") or sender_name)
                t = m.get("voice_transcript") or m.get("text") or ""
                if t:
                    lines.append(f"{s}: {t}")
            if lines:
                context_str = "Oldingi xabarlar konteksti:\n" + "\n".join(lines) + "\n\n"

        owner_info = f"{owner_name} nomidan" if owner_name else "Telegram akkaunt egasi nomidan"

        custom_block = ""
        if custom_instructions and custom_instructions.strip():
            custom_block = f"\nMAXSUS KO'RSATMA (EGASIDAN):\n{custom_instructions.strip()}\n"

        is_voice = bool(media_path and os.path.exists(media_path))
        if is_voice:
            if message_text:
                media_info = f"Suhbatdosh ({sender_name}) ovozli xabar yubordi. Undagi so'zlar: \"{message_text}\""
            else:
                media_info = f"Suhbatdosh ({sender_name}) ovozli xabar yubordi. Iltimos, biriktirilgan audio fayldagi gaplarni tinglab javob bering."
        else:
            media_info = f"Hozir sizga {sender_name} quyidagi xabarni yozdi:\n\"{message_text}\""

        prompt = f"""
Siz {owner_info} Telegramda kelgan xabarlarga javob beruvchi aqlli va samimiy shaxsiy AI yordamchisiz.

{context_str}{media_info}
{custom_block}
Vazifangiz:
Ushbu xabarga tabiiy, samimiy, insoniylikni saqlagan holda mos va to'g'ri javob bering.

Qoidalar:
1. Suhbatdosh qaysi tilda gapirgan/yozgan bo'lsa (o'zbek, rus, ingliz va h.k.), xuddi o'sha tilda javob qaytaring.
2. Javobingiz Telegram chatiga mos bo'lsin: ixcham, lo'nda, samimiy va ortiqcha cho'zmasdan.
3. Agar u salom bersa yoki oddiy hol-ahvol so'rasa, muloyim alik oling va nima yordam bera olishingizni bildiring.
4. Agar savol bersa, aniq va foydali javob bering.
5. Agar shaxsiy sir, parol, pul, to'lov yoki faqat {owner_name or 'akkaunt egasi'}ning o'zi hal qila oladigan muhim masala so'ralsa, siz AI yordamchisi ekanligingizni va xabarni unga yetkazishingizni, tez orada o'zi bog'lanishini muloyim tushuntiring.
6. Hech qachon o'zingizdan yolg'on fakt yoki quruq va'dalar to'qimang.
7. Faqat to'g'ridan-to'g'ri yuboriladigan javob matnini yozing. Hech qanday "Javob:", "Assistent:" yoki qo'shtirnoq kabi keraksiz so'zlarni qo'shmang.
"""

        uploaded = None
        try:
            contents = prompt
            # Agar audio fayl mavjud bo'lsa va matn transkripsiyasi bo'lmasa, audioni Gemini'ga yuklash
            if is_voice and not message_text and hasattr(self.client, "files"):
                uploaded = self.client.files.upload(file=media_path)
                contents = [uploaded, prompt]

            reply = await self._call_gemini_contents(contents)
            cleaned = reply.strip()
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1].strip()
            if cleaned.lower().startswith("javob:"):
                cleaned = cleaned[6:].strip()
            return cleaned
        except Exception as e:
            logger.error(f"Auto-reply yaratishda xatolik: {e}")
            return ""
        finally:
            if uploaded and hasattr(self.client, "files") and hasattr(uploaded, "name"):
                try:
                    self.client.files.delete(name=uploaded.name)
                except Exception:
                    pass

    async def _call_gemini(self, prompt: str) -> str:
        """Gemini modeliga matnli so'rov yuborish."""
        return await self._call_gemini_contents(prompt)

    async def _call_gemini_contents(self, contents: Any) -> str:
        """Gemini modeliga so'rov yuborish (avtomatik fallback va retry bilan)."""
        import asyncio
        working_fallbacks = [
            "gemini-3.1-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
        candidate_models = [self.model_name]
        for fallback in working_fallbacks:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for model in candidate_models:
            for attempt in range(2):
                try:
                    if hasattr(self.client, "models"):
                        response = self.client.models.generate_content(
                            model=model,
                            contents=contents
                        )
                        return response.text.strip() if response and response.text else ""
                    elif self.client == "legacy":
                        import google.generativeai as legacy_genai
                        m = legacy_genai.GenerativeModel(model)
                        response = m.generate_content(contents)
                        return response.text.strip() if response and response.text else ""
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if ("503" in err_str or "UNAVAILABLE" in err_str) and attempt == 0:
                        await asyncio.sleep(1.5)
                        continue
                    break

        if last_error:
            raise last_error
        return ""
