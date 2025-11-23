import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker


DB_NAME = os.getenv("DB_NAME", "miniden")
DB_USER = os.getenv("DB_USER", "miniden_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "strongpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

engine = create_engine(DATABASE_URL, future=True, echo=os.getenv("SQLALCHEMY_ECHO") == "1")
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from config import ADMIN_IDS_SET  # noqa: WPS433
    from models import Base, User  # noqa: WPS433

    Base.metadata.create_all(bind=engine)

    if ADMIN_IDS_SET:
        with get_session() as session:
            for admin_id in ADMIN_IDS_SET:
                user = session.scalar(select(User).where(User.telegram_id == admin_id))
                if user:
                    if not user.is_admin:
                        user.is_admin = True
                else:
                    session.add(User(telegram_id=admin_id, is_admin=True))


def get_connection():
    """Legacy compatibility stub for old sqlite-style code."""
    raise RuntimeError("Use SQLAlchemy sessions via get_session() instead of direct connections")
