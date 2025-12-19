"""Совместимость: тонкие врапперы над новой auth-службой."""

from models.admin_user import AdminRole, AdminSession, AdminUser
from services import auth as auth_service
from services.passwords import hash_password, verify_password

create_session = auth_service.create_session
delete_session = auth_service.remove_session
SESSION_TTL_HOURS = auth_service.SESSION_TTL_HOURS
