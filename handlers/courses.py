from aiogram import Router, types, F

from services.products import get_courses
from utils.texts import format_course_list

router = Router()


@router.message(F.text == "🎓 Онлайн-курсы")
async def show_courses(message: types.Message) -> None:
    courses = get_courses()
    if not courses:
        await message.answer("Список курсов пока пуст. Попробуйте позже 🙈")
        return

    text = format_course_list(courses)
    await message.answer(text, disable_web_page_preview=True)
