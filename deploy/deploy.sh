#!/usr/bin/env bash
#
# Idempotent deploy for the Svadba RSVP service on Ubuntu.
# Run as root from the repository root checked out at /opt/svadba:
#
#   ADMIN_PASSWORD='...' MAIL_PASS='...' bash deploy/deploy.sh
#
# Secrets are read from the environment and written only into the server-local
# env file (/opt/svadba/svadba.env) — never into the repository.
set -euo pipefail

ROOT=/opt/svadba
APP="$ROOT/app"
VENV="$ROOT/venv"
ENV_FILE="$ROOT/svadba.env"
DATA="$ROOT/data"
SVC_USER=svadba
DOMAIN=kostya-i-gera.ru

echo "==> Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx certbot python3-certbot-nginx dnsutils curl >/dev/null

echo "==> Creating service user '$SVC_USER'"
id "$SVC_USER" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "$SVC_USER"

echo "==> Preparing directories"
mkdir -p "$DATA"
chown -R "$SVC_USER:$SVC_USER" "$DATA"

echo "==> Python virtualenv"
test -d "$VENV" || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$ROOT/requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
  echo "==> Generating env file (first run)"
  : "${ADMIN_PASSWORD:?Set ADMIN_PASSWORD when creating the env file}"
  SECRET_KEY="$(openssl rand -hex 32)"
  ADMIN_PATH="${ADMIN_PATH:-admin-$(openssl rand -hex 4)}"
  export ADMIN_PASSWORD
  ADMIN_PASSWORD_HASH="$("$VENV/bin/python" -c "import os;from werkzeug.security import generate_password_hash as g;print(g(os.environ['ADMIN_PASSWORD']))")"

  umask 077
  cat > "$ENV_FILE" <<EOF
SECRET_KEY=$SECRET_KEY
ADMIN_PASSWORD_HASH=$ADMIN_PASSWORD_HASH
ADMIN_PATH=$ADMIN_PATH
COOKIE_SECURE=${COOKIE_SECURE:-false}
BASE_URL=${BASE_URL:-https://$DOMAIN}
DB_PATH=$DATA/svadba.db
LOGIN_MAX_ATTEMPTS=5
LOGIN_WINDOW_SECONDS=900
WEDDING_DATE=26.06.2026
DISPLAY_TZ=Europe/Moscow
MAIL_ENABLED=${MAIL_ENABLED:-false}
MAIL_USER=${MAIL_USER:-info@$DOMAIN}
MAIL_PASS=${MAIL_PASS:-}
MAIL_TO=${MAIL_TO:-info@$DOMAIN}
SMTP_HOST=${SMTP_HOST:-smtp.beget.com}
SMTP_PORT=${SMTP_PORT:-465}
SMTP_MODE=${SMTP_MODE:-ssl}
EOF
  chown root:"$SVC_USER" "$ENV_FILE"
  chmod 640 "$ENV_FILE"
  echo "    Admin path: /$ADMIN_PATH"
else
  echo "==> Env file already exists — keeping it (edit $ENV_FILE to change settings)"
fi

echo "==> Installing systemd units"
install -m 644 "$ROOT/deploy/svadba.service" /etc/systemd/system/svadba.service
install -m 644 "$ROOT/deploy/svadba-autocert.service" /etc/systemd/system/svadba-autocert.service
install -m 644 "$ROOT/deploy/svadba-autocert.timer" /etc/systemd/system/svadba-autocert.timer
chmod +x "$ROOT/deploy/enable-https.sh" "$ROOT/deploy/autocert-check.sh"
systemctl daemon-reload
systemctl enable --now svadba

echo "==> Configuring nginx"
install -m 644 "$ROOT/deploy/nginx-svadba.conf" /etc/nginx/sites-available/svadba.conf
ln -sf /etc/nginx/sites-available/svadba.conf /etc/nginx/sites-enabled/svadba.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo "==> Enabling auto-HTTPS timer (issues cert once DNS points here)"
systemctl enable --now svadba-autocert.timer

echo "==> Restarting service"
systemctl restart svadba
sleep 1
systemctl --no-pager --full status svadba | head -n 8 || true

echo "==> Done. Local health check:"
curl -fsS http://127.0.0.1:8000/healthz && echo "  gunicorn OK"
curl -fsS -H 'Host: '"$DOMAIN" http://127.0.0.1/healthz && echo "  nginx OK"
