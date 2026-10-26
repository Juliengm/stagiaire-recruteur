#!/bin/sh
# Basic auth depuis BASIC_AUTH_USER / BASIC_AUTH_PASSWORD (.env). Sans identifiants : refus de démarrer.
set -eu
if [ -z "${BASIC_AUTH_USER:-}" ] || [ -z "${BASIC_AUTH_PASSWORD:-}" ]; then
    echo "BASIC_AUTH_USER et BASIC_AUTH_PASSWORD sont obligatoires" >&2
    exit 1
fi
hash=$(printf '%s' "$BASIC_AUTH_PASSWORD" | openssl passwd -apr1 -stdin)
printf '%s:%s\n' "$BASIC_AUTH_USER" "$hash" > /etc/nginx/htpasswd
chmod 640 /etc/nginx/htpasswd
chgrp nginx /etc/nginx/htpasswd
