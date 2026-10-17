import os
import aiosqlite
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Ma'lumotlar bazasi jadvallarini yaratish va indekslarni sozlash."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            
            # Xabarlar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    sender_id INTEGER,
                    sender_username TEXT,
                    sender_name TEXT,
                    chat_title TEXT,
                    chat_type TEXT,
                    text TEXT,
                    media_type TEXT,
                    media_path TEXT,
                    voice_transcript TEXT,
                    is_outgoing INTEGER DEFAULT 0,
                    is_read INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0,
                    date TEXT NOT NULL,
                    deleted_at TEXT,
                    UNIQUE(chat_id, message_id)
                );
            """)

            # Foydalanuvchilar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    first_seen TEXT,
                    last_seen TEXT
                );
            """)

            # Chatlar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    username TEXT,
                    chat_type TEXT,
                    first_seen TEXT,
                    last_seen TEXT
                );
            """)

            # Qora ro'yxat (Blacklist) jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    username TEXT UNIQUE,
                    reason TEXT,
                    added_at TEXT
                );
            """)

            # Tizim sozlamalari (Settings) jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

            # Indekslar
            await db.execute("CREATE INDEX IF NOT EXISTS idx_chat_msg ON messages(chat_id, message_id);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_date ON messages(date);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_deleted ON messages(is_deleted);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sender_id ON messages(sender_id);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sender_username ON messages(sender_username);")
            await db.commit()

    async def save_message(
        self,
        message_id: int,
        chat_id: int,
        sender_id: Optional[int],
        sender_username: Optional[str],
        sender_name: Optional[str],
        chat_title: Optional[str],
        chat_type: str,
        text: Optional[str],
        media_type: Optional[str],
        media_path: Optional[str],
        date: datetime,
        is_outgoing: bool = False,
        voice_transcript: Optional[str] = None
    ) -> None:
        """Yangi xabarni bazaga yozish yoki yangilash."""
        date_str = date.isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO messages (
                    message_id, chat_id, sender_id, sender_username, sender_name,
                    chat_title, chat_type, text, media_type, media_path,
                    voice_transcript, is_outgoing, is_read, is_deleted, date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                ON CONFLICT(chat_id, message_id) DO UPDATE SET
                    text = excluded.text,
                    media_path = coalesce(excluded.media_path, messages.media_path),
                    voice_transcript = coalesce(excluded.voice_transcript, messages.voice_transcript);
            """, (
                message_id, chat_id, sender_id, sender_username, sender_name,
                chat_title, chat_type, text or "", media_type, media_path,
                voice_transcript, 1 if is_outgoing else 0, date_str
            ))
            await db.commit()

    async def update_voice_transcript(self, chat_id: int, message_id: int, transcript: str) -> None:
        """Ovozli xabar transkripsiyasini saqlash."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE messages
                SET voice_transcript = ?
                WHERE chat_id = ? AND message_id = ?;
            """, (transcript, chat_id, message_id))
            await db.commit()

    async def find_and_mark_deleted(self, message_ids: List[int], chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """O'chirilgan xabarlarni topish va ularni is_deleted = 1 qilib belgilash."""
        if not message_ids:
            return []
        
        now_str = datetime.now(timezone.utc).isoformat()
        placeholders = ",".join("?" for _ in message_ids)
        params: List[Any] = list(message_ids)

        query = f"""
            SELECT id, message_id, chat_id, sender_id, sender_username, sender_name,
                   chat_title, chat_type, text, media_type, media_path, voice_transcript,
                   is_outgoing, date
            FROM messages
            WHERE message_id IN ({placeholders}) AND is_deleted = 0
        """
        if chat_id is not None:
            query += " AND chat_id = ?"
            params.append(chat_id)

        found = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    found.append(dict(row))

            if found:
                mark_query = f"""
                    UPDATE messages
                    SET is_deleted = 1, deleted_at = ?
                    WHERE message_id IN ({placeholders})
                """
                mark_params: List[Any] = [now_str] + list(message_ids)
                if chat_id is not None:
                    mark_query += " AND chat_id = ?"
                    mark_params.append(chat_id)

                await db.execute(mark_query, mark_params)
                await db.commit()

        return found

    async def is_first_time_user(self, user_id: int) -> bool:
        """Foydalanuvchi birinchi marta yozayotganini tekshirish."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row is None

    async def upsert_user(self, user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]) -> None:
        """Foydalanuvchi ma'lumotlarini kiritish yoki yangilash."""
        now_str = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_seen = excluded.last_seen;
            """, (user_id, username, first_name, last_name, now_str, now_str))
            await db.commit()

    async def upsert_chat(self, chat_id: int, title: Optional[str], username: Optional[str], chat_type: str) -> None:
        """Chat ma'lumotlarini kiritish yoki yangilash."""
        now_str = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO chats (chat_id, title, username, chat_type, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = excluded.title,
                    username = excluded.username,
                    chat_type = excluded.chat_type,
                    last_seen = excluded.last_seen;
            """, (chat_id, title, username, chat_type, now_str, now_str))
            await db.commit()

    async def get_messages_for_digest(self, since_iso: str) -> List[Dict[str, Any]]:
        """AI Digest uchun ma'lum vaqtdan keyingi kiruvchi xabarlarni olish."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT message_id, chat_id, sender_id, sender_username, sender_name,
                       chat_title, chat_type, text, media_type, voice_transcript, date
                FROM messages
                WHERE date >= ? AND is_outgoing = 0
                ORDER BY date ASC
                LIMIT 500
            """, (since_iso,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_recent_deleted_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Oxirgi o'chirilgan xabarlarni olish (/deleted buyrug'i uchun)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT message_id, chat_id, sender_id, sender_username, sender_name,
                       chat_title, chat_type, text, media_type, media_path, voice_transcript,
                       date, deleted_at
                FROM messages
                WHERE is_deleted = 1
                ORDER BY deleted_at DESC, id DESC
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_deleted_messages_by_user(self, user_identifier: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Faqat ma'lum bir foydalanuvchi o'chirgan xabarlarni olish (/deleted_by uchun)."""
        clean = user_identifier.lstrip("@").lower().strip()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if clean.isdigit():
                query = """
                    SELECT message_id, chat_id, sender_id, sender_username, sender_name,
                           chat_title, chat_type, text, media_type, voice_transcript, date, deleted_at
                    FROM messages
                    WHERE is_deleted = 1 AND (sender_id = ? OR chat_id = ?)
                    ORDER BY id DESC
                    LIMIT ?
                """
                params = (int(clean), int(clean), limit)
            else:
                query = """
                    SELECT message_id, chat_id, sender_id, sender_username, sender_name,
                           chat_title, chat_type, text, media_type, voice_transcript, date, deleted_at
                    FROM messages
                    WHERE is_deleted = 1 AND (lower(sender_username) = ? OR lower(sender_name) LIKE ?)
                    ORDER BY id DESC
                    LIMIT ?
                """
                params = (clean, f"%{clean}%", limit)

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def clear_old_messages(self, days: int = 30) -> int:
        """Eski xabarlarni o'chirish va bo'sh joyni tozalash (/clear_history uchun)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM messages WHERE date < ?", (cutoff,))
            deleted_count = cursor.rowcount
            await db.commit()
            try:
                await db.execute("VACUUM;")
            except Exception:
                pass
            return deleted_count

    async def is_silent_mode(self) -> bool:
        """Tinchlik rejimi holatini tekshirish (/silent)."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = 'silent_mode'") as cursor:
                row = await cursor.fetchone()
                return bool(row and row[0] == "1")

    async def set_silent_mode(self, enabled: bool) -> None:
        """Tinchlik rejimini yoqish yoki o'chirish."""
        val = "1" if enabled else "0"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO settings (key, value) VALUES ('silent_mode', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (val,))
            await db.commit()

    async def is_auto_reply_enabled(self) -> bool:
        """AI avtomatik javob berish rejimi holatini tekshirish (/autoreply)."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = 'auto_reply_mode'") as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    return bool(row[0] == "1")
        from config import config
        return config.ENABLE_AUTO_REPLY

    async def set_auto_reply_enabled(self, enabled: bool) -> None:
        """AI avtomatik javob berish rejimini yoqish yoki o'chirish."""
        val = "1" if enabled else "0"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO settings (key, value) VALUES ('auto_reply_mode', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (val,))
            await db.commit()

    async def get_auto_reply_prompt(self) -> Optional[str]:
        """Maxsus AI avtomatik javob promptini olish."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = 'auto_reply_prompt'") as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
        from config import config
        return config.AUTO_REPLY_PROMPT or None

    async def set_auto_reply_prompt(self, prompt: Optional[str]) -> None:
        """Maxsus AI avtomatik javob promptini saqlash yoki tozalash."""
        async with aiosqlite.connect(self.db_path) as db:
            if prompt and prompt.strip():
                await db.execute("""
                    INSERT INTO settings (key, value) VALUES ('auto_reply_prompt', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                """, (prompt.strip(),))
            else:
                await db.execute("DELETE FROM settings WHERE key = 'auto_reply_prompt';")
            await db.commit()

    async def add_to_blacklist(self, user_id: Optional[int], username: Optional[str], reason: str = "") -> Tuple[bool, str]:
        """Foydalanuvchini qora ro'yxatga kiritish (/blacklist add)."""
        now_str = datetime.now(timezone.utc).isoformat()
        clean_user = username.lstrip("@").lower().strip() if username else None

        # Agar user_id noma'lum bo'lsa, bazadan tekshirish
        if not user_id and clean_user:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT user_id FROM users WHERE lower(username) = ?", (clean_user,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        user_id = row[0]
                if not user_id:
                    async with db.execute("SELECT sender_id FROM messages WHERE lower(sender_username) = ? LIMIT 1", (clean_user,)) as cursor:
                        row = await cursor.fetchone()
                        if row and row[0]:
                            user_id = row[0]

        async with aiosqlite.connect(self.db_path) as db:
            try:
                if user_id:
                    await db.execute("""
                        INSERT INTO blacklist (user_id, username, reason, added_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            username = coalesce(excluded.username, blacklist.username),
                            reason = excluded.reason,
                            added_at = excluded.added_at;
                    """, (user_id, clean_user, reason, now_str))
                else:
                    await db.execute("""
                        INSERT INTO blacklist (user_id, username, reason, added_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(username) DO UPDATE SET
                            user_id = coalesce(excluded.user_id, blacklist.user_id),
                            reason = excluded.reason,
                            added_at = excluded.added_at;
                    """, (None, clean_user, reason, now_str))
                await db.commit()
                return True, f"@{clean_user}" if clean_user else f"ID:{user_id}"
            except Exception as e:
                return False, str(e)

    async def remove_from_blacklist(self, identifier: str) -> bool:
        """Foydalanuvchini qora ro'yxatdan chiqarish (/blacklist remove)."""
        clean = identifier.lstrip("@").lower().strip()
        async with aiosqlite.connect(self.db_path) as db:
            if clean.isdigit():
                cursor = await db.execute("DELETE FROM blacklist WHERE user_id = ?", (int(clean),))
            else:
                cursor = await db.execute("DELETE FROM blacklist WHERE lower(username) = ?", (clean,))
            await db.commit()
            return cursor.rowcount > 0

    async def get_blacklist(self) -> List[Dict[str, Any]]:
        """Qora ro'yxatdagi akkauntlarni olish."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id, user_id, username, reason, added_at FROM blacklist ORDER BY id DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def is_blacklisted(self, user_id: Optional[int] = None, username: Optional[str] = None) -> bool:
        """Akkaunt qora ro'yxatda bor-yo'qligini tekshirish."""
        clean_user = username.lstrip("@").lower().strip() if username else None
        async with aiosqlite.connect(self.db_path) as db:
            if user_id and clean_user:
                query = "SELECT 1 FROM blacklist WHERE user_id = ? OR lower(username) = ?"
                params = (user_id, clean_user)
            elif user_id:
                query = "SELECT 1 FROM blacklist WHERE user_id = ?"
                params = (user_id,)
            elif clean_user:
                query = "SELECT 1 FROM blacklist WHERE lower(username) = ?"
                params = (clean_user,)
            else:
                return False

            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def get_user_stats(self, user_identifier: str) -> Optional[Dict[str, Any]]:
        """Foydalanuvchi statistikasi (/whois buyrug'i uchun)."""
        clean = user_identifier.lstrip("@").lower().strip()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            user_row = None
            if clean.isdigit():
                async with db.execute("SELECT * FROM users WHERE user_id = ?", (int(clean),)) as cur:
                    user_row = await cur.fetchone()
            else:
                async with db.execute("SELECT * FROM users WHERE lower(username) = ? OR lower(first_name) LIKE ?", (clean, f"%{clean}%")) as cur:
                    user_row = await cur.fetchone()

            target_sender_id = None
            username = clean if not clean.isdigit() else None
            name = None
            first_seen = None
            last_seen = None

            if user_row:
                user_dict = dict(user_row)
                target_sender_id = user_dict["user_id"]
                username = user_dict.get("username")
                name = f"{user_dict.get('first_name') or ''} {user_dict.get('last_name') or ''}".strip()
                first_seen = user_dict.get("first_seen")
                last_seen = user_dict.get("last_seen")
            else:
                if clean.isdigit():
                    q = "SELECT sender_id, sender_username, sender_name, min(date) as min_d, max(date) as max_d FROM messages WHERE sender_id = ? GROUP BY sender_id"
                    p = (int(clean),)
                else:
                    q = "SELECT sender_id, sender_username, sender_name, min(date) as min_d, max(date) as max_d FROM messages WHERE lower(sender_username) = ? GROUP BY sender_id"
                    p = (clean,)
                async with db.execute(q, p) as cur:
                    r = await cur.fetchone()
                    if r:
                        target_sender_id = r["sender_id"]
                        username = r["sender_username"]
                        name = r["sender_name"]
                        first_seen = r["min_d"]
                        last_seen = r["max_d"]

            if not target_sender_id and not username:
                return None

            incoming_count = 0
            outgoing_count = 0
            deleted_count = 0

            if target_sender_id:
                async with db.execute("SELECT count(*) FROM messages WHERE sender_id = ? AND is_outgoing = 0", (target_sender_id,)) as cur:
                    incoming_count = (await cur.fetchone())[0]
                async with db.execute("SELECT count(*) FROM messages WHERE chat_id = ? AND is_outgoing = 1", (target_sender_id,)) as cur:
                    outgoing_count = (await cur.fetchone())[0]
                async with db.execute("SELECT count(*) FROM messages WHERE sender_id = ? AND is_deleted = 1", (target_sender_id,)) as cur:
                    deleted_count = (await cur.fetchone())[0]
                async with db.execute("SELECT min(date), max(date) FROM messages WHERE sender_id = ? OR chat_id = ?", (target_sender_id, target_sender_id)) as cur:
                    dates = await cur.fetchone()
                    if dates and dates[0]:
                        first_seen = first_seen or dates[0]
                        last_seen = last_seen or dates[1]
            else:
                async with db.execute("SELECT count(*) FROM messages WHERE lower(sender_username) = ? AND is_outgoing = 0", (username.lower(),)) as cur:
                    incoming_count = (await cur.fetchone())[0]
                async with db.execute("SELECT count(*) FROM messages WHERE lower(sender_username) = ? AND is_deleted = 1", (username.lower(),)) as cur:
                    deleted_count = (await cur.fetchone())[0]

            return {
                "user_id": target_sender_id,
                "username": username,
                "name": name or "Noma'lum",
                "first_seen": first_seen,
                "last_seen": last_seen,
                "incoming_count": incoming_count,
                "outgoing_count": outgoing_count,
                "deleted_count": deleted_count
            }

    async def get_top_chatted_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Sizga eng ko'p yozgan odamlar reytingi (/chats)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT sender_id, sender_username, sender_name, chat_title,
                       count(*) as msg_count,
                       max(date) as last_activity
                FROM messages
                WHERE is_outgoing = 0 AND sender_id IS NOT NULL
                GROUP BY sender_id
                ORDER BY msg_count DESC
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def search_messages(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Yozishmalar orasidan qidiruv (/search)."""
        clean_q = f"%{query.strip()}%"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT message_id, chat_id, sender_id, sender_username, sender_name,
                       chat_title, chat_type, text, voice_transcript, is_outgoing, date
                FROM messages
                WHERE text LIKE ? OR voice_transcript LIKE ?
                ORDER BY date DESC
                LIMIT ?
            """, (clean_q, clean_q, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_user_dialog_messages(self, user_identifier: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Biror kontakt bilan bo'lgan oxirgi yozishmalar (/summarize va /reply_suggest uchun)."""
        clean = user_identifier.lstrip("@").lower().strip()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if clean.isdigit():
                query = """
                    SELECT message_id, chat_id, sender_id, sender_username, sender_name,
                           text, voice_transcript, is_outgoing, date
                    FROM messages
                    WHERE chat_id = ? OR sender_id = ?
                    ORDER BY date DESC
                    LIMIT ?
                """
                params = (int(clean), int(clean), limit)
            else:
                query = """
                    SELECT message_id, chat_id, sender_id, sender_username, sender_name,
                           text, voice_transcript, is_outgoing, date
                    FROM messages
                    WHERE lower(sender_username) = ? OR lower(sender_name) LIKE ?
                    ORDER BY date DESC
                    LIMIT ?
                """
                params = (clean, f"%{clean}%", limit)

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                res = [dict(r) for r in rows]
                res.reverse()
                return res

    async def get_stats(self) -> Dict[str, Any]:
        """Tizim statistikasi (/status buyrug'i uchun)."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT count(*) FROM messages") as cursor:
                total_messages = (await cursor.fetchone())[0]
            async with db.execute("SELECT count(*) FROM messages WHERE is_deleted = 1") as cursor:
                deleted_messages = (await cursor.fetchone())[0]
            async with db.execute("SELECT count(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
            async with db.execute("SELECT count(*) FROM chats") as cursor:
                total_chats = (await cursor.fetchone())[0]
            async with db.execute("SELECT count(*) FROM blacklist") as cursor:
                blacklisted_count = (await cursor.fetchone())[0]
            silent_mode = await self.is_silent_mode()
            auto_reply_mode = await self.is_auto_reply_enabled()

        db_size_mb = 0.0
        if os.path.exists(self.db_path):
            db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)

        return {
            "total_messages": total_messages,
            "deleted_messages": deleted_messages,
            "total_users": total_users,
            "total_chats": total_chats,
            "blacklisted_count": blacklisted_count,
            "silent_mode": silent_mode,
            "auto_reply_mode": auto_reply_mode,
            "db_size_mb": round(db_size_mb, 2)
        }
