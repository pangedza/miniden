from typing import Iterable


def format_basket_list(baskets: Iterable[dict]) -> str:
    lines: list[str] = ["🧺 <b>Наши корзинки</b>:\n"]
    for item in baskets:
        lines.append(
            f"• <b>{item.get('name')}</b> — {item.get('price')} ₽\n"
            f"{item.get('description', '').strip()}"
        )
        url = item.get("detail_url")
        if url:
            lines.append(f"Подробнее: {url}")
        lines.append("")

    return "\n".join(lines).strip()


def format_course_list(courses: Iterable[dict]) -> str:
    lines: list[str] = ["🎓 <b>Наши онлайн-курсы</b>:\n"]
    for item in courses:
        lines.append(
            f"• <b>{item.get('name')}</b> — {item.get('price')} ₽\n"
            f"{item.get('description', '').strip()}"
        )
        url = item.get("detail_url")
        if url:
            lines.append(f"Подробнее: {url}")
        lines.append("")

    return "\n".join(lines).strip()
