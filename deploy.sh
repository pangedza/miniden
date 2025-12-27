#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_BIN="$PROJECT_DIR/venv/bin"
PIP_BIN="$VENV_BIN/pip"
ALEMBIC_BIN="$VENV_BIN/alembic"
SERVICE_USER="miniden"
SERVICE_GROUP="miniden"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/deploy.log"
BACKUP_DIR="$PROJECT_DIR/backups"
NGINX_SRC="$PROJECT_DIR/deploy/nginx/miniden.conf"
NGINX_DST="/etc/nginx/sites-available/miniden.conf"
NGINX_ENABLED_DST="/etc/nginx/sites-enabled/miniden.conf"
SYSTEMD_SRC_DIR="$PROJECT_DIR/deploy/systemd"
SYSTEMD_DST_DIR="/etc/systemd/system"
BACKEND_HEALTH="http://127.0.0.1:8000/api/health"

log() {
  echo "[deploy] $*"
}

warn() {
  echo "[deploy][WARN] $*" >&2
}

ts() {
  date +%F_%H%M%S
}

backup_file() {
  local src="$1"
  local name="$2"
  if [ ! -f "$src" ]; then
    return
  fi

  local target="$BACKUP_DIR/${name}.$(ts)"
  sudo mkdir -p "$(dirname "$target")"
  sudo cp -a "$src" "$target"
  log "-> Backup saved: $src -> $target"
}

fail_with_logs() {
  warn "$1"
  warn "---- journalctl -u miniden-api.service (last 120 lines) ----"
  sudo journalctl -u miniden-api.service -n 120 --no-pager || true
  warn "---- journalctl -u miniden-bot.service (last 120 lines) ----"
  sudo journalctl -u miniden-bot.service -n 120 --no-pager || true
  if sudo test -f /var/log/nginx/miniden.error.log; then
    warn "---- /var/log/nginx/miniden.error.log (last 120 lines) ----"
    sudo tail -n 120 /var/log/nginx/miniden.error.log || true
  fi
  exit 1
}

setup_logging() {
  mkdir -p "$LOG_DIR"
  chmod 755 "$LOG_DIR"
  touch "$LOG_FILE"
  chmod 664 "$LOG_FILE"
  mkdir -p "$BACKUP_DIR/nginx" "$BACKUP_DIR/systemd"
  exec > >(tee -a "$LOG_FILE") 2>&1
}

check_http_ok() {
  local url="$1"
  if ! curl -fsS "$url" > /dev/null; then
    fail_with_logs "Healthcheck failed: $url"
  fi
}

check_head_ok() {
  local url="$1"
  if ! curl -fsSI "$url" > /dev/null; then
    fail_with_logs "Healthcheck (HEAD) failed: $url"
  fi
}

ensure_js_content_type() {
  local url="$1"
  local headers
  headers=$(curl -fsSI "$url" | tr -d '\r') || fail_with_logs "Failed to read headers for $url"
  if echo "$headers" | grep -qi "content-type: text/html"; then
    fail_with_logs "Unexpected text/html Content-Type for $url"
  fi
  if ! echo "$headers" | grep -Eqi "content-type: .*javascript"; then
    fail_with_logs "Content-Type for $url is not JavaScript: $(echo "$headers" | grep -i 'content-type')"
  fi
}

ensure_system_user() {
  if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
    log "-> Creating system group $SERVICE_GROUP"
    sudo groupadd --system "$SERVICE_GROUP"
  fi

  if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    log "-> Creating system user $SERVICE_USER"
    sudo useradd --system --home-dir "$PROJECT_DIR" --shell /usr/sbin/nologin --gid "$SERVICE_GROUP" "$SERVICE_USER"
  fi

  sudo usermod -g "$SERVICE_GROUP" "$SERVICE_USER"
}

ensure_permissions() {
  sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$PROJECT_DIR"

  for path in "$PROJECT_DIR/logs" "$PROJECT_DIR/media" "$PROJECT_DIR/uploads"; do
    sudo mkdir -p "$path"
    sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$path"
    sudo find "$path" -type d -exec chmod 775 {} +
    sudo find "$path" -type f -exec chmod 664 {} +
  done

  sudo touch "$PROJECT_DIR/logs/bot.log"
  sudo touch "$PROJECT_DIR/logs/api.log"
  sudo chown "$SERVICE_USER:$SERVICE_GROUP" "$PROJECT_DIR/logs/bot.log"
  sudo chown "$SERVICE_USER:$SERVICE_GROUP" "$PROJECT_DIR/logs/api.log"
  sudo chmod 664 "$PROJECT_DIR/logs/bot.log"
  sudo chmod 664 "$PROJECT_DIR/logs/api.log"
}

install_nginx_config() {
  if [ ! -f "$NGINX_SRC" ]; then
    fail_with_logs "nginx source config not found: $NGINX_SRC"
  fi

  log "-> Install nginx config: $NGINX_SRC -> $NGINX_DST"
  local current_target
  current_target=$(sudo readlink -f "$NGINX_ENABLED_DST" || true)
  local tmp_dst
  tmp_dst="${NGINX_DST}.tmp.$(ts)"

  backup_file "$NGINX_DST" "nginx/miniden.conf"

  sudo install -m 0644 "$NGINX_SRC" "$tmp_dst"
  sudo ln -sfn "$tmp_dst" "$NGINX_ENABLED_DST"

  log "-> Guard: verifying https listener is present"
  sudo grep -q 'listen 443 ssl' "$tmp_dst" || fail_with_logs "nginx config does not contain https listener"

  log "-> nginx config test"
  if ! sudo nginx -t; then
    warn "nginx -t failed; restoring previous config"
    sudo rm -f "$tmp_dst"
    if [ -n "$current_target" ]; then
      sudo ln -sfn "$current_target" "$NGINX_ENABLED_DST"
    else
      sudo rm -f "$NGINX_ENABLED_DST"
    fi
    fail_with_logs "nginx config test failed"
  fi

  sudo mv "$tmp_dst" "$NGINX_DST"
  sudo ln -sfn "$NGINX_DST" "$NGINX_ENABLED_DST"
  log "-> Active nginx config: $(sudo readlink -f "$NGINX_ENABLED_DST")"
}

sync_systemd_units() {
  log "-> Syncing systemd units"
  if [ -d "$SYSTEMD_SRC_DIR" ]; then
    for unit in "$SYSTEMD_SRC_DIR"/*.service; do
      [ -f "$unit" ] || continue
      local target="$SYSTEMD_DST_DIR/$(basename "$unit")"
      backup_file "$target" "systemd/$(basename "$unit")"
      sudo install -m 0644 "$unit" "$target"
    done
    sudo systemctl daemon-reload
  else
    warn "Systemd source dir not found: $SYSTEMD_SRC_DIR"
  fi
}

restart_services() {
  for service_name in miniden-api miniden-bot; do
    log "-> Restarting $service_name"
    sudo systemctl reset-failed "$service_name" || true
    if ! sudo systemctl restart "$service_name"; then
      fail_with_logs "Failed to restart $service_name"
    fi
    if ! sudo systemctl is-active --quiet "$service_name"; then
      fail_with_logs "$service_name is not active after restart"
    fi
    sudo systemctl status "$service_name" --no-pager || warn "status check failed for $service_name"
  done
}

apply_migrations() {
  if [ -x "$ALEMBIC_BIN" ] && [ -f "$PROJECT_DIR/alembic.ini" ]; then
    log "-> Applying database migrations"
    "$ALEMBIC_BIN" upgrade head
  else
    warn "Alembic not configured; skipping migrations"
  fi
}

setup_logging

log "-> Ensuring system user and permissions"
ensure_system_user
ensure_permissions

log "-> Updating repository"
current_branch=$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)
git -C "$PROJECT_DIR" fetch --all
git -C "$PROJECT_DIR" reset --hard "origin/${current_branch}"
log "-> Cleaning working tree (preserving .env, logs, media, uploads, backups)"
git -C "$PROJECT_DIR" clean -fd -e .env -e logs -e media -e uploads -e backups || warn "git clean reported issues"

if [ -x "$PIP_BIN" ]; then
  log "-> Installing Python dependencies"
  "$PIP_BIN" install -r "$PROJECT_DIR/requirements.txt"
else
  warn "Python virtualenv not found at $PIP_BIN; skipping pip install"
fi

apply_migrations

sync_systemd_units
install_nginx_config

log "-> Reload systemd configuration"
sudo systemctl daemon-reload

restart_services

log "-> Reload nginx"
sudo systemctl reload nginx

log "-> Post-deploy healthchecks (local)"
check_http_ok "$BACKEND_HEALTH"
check_http_ok "http://127.0.0.1:8000/adminsite/"
check_http_ok "http://127.0.0.1:8000/adminsite/constructor"
check_http_ok "http://127.0.0.1:8000/static/adminsite/base.css"
check_http_ok "http://127.0.0.1:8000/static/adminsite/constructor.js"
ensure_js_content_type "http://127.0.0.1:8000/static/adminsite/constructor.js"
check_http_ok "http://127.0.0.1:8000/js/site_app.js"
ensure_js_content_type "http://127.0.0.1:8000/js/site_app.js"

log "-> Post-deploy healthchecks (public domain)"
check_head_ok "https://miniden.ru/"
check_head_ok "https://miniden.ru/adminsite/"
check_head_ok "https://miniden.ru/adminsite/constructor"
check_head_ok "https://miniden.ru/static/adminsite/constructor.js"
ensure_js_content_type "https://miniden.ru/static/adminsite/constructor.js"
check_head_ok "https://miniden.ru/js/site_app.js"
ensure_js_content_type "https://miniden.ru/js/site_app.js"

log "-> Healthchecks succeeded"
