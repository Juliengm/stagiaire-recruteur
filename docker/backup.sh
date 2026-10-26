#!/bin/sh
# Sauvegarde quotidienne de la base veille (format custom pg_dump), rotation BACKUP_KEEP_DAYS jours.
# Restauration : pg_restore -h postgres -U $POSTGRES_USER -d <base vide> --no-owner <fichier>
set -eu
export PGPASSWORD="$POSTGRES_PASSWORD"
while :; do
    out="/backups/veille-$(date +%Y%m%d-%H%M).dump"
    if pg_dump -h postgres -U "$POSTGRES_USER" -Fc veille > "$out.tmp"; then
        mv "$out.tmp" "$out"
        echo "sauvegarde : $out ($(du -h "$out" | cut -f1))"
    else
        rm -f "$out.tmp"
        echo "sauvegarde échouée" >&2
    fi
    find /backups -name 'veille-*.dump' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
    sleep 86400
done
