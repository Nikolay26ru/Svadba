#!/usr/bin/env bash
# Issue a Let's Encrypt certificate and switch the site to HTTPS.
# Safe to run once the domain resolves to this server.
set -euo pipefail

DOMAIN="${DOMAIN:-kostya-i-gera.ru}"
EMAIL="${LE_EMAIL:-info@kostya-i-gera.ru}"
ENV_FILE=/opt/svadba/svadba.env

certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos -m "$EMAIL" --redirect

# Cookies can be marked Secure now that TLS is active.
if grep -q '^COOKIE_SECURE=' "$ENV_FILE"; then
  sed -i 's#^COOKIE_SECURE=.*#COOKIE_SECURE=true#' "$ENV_FILE"
else
  echo 'COOKIE_SECURE=true' >> "$ENV_FILE"
fi

systemctl restart svadba
nginx -t && systemctl reload nginx
echo "HTTPS enabled for https://$DOMAIN"
