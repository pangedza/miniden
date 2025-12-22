# AdminSite API тесты

Примеры запросов для новых эндпоинтов (`/api/adminsite/*`). Предполагается, что кука `admin_session` уже получена после авторизации в админке.

## Категории

Получить категории по типу:

```bash
curl -b "admin_session=<token>" "http://localhost:8000/api/adminsite/categories?type=product"
```

Создать категорию:

```bash
curl -X POST -H "Content-Type: application/json" \
  -b "admin_session=<token>" \
  -d '{
    "type": "product",
    "title": "Аксессуары",
    "slug": "aksessuary",
    "is_active": true,
    "sort": 10
  }' \
  http://localhost:8000/api/adminsite/categories
```

Обновить категорию:

```bash
curl -X PUT -H "Content-Type: application/json" \
  -b "admin_session=<token>" \
  -d '{
    "title": "Аксессуары и сувениры",
    "sort": 20
  }' \
  http://localhost:8000/api/adminsite/categories/1
```

Удалить категорию (удаление заблокировано, если есть элементы):

```bash
curl -X DELETE -b "admin_session=<token>" http://localhost:8000/api/adminsite/categories/1
```

## Элементы

Список элементов по типу и категории:

```bash
curl -b "admin_session=<token>" "http://localhost:8000/api/adminsite/items?type=product&category_id=1"
```

Создать элемент:

```bash
curl -X POST -H "Content-Type: application/json" \
  -b "admin_session=<token>" \
  -d '{
    "type": "product",
    "category_id": 1,
    "title": "Новый товар",
    "price": 990,
    "short_text": "Краткое описание"
  }' \
  http://localhost:8000/api/adminsite/items
```

Обновить элемент:

```bash
curl -X PUT -H "Content-Type: application/json" \
  -b "admin_session=<token>" \
  -d '{
    "title": "Обновленный товар",
    "is_active": false
  }' \
  http://localhost:8000/api/adminsite/items/1
```

Удалить элемент:

```bash
curl -X DELETE -b "admin_session=<token>" http://localhost:8000/api/adminsite/items/1
```

## Настройки WebApp

Получить настройки (вернёт категорию, если есть, иначе global):

```bash
curl -b "admin_session=<token>" "http://localhost:8000/api/adminsite/webapp-settings?type=product&category_id=1"
```

Upsert настроек:

```bash
curl -X PUT -H "Content-Type: application/json" \
  -b "admin_session=<token>" \
  -d '{
    "scope": "category",
    "type": "product",
    "category_id": 1,
    "action_enabled": true,
    "action_label": "Оформить",
    "min_selected": 1
  }' \
  http://localhost:8000/api/adminsite/webapp-settings
```
