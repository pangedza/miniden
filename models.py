from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
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

    @property
    def name(self) -> str:
        return self.title


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    qty = Column(Integer, nullable=False, default=1)

    user = relationship("User", back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="orders")
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


__all__ = [
    "Base",
    "CartItem",
    "Order",
    "OrderItem",
    "ProductBasket",
    "ProductCourse",
    "User",
]
