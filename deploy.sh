#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_BIN="$PROJECT_DIR/venv/bin"
PIP_BIN="$VENV_BIN/pip"
PYTHON_BIN="$VENV_BIN/python"
NGINX_SRC="$PROJECT_DIR/deploy/nginx/miniden.conf"
NGINX_DST="/etc/nginx/sites-available/miniden.conf"
SYSTEMD_SRC_DIR="$PROJECT_DIR/deploy/systemd"

log() {
  echo "[deploy] $*"
}

warn() {
  echo "[deploy][WARN] $*" >&2
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
  sudo cp -f "$NGINX_SRC" "$NGINX_DST"
  sudo ln -sf "$NGINX_DST" /etc/nginx/sites-enabled/miniden.conf
  sudo nginx -t
  sudo systemctl reload nginx
else
  warn "nginx source config not found: $NGINX_SRC"
fi

for service_name in miniden-api miniden-bot; do
  log "-> Restarting $service_name"
  if ! sudo systemctl restart "$service_name"; then
    warn "Failed to restart $service_name"
  fi
  sudo systemctl status "$service_name" --no-pager || warn "status check failed for $service_name"

done

if [ -x "$PYTHON_BIN" ]; then
  HEALTH_URL="http://127.0.0.1:8000/api/health"
  log "-> Healthcheck $HEALTH_URL"
  if ! curl -fsS "$HEALTH_URL" > /dev/null; then
    warn "Healthcheck failed: $HEALTH_URL"
  fi
fi
