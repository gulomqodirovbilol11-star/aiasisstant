# 🤖 Telegram Shaxsiy AI Agent (Userbot)

Ushbu loyiha shaxsiy Telegram akkauntini avtomatlashtirish, barcha kiruvchi xabarlarni lokal bazaga yozib borish, **o'chirilgan xabarlar va medialarni ushlab qolib "Saved Messages"ga yetkazish**, shoshilinch xabarlarni saralash hamda **Google Gemini AI** orqali kunlik aqlli hisobotlar (AI Digest) tayyorlash uchun mo'ljallangan to'liq tizimdir.

---

## 🌟 Asosiy Imkoniyatlar

1. **🗑 O'chirilgan Xabarlar Nazorati (Anti-Delete Logger):**
   - Kimdir sizga yuborgan xabarini (matn, rasm, ovozli xabar yoki fayl) o'chirib tashlasa, agent darhol uni lokal bazadan topadi.
   - O'zingizning **Saved Messages** (Saqlangan xabarlar)ingizga o'chirilgan xabar matni, yuboruvchisi, vaqti va agar media bo'lsa o'sha faylni yuboradi.

2. **📑 Kunlik Aqlli AI Digest (Gemini AI):**
   - Har kuni belgilangan vaqtda (masalan, 21:00 yoki 22:00 da) so'nggi xabarlarni to'playdi.
   - Gemini modeli orqali 3 toifada tahlil qilingan hisobot beradi:
     - 🚨 **O'ta muhim:** Shoshilinch javob kutayotganlar, to'lovlar, kodlar.
     - 📌 **Umumiy xulosalar:** Guruh va chatlardagi asosiy yangiliklar.
     - 💡 **E'tibordan chetda qolganlar:** Qisqacha ikkinchi darajali mavzular.

3. **🚨 Tezkor Shoshilinchlik Filtri (Urgency Alert):**
   - Xabarda "muhim", "pul", "tasdiqlang", "kod", "tezda" kabi so'zlar yoki favqulodda vaziyat aniqlansa, kechki hisobotni kutmasdan darhol **Saved Messages**ga signal yuboradi.

4. **🎤 Ovozli Xabarlarni Transkripsiya Qilish:**
   - Kelgan voice va audio xabarlarni Gemini multimodal orqali avtomatik ravishda matnga o'girib bazada saqlaydi (o'chirilganda ham matni qoladi).

5. **👤 Yangi Chat va Kanal Xabarnomalari:**
   - Yangi foydalanuvchi birinchi marta yozganida xabardor qiladi.
   - Yangi guruh yoki kanallarga qo'shilganingizda (yoki kimdir sizni qo'shganda) bildirishnoma keladi.

6. **💬 AI Avtomatik Javob Berish (Auto-Reply):**
   - Shaxsiy chatga yangi xabar (matn yoki ovozli xabar) kelganda, Gemini AI sizning shaxsiy aqlli yordamchingiz sifatida avtomatik javob qaytaradi.
   - Suhbatdosh tilini tushunadi (o'zbek, rus, ingliz), avvalgi yozishmalar kontekstini hisobga oladi va tabiiy javob beradi.
   - O'zingiz xohlagan shaxsiyat yoki yo'riqnomani `/autoreply prompt [matn]` orqali istalgan payt kiritishingiz mumkin.

7. **🛡 Spam va Reklama Filtri:**
   - Shaxsiyga kelgan reklama, spam va fishing xabarlarni aniqlaydi va bunday xabarlarga avtojavob bermaydi.

8. **🎮 Masofaviy Boshqaruv (Saved Messages va Telegram Bot Buyruqlari):**
   - O'zingizning "Saved Messages"ingiz orqali yoki Telegram Bot orqali quyidagi buyruqlarni berishingiz mumkin:
     - **🧠 AI va Xulosalash:**
       - `/digest` — Bugungi barcha xabarlar tahlili va konspekti.
       - `/summarize @username` — Foydalanuvchi bilan bo'lgan yozishmalar xulosasi.
       - `/reply_suggest @username` — Oxirgi xabarga mos va muloyim 3 ta javob varianti.
     - **🗑 O'chirilgan Xabarlar va Audit:**
       - `/deleted [son]` — Oxirgi o'chirilgan xabarlar ro'yxati (masalan, `/deleted 10`).
       - `/deleted_by @username` — Aniq bir shaxs o'chirgan xabarlar tarixi.
       - `/clear_history [kun]` — Bazadagi eski xabarlarni tozalash (standart: 30 kun).
     - **👤 Kontaktlar va Profil Nazorati:**
       - `/whois @username` — Foydalanuvchi haqida to'liq dosye va statistika.
       - `/chats` — Sizga eng ko'p yozgan odamlar reytingi (Top-10).
       - `/unread` — O'qilmagan holatda qolib ketgan chatlar va kanallar.
     - **🛡 Avtomatlashtirish va Xavfsizlik:**
       - `/autoreply on` / `/autoreply off` — AI avtomatik javob berishini yoqish/o'chirish.
       - `/autoreply prompt [matn]` — AI qanday javob berishi bo'yicha maxsus ko'rsatma berish.
       - `/autoreply status` — Avtomatik javob holati va faol promptni ko'rish.
       - `/silent on` / `/silent off` — Tinchlik rejimi (faqat favqulodda muhim xabarlar keladi).
       - `/search [kalit so'z]` — Yozishmalar orasidan tezkor qidiruv.
       - `/blacklist add @username` / `/blacklist remove` / `/blacklist list` — Qora ro'yxatni boshqarish.
     - **⚙️ Tizim:**
       - `/status` — Tizim, baza, xotira va AI holati statistikasi.
       - `/send @foydalanuvchi Xabar matni` — Profil nomingizdan xabar yuborish.
       - `/help` — Buyruqlar bo'yicha to'liq qo'llanma.

---

## 🛠 Texnologik Stek

- **Til:** Python 3.11+
- **Telegram Client:** Telethon (MTProto Userbot)
- **AI Dvigateli:** Google Gemini API (`google-genai` / `google-generativeai`)
- **Ma'lumotlar Bazasi:** SQLite (`aiosqlite`) — asinxron va yengil
- **Vazifalar Rejalashtiruvchisi:** APScheduler (AsyncIOScheduler)

---

## 📁 Loyiha Tuzilishi

```
My AI Agent/
├── handlers/
│   ├── __init__.py
│   ├── messages.py       # Xabarlarni yozish, shoshilinchlik va ovoz tahlili
│   ├── deleted.py        # O'chirilgan xabarlarni ushlash va yuborish
│   ├── actions.py        # Yangi guruh va kanallarni monitoring qilish
│   └── commands.py       # Saved Messages masofaviy buyruqlari
├── storage/
│   └── media/            # Saqlab qolingan media fayllar
├── .env                  # API kalitlar va shaxsiy sozlamalar
├── .env.example          # Sozlamalar namunasi
├── ai_service.py         # Gemini AI integratsiyasi
├── database.py           # Asinxron ma'lumotlar bazasi
├── config.py             # Sozlamalar boshqaruvi
├── scheduler.py          # Kunlik hisobot rejalashtiruvchisi
├── main.py               # Asosiy ishga tushirish fayli
├── run.bat               # Windows uchun tezkor ishga tushiruvchi
├── run.sh                # Linux / macOS uchun skript
├── Dockerfile            # Docker sozlamasi
├── docker-compose.yml    # Docker Compose orqali 24/7 yurgizish
├── bot.service           # Linux systemd xizmati
└── requirements.txt      # Kutubxonalar ro'yxati
```

---

## 🚀 O'rnatish va Ishga Tushirish

### 1-qadam: Kerakli kalitlarni olish

1. **Telegram API ma'lumotlari:**
   - [my.telegram.org](https://my.telegram.org/) saytiga kiring.
   - Telefon raqamingiz orqali tizimga kiring.
   - **API development tools** bo'limiga o'tib, yangi dastur yarating (masalan, nomiga `MyUserbot`).
   - `api_id` va `api_hash` ma'lumotlarini nusxalab oling.

2. **Google Gemini API kaliti:**
   - [Google AI Studio](https://aistudio.google.com/) saytiga kiring.
   - **Get API Key** tugmasini bosib bepul API kalit yarating va nusxalang.

---

### 2-qadam: Sozlamalarni kiritish (.env)

Loyiha papkasidagi `.env` faylini oching va ma'lumotlaringizni kiriting:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef

GEMINI_API_KEY=AIzaSy...sizning_kalitingiz
GEMINI_MODEL=gemini-2.5-flash

DIGEST_TIME=21:00
TIMEZONE=Asia/Tashkent
```

---

### 3-qadam: Ishga tushirish

#### Windows tizimida:
Siz shunchaki `run.bat` faylini ikki marta bosib ishga tushirishingiz mumkin.
Yoki terminalda:
```powershell
.\venv\Scripts\python.exe main.py
```

#### Linux / macOS tizimida:
```bash
chmod +x run.sh
./run.sh
```

> **Birinchi marta kirish:**
> Terminalda Telegram akkauntingiz telefon raqami (masalan: `+998901234567`) va Telegram orqali kelgan tasdiqlash kodi so'raladi. Bir marta kirgach, sessiya fayli saqlanib qoladi va keyingi safar kod so'ramaydi.

---

## 🌐 Serverda 24/7 Ishlatish (VPS)

### Usul 1: Docker orqali
```bash
docker compose up -d
```

### Usul 2: Linux Systemd orqali (Tavsiya etiladi)
1. Loyihani VPS serverning `/opt/telegram-ai-agent` papkasiga yuklang.
2. `bot.service` faylini tizimga nusxalang:
   ```bash
   sudo cp bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable bot.service
   sudo systemctl start bot.service
   ```
3. Holatini tekshirish:
   ```bash
   sudo systemctl status bot.service
   ```

---

## 🔒 Xavfsizlik Eslatmasi

- `.session` va `.env` fayllarini hech qachon birovga bermang yoki GitHub'ga ommaviy yuklamang. Ushbu fayllar `.gitignore` ga kiritilgan.
- Masofaviy buyruqlar faqat o'zingizning "Saved Messages" chatida va faqat o'z hisobingizdan berilgandagina ishlaydi.
