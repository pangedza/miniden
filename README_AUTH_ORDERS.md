# Пользователи и заказы (PHP/MySQL, localhost)
## 1) Импортируйте SQL
phpMyAdmin → выбрать базу → Импорт → db/migrations/001_init.sql.
## 2) Заполните api/config.php
DB_HOST=localhost, и свои DB_NAME/DB_USER/DB_PASS, COOKIE_DOMAIN=ваш_домен.
## 3) Страницы
- auth.html — вход/регистрация
- orders.html — история заказов
## 4) Эндпоинты
- /api/auth_register.php, /api/auth_login.php, /api/auth_logout.php, /api/me.php
- /api/create_order.php, /api/my_orders.php
## 5) Интеграция корзины
На странице cart.html должна быть кнопка id="checkout" и элемент #checkout-msg (см. автопатч ниже).
## Примечания
Внешний доступ к MySQL не используется: все подключения только через localhost на сервере REG.RU.
