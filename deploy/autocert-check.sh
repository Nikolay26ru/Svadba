#!/usr/bin/env bash
# Runs on a timer: as soon as the domain publicly resolves to THIS server,
# obtain the TLS certificate and stop the timer. Makes HTTPS fully automatic
# after the A record is pointed here and DNS propagates.
set -euo pipefail

DOMAIN="${DOMAIN:-kostya-i-gera.ru}"
SERVER_IP="${SERVER_IP:-155.212.223.189}"

if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  systemctl disable --now svadba-autocert.timer 2>/dev/null || true
  exit 0
fi

resolved="$(dig +short A "$DOMAIN" @1.1.1.1 | tail -n1 || true)"
[ -z "$resolved" ] && resolved="$(dig +short A "$DOMAIN" @8.8.8.8 | tail -n1 || true)"

if [ "$resolved" = "$SERVER_IP" ]; then
  echo "DNS points to $SERVER_IP — issuing certificate."
  /opt/svadba/deploy/enable-https.sh
  systemctl disable --now svadba-autocert.timer 2>/dev/null || true
else
  echo "DNS not ready (A=$resolved, expected $SERVER_IP). Will retry later."
fi
