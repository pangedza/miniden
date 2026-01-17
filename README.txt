MiniDeN — Telegram-бот и веб-магазин
====================================

UI Upgrade витрины
------------------
- Освежён визуальный стиль витрины: спокойные фоны, мягкие границы и тени без визуального шума.
- Карточки товаров приведены к единой стабильной сетке с фиксированной высотой изображения и аккуратными hover-эффектами.
- Подправлены header, боковая навигация и нижняя корзина для более компактной и ровной компоновки.

AdminSite Task1: меню + type в URL
---------------------------------
- Изменённые файлы:
  - admin_panel/adminsite/templates/base_adminsite.html
  - admin_panel/adminsite/static/adminsite/constructor.js
- Как проверить:
  1. Открыть `/adminsite/constructor`.
  2. Нажать в верхнем меню «Товары», «Мастер-классы» или «Курсы».
  3. Убедиться, что URL меняется на `/adminsite/constructor?type=products|masterclasses|courses`, а список категорий перезагружается.

AdminSite Task2: API type фильтр
--------------------------------
- Эндпоинт: `GET /api/adminsite/categories?type=products|masterclasses|courses`
- Примечания:
  - Если `type` не указан или неизвестен — используется `products`.
  - Записи без `type` в БД трактуются как `products`.
- Примеры:
  - `GET /api/adminsite/categories` (по умолчанию `products`)
  - `GET /api/adminsite/categories?type=masterclasses`
  - `GET /api/adminsite/categories?type=courses`
- Изменённые файлы:
  - admin_panel/adminsite/router.py
  - admin_panel/adminsite/service.py

AdminSite Task3: сохранение type в create/edit
---------------------------------------------
- Изменённые файлы:
  - admin_panel/adminsite/static/adminsite/constructor.js
  - webapi.py
- Как проверить:
  1. Открыть `/adminsite/constructor?type=masterclasses`.
  2. Создать категорию и убедиться, что после обновления страницы она остаётся в мастер-классах.
  3. Перейти на `/adminsite/constructor?type=products` и убедиться, что категория не отображается.
  4. Создать категорию в продуктах и проверить, что она не появляется в мастер-классах.

Changelog / История изменений
-----------------------------
- 2026-06-XX: Корзина WebApp переведена на единое хранение в БД: браузер использует cookie `cart_session_id`, Telegram WebApp проходит серверную auth через `initData` и использует `tg_user_id`, маршруты `/api/cart*` больше не зависят от localStorage; кнопки корзины ведут на `/cart.html`.
- 2026-06-XX: В корзине WebApp добавлена модалка «Оформление заказа» с выбором: ссылка на Telegram админа и кнопка «Оформить в боте» (доступна только в Telegram WebApp и отправляет `tg.sendData({type:'cart_checkout'})`).
- 2026-06-XX: Витрина получила упрощённую нижнюю панель корзины: строка «В корзине: {count} · {total} ₽», появляется только при непустой корзине и пока реагирует на клик выводом в консоль (без отправки заказа).
- 2026-06-XX: WebApp success-модалка «Заказ отправлен» показывается только после успешного ответа `POST /api/public/checkout/from-webapp` и больше не открывается автоматически при загрузке/переходах; состояние не хранится в storage и не восстанавливается после обновления.
- 2026-06-XX: Витрина: кнопка «В корзину» активна для доступных позиций (is_active != false и stock_qty != 0), toast «Товар добавлен» показывается 2 секунды после успешного добавления, cart bar отображается при непустой корзине, а кнопка «Оформить» доступна только при наличии позиций.
- 2026-06-XX: WebApp получил фиксированную cart bar (кол-во, сумма, кнопки «Корзина»/«Оформить»). Кнопка «Оформить» шлёт содержимое корзины в Telegram через событие `webapp_checkout_created` и отправляет пользователю сообщение с кнопками. Добавлен endpoint `/api/public/checkout/from-webapp` и таблица `checkout_orders`.
- 2026-06-XX: Витрина: стабилизирован hover карточек — текст поднимается плавно без наезда на заголовок, кнопка «В корзину» появляется в закреплённой позиции без смещения верстки.
- 2026-06-XX: Карточки витрины получили iiko-like hover/focus: при наведении/фокусе карточка поднимается, описание и кнопка «В корзину» появляются без изменения высоты сетки; на touch-устройствах описание и кнопка видны всегда. Кнопка «В корзину» отключается при stock_qty=0, показывается бейдж «Нет в наличии».
- 2026-06-XX: WebApp витрина приведена к iiko-like layout: единый контейнер, sticky header, фиксированный sidebar и отдельный скролл для main/sidebar; карточки и кнопки приведены к единой сетке и design tokens.
- 2026-06-XX: Витрина обновлена под iiko-like UX: единые design tokens, фиксированный header, левый сайдбар категорий, карточки позиций и единый стиль страниц. Контентные блоки вынесены в таблицу `site_blocks`, добавлены публичные `/api/public/*` и админские `/api/admin/blocks` эндпоинты. Добавлены поля `hero_enabled`, `menu_categories.image_url`, `menu_items.legacy_link`, а также авто-сид для slug `korzinki/basket/cradle/set` для back-compat `/c/<slug>`.
- 2026-06-XX: AdminSite — восстановлены кликабельность конструктора и навигация старых разделов (товары/категории/курсы/мастер-классы/главная), отдельным пунктом оставлено «Меню витрины»; скрытые оверлеи больше не перекрывают клики.
- 2026-06-XX: Витрина и AdminSite переведены на menu-driven модель: таблицы `menu_categories`, `menu_items`, `site_settings`; публичные данные отдаются через `/public/*`, админка управляет меню через `/api/admin/menu/*` и настройками через `/api/admin/site-settings`. Старые темы/шаблоны/блоки отключены для витрины (рендер больше не зависит от `/api/site/theme` и `/api/site/pages/*`).
- 2026-06-XX: Вернули совместимость со старыми ссылками PROD_MENU `/c/<slug>`: сервер отдаёт `webapp/index.html` для `/c/{slug}`, фронтенд берёт категории из БД меню (`/public/menu`) и показывает 404-экран при неизвестном slug.
- 2026-06-XX: Публичная витрина читает только опубликованные данные конструктора: тема (/api/site/theme), меню (/api/site/menu) и страницы (/api/site/pages/{key}) возвращают version/updated_at; публикация копирует draft → published и обновляет version. Тема по умолчанию Linen & Sage, webapp применяет её через CSS variables без перекомпиляции.
- 2026-05-XX: Палитра витрины хранится в `/api/site-settings` (activePalette + cssVars); конструктор AdminSite сохраняет черновик страницы через `PUT /api/adminsite/pages/{pageKey}` и публикует через `POST /api/adminsite/pages/{pageKey}/publish`, а витрина читает опубликованные блоки по `GET /api/site/pages/{pageKey}`. Кнопка «➕» на карточке отображается только при количестве > 0 (stock/quantity/count).
- 2026-05-XX: Добавлен health-эндпоинт `/api/adminsite/health/page/{key}` и строгий контракт черновик/публикация: сохраняем блоки через `PUT /api/adminsite/pages/{key}` (draft), публикуем через `POST /api/adminsite/pages/{key}/publish` (published), публичная витрина читает только `/api/site/pages/{key}` и `/api/site/home` (published). Публичный ответ теперь содержит `theme`, а конструктор и витрина поддерживают блок `categories` без ошибок валидации.
- 2026-05-XX: Legacy `webapp/admin.html` удалена; управление витриной и главной страницей ведётся только через AdminSite (`/adminsite`, конструктор страниц/блоков/шаблонов).
- 2026-05-XX: Deploy управляется только вручную через `systemctl start miniden-deploy.service` (без вызовов из adminbot/adminsite). UI и API для запуска деплоя удалены; неизвестные action_type показываются как «Удалено», постоянное Reply-меню использует меню из `/adminbot/menu-buttons` (кнопки «Написать»/«О проекте» работают).
- 2026-04-XX: Обновление товара допускает `slug=null` — API сохраняет текущий slug в БД и не возвращает 422.
- 2026-04-XX: Обработчик валидации упаковывает ошибки безопасно (без ValidationInfo в Pydantic v2) и возвращает 422 в формате JSON.
- 2026-04-XX: /api/adminsite/items стабилизирован: бэкенд логирует ошибки и отдаёт 200 с пустым списком вместо 500, конструктор AdminSite игнорирует некорректный ответ и не падает при пустых данных.
- 2026-04-XX: ReplyKeyboard вынесен в конструктор AdminBot: добавлена таблица `menu_buttons`, страницы `/adminbot/menu-buttons` для создания/редактирования меню и флаг `clear_chat` у узлов, очищающий чат перед показом экрана.
- 2026-03-18: Добавлен учёт остатка stock для товаров/курсов в API и AdminSite: формы отображают поле «В наличии (stock)», витрина показывает кнопку «➕» только в Telegram WebApp и при наличии товара, бот принимает web_app_data add_to_cart и предлагает открыть корзину.
- 2026-02-10: Главная витрина перешла на портфолио-пресет: hero с CTA-кнопками, карточки разделов и соцсети по умолчанию. Блок категорий выводится только если добавить блок `categories` в конструкторе AdminSite.
- 2026-02-06: Global audit витрины/AdminSite. /api/site/home теперь возвращает templateId/version/updatedAt + blocksCount/blockTypes для диагностики; витрина читает конфиг только из API с защитой рендера (try/catch по блокам) и debug-оверлеем (?debug=1) со статусом запроса; кнопка «Предпросмотр» в AdminSite открывает витрину с cache-bust параметром и debug-флагом; placeholder вынесен в data URI, каталог static/uploads создаётся при старте.
- 2025-12-07: Исправлен SyntaxError в `services/products.py` (незакрытые скобки вокруг запроса категорий), из-за которого падал запуск `miniden-api`. Проверка: `python -m py_compile services/products.py`.
- 2025-12-01: Fix AdminSite static + unify nginx deploy config. Исправлено монтирование `/static` в FastAPI (ошибка `url_for('static', ...)` больше не возникает), шаблоны AdminSite теперь ссылаются на конструктор через `url_for`, а единственным источником nginx-конфига остаётся `deploy/nginx/miniden.conf`, который копируется из `deploy.sh` в `/etc/nginx/sites-available/miniden.conf` и линкуется в `sites-enabled`. Проверка: `curl -I http://127.0.0.1:8000/static/adminsite/base.css`, `curl -I http://127.0.0.1:8000/static/adminsite/constructor.js`, открытие https://miniden.ru/adminsite/ и https://miniden.ru/adminsite/constructor/ (CSS/JS должны быть 200 и с корректным Content-Type).
- Hotfix: Pydantic v2 compatibility (pattern вместо regex и др.) — backend падал при старте (502 Bad Gateway) из-за использования синтаксиса Pydantic v1 в AdminSite моделях.
- 2025-12-30: AdminSite constructor — удаление категорий возвращает 409 с причиной (если есть товары/дочерние категории/WebApp-настройки), slug валидируется по [a-z0-9-] с автогенерацией из Title и понятными ошибками 422, модалки закрываются по X/Cancel/Esc/фон/Назад, страница категории подтягивает товары по `category_id`.

Кнопка «➕» в витрине WebApp
---------------------------
- Кнопка «В корзину» активна, если позиция доступна: `is_active != false` и `stock_qty != 0` (при `stock_qty=null/undefined` ограничение не применяется).
- По клику витрина добавляет позицию в корзину через `POST /api/cart/add` (тип позиции мапится на `basket/course`); для браузера используется серверная сессия `cart_session_id`, для Telegram WebApp — `tg_user_id` из initData (через `/api/auth/telegram_webapp`).
- Cart bar появляется при наличии позиций, показывает строку «В корзине: {count} · {total} ₽» и обновляется при изменениях корзины.
- После успешного добавления показывается toast «Товар добавлен» на 2 секунды.

Корзина: единое хранение (браузер + Telegram)
---------------------------------------------
- Корзина хранится в БД (`cart_items`) и доступна через `/api/cart*`; localStorage больше не является источником истины.
- Браузер (не Telegram): корзина идентифицируется по cookie `cart_session_id`.
- Telegram WebApp: при старте выполняется `/api/auth/telegram_webapp` с `initData`, после чего корзина связана с `tg_user_id` и совпадает с ботом.

Как проверить корзину (новый поток)
-----------------------------------
1. В браузере открыть витрину, добавить товар в корзину, перейти на `/cart.html` и убедиться, что товары отображаются.
2. Обновить страницу (`F5`) и проверить, что корзина сохраняется (используется `cart_session_id`).
3. В Telegram WebApp открыть витрину из бота, добавить товар в корзину и перейти в корзину — состав должен совпадать с сервером.
4. В боте проверить, что корзина пользователя содержит те же позиции.
5. Если Telegram WebApp не авторизуется, добавить вручную `BOT_TOKEN` в окружение backend (перезапустить сервис).

WebApp checkout → Telegram (adminbot)
-------------------------------------
- В `/cart` кнопка «Оформить заказ» открывает модалку «Оформление заказа»: ссылка «Связаться с админом» ведёт на Telegram контакт из `site_settings` (или fallback), а кнопка «Оформить в боте» доступна только внутри Telegram WebApp и отправляет `tg.sendData({ type: 'cart_checkout' })`.
- Витрина берёт `tg_user_id` из `Telegram.WebApp.initDataUnsafe.user.id` и показывает кнопку «Оформить» только для Telegram WebApp.
- По клику «Оформить» отправляется `POST /api/public/checkout/from-webapp` с items/totals и клиентским контекстом.
- Success-модалка «Заказ отправлен» открывается только после успешного ответа `POST /api/public/checkout/from-webapp` и закрывается по кнопке/клику по фону; при загрузке страницы модалка не восстанавливается и не зависит от query-параметров.
- Backend сохраняет запись в `checkout_orders` и диспатчит событие `webapp_checkout_created`.
- Событие использует `bot_event_triggers` (дефолтный триггер создаётся при `init_db`) и отправляет пользователю сообщение со списком позиций и inline-кнопками («Связаться», «Открыть витрину»).
- Обработчик inline-кнопки «Связаться» принимает callback `trigger:contact_manager` (см. `handlers/support.py`).

Автоматизации (Rules)
---------------------
- Раздел AdminBot: `/adminbot/automations` — визуальный мастер правил в 3 шага: Триггер → Условия → Действия.
- Первый триггер: «Пришёл заказ из WebApp» (используется при `POST /api/public/checkout/from-webapp`).
- Действия доступны из списка: «Сохранить заказ», «Отправить сообщение пользователю», «Отправить сообщение админу», «Прикрепить набор кнопок».
- Сообщения собираются кликами: переменные вставляются через кнопки, список товаров настраивается чекбоксами, предпросмотр — справа.
- Пресеты кнопок: `/adminbot/automations/button-presets` (отдельные наборы для пользователя/админа).
- Если правил нет, можно нажать «Создать правило по шаблону» — создаст правило и дефолтные пресеты.

Доступные переменные шаблона
----------------------------
- `{order_id}` — номер заказа.
- `{total}` — сумма заказа.
- `{items}` — список товаров (по выбранным полям).
- `{user_name}` — имя пользователя.
- `{user_id}` — Telegram ID пользователя.
- `{phone}` — телефон пользователя (если известен).
- `{comment}` — комментарий к заказу (если есть).

Кнопки и пресеты по умолчанию
-----------------------------
- Пользовательский пресет: «Связаться с админом» (callback `trigger:contact_manager`), «Открыть витрину» (`{webapp_url}`).
- Админский пресет: «Написать клиенту» (`admin:order:client:{user_id}`), «Открыть витрину» (`{webapp_url}`).

Правила slug и удаления категорий (доп. 2025-12-30)
- Slug: только латиница/цифры/дефисы (`^[a-z0-9]+(?:-[a-z0-9]+)*$`), поле можно оставить пустым — slug сгенерируется из Title (транслитерация + slugify).
- Конструктор показывает подсказку по slug и чистит ввод до допустимого формата, ошибки 422 отображаются как человекочитаемые сообщения.
- Категорию нельзя удалить, если к ней привязаны элементы витрины, дочерние категории или WebApp-настройки: API вернёт 409 с перечислением блокирующих сущностей вместо 500.

Maintenance log (2025-12-26)
- Исправлен критический баг валидации формы узлов: required снимается с скрытых/неактивных полей редактора узлов, так что скрытые поля больше не блокируют сохранение. Правило: required ставится только на активные поля.
- Маршрут витрины `/c/:slug` ищет категорию по slug в нижнем регистре и, если найдена, подгружает элементы витрины по `category_id`.
- Страница категории показывает товары выбранной категории через новый `GET /api/site/items?type=...&category_id=...`.
- Модалка создания/редактирования товара/курса корректно парсит цену/категорию (значения не залипают при вводе) и закрывается по Cancel/Backdrop/Esc.
- Диагностика данных (in-memory прогон): категория «Корзинки» получила `id=1`, товар «Корзинка вязаная» — `category_id=1`.

Пример API JSON (короткий):
- `GET /public/menu/items?category=korzinki` → `{"items": [{"title": "Корзинка вязаная", "category_id": 1}]}`.

Smoke test
1. Создать в конструкторе категорию «Корзинки» (type=product, slug=korzinki, активна).
2. Создать позицию «Корзинка вязаная», выбрать категорию «Корзинки», ввести цену (например, 750) и сохранить.
3. Открыть `/c/korzinki` в витрине.
4. Убедиться, что позиция отображается в списке категории и порядок соответствует `order_index`.

Menu-driven витрина (iiko-like)
-------------------------------
- Витрина рендерит категории → позиции из `/public/menu` или `/api/public/menu` и настройки из `/public/site-settings` или `/api/public/site-settings`.
- Используется единый набор design tokens (цвета/шрифты/радиусы) и layout с левым сайдбаром.
- Блоки страницы выводятся из `site_blocks` через `/api/public/blocks?page=...` (home/category/footer/custom).
- Порядок определяется `order_index` у категорий и позиций; флаг `is_active=false` скрывает записи на сайте и в боте.
- AdminSite управляет меню через `/api/admin/menu/*`, блоками через `/api/admin/blocks` и настройками сайта через `/api/admin/site-settings`.

WebApp layout и design tokens
-----------------------------
- Layout витрины реализован в `webapp/index.html` и `webapp/cart.html`: `header.site-header` + `div.site-layout` (grid: sidebar + main) + `aside.site-sidebar` и `main.site-content`.
- Sticky header использует высоту `--headerH`, контейнер центруется через `--container`, а sidebar/main скроллятся независимо за счёт `height: calc(100vh - var(--headerH))` и `overflow: auto`.
- Design tokens объявлены в `webapp/css/theme.css` и используются через CSS variables (`--font`, `--bg`, `--surface`, `--text`, `--primary`, `--radius*`, `--shadow*`, `--container`, `--sidebarW`, `--gap`, `--pad`).
- Точки входа витрины: `/` и `/c/<slug>` (оба используют `webapp/index.html`), `/cart` использует `webapp/cart.html`, карточка позиции открывается во view `#view-product` внутри `index.html`.

Карточка позиции (ItemCard) — hover/focus и кнопка «В корзину»
--------------------------------------------------------------
- Компонент карточки формируется в `webapp/js/site_app.js`, функция `buildItemCard`.
- Стили карточки и hover/focus эффектов описаны в `webapp/css/theme.css` (классы `.catalog-card`, `.catalog-card-description`, `.catalog-card-actions`, `.catalog-card-add`, `.catalog-card-buttons`).
- Описание показывается через абсолютный overlay с плавной анимацией (opacity/transform) без изменения высоты сетки.
- На desktop при hover/focus карточка поднимается (`translateY`) и усиливает тень (`--shadow-md`).
- На touch-устройствах (`@media (hover: none)`) описание и кнопка «В корзину» видны постоянно.

Как проверить hover/focus карточки (desktop/mobile)
---------------------------------------------------
1. Открыть `/` или `/c/<slug>` и навести курсор на карточку — карточка должна подняться, появиться описание и кнопка «В корзину», сетка не смещается.
2. С клавиатуры (Tab) сфокусироваться на кнопке «Подробнее» — описание и кнопка «В корзину» должны появиться.
3. На мобильной ширине (или с эмуляцией `hover: none`) убедиться, что описание и кнопка «В корзину» отображаются без наведения.
4. Если `stock_qty == 0`, убедиться, что показывается бейдж «Нет в наличии», а кнопка «В корзину» отключена.

Как проверить верстку витрины
-----------------------------
1. Открыть `/` и убедиться, что header фиксирован, sidebar слева, main справа в контейнере 1200px.
2. Перейти в `/c/korzinki` (или любой slug) и проверить сетку карточек: 4 колонки на desktop, 2 на tablet, 1 на mobile.
3. Кликнуть по карточке товара и убедиться, что открывается модалка (крестик/ESC/фон закрывают), а URL меняется на `/i/<id>`.
4. Открыть `/cart` и проверить, что layout совпадает с главной страницей (тот же header/sidebar/main).
5. На ширине <=1024px открыть меню через кнопку «Категории» и убедиться, что sidebar открывается как drawer.

Архитектура проекта
-------------------
- Telegram-бот (`bot.py`): точка входа, проверка подписки, стартовый экран и главное меню с WebApp-кнопками, мини-CRM для админов.
- Backend (`webapi.py`): FastAPI-приложение `webapi:app`, обслуживает авторизацию, каталог, корзину, заказы, избранное, промокоды и админку.
  - Для корректной работы эндпоинтов, принимающих form-data (`UploadFile`, `Form`), требуется установленный пакет `python-multipart`.
  - Пакет включён в `requirements.txt` и ставится вместе с остальными зависимостями командой: `pip install -r requirements.txt`.
- PostgreSQL: единая база данных для бота, WebApp и сайта (строка подключения `DATABASE_URL`).
- WebApp: HTML/JS-фронтенд магазина, корзины и профиля, получает данные только через `webapi:app`.
- AdminSite (`/adminsite`): управление меню (категории/позиции/сортировка) и настройками витрины (бренд, цвета, контакты, hero).
- Legacy shim (`main.py`): прокидывает `app` из `webapi.py` для обратной совместимости; в продакшене запускать `uvicorn webapi:app`.

Ключевые API эндпоинты витрины
-----------------------------
Публичные (для сайта и бота):
- `GET /public/site-settings`
- `GET /public/menu`
- `GET /public/menu/tree?type=product|masterclass`
- `GET /public/menu/categories`
- `GET /public/menu/items?category=slug|id`
- `GET /api/public/site-settings`
- `GET /api/public/menu`
- `GET /api/public/menu/tree?type=product|masterclass`
- `GET /api/public/menu/categories`
- `GET /api/public/menu/category/{slug}`
- `GET /api/public/menu/items?category_slug=...`
- `GET /api/public/item/{id}`
- `GET /api/public/blocks?page=home|category|footer|custom`
- `POST /api/public/checkout/from-webapp`
- WebApp-роут `/c/<slug>` использует эти публичные эндпоинты и ищет категорию по `menu_categories.slug`.
- WebApp-роут `/i/<id>` открывает карточку позиции как модалку (deep-link).

Админские (для AdminSite):
- `GET/POST/PUT/DELETE /api/admin/menu/categories`
- `GET/POST/PUT/DELETE /api/admin/menu/items`
- `POST /api/admin/menu/reorder`
- `GET/PUT /api/admin/site-settings`
- `GET/POST/PUT/DELETE /api/admin/blocks`
- `POST /api/admin/blocks/reorder`

Миграции меню
-------------
- В проекте нет Alembic: таблицы `menu_categories`, `menu_items`, `site_settings`, `site_blocks` создаются через `init_db()` при запуске backend.
- Новые поля меню: `menu_categories.type`, `menu_categories.parent_id`, `menu_items.stock_qty` (null = без лимита).
- Старые таблицы товаров/страниц не удаляются и остаются для legacy-функций; перенос данных в меню выполняется вручную при необходимости.

Архитектура админки
--------------------
- `/adminbot/*` — фронтенд-маршруты (HTML/JS) админбота.
- `/adminsite/*` — веб-интерфейс AdminSite с конструктором.
- `/api/admin/*` — backend API для админских разделов; данные для форм и списков подгружаются через эти эндпоинты.
- JS админских интерфейсов всегда обращается к `/api/admin/...`, чтобы разделить frontend и backend зоны ответственности.

Создание меню и категорий через кнопки
--------------------------------------
- В разделе «Узлы» зайдите в кнопки нужного узла (например, MAIN_MENU) и нажмите «Создать кнопку».
- Заполните поля:
  - «Текст кнопки» — что увидит пользователь.
  - «Действие кнопки» — выберите NODE (переход в узел), URL или WEBAPP.
  - Для NODE не нужно вводить код вручную: выберите узел в выпадающем списке или нажмите «+ Создать новый раздел», чтобы сразу добавить узел и выбрать его.
  - Для URL/WebApp укажите ссылку вида https://example.com.
- Структура каталогов строится кнопками: пример MAIN_MENU → Товары → Категории → (узлы или WebApp/URL).
- При сохранении действие записывается и в новом формате (action_type/target/url/webapp_url), и в прежних полях type/payload для совместимости.

ReplyKeyboard-меню из конструктора AdminBot
-------------------------------------------
- Новый раздел `/adminbot/menu-buttons` позволяет создавать, редактировать и выключать кнопки нижней клавиатуры.
- Поля кнопки: `text`, `action_type` (node/command/url/webapp), `action_payload`, `row`, `position`, `is_active`.
- Бот на /start и «Меню» запрашивает активные `menu_buttons` и строит ReplyKeyboard по row/position. Если список пуст — показывает только кнопку «Меню».
- Для URL/WebApp бот отправляет сообщение с inline-кнопкой открытия ссылки.
- В форме узла добавлен флаг «Очищать чат перед показом узла» (`clear_chat`): при включении бот пытается удалить предыдущие сообщения бота перед новым экраном (best effort).

Авторизация админов
-------------------
- Точка входа: `/login` (после успешного входа перенаправляет на `/adminbot`).
- Доступные роли: `superadmin`, `admin_bot`, `moderator`, `viewer` (роль `admin_site` поддерживается для совместимости старых данных).
- Разделы:
  - `/adminbot/admins` — управление администраторами (создание, роли, включение/выключение, смена пароля; только супер-админ).
  - `/adminbot/profile` — профиль текущего пользователя (логин/роли + смена пароля по старому паролю).
  - `/admin/users`, `/admin/profile` — старые адреса админки сайта, работают как раньше.
- Роли: Суперадмин / Админ бота / Модератор / Только просмотр. Только супер-админ может менять роли и пароли других админов; модератор может работать с узлами/кнопками; роль "Только просмотр" доступна для чтения.
- Сессия хранится в БД (`admin_sessions`), cookie `admin_session` выдаётся с `HttpOnly`, `Secure`, `SameSite=Lax`.
- При пустой таблице `admin_users` автоматически создаётся superadmin: логин `admin`, пароль `admin`.

Управление администраторами (Админы)
------------------------------------
- Открыть раздел: `/adminbot/admins` (кнопка "Админы" в шапке админки).
- Создание: задайте логин, пароль, отметьте роли и флаг активности.
- Редактирование: обновление логина, набора ролей, активности и пароля (по желанию).
- Ограничение: нельзя отключить или разжаловать последнего суперадмина.

Смена пароля себе
-----------------
- Перейдите в `/adminbot/profile`, введите текущий пароль и новый пароль дважды.
- После смены пароля активные сессии сбрасываются, создаётся новая.

Восстановление доступа в AdminBot
---------------------------------
- Если вход перестал работать, а править `.env` и БД нельзя, выполните сброс пароля:
  - `cd /opt/miniden`
  - `source venv/bin/activate`
  - `/opt/miniden/venv/bin/python scripts/reset_admin.py --username admin --password admin`
- Скрипт создаёт пользователя при пустой таблице или обновляет существующего, активирует его и очищает активные сессии.

Запуск backend (FastAPI)
------------------------
- cd /opt/miniden
- source venv/bin/activate
- pip install -r requirements.txt
- uvicorn webapi:app --host 0.0.0.0 --port 8000
- НЕ запускать `python api/main.py` — это legacy shim.

Автозапуск backend через systemd
--------------------------------
1. cd /opt/miniden && source venv/bin/activate
2. pip install -r requirements.txt
3. sudo cp deploy/miniden-api.service /etc/systemd/system/miniden-api.service
4. sudo systemctl daemon-reload
5. sudo systemctl enable miniden-api
6. sudo systemctl restart miniden-api
- Проверка: sudo systemctl status miniden-api --no-pager
- Проверка URL: http://127.0.0.1:8000/adminbot/login (с сервера) и https://домен/adminbot/login (через nginx)

Production деплой (systemd)
---------------------------
- Контракт: `deploy/DEPLOY_CONTRACT.md` описывает, что именно обновляет `deploy.sh` и какие каталоги запрещено трогать.
- Скрипт `deploy.sh` обновляет git-репозиторий, применяет Alembic-миграции и перезапускает сервисы `miniden-api`/`miniden-bot`. Конфиги nginx/systemd ставятся вручную из `deploy/nginx` и `deploy/systemd`.
- Ожидаемая команда на сервере: `systemctl start miniden-deploy.service` (юнит дергает `/opt/miniden/deploy.sh`). Запуск выполняется вручную на сервере; в adminbot/adminsite нет кнопок и эндпоинтов деплоя.
- Перед запуском деплоя администратор сам обновляет зависимости внутри `venv` (например, `source venv/bin/activate && pip install -r requirements.txt`, если менялся `requirements.txt`).
- Защищённые пути (деплой не трогает): `/opt/miniden/.env`, `/opt/miniden/media/`, `/opt/miniden/data/`.
- Быстрый чек после деплоя: `curl http://127.0.0.1:8000/api/health`.

Deploy через systemd (root)
---------------------------
- Deploy запускается вручную через системный юнит `/etc/systemd/system/miniden-deploy.service` (User=root, Type=oneshot), который вызывает `/opt/miniden/deploy.sh` и пишет лог в `/opt/miniden/logs/deploy.log`.
- Установка юнита:
  1. `sudo cp deploy/systemd/miniden-deploy.service /etc/systemd/system/`
  2. `sudo systemctl daemon-reload`
  3. `sudo systemctl enable miniden-deploy.service`
- Статус и логи смотрим через `systemctl status miniden-deploy.service` и содержимое `/opt/miniden/logs/deploy.log`. Веб-интерфейс деплой не запускает.

Почему 405 на curl -I — это нормально
-------------------------------------
- Ответ 405 на `curl -I` (HEAD) для страниц авторизации — ожидаемое поведение. Используйте GET/браузер для проверки (`curl -v http://127.0.0.1:8000/adminbot/login`).

Проверка админок
----------------
- /adminbot/login
- /adminsite/login

Меню и настройки сайта (коротко)
--------------------------------
- Публичные данные: `GET /public/site-settings` и `GET /public/menu` (категории сразу с позициями), плюс `/api/public/*` аналоги.
- Блоки страницы: `GET /api/public/blocks?page=...` и админские `GET/POST/PUT/DELETE /api/admin/blocks` + `POST /api/admin/blocks/reorder`.
- Админка меню: `GET/POST/PUT/DELETE /api/admin/menu/categories`, `GET/POST/PUT/DELETE /api/admin/menu/items`, сортировка через `POST /api/admin/menu/reorder`.
- Настройки сайта: `GET/PUT /api/admin/site-settings` (brand_name, logo_url, цвета, контакты, соцсети, hero_enabled/hero_*).
- Плюс-кнопка в витрине доступна только в Telegram WebApp; отправляется `sendData` с `{action:'add_to_cart', product_id, type, source:'menu'}`.

Тронутые файлы (ключевые изменения)
----------------------------------
- `models/__init__.py`, `services/menu_catalog.py`, `webapi.py` — новые сущности меню и site settings, публичные `/public/*` и админские `/api/admin/menu/*`.
- `admin_panel/adminsite/templates/constructor.html`, `admin_panel/adminsite/static/adminsite/constructor.js` — интерфейс AdminSite под меню и настройки сайта.
- `webapp/index.html`, `webapp/js/site_app.js`, `webapp/js/site_api.js` — единый рендер меню без тем/шаблонов/блоков.

AdminSite UI / шаблоны
----------------------
- Жёсткая структура AdminSite:
  - `admin_panel/adminsite/templates/base_adminsite.html`
  - `admin_panel/adminsite/templates/dashboard.html`
  - `admin_panel/adminsite/templates/constructor.html`
  - `admin_panel/adminsite/templates/login.html`
  - `admin_panel/adminsite/static/adminsite/*` (base.css, constructor.css/js, apiClient.js, modals.js)
- Макет `base_adminsite.html` подключает `/static/adminsite/base.css` и навигацию AdminBot | AdminSite | Админы | Профиль | Выход.
- Страница конструктора подключает JS по абсолютному пути `/static/adminsite/constructor.js` (отдаётся как JavaScript, не как HTML).
- Рабочие URL после поднятия приложения и nginx:
  - `/adminsite/` (дашборд админки)
  - `/adminsite/login` (форма входа)
  - `/adminsite/constructor` (конструктор витрины)
  - `/static/adminsite/constructor.js` (JS возвращается с корректным Content-Type)

AdminSite Static
----------------
- FastAPI монтирует `/static` напрямую на `admin_panel/adminsite/static`, чтобы `url_for('static', path='adminsite/...')` работал во всех шаблонах AdminSite.
- Каталоги создаются при старте приложения; в `static/adminsite/` лежат `base.css` и `constructor.js`, доступные по URL `/static/adminsite/base.css` и `/static/adminsite/constructor.js`.
- Если сервер отдаёт 500 на `/adminsite/`, проверьте, что маршрут `static` зарегистрирован (`GET /api/adminsite/debug/routes`) и что `admin_panel/adminsite/static` существует на диске.

Логи AdminBot
-------------
- Каталог логов: `/opt/miniden/logs` (создаётся автоматически при старте приложений).
- API пишет в `/opt/miniden/logs/app.log`, бот — в `/opt/miniden/logs/bot.log`.
- Страница `/adminbot/logs` в админке показывает последние строки файлов логов (переключатель API/BOT, параметр `limit` до 2000). Если файлов нет, выводится подсказка, а не JSON 404.
- Если на странице пусто — убедитесь, что сервисы имеют права на запись в каталог `logs` и что файловые логи включены.

Почему раньше появлялся 422 при пустых числах
--------------------------------------------
- Пустые значения числовых полей в HTML-формах (например, `input_min_len=""`) превращались в `""` и отдавались FastAPI как некорректный `int`, из-за чего возникала ошибка 422.
- Теперь числовые поля админки парсятся безопасно: пустые строки приводятся к `0` для минимальной длины ввода или полностью игнорируются, поэтому MAIN_MENU и новые узлы сохраняются без падений.

Правила обязательных полей по типам узла
---------------------------------------
- MESSAGE — нужен только текст сообщения.
- INPUT — обязательны тип ввода, ключ переменной и переход при успехе; минимальная длина ввода по умолчанию 0 и может быть пустой.
- CONDITION — обязательны переменная/оператор и оба перехода; для проверки подписки требуется список каналов.
- ACTION — дополнительных обязательных полей нет; невидимые секции форм выключаются и не блокируют отправку.

Частые ошибки
-------------
- Если приложение ругается на static — убедитесь, что существует `admin_panel/static`; при запуске папки создаются автоматически.
- Если приложение сообщает об отсутствии jinja2 — установите зависимости командой `pip install -r requirements.txt`.
- Статика конструктора AdminSite лежит в `admin_panel/adminsite/static/adminsite` и отдаётся FastAPI по пути `/static/adminsite/*`; если по URL JS возвращается HTML, проверьте проксирование `/static/` в nginx и наличие директории.

Диагностика конструктора AdminSite
-----------------------------------
- JS конструктора подключается по пути `/static/adminsite/constructor.js`; при корректной настройке сервер отдаёт сам JS-код, а не HTML.
- Быстрая проверка API: `GET /api/adminsite/health` (ожидается `{ "ok": true }`).
- На странице `/adminsite/constructor` вверху отображается статусный блок: «JS: LOADED» появляется после выполнения `constructor.js`, «API: OK» — после успешного ответа health-checkа. Ошибки API (например, 401/403/500 или не-JSON ответы) показываются там же.
- Nginx должен проксировать `/static/` в backend до fallback на `/index.html`. Эталонный блок (см. `deploy/nginx/miniden.conf`):
  - `location ^~ /static/ { proxy_pass http://127.0.0.1:8000; ... }`
  - после применения конфигурации `curl -I https://<host>/static/adminsite/constructor.js` должен отдавать `Content-Type: application/javascript`, а не HTML.
  - контрольные эндпоинты: `GET /api/adminsite/debug/static` (путь/наличие constructor.js) и `GET /api/adminsite/debug/routes` (список зарегистрированных маршрутов).

Фронтенд-оболочка
------------------
- Заголовок, переключатель темы и отображение ссылки «Админка» и статуса авторизации вынесены в общий файл `webapp/js/app_shell.js`.
- Скрипт подключается на всех страницах WebApp после `api.js`, чтобы избежать дублирования кода и ошибок повторного объявления переменных.

### Категории как отдельные страницы

- Добавлены категории как самостоятельные страницы-направления: список `/categories` и детальные страницы `/category/<slug>`.
- У категорий появились поля `description` и `image_url` (хранят путь `/media/...`), изображения отдаются с версией, чтобы не кешировать старые файлы.
- Миграция product_categories дополнена безопасным добавлением столбцов description / image_url / updated_at при старте приложения.

## 🛠 Текущие задачи (на 2025-12-06)

### Страница товара и мастер-класса

- Деталка товара теперь использует тот же layout и стили, что и деталка мастер-класса: общий шаблон с левой галереей, правым блоком информации/цены/кнопок и вкладками ниже.
- Блоки товарной деталки собираются в `webapp/js/product_page.js` (галерея, заголовок, мета/бейджи, цена + CTA, вкладки «Описание» и «Отзывы»), стили берутся из `webapp/css/theme.css` (классы `product-detail`, `product-gallery`, `product-info`, `product-tabs`).
- Страница товара: новая структура с галереей слева, блоком покупки справа и вкладками ниже (описание/отзывы).
- Описание: сохраняет переносы строк в блоке с `white-space: pre-wrap`.
- Фото: object-fit contain + aspect-ratio, миниатюры переключают главное изображение.

### Обновления стабильности API и веб-чата (2025-12-06)

- Добавлен health-чек `/api/health`, чтобы быстро проверять доступность сервиса (возвращает `{ "ok": true }`).
- Эндпоинты веб-чата принимают гибкие JSON-поля: `session_key` и `text` обязательны, остальные поля опциональны; ошибки валидации логируются в backend.
- В ответе `/api/webchat/start` теперь всегда приходят `session_id` и `session_key`, чтобы виджет и бот могли надёжно продолжать сессию.
- Эндпоинт `/api/webchat/manager_reply` принимает POST с параметрами в query или JSON-ключами (`session_id`/`session_key`, `text`/`message`/`reply`) и возвращает `{ "ok": true }`.
- Добавлены отдельные админские эндпоинты для чатов в стиле мессенджера:
  - `GET /api/webchat/sessions` — список сессий с поиском/статусом/пагинацией;
  - `GET /api/webchat/sessions/{session_id}` — метаданные сессии и сообщения;
  - `POST /api/webchat/sessions/{session_id}/reply` — ответ менеджера через body {"text": "..."};
  - `POST /api/webchat/sessions/{session_id}/read` — отметка прочитанного (опционально `{ "last_read_message_id": N }`);
  - `POST /api/webchat/sessions/{session_id}/close` — закрытие диалога.
- Виджет (`webapp/js/api.js`) корректно обрабатывает не-JSON ответы (например, HTML от 502) и больше не падает на JSON.parse.
- Логи веб-чата стали подробнее: старт, пользовательские сообщения и ответы менеджера пишутся с ключевыми атрибутами, а ошибки валидации фиксируются с перечислением полей.

Проверка после деплоя:
- `curl -sS https://<host>/api/health` → `{ "ok": true }`.
- Инициализация чата в виджете (открыть сайт, нажать «?») должна возвращать 200 и показать новые сообщения из `/api/webchat/messages`.
- Ответ админа в Telegram на уведомление «Новый чат с сайта #ID» уходит POST-запросом на `/api/webchat/manager_reply` и приходит в виджет при следующей выборке сообщений.

- Legacy веб-админка (`webapp/admin.html` + `webapp/js/admin_*.js`) удалена: администрирование витрины и главной страницы перенесено в AdminSite.

- Категории стали отдельными страницами-направлениями: список `/categories` и детальные страницы `/category/{slug}` с баннером и описанием. Страницы выводят товары и мастер-классы выбранной категории и хлебные крошки для навигации.
- Управление категориями в админке: разделы «Категории товаров» и «Категории мастер-классов» позволяют задавать slug, описание, изображение, порядок и активность.
- URL-структура категорий: публичные страницы `/categories`, `/category/{slug}`, данные по API `/api/categories` и `/api/categories/{slug}`.

### Брендинг сайта из админки

- Добавлен раздел «Брендинг»: из админки можно задать название сайта, загрузить логотип и favicon. Пути хранятся в таблице `site_branding`, файлы складываются в `/media/branding/`.
- Поддерживаемые форматы: логотип — PNG/JPG/JPEG/WEBP/SVG (до 5 МБ), favicon — ICO/PNG/SVG (до 2 МБ). При отсутствии файлов используется дефолтный `/favicon.ico` и текстовый логотип MiniDeN.
- После замены логотипа или favicon автоматически увеличивается `assets_version`, а ссылки на ресурсы приходят с суффиксом `?v=...`, чтобы сбрасывать кеш в браузерах.
- Данные брендинга отдаются через публичный endpoint `/api/branding` для WebApp.

AdminSite API (категории и товары/курсы)
----------------------------------------

Все методы под префиксом `/api/adminsite/*`, требуют авторизации администратора (`superadmin` или `admin_site`). Схемы полностью совместимы с Pydantic v2.

- Health-check: `GET /api/adminsite/health` → `{ "ok": true }`.
- Категории:
  - `GET /api/adminsite/categories?type=product|course`
  - `POST /api/adminsite/categories`
  - `PUT /api/adminsite/categories/{id}`
  - `DELETE /api/adminsite/categories/{id}` (удаление запрещено, если есть товары/курсы в категории)
- Элементы (товары/мастер-классы):
  - `GET /api/adminsite/items?type=product|course&category_id=<id>`

    - `POST /api/adminsite/items`
    - `PUT /api/adminsite/items/{id}`
  - `DELETE /api/adminsite/items/{id}`

- Функционал WebApp-кнопки удалён: эндпоинты `/api/adminsite/webapp-settings` больше не доступны, связанные настройки больше не блокируют удаление категорий, таблица `adminsite_webapp_settings` удаляется при инициализации БД, вкладка WebApp в конструкторе скрыта.

- AdminPanel/adminsite: страницы конструктора
-------------------------------------------
- Маршрут `/adminsite/constructor` открывает раздел "AdminSite Конструктор" с вкладками для CRUD категорий и элементов.
- Шаблон: `admin_panel/adminsite/templates/constructor.html` (вкладки, таблицы и формы для категорий/элементов).
- Статические модули:
  - `admin_panel/adminsite/static/adminsite/apiClient.js` — обёртка над fetch с разбором ошибок.
  - `admin_panel/adminsite/static/adminsite/modals.js` — компоненты CategoryModal и ItemModal с блокировкой кнопок на время сохранения.
  - `admin_panel/adminsite/static/adminsite/constructor.js` — логика страниц: загрузка данных, фильтры, поиск по названию и CRUD.
  - `admin_panel/adminsite/static/adminsite/constructor.css` — стили карточек, таблиц, модалок и тостов.
  - URL для загрузки конструкторских статик-ресурсов: `/static/adminsite/constructor.js` и `/static/adminsite/constructor.css`.
- Новые кнопки навигации на страницах админки ведут в раздел "AdminSite Конструктор".

Примеры curl (замените `<cookie>` на значение `admin_session`):

```bash
curl -H "Cookie: admin_session=<cookie>" "http://127.0.0.1:8000/api/adminsite/categories?type=product"

curl -H "Cookie: admin_session=<cookie>" \
  -H "Content-Type: application/json" \
  -d '{"type":"product","title":"Керамика","slug":null,"sort":10}' \
  http://127.0.0.1:8000/api/adminsite/categories

curl -H "Cookie: admin_session=<cookie>" \
  -H "Content-Type: application/json" \
  -d '{"type":"product","category_id":1,"title":"Бокал","price":990}' \
  http://127.0.0.1:8000/api/adminsite/items
```

### Система отзывов

- Восстановлена исходная система отзывов:
    * используется исходная таблица и модели отзывов;
    * отзывы вновь отображаются и модерируются через админку.
- Все новые временные сущности и эндпоинты для отзывов,
  созданные при рефакторинге, отключены; фронтенд теперь
  снова пишет отзывы в основную таблицу, чтобы они
  проходили модерацию.

### Фронтенд виджета отзывов

- Для страниц товара (`webapp/product.html?id=...`) и
  мастер-класса (`webapp/masterclass.html?id=...`) используется
  общий виджет отзывов:
    * кнопка "Оставить отзыв" раскрывает аккордеон с формой;
    * можно выбрать оценку звёздами и прикрепить фотографии;
    * список отзывов отображается карточками (автор, рейтинг,
      текст, фото, дата).
- Для отправки отзывов используются существующие эндпоинты:
    * `/api/products/{id}/reviews`
    * `/api/masterclasses/{id}/reviews`
  которые интегрированы с админкой и системой модерации.

### Админка — категории товаров и мастер-классов
- Селекты категорий теперь полностью синхронизируются с API.
- Категории всегда отображаются корректно и без дублей.
- Привязка категории к товару и мастер-классу осуществляется только через category_id.
- Фильтры категорий теперь корректно используют полный список категорий из БД.

### Админка — раздел «Заказы»

- При открытии страницы по умолчанию показываются только заказы со статусом «Новый». Для просмотра всех заказов нужно явно выбрать статус «Все».
- В таблице заказов в колонке «Клиент» отображается имя покупателя (если оно указано), а не «Без имени».
- В карточке заказа отображаются контактные данные:
  - имя клиента,
  - телефон,
  - Telegram ID.
  - Блок быстрых действий:
    - «Позвонить» — ссылка tel: на номер клиента;
    - «Написать в Telegram» — ссылка на пользователя в Telegram по username или telegram_id.

## Управление главной страницей

В админке доступен раздел «Главная страница», который управляет содержимым webapp/index.html:

- **Баннеры (слайдер «Популярный набор»)**
  - админка позволяет создавать и редактировать баннеры (заголовок, подзаголовок, текст и ссылка кнопки, порядок, активность);
  - для изображений используется общий механизм загрузки файлов, как и для картинок товаров: файл загружается на сервер, в поле `image_url` сохраняется публичный URL и сразу доступен для предпросмотра;
  - в случае ошибок backend возвращает JSON с описанием, админка показывает человеко-понятное сообщение;
  - публичный API `/api/home` отдаёт только активные баннеры с сортировкой по `sort_order` и `created_at`.

- **Текстовые блоки**
  - сущность `home_sections` с полями `slug`, `title`, `text`, `icon`, `sort_order`, `is_active`;
  - используются для блоков «Почему MiniDeN» и «Как это работает» на главной; при отсутствии данных выводится прежний статический контент.

- **Мини-блог**
  - сущность `home_posts` с заголовком, коротким текстом, ссылкой, сортировкой и флагом активности;
  - на главной выводятся активные посты, отсортированные по `sort_order` и дате создания.

- **Админка → Главная страница**
  - Вкладки «Баннеры», «Блоки» и «Мини-блог» переключаются без перезагрузки страницы.
  - В каждой вкладке есть список элементов и форма редактирования:
    - при нажатии «Редактировать» в форму подставляются данные выбранного элемента;
    - кнопка «Создать …» очищает форму и создаёт новую запись;
    - после сохранения списки автоматически обновляются.

Главная страница теперь подгружает контент через API `/api/home` и собирает блоки из таблиц `home_banners`, `home_sections` и `home_posts`. Секреты и переменные окружения по-прежнему живут только в `.env`.

- Исправлены Pydantic-модели страниц главной (home_banners, home_posts, home_sections) для совместимости с Pydantic v2. Теперь используются model_config = ConfigDict(from_attributes=True), что позволяет корректно применять from_orm() для SQLAlchemy-объектов. Эндпоинты возвращают корректный JSON.

### Сортировка и порядок блоков главной

- Все блоки выдаются в API `/api/homepage/blocks` и `/api/admin/home/blocks` в порядке `sort_order` ASC, `id` ASC.
- Для ключевых блоков задаются дефолты, чтобы hero шёл первым: hero_main=10, tile_home_kids=20, tile_process=21, tile_baskets=22, tile_learning=23, about_short=30, process_text=40, shop_entry=50, learning_entry=60.
- При инициализации базы недостающие записи с этими `block_key` создаются с указанными значениями `sort_order`.

### Админка блоков главной страницы

- Вкладка «Блоки» работает как мастер-detail: слева таблица блоков, справа — форма выбранного блока.
- Клик по строке таблицы выбирает `selectedBlockId` и заполняет форму справа; после сохранения через PUT показывается статус «Сохранено» и данные сразу обновляются.
- Для картинок в версии v1 используется только поле **Image URL (https)**. Загрузка файлов пока отключена: указываем прямую ссылку, предпросмотр показывает изображение или градиент-заглушку при пустом/битом URL.

### Главная страница — баннеры

- Исправлена Pydantic-схема `HomeBannerOut`: поля `created_at` и `updated_at` теперь имеют тип `datetime`, соответствующий типам в ORM-модели. Благодаря этому вызов `HomeBannerOut.from_orm()` больше не вызывает ошибок валидации, и API `/api/admin/home/banners` стабильно возвращает корректный JSON.

Работа с изображениями главной страницы
--------------------------------------
- Картинки главной: источник = БД `image_url` (только локальные пути/домен).
- Анти-кеш: все ссылки содержат `?v=updated_at` (дополняется автоматически).
- Как заменить картинку: загрузить/положить файл на сервер → обновить `image_url` в админке → сохранить.

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
- `deploy.sh` и `.env.example` также ведутся вручную и не меняются автоматическими задачами.

Система тем WebApp
------------------
- Фронтенд MiniDeN использует систему тем на CSS-переменных: фоновый градиент, карточки, текст, границы, модальные окна и подложки зависят от набора переменных в `body[data-theme]`.
- По умолчанию включена фиолетовая тема с градиентом на базе `#150D80` (`data-theme="purple"`). Дополнительно доступны тёмная (`data-theme="dark"`) и светлая (`data-theme="light"`).
- Все ключевые цвета (фон страницы, карточек, текста, границ, оверлеев) берутся из переменных `--color-bg`, `--color-bg-card`, `--color-text-main`, `--color-text-muted`, `--color-border-subtle`, `--color-overlay` и т.д.
- В шапке страниц есть переключатель темы. Выбор сохраняется в `localStorage` (`miniden.theme`) и применяется автоматически при следующих визитах без перезагрузки.

### 🔑 Авторизация

- При первом взаимодействии с Telegram-ботом создаётся пользователь в БД,
  привязанный к `telegram_id`.
- Бот и веб-сайт используют одну и ту же учётную запись по `telegram_id`,
  чтобы корзина, заказы и профиль совпадали.
- Пользовательская часть сайта авторизуется только через Telegram:
  * если сайт открыт через Telegram Mini App — backend считывает initData
    из запроса и авторизует пользователя при обращении к `/api/auth/session`;
  * если сайт открыт в обычном браузере — используется кнопка
    «Войти через Telegram», которая запускает стандартный OAuth-поток Telegram
    и после возврата создаёт сессию на сайте.
- Для админ-панели при необходимости можно оставить отдельный логин/пароль
  на другом URL (например, /admin-login), чтобы не мешать пользователям.

### Авторизация в Telegram Mini App (WebApp)

- Мини-приложение MiniDeN запускается из Telegram-бота через
  web_app-кнопки (reply или inline). Кнопки создаются в Python-коде
  бота (см. файлы бота).
- При запуске Mini App Telegram передаёт initData (tgWebAppData /
  Telegram-Init-Data), которое backend использует для авторизации:
    * в каждом запросе к `/api/auth/session` backend пробует извлечь
      initData из query-параметров и HTTP-заголовков;
    * initData валидируется с использованием BOT_TOKEN через уже
      существующую функцию проверки;
    * при успешной проверке создаётся/находитcя пользователь в БД
      и устанавливается сессия.
- Фронтенд WebApp просто вызывает `/api/auth/session` и не
  занимается самостоятельной обработкой initData.
- В обычном браузере (если сайт открыт не из Telegram) initData
  отсутствует, поэтому авторизация происходит как раньше
  (через обычные механизмы сайта).

Профиль
-------
- На странице профиля отображается Telegram ID пользователя — он берётся из базы и недоступен для ручного редактирования.
- Имя и телефон можно менять в профиле: изменения отправляются в backend и сохраняются в базе. Эти данные используются при оформлении заказов.
- В БД хранится только текстовое поле `avatar_url` с путём до файла аватара (например, `/media/users/<telegram_id>/avatar.jpg`). Бинарные файлы аватаров в репозитории отсутствуют — владелец проекта загружает их вручную на сервер (например, `/opt/miniden/media/...`).
- В профиле WebApp аватар отображается кругом с CSS: если `avatar_url` задан и файл существует на сервере, он подставляется как фон; если `avatar_url` пустой, показываются инициалы пользователя в цветном кружке без использования файлов-заглушек.

Управление каталогом в админке
------------------------------
- В AdminSite (`/adminsite`) доступно полноценное управление двумя разделами: «Товары» (корзинки и сопутствующие товары) и «Мастер-классы».
- Карточка товара/курса включает имя, цену, краткое и полное описания, ссылку на фото, категорию и набор ссылок:
  - detail_url (подробности/лендинг),
  - wb_url, ozon_url, yandex_url, avito_url (маркетплейсы),
  - masterclass_url (основная ссылка на онлайн-курс или урок, если связан).
- [x] Админка — товары:
  - форма редактирования товара корректно работает с категориями;
  - выбранная в форме категория совпадает с отображением в таблице и на витрине (связь по `category_id`).
- [x] Админка — мастер-классы:
  - форма редактирования мастер-класса корректно привязана к категориям;
  - при смене категории в форме колонка «Категория» в таблице и отображение на сайте синхронизированы по `category_id`.
- Все ссылки сохраняются в БД (колонки wb_url/ozon_url/yandex_url/avito_url/masterclass_url добавляются при инициализации БД) и доступны в API, чтобы фронтенд выводил кнопки переходов.
- В админке можно создавать и редактировать товары/курсы с переключением активного состояния, обновлением цены, описаний, фото и ссылок, а также менять категорию.
- Для товаров и мастер-классов добавлено отдельное поле `short_description`: оно редактируется в админке и выводится на карточках витрины как краткий текст.

Фото товаров и курсов
---------------------
- Изображения товаров и онлайн-курсов загружаются через админку: админ выбирает файл на устройстве, фронтенд отправляет его на `/api/admin/upload-image`.
- Backend сохраняет файл в `/opt/miniden/media/adminsite/products/` или `/opt/miniden/media/adminsite/courses/`, генерирует уникальное имя и возвращает `image_url` вида `/media/adminsite/products/<uuid>.jpg`.
- Админка автоматически подставляет возвращённый `image_url` в карточку и показывает превью; поле можно отредактировать вручную при необходимости.
- В базе хранится только строка `image_url`; бинарные файлы изображений не коммитятся в git и создаются только на сервере во время работы backend.

Фото блоков главной страницы
----------------------------
- В админке на вкладке «Главная страница» рядом с полем Image URL появилась кнопка загрузки файла (`input[type=file]` с accept="image/*").
- При выборе файла фронтенд отправляет FormData на `/api/admin/home/upload_image`, backend сохраняет изображение в `/opt/miniden/media/adminsite/home/` и возвращает путь вида `/media/adminsite/home/<uuid>.<ext>`.
- Полученный `image_url` автоматически подставляется в форму, обновляет превью и сохраняется в блоке (для уже созданного блока обновление уходит сразу, для нового — нужно нажать «Сохранить»).

Структура директорий медиа
--------------------------
Директории создаются автоматически при старте backend:

```
/opt/miniden/media/
├── adminsite/           # все загрузки из AdminSite
│   ├── products/        # изображения товаров
│   ├── courses/         # изображения онлайн-курсов
│   ├── categories/      # картинки категорий
│   └── home/            # изображения блоков главной страницы
├── adminbot/            # вложения, загруженные из конструктора AdminBot
├── users/               # аватары пользователей
├── products/            # сервисные картинки (исторически)
├── courses/             # сервисные картинки (исторически)
├── home/                # сервисные картинки (исторически)
└── tmp/
    ├── products/        # временные загрузки товаров
    └── courses/         # временные загрузки курсов
```

Во всех случаях в базе храним веб-путь вида `/media/...` без домена; при отправке через бота или публичный фронтенд абсолютный URL собирается на клиенте из базового домена и сохранённого пути.

- В репозиторий НЕ добавлены никакие бинарные изображения.
- Разрешено использовать пустой файл `.gitkeep` для сохранения директории в Git, если структура каталогов должна быть видимой в проекте.

Кнопка «Админка»
---------------
- Ссылка на `/adminsite` показывается в шапке сайта только для пользователей с флагом `is_admin = true`.
- Для всех остальных посетителей кнопка скрыта и остаётся недоступной без авторизации администратора.

### Отзывы к товарам

- На странице товара `/webapp/product.html?id=...` теперь отображается блок "Отзывы":
  - список опубликованных отзывов для этого товара;
  - форма отправки нового отзыва (оценка и текст).
- Для загрузки и отправки отзывов используются эндпоинты:
  - `GET  /api/products/{product_id}/reviews` — список отзывов по товару;
  - `POST /api/products/{product_id}/reviews` — создание нового отзыва.
  Вся бизнес-логика (кто и когда может оставить отзыв) остаётся такой же, как в прежней системе отзывов.
- Список товаров и страница мастер-классов не изменены, отзывы отображаются только на детальной странице товара.

### Отзывы к мастер-классам

- На странице мастер-класса `/webapp/masterclass.html?id=...` теперь отображается блок "Отзывы":
  - список опубликованных отзывов для выбранного мастер-класса;
  - форма отправки нового отзыва (оценка и текст).
- Для этого используются эндпоинты:
  - `GET  /api/masterclasses/{mc_id}/reviews` — список отзывов;
  - `POST /api/masterclasses/{mc_id}/reviews` — создание отзыва.
  Логика прав доступа и модерации совпадает с отзывами к товарам.

Каталог и корзина на сайте
--------------------------
- `/products.html` (товары) и `/masterclasses.html` (мастер-классы) доступны всем пользователям, даже без авторизации — карточки грузятся напрямую из `/api/products`.
- Каталог товаров и мастер-классов доступен гостям: даже если `/api/auth/session` отвечает 401, страницы каталога всё равно запрашивают категории (`/api/categories`) и карточки (`/api/products`).
- [x] Страница «Товары»:
  - реализован поиск по названию и краткому описанию товаров (frontend);
  - товары выводятся блоками по категориям:
    отдельный блок для «Корзинок», «Люлек» и т.д.;
  - сверху есть навигация по категориям и строка поиска.
- [x] Страница «Мастер-классы»:
  - реализован поиск по названию и описанию мастер-классов (frontend);
  - мастер-классы выводятся блоками по категориям (например, для разных уровней, форматов или тематик);
  - сверху есть навигация по категориям и строка поиска.
- Кнопка «Перейти к мастер-классу» ведёт на детальную страницу (`masterclass.html?id=...`) вместо показа всплывающего окна.
- Детальная страница мастер-класса доступна по `/webapp/masterclass.html?id=...`: берет идентификатор из `?id=...`, запрашивает данные через `/api/masterclasses/{id}` и выводит карточку с описанием, ценой и кнопкой добавления в корзину/записи. Кнопки в списке мастер-классов перенаправляют на эту страницу.
- Авторизация через Telegram нужна только для сохранения корзины в базе и оформления заказа с привязкой к профилю.
- Неавторизованные пользователи могут добавлять позиции в «гостевую» корзину: данные хранятся в браузерном `localStorage` и показываются на `/cart.html`.
- Для авторизованных пользователей корзина и оформление работают через серверные эндпоинты `/api/cart/*` и `/api/checkout`.
- При успешном добавлении товара в корзину показывается компактное toast-уведомление внизу экрана («Товар добавлен в корзину»), которое автоматически исчезает через несколько секунд и не блокирует работу; механизм реализован на чистом JS/CSS и используется на всех страницах с добавлением в корзину.
- При попытке оформить заказ без авторизации страница корзины сообщает о необходимости входа и перенаправляет на `/index.html` (Telegram Login).
- После авторизации содержимое гостевой корзины автоматически переносится на сервер и связывается с Telegram ID пользователя.
- Бесплатные мастер-классы по-прежнему открываются сразу (кнопка «Перейти к мастер-классу»), платные добавляются в корзину и оплачиваются как товары.

Промокоды
---------
- Типы скидок: `percent` (проценты, ограничено 0–100) и `fixed` (фиксированная сумма).
- Области применения (`scope`): `all` — весь заказ, `basket` — только товары-корзинки, `course` — только мастер-классы, `product` — конкретный товар/курс по `target_id`, `category` — корзинки выбранной категории по `target_id`.
- Даты действия: `date_start`/`date_end` в ISO8601. Код не применяется, если текущее время вне диапазона.
- Поле `expires_at` (опциональное) автоматически конвертируется из строки в `datetime` при создании/редактировании через админку: поддерживаются форматы `YYYY-MM-DD HH:MM`, `YYYY-MM-DDTHH:MM` и `DD.MM.YYYY HH:MM`. Пустая строка сохраняет `NULL`.
- При неверном формате `expires_at` API возвращает HTTP 400 с текстом ошибки в поле `detail` вместо 500 Internal Server Error.
- Ограничения: `max_uses` (глобальный лимит), `one_per_user` (каждый пользователь может использовать только один раз; проверяется по заказам с этим промокодом), `active` (вкл/выкл).
- Учёт использования: поле `used_count` увеличивается после успешного заказа, скидка считается только по подходящим позициям корзины; фиксированная скидка не превышает сумму подходящих товаров, процентная — не выше 100%.
- API: админские эндпоинты `/api/admin/promocodes` (GET/POST/PUT/DELETE) и публичный `/api/cart/apply-promocode` для расчёта скидки в корзине. В админке доступна форма создания/редактирования с выбором области применения и лимитов.

Фронтенд каталога
------------------
- Страницы `webapp/products.html` и `webapp/masterclasses.html` используют унифицированную сетку карточек: 4 карточки в ряд на десктопе с переходом на 3/2/1 колонку на меньших экранах.
- Карточки товаров и курсов одинакового размера и повторяют структуру карточек на главной странице в блоке «Популярные категории».
- Изображения внутри карточек выводятся через `background-size: cover` или `object-fit: cover`, чтобы разные пропорции фото не ломали верстку.
- Для карточек товаров и мастер-классов выводится краткое описание (`short_description`). Если поле пустое, на карточке показывается обрезанный вариант `description` (около 140 символов) с многоточием; полный текст доступен на детальной странице.
- Страница «Мастер-классы»: кнопки фильтров («Бесплатные уроки» / «Платные курсы») оформлены в том же стиле «чипсов», что и категории на странице товаров, чтобы сохранить единство интерфейса.

### Мастер-классы

- Убрана старая кнопка «Подробнее» и модальное окно на странице `/webapp/masterclasses.html`.
- Для перехода к детальной информации используется только кнопка «Перейти к мастер-классу», ведущая на `masterclass.html?id=...`.

### Детальные страницы товаров и мастер-классов

- Добавлены отдельные страницы:
    - `/webapp/product.html?id=...` — карточка одного товара;
    - `/webapp/masterclass.html?id=...` — карточка одного мастер-класса.
- Страницы получают `id` из параметра `?id=...`, запрашивают данные через API
  `/api/products/{id}` и `/api/masterclasses/{id}` и отображают подробную карточку.
- На этих страницах доступны кнопки "В корзину"/"Записаться" и переход
  обратно к списку.
- Отзывы на страницах товара и мастер-класса теперь полностью интегрированы с основной системой отзывов и модерацией в админке:
    * новые отзывы создаются со статусом «новый» и попадают в общий список отзывов админки;
    * администратор может их одобрять или отклонять из одного места;
    * на публичных страницах отображаются только одобренные отзывы;
    * никаких временных или параллельных систем отзывов не используется.

Фронтенд и мобильная версия
---------------------------
- Боковое меню с разделами каталога реализовано как offcanvas-панель: на широких экранах навигация видна сразу, а на мобильных скрыта до нажатия на кнопку-«бургер».
- Внутри Telegram Mini App (WebApp) это позволяет не перекрывать основной контент каталога, корзины и профиля боковой панелью.
- При выборе пункта меню, повторном нажатии на бургер или клике по фоновой подложке меню автоматически закрывается.
- Offcanvas-режим работает только на экранах до 1024px: на десктопах меню остаётся статичным в шапке и не даёт горизонтальный скролл.

Обновление статики WebApp
-------------------------
- Все HTML-страницы WebApp подключают локальные js/css-файлы с параметром версии (`?v=20241205`), чтобы браузеры (особенно Яндекс.Браузер и мобильные) не держали устаревший кэш.
- При любых изменениях фронтенда (JS/CSS) обновляйте номер версии во всех HTML-файлах WebApp на одно и то же значение, чтобы пользователи сразу получили свежую статику без ручной очистки кэша.
- Если используется service worker, обновляйте его имя/версию вместе с параметром `?v=...`, чтобы предыдущие кэши автоматически инвалидировались и не мешали загрузке новых файлов.

Доступ к онлайн-курсам
----------------------
- Бесплатные мастер-классы (цена 0) становятся доступными пользователю сразу после оформления заказа.
- Платные мастер-классы открываются только после перевода связанного заказа администратором в статус «оплачен» через админский API/интерфейс.
- В профиле пользователя выводится список доступных курсов с кнопками перехода по masterclass_url; оплаченные отмечаются как «Оплаченный доступ», бесплатные — как «Бесплатный».
- В разделе «Мои заказы» для позиций типа course отображается ссылка на мастер-класс, если доступ открыт; иначе показывается текст «Ссылка появится после оплаты».

Профиль пользователя
--------------------
- На странице профиля есть блок «Мои мастер-классы», который берёт данные из поля `courses` профиля (`/api/auth/session` или `/api/auth/telegram`).
- Бесплатные курсы попадают туда автоматически, платные появляются после оплаты заказа и перевода его в статус «оплачен».
- Раздел «Мои заказы» для позиций типа course показывает подсказку «Ссылка появится после оплаты» до смены статуса; после оплаты переходы доступны через список «Мои мастер-классы».

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
- `.env`, `.gitignore` и `deploy.sh` не изменяются автоматически и поддерживаются вручную владельцем проекта.

Файлы под ручным управлением
----------------------------
- `.env`, `.env.example`, `.gitignore` и `deploy.sh` изменяются только владельцем проекта вручную и не должны правиться автоматизированными задачами.

Виджет помощника
----------------
- На сайте появилась плавающая кнопка помощника в правом нижнем углу.
- Виджет показывает категории и вопросы/ответы FAQ, загружая данные из эндпоинта `/api/faq`.
- Внутри есть кнопка перехода в Telegram-бота для связи с менеджером.
- AI не используется: все ответы берутся из базы знаний, которую администратор наполняет через админку.

Веб-чат
-------
- В виджете помощника на сайте доступен режим живого чата с менеджером.
- Сообщения пользователя сохраняются в БД и пересылаются администратору в Telegram.
- Менеджер отвечает из Telegram, а ответ отображается прямо в окне веб-чата на сайте.
- Вся логика работает без AI: только переписка пользователя и менеджера и внутренняя обработка сообщений.
- Добавлены Pydantic-модели WebChatStartPayload, WebChatMessagePayload, WebChatManagerReplyPayload.
- Это исправило ошибку NameError при старте сервиса, когда webapi.py не мог импортироваться из-за отсутствия класса.
- Модели применяются для эндпоинтов /api/webchat/start, /api/webchat/message и /api/webchat/manager_reply.

Фикс веб-чата
-------------
- В webapi.py добавлен `from __future__ import annotations`, чтобы отложить вычисление аннотаций типов и избежать NameError при импортe.
- Дополнительно добавлены и уточнены Pydantic-модели `WebChatStartPayload`, `WebChatMessagePayload`, `WebChatManagerReplyPayload`.
- Эти модели используются эндпоинтами `/api/webchat/start`, `/api/webchat/message`, `/api/webchat/manager_reply` для корректной валидации payload'ов.
- Добавлен виджет помощника (support_widget.css и support_widget.js), подключён на главной и ключевых страницах сайта. На текущем этапе показывает плавающую кнопку и простое окно чата без интеграции с API, чтобы проверить отображение.

Обновления виджета (2025-05-21)
------------------------------
- support_widget.css и support_widget.js теперь гарантированно подключены на index.html и других основных страницах веб-приложения.
- В JS добавлен console.log('Support widget script loaded'), по которому можно проверить загрузку скрипта через консоль браузера.

Интеграция веб-чата виджета
---------------------------
- Виджет помощника теперь связан с API веб-чата: используется `/api/webchat/start` для старта сессии, `/api/webchat/message` для отправки сообщений и `/api/webchat/messages` для получения истории.
- Ключ сессии сохраняется в `localStorage` под именем `support_widget_session_key`, благодаря чему история сообщений восстанавливается после перезагрузки страницы.
- Пользовательские сообщения отправляются в backend и могут быть пересланы менеджеру в Telegram, а ответы менеджера подхватываются и отображаются в виджете через периодический опрос API.

Добавлена корректная Pydantic-валидация для веб-чата:
- WebChatStartPayload
- WebChatMessagePayload
- WebChatManagerReplyPayload
Этим исправлена ошибка 422 при вызове /api/webchat/start и /api/webchat/message.
Добавлен фикс веб-чата:
- эндпоинты /api/webchat/start и /api/webchat/message теперь принимают JSON
  как словарь (payload: dict = Body(...));
- поля session_key и text/page читаются вручную, поэтому больше не возникает
  ошибки 422 Unprocessable Entity при несовпадении Pydantic-схем.
Добавлен обратный канал поддержки:
- Админ отвечает reply на сообщение "Новый чат с сайта #ID" в Telegram.
- Бот отправляет текст ответа на backend через POST /api/webchat/manager_reply.
- Ответ отображается в веб-виджете на сайте через polling /api/webchat/messages.
Исправлено: бот отправляет ответы менеджера на сайт через POST /api/webchat/manager_reply, раньше ошибочно использовался GET и backend отвечал 405 Method Not Allowed.
Исправлено: в handlers/site_chat.py функция _post_json теперь реально делает POST-запрос.
Это устранило 405 Method Not Allowed при отправке ответа менеджера на /api/webchat/manager_reply.
Исправлена отправка ответов менеджера в веб-чат:
- Бот отправляет manager_reply через POST /api/webchat/manager_reply.
- В backend добавлен GET fallback для /api/webchat/manager_reply (на случай ошибочного метода),
  принимающий session_id и text из query.
- POST /api/webchat/manager_reply теперь принимает JSON как словарь и валидирует поля вручную,
  чтобы избежать 422.
Починен обратный канал Telegram -> сайт:
- Бот отправляет ответ менеджера через POST /api/webchat/manager_reply с JSON {session_id, text}.
- Backend /api/webchat/manager_reply (POST) принимает payload как dict через Body(...) и валидирует вручную (без 422).
- GET fallback оставлен, но параметры session_id/text сделаны optional и при отсутствии возвращается 400 вместо 422.
Исправлено: бот отправляет ответы менеджера в веб-чат строго через POST /api/webchat/manager_reply
с JSON телом {session_id, text}. Убран вызов GET без query параметров, который приводил к 400/422.
Исправлен ответ менеджера для веб-чата:
- session_id извлекается из reply-сообщения по шаблону 'Новый чат с сайта #ID'
- ответы отправляются на backend строго POST /api/webchat/manager_reply с JSON {session_id, text}
- бот сообщает администратору, если reply сделан не на правильное сообщение или не найден #ID
Веб-чат: исправлено отображение ответов менеджера на сайте.
- /api/webchat/messages возвращает сообщения user и manager с полем sender.
- manager_reply сохраняет сообщение в ту же историю по session_key.
- support_widget.js отображает сообщения manager и не фильтрует их.
[FIX] WebChat manager_reply
Исправлена отправка ответов менеджера с Telegram на сайт.
session_id теперь передаётся как query-параметр, как ожидает FastAPI.
Ошибка 400 session_id is required устранена.
[FIX] WebChat manager_reply совместимость
- POST /api/webchat/manager_reply теперь принимает session_id из query ИЛИ JSON body.
- text берётся из body.
- Ответ менеджера сохраняется в ту же историю сообщений, которую читает /api/webchat/messages.
- /api/webchat/messages возвращает user+manager без фильтрации.
[BIG FIX] Поддержка/чат менеджера
- Унифицирован механизм обращений: webchat и "запрос пользователя" теперь создают одну SupportSession (#session_id).
- Любое уведомление админа содержит #ID и дополнительно сохраняется связь telegram_message_id -> session_id.
- Reply администратора работает для обоих типов уведомлений.
- Backend принимает manager_reply устойчиво (query/body), сохраняет в историю, messages возвращает user+manager.
- Виджет сайта отображает ответы менеджера.

[UPDATE] Чаты поддержки перенесены в веб-админку
- Добавлены admin API: список сессий, история, ответ менеджера, закрытие чата.
- В админке добавлена вкладка "Чаты поддержки" для переписки с клиентами.
- Виджет на сайте отображает сообщения менеджера (sender=manager).
- Telegram оставлен опционально только как уведомления (без reply логики).
[CRITICAL FIX]
- Исправлена ошибка FastAPI Invalid args for response field.
- Все response_model приведены к Pydantic моделям или отключены.
- Backend стабильно стартует, чаты поддержки могут работать.

Обновление: Lifestyle тема + Управление блоками главной
------------------------------------------------------
* Переключатель темы (`.theme-switcher` с `select#theme-select`) доступен на всех страницах, выбранное значение сохраняется в `localStorage` под ключом `miniden_theme` (поддерживается и старый `miniden.theme`).
* Проверка применения темы: выберите Lifestyle на любой странице, перейдите на товары/админку/курсы — атрибут `data-theme` на `<html>`/`<body>` обновится автоматически и сохранится после перезагрузки.
* Блоки главной страницы приходят с `/api/homepage/blocks` и идентифицируются по `block_key` (`hero_main`, `tile_home_kids`, `tile_process`, `tile_baskets`, `tile_learning`, `about_short`, `process_text`, `shop_entry`, `learning_entry`). Поля блока: `title`, `subtitle`, `body`, `button_text`, `button_url`, `image_url`, `is_active`, `order`.
* В админке раздел «Главная страница» управляет всеми блоками: можно выбрать `block_key`, редактировать тексты, ссылки, порядок, активность и картинки (загрузка через существующий аплоад). Табуляторы Hero/Плитки/Тексты/Переходы фильтруют список.
* Изображения на новой главной временно берутся по внешним HTTPS-ссылкам; при недоступности срабатывают градиентные фоны, позже можно будет заменить URL через админку.

Апдейт: миграция home_banners + стабильность главной
----------------------------------------------------
* При инициализации БД добавляются (если отсутствуют) колонки `block_key`, `subtitle`, `body`, `button_text`, `button_link`, `image_url`, `is_active` (DEFAULT TRUE), `sort_order` (DEFAULT 0), `created_at`, `updated_at` в таблицу `home_banners`. Старым записям без ключа выставляется `block_key='legacy_banner'`.
* `/api/homepage/blocks` всегда возвращает JSON `{items: []}` даже при сбоях, нормальный ответ — блоки, отсортированные по `sort_order`, `updated_at`, `created_at`, только активные по умолчанию.
* Фронтенд главной оборачивает загрузку API в try/catch и при любой ошибке подставляет встроенные блоки с безопасными HTTPS-картинками (Unsplash с `?auto=format&fit=crop&w=1200&q=80`). Картинки имеют fallback на градиент через `data-fallback`/`image-fallback`.
* Тема сохраняется в `localStorage` (`miniden_theme`) и при загрузке ставится на `<html data-theme>` и `<body data-theme>`, чтобы Lifestyle применялась на всех страницах.

Новые заметки по главной (seed + админка)
-----------------------------------------
- Добавлено: seed блоков главной страницы (фиксированные block_key).
- Порядок блоков: sort_order.
- Админка: как редактировать блоки (выбор строки слева -> форма справа).
- Картинки v1: только Image URL (https), загрузка файла позже.

Детальная страница товаров
---------------------------
- Детальная страница товара теперь использует единый layout с мастер-классами.
- Описание товара поддерживает переносы строк.
- Единый стиль detail-страниц (товары + мастер-классы).

Конструктор меню AdminBot (ботовые узлы/кнопки)
----------------------------------------------
- Добавлены таблицы `bot_nodes`, `bot_buttons`, `bot_actions`, `bot_runtime` (seed создаёт узел MAIN_MENU и 4 кнопки: товары, мастерклассы, чат, канал).
- В админке /adminbot появились разделы: список узлов, редактирование узла, список/редактирование кнопок, Runtime (версия конфигурации).
- Типы кнопок: callback (`ACTION:VALUE`), url (HTTP/HTTPS ссылка), webapp (HTTP/HTTPS ссылка для WebAppInfo).
- Кнопка «Обновить бота» на странице Runtime увеличивает `config_version`; бот перезагружает кэш меню без рестарта.
 - /start в Telegram читает MAIN_MENU из БД (кнопки webapp/url/callback рендерятся из таблиц), старая логика остаётся как fallback.
 - Добавлен условный узел «Проверка подписки»: в редакторе узла выберите тип «Условие» → «Проверка подписки» и укажите каналы, кнопки и переходы при успехе/ошибке. Бот строит клавиатуру с кнопками «Подписаться» (URL) и «Проверить подписку» (callback) автоматически.
 - Поддерживаются каналы в формате `@username`, `t.me/username`, `https://t.me/username` и числовой `chat_id` (`-100...`). Для корректной проверки бот должен быть добавлен в канал (лучше администратором).
 - Стартовый узел настраивается на странице AdminBot → Runtime. Чтобы включить подписочный гейт, задайте код стартового узла, например `SUBSCRIPTION_CHECK`; при успешной проверке переходите в `MAIN_MENU`, при провале оставляйтесь на узле проверки.

Шаблоны AdminBot: быстрый старт
-------------------------------
- Раздел «Шаблоны» находится в админке `/adminbot/templates`.
- Пресеты `tpl_welcome_menu`, `tpl_subscription_gate`, `tpl_support_simple`, `tpl_shop_minimal`, `tpl_courses_minimal` добавляются автоматически при запуске.
- При применении шаблона создаются новые коды узлов/кнопок/триггеров с автоматическим префиксом, существующие данные не затираются.
- Перед применением показывается предпросмотр, после применения выводится отчёт о количестве созданных узлов/кнопок/триггеров.

Загрузка изображений в AdminBot
-------------------------------
- Менеджер медиа доступен по ссылке `/adminbot/media`: загрузка jpg/png/webp до 5 МБ, просмотр списка файлов, копирование и удаление.
- Файлы сохраняются в папку проекта `static/uploads/` (путь в продакшене: `/opt/miniden/static/uploads/`). URL для вставки имеет вид `/static/uploads/<имя_файла>`.
- В форме узла есть поле «Изображение (URL)» с кнопкой «Загрузить»: откроется модальное окно, загрузит файл и автоматически подставит ссылку в поле. Кнопка «Скопировать» копирует текущий URL.

Удаление узлов и очистка ссылок
-------------------------------
- Внизу формы редактирования узла есть блок «Удалить узел» с предупреждением и кнопкой удаления.
- При удалении очищаются переходы в других узлах, кнопки отключаются и очищают payload, триггеры, ведущие на удалённый узел, отключаются. Действия узла удаляются.
- После удаления узел исчезает из списка, а версия конфигурации бота увеличивается для корректного обновления кэша.

Аудит и проверка сценариев
--------------------------
- Проверены и стабилизированы формы создания/редактирования узлов типов MESSAGE/INPUT/CONDITION/ACTION, сохранение кнопок url/webapp/callback, триггеры и переходы.
- Добавлены пользовательские сообщения об ошибках валидации, защита от пустых числовых полей и безопасная обработка отсутствующих переходов.
- Рекомендованный ручной тест: применить шаблон «Проверка подписки + меню», создать узел MESSAGE с загрузкой картинки, настроить кнопки и триггер на текст, затем удалить тестовый узел и убедиться, что ссылки очищены и бот не падает.

Front reset: theme-only + constructor-driven site
-------------------------------------------------
- Публичный сайт строится на данных конструктора AdminSite: категории и элементы берутся через публичные эндпоинты `/api/site/*`.
- Маршруты витрины: `/` (дом), `/c/:slug` (страница категории), `/p/:slug` (товар), `/m/:slug` (мастер-класс). Backend отдаёт активные записи из таблиц `adminsite_*` с сортировкой по `sort` и `id`.
- Легаси-страницы и JS, заточенные под старый фронт (`categories.html`, `category.html`, `products.html`, `masterclasses.html`, `product.html`, `masterclass.html`, `baskets.html`, `courses.html`, каталог `webapp/shop`, файлы `webapp/js/*_page.js` и `telegram_shop_page.js`) удалены.
- Тема/стили остаются в `webapp/css/theme.css` (переключатель в шапке), новая логика витрины — в `webapp/js/site_app.js` и `webapp/js/site_api.js`.

## Unified project structure
- Backend API: `webapi.py` (FastAPI), routers under `api/routers/*`, admin routes under `admin_panel/routes/*`, AdminSite API in `admin_panel/adminsite/router.py`.
- Frontend (customer site): static HTML/JS/CSS in `webapp/` served via `/css`, `/js`, `/media`.
- AdminSite UI: templates in `admin_panel/adminsite/templates`, constructor assets in `admin_panel/adminsite/static/adminsite` (served at `/static/adminsite/*`).
- AdminBot UI: templates in `admin_panel/templates/adminbot*`, routes under `admin_panel/routes/*`.
- Automation: `deploy.sh`, configs in `deploy/nginx/` and `deploy/systemd/`, diagnostics in `deploy/DEPLOY_CONTRACT.md`.
- Support files: `docs/legacy-data/` (archived seeds), `data/*.json` demo payloads, `scripts/` maintenance helpers.

## How to run (bot/api/front/adminsite)
- Install dependencies: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- API: `uvicorn webapi:app --host 0.0.0.0 --port 8000` (requires PostgreSQL and `.env` variables for DB/auth).
- Bot: `python bot.py` (runs against the same `.env` settings and database as the API).
- AdminSite/AdminBot: open `https://<host>/adminsite/` or `/adminbot/` after authenticating via `/login`; constructor scripts load from `/static/adminsite/constructor.js`.
- Web front: serve `webapp/` via nginx or any static server (`/css`, `/js`, `/media` mounts needed for uploads/JS/CSS).

## Deploy notes
- Single entrypoint: run `sudo /opt/miniden/deploy.sh` or `systemctl start miniden-deploy.service` to update code, run Alembic migrations, and restart services.
- Reference configs live in `deploy/nginx/miniden.conf` and `deploy/systemd/*.service` and are installed manually (deploy.sh больше не копирует их автоматически).
- Service restarts: `deploy.sh` touches only `miniden-api` и `miniden-bot`, оставляя `.env`, `media/`, `data/` и `logs/` нетронутыми.
- AdminBot/AdminSite do not expose deploy buttons or API endpoints; запуск выполняется только с сервера.

## AdminSite/Constructor: Категории → Страницы
- При создании/обновлении категории товаров или мастер-классов автоматически создаётся страница конструктора (таблица `adminsite_categories`) и `page_id` сохраняется в `product_categories.page_id`.
- Slug и название синхронизируются с категорией; при запросах к API категории заполняется связка `page_id/page_slug`, а существующие категории без связки получают страницу автоматически при загрузке списков.
- Отдельный эндпоинт `/api/admin/product-categories/{id}/page` позволяет принудительно создать/привязать страницу, если она потерялась.

## Быстрые переходы в админке
- В списке категорий добавлены ссылки: «Страница» (открывает `/adminsite/constructor` с нужной категорией), «Товары» и «Мастер-классы» (открывают списки с фильтром `category_id`/`type`).
- В формах категорий отображается read-only блок с `page_id/page_slug`, кнопки для открытия конструктора и списков, а также кнопка «Создать страницу», вызывающая `/api/admin/product-categories/{id}/page`.
- Ссылки используют query-параметры `view`, `type`, `category_id`, поэтому переход из списка категорий сразу включает нужный фильтр в админке.

## Проверка (smoke test)
1. Создать категорию в админке (вкладка «Категории товаров/мастер-классов») — после сохранения у записи появляется `page_id`, а в конструкторе видна страница.
2. Создать товар и указать созданную категорию.
3. Открыть публичную страницу категории (`/category/<slug>` или кнопка «Страница») и убедиться, что новый товар отображается без ручного редактирования страницы; при необходимости из формы категории можно нажать «Создать страницу» для восстановления привязки.

## Maintenance log
- Fixed AdminBot subscription check: теперь используется реальный `getChatMember`, нормализуются ссылки на канал и логируется статус/ошибка Telegram.
- Audited repository layout and deployment entrypoints (see `docs/audit_report.md`).
- Fixed AdminSite constructor history sync so browser Back closes modals cleanly and does not trap navigation.
- Removed unused placeholder `admin_panel/static/.keep` to avoid duplicate sentinel files.
- Documented unified structure, run commands, and deploy expectations.
- Fixed AdminSite constructor modals so category/product dialogs close on Отмена, Esc, and backdrop clicks without page reloads; touched `admin_panel/adminsite/static/adminsite/modals.js`, verify with the constructor smoke steps.
- Fixed AdminSite constructor block picker: окно «Добавить блок» закрывается по крестику, клику на фон и клавише Esc без нарушения истории браузера.
- Unified бот-кнопки: у BotButton добавлены поля render/action_payload, поддержка REPLY-кнопок по узлам, новые API `/adminbot/api/buttons`, `/adminbot/api/buttons/save`, `/adminbot/api/buttons/delete`.
- Устойчивость стартовых фото бота: добавлены ретраи/фолбэки для answer_photo, кэширование file_id после первой загрузки и увеличен HTTP-timeout сессии.
- Восстановлена обработка OPEN_NODE: кнопки CONTACT/ABOUT с payload вида `OPEN_NODE CONTACT` корректно открывают узлы и логируют причины ошибок.
- Исправлена зависимость DB для AdminSite API: в FastAPI используется `Depends(get_db)` (yield Session), а `database.get_session()` остаётся контекстным менеджером.

## Фикс: Automations Edit 500
- Что было: `/adminbot/automations/{id}/edit` отдавал 500 Internal Server Error при открытии страницы редактирования.
- Что сделано: исправлен backend endpoint для edit (добавлены payload пресетов, 404 для отсутствующего правила, логирование загрузки/ошибок), добавлены безопасные сообщения об отсутствии правила.
- Как проверить:
  1. Откройте `/adminbot/automations`.
  2. Нажмите «Редактировать» у правила — страница должна открыться без 500.
  3. Откройте несуществующий ID (например `/adminbot/automations/999999/edit`) — должна появиться страница с текстом «Правило не найдено» (HTTP 404).
- Где смотреть логи при проблемах: `admin_panel/routes/adminbot_automations.py`, обработчики `/adminbot/automations/{id}/edit` (GET/POST) пишут info-логи с `rule_id`.

Важно: AdminSite / Версии / Кэш
- Публичный эндпоинт `/api/site/home` должен отдавать заголовок Cache-Control: no-store (плюс совместимый Pragma: no-cache).
- Админские эндпоинты сохранения/публикации страниц возвращают updatedAt/version, чтобы фронт мог отличать свежий ответ.
- Конструктор должен работать с защитой DOM: отсутствующие элементы не ломают сценарий (warning + skip вместо ошибки).
- Быстрая проверка: DevTools → Network, сохранить страницу и сразу открыть `/api/site/home` — JSON должен быть новым без кэша и с актуальным updatedAt/version.
- Фикс: нижняя панель корзины была некликабельна из-за CSS/overlay.
- Как проверять: ПК/Telegram -> добавить товар -> кликнуть панель -> перейти в корзину.

Builder (Сборка бота)
----------------------
- Единый экран сборки: `/adminbot/builder`.
- Показывает статусы ключевых блоков (старт, меню, каталог, корзина/заказы, профиль, помощь, мастер-классы, автоматизации).
- Карточка «Настроить» ведёт сразу в нужный раздел.
- Встроен короткий мастер на 3 шага для новичков.

Template Packs (Шаблоны-пакеты) и безопасное применение
-------------------------------------------------------
- Раздел: `/adminbot/templates`.
- Шаблоны-пакеты (Starter Kits) можно установить в 2 шага: Preview → Confirm.
- При совпадениях по slug используется правило «не трогать существующее».
- Для совпадений доступен чекбокс «Заменить» (только после подтверждения).
- В пакеты входят: профиль, корзина+заказы, обратная связь, помощь, мастер-классы, стартовый бот-магазин.

Удаление сущностей и проверка целостности
----------------------------------------
- Узлы: удаление запрещено, если на узел есть ссылки (узлы/кнопки/триггеры).
- Кнопки: удаление доступно прямо из списка кнопок узла.
- Шаблоны: удаление доступно в списке шаблонов.
- Проверка целостности: `/adminbot/integrity` (UI) и `/adminbot/api/integrity` (JSON, только чтение).

Аудит связей AdminBot (сущности и связи)
----------------------------------------
- Узлы (BotNode): `code` + переходы `next_node_code*` → другие узлы.
- Кнопки (BotButton): принадлежат узлу (`node_id`), переходы хранятся в `target_node_code` и payload `OPEN_NODE:<code>`.
- Триггеры (BotTrigger): `target_node_code` → узел.
- Reply-меню (MenuButton): `action_type=node` + `action_payload` → узел.
- Действия узлов (BotNodeAction): в payload может храниться `node_code` → узел.
- Пресеты кнопок (BotButtonPreset): используются в автоматизациях.
- Автоматизации (BotAutomationRule): в `actions_json` может быть `preset_id` → пресет.

Как новичку собрать бота за 10 минут
------------------------------------
1) Откройте `/adminbot/builder` и посмотрите статусы.
2) Задайте стартовый узел в `/adminbot/runtime`.
3) Создайте узлы и кнопки: `/adminbot/nodes` → «Кнопки».
4) Настройте Reply-меню: `/adminbot/menu-buttons`.
5) Установите нужный Template Pack в `/adminbot/templates` (Preview → Confirm).
6) Запустите проверку `/adminbot/integrity`, убедитесь, что нет битых ссылок.

Фикс: корзина и панель использовали разные источники данных
------------------------------------------------------------
- Единый источник: `/api/cart` для Telegram WebApp (user_id из WebApp), иначе гостевая корзина в localStorage `miniden_guest_cart`.

Кнопка "Оформить в боте" в корзине
---------------------------------
- Показывается только при доступном `Telegram.WebApp` и наличии `initData`, иначе скрыта и выводится подсказка "Оформление в боте доступно в Telegram".
- Отправляет payload через `Telegram.WebApp.sendData()`:
  `{ type: 'webapp_order', cart: { items: [{ id, title, qty, price }], total, currency: 'RUB' } }`.

Фикс корзины: NotFound/EmptyState был подключен неправильно
------------------------------------------------------------
- Исправлена навигация: маршрут `/cart` теперь ведёт на отдельную страницу корзины вместо страницы «Ничего не найдено».

DEBUG_CART: как включить/выключить и что показывает
---------------------------------------------------
- В `webapp/cart.html` выставьте `DEBUG_CART = true` для отображения плашки.
- Плашка показывает текущий URL, items.length, count, total, а также сведения о localStorage для ключей корзины.
