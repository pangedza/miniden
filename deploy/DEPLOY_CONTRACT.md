# Контракт деплоя MiniDeN (production)

## Источник правды
Репозиторий GitHub содержит:
- код API
- код Telegram-бота
- webapp (HTML/JS/CSS) для раздачи nginx
- эталонные server-конфиги (deploy/nginx и deploy/systemd)

## Одна команда деплоя на сервере
sudo /opt/miniden/deploy.sh

## Что деплой ОБЯЗАН обновлять
- git pull в /opt/miniden
- зависимости Python (если менялся requirements.txt)
- webapp -> /opt/miniden/webapp
- nginx config -> /etc/nginx/sites-available/miniden.conf (+ symlink sites-enabled)
- systemd units -> /etc/systemd/system/
- restart: miniden-api, miniden-bot
- reload: nginx
- post-check: curl http://127.0.0.1:8000/api/health

## Что деплой НЕ ИМЕЕТ ПРАВА трогать
- /opt/miniden/.env
- /opt/miniden/media/
- /opt/miniden/data/
