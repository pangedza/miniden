"""CLI-скрипт для создания первого SuperAdmin."""

import argparse

from admin_panel.auth import hash_password
from database import SessionLocal, init_db
from models import AdminUser


def main() -> None:
    parser = argparse.ArgumentParser(description="Создание SuperAdmin для admin_panel")
    parser.add_argument("--username", required=True, help="Имя пользователя SuperAdmin")
    parser.add_argument("--password", required=True, help="Пароль SuperAdmin")
    args = parser.parse_args()

    init_db()

    db = SessionLocal()
    try:
        exists = db.query(AdminUser).filter(AdminUser.username == args.username).first()
        if exists:
            print(f"Пользователь {args.username} уже существует (id={exists.id}).")
            return

        user = AdminUser(
            username=args.username,
            password_hash=hash_password(args.password),
            role="SuperAdmin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Создан SuperAdmin: {user.username} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
