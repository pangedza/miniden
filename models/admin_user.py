"""Модели и роли админов."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class AdminRole(str, Enum):
    superadmin = "superadmin"
    admin_bot = "admin_bot"
    admin_site = "admin_site"
    moderator = "moderator"
    viewer = "viewer"


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('superadmin', 'admin_bot', 'admin_site', 'moderator', 'viewer')",
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

    roles = relationship(
        "AdminRoleModel",
        secondary="admin_user_roles",
        back_populates="users",
        lazy="selectin",
    )

    def role_codes(self) -> list[str]:
        if self.roles:
            return [role.code for role in self.roles]
        return [self.role] if self.role else []

    def has_role(self, code: str) -> bool:
        return code in self.role_codes()


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


class AdminRoleModel(Base):
    __tablename__ = "admin_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    title = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)

    permissions = relationship(
        "AdminPermission",
        secondary="admin_role_permissions",
        back_populates="roles",
        lazy="selectin",
    )
    users = relationship(
        "AdminUser",
        secondary="admin_user_roles",
        back_populates="roles",
        lazy="selectin",
    )


class AdminPermission(Base):
    __tablename__ = "admin_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

    roles = relationship(
        "AdminRoleModel",
        secondary="admin_role_permissions",
        back_populates="permissions",
        lazy="selectin",
    )


class AdminUserRole(Base):
    __tablename__ = "admin_user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_admin_user_role"),)

    user_id = Column(
        Integer,
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id = Column(
        Integer,
        ForeignKey("admin_roles.id", ondelete="CASCADE"),
        primary_key=True,
    )


class AdminRolePermission(Base):
    __tablename__ = "admin_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_admin_role_permission"),
    )

    role_id = Column(
        Integer,
        ForeignKey("admin_roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id = Column(
        Integer,
        ForeignKey("admin_permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )


__all__ = [
    "AdminUser",
    "AdminSession",
    "AdminRole",
    "AdminRoleModel",
    "AdminPermission",
    "AdminRolePermission",
    "AdminUserRole",
]
