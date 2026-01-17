from fastapi import APIRouter

from admin_panel.routes import adminbot

router = APIRouter()
router.include_router(adminbot.router)
