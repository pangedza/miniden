# MiniDeN deployment runbook

## Services and entrypoints
- Backend app: `webapi:app` (FastAPI), launched by `uvicorn`.
- Systemd unit template: `deploy/miniden-api.service`.
- Nginx config template: `deploy/miniden-nginx.conf`.

## Deploy / update steps
1. Upload the repository to `/opt/miniden` on the server (including updated templates and static files).
2. Install dependencies in the project virtualenv if needed:
   ```bash
   cd /opt/miniden
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Update the systemd unit (first time or after edits):
   ```bash
   sudo cp /opt/miniden/deploy/miniden-api.service /etc/systemd/system/miniden-api.service
   sudo systemctl daemon-reload
   sudo systemctl enable miniden-api.service
   sudo systemctl restart miniden-api.service
   ```
4. Deploy nginx config:
   ```bash
   sudo cp /opt/miniden/deploy/miniden-nginx.conf /etc/nginx/sites-available/miniden.conf
   sudo ln -sf /etc/nginx/sites-available/miniden.conf /etc/nginx/sites-enabled/miniden.conf
   sudo nginx -t
   sudo systemctl reload nginx
   ```

## Post-deploy checks
Run locally against uvicorn (replace host with domain for live checks):
- `curl -s http://127.0.0.1:8000/api/health` → `{ "ok": true }`
- `curl -I http://127.0.0.1:8000/adminbot/login` → HTTP 200
- `curl -I http://127.0.0.1:8000/` → `Content-Type: text/html`

Through nginx / domain:
- `curl -I https://miniden.ru/` → HTTP 200, `Content-Type: text/html`
- `curl -I https://miniden.ru/adminbot/login` → HTTP 200

Services:
- `sudo systemctl status miniden-api --no-pager -l`
- `sudo systemctl restart miniden-api`
- `sudo systemctl reload nginx`

## Notes
- Static assets are served via nginx aliases for `/static`, `/css`, and `/js` and from uvicorn for dynamic pages.
- Media uploads are read from `/opt/miniden/media` via nginx `alias /media/` and by FastAPI.
