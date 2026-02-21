#!/usr/bin/env bash
set -Eeuo pipefail

# Idempotent VPS deploy script for this project.
# It deploys to an isolated path, runs on a dedicated port and publishes via Nginx domain config.
# Existing projects are not removed or modified.

APP_NAME="${APP_NAME:-qq}"
APP_DOMAIN="${APP_DOMAIN:-mydomen.uz}"
APP_USER="${APP_USER:-qqapp}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
APP_BASE_DIR="${APP_BASE_DIR:-/opt/$APP_NAME}"
APP_DIR="${APP_DIR:-$APP_BASE_DIR/app}"
VENV_DIR="${VENV_DIR:-$APP_BASE_DIR/venv}"
REPO_URL="${REPO_URL:-https://github.com/SultanbekKenesbaev/qq.git}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-${APP_NAME}-app.service}"
ENV_FILE="${ENV_FILE:-/etc/${APP_NAME}.env}"
BIND_ADDRESS="${BIND_ADDRESS:-127.0.0.1}"
APP_PORT="${APP_PORT:-18010}"
WORKERS="${WORKERS:-3}"
ENABLE_SSL="${ENABLE_SSL:-true}"
ENABLE_WWW_ALIAS="${ENABLE_WWW_ALIAS:-true}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-admin@${APP_DOMAIN}}"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/sites-available/${APP_NAME}.conf}"
NGINX_LINK="${NGINX_LINK:-/etc/nginx/sites-enabled/${APP_NAME}.conf}"

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

is_true() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

upsert_env() {
  local key="$1"
  local value="$2"
  local escaped

  escaped="$(printf '%s' "$value" | sed 's/[&|]/\\&/g')"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
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
  local packages=(
    git
    python3
    python3-venv
    python3-pip
    nginx
  )

  if is_true "$ENABLE_SSL"; then
    packages+=(certbot python3-certbot-nginx)
  fi

  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
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
  log "Creating/updating env file at $ENV_FILE..."
  local server_ip secret_key allowed_hosts settings_module
  server_ip="$(hostname -I | awk '{print $1}')"
  settings_module="kiyim_platform.settings"
  if [ -f "$APP_DIR/kiyim_platform/settings_vps.py" ]; then
    settings_module="kiyim_platform.settings_vps"
  fi

  mkdir -p "$(dirname "$ENV_FILE")"
  touch "$ENV_FILE"

  secret_key="$(grep -E '^DJANGO_SECRET_KEY=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  if [ -z "$secret_key" ]; then
    secret_key="$(
      python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
    )"
  fi

  allowed_hosts="127.0.0.1,localhost,$server_ip,$APP_DOMAIN"
  if is_true "$ENABLE_WWW_ALIAS" && [[ "$APP_DOMAIN" != www.* ]]; then
    allowed_hosts="$allowed_hosts,www.$APP_DOMAIN"
  fi

  upsert_env "DJANGO_SETTINGS_MODULE" "$settings_module"
  upsert_env "DJANGO_DEBUG" "False"
  upsert_env "DJANGO_SECRET_KEY" "$secret_key"
  upsert_env "DJANGO_ALLOWED_HOSTS" "$allowed_hosts"
  upsert_env "DJANGO_BEHIND_HTTPS" "False"
  upsert_env "PYTHONUNBUFFERED" "1"

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

check_nginx_domain_conflict() {
  local escaped_domain other_hits
  escaped_domain="${APP_DOMAIN//./\\.}"

  other_hits="$(
    grep -RslE "server_name[^;]*\\b(${escaped_domain}|www\\.${escaped_domain})\\b" \
      /etc/nginx/sites-available /etc/nginx/conf.d 2>/dev/null || true
  )"
  if [ -z "$other_hits" ]; then
    return
  fi

  other_hits="$(printf '%s\n' "$other_hits" | grep -vFx "$NGINX_CONF" || true)"
  if [ -z "$other_hits" ]; then
    return
  fi

  printf 'ERROR: Domain %s already exists in nginx configs:\n%s\n' "$APP_DOMAIN" "$other_hits" >&2
  printf 'Use another APP_DOMAIN to avoid conflict.\n' >&2
  exit 1
}

write_nginx_config() {
  local server_names="$APP_DOMAIN"
  if is_true "$ENABLE_WWW_ALIAS" && [[ "$APP_DOMAIN" != www.* ]]; then
    server_names="$server_names www.$APP_DOMAIN"
  fi

  check_nginx_domain_conflict

  log "Writing nginx config at $NGINX_CONF..."
  cat >"$NGINX_CONF" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $server_names;

    client_max_body_size 25M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias $APP_DIR/media/;
        access_log off;
        expires 30d;
    }

    location / {
        proxy_pass http://$BIND_ADDRESS:$APP_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120;
    }
}
EOF

  ln -sfn "$NGINX_CONF" "$NGINX_LINK"
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
}

domain_points_to_server() {
  local domain_ips local_ips
  domain_ips="$(getent ahostsv4 "$APP_DOMAIN" 2>/dev/null | awk '{print $1}' | sort -u || true)"
  local_ips="$(hostname -I | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' || true)"

  if [ -z "$domain_ips" ] || [ -z "$local_ips" ]; then
    return 1
  fi

  while IFS= read -r dip; do
    if printf '%s\n' "$local_ips" | grep -qx "$dip"; then
      return 0
    fi
  done <<<"$domain_ips"
  return 1
}

setup_ssl_if_possible() {
  if ! is_true "$ENABLE_SSL"; then
    log "SSL disabled (ENABLE_SSL=$ENABLE_SSL)."
    return
  fi

  if ! domain_points_to_server; then
    log "Domain $APP_DOMAIN is not pointed to this VPS yet. Skipping SSL for now."
    log "After DNS A-record is configured, rerun: sudo ENABLE_SSL=true bash deploy_vps.sh"
    return
  fi

  log "Requesting Let's Encrypt certificate for $APP_DOMAIN..."
  local cert_domains=("-d" "$APP_DOMAIN")
  if is_true "$ENABLE_WWW_ALIAS" && [[ "$APP_DOMAIN" != www.* ]]; then
    cert_domains+=("-d" "www.$APP_DOMAIN")
  fi

  if certbot --nginx --non-interactive --agree-tos --keep-until-expiring --redirect \
      --email "$CERTBOT_EMAIL" "${cert_domains[@]}"; then
    upsert_env "DJANGO_BEHIND_HTTPS" "True"
    systemctl restart "$SERVICE_NAME"
    log "SSL configured successfully."
  else
    log "Certbot failed. Application remains available over HTTP."
  fi
}

print_summary() {
  local server_ip scheme
  server_ip="$(hostname -I | awk '{print $1}')"
  scheme="http"
  if [ -f "/etc/letsencrypt/live/$APP_DOMAIN/fullchain.pem" ]; then
    scheme="https"
  fi

  log "Deployment complete."
  log "Service: $SERVICE_NAME"
  log "Status : $(systemctl is-active "$SERVICE_NAME")"
  log "Local  : http://$server_ip:$APP_PORT"
  log "Public : $scheme://$APP_DOMAIN"
  if is_true "$ENABLE_WWW_ALIAS" && [[ "$APP_DOMAIN" != www.* ]]; then
    log "Public : $scheme://www.$APP_DOMAIN"
  fi
  log "Logs   : journalctl -u $SERVICE_NAME -f"
  log "Nginx  : $NGINX_CONF"
  log "Note   : App is isolated in $APP_BASE_DIR and does not modify other projects."
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
  write_nginx_config
  setup_ssl_if_possible
  print_summary
}

main "$@"
