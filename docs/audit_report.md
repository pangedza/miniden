# Audit summary (2025-12-26)

## Repository map
- Entrypoints: `bot.py` (Telegram bot), `webapi.py` (`uvicorn webapi:app`), `deploy.sh` (server deploy helper), `admin_panel/routes` (admin UI routes), `api/main.py` (legacy shim calling `webapi`).
- Frontends: `webapp/` static site (HTML/JS/CSS), `admin_panel/adminsite/templates` (AdminSite dashboard/constructor), `admin_panel/templates` (AdminBot UI), `admin_panel/adminsite/static/adminsite` (constructor assets).
- APIs: FastAPI routers under `api/routers/*` plus admin routes `admin_panel/routes/*` and AdminSite API `admin_panel/adminsite/router.py`.
- Deploy artifacts: `deploy/nginx/miniden.conf`, `deploy/systemd/miniden-{api,bot}.service`, `deploy/DEPLOY_CONTRACT.md`, top-level `deploy.sh` (copies configs, restarts services).
- Data/storages: `data/*.json` demo payloads, `static/uploads` placeholder, `media/` expected at runtime (not in repo), admin/webapp logs under `logs/` (created at runtime), legacy catalog snapshots under `docs/legacy-data`.

## Observations
- AdminSite constructor is served from `/adminsite/constructor` with static assets under `/static/adminsite/*` (FastAPI mount + nginx alias).
- AdminSite API base URL is `/api/adminsite`; health check `/api/adminsite/health` and debug routes `/api/adminsite/debug/*` exist for troubleshooting.
- WebApp static mounts: `/css` and `/js` mapped directly to `webapp` subfolders; `/media` serves uploads.
- Deploy script relies on `deploy/nginx/miniden.conf` as single source of truth (copies via `deploy.sh`, ensures JS served as `application/javascript`).

## Repro status
- Full runtime not launched: environment variables and backing services (DB, tokens) are not available in the container. Constructor logic reviewed via source inspection; tests run only for pure-Python utilities.
