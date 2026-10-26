#!/bin/sh
# Certificat Let's Encrypt s'il existe ; sinon auto-signé (premier démarrage, essais en local).
set -eu
live="/etc/letsencrypt/live/$DOMAIN"
certs=/etc/nginx/certs
mkdir -p "$certs"
if [ -s "$live/fullchain.pem" ]; then
    ln -sf "$live/fullchain.pem" "$certs/fullchain.pem"
    ln -sf "$live/privkey.pem" "$certs/privkey.pem"
else
    if [ ! -s "$certs/selfsigned.pem" ]; then
        openssl req -x509 -nodes -newkey rsa:2048 -days 30 -subj "/CN=$DOMAIN" \
            -keyout "$certs/selfsigned.key" -out "$certs/selfsigned.pem" 2>/dev/null
    fi
    ln -sf "$certs/selfsigned.pem" "$certs/fullchain.pem"
    ln -sf "$certs/selfsigned.key" "$certs/privkey.pem"
    echo "40-certs: pas de certificat Let's Encrypt pour $DOMAIN, certificat auto-signé" >&2
fi
