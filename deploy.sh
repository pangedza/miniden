#!/usr/bin/env bash
set -euo pipefail
trap 'warn "Command failed (exit $?): $BASH_COMMAND"' ERR

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_BIN="$PROJECT_DIR/venv/bin"
ALEMBIC_BIN="$VENV_BIN/alembic"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/deploy.log"

log() {
  echo "[deploy] $*"
}

warn() {
  echo "[deploy][WARN] $*" >&2
}

setup_logging() {
  mkdir -p "$LOG_DIR"
  touch "$LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1
}

fail_with_logs() {
  warn "$1"
  exit 1
}

update_repo() {
  log "-> Updating repository"
  local current_branch
  current_branch=$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)
  git -C "$PROJECT_DIR" fetch --all
  git -C "$PROJECT_DIR" reset --hard "origin/${current_branch}"
  log "-> Cleaning working tree (preserving .env, data, logs, media, uploads, backups)"
  git -C "$PROJECT_DIR" clean -fd -e .env -e data -e logs -e media -e uploads -e backups || warn "git clean reported issues"
}

apply_migrations() {
  if [ -x "$ALEMBIC_BIN" ] && [ -f "$PROJECT_DIR/alembic.ini" ]; then
    log "-> Applying database migrations"
    "$ALEMBIC_BIN" upgrade head
  else
    warn "Alembic not configured; skipping migrations"
  fi
}

restart_services() {
  for service_name in miniden-api miniden-bot; do
    log "-> Restarting $service_name"
    systemctl reset-failed "$service_name" || true
    systemctl restart "$service_name"
    systemctl is-active --quiet "$service_name" || fail_with_logs "$service_name is not active after restart"
    systemctl status "$service_name" --no-pager || warn "status check failed for $service_name"
  done
}

setup_logging
log "=== deploy start $(date -Iseconds) ==="

update_repo
apply_migrations
restart_services

log "-> Deploy finished"
exit 0
