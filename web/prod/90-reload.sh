#!/bin/sh
# Recharge nginx toutes les 6 h pour prendre les certificats renouvelés par le service certbot.
(while sleep 6h; do /docker-entrypoint.d/40-certs.sh && nginx -s reload; done) &
