import datetime
import logging
import os
import subprocess
from collections import deque
from pathlib import Path

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, ADMIN_IDS_SET
from services import admin_notes as admin_notes_service
from services import bans as bans_service
from services import orders as orders_service
from services import products as products_service
from services import user_stats as user_stats_service
from services.bot_config import load_menu_buttons
from keyboards.admin_inline import (
    course_access_list_kb,
    course_access_actions_kb,
)
from keyboards.main_menu import get_admin_menu, get_main_menu
from utils.commands_map import get_admin_commands, get_user_commands
from utils.texts import (
    format_admin_client_profile,
    format_order_detail_text,
    format_orders_list_text,
    format_order_status_changed_for_user,
    format_user_courses_access_granted,
    format_user_notes,
)

router = Router()
logger = logging.getLogger(__name__)

DEPLOY_SCRIPT_PATH = "/opt/miniden/deploy.sh"
DEPLOY_LOG_PATH = "/opt/miniden/logs/deploy.log"
DEPLOY_PID_PATH = "/opt/miniden/logs/deploy.pid"
DEPLOY_LOG_DIR = Path(DEPLOY_LOG_PATH).parent

WEB_ADMIN_REDIRECT_TEXT = (
    "Управление каталогом, промокодами и статистикой теперь доступно в веб-админке.\n"
    "Откройте админку через кнопку «⚙️ Админка (WebApp)» в главном меню бота."
)


def _is_admin(user_id: int | None) -> bool:
    return bool(user_id) and user_id in ADMIN_IDS_SET


def _get_reply_menu():
    return get_main_menu(load_menu_buttons(), include_fallback=True)


def read_pid() -> int | None:
    try:
        with open(DEPLOY_PID_PATH, "r") as pid_file:
            raw_pid = pid_file.read().strip().splitlines()[0]
        return int(raw_pid)
    except FileNotFoundError:
        return None
    except (ValueError, IndexError, OSError):
        return None


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False

    return True


def is_running() -> bool:
    pid = read_pid()
    return is_pid_running(pid)


def tail_log(n: int = 60) -> list[str]:
    try:
        with open(DEPLOY_LOG_PATH, "r") as log_file:
            lines = deque(log_file, maxlen=n)
        return [line.rstrip("\n") for line in lines]
    except FileNotFoundError:
        return []
    except OSError:
        return []


def _deploy_paths_ok() -> tuple[bool, str | None]:
    if not DEPLOY_LOG_DIR.exists():
        return False, "Папка логов /opt/miniden/logs отсутствует. Создайте её и повторите попытку."

    if not Path(DEPLOY_SCRIPT_PATH).exists():
        return False, "Не найден скрипт деплоя /opt/miniden/deploy.sh."

    return True, None


def start_deploy_process() -> tuple[bool, str]:
    if is_running():
        return False, "⏳ Деплой уже выполняется"

    paths_ok, paths_error = _deploy_paths_ok()
    if not paths_ok:
        return False, paths_error or "Путь к деплою недоступен"

    try:
        with open(DEPLOY_LOG_PATH, "a") as log_file:
            log_file.write(f"=== DEPLOY START {datetime.datetime.now().isoformat()} ===\n")
            log_file.flush()
            process = subprocess.Popen(
                [DEPLOY_SCRIPT_PATH],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
    except OSError:
        logger.exception("Failed to open deploy log file")
        return False, "Не удалось открыть лог деплоя. Проверьте права на /opt/miniden/logs/."
    except Exception:
        logger.exception("Failed to start deploy script")
        return False, "Не удалось запустить деплой. Проверьте логи."

    pid_written = True
    try:
        with open(DEPLOY_PID_PATH, "w") as pid_file:
            pid_file.write(str(process.pid))
    except OSError:
        pid_written = False
        logger.exception("Failed to write deploy pid file")

    response = f"✅ Деплой запущен. PID: {process.pid}"
    if not pid_written:
        response += "\n⚠️ Не удалось записать PID-файл (/opt/miniden/logs/deploy.pid)."
    return True, response


def build_deploy_status_text(max_lines: int = 60) -> str:
    pid = read_pid()
    running = is_pid_running(pid)
    log_lines = tail_log(max_lines)

    lines = [
        f"running: {'да' if running else 'нет'}",
        f"pid: {pid if pid is not None else '—'}",
    ]

    if not DEPLOY_LOG_DIR.exists():
        lines.append("папка логов: отсутствует (/opt/miniden/logs)")
        return "\n".join(lines)

    if log_lines:
        log_text = "\n".join(log_lines)
        max_len = 3500
        if len(log_text) > max_len:
            log_text = log_text[-max_len:]
            lines.append("(лог обрезан до последних строк)")
        lines.append("последние строки лога:")
        lines.append(log_text)
    else:
        lines.append("последние строки лога: (нет данных)")

    return "\n".join(lines)


def _build_order_actions_kb(order_id: int, user_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="👁 Открыть", callback_data=f"admin:order:open:{order_id}"
                ),
                types.InlineKeyboardButton(
                    text="✅ Оплачен", callback_data=f"admin:order:paid:{order_id}"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="📁 В архив", callback_data=f"admin:order:archive:{order_id}"
                ),
                types.InlineKeyboardButton(
                    text="👤 CRM", callback_data=f"admin:order:client:{user_id}"
                ),
            ],
        ]
    )


def _build_orders_menu_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🆕 Новые", callback_data="admin:orders:status:new"
                ),
                types.InlineKeyboardButton(
                    text="🕒 В работе", callback_data="admin:orders:status:in_progress"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="✅ Оплаченные", callback_data="admin:orders:status:paid"
                ),
                types.InlineKeyboardButton(
                    text="📤 Отправленные", callback_data="admin:orders:status:sent"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="📁 Архив", callback_data="admin:orders:status:archived"
                ),
                types.InlineKeyboardButton(
                    text="📦 Все", callback_data="admin:orders:status:all"
                ),
            ],
        ]
    )


async def _send_web_admin_redirect_message(target_message: types.Message) -> None:
    await target_message.answer(WEB_ADMIN_REDIRECT_TEXT)


async def _send_web_admin_redirect_callback(callback: types.CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer(WEB_ADMIN_REDIRECT_TEXT)
    await callback.answer()


async def _send_orders_menu(message: types.Message) -> None:
    await message.answer(
        "📦 <b>Раздел заказов</b>\nВыберите, какие заказы показать:",
        reply_markup=_build_orders_menu_kb(),
    )


class CourseAccessState(StatesGroup):
    waiting_grant_user_id = State()
    waiting_revoke_user_id = State()


# ---------------- ВХОД В АДМИНКУ ----------------


@router.message(F.text == "⚙️ Админка")
async def open_admin_panel(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()

    await message.answer(
        "⚙️ Админ-панель.\nВыберите категорию:", reply_markup=get_admin_menu()
    )


@router.message(F.text == "👤 Клиент (CRM)")
async def admin_client_menu_hint(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "Отправьте команду <code>/client &lt;telegram_id&gt;</code>, "
        "чтобы открыть профиль нужного клиента."
    )


@router.message(F.text == "🚫 Бан / ✅ Разбан")
async def admin_ban_menu_hint(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "Используйте команды:\n"
        "• <code>/ban &lt;user_id&gt; [причина]</code>\n"
        "• <code>/unban &lt;user_id&gt;</code>"
    )


@router.message(Command("stats"))
async def admin_stats_command(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await _send_web_admin_redirect_message(message)


@router.message(Command("promo_stats"))
async def admin_promo_stats_command(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await _send_web_admin_redirect_message(message)


@router.message(F.text == "📊 Статистика")
async def admin_stats_button(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await _send_web_admin_redirect_message(message)


@router.message(F.text == "🎟 Промокоды")
async def admin_promocodes_menu(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await _send_web_admin_redirect_message(message)


@router.callback_query(F.data.startswith("admin:stats:"))
async def admin_stats_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    await _send_web_admin_redirect_callback(callback)


@router.callback_query(F.data.startswith("admin:promo"))
async def admin_promocode_disabled(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await _send_web_admin_redirect_callback(callback)


@router.message(F.text == "📝 Заметки")
async def admin_notes_menu_hint(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "Работа с заметками:\n"
        "• <code>/note &lt;user_id&gt; &lt;текст&gt;</code> — добавить заметку\n"
        "• <code>/notes &lt;user_id&gt;</code> — посмотреть заметки"
    )


# ---------------- ДЕПЛОЙ ----------------


@router.message(F.text == "🚀 Deploy")
async def admin_deploy_start(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    _, response = start_deploy_process()
    await message.answer(response)


@router.message(F.text == "📄 Deploy статус")
async def admin_deploy_status(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(build_deploy_status_text())


@router.message(F.text.in_({"📋 Товары: корзинки", "📋 Товары: курсы"}))
async def admin_products_redirect(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()
    await _send_web_admin_redirect_message(message)


# ---------------- ВЫБОР КОНКРЕТНОГО ТОВАРА ----------------


@router.callback_query(F.data.startswith("admin:product:"))
async def admin_product_selected(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await _send_web_admin_redirect_callback(callback)


# ---------------- НАЗАД К СПИСКУ ----------------


@router.callback_query(F.data == "admin:back_to_list")
async def admin_back_list(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await _send_web_admin_redirect_callback(callback)


# ---------------- НАЗАД В АДМИНКУ ----------------


@router.callback_query(F.data == "admin:back")
async def admin_back_panel(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "⚙️ Админ-панель.\nВыберите категорию:", reply_markup=get_admin_menu()
    )


# ---------------- ДОМОЙ (в обычное главное меню) ----------------


@router.callback_query(F.data == "admin:home")
async def admin_home_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "Главное меню:",
        reply_markup=_get_reply_menu(),
    )


@router.callback_query(
    F.data.startswith(
        (
            "admin:add:",
            "admin:course:new",
            "admin:edit:",
            "admin:hide:",
            "admin:toggle:",
            "admin:delete_disabled",
        )
    )
)
async def admin_products_actions_disabled(
    callback: types.CallbackQuery, state: FSMContext
):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await _send_web_admin_redirect_callback(callback)


# =====================================================================
#                 УПРАВЛЕНИЕ ДОСТУПОМ К КУРСАМ (АДМИН)
# =====================================================================


async def _send_course_access_list(target_message: types.Message) -> None:
    courses = products_service.get_courses()
    text = "🎓 Выберите курс для управления доступом:" if courses else "Пока нет курсов для управления доступом."

    await target_message.answer(
        text,
        reply_markup=course_access_list_kb(courses),
    )


async def _send_course_access_info(target_message: types.Message, course_id: int) -> None:
    course = products_service.get_product_by_id(course_id)
    if not course or course.get("type") != "course":
        await target_message.answer("Курс не найден или недоступен.")
        return

    users = orders_service.get_course_users(course_id)

    lines: list[str] = [
        f"🎓 <b>{course['name']}</b> (ID: <code>{course_id}</code>)",
        f"Пользователей с доступом: <b>{len(users)}</b>",
    ]

    if users:
        lines.append("\nСписок (первые 10):")
        for u in users[:10]:
            base = f"• {u['user_id']}"
            extra_parts: list[str] = []
            if u.get("granted_at"):
                extra_parts.append(u["granted_at"])
            if u.get("comment"):
                extra_parts.append(u["comment"])

            if extra_parts:
                base += " — " + "; ".join(extra_parts)

            lines.append(base)

        if len(users) > 10:
            lines.append(f"… и ещё {len(users) - 10} пользователей")

    await target_message.answer(
        "\n".join(lines).strip(),
        reply_markup=course_access_actions_kb(course_id),
    )


@router.message(F.text == "🎓 Доступ к курсам")
async def admin_course_access_entry(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()
    await _send_course_access_list(message)


@router.callback_query(F.data == "admin:course_access:list")
async def admin_course_access_list(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await _send_course_access_list(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:course_access:grant:"))
async def admin_course_access_grant(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        course_id = int(parts[3])
    except ValueError:
        await callback.answer("Некорректный ID курса", show_alert=True)
        return

    course = products_service.get_product_by_id(course_id)
    if not course or course.get("type") != "course":
        await callback.answer("Курс не найден", show_alert=True)
        return

    await state.clear()
    await state.update_data(course_id=course_id)
    await state.set_state(CourseAccessState.waiting_grant_user_id)

    await callback.message.answer(
        f"Введите user_id для выдачи доступа к курсу <b>{course['name']}</b> (ID: <code>{course_id}</code>):"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:course_access:revoke:"))
async def admin_course_access_revoke(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        course_id = int(parts[3])
    except ValueError:
        await callback.answer("Некорректный ID курса", show_alert=True)
        return

    course = products_service.get_product_by_id(course_id)
    if not course or course.get("type") != "course":
        await callback.answer("Курс не найден", show_alert=True)
        return

    await state.clear()
    await state.update_data(course_id=course_id)
    await state.set_state(CourseAccessState.waiting_revoke_user_id)

    await callback.message.answer(
        f"Введите user_id для отзыва доступа к курсу <b>{course['name']}</b> (ID: <code>{course_id}</code>):"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:course_access:"))
async def admin_course_access_choose(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        return

    raw_course_id = parts[2]
    if not raw_course_id.isdigit():
        await callback.answer()
        return

    course_id = int(raw_course_id)

    await _send_course_access_info(callback.message, course_id)
    await callback.answer()


@router.message(CourseAccessState.waiting_grant_user_id)
async def admin_course_access_grant_user(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    course_id = data.get("course_id")

    if not course_id:
        await state.clear()
        await message.answer("Курс не найден в состоянии. Попробуйте снова.")
        return

    try:
        user_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Нужно ввести числовой user_id. Попробуйте ещё раз:")
        return

    success = orders_service.grant_course_access(
        user_id=user_id,
        course_id=course_id,
        granted_by=message.from_user.id,
        source_order_id=None,
        comment=None,
    )

    await state.clear()

    if success:
        await message.answer(
            f"Доступ к курсу ID {course_id} выдан пользователю <code>{user_id}</code>."
        )
        await _send_course_access_info(message, course_id)
    else:
        await message.answer("Не удалось выдать доступ. Попробуйте позже.")


@router.message(CourseAccessState.waiting_revoke_user_id)
async def admin_course_access_revoke_user(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    course_id = data.get("course_id")

    if not course_id:
        await state.clear()
        await message.answer("Курс не найден в состоянии. Попробуйте снова.")
        return

    try:
        user_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Нужно ввести числовой user_id. Попробуйте ещё раз:")
        return

    success = orders_service.revoke_course_access(user_id=user_id, course_id=course_id)

    await state.clear()

    if success:
        await message.answer(
            f"Доступ к курсу ID {course_id} отозван у пользователя <code>{user_id}</code>."
        )
        await _send_course_access_info(message, course_id)
    else:
        await message.answer("Не удалось отозвать доступ. Возможно, его и так не было.")


# =====================================================================
#                          ДЕБАГ СПИСКА КОМАНД
# =====================================================================


@router.message(Command("debug_commands"))
async def admin_debug_commands(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    user_cmds = get_user_commands()
    admin_cmds = get_admin_commands()

    lines: list[str] = ["🧩 <b>Команды бота</b>", "", "👥 Пользовательские:"]

    if user_cmds:
        for name, desc in sorted(user_cmds.items()):
            lines.append(f"/{name} — {desc}")
    else:
        lines.append("(нет пользовательских команд)")

    lines.append("")
    lines.append("🛠 Админские:")

    if admin_cmds:
        for name, desc in sorted(admin_cmds.items()):
            lines.append(f"/{name} — {desc}")
    else:
        lines.append("(нет админских команд)")

    await message.answer("\n".join(lines))


# =====================================================================
#                    БАН/РАЗБАН И ЗАМЕТКИ ПО ПОЛЬЗОВАТЕЛЯМ
# =====================================================================


@router.message(Command("ban"))
async def admin_ban_user(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "Использование: <code>/ban &lt;user_id&gt; [причина]</code>"
        )
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "Использование: <code>/ban &lt;user_id&gt; [причина]</code>"
        )
        return

    reason = parts[2].strip() if len(parts) == 3 else None

    bans_service.ban_user(target_user_id, reason=reason)

    response = f"Пользователь {target_user_id} забанен."
    if reason:
        response += f" Причина: {reason}"

    await message.answer(response)


@router.message(Command("unban"))
async def admin_unban_user(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: <code>/unban &lt;user_id&gt;</code>")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: <code>/unban &lt;user_id&gt;</code>")
        return

    bans_service.unban_user(target_user_id)

    await message.answer(f"Пользователь {target_user_id} разбанен.")


@router.message(Command("note"))
async def admin_add_note(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Использование: <code>/note &lt;user_id&gt; &lt;текст заметки&gt;</code>"
        )
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "Использование: <code>/note &lt;user_id&gt; &lt;текст заметки&gt;</code>"
        )
        return

    note_text = parts[2].strip()
    if not note_text:
        await message.answer("Текст заметки не может быть пустым.")
        return

    admin_notes_service.add_note(
        user_id=target_user_id, admin_id=message.from_user.id, note=note_text
    )

    await message.answer("Заметка добавлена.")


@router.message(Command("notes"))
async def admin_show_notes(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: <code>/notes &lt;user_id&gt;</code>")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: <code>/notes &lt;user_id&gt;</code>")
        return

    notes = admin_notes_service.list_notes(target_user_id)
    if not notes:
        await message.answer("Заметок для этого пользователя пока нет.")
        return

    notes_text = format_user_notes(notes)
    await message.answer(
        "\n".join(
            [f"📝 Заметки для клиента <code>{target_user_id}</code>", "", notes_text]
        ).strip()
    )


# =====================================================================
#                           ПРОФИЛЬ КЛИЕНТА (CRM)
# =====================================================================


@router.message(Command("client"))
async def admin_client_profile(message: types.Message) -> None:
    """Показать CRM-профиль клиента по Telegram ID."""

    if not _is_admin(message.from_user.id):
        return

    usage_text = "Использование: <code>/client &lt;telegram_id_пользователя&gt;</code>"
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(usage_text)
        return

    try:
        target_user_id = int(parts[1].strip())
    except ValueError:
        await message.answer(usage_text)
        return

    user_stats = user_stats_service.get_user_order_stats(target_user_id)
    courses_summary = user_stats_service.get_user_courses_summary(target_user_id)
    ban_status = bans_service.is_banned(target_user_id)
    if ban_status.get("banned_at") and not ban_status.get("updated_at"):
        ban_status["updated_at"] = ban_status.get("banned_at")
    notes = admin_notes_service.list_notes(target_user_id, limit=5)

    has_data = any(
        [
            user_stats.get("total_orders", 0) > 0,
            courses_summary.get("count", 0) > 0,
            ban_status.get("is_banned"),
            len(notes) > 0,
        ]
    )

    if not has_data:
        await message.answer(
            "По этому пользователю пока нет данных (заказов и курсов не найдено)."
        )
        return

    text = format_admin_client_profile(
        target_user_id,
        user_stats=user_stats,
        courses_summary=courses_summary,
        ban_status=ban_status,
        notes=notes,
        notes_limit=5,
    )
    await message.answer(text)


# =====================================================================
#                           СПИСОК ЗАКАЗОВ
# =====================================================================


@router.message(Command("orders"))
@router.message(F.text == "📦 Заказы")
async def admin_orders_menu(message: types.Message):
    """
    Открытие меню заказов в админке.
    """
    if not _is_admin(message.from_user.id):
        return

    await _send_orders_menu(message)


@router.callback_query(F.data.startswith("admin:orders:status:"))
async def admin_orders_filter(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    status = parts[-1]
    orders = orders_service.get_orders_for_admin(status, limit=30)

    if status == orders_service.STATUS_NEW:
        title = "🆕 Новые заказы"
    elif status == orders_service.STATUS_IN_PROGRESS:
        title = "🕒 Заказы в работе"
    elif status == orders_service.STATUS_PAID:
        title = "✅ Оплаченные заказы"
    elif status == orders_service.STATUS_SENT:
        title = "📤 Отправленные заказы"
    elif status == orders_service.STATUS_ARCHIVED:
        title = "📁 Заказы в архиве"
    else:
        title = "📦 Все заказы"

    if not orders:
        text = "Заказов с таким статусом пока нет."
    else:
        text = f"{title}\n\n{format_orders_list_text(orders, show_client_hint=True)}"

    try:
        await callback.message.edit_text(text, reply_markup=_build_orders_menu_kb())
    except Exception:
        await callback.message.answer(text, reply_markup=_build_orders_menu_kb())

    for order in orders:
        status = order.get("status", orders_service.STATUS_NEW)
        status_title = orders_service.STATUS_TITLES.get(status, status)
        user_id = int(order.get("user_id") or 0)
        order_id = int(order.get("id") or 0)
        header_lines = [
            f"Заказ №{order_id} — {status_title}",
            f"user_id=<code>{user_id}</code>",
        ]

        await callback.message.answer(
            "\n".join(header_lines),
            reply_markup=_build_order_actions_kb(order_id, user_id),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:open:"))
async def admin_order_open(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный номер заказа", show_alert=True)
        return

    order = orders_service.get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="👤 Профиль клиента",
                    callback_data=f"admin:order:client:{order.get('user_id')}",
                )
            ]
        ]
    )

    await callback.message.answer(format_order_detail_text(order), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:paid:"))
async def admin_order_paid(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный номер заказа", show_alert=True)
        return

    success = orders_service.set_order_status(order_id, orders_service.STATUS_PAID)
    granted_count = 0
    order = orders_service.get_order_by_id(order_id)

    if success:
        granted_count = orders_service.grant_courses_from_order(
            order_id, admin_id=callback.from_user.id
        )

        admin_text = f"Заказ №{order_id} переведён в статус: Оплачен"
        if granted_count > 0:
            admin_text += f"\nОткрыт доступ к {granted_count} курсам пользователю."

        await callback.message.answer(admin_text)

        # Уведомляем пользователя о статусе/доступе
        try:
            user_id = int(order.get("user_id")) if order else None
        except Exception:
            user_id = None

        if user_id:
            user_text: str | None = None
            if granted_count > 0:
                courses = orders_service.get_courses_from_order(order_id)
                if courses:
                    user_text = format_user_courses_access_granted(order_id, courses)

            if not user_text:
                user_text = format_order_status_changed_for_user(
                    order_id, orders_service.STATUS_PAID
                )

            if user_text:
                try:
                    await callback.message.bot.send_message(
                        chat_id=user_id, text=user_text
                    )
                except Exception as e:
                    print(
                        f"Failed to notify user {user_id} about order {order_id}: {e}"
                    )
    else:
        await callback.message.answer("Не удалось изменить статус заказа.")

    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:archive:"))
async def admin_order_archive(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный номер заказа", show_alert=True)
        return

    success = orders_service.set_order_status(
        order_id, orders_service.STATUS_ARCHIVED
    )
    if success:
        await callback.message.answer(f"Заказ №{order_id} отправлен в архив.")

        order = orders_service.get_order_by_id(order_id)
        try:
            user_id = int(order.get("user_id")) if order else None
        except Exception:
            user_id = None

        if user_id:
            try:
                await callback.message.bot.send_message(
                    chat_id=user_id,
                    text=format_order_status_changed_for_user(
                        order_id, orders_service.STATUS_ARCHIVED
                    ),
                )
            except Exception as e:
                print(
                    f"Failed to notify user {user_id} about order {order_id}: {e}"
                )
    else:
        await callback.message.answer("Не удалось изменить статус заказа.")

    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:client:"))
async def admin_order_client_profile(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        target_user_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный user_id", show_alert=True)
        return

    user_stats = user_stats_service.get_user_order_stats(target_user_id)
    courses_summary = user_stats_service.get_user_courses_summary(target_user_id)
    ban_status = bans_service.is_banned(target_user_id)
    if ban_status.get("banned_at") and not ban_status.get("updated_at"):
        ban_status["updated_at"] = ban_status.get("banned_at")
    notes = admin_notes_service.list_notes(target_user_id, limit=5)

    has_data = any(
        [
            user_stats.get("total_orders", 0) > 0,
            courses_summary.get("count", 0) > 0,
            ban_status.get("is_banned"),
            len(notes) > 0,
        ]
    )

    if not has_data:
        await callback.message.answer(
            "По этому пользователю пока нет данных (заказов и курсов не найдено)."
        )
        await callback.answer()
        return

    text = format_admin_client_profile(
        target_user_id,
        user_stats=user_stats,
        courses_summary=courses_summary,
        ban_status=ban_status,
        notes=notes,
        notes_limit=5,
    )
    await callback.message.answer(text)
    await callback.answer()


# ---------------- ВЫХОД В ГЛАВНОЕ МЕНЮ ----------------


@router.message(F.text == "⬅️ В главное меню")
async def admin_go_main(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=_get_reply_menu(),
    )


# ---------------- ФИЛЬТР СПИСКА ТОВАРОВ В АДМИНКЕ ----------------


@router.callback_query(F.data.startswith("admin:flt:"))
async def admin_filter_products(callback: types.CallbackQuery, state: FSMContext):
    """
    admin:flt:<type>:<status>

    type:
        - basket
        - course

    status:
        - all
        - active
        - hidden / deleted (считаем как скрытые)
    """
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Неверный формат фильтра.", show_alert=True)
        return

    _, _, product_type, status_code = parts

    if product_type not in ("basket", "course"):
        await callback.answer("Неизвестная категория.", show_alert=True)
        return

    status_code = (status_code or "all").lower()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_products_list(callback.message, state, category=product_type, status=status_code)
    await callback.answer()


# ---------------- ПУСТАЯ КНОПКА (для строки «пока нет товаров») ----------------


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: types.CallbackQuery):
    """
    Ничего не делаем, просто закрываем «кружочек» загрузки.
    """
    if not _is_admin(callback.from_user.id):
        return

    await callback.answer()
