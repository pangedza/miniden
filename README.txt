MiniDeN — Telegram-бот и веб-магазин
====================================

Архитектура проекта
-------------------
- Telegram-бот (`bot.py`): точка входа, проверка подписки, стартовый экран и главное меню с WebApp-кнопками, мини-CRM для админов.
- Backend (`webapi.py`): FastAPI-приложение `webapi:app`, обслуживает авторизацию, каталог, корзину, заказы, избранное, промокоды и админку.
- PostgreSQL: единая база данных для бота, WebApp и сайта (строка подключения `DATABASE_URL`).
- WebApp: HTML/JS-фронтенд магазина, корзины, профиля и админки, получает данные только через `webapi:app`.
- Legacy shim (`main.py`): прокидывает `app` из `webapi.py` для обратной совместимости; в продакшене запускать `uvicorn webapi:app`.

Структура проекта
-----------------
- `bot.py` — точка входа Telegram-бота.
- `webapi.py` — основной backend (FastAPI).
- `main.py` — shim для совместимости (импортирует `webapi.app`).
- `config.py` — загрузка настроек из `.env`.
- `database.py` — подключение к PostgreSQL (SQLAlchemy).
- `models.py` — общие ORM-модели.
- `handlers/` — актуальные роутеры бота (`start.py`, `webapp.py`, админская CRM в `admin.py`).
- `services/` — бизнес-логика (пользователи, товары, корзина, заказы, промокоды и пр.).
- `webapp/` — статические HTML/JS-страницы витрины, профиля и админки.
- `docs/legacy-data/` — сохранённые JSON-файлы старой версии каталога (`products_baskets.json`, `products_courses.json`).
- `api/routers/` — legacy-эндпоинты, оставлены только как архив.
- `examples/example_openai.py` — пример использования OpenAI API (не часть продакшн-кода).

Правила репозитория
-------------------
- `.env` НЕ хранится в git и управляется вручную. Codex его НЕ изменяет.
- `.gitignore` НЕ изменяется Codex'ом — он управляется вручную.

База данных
-----------
Backend и бот работают от одной PostgreSQL-базы (`DATABASE_URL`). Таблицы создаются через `database.init_db()`, а сервисы из `services/` используют общие модели из `models.py`.

Запуск в продакшене
--------------------
- Backend: `uvicorn webapi:app --host 0.0.0.0 --port 8000`.
- Бот: `python -m bot` (aiogram 3, настройки из `config.py`, инициализация БД через `init_db()`).

Systemd и nginx
---------------
- Рекомендуется настроить два systemd-unit'а: один для бота (exec=`/usr/bin/python -m bot`) и один для backend'а (exec=`/usr/bin/uvicorn webapi:app --host 0.0.0.0 --port 8000`), оба с автоперезапуском и загрузкой переменных окружения из `/etc/miniden.env`.
- Nginx проксирует HTTPS-трафик на backend: `location /api/ { proxy_pass http://127.0.0.1:8000; proxy_set_header X-Real-IP $remote_addr; }`. Статику WebApp можно раздавать напрямую (root в директорию `webapp/`).
- Скрипт `deploy.sh` не изменяется и остаётся как есть.

Legacy
------
- Старые API-роутеры лежат в `api/routers/` и помечены как архивные.
- Исторические seed-файлы перенесены в `docs/legacy-data/`; PostgreSQL — единственный источник данных в продакшене.
