#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_BIN="$PROJECT_DIR/venv/bin"
PIP_BIN="$VENV_BIN/pip"
NGINX_SRC="$PROJECT_DIR/deploy/nginx/miniden.conf"
NGINX_DST="/etc/nginx/sites-available/miniden.conf"
NGINX_ENABLED_DST="/etc/nginx/sites-enabled/miniden.conf"
SYSTEMD_SRC_DIR="$PROJECT_DIR/deploy/systemd"

log() {
  echo "[deploy] $*"
}

warn() {
  echo "[deploy][WARN] $*" >&2
}

fail_with_logs() {
  warn "$1"
  warn "---- journalctl -u miniden-api.service (last 120 lines) ----"
  sudo journalctl -u miniden-api.service -n 120 --no-pager || true
  if sudo test -f /var/log/nginx/miniden.error.log; then
    warn "---- /var/log/nginx/miniden.error.log (last 120 lines) ----"
    sudo tail -n 120 /var/log/nginx/miniden.error.log || true
  fi
  exit 1
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

log "-> Updating repository"
git -C "$PROJECT_DIR" pull --ff-only

if [ -x "$PIP_BIN" ]; then
  log "-> Installing Python dependencies"
  "$PIP_BIN" install -r "$PROJECT_DIR/requirements.txt"
else
  warn "Python virtualenv not found at $PIP_BIN; skipping pip install"
fi

log "-> Syncing systemd units"
if [ -d "$SYSTEMD_SRC_DIR" ]; then
  for unit in "$SYSTEMD_SRC_DIR"/*.service; do
    [ -f "$unit" ] || continue
    sudo cp -f "$unit" "/etc/systemd/system/$(basename "$unit")"
  done
  sudo systemctl daemon-reload
else
  warn "Systemd source dir not found: $SYSTEMD_SRC_DIR"
fi

log "-> Install nginx config: $NGINX_SRC -> $NGINX_DST"
if [ -f "$NGINX_SRC" ]; then
  log "-> Backing up current nginx config (if exists)"
  sudo cp -a "$NGINX_DST" "$NGINX_DST.bak.$(date +%F_%H%M%S)" || true

  sudo install -m 0644 "$NGINX_SRC" "$NGINX_DST"
  sudo ln -sfn "$NGINX_DST" "$NGINX_ENABLED_DST"

  log "-> Guard: verifying https listener is present"
  sudo grep -q 'listen 443 ssl' "$NGINX_DST" || fail_with_logs "nginx config does not contain https listener"

  log "-> nginx config test"
  sudo nginx -t
  log "-> Reload systemd configuration"
  sudo systemctl daemon-reload
  log "-> Active nginx config: $(sudo readlink -f "$NGINX_ENABLED_DST")"
else
  fail_with_logs "nginx source config not found: $NGINX_SRC"
fi

for service_name in miniden-api miniden-bot; do
  log "-> Restarting $service_name"
  if ! sudo systemctl restart "$service_name"; then
    warn "Failed to restart $service_name"
  fi
  sudo systemctl status "$service_name" --no-pager || warn "status check failed for $service_name"

done

log "-> Reload nginx"
sudo systemctl reload nginx

log "-> Post-deploy healthchecks (local)"
check_http_ok "http://127.0.0.1:8000/adminsite/"
check_http_ok "http://127.0.0.1:8000/static/adminsite/base.css"
check_http_ok "http://127.0.0.1:8000/static/adminsite/constructor.js"
ensure_js_content_type "http://127.0.0.1:8000/static/adminsite/constructor.js"

log "-> Post-deploy healthchecks (public domain)"
check_head_ok "https://miniden.ru/adminsite/"
check_head_ok "https://miniden.ru/static/adminsite/constructor.js"
ensure_js_content_type "https://miniden.ru/static/adminsite/constructor.js"

log "-> Healthchecks succeeded"
