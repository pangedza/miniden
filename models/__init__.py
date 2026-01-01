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
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base
from models.admin_user import (
    AdminPermission,
    AdminRole,
    AdminRoleModel,
    AdminRolePermission,
    AdminSession,
    AdminUser,
    AdminUserRole,
)


class BotNode(Base):
    __tablename__ = "bot_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    message_text = Column(Text, nullable=False)
    parse_mode = Column(String, nullable=False, default="HTML", server_default="HTML")
    image_url = Column(Text, nullable=True)
    node_type = Column(String, nullable=False, default="MESSAGE", server_default="MESSAGE")
    input_type = Column(String, nullable=True)
    input_var_key = Column(String, nullable=True)
    input_required = Column(Boolean, nullable=False, default=True, server_default="true")
    input_min_len = Column(Integer, nullable=True)
    input_error_text = Column(Text, nullable=True)
    next_node_code_success = Column(String, nullable=True)
    next_node_code_cancel = Column(String, nullable=True)
    next_node_code = Column(String, nullable=True)
    cond_var_key = Column(String, nullable=True)
    cond_operator = Column(String, nullable=True)
    cond_value = Column(Text, nullable=True)
    next_node_code_true = Column(String, nullable=True)
    next_node_code_false = Column(String, nullable=True)
    config_json = Column(JSONB, nullable=True)
    clear_chat = Column(Boolean, nullable=False, default=False, server_default="false")
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="true")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=False)

    buttons = relationship(
        "BotButton",
        back_populates="node",
        cascade="all, delete-orphan",
        order_by="(BotButton.row, BotButton.pos, BotButton.id)",
    )


class BotButton(Base):
    __tablename__ = "bot_buttons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(Integer, ForeignKey("bot_nodes.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    action_type = Column(String(16), nullable=False, default="NODE", server_default="NODE")
    target_node_code = Column(String(64), nullable=True)
    url = Column(Text, nullable=True)
    webapp_url = Column(Text, nullable=True)
    row = Column(Integer, nullable=False, default=0, server_default="0")
    pos = Column(Integer, nullable=False, default=0, server_default="0")
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="true")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=False)

    node = relationship("BotNode", back_populates="buttons")


class BotNodeAction(Base):
    __tablename__ = "bot_node_actions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    node_code = Column(String(64), index=True, nullable=False)
    action_type = Column(String(32), nullable=False)
    action_payload = Column(JSONB, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="true")


class BotAction(Base):
    __tablename__ = "bot_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_code = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    handler_type = Column(String, nullable=False)
    handler_payload_schema = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="true")


class BotRuntime(Base):
    __tablename__ = "bot_runtime"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_version = Column(Integer, nullable=False, default=1, server_default="1")
    start_node_code = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=True)


class BotTrigger(Base):
    __tablename__ = "bot_triggers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trigger_type = Column(String(16), nullable=False)
    trigger_value = Column(Text, nullable=True)
    match_mode = Column(String(16), nullable=False, default="EXACT", server_default="EXACT")
    target_node_code = Column(String(64), nullable=False)
    priority = Column(Integer, nullable=False, default=100, server_default="100")
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="true")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=False)


class MenuButton(Base):
    __tablename__ = "menu_buttons"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    text = Column(String(255), nullable=False)
    action_type = Column(String(16), nullable=False, default="NODE", server_default="NODE")
    action_payload = Column(Text, nullable=True)
    row = Column(Integer, nullable=False, default=0, server_default="0")
    position = Column(Integer, nullable=False, default=0, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=False)


class BotTemplate(Base):
    __tablename__ = "bot_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    template_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BotLog(Base):
    __tablename__ = "bot_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(BigInteger, index=True, nullable=False)
    username = Column(String(64), nullable=True)
    event_type = Column(String(32), nullable=False)
    node_code = Column(String(64), nullable=True)
    details = Column(Text, nullable=True)
    config_version = Column(Integer, nullable=False, default=1, server_default="1")


class ProductBasket(Base):
    __tablename__ = "products_baskets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    short_description = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    stock = Column(Integer, nullable=False, default=0, server_default="0")
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
    stock = Column(Integer, nullable=False, default=0, server_default="0")
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
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    type = Column(String, nullable=False, default="basket")
    page_id = Column(Integer, ForeignKey("adminsite_categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=False)

    page = relationship("AdminSiteCategory")


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


class UserTag(Base):
    __tablename__ = "user_tags"

    __table_args__ = (
        Index("ix_user_tags_user_tag", "user_id", "tag", unique=True),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    tag = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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


class SiteBranding(Base):
    __tablename__ = "site_branding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_title = Column(String, nullable=True)
    logo_url = Column(Text, nullable=True)
    favicon_url = Column(Text, nullable=True)
    assets_version = Column(Integer, nullable=False, default=1, server_default="1")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=True)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_favorites_user_product_type", Favorite.user_id, Favorite.product_id, Favorite.type, unique=True)


class UserVar(Base):
    __tablename__ = "user_vars"

    __table_args__ = (
        Index("ix_user_vars_user_key", "user_id", "key", unique=True),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    key = Column(String, index=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=False)


class UserState(Base):
    __tablename__ = "user_state"

    user_id = Column(BigInteger, primary_key=True)
    waiting_node_code = Column(String, nullable=True)
    waiting_input_type = Column(String, nullable=True)
    waiting_var_key = Column(String, nullable=True)
    next_node_code_success = Column(String, nullable=True)
    next_node_code_cancel = Column(String, nullable=True)
    bot_message_ids = Column(JSONB, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now(), nullable=False)


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
    product_id = Column(
        Integer, ForeignKey("products_baskets.id", ondelete="CASCADE"), nullable=True
    )
    masterclass_id = Column(
        Integer, ForeignKey("products_courses.id", ondelete="CASCADE"), nullable=True
    )
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
    masterclass = relationship("ProductCourse", foreign_keys=[masterclass_id])
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
    block_key = Column(String(100), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    subtitle = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
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


class FaqItem(Base):
    __tablename__ = "faq"

    id = Column(Integer, primary_key=True)
    category = Column(String(64), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class WebChatSession(Base):
    __tablename__ = "webchat_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    session_key = Column(String(64), unique=True, index=True, nullable=True)
    user_identifier = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    client_ip = Column(String(64), nullable=True)
    status = Column(String(16), default="open", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_message_at = Column(DateTime, nullable=True, index=True)
    unread_for_manager = Column(Integer, default=0, nullable=False)
    telegram_thread_message_id = Column(BigInteger, nullable=True)

    messages = relationship(
        "WebChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="WebChatMessage.created_at",
    )


class WebChatMessage(Base):
    __tablename__ = "webchat_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("webchat_sessions.id"), nullable=False, index=True)
    sender = Column(String(16), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_read_by_manager = Column(Boolean, nullable=False, default=False)
    is_read_by_client = Column(Boolean, nullable=False, default=False)

    session = relationship("WebChatSession", back_populates="messages")


class AdminSiteCategory(Base):
    __tablename__ = "adminsite_categories"
    __table_args__ = (
        CheckConstraint(
            "type IN ('product', 'course')",
            name="ck_adminsite_categories_type",
        ),
        UniqueConstraint(
            "type",
            "slug",
            name="uq_adminsite_categories_type_slug",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(32), nullable=False)
    title = Column(Text, nullable=False)
    slug = Column(String(150), nullable=False)
    parent_id = Column(Integer, ForeignKey("adminsite_categories.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    sort = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    children = relationship("AdminSiteCategory", remote_side=[id], lazy="selectin")
    items = relationship(
        "AdminSiteItem",
        back_populates="category",
        lazy="selectin",
    )


class AdminSiteItem(Base):
    __tablename__ = "adminsite_items"
    __table_args__ = (
        CheckConstraint(
            "type IN ('product', 'course')",
            name="ck_adminsite_items_type",
        ),
        UniqueConstraint(
            "type",
            "category_id",
            "slug",
            name="uq_adminsite_items_type_category_slug",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(32), nullable=False)
    category_id = Column(
        Integer,
        ForeignKey("adminsite_categories.id"),
        nullable=False,
    )
    title = Column(Text, nullable=False)
    slug = Column(String(150), nullable=False)
    price = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    stock = Column(Integer, nullable=False, default=0, server_default="0")
    image_url = Column(Text, nullable=True)
    short_text = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    sort = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    category = relationship("AdminSiteCategory", back_populates="items")


class AdminSitePage(Base):
    __tablename__ = "adminsite_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), nullable=False, unique=True)
    template_id = Column(String(64), nullable=False, default="services", server_default="services")
    blocks = Column(JSONB, nullable=False, default=list, server_default="[]")
    theme = Column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

__all__ = [
    "BotNode",
    "BotButton",
    "BotAction",
    "BotRuntime",
    "Base",
    "AdminSession",
    "AdminUser",
    "AdminRole",
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
    "FaqItem",
    "WebChatSession",
    "WebChatMessage",
    "AdminSiteCategory",
    "AdminSiteItem",
    "AdminSitePage",
]
