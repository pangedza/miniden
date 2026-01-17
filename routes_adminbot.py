"""Роуты API для конструктора бота."""

from fastapi import APIRouter

from admin_panel.routes import adminbot as adminbot_routes

router = APIRouter()
router.include_router(adminbot_routes.router)
