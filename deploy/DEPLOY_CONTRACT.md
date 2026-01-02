# Контракт деплоя MiniDeN (production)

## Источник правды
Репозиторий GitHub содержит:
- код API
- код Telegram-бота
- webapp (HTML/JS/CSS) для раздачи nginx
- эталонные server-конфиги (deploy/nginx/miniden.conf и deploy/systemd)
- единый deploy.sh, который **не** порождает альтернативных конфигов

## Одна команда деплоя на сервере
sudo /opt/miniden/deploy.sh

## Что деплой ОБЯЗАН обновлять
-- git reset --hard origin/<branch> в /opt/miniden
- webapp -> /opt/miniden/webapp
- nginx config -> /etc/nginx/sites-available/miniden.conf (+ symlink sites-enabled)
- systemd units -> /etc/systemd/system/
- restart: miniden-api, miniden-bot
- reload: nginx
- проверка прав: пользователь/группа miniden, права на /opt/miniden/logs, /opt/miniden/media, /opt/miniden/uploads
- post-checks (деплой падает, если любая проверка не прошла):
  - curl http://127.0.0.1:8000/api/health
  - curl http://127.0.0.1:8000/adminsite/
  - curl http://127.0.0.1:8000/static/adminsite/base.css
  - curl http://127.0.0.1:8000/static/adminsite/constructor.js
  - curl -I https://miniden.ru/
  - curl -I https://miniden.ru/adminsite/
  - curl -I https://miniden.ru/static/adminsite/constructor.js (Content-Type не text/html)

## Что деплой НЕ ИМЕЕТ ПРАВА трогать
- /opt/miniden/.env
- /opt/miniden/media/
- /opt/miniden/data/
- действующий SSL-сертификат (Let’s Encrypt) и /etc/letsencrypt/*.pem

## Предварительные условия (делаются вручную до запуска deploy.sh)
- Python-зависимости устанавливаются вручную в `venv` (если менялся `requirements.txt`).
- Системный пользователь/группа `miniden` и права на каталоги `/opt/miniden`, `/opt/miniden/logs`, `/opt/miniden/media`, `/opt/miniden/uploads`, `/opt/miniden/data` подготовлены заранее.
- deploy.sh запускается от root (systemd юнит или `sudo`), чтобы обновлять конфиги и перезапускать сервисы.
