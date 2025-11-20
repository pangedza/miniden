from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _status_label(product: dict) -> str:
    """
    Текстовый статус товара для админ-списка.
    """
    is_active = int(product.get("is_active") or 0)
    if is_active == 1:
        return "✅ активен"
    else:
        return "🚫 скрыт / «удалён»"


def products_list_kb(
    products: list[dict],
    product_type: str,
    status_filter: str = "all",
) -> InlineKeyboardMarkup:
    """
    Список товаров для админа — с фильтрами и статусами.
    """

    rows: list[list[InlineKeyboardButton]] = []

    # ----- первая строка — фильтры -----
    status_filter = (status_filter or "all").lower()

    filter_items = [
        ("all", "Все"),
        ("active", "Активные"),
        ("hidden", "Скрытые/удалённые"),
    ]

    filter_row: list[InlineKeyboardButton] = []
    for code, label in filter_items:
        text = ("✅ " if code == status_filter else "") + label
        filter_row.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"admin:flt:{product_type}:{code}",
            )
        )
    rows.append(filter_row)

    # ----- список товаров -----
    if not products:
        rows.append(
            [
                InlineKeyboardButton(
                    text="(пока нет товаров)",
                    callback_data="admin:noop",
                )
            ]
        )
    else:
        for p in products:
            title = f"{p['id']}. {p['name']} — {_status_label(p)}"
            rows.append(
                [
                    InlineKeyboardButton(
                        text=title,
                        callback_data=f"admin:product:{p['id']}",
                    )
                ]
            )

    # ----- кнопка «Добавить» -----
    if product_type == "basket":
        add_text = "➕ Добавить корзинку"
        add_cb = "admin:add:basket"
    else:
        add_text = "➕ Добавить курс"
        add_cb = "admin:add:course"

    rows.append(
        [
            InlineKeyboardButton(
                text=add_text,
                callback_data=add_cb,
            )
        ]
    )

    # ----- назад в админку -----
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅ Назад в админку",
                callback_data="admin:back",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_actions_kb(product_id: int) -> InlineKeyboardMarkup:
    """
    Меню редактирования конкретного товара (админка).
    Кнопка «Удалить» по сути делает «Скрыть» (is_active = 0),
    чтобы можно было вернуть товар обратно кнопкой «Показ».
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏ Название",
                    callback_data=f"admin:edit:name:{product_id}",
                ),
                InlineKeyboardButton(
                    text="💰 Цена",
                    callback_data=f"admin:edit:price:{product_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📝 Описание",
                    callback_data=f"admin:edit:desc:{product_id}",
                ),
                InlineKeyboardButton(
                    text="🔗 Ссылка",
                    callback_data=f"admin:edit:link:{product_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🖼 Фото",
                    callback_data=f"admin:edit:photo:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Скрыть",
                    callback_data=f"admin:hide:{product_id}",
                ),
                InlineKeyboardButton(
                    text="🔁 Показ",
                    callback_data=f"admin:toggle:{product_id}",
                ),
            ],
            # «Удалить» = то же самое, что «Скрыть»
            [
                InlineKeyboardButton(
                    text="❌ Удалить (скрыть)",
                    callback_data=f"admin:hide:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Назад",
                    callback_data="admin:back_to_list",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Домой",
                    callback_data="admin:home",
                ),
            ],
        ]
    )


def course_access_list_kb(courses: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if not courses:
        rows.append([
            InlineKeyboardButton(text="(нет курсов)", callback_data="admin:noop")
        ])
    else:
        for course in courses:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{course['id']}. {course['name']}",
                        callback_data=f"admin:course_access:{course['id']}",
                    )
                ]
            )

    rows.append(
        [InlineKeyboardButton(text="⬅ Назад в админку", callback_data="admin:back")]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_access_actions_kb(course_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Выдать доступ",
                    callback_data=f"admin:course_access:grant:{course_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Отозвать доступ",
                    callback_data=f"admin:course_access:revoke:{course_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅ К списку курсов",
                    callback_data="admin:course_access:list",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Назад в админку",
                    callback_data="admin:back",
                )
            ],
        ]
    )
