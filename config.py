from dataclasses import dataclass
from typing import Set
import os

from dotenv import load_dotenv

# Загружаем .env один раз при импорте модуля
load_dotenv()

# 🔹 Канал для проверки обязательной подписки
# Укажите username канала (с @) или установите в None, чтобы отключить проверку.
REQUIRED_CHANNEL_USERNAME = os.getenv("REQUIRED_CHANNEL_USERNAME")
REQUIRED_CHANNEL_ID = os.getenv("REQUIRED_CHANNEL_ID")

if REQUIRED_CHANNEL_USERNAME:
    normalized_username = REQUIRED_CHANNEL_USERNAME.strip()
    if normalized_username.startswith("@"):
        normalized_username = normalized_username[1:]
    REQUIRED_CHANNEL_USERNAME = normalized_username or None

if REQUIRED_CHANNEL_ID:
    REQUIRED_CHANNEL_ID = REQUIRED_CHANNEL_ID.strip() or None

if REQUIRED_CHANNEL_ID:
    try:
        REQUIRED_CHANNEL_ID = int(REQUIRED_CHANNEL_ID)
    except ValueError:
        REQUIRED_CHANNEL_ID = None


@dataclass
class Settings:
    bot_token: str
    admin_ids: Set[int]
    # Для обратной совместимости: старый код использует admin_chat_id
    admin_chat_id: int | None = None
    payments_provider_token: str | None = None

    # 🔹 Новые поля для проверки подписки на канал
    required_channel_id: int | str | None = None  # username без @ или -1001234567890
    required_channel_link: str | None = None     # https://t.me/username

    # 🔹 Баннеры
    start_banner_id: str | None = None  # file_id или URL
    banner_start: str | None = None
    banner_courses: str | None = None
    banner_baskets: str | None = None
    banner_profile: str | None = None


def _load_admin_ids() -> list[int]:
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

    return list(ids)


# Глобальный список админов — удобно использовать в хендлерах
ADMIN_IDS: list[int] = _load_admin_ids()
# Для быстрого поиска оставляем и множество
ADMIN_IDS_SET: Set[int] = set(ADMIN_IDS)


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

    admin_ids = set(ADMIN_IDS) or set(_load_admin_ids())

    # Для обратной совместимости: берём первого админа из множества
    admin_chat_id: int | None = None
    for _id in admin_ids:
        admin_chat_id = _id
        break

    # 🔹 Канал, на который нужно быть подписанным
    channel_link = os.getenv("REQUIRED_CHANNEL_LINK", "").strip() or None

    channel_id: int | str | None = None
    if REQUIRED_CHANNEL_ID is not None:
        channel_id = REQUIRED_CHANNEL_ID
    elif REQUIRED_CHANNEL_USERNAME:
        channel_id = REQUIRED_CHANNEL_USERNAME

    if not channel_link and REQUIRED_CHANNEL_USERNAME:
        channel_link = f"https://t.me/{REQUIRED_CHANNEL_USERNAME}"

    # 🔹 Баннеры (file_id или URL)
    start_banner_id = os.getenv("START_BANNER_ID") or None
    banner_start = os.getenv("BANNER_START") or start_banner_id
    banner_courses = os.getenv("BANNER_COURSES") or None
    banner_baskets = os.getenv("BANNER_BASKETS") or None
    banner_profile = os.getenv("BANNER_PROFILE") or None

    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        admin_chat_id=admin_chat_id,
        payments_provider_token=payments_token,
        required_channel_id=channel_id,
        required_channel_link=channel_link,
        start_banner_id=start_banner_id,
        banner_start=banner_start,
        banner_courses=banner_courses,
        banner_baskets=banner_baskets,
        banner_profile=banner_profile,
    )
