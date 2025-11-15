from dataclasses import dataclass
from dotenv import load_dotenv
import os


@dataclass
class Settings:
    bot_token: str
    admin_chat_id: int | None = None
    payments_provider_token: str | None = None


def get_settings() -> Settings:
    load_dotenv()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("Не найден BOT_TOKEN в .env")

    admin_chat_id_raw = os.getenv("ADMIN_CHAT_ID")
    admin_chat_id = int(admin_chat_id_raw) if admin_chat_id_raw else None

    payments_token = os.getenv("PAYMENTS_PROVIDER_TOKEN") or None

    return Settings(
        bot_token=token,
        admin_chat_id=admin_chat_id,
        payments_provider_token=payments_token,
    )
