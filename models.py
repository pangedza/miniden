"""
ORM-модели SQLAlchemy.
Общие для Telegram-бота и backend webapi.py.
База данных — PostgreSQL.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base


class ProductBasket(Base):
    __tablename__ = "products_baskets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    short_description = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    image = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    detail_url = Column(Text, nullable=True)
    wb_url = Column(Text, nullable=True)
    ozon_url = Column(Text, nullable=True)
    yandex_url = Column(Text, nullable=True)
    avito_url = Column(Text, nullable=True)
    masterclass_url = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    category_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product_images = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.position",
    )

    @property
    def name(self) -> str:
        return self.title


class ProductCourse(Base):
    __tablename__ = "products_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    short_description = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    image = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    detail_url = Column(Text, nullable=True)
    masterclass_url = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    category_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    masterclass_images = relationship(
        "MasterclassImage",
        back_populates="masterclass",
        cascade="all, delete-orphan",
        order_by="MasterclassImage.position",
    )

    @property
    def name(self) -> str:
        return self.title


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products_baskets.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(Text, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    is_main = Column(Boolean, default=False, nullable=False)

    product = relationship("ProductBasket", back_populates="product_images")


class MasterclassImage(Base):
    __tablename__ = "masterclass_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    masterclass_id = Column(
        Integer, ForeignKey("products_courses.id", ondelete="CASCADE"), nullable=False
    )
    image_url = Column(Text, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    is_main = Column(Boolean, default=False, nullable=False)

    masterclass = relationship("ProductCourse", back_populates="masterclass_images")


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    slug = Column(String, nullable=True, unique=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    type = Column(String, nullable=False, default="basket")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    avatar_url = Column(Text, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")


class AdminNote(Base):
    __tablename__ = "admin_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False
    )
    admin_id = Column(BigInteger, nullable=True)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserBan(Base):
    __tablename__ = "user_bans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False
    )
    reason = Column(Text, nullable=True)
    banned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    active = Column(Boolean, default=True, nullable=False)


class UserStats(Base):
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    orders_count = Column(Integer, default=0, nullable=False)
    total_spent = Column(Integer, default=0, nullable=False)
    last_order_at = Column(DateTime, nullable=True)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_favorites_user_product_type", Favorite.user_id, Favorite.product_id, Favorite.type, unique=True)


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    qty = Column(Integer, nullable=False, default=1)

    user = relationship("User", back_populates="cart_items", foreign_keys=[user_id])


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="SET NULL"))
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    customer_name = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    promocode_code = Column(String, nullable=True)
    discount_amount = Column(Numeric(10, 2), nullable=True)
    status = Column(String, nullable=True)
    order_text = Column(Text, nullable=True)

    user = relationship("User", back_populates="orders", foreign_keys=[user_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False, default="basket")
    qty = Column(Integer, nullable=False, default=1)
    price = Column(Numeric(10, 2), nullable=False, default=0)

    order = relationship("Order", back_populates="items")


class ProductReview(Base):
    __tablename__ = "product_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products_baskets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    rating = Column(SmallInteger, nullable=False)
    text = Column(Text, nullable=False)
    photos_json = Column(JSONB, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    product = relationship("ProductBasket", foreign_keys=[product_id])
    order = relationship("Order", foreign_keys=[order_id])


class PromoCode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True, index=True)
    discount_type = Column(String, nullable=False)
    discount_value = Column(Numeric(10, 2), nullable=False, default=0)
    scope = Column(String, nullable=False, default="all")
    target_id = Column(Integer, nullable=True)
    date_start = Column(DateTime, nullable=True)
    date_end = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    max_uses = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0, nullable=False)
    one_per_user = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token = Column(String, primary_key=True, index=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class HomeBanner(Base):
    __tablename__ = "home_banners"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    subtitle = Column(Text, nullable=True)
    button_text = Column(String(100), nullable=True)
    button_link = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class HomeSection(Base):
    __tablename__ = "home_sections"

    id = Column(Integer, primary_key=True)
    slug = Column(String(100), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    icon = Column(String(100), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class HomePost(Base):
    __tablename__ = "home_posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    short_text = Column(Text, nullable=False)
    link = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)


__all__ = [
    "Base",
    "AdminNote",
    "CartItem",
    "Favorite",
    "Order",
    "OrderItem",
    "ProductImage",
    "MasterclassImage",
    "ProductReview",
    "PromoCode",
    "AuthSession",
    "ProductBasket",
    "ProductCourse",
    "UserBan",
    "UserStats",
    "User",
    "HomeBanner",
    "HomeSection",
    "HomePost",
]
