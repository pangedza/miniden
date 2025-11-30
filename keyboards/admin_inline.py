from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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
