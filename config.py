from dataclasses import dataclass
from typing import Set
import os

from dotenv import load_dotenv

# Загружаем .env один раз при импорте модуля
load_dotenv()


@dataclass
class Settings:
    bot_token: str
    admin_ids: Set[int]
    # Для обратной совместимости: старый код использует admin_chat_id
    admin_chat_id: int | None = None
    payments_provider_token: str | None = None

    # 🔹 Новые поля для проверки подписки на канал
    required_channel_id: str | None = None       # @username или -1001234567890
    required_channel_link: str | None = None     # https://t.me/username


def _load_admin_ids() -> Set[int]:
    """
    Считывает админов из переменных окружения:
    - ADMIN_CHAT_ID=123
    - ADMIN_CHAT_IDS=123,456,789
    Возвращает множество int.
    """
    ids: set[int] = set()

    # Старый вариант — один админ
    single_raw = os.getenv("ADMIN_CHAT_ID", "").strip()
    if single_raw:
        try:
            ids.add(int(single_raw))
        except ValueError:
            pass

    # Новый вариант — несколько админов через запятую
    list_raw = os.getenv("ADMIN_CHAT_IDS", "").strip()
    if list_raw:
        for part in list_raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                ids.add(int(part))
            except ValueError:
                continue

    return ids


# Глобальный набор админов — удобно использовать в хендлерах
ADMIN_IDS: Set[int] = _load_admin_ids()


def get_settings() -> Settings:
    """
    Возвращает объект настроек.
    Сохраняем:
    - bot_token
    - admin_ids (множество админов)
    - admin_chat_id (первый админ из списка, для старого кода)
    - payments_provider_token
    - required_channel_id / required_channel_link (для проверки подписки)
    """
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("Не найден BOT_TOKEN в .env")

    payments_token = os.getenv("PAYMENTS_PROVIDER_TOKEN") or None

    admin_ids = ADMIN_IDS or _load_admin_ids()

    # Для обратной совместимости: берём первого админа из множества
    admin_chat_id: int | None = None
    for _id in admin_ids:
        admin_chat_id = _id
        break

    # 🔹 Канал, на который нужно быть подписанным
    channel_id = os.getenv("REQUIRED_CHANNEL_ID", "").strip() or None
    channel_link = os.getenv("REQUIRED_CHANNEL_LINK", "").strip() or None

    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        admin_chat_id=admin_chat_id,
        payments_provider_token=payments_token,
        required_channel_id=channel_id,
        required_channel_link=channel_link,
    )
