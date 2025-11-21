from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_admin_menu() -> ReplyKeyboardMarkup:
    """
    Клавиатура для админ-панели.
    """
    keyboard = [
        [KeyboardButton(text="📦 Заказы")],
        [KeyboardButton(text="/id")],
        [KeyboardButton(text="📋 Товары: корзинки")],
        [KeyboardButton(text="📋 Товары: курсы")],
        [KeyboardButton(text="🎟 Промокоды")],
        [KeyboardButton(text="⬅️ В главное меню")],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Админ-панель",
    )


def get_products_actions_menu(product_type: str | None = None) -> ReplyKeyboardMarkup:
    """
    Меню действий над товарами (для раздела Товары: корзинки/курсы).

    product_type:
      - "basket" -> в меню будет кнопка "➕ Добавить корзинку"
      - "course" -> в меню будет кнопка "➕ Добавить курс"
      - None     -> без кнопки добавления (например, вызов после редактирования).
    """
    keyboard: list[list[KeyboardButton]] = []

    # Первая строка — добавление товара в нужной категории
    if product_type == "basket":
        keyboard.append([KeyboardButton(text="➕ Добавить корзинку")])
    elif product_type == "course":
        keyboard.append([KeyboardButton(text="➕ Добавить курс")])

    # Остальные действия
    keyboard.append(
        [
            KeyboardButton(text="✏️ Изменить название"),
            KeyboardButton(text="💰 Изменить цену"),
        ]
    )
    keyboard.append(
        [
            KeyboardButton(text="📝 Изменить описание"),
            KeyboardButton(text="🔗 Изменить ссылку"),
        ]
    )
    keyboard.append(
        [
            KeyboardButton(text="🖼 Изменить фото"),
        ]
    )
    keyboard.append(
        [
            KeyboardButton(text="🚫 Скрыть товар"),
            KeyboardButton(text="🔁 Вкл/выкл показ"),
        ]
    )
    keyboard.append(
        [
            KeyboardButton(text="⬅️ Назад"),
        ]
    )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Управление товарами",
    )
