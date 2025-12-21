"""Шаблоны сценариев для AdminBot.

Файл содержит стартовые пресеты, которые создаются при инициализации БД.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Описание шаблонов: код, заголовок, описание и JSON с узлами/триггерами
STARTER_TEMPLATES: List[Dict[str, Any]] = [
    {
        "code": "welcome_bot",
        "title": "Приветственный бот",
        "description": "Быстрое приветствие с заявкой и подсказками для новых пользователей.",
        "template_json": {
            "description": "Базовый поток приветствия и простой заявки.",
            "nodes": [
                {
                    "code": "WELCOME_MAIN",
                    "title": "Приветствие",
                    "message_text": (
                        "<b>Добро пожаловать!</b> Я помогу рассказать о проекте и собрать вопросы.\n\n"
                        "Используйте кнопки ниже, чтобы узнать подробнее."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "🚀 Начать знакомство",
                            "type": "callback",
                            "payload": "OPEN_NODE:WELCOME_MENU",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "📝 Оставить вопрос",
                            "type": "callback",
                            "payload": "OPEN_NODE:WELCOME_CONTACT",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "WELCOME_MENU",
                    "title": "Навигация",
                    "message_text": (
                        "Вот что я умею: поделиться описанием, дать ссылки и принять сообщение для команды."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "ℹ️ О проекте",
                            "type": "callback",
                            "payload": "OPEN_NODE:WELCOME_ABOUT",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "✉️ Связаться",
                            "type": "callback",
                            "payload": "OPEN_NODE:WELCOME_CONTACT",
                            "row": 0,
                            "pos": 1,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "WELCOME_ABOUT",
                    "title": "Описание",
                    "message_text": (
                        "Расскажите, чем вы полезны: услуги, сроки, формат работы. Текст легко поменять после применения шаблона."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "⬅️ Назад",
                            "type": "callback",
                            "payload": "OPEN_NODE:WELCOME_MENU",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        }
                    ],
                },
                {
                    "code": "WELCOME_CONTACT",
                    "title": "Получить вопрос",
                    "message_text": "Напишите ваш вопрос или контакт, мы ответим в ближайшее время.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "TEXT",
                    "input_var_key": "contact",
                    "input_required": True,
                    "input_min_len": 5,
                    "input_error_text": "Напишите сообщение, чтобы мы могли ответить.",
                    "next_node_code_success": "WELCOME_THANKS",
                    "next_node_code_cancel": "WELCOME_MENU",
                    "is_enabled": True,
                },
                {
                    "code": "WELCOME_THANKS",
                    "title": "Спасибо",
                    "message_text": "Спасибо! Сообщение передано команде.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {
                                "text": "Новое обращение из приветственного бота: {{contact}}",
                            },
                            "sort_order": 0,
                            "is_enabled": True,
                        },
                        {
                            "action_type": "SEND_MESSAGE",
                            "payload": {"text": "Ваше обращение записано, мы ответим."},
                            "sort_order": 1,
                            "is_enabled": True,
                        },
                    ],
                    "next_node_code": "WELCOME_MENU",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "welcome",
                    "match_mode": "EXACT",
                    "target_node_code": "WELCOME_MAIN",
                    "priority": 5,
                    "is_enabled": True,
                },
                {
                    "trigger_type": "TEXT",
                    "trigger_value": "привет",
                    "match_mode": "CONTAINS",
                    "target_node_code": "WELCOME_MAIN",
                    "priority": 10,
                    "is_enabled": True,
                },
            ],
        },
    },
    {
        "code": "support_bot",
        "title": "Бот поддержки",
        "description": "Собирает имя, контакт и вопрос, отправляет заявку администраторам.",
        "template_json": {
            "description": "Мини-форма обращения в поддержку.",
            "nodes": [
                {
                    "code": "SUPPORT_START",
                    "title": "Старт поддержки",
                    "message_text": "Опишите проблему, а мы вернёмся с ответом.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "📨 Оставить обращение",
                            "type": "callback",
                            "payload": "OPEN_NODE:SUPPORT_ASK_NAME",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        }
                    ],
                },
                {
                    "code": "SUPPORT_ASK_NAME",
                    "title": "Имя",
                    "message_text": "Как вас зовут?", 
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "TEXT",
                    "input_var_key": "name",
                    "input_required": True,
                    "input_min_len": 2,
                    "input_error_text": "Введите имя, чтобы мы знали, как к вам обращаться.",
                    "next_node_code_success": "SUPPORT_ASK_CONTACT",
                    "next_node_code_cancel": "SUPPORT_START",
                    "is_enabled": True,
                },
                {
                    "code": "SUPPORT_ASK_CONTACT",
                    "title": "Контакт",
                    "message_text": "Оставьте телефон или @username для связи.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "PHONE_TEXT",
                    "input_var_key": "contact",
                    "input_required": True,
                    "input_min_len": 5,
                    "input_error_text": "Укажите телефон или ник, чтобы мы могли ответить.",
                    "next_node_code_success": "SUPPORT_ASK_QUESTION",
                    "next_node_code_cancel": "SUPPORT_START",
                    "is_enabled": True,
                },
                {
                    "code": "SUPPORT_ASK_QUESTION",
                    "title": "Вопрос",
                    "message_text": "Опишите ситуацию или вопрос подробно.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "TEXT",
                    "input_var_key": "question",
                    "input_required": True,
                    "input_min_len": 5,
                    "input_error_text": "Добавьте детали, чтобы мы быстрее помогли.",
                    "next_node_code_success": "SUPPORT_SUMMARY",
                    "next_node_code_cancel": "SUPPORT_START",
                    "is_enabled": True,
                },
                {
                    "code": "SUPPORT_SUMMARY",
                    "title": "Отправка",
                    "message_text": "Спасибо! Мы приняли заявку и ответим в рабочее время.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {
                                "text": (
                                    "Новая заявка в поддержку:\n"
                                    "Имя: {{name}}\n"
                                    "Контакт: {{contact}}\n"
                                    "Вопрос: {{question}}"
                                ),
                            },
                            "sort_order": 0,
                            "is_enabled": True,
                        },
                        {
                            "action_type": "SEND_MESSAGE",
                            "payload": {"text": "Мы на связи и скоро ответим."},
                            "sort_order": 1,
                            "is_enabled": True,
                        },
                    ],
                    "next_node_code": "SUPPORT_START",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "support",
                    "match_mode": "EXACT",
                    "target_node_code": "SUPPORT_START",
                    "priority": 5,
                    "is_enabled": True,
                },
                {
                    "trigger_type": "TEXT",
                    "trigger_value": "поддержка",
                    "match_mode": "CONTAINS",
                    "target_node_code": "SUPPORT_START",
                    "priority": 10,
                    "is_enabled": True,
                },
            ],
        },
    },
    {
        "code": "shop_bot",
        "title": "Простой магазин",
        "description": "Витрина с каталогом, корзиной и контактами для заказов.",
        "template_json": {
            "description": "Мини-сценарий магазина: меню, каталог, контакт.",
            "nodes": [
                {
                    "code": "SHOP_HOME",
                    "title": "Главное меню",
                    "message_text": (
                        "Это стартовый экран магазина. Расскажите, что продаёте, и ведите клиента к каталогу."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "🛍 Каталог",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_CATALOG",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "🛒 Корзина",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_CART",
                            "row": 0,
                            "pos": 1,
                            "is_enabled": True,
                        },
                        {
                            "title": "☎️ Консультация",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_CONTACT",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "SHOP_CATALOG",
                    "title": "Каталог",
                    "message_text": (
                        "Добавьте ссылки на ваш сайт или WebApp. Можно заменить кнопки на свои категории."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "Открыть каталог",
                            "type": "url",
                            "payload": "https://example.com/catalog",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "⬅️ В меню",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_HOME",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "SHOP_CART",
                    "title": "Корзина",
                    "message_text": "Расскажите, как клиент может оформить заказ и что проверить перед оплатой.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "Оформить заказ",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_CONTACT",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "⬅️ В меню",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_HOME",
                            "row": 0,
                            "pos": 1,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "SHOP_CONTACT",
                    "title": "Запрос контакта",
                    "message_text": (
                        "Оставьте телефон или удобный способ связи, и менеджер оформит заказ."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "PHONE_TEXT",
                    "input_var_key": "shop_contact",
                    "input_required": True,
                    "input_min_len": 5,
                    "input_error_text": "Нужен телефон или ник, чтобы продолжить оформление.",
                    "next_node_code_success": "SHOP_THANKS",
                    "next_node_code_cancel": "SHOP_HOME",
                    "is_enabled": True,
                },
                {
                    "code": "SHOP_THANKS",
                    "title": "Завершение",
                    "message_text": "Спасибо за интерес! Мы свяжемся для подтверждения заказа.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {
                                "text": "Заявка из магазина. Контакт: {{shop_contact}}",
                            },
                            "sort_order": 0,
                            "is_enabled": True,
                        },
                        {
                            "action_type": "SEND_MESSAGE",
                            "payload": {"text": "Мы получили заявку и выходим на связь."},
                            "sort_order": 1,
                            "is_enabled": True,
                        },
                    ],
                    "next_node_code": "SHOP_HOME",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "shop",
                    "match_mode": "EXACT",
                    "target_node_code": "SHOP_HOME",
                    "priority": 5,
                    "is_enabled": True,
                },
                {
                    "trigger_type": "TEXT",
                    "trigger_value": "магазин",
                    "match_mode": "CONTAINS",
                    "target_node_code": "SHOP_HOME",
                    "priority": 10,
                    "is_enabled": True,
                },
            ],
        },
    },
]
