import re

from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import ADMIN_IDS, get_settings
from database import get_session
from models import AuthSession, UserState, UserVar
from services import users as users_service
from keyboards.main_menu import get_main_menu
from services.bot_config import NodeView, load_node
from services.subscription import (
    ensure_subscribed,
    get_subscription_keyboard,
    is_user_subscribed,
)
from utils.texts import format_start_text, format_subscription_required_text

router = Router()


VAR_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


async def _send_subscription_invite(target_message) -> None:
    await target_message.answer(
        format_subscription_required_text(),
        reply_markup=get_subscription_keyboard(),
    )


async def _send_message_node(
    message: types.Message, node: NodeView, user_vars: dict[str, str], *, reply_markup=None
) -> None:
    settings = get_settings()
    keyboard = reply_markup if reply_markup is not None else node.keyboard
    photo = node.image_url or settings.banner_start or settings.start_banner_id
    rendered_text = _apply_variables(node.message_text, user_vars)

    if photo:
        await message.answer_photo(
            photo=photo,
            caption=rendered_text,
            parse_mode=node.parse_mode,
            reply_markup=keyboard,
        )
    else:
        await message.answer(
            rendered_text,
            parse_mode=node.parse_mode,
            reply_markup=keyboard,
        )


async def _send_input_node(message: types.Message, node: NodeView, user_vars: dict[str, str]) -> None:
    inline_keyboard = _build_inline_keyboard_with_cancel(node)
    await _send_message_node(message, node, user_vars, reply_markup=inline_keyboard)

    if node.input_type == "CONTACT":
        await message.answer(
            "Отправьте контакт или нажмите «Отмена».",
            reply_markup=_build_contact_keyboard(node),
        )

    _set_waiting_state(message.from_user.id, node)


async def _send_node(message: types.Message, node: NodeView, *, remove_reply_keyboard: bool = False) -> None:
    user_vars = _load_user_vars(message.from_user.id)
    if node.node_type == "CONDITION":
        _clear_user_state(message.from_user.id)
        is_true = _evaluate_condition(node, user_vars)
        target_code = node.next_node_code_true if is_true else node.next_node_code_false
        await _open_node_with_fallback(message, target_code)
        return

    if node.node_type == "INPUT":
        await _send_input_node(message, node, user_vars)
    else:
        reply_markup = ReplyKeyboardRemove() if remove_reply_keyboard else None
        _clear_user_state(message.from_user.id)
        await _send_message_node(message, node, user_vars, reply_markup=reply_markup)


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
        await message.answer("Ошибка конфигурации: узел перехода не найден.")
        return

    await _send_node(message, node)


async def _open_node_with_fallback(message: types.Message, node_code: str | None) -> None:
    if not node_code:
        await message.answer("Ошибка конфигурации: узел перехода не найден.")
        return

    node = load_node(node_code)
    if node:
        await _send_node(message, node)
        return

    await message.answer("Ошибка конфигурации: узел перехода не найден.")
    main_menu = load_node("MAIN_MENU")
    if main_menu:
        await _send_node(message, main_menu)


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
        await message.answer("Ввод отменён.", reply_markup=ReplyKeyboardRemove())


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


def _apply_variables(text: str, user_vars: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return user_vars.get(key, "")

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


def _set_waiting_state(user_id: int, node: NodeView) -> None:
    with get_session() as session:
        state = session.get(UserState, user_id)
        if not state:
            state = UserState(user_id=user_id)
        state.waiting_node_code = node.code
        state.waiting_input_type = node.input_type
        state.waiting_var_key = node.input_var_key
        state.next_node_code_success = node.next_node_code_success
        state.next_node_code_cancel = node.next_node_code_cancel
        session.add(state)


def _get_user_state(user_id: int) -> UserState | None:
    with get_session() as session:
        return session.get(UserState, user_id)


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
            await message.answer("Ссылка для авторизации устарела или неверна. Попробуйте начать авторизацию на сайте заново.")
            return

        session.telegram_id = message.from_user.id

    await message.answer(
        "✅ Авторизация для сайта выполнена!\n\n"
        "Вернитесь в браузер и обновите страницу — ваш профиль и корзина будут доступны."
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

    if await ensure_subscribed(message, message.bot, is_admin=is_admin):
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


async def _send_start_screen(message: types.Message, is_admin: bool) -> None:
    if await _send_dynamic_start_screen(message):
        return

    settings = get_settings()
    main_menu = get_main_menu(is_admin=is_admin)
    banner = settings.banner_start or settings.start_banner_id

    if banner:
        await message.answer_photo(
            photo=banner,
            caption=format_start_text(),
            reply_markup=main_menu,
        )
    else:
        await message.answer(
            format_start_text(),
            reply_markup=main_menu,
        )


async def _send_dynamic_start_screen(message: types.Message) -> bool:
    start_node = load_node("MAIN_MENU")
    if not start_node:
        return False

    await _send_node(message, start_node)
    return True


@router.callback_query(F.data.startswith("OPEN_NODE:"))
async def handle_open_node(callback: CallbackQuery):
    _, node_code = callback.data.split(":", maxsplit=1)
    node = load_node(node_code)

    if not node:
        await callback.answer("Раздел временно недоступен", show_alert=True)
        return

    await _send_node(callback.message, node)
    await callback.answer()


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
        await message.answer("Ошибка конфигурации: узел не найден")
        _clear_user_state(message.from_user.id)
        return

    if state.next_node_code_cancel and (message.text or "").strip().lower() == "отмена":
        await _handle_cancel_action(message, state)
        return

    ok, value, error_text = _validate_input_value(node, message)
    if not ok:
        reply_markup = _build_contact_keyboard(node) if node.input_type == "CONTACT" else None
        await message.answer(error_text, reply_markup=reply_markup)
        return

    if node.input_var_key:
        _save_user_var(message.from_user.id, node.input_var_key, value)

    _clear_user_state(message.from_user.id)

    if not node.next_node_code_success:
        await message.answer("Ошибка конфигурации: узел не найден")
        return

    await _open_node_by_code(message, node.next_node_code_success)
