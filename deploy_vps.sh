#!/usr/bin/env bash
set -Eeuo pipefail

# Idempotent VPS deploy script for this project.
# It deploys to an isolated path and runs on a dedicated port, so existing projects stay untouched.

APP_NAME="${APP_NAME:-qq}"
APP_USER="${APP_USER:-qqapp}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
APP_BASE_DIR="${APP_BASE_DIR:-/opt/$APP_NAME}"
APP_DIR="${APP_DIR:-$APP_BASE_DIR/app}"
VENV_DIR="${VENV_DIR:-$APP_BASE_DIR/venv}"
REPO_URL="${REPO_URL:-https://github.com/SultanbekKenesbaev/qq.git}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-${APP_NAME}-app.service}"
ENV_FILE="${ENV_FILE:-/etc/${APP_NAME}.env}"
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0}"
APP_PORT="${APP_PORT:-18010}"
WORKERS="${WORKERS:-3}"

log() {
  printf '[%s] %s\n' "$(date +'%F %T')" "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

run_as_app_user() {
  runuser -u "$APP_USER" -- "$@"
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :$port" | tail -n +2 | grep -q .
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1
    return
  fi
  netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$port$"
}

pick_free_port() {
  local port="$1"
  while port_in_use "$port"; do
    port=$((port + 1))
  done
  printf '%s' "$port"
}

install_system_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    fail "Этот скрипт сейчас поддерживает только Debian/Ubuntu (apt-get)."
  fi

  log "Installing required system packages..."
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git \
    python3 \
    python3-venv \
    python3-pip
}

ensure_app_user() {
  if id -u "$APP_USER" >/dev/null 2>&1; then
    log "User $APP_USER already exists."
    return
  fi
  log "Creating system user $APP_USER..."
  useradd --system --create-home --home-dir "/home/$APP_USER" --shell /usr/sbin/nologin "$APP_USER"
}

sync_repo() {
  mkdir -p "$APP_BASE_DIR"
  chown -R "$APP_USER:$APP_GROUP" "$APP_BASE_DIR"

  if [ -d "$APP_DIR/.git" ]; then
    log "Updating existing repository in $APP_DIR..."
    run_as_app_user git -C "$APP_DIR" fetch --all --prune
    run_as_app_user git -C "$APP_DIR" checkout "$BRANCH"
    run_as_app_user git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
    return
  fi

  if [ -e "$APP_DIR" ] && [ ! -d "$APP_DIR/.git" ]; then
    fail "Path $APP_DIR exists, but is not a git repository. Move it and rerun."
  fi

  log "Cloning repository into $APP_DIR..."
  run_as_app_user git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
}

setup_venv() {
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    log "Creating virtualenv in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
  fi

  log "Installing Python dependencies..."
  "$VENV_DIR/bin/pip" install --upgrade pip wheel
  "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" gunicorn
}

resolve_bind_and_port() {
  local service_file="/etc/systemd/system/$SERVICE_NAME"
  if [ -f "$service_file" ]; then
    local existing_bind
    existing_bind="$(grep -Eo -- '--bind [^ ]+' "$service_file" | awk '{print $2}' | tail -n 1 || true)"
    if [ -n "$existing_bind" ]; then
      BIND_ADDRESS="${existing_bind%:*}"
      APP_PORT="${existing_bind##*:}"
      log "Reusing existing bind ${BIND_ADDRESS}:${APP_PORT} from $SERVICE_NAME."
      return
    fi
  fi

  local preferred_port="$APP_PORT"
  APP_PORT="$(pick_free_port "$APP_PORT")"
  if [ "$APP_PORT" != "$preferred_port" ]; then
    log "Port $preferred_port is busy, selected free port $APP_PORT."
  fi
}

write_env_file() {
  if [ -f "$ENV_FILE" ]; then
    log "Env file exists at $ENV_FILE, keeping existing values."
    chown "root:$APP_GROUP" "$ENV_FILE"
    chmod 640 "$ENV_FILE"
    return
  fi

  log "Creating env file at $ENV_FILE..."
  local server_ip secret_key
  server_ip="$(hostname -I | awk '{print $1}')"
  secret_key="$(
    python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
  )"

  cat >"$ENV_FILE" <<EOF
DJANGO_SETTINGS_MODULE=kiyim_platform.settings_vps
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=$secret_key
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,$server_ip
PYTHONUNBUFFERED=1
EOF

  chown "root:$APP_GROUP" "$ENV_FILE"
  chmod 640 "$ENV_FILE"
}

django_prepare() {
  log "Running migrations and collectstatic..."
  mkdir -p "$APP_DIR/media" "$APP_DIR/staticfiles"
  chown -R "$APP_USER:$APP_GROUP" "$APP_BASE_DIR"

  run_as_app_user /bin/bash -lc "
    set -Eeuo pipefail
    cd '$APP_DIR'
    set -a
    source '$ENV_FILE'
    set +a
    '$VENV_DIR/bin/python' manage.py migrate --noinput
    '$VENV_DIR/bin/python' manage.py collectstatic --noinput
  "
}

write_systemd_service() {
  log "Writing systemd service /etc/systemd/system/$SERVICE_NAME..."
  cat >"/etc/systemd/system/$SERVICE_NAME" <<EOF
[Unit]
Description=$APP_NAME Django (Gunicorn)
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/gunicorn --workers $WORKERS --bind $BIND_ADDRESS:$APP_PORT --timeout 120 --access-logfile - --error-logfile - kiyim_platform.wsgi:application
Restart=always
RestartSec=5
KillSignal=SIGQUIT
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"
}

print_summary() {
  local server_ip
  server_ip="$(hostname -I | awk '{print $1}')"

  log "Deployment complete."
  log "Service: $SERVICE_NAME"
  log "Status : $(systemctl is-active "$SERVICE_NAME")"
  log "URL    : http://$server_ip:$APP_PORT"
  log "Logs   : journalctl -u $SERVICE_NAME -f"
  log "Note   : This app is isolated in $APP_BASE_DIR and does not modify other projects."
}

main() {
  [ "$(id -u)" -eq 0 ] || fail "Run as root: sudo bash deploy_vps.sh"
  install_system_packages
  ensure_app_user
  sync_repo
  setup_venv
  resolve_bind_and_port
  write_env_file
  django_prepare
  write_systemd_service
  print_summary
}

main "$@"
