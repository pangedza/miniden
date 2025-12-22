"""Сброс доступа к админке без правки .env и ручного редактирования БД."""

import argparse

from database import SessionLocal, init_db
from models.admin_user import AdminRole, AdminRoleModel, AdminSession, AdminUser, AdminUserRole
from services.passwords import hash_password


def _invalidate_sessions(db, user_id: int) -> None:
    db.query(AdminSession).filter(AdminSession.user_id == user_id).delete()


def main() -> None:
    parser = argparse.ArgumentParser(description="Сброс пароля администратора AdminBot")
    parser.add_argument("--username", required=True, help="Логин администратора (например, admin)")
    parser.add_argument(
        "--password",
        required=True,
        help="Новый пароль (не выводится в консоль и не пишется в логи)",
    )
    args = parser.parse_args()

    init_db()

    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(AdminUser.username == args.username).first()
        super_role = (
            db.query(AdminRoleModel)
            .filter(AdminRoleModel.code == AdminRole.superadmin.value)
            .first()
        )
        if not super_role:
            super_role = AdminRoleModel(
                code=AdminRole.superadmin.value,
                title="Суперадмин",
                description="Полный доступ ко всем функциям",
            )
            db.add(super_role)
            db.flush()
        password_hash = hash_password(args.password)

        if user:
            user.password_hash = password_hash
            user.is_active = True
            if not user.role:
                user.role = AdminRole.superadmin.value
            _invalidate_sessions(db, user.id)
            if not user.roles:
                db.add(AdminUserRole(user_id=user.id, role_id=super_role.id))
            db.commit()
            message = (
                "Пользователь '{username}' найден: пароль сброшен, пользователь активирован."
                " Все активные сессии обнулены."
            ).format(username=args.username)
            print(message)
        else:
            user = AdminUser(
                username=args.username,
                password_hash=password_hash,
                role=AdminRole.superadmin.value,
                is_active=True,
            )
            db.add(user)
            db.flush()
            db.add(AdminUserRole(user_id=user.id, role_id=super_role.id))
            db.commit()
            db.refresh(user)
            print(f"Создан суперпользователь: '{user.username}' (id={user.id}). Пароль установлен.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
