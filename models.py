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
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class ProductBasket(Base):
    __tablename__ = "products_baskets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    image = Column(Text, nullable=True)
    detail_url = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    category_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def name(self) -> str:
        return self.title


class ProductCourse(Base):
    __tablename__ = "products_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    image = Column(Text, nullable=True)
    detail_url = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    category_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def name(self) -> str:
        return self.title


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")


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


class PromoCode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True, index=True)
    discount_type = Column(String, nullable=False)
    value = Column(Integer, nullable=False)
    min_order_total = Column(Integer, nullable=True)
    max_uses = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


__all__ = [
    "Base",
    "CartItem",
    "Favorite",
    "Order",
    "OrderItem",
    "PromoCode",
    "ProductBasket",
    "ProductCourse",
    "User",
]
