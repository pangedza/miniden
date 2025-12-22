"""Шаблоны сценариев для AdminBot.

Файл содержит стартовые пресеты, которые создаются при инициализации БД.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Описание шаблонов: код, заголовок, описание и JSON с узлами/триггерами
STARTER_TEMPLATES: List[Dict[str, Any]] = [
    {
        "code": "tpl_welcome_menu",
        "title": "Приветствие + меню",
        "description": "Старт /start → MAIN_MENU с кнопками для быстрого знакомства.",
        "template_json": {
            "description": "Простое приветствие с основным меню и сбором вопроса",
            "nodes": [
                {
                    "code": "WELCOME_START",
                    "title": "Стартовое приветствие",
                    "message_text": (
                        "<b>Добро пожаловать!</b> Мы подготовили меню, чтобы вы быстро нашли нужный раздел.\n"
                        "Нажмите кнопку ниже, чтобы открыть главное меню."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "Открыть меню",
                            "type": "callback",
                            "payload": "OPEN_NODE:MAIN_MENU",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        }
                    ],
                },
                {
                    "code": "MAIN_MENU",
                    "title": "Главное меню",
                    "message_text": (
                        "Выберите раздел: узнать о проекте, получить ссылку или задать вопрос."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "ℹ️ О проекте",
                            "type": "callback",
                            "payload": "OPEN_NODE:ABOUT_INFO",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "📎 Ссылки",
                            "type": "callback",
                            "payload": "OPEN_NODE:LINKS",
                            "row": 0,
                            "pos": 1,
                            "is_enabled": True,
                        },
                        {
                            "title": "✉️ Задать вопрос",
                            "type": "callback",
                            "payload": "OPEN_NODE:ASK_MESSAGE",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "ABOUT_INFO",
                    "title": "Описание",
                    "message_text": "Расскажите коротко, чем полезен ваш проект. Текст можно менять после применения.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "⬅️ Назад",
                            "type": "callback",
                            "payload": "OPEN_NODE:MAIN_MENU",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        }
                    ],
                },
                {
                    "code": "LINKS",
                    "title": "Полезные ссылки",
                    "message_text": "Добавьте ссылки на сайт, каталог или соцсети.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "🌐 Сайт",
                            "type": "url",
                            "payload": "https://example.com",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "⬅️ В меню",
                            "type": "callback",
                            "payload": "OPEN_NODE:MAIN_MENU",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "ASK_MESSAGE",
                    "title": "Получить вопрос",
                    "message_text": "Напишите ваш вопрос или пожелание. Мы ответим лично.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "TEXT",
                    "input_var_key": "question",
                    "input_required": True,
                    "input_min_len": 3,
                    "input_error_text": "Опишите вопрос, чтобы мы могли помочь.",
                    "next_node_code_success": "THANKS",
                    "next_node_code_cancel": "MAIN_MENU",
                    "is_enabled": True,
                },
                {
                    "code": "THANKS",
                    "title": "Спасибо",
                    "message_text": "Спасибо! Мы получили ваш вопрос и вернёмся с ответом.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {
                                "text": "Новое обращение из приветственного шаблона: {{question}}",
                            },
                            "sort_order": 0,
                            "is_enabled": True,
                        },
                        {
                            "action_type": "SEND_MESSAGE",
                            "payload": {"text": "Ваше сообщение сохранено, скоро ответим."},
                            "sort_order": 1,
                            "is_enabled": True,
                        },
                    ],
                    "next_node_code": "MAIN_MENU",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "start",
                    "match_mode": "EXACT",
                    "target_node_code": "WELCOME_START",
                    "priority": 1,
                    "is_enabled": True,
                },
                {
                    "trigger_type": "TEXT",
                    "trigger_value": "меню",
                    "match_mode": "CONTAINS",
                    "target_node_code": "MAIN_MENU",
                    "priority": 5,
                    "is_enabled": True,
                },
            ],
        },
    },
    {
        "code": "tpl_subscription_gate",
        "title": "Проверка подписки + меню",
        "description": "Доступ к меню только после подписки на канал.",
        "template_json": {
            "description": "Проверка подписки с переходом в меню после успеха",
            "nodes": [
                {
                    "code": "SUBSCRIPTION_CHECK",
                    "title": "Проверка подписки",
                    "message_text": (
                        "Подпишитесь на канал, затем нажмите «Проверить подписку»."
                    ),
                    "parse_mode": "HTML",
                    "node_type": "CONDITION",
                    "cond_var_key": None,
                    "cond_operator": None,
                    "next_node_code_true": "MAIN_MENU",
                    "next_node_code_false": "SUBSCRIPTION_CHECK",
                    "is_enabled": True,
                    "config_json": {
                        "condition_type": "CHECK_SUBSCRIPTION",
                        "condition_payload": {
                            "channels": ["https://t.me/your_channel"],
                            "on_success_node": "MAIN_MENU",
                            "on_fail_node": "SUBSCRIPTION_CHECK",
                            "fail_message": "Нужно подписаться, чтобы открыть меню.",
                            "subscribe_url": "https://t.me/your_channel",
                            "check_button_text": "Проверить подписку",
                            "subscribe_button_text": "Подписаться",
                        },
                    },
                    "buttons": [],
                },
                {
                    "code": "MAIN_MENU",
                    "title": "Главное меню",
                    "message_text": "Вы успешно подписались! Выберите раздел.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "📢 Новости",
                            "type": "url",
                            "payload": "https://t.me/your_channel",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "ℹ️ О проекте",
                            "type": "callback",
                            "payload": "OPEN_NODE:ABOUT",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "✉️ Написать",
                            "type": "callback",
                            "payload": "OPEN_NODE:CONTACT",
                            "row": 1,
                            "pos": 1,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "ABOUT",
                    "title": "Описание",
                    "message_text": "Расскажите, что получите подписчики. Текст можно менять.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "⬅️ Меню",
                            "type": "callback",
                            "payload": "OPEN_NODE:MAIN_MENU",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        }
                    ],
                },
                {
                    "code": "CONTACT",
                    "title": "Написать в поддержку",
                    "message_text": "Напишите ваш вопрос, мы ответим в личку.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "TEXT",
                    "input_var_key": "question",
                    "input_required": True,
                    "input_min_len": 4,
                    "input_error_text": "Напишите пару слов, чтобы мы помогли.",
                    "next_node_code_success": "CONTACT_THANKS",
                    "next_node_code_cancel": "MAIN_MENU",
                    "is_enabled": True,
                },
                {
                    "code": "CONTACT_THANKS",
                    "title": "Спасибо",
                    "message_text": "Спасибо! Мы получили обращение.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {"text": "Сообщение после подписки: {{question}}"},
                            "sort_order": 0,
                            "is_enabled": True,
                        }
                    ],
                    "next_node_code": "MAIN_MENU",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "start",
                    "match_mode": "EXACT",
                    "target_node_code": "SUBSCRIPTION_CHECK",
                    "priority": 1,
                    "is_enabled": True,
                },
                {
                    "trigger_type": "TEXT",
                    "trigger_value": "меню",
                    "match_mode": "CONTAINS",
                    "target_node_code": "SUBSCRIPTION_CHECK",
                    "priority": 10,
                    "is_enabled": True,
                },
            ],
        },
    },
    {
        "code": "tpl_support_simple",
        "title": "Поддержка (просто)",
        "description": "Кнопка 'Написать' → сбор сообщения → уведомление админу.",
        "template_json": {
            "description": "Мини-форма обращения в поддержку",
            "nodes": [
                {
                    "code": "SUPPORT_START",
                    "title": "Поддержка",
                    "message_text": "Расскажите о проблеме: мы ответим в рабочее время.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "📝 Написать",
                            "type": "callback",
                            "payload": "OPEN_NODE:SUPPORT_INPUT",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        }
                    ],
                },
                {
                    "code": "SUPPORT_INPUT",
                    "title": "Получить текст",
                    "message_text": "Опишите вопрос или запрос.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "TEXT",
                    "input_var_key": "support_text",
                    "input_required": True,
                    "input_min_len": 5,
                    "input_error_text": "Нужно хотя бы пару слов, чтобы помочь.",
                    "next_node_code_success": "SUPPORT_THANKS",
                    "next_node_code_cancel": "SUPPORT_START",
                    "is_enabled": True,
                },
                {
                    "code": "SUPPORT_THANKS",
                    "title": "Отправлено",
                    "message_text": "Спасибо! Сообщение передано команде.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {"text": "Новое обращение: {{support_text}}"},
                            "sort_order": 0,
                            "is_enabled": True,
                        },
                        {
                            "action_type": "SEND_MESSAGE",
                            "payload": {"text": "Мы получили ваш запрос и скоро ответим."},
                            "sort_order": 1,
                            "is_enabled": True,
                        },
                    ],
                    "next_node_code": "SUPPORT_START",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "TEXT",
                    "trigger_value": "поддержка",
                    "match_mode": "CONTAINS",
                    "target_node_code": "SUPPORT_START",
                    "priority": 5,
                    "is_enabled": True,
                }
            ],
        },
    },
    {
        "code": "tpl_shop_minimal",
        "title": "Магазин (минимальный)",
        "description": "Категории → карточка → 'Получить' (ссылка/чат)",
        "template_json": {
            "description": "Мини-витрина с категориями и ссылкой на покупку",
            "nodes": [
                {
                    "code": "SHOP_MENU",
                    "title": "Категории",
                    "message_text": "Выберите категорию, чтобы посмотреть товары.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "🎁 Популярное",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_FEATURED",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "🛍 Все товары",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_CARD",
                            "row": 0,
                            "pos": 1,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "SHOP_FEATURED",
                    "title": "Популярное",
                    "message_text": "Добавьте описание топового предложения.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "Получить",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_CONTACT",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "⬅️ Категории",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_MENU",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "SHOP_CARD",
                    "title": "Карточка",
                    "message_text": "Кратко опишите товар и добавьте ссылку или кнопку 'Получить'.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "Перейти на сайт",
                            "type": "url",
                            "payload": "https://example.com/buy",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "Получить в чате",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_CONTACT",
                            "row": 0,
                            "pos": 1,
                            "is_enabled": True,
                        },
                        {
                            "title": "⬅️ Категории",
                            "type": "callback",
                            "payload": "OPEN_NODE:SHOP_MENU",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "SHOP_CONTACT",
                    "title": "Контакт",
                    "message_text": "Оставьте телефон или @username для оформления заказа.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "PHONE_TEXT",
                    "input_var_key": "shop_contact",
                    "input_required": True,
                    "input_min_len": 5,
                    "input_error_text": "Нужен телефон или ник, чтобы оформить заказ.",
                    "next_node_code_success": "SHOP_THANKS",
                    "next_node_code_cancel": "SHOP_MENU",
                    "is_enabled": True,
                },
                {
                    "code": "SHOP_THANKS",
                    "title": "Спасибо",
                    "message_text": "Спасибо! Мы свяжемся для подтверждения заказа.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {"text": "Заявка из магазина: {{shop_contact}}"},
                            "sort_order": 0,
                            "is_enabled": True,
                        },
                        {
                            "action_type": "SEND_MESSAGE",
                            "payload": {"text": "Мы получили запрос и напишем вам."},
                            "sort_order": 1,
                            "is_enabled": True,
                        },
                    ],
                    "next_node_code": "SHOP_MENU",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "shop",
                    "match_mode": "EXACT",
                    "target_node_code": "SHOP_MENU",
                    "priority": 5,
                    "is_enabled": True,
                }
            ],
        },
    },
    {
        "code": "tpl_courses_minimal",
        "title": "Мастер-классы (минимальный)",
        "description": "Платные/бесплатные → 'Получить'",
        "template_json": {
            "description": "Витрина мастер-классов с выбором и выдачей ссылки",
            "nodes": [
                {
                    "code": "COURSES_MENU",
                    "title": "Категории",
                    "message_text": "Выберите формат мастер-класса.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "💳 Платные",
                            "type": "callback",
                            "payload": "OPEN_NODE:COURSES_PAID",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "🎁 Бесплатные",
                            "type": "callback",
                            "payload": "OPEN_NODE:COURSES_FREE",
                            "row": 0,
                            "pos": 1,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "COURSES_PAID",
                    "title": "Платные",
                    "message_text": "Добавьте список платных мастер-классов и ссылку на оплату.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "Оплатить",
                            "type": "url",
                            "payload": "https://example.com/pay",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "Запросить консультацию",
                            "type": "callback",
                            "payload": "OPEN_NODE:COURSES_CONTACT",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "⬅️ Назад",
                            "type": "callback",
                            "payload": "OPEN_NODE:COURSES_MENU",
                            "row": 2,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "COURSES_FREE",
                    "title": "Бесплатные",
                    "message_text": "Добавьте ссылку на бесплатный материал или урок.",
                    "parse_mode": "HTML",
                    "node_type": "MESSAGE",
                    "is_enabled": True,
                    "buttons": [
                        {
                            "title": "Получить",
                            "type": "url",
                            "payload": "https://example.com/free",
                            "row": 0,
                            "pos": 0,
                            "is_enabled": True,
                        },
                        {
                            "title": "⬅️ Назад",
                            "type": "callback",
                            "payload": "OPEN_NODE:COURSES_MENU",
                            "row": 1,
                            "pos": 0,
                            "is_enabled": True,
                        },
                    ],
                },
                {
                    "code": "COURSES_CONTACT",
                    "title": "Контакт",
                    "message_text": "Оставьте контакт, чтобы обсудить детали мастер-класса.",
                    "parse_mode": "HTML",
                    "node_type": "INPUT",
                    "input_type": "PHONE_TEXT",
                    "input_var_key": "course_contact",
                    "input_required": True,
                    "input_min_len": 5,
                    "input_error_text": "Нужен телефон или @username.",
                    "next_node_code_success": "COURSES_THANKS",
                    "next_node_code_cancel": "COURSES_MENU",
                    "is_enabled": True,
                },
                {
                    "code": "COURSES_THANKS",
                    "title": "Спасибо",
                    "message_text": "Спасибо! Мы свяжемся, чтобы рассказать детали.",
                    "parse_mode": "HTML",
                    "node_type": "ACTION",
                    "is_enabled": True,
                    "actions": [
                        {
                            "action_type": "SEND_ADMIN_MESSAGE",
                            "payload": {"text": "Запрос на мастер-класс: {{course_contact}}"},
                            "sort_order": 0,
                            "is_enabled": True,
                        }
                    ],
                    "next_node_code": "COURSES_MENU",
                },
            ],
            "triggers": [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "course",
                    "match_mode": "EXACT",
                    "target_node_code": "COURSES_MENU",
                    "priority": 5,
                    "is_enabled": True,
                }
            ],
        },
    },
]
