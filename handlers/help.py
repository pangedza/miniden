from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import get_settings
from utils.texts import (
    format_help_main,
    format_help_order,
    format_help_payment,
    format_help_courses,
)

router = Router()


def _get_admin_url() -> str | None:
    settings = get_settings()
    if settings.admin_chat_id:
        return f"tg://user?id={settings.admin_chat_id}"
    return None


def _help_menu_keyboard(admin_url: str | None) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Как оформить заказ?", callback_data="help:order")],
        [InlineKeyboardButton(text="Про оплату", callback_data="help:payment")],
        [InlineKeyboardButton(text="Доступ к курсам", callback_data="help:course")],
    ]

    if admin_url:
        buttons.append([InlineKeyboardButton(text="Связаться с админом", url=admin_url)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _help_back_keyboard(admin_url: str | None) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="⬅️ Назад в FAQ", callback_data="help:main")]
    ]

    if admin_url:
        buttons.append([InlineKeyboardButton(text="Связаться с админом", url=admin_url)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message) -> None:
    admin_url = _get_admin_url()
    await message.answer(
        format_help_main(),
        reply_markup=_help_menu_keyboard(admin_url),
    )


@router.callback_query(F.data == "help:main")
async def cb_help_main(callback: CallbackQuery) -> None:
    admin_url = _get_admin_url()
    await callback.message.answer(
        format_help_main(),
        reply_markup=_help_menu_keyboard(admin_url),
    )
    await callback.answer()


@router.callback_query(F.data == "help:order")
async def cb_help_order(callback: CallbackQuery) -> None:
    admin_url = _get_admin_url()
    await callback.message.answer(
        format_help_order(),
        reply_markup=_help_back_keyboard(admin_url),
    )
    await callback.answer()


@router.callback_query(F.data == "help:payment")
async def cb_help_payment(callback: CallbackQuery) -> None:
    admin_url = _get_admin_url()
    await callback.message.answer(
        format_help_payment(),
        reply_markup=_help_back_keyboard(admin_url),
    )
    await callback.answer()


@router.callback_query(F.data == "help:course")
async def cb_help_course(callback: CallbackQuery) -> None:
    admin_url = _get_admin_url()
    await callback.message.answer(
        format_help_courses(),
        reply_markup=_help_back_keyboard(admin_url),
    )
    await callback.answer()
