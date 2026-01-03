import asyncio
import logging
import os
import re

from aiogram import Router, types, F
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from aiohttp import ClientError

from config import ADMIN_IDS, ADMIN_IDS_SET, get_settings
from database import get_session
from models import AuthSession, User, UserState, UserTag, UserVar
from services import users as users_service
from services.bot_config import (
    BotTriggerView,
    MenuButtonView,
    NodeButtonView,
    NodeView,
    cache_node_image_file_id,
    get_start_node_code,
    load_button,
    load_menu_buttons,
    load_node,
    load_triggers,
    persist_node_image_file_id,
)
from services.bot_logging import (
    log_action_event,
    log_error_event,
    log_node_event,
    log_trigger_event,
)
from services.subscription import (
    ensure_subscribed,
    get_subscription_keyboard,
    check_channels_subscription,
    is_user_subscribed,
)
from keyboards.main_menu import get_main_menu
from utils.texts import format_start_text, format_subscription_required_text


BASE_ORIGIN = (os.getenv("BASE_URL") or os.getenv("API_URL") or "http://localhost:8000").rstrip("/")
if BASE_ORIGIN.endswith("/api"):
    BASE_ORIGIN = BASE_ORIGIN[: -len("/api")]


def _to_absolute_media(url: str | None) -> str | None:
    if not url:
        return None

    cleaned = url.strip()
    if cleaned.startswith("/media/"):
        return f"{BASE_ORIGIN}{cleaned}"

    return cleaned

router = Router()


VAR_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
logger = logging.getLogger(__name__)

BOT_MESSAGE_LIMIT = 50


async def _safe_answer(message: types.Message, text: str, **kwargs) -> types.Message | None:
    try:
        return await message.answer(text, **kwargs)
    except (TelegramNetworkError, ClientError, asyncio.TimeoutError):
        logger.warning(
            "Не удалось отправить сообщение из-за сетевой ошибки Telegram", exc_info=True
        )
        return None


async def _safe_answer_photo(
    message: types.Message,
    *,
    fallback_text: str | None = None,
    retry_delays: tuple[float, ...] = (0.5, 1.5),
    **kwargs,
) -> types.Message | None:
    last_exception: Exception | None = None

    for attempt, delay in enumerate((0.0, *retry_delays), start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await message.answer_photo(**kwargs)
        except (TelegramNetworkError, ClientError, asyncio.TimeoutError) as exc:
            last_exception = exc
            logger.warning(
                "Не удалось отправить фото из-за сетевой ошибки Telegram (попытка %s)",
                attempt,
                exc_info=True,
            )
            continue

    if fallback_text is not None:
        logger.warning(
            "Переключаемся на текстовый ответ из-за ошибки отправки фото: %s",
            last_exception,
        )
        return await _safe_answer(
            message,
            fallback_text,
            reply_markup=kwargs.get("reply_markup"),
            parse_mode=kwargs.get("parse_mode"),
        )

    return None


def _get_tracked_messages(user_id: int) -> list[dict[str, int]]:
    with get_session() as session:
        state = session.get(UserState, user_id)
        if not state or not isinstance(state.bot_message_ids, list):
            return []

        result: list[dict[str, int]] = []
        for item in state.bot_message_ids:
            if not isinstance(item, dict):
                continue
            message_id = item.get("message_id")
            chat_id = item.get("chat_id")
            if message_id is None:
                continue
            try:
                normalized_chat_id = int(chat_id) if chat_id is not None else None
                normalized_message_id = int(message_id)
            except Exception:
                continue

            result.append(
                {
                    "chat_id": normalized_chat_id or 0,
                    "message_id": normalized_message_id,
                }
            )
        return result


def _save_tracked_messages(user_id: int, messages: list[dict[str, int]]) -> None:
    normalized = [
        {
            "chat_id": int(item.get("chat_id") or 0),
            "message_id": int(item.get("message_id") or 0),
        }
        for item in messages
        if item.get("message_id")
    ]

    with get_session() as session:
        state = session.get(UserState, user_id)
        if not state:
            state = UserState(user_id=user_id)
        state.bot_message_ids = normalized[-BOT_MESSAGE_LIMIT:]
        session.add(state)


def _remember_bot_message(user_id: int, bot_message: types.Message | None) -> None:
    if not bot_message:
        return

    tracked = _get_tracked_messages(user_id)
    tracked.append(
        {
            "chat_id": bot_message.chat.id if bot_message.chat else 0,
            "message_id": bot_message.message_id,
        }
    )
    _save_tracked_messages(user_id, tracked)


async def _clear_previous_bot_messages(message: types.Message) -> None:
    tracked = _get_tracked_messages(message.from_user.id)
    if not tracked:
        return

    for item in tracked:
        try:
            await message.bot.delete_message(
                chat_id=item.get("chat_id") or message.chat.id,
                message_id=item.get("message_id"),
            )
        except Exception:
            continue

    _save_tracked_messages(message.from_user.id, [])


def _extract_node_code_from_payload(raw_payload: str | None) -> tuple[str | None, str]:
    if not raw_payload:
        return None, "payload_is_empty"

    normalized = raw_payload.strip()
    if not normalized.upper().startswith("OPEN_NODE"):
        return None, "payload_not_open_node"

    parts = re.split(r"[:\s]+", normalized, maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return None, "node_code_missing"

    return parts[1].strip(), ""


async def _answer_and_track(message: types.Message, text: str, **kwargs):
    sent = await _safe_answer(message, text, **kwargs)
    if not sent:
        return None

    _remember_bot_message(message.from_user.id, sent)
    return sent


async def _apply_reply_keyboard(message: types.Message, keyboard: ReplyKeyboardMarkup | None):
    if not keyboard:
        return None

    return await _answer_and_track(message, "\u2060", reply_markup=keyboard)


async def _dispatch_button_action(message: types.Message, button: NodeButtonView) -> None:
    action_type = (button.action_type or "").upper()
    payload = (button.action_payload or "").strip()

    if action_type == "NODE":
        target_code = button.target_node_code or payload
        if target_code:
            await _open_node_with_fallback(message, target_code)
        else:
            await _answer_and_track(message, "Узел для перехода не настроен.")
        return

    if action_type == "COMMAND":
        if payload:
            handled = await _process_triggers(message, text_override=payload)
            if handled:
                return
        await _answer_and_track(message, "Команда недоступна или не настроена.")
        return

    if action_type in {"URL", "WEBAPP"}:
        target_url = button.url or button.webapp_url or payload
        if not target_url:
            await _answer_and_track(message, "Ссылка недоступна.")
            return

        inline_button = (
            InlineKeyboardButton(text=button.text, url=target_url)
            if action_type == "URL"
            else InlineKeyboardButton(text=button.text, web_app=WebAppInfo(url=target_url))
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[[inline_button]])
        await _answer_and_track(message, "Открыть ссылку", reply_markup=markup)
        return

    if action_type == "BACK":
        await _answer_and_track(message, "Возврат невозможен из этого раздела.")
        return

    logger.warning(
        "Unknown node button action",
        extra={
            "user_id": message.from_user.id if message.from_user else None,
            "button_id": button.id,
            "button_text": button.text,
            "action_type": action_type,
            "payload": payload,
        },
    )
    await _answer_and_track(message, "Действие временно недоступно.")


async def _dispatch_menu_button(message: types.Message, button: MenuButtonView) -> bool:
    action_type = (button.action_type or "").upper()
    payload = (button.action_payload or "").strip()

    if action_type == "NODE":
        if payload:
            await _open_node_with_fallback(message, payload)
        else:
            await _answer_and_track(message, "Узел для перехода не настроен.")
        return True

    if action_type == "COMMAND":
        if payload:
            handled = await _process_triggers(message, text_override=payload)
            if handled:
                return True
        await _answer_and_track(message, "Команда недоступна или не настроена.")
        return True

    if action_type in {"URL", "WEBAPP"}:
        if not payload:
            await _answer_and_track(message, "Ссылка недоступна.")
            return True
        inline_button = (
            InlineKeyboardButton(text=button.text, url=payload)
            if action_type == "URL"
            else InlineKeyboardButton(text=button.text, web_app=WebAppInfo(url=payload))
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[[inline_button]])
        await _answer_and_track(message, "Открыть ссылку", reply_markup=markup)
        return True

    logger.warning(
        "Unknown menu button action",
        extra={
            "user_id": message.from_user.id if message.from_user else None,
            "button_text": button.text,
            "action_type": action_type,
            "payload": payload,
        },
    )
    await _answer_and_track(message, "Действие временно недоступно.")
    return True


async def _send_subscription_invite(target_message) -> None:
    await _answer_and_track(
        target_message,
        format_subscription_required_text(),
        reply_markup=get_subscription_keyboard(),
    )


def _is_subscription_condition(node: NodeView | None) -> bool:
    return bool(node and (node.condition_type or "").upper() == "CHECK_SUBSCRIPTION")


def _get_subscription_payload(node: NodeView) -> dict:
    payload = node.condition_payload or {}
    return payload if isinstance(payload, dict) else {}


def _build_subscription_keyboard(node: NodeView) -> InlineKeyboardMarkup:
    payload = _get_subscription_payload(node)
    return get_subscription_keyboard(
        callback_data=f"SUB_CHECK:{node.code}",
        subscribe_url=payload.get("subscribe_url"),
        channels=payload.get("channels") or [],
        subscribe_button_text=payload.get("subscribe_button_text") or "Подписаться",
        check_button_text=payload.get("check_button_text") or "Проверить подписку",
    )


async def _send_subscription_prompt(
    message: types.Message, node: NodeView, *, text_override: str | None = None
) -> None:
    user_vars = _load_user_vars(message.from_user.id)
    keyboard = _build_subscription_keyboard(node)
    text = text_override or node.message_text
    await _send_message_node(message, node, user_vars, reply_markup=keyboard)


async def _send_message_node(
    message: types.Message, node: NodeView, user_vars: dict[str, str], *, reply_markup=None
) -> None:
    settings = get_settings()
    keyboard = reply_markup if reply_markup is not None else node.keyboard
    photo = (
        (node.config_json or {}).get("image_file_id")
        or _to_absolute_media(node.image_url)
        or settings.banner_start
        or settings.start_banner_id
    )
    context_vars = _build_template_context(message.from_user, user_vars)
    rendered_text = _apply_variables(node.message_text, context_vars)

    sent_message: types.Message | None = None

    if photo:
        sent_message = await _safe_answer_photo(
            message,
            photo=photo,
            caption=rendered_text,
            parse_mode=node.parse_mode,
            reply_markup=keyboard,
            fallback_text=rendered_text,
        )
        if sent_message:
            if sent_message.photo:
                photo_id = sent_message.photo[-1].file_id
                cache_node_image_file_id(node.code, photo_id)
                persist_node_image_file_id(node.code, photo_id)
            _remember_bot_message(message.from_user.id, sent_message)
            return
        # Fallback to text if Telegram rejects the image URL or network error occurred

    sent_message = await _safe_answer(
        message,
        rendered_text,
        parse_mode=node.parse_mode,
        reply_markup=keyboard,
    )
    if not sent_message:
        return

    _remember_bot_message(message.from_user.id, sent_message)


async def _send_input_node(message: types.Message, node: NodeView, user_vars: dict[str, str]) -> None:
    inline_keyboard = _build_inline_keyboard_with_cancel(node)
    await _send_message_node(message, node, user_vars, reply_markup=inline_keyboard)

    if node.input_type == "CONTACT":
        await _answer_and_track(
            message,
            "Отправьте контакт или нажмите «Отмена».",
            reply_markup=_build_contact_keyboard(node),
        )

    _set_waiting_state(message.from_user.id, node)


async def _send_node(message: types.Message, node: NodeView, *, remove_reply_keyboard: bool = False) -> None:
    user_vars = _load_user_vars(message.from_user.id)
    log_node_event(
        user_id=message.from_user.id,
        username=message.from_user.username,
        node_code=node.code,
    )
    _remember_current_node(message.from_user.id, node.code)
    reply_keyboard = _build_reply_keyboard(node) or _build_global_reply_keyboard()
    if node.clear_chat:
        await _clear_previous_bot_messages(message)
    if reply_keyboard:
        await _apply_reply_keyboard(message, reply_keyboard)
    else:
        await _apply_reply_keyboard(message, ReplyKeyboardRemove())
    if node.node_type == "CONDITION":
        _clear_user_state(message.from_user.id)
        if _is_subscription_condition(node):
            await _send_subscription_prompt(message, node)
            return

        is_true = _evaluate_condition(node, user_vars)
        target_code = node.next_node_code_true if is_true else node.next_node_code_false
        await _open_node_with_fallback(message, target_code)
        return

    if node.node_type == "ACTION":
        await _execute_action_node(message, node, user_vars)
        return

    if node.node_type == "INPUT":
        await _send_input_node(message, node, user_vars)
    else:
        _clear_user_state(message.from_user.id)
        await _send_message_node(message, node, user_vars)


def _validate_input_value(node: NodeView, message: types.Message) -> tuple[bool, str, str]:
    error_text = node.input_error_text or "Пожалуйста, введите корректное значение."

    if node.input_type == "CONTACT":
        if not message.contact or not message.contact.phone_number:
            return False, "", error_text
        return True, message.contact.phone_number, ""

    text_value = (message.text or "").strip()

    if node.input_required and not text_value:
        return False, "", error_text

    if node.input_type == "TEXT":
        if node.input_min_len and len(text_value) < node.input_min_len:
            return False, "", error_text
        return True, text_value, ""

    if node.input_type == "NUMBER":
        try:
            normalized = float(text_value.replace(",", "."))
        except Exception:
            return False, "", error_text
        return True, str(normalized), ""

    if node.input_type == "PHONE_TEXT":
        digits = re.sub(r"\D", "", text_value)
        if node.input_required and not digits:
            return False, "", error_text
        if len(digits) < 10:
            return False, "", error_text
        return True, text_value, ""

    return True, text_value, ""


async def _open_node_by_code(message: types.Message, node_code: str) -> None:
    node = load_node(node_code)
    if not node:
        await _answer_and_track(message, "Ошибка конфигурации: узел перехода не найден.")
        log_error_event(
            user_id=message.from_user.id,
            username=message.from_user.username,
            node_code=node_code,
            details="Узел перехода не найден",
        )
        return

    await _send_node(message, node)


async def _open_node_with_fallback(message: types.Message, node_code: str | None) -> None:
    if not node_code:
        await _answer_and_track(message, "Ошибка конфигурации: узел перехода не найден.")
        log_error_event(
            user_id=message.from_user.id,
            username=message.from_user.username,
            node_code=node_code,
            details="Не указан код узла для перехода",
        )
        main_menu = load_node("MAIN_MENU")
        if main_menu:
            await _send_node(message, main_menu)
        return

    node = load_node(node_code)
    if node:
        await _send_node(message, node)
        return

    await _answer_and_track(message, "Ошибка конфигурации: узел перехода не найден.")
    log_error_event(
        user_id=message.from_user.id,
        username=message.from_user.username,
        node_code=node_code,
        details="Запрошенный узел не найден, выполнен fallback",
    )
    main_menu = load_node("MAIN_MENU")
    if main_menu:
        await _send_node(message, main_menu)


def _extract_command(text: str) -> str:
    normalized = text.strip()
    if not normalized.startswith("/"):
        return ""
    return normalized[1:].split(maxsplit=1)[0].lower()


def _matches_text_trigger(trigger: BotTriggerView, normalized_text: str) -> bool:
    value = (trigger.trigger_value or "").strip().lower()
    if not value:
        return False

    mode = (trigger.match_mode or "EXACT").upper()
    if mode == "CONTAINS":
        return value in normalized_text
    if mode == "STARTS_WITH":
        return normalized_text.startswith(value)
    return normalized_text == value


def _matches_command_trigger(trigger: BotTriggerView, command: str) -> bool:
    value = (trigger.trigger_value or "").strip().lower()
    if not value:
        return False

    mode = (trigger.match_mode or "EXACT").upper()
    if mode == "STARTS_WITH":
        return command.startswith(value)
    if mode == "CONTAINS":
        return value in command
    return command == value


async def _process_triggers(
    message: types.Message, *, text_override: str | None = None
) -> bool:
    text_value = (text_override or message.text or "").strip()
    normalized_text = text_value.lower()
    command = _extract_command(text_value)
    triggers = load_triggers()

    for trigger in triggers:
        trigger_type = (trigger.trigger_type or "").upper()
        if trigger_type == "COMMAND":
            if command and _matches_command_trigger(trigger, command):
                log_trigger_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    trigger_type="COMMAND",
                    trigger_value=trigger.trigger_value,
                    target_node=trigger.target_node_code,
                )
                await _open_node_with_fallback(message, trigger.target_node_code)
                return True
        elif trigger_type == "TEXT":
            if text_value and _matches_text_trigger(trigger, normalized_text):
                log_trigger_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    trigger_type="TEXT",
                    trigger_value=trigger.trigger_value,
                    target_node=trigger.target_node_code,
                )
                await _open_node_with_fallback(message, trigger.target_node_code)
                return True
        elif trigger_type == "FALLBACK":
            log_trigger_event(
                user_id=message.from_user.id,
                username=message.from_user.username,
                trigger_type="FALLBACK",
                trigger_value=trigger.trigger_value,
                target_node=trigger.target_node_code,
            )
            await _open_node_with_fallback(message, trigger.target_node_code)
            return True

    return False


def _evaluate_condition(node: NodeView, user_vars: dict[str, str]) -> bool:
    operator = (node.cond_operator or "").upper()
    var_key = node.cond_var_key or ""
    raw_value = user_vars.get(var_key)

    def _normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    def _to_float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "."))
        except Exception:
            return None

    normalized_value = _normalize_text(raw_value)

    if operator == "EXISTS":
        return bool(normalized_value)
    if operator == "NOT_EXISTS":
        return not normalized_value

    if normalized_value is None:
        return False

    left = normalized_value
    right = _normalize_text(node.cond_value) or ""

    if operator == "EQ":
        return left == right
    if operator == "NEQ":
        return left != right
    if operator == "CONTAINS":
        return right in left
    if operator == "STARTS_WITH":
        return left.startswith(right)
    if operator == "ENDS_WITH":
        return left.endswith(right)
    if operator in {"GT", "GTE", "LT", "LTE"}:
        left_num = _to_float(left)
        right_num = _to_float(right)
        if left_num is None or right_num is None:
            return False

        if operator == "GT":
            return left_num > right_num
        if operator == "GTE":
            return left_num >= right_num
        if operator == "LT":
            return left_num < right_num
        if operator == "LTE":
            return left_num <= right_num

    return False


async def _handle_cancel_action(message: types.Message, state: UserState) -> None:
    _clear_user_state(state.user_id)
    if state.next_node_code_cancel:
        await _open_node_by_code(message, state.next_node_code_cancel)
    else:
        await _answer_and_track(
            message, "Ввод отменён.", reply_markup=ReplyKeyboardRemove()
        )


def _ensure_user_exists(telegram_user: types.User) -> None:
    users_service.get_or_create_user_from_telegram(
        {
            "id": telegram_user.id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
        }
    )


def _load_user_vars(user_id: int) -> dict[str, str]:
    with get_session() as session:
        vars_rows = session.query(UserVar).filter(UserVar.user_id == user_id).all()
        return {row.key: row.value for row in vars_rows}


def _build_template_context(telegram_user: types.User | None, user_vars: dict[str, str]) -> dict[str, str]:
    return {
        **user_vars,
        "telegram_id": str(telegram_user.id) if telegram_user else "",
        "username": telegram_user.username or "" if telegram_user else "",
        "first_name": telegram_user.first_name or "" if telegram_user else "",
        "last_name": telegram_user.last_name or "" if telegram_user else "",
    }


def _apply_variables(text: str, context_vars: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return context_vars.get(key, "")

    return VAR_PATTERN.sub(_replace, text or "")


def _save_user_var(user_id: int, key: str, value: str) -> None:
    with get_session() as session:
        record = (
            session.query(UserVar)
            .filter(UserVar.user_id == user_id, UserVar.key == key)
            .first()
        )
        if record:
            record.value = value
        else:
            session.add(UserVar(user_id=user_id, key=key, value=value))


def _delete_user_var(user_id: int, key: str) -> None:
    with get_session() as session:
        session.query(UserVar).filter(UserVar.user_id == user_id, UserVar.key == key).delete()


def _add_user_tag(user_id: int, tag: str) -> None:
    normalized_tag = tag.strip()
    if not normalized_tag:
        return
    with get_session() as session:
        exists = (
            session.query(UserTag)
            .filter(UserTag.user_id == user_id, UserTag.tag == normalized_tag)
            .first()
        )
        if exists:
            return
        session.add(UserTag(user_id=user_id, tag=normalized_tag))


def _remove_user_tag(user_id: int, tag: str) -> None:
    normalized_tag = tag.strip()
    if not normalized_tag:
        return
    with get_session() as session:
        session.query(UserTag).filter(UserTag.user_id == user_id, UserTag.tag == normalized_tag).delete()


def _set_waiting_state(user_id: int, node: NodeView) -> None:
    with get_session() as session:
        state = session.get(UserState, user_id)
        if not state:
            state = UserState(user_id=user_id)
        state.current_node_code = node.code
        state.waiting_node_code = node.code
        state.waiting_input_type = node.input_type
        state.waiting_var_key = node.input_var_key
        state.next_node_code_success = node.next_node_code_success
        state.next_node_code_cancel = node.next_node_code_cancel
        session.add(state)


def _get_user_state(user_id: int) -> UserState | None:
    with get_session() as session:
        return session.get(UserState, user_id)


def _remember_current_node(user_id: int, node_code: str | None) -> None:
    with get_session() as session:
        state = session.get(UserState, user_id)
        if not state:
            state = UserState(user_id=user_id)
        state.current_node_code = node_code
        session.add(state)


def _get_current_node_code(user_id: int) -> str | None:
    state = _get_user_state(user_id)
    return state.current_node_code if state else None


def _clear_user_state(user_id: int) -> None:
    with get_session() as session:
        state = session.get(UserState, user_id)
        if state:
            state.waiting_node_code = None
            state.waiting_input_type = None
            state.waiting_var_key = None
            state.next_node_code_success = None
            state.next_node_code_cancel = None
            session.add(state)


def _build_inline_keyboard_with_cancel(
    node: NodeView, *, include_cancel: bool = True
) -> InlineKeyboardMarkup | None:
    base_keyboard: list[list[InlineKeyboardButton]] = []
    if node.keyboard and node.keyboard.inline_keyboard:
        base_keyboard = [list(row) for row in node.keyboard.inline_keyboard]

    if include_cancel and node.next_node_code_cancel:
        base_keyboard.append(
            [InlineKeyboardButton(text="Отмена", callback_data=f"INPUT_CANCEL:{node.code}")]
        )

    if not base_keyboard:
        return None

    return InlineKeyboardMarkup(inline_keyboard=base_keyboard)


def _build_contact_keyboard(node: NodeView) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Поделиться контактом", request_contact=True)],
    ]
    if node.next_node_code_cancel:
        buttons.append([KeyboardButton(text="Отмена")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def _build_request_keyboard(button_text: str, request_type: str) -> ReplyKeyboardMarkup:
    if request_type == "contact":
        btn = KeyboardButton(text=button_text or "Поделиться контактом", request_contact=True)
    else:
        btn = KeyboardButton(text=button_text or "Отправить геолокацию", request_location=True)
    return ReplyKeyboardMarkup(keyboard=[[btn]], resize_keyboard=True, one_time_keyboard=True)


def _build_reply_keyboard(node: NodeView) -> ReplyKeyboardMarkup | None:
    rows: dict[int, list[KeyboardButton]] = {}
    for button in node.reply_buttons:
        text = (button.text or "").strip()
        if not text:
            continue
        rows.setdefault(button.row, []).append((button.position, KeyboardButton(text=text)))

    if not rows:
        return None

    keyboard_rows: list[list[KeyboardButton]] = []
    for row in sorted(rows.keys()):
        row_buttons = [btn for _, btn in sorted(rows[row], key=lambda item: (item[0], item[1].text))]
        if row_buttons:
            keyboard_rows.append(row_buttons)

    if not keyboard_rows:
        return None

    return ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True)


def _build_global_reply_keyboard() -> ReplyKeyboardMarkup | None:
    menu_buttons = load_menu_buttons()
    return get_main_menu(menu_buttons, include_fallback=False)


def _find_reply_button_by_text(node: NodeView, text_value: str | None) -> NodeButtonView | None:
    normalized = (text_value or "").strip().lower()
    if not normalized:
        return None

    for button in node.reply_buttons:
        if (button.text or "").strip().lower() == normalized:
            return button

    return None


def _find_menu_button_by_text(text_value: str | None) -> MenuButtonView | None:
    normalized = (text_value or "").strip().lower()
    if not normalized:
        return None

    for button in load_menu_buttons():
        if (button.text or "").strip().lower() == normalized:
            return button

    return None


def _get_admin_telegram_ids() -> list[int]:
    admin_ids = set(ADMIN_IDS_SET)
    with get_session() as session:
        rows = session.query(User.telegram_id).filter(User.is_admin.is_(True)).all()
        admin_ids.update([row[0] for row in rows if row and row[0]])
    return [admin_id for admin_id in admin_ids if admin_id]


def _parse_int(value: str | int | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except Exception:
        return default


async def _execute_single_action(
    message: types.Message, node: NodeView, action, user_vars: dict[str, str]
) -> tuple[bool, str | None]:
    action_type = (getattr(action, "action_type", "") or "").upper()
    payload = getattr(action, "payload", {}) or {}
    context = _build_template_context(message.from_user, user_vars)

    log_action_event(
        user_id=message.from_user.id,
        username=message.from_user.username,
        node_code=node.code,
        action_type=action_type,
        payload=payload,
    )

    try:
        if action_type == "SET_VAR":
            key = (payload.get("key") or "").strip()
            if not key:
                logger.error("[ACTION] SET_VAR: отсутствует ключ переменной (узел=%s)", node.code)
                log_error_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    node_code=node.code,
                    details="SET_VAR: отсутствует ключ переменной",
                )
                return False, None
            value = _apply_variables(str(payload.get("value", "")), context)
            user_vars[key] = value
            _save_user_var(message.from_user.id, key, value)
            return False, None

        if action_type == "CLEAR_VAR":
            key = (payload.get("key") or "").strip()
            if not key:
                logger.error("[ACTION] CLEAR_VAR: отсутствует ключ переменной (узел=%s)", node.code)
                return False, None
            user_vars.pop(key, None)
            _delete_user_var(message.from_user.id, key)
            return False, None

        if action_type in {"INCREMENT_VAR", "DECREMENT_VAR"}:
            key = (payload.get("key") or "").strip()
            if not key:
                logger.error("[ACTION] %s: отсутствует ключ переменной (узел=%s)", action_type, node.code)
                log_error_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    node_code=node.code,
                    details=f"{action_type}: отсутствует ключ переменной",
                )
                return False, None
            step = _parse_int(payload.get("step"), 1)
            current = _parse_int(user_vars.get(key), 0)
            delta = step if action_type == "INCREMENT_VAR" else -step
            new_value = current + delta
            user_vars[key] = str(new_value)
            _save_user_var(message.from_user.id, key, str(new_value))
            return False, None

        if action_type == "ADD_TAG":
            tag = (payload.get("tag") or "").strip()
            if not tag:
                logger.error("[ACTION] ADD_TAG: отсутствует тег (узел=%s)", node.code)
                log_error_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    node_code=node.code,
                    details="ADD_TAG: отсутствует тег",
                )
                return False, None
            _add_user_tag(message.from_user.id, tag)
            return False, None

        if action_type == "REMOVE_TAG":
            tag = (payload.get("tag") or "").strip()
            if not tag:
                logger.error("[ACTION] REMOVE_TAG: отсутствует тег (узел=%s)", node.code)
                log_error_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    node_code=node.code,
                    details="REMOVE_TAG: отсутствует тег",
                )
                return False, None
            _remove_user_tag(message.from_user.id, tag)
            return False, None

        if action_type == "SEND_MESSAGE":
            text = _apply_variables(str(payload.get("text", "")), context)
            if not text:
                logger.error("[ACTION] SEND_MESSAGE: пустой текст (узел=%s)", node.code)
                log_error_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    node_code=node.code,
                    details="SEND_MESSAGE: пустой текст",
                )
                return False, None
            await _answer_and_track(message, text, parse_mode=node.parse_mode)
            return False, None

        if action_type == "SEND_ADMIN_MESSAGE":
            text = _apply_variables(str(payload.get("text", "")), context)
            if not text:
                logger.error("[ACTION] SEND_ADMIN_MESSAGE: пустой текст (узел=%s)", node.code)
                log_error_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    node_code=node.code,
                    details="SEND_ADMIN_MESSAGE: пустой текст",
                )
                return False, None
            admin_ids = _get_admin_telegram_ids()
            for admin_id in admin_ids:
                try:
                    await message.bot.send_message(admin_id, text, parse_mode=node.parse_mode)
                except Exception as exc:  # noqa: WPS440
                    logger.error("[ACTION] SEND_ADMIN_MESSAGE failed: %s", exc)
            return False, None

        if action_type == "GOTO_NODE":
            target_code = (payload.get("node_code") or "").strip()
            if not target_code:
                logger.error("[ACTION] GOTO_NODE: отсутствует код узла (узел=%s)", node.code)
                log_error_event(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    node_code=node.code,
                    details="GOTO_NODE: отсутствует код узла",
                )
                return False, None
            return True, target_code

        if action_type == "GOTO_MAIN":
            return True, "MAIN_MENU"

        if action_type == "STOP_FLOW":
            return True, None

        if action_type == "REQUEST_CONTACT":
            text = _apply_variables(str(payload.get("text", "")), context)
            keyboard = _build_request_keyboard(text or "Поделиться контактом", "contact")
            await _answer_and_track(
                message, text or "Поделитесь контактом", reply_markup=keyboard
            )
            return False, None

        if action_type == "REQUEST_LOCATION":
            text = _apply_variables(str(payload.get("text", "")), context)
            keyboard = _build_request_keyboard(text or "Отправить геолокацию", "location")
            await _answer_and_track(
                message,
                text or "Отправьте вашу геолокацию",
                reply_markup=keyboard,
            )
            return False, None

        logger.error("[ACTION] Неизвестный тип действия: %s (узел=%s)", action_type, node.code)
        log_error_event(
            user_id=message.from_user.id,
            username=message.from_user.username,
            node_code=node.code,
            details=f"Неизвестный тип действия: {action_type}",
        )
        return False, None
    except Exception as exc:  # noqa: WPS440
        logger.exception("[ACTION] Ошибка выполнения действия %s в узле %s: %s", action_type, node.code, exc)
        log_error_event(
            user_id=message.from_user.id,
            username=message.from_user.username,
            node_code=node.code,
            details=f"Ошибка выполнения действия {action_type}: {exc}",
        )
        return False, None


async def _execute_action_node(message: types.Message, node: NodeView, user_vars: dict[str, str]) -> None:
    _clear_user_state(message.from_user.id)
    for action in sorted(node.actions, key=lambda a: (a.sort_order, a.action_type)):
        if not action.is_enabled:
            continue
        stop_flow, next_code = await _execute_single_action(message, node, action, user_vars)
        if stop_flow:
            if next_code:
                await _open_node_with_fallback(message, next_code)
            return

    if node.next_node_code:
        await _open_node_with_fallback(message, node.next_node_code)


# -------------------------------------------------------------------
#   Экран приветствия /start
# -------------------------------------------------------------------


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: types.Message, command: CommandObject):
    """
    /start auth_<token>
    Этот обработчик вызывается, когда пользователь переходит из сайта в бота по ссылке
    https://t.me/BotMiniden_bot?start=auth_<token>.
    """
    payload = (command.args or "").strip()
    if not payload.startswith("auth_"):
        # обычный /start без авторизации, тут оставляем текущую приветственную логику
        # (если уже есть handler для CommandStart без deep_link — НЕ ломать его)
        return

    token = payload[len("auth_") :]

    _ensure_user_exists(message.from_user)

    # связываем token ↔ telegram_id
    with get_session() as s:
        session = s.query(AuthSession).filter(AuthSession.token == token).first()
        if not session:
            await _answer_and_track(
                message,
                "Ссылка для авторизации устарела или неверна. Попробуйте начать авторизацию на сайте заново.",
            )
            return

        session.telegram_id = message.from_user.id

    await _answer_and_track(
        message,
        "✅ Авторизация для сайта выполнена!\n\n"
        "Вернитесь в браузер и обновите страницу — ваш профиль и корзина будут доступны.",
    )


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    _ensure_user_exists(message.from_user)

    payload = (message.text or "").split(maxsplit=1)
    deep_link = payload[1] if len(payload) > 1 else ""
    if deep_link.startswith("auth_"):
        return

    if await _open_start_node(message, is_admin=is_admin):
        return

    if await ensure_subscribed(message, message.bot, is_admin=is_admin):
        if await _process_triggers(message):
            return

        await _send_start_screen(message, is_admin=is_admin)


# -------------------------------------------------------------------
#   Кнопка «🔵 Старт» — ПЕРВИЧНАЯ ПРОВЕРКА ПОДПИСКИ
# -------------------------------------------------------------------


@router.message(F.text == "🔵 Старт")
async def start_button(message: types.Message):
    """
    Обработка нажатия на кнопку «🔵 Старт».

    1) Проверяем подписку на канал.
    2) Если подписан — показываем главное меню.
    3) Если нет — показываем экран с просьбой подписаться.
    """
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    _ensure_user_exists(message.from_user)

    if await _open_start_node(message, is_admin=is_admin):
        return

    if await ensure_subscribed(message, message.bot, is_admin=is_admin):
        await _send_start_screen(message, is_admin=is_admin)


# -------------------------------------------------------------------
#   Кнопка «✅ Я подписался» под сообщением о подписке
# -------------------------------------------------------------------


@router.callback_query(F.data == "sub_check:start")
async def cb_check_subscription(callback: CallbackQuery):
    """
    Обработка нажатия на кнопку «✅ Я подписался».

    Ещё раз проверяем подписку:
    - если подписан — показываем главное меню.
    - если нет — показываем alert и оставляем всё как есть.
    """
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if is_admin or await is_user_subscribed(callback.message.bot, user_id):
        try:
            await callback.message.delete()
        except Exception:
            pass

        await _send_start_screen(callback.message, is_admin=is_admin)
        await callback.answer("✅ Спасибо, подписка подтверждена!")
    else:
        await callback.answer(
            "❌ Подписка не найдена. Подпишитесь на канал и нажмите «Я подписался» ещё раз.",
            show_alert=True,
        )
        await _send_subscription_invite(callback.message)


@router.message(F.text == "Меню")
async def open_menu_command(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    _ensure_user_exists(message.from_user)

    if await _open_start_node(message, is_admin=is_admin):
        return

    if await ensure_subscribed(message, message.bot, is_admin=is_admin):
        await _send_start_screen(message, is_admin=is_admin)


async def _send_start_screen(message: types.Message, is_admin: bool) -> None:
    _remember_current_node(message.from_user.id, None)
    if await _send_dynamic_start_screen(message, None):
        return

    settings = get_settings()
    banner = settings.banner_start or settings.start_banner_id

    if banner:
        sent = await _safe_answer_photo(
            message,
            photo=banner,
            caption=format_start_text(),
            fallback_text=format_start_text(),
        )
        if not sent:
            return
        if sent.photo:
            settings.start_banner_id = sent.photo[-1].file_id
            settings.banner_start = settings.start_banner_id
        _remember_bot_message(message.from_user.id, sent)
    else:
        await _answer_and_track(
            message,
            format_start_text(),
        )


async def _send_dynamic_start_screen(
    message: types.Message, reply_keyboard: ReplyKeyboardMarkup | None
) -> bool:
    start_node = load_node("MAIN_MENU")
    if not start_node:
        return False

    if reply_keyboard:
        await _apply_reply_keyboard(message, reply_keyboard)

    await _send_node(message, start_node)
    return True


async def _process_subscription_check(callback: CallbackQuery, node: NodeView) -> None:
    payload = _get_subscription_payload(node)
    channels = payload.get("channels") or []
    ok, error = await check_channels_subscription(callback.bot, callback.from_user.id, channels)

    if error:
        log_error_event(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            node_code=node.code,
            details="Ошибка Telegram API при проверке подписки",
        )
        await callback.answer("Не могу проверить подписку, попробуйте позже", show_alert=True)
        await _send_subscription_prompt(
            callback.message,
            node,
            text_override=payload.get("fail_message") or node.message_text,
        )
        return

    if ok:
        target_code = (
            payload.get("on_success_node")
            or node.next_node_code_true
            or "MAIN_MENU"
        )
        await callback.answer("Подписка подтверждена!", show_alert=False)
        await _open_node_with_fallback(callback.message, target_code)
        return

    fail_text = (
        payload.get("fail_message")
        or node.message_text
        or "Подпишитесь на канал и нажмите «Проверить подписку»."
    )
    await callback.answer("Подписка не найдена", show_alert=True)
    on_fail = payload.get("on_fail_node") or node.next_node_code_false or node.code
    if on_fail and on_fail != node.code:
        await _open_node_with_fallback(callback.message, on_fail)
        return

    await _send_subscription_prompt(callback.message, node, text_override=fail_text)


async def _open_start_node(message: types.Message, is_admin: bool) -> bool:
    start_code = get_start_node_code()
    if not start_code:
        return False

    node = load_node(start_code)
    if not node:
        log_error_event(
            user_id=message.from_user.id,
            username=message.from_user.username,
            node_code=start_code,
            details="Стартовый узел не найден",
        )
        return False

    if _is_subscription_condition(node):
        await _send_node(message, node)
        return True

    if await ensure_subscribed(message, message.bot, is_admin=is_admin):
        await _send_node(message, node)
    return True


@router.callback_query(F.data.startswith("OPEN_NODE"))
async def handle_open_node(callback: CallbackQuery):
    payload = callback.data or ""
    node_code, error = _extract_node_code_from_payload(payload)

    if not node_code:
        logger.warning(
            "Malformed OPEN_NODE payload",
            extra={
                "user_id": callback.from_user.id if callback.from_user else None,
                "username": callback.from_user.username if callback.from_user else None,
                "payload": payload,
                "reason": error,
            },
        )
        await callback.answer(
            "Кнопка настроена некорректно, сообщите администратору.", show_alert=True
        )
        return

    logger.info(
        "Opening node from callback",
        extra={
            "user_id": callback.from_user.id if callback.from_user else None,
            "username": callback.from_user.username if callback.from_user else None,
            "node_code": node_code,
            "payload": payload,
        },
    )
    await _open_node_with_fallback(callback.message, node_code)
    await callback.answer()


@router.callback_query(F.data.startswith("BTN_ACTION:"))
async def handle_button_action(callback: CallbackQuery):
    _, raw_button_id = callback.data.split(":", maxsplit=1)
    try:
        button_id = int(raw_button_id)
    except Exception:
        await callback.answer("Действие недоступно", show_alert=True)
        return

    button = load_button(button_id)
    if not button:
        await callback.answer("Кнопка недоступна", show_alert=True)
        return

    if callback.message:
        await _dispatch_button_action(callback.message, button)
    await callback.answer()


@router.callback_query(F.data.startswith("SUB_CHECK:"))
async def handle_subscription_check_callback(callback: CallbackQuery):
    _, node_code = callback.data.split(":", maxsplit=1)
    node = load_node(node_code)

    if not node or not _is_subscription_condition(node):
        await callback.answer("Элемент недоступен", show_alert=True)
        return

    await _process_subscription_check(callback, node)


@router.callback_query(F.data.startswith("INPUT_CANCEL:"))
async def handle_input_cancel(callback: CallbackQuery):
    _, node_code = callback.data.split(":", maxsplit=1)
    state = _get_user_state(callback.from_user.id)
    if not state or not state.waiting_node_code:
        await callback.answer("Нечего отменять")
        return

    if state.waiting_node_code and state.waiting_node_code != node_code:
        await callback.answer("Другое действие активно")
        return

    await _handle_cancel_action(callback.message, state)
    await callback.answer("Ввод отменён")


@router.callback_query(F.data.startswith("SEND_TEXT:"))
async def handle_send_text(callback: CallbackQuery):
    _, node_code = callback.data.split(":", maxsplit=1)
    node = load_node(node_code)

    if not node:
        await callback.answer("Элемент недоступен", show_alert=True)
        return

    await _send_node(callback.message, node)
    await callback.answer()


@router.message(lambda message: bool(_get_user_state(message.from_user.id)))
async def handle_waiting_input(message: types.Message):
    state = _get_user_state(message.from_user.id)
    if not state or not state.waiting_node_code:
        return

    node = load_node(state.waiting_node_code)
    if not node:
        await _answer_and_track(message, "Ошибка конфигурации: узел не найден")
        _clear_user_state(message.from_user.id)
        log_error_event(
            user_id=message.from_user.id,
            username=message.from_user.username,
            node_code=state.waiting_node_code,
            details="Ожидаемый узел ввода не найден",
        )
        return

    if state.next_node_code_cancel and (message.text or "").strip().lower() == "отмена":
        await _handle_cancel_action(message, state)
        return

    ok, value, error_text = _validate_input_value(node, message)
    if not ok:
        reply_markup = _build_contact_keyboard(node) if node.input_type == "CONTACT" else None
        await _answer_and_track(message, error_text, reply_markup=reply_markup)
        return

    if node.input_var_key:
        _save_user_var(message.from_user.id, node.input_var_key, value)

    _clear_user_state(message.from_user.id)

    if not node.next_node_code_success:
        await _answer_and_track(message, "Ошибка конфигурации: узел не найден")
        log_error_event(
            user_id=message.from_user.id,
            username=message.from_user.username,
            node_code=node.code,
            details="Не указан next_node_code_success для узла INPUT",
        )
        return

    await _open_node_by_code(message, node.next_node_code_success)


@router.message(F.text)
async def handle_reply_buttons_or_triggers(message: types.Message):
    current_node_code = _get_current_node_code(message.from_user.id)
    if current_node_code:
        node = load_node(current_node_code)
        if node:
            reply_button = _find_reply_button_by_text(node, message.text)
            if reply_button:
                await _dispatch_button_action(message, reply_button)
                return

    menu_button = _find_menu_button_by_text(message.text)
    if menu_button:
        await _dispatch_menu_button(message, menu_button)
        return

    await _process_triggers(message)
