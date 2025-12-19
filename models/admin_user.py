"""Модели и роли админов."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class AdminRole(str, Enum):
    superadmin = "superadmin"
    admin_bot = "admin_bot"
    admin_site = "admin_site"


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('superadmin', 'admin_bot', 'admin_site')",
            name="ck_admin_users_role",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(
        String(50),
        nullable=False,
        default=AdminRole.superadmin.value,
        server_default=AdminRole.superadmin.value,
    )
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        server_default="NOW()",
    )

    sessions = relationship(
        "AdminSession", back_populates="user", cascade="all, delete-orphan"
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token = Column(String(128), unique=True, nullable=False, index=True)
    app = Column(String(32), nullable=False, default="admin", server_default="admin")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("AdminUser", back_populates="sessions")


__all__ = ["AdminUser", "AdminSession", "AdminRole"]
