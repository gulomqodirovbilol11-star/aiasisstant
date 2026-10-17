import os
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram API sozlamalari
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_SESSION_NAME: str = "my_agent_session"
    BOT_TOKEN: str = ""
    MY_TELEGRAM_ID: int = 0

    @field_validator("TELEGRAM_API_ID", "MY_TELEGRAM_ID", mode="before")
    @classmethod
    def parse_api_id(cls, v: Union[str, int]) -> int:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return 0
        try:
            return int(v)
        except Exception:
            return 0

    # Google Gemini AI sozlamalari
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"

    # Rejalashtiruvchi sozlamalari
    DIGEST_TIME: str = "21:00"
    TIMEZONE: str = "Asia/Tashkent"

    # Modullar faolligi
    ENABLE_MESSAGE_LOGGER: bool = True
    ENABLE_DELETED_MESSAGE_ALERT: bool = True
    ENABLE_NEW_CHAT_ALERT: bool = True
    ENABLE_URGENCY_ALERT: bool = True
    ENABLE_VOICE_TRANSCRIPTION: bool = True
    ENABLE_SPAM_FILTER: bool = True
    ENABLE_AUTO_REPLY: bool = True
    AUTO_REPLY_ONLY_PRIVATE: bool = True
    AUTO_REPLY_PREFIX: str = ""
    AUTO_REPLY_PROMPT: str = ""
    AUTO_REPLY_COOLDOWN_SECONDS: int = 3

    # Shoshilinchlik kalit so'zlari
    URGENCY_KEYWORDS: str = "muhim,tezda,pul,tasdiqlang,kod,sms,shoshilinch,urgent,parol,to'lov,alert,bank"

    # Saqlash yo'llari
    DATABASE_PATH: str = "./storage/agent.db"
    MEDIA_STORAGE_DIR: str = "./storage/media"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def urgency_keywords_list(self) -> List[str]:
        return [kw.strip().lower() for kw in self.URGENCY_KEYWORDS.split(",") if kw.strip()]

    @property
    def digest_hour_minute(self) -> tuple[int, int]:
        try:
            parts = self.DIGEST_TIME.split(":")
            return int(parts[0]), int(parts[1])
        except Exception:
            return 21, 0

    def ensure_directories(self) -> None:
        """Ma'lumotlar bazasi va media saqlash papkalarini yaratadi."""
        db_dir = Path(self.DATABASE_PATH).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        media_dir = Path(self.MEDIA_STORAGE_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)


config = Settings()
