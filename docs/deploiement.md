# Déploiement sur un VPS

Cible : un VPS dédié (2 vCPU, 4 Go, Ubuntu), un nom de domaine pointant dessus. L'interface est
publique : HTTPS (Let's Encrypt) et basic auth devant tout (front, `/api/`, `/dagster/`). Seul le
conteneur `web` publie des ports (80 et 443) ; Postgres, l'API et Dagster ne sont joignables que
par le réseau Docker.

Toutes les commandes Compose de production passent par les deux fichiers (jamais l'override de dev) :

```bash
alias dc='docker compose -f docker-compose.yml -f docker-compose.prod.yml'
```

## 1. Préparer le serveur (une fois)

```bash
# utilisateur de déploiement avec la clé SSH du poste, puis :
sudo apt update && sudo apt upgrade -y
sudo apt install -y git fail2ban ufw
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER            # se reconnecter ensuite

# 2 Go de swap : absorbe les pics du modèle d'embeddings
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# pare-feu : SSH, HTTP, HTTPS (Docker contourne ufw, mais seuls 80/443 sont publiés)
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
```

fail2ban protège SSH avec ses réglages par défaut ; mettre ses propres IP dans `ignoreip`
(`/etc/fail2ban/jail.local`) évite de se bannir soi-même.

DNS : un enregistrement A (et AAAA si IPv6) du domaine vers l'IP du VPS, avant l'étape 4.

## 2. Code et secrets

Le code déployé doit d'abord être poussé depuis le poste (branche de travail ou `main` après
fusion).

```bash
git clone -b <branche> https://github.com/<compte>/stagiaire-recruteur.git ~/stagiaire-recruteur
```

Ce qui n'est **jamais** dans git se copie depuis le poste par `scp` :

```bash
scp .env.prod  <vps>:~/stagiaire-recruteur/.env        # voir ci-dessous
scp -r credentials cv <vps>:~/stagiaire-recruteur/
```

`.env` de production : partir de `.env.example` et renseigner au minimum

- `POSTGRES_PASSWORD` (long, aléatoire) et le même dans `VEILLE_DB_URL` ;
- `DOMAIN`, `LETSENCRYPT_EMAIL`, `INTERFACE_URL=https://<DOMAIN>/` ;
- `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD` (sans `$`, ex. `openssl rand -base64 24`) ;
- `SCHEDULES_RUNNING=true` (sinon Dagster laisse les planifications arrêtées) ;
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `DIGEST_TO` (pas de Mailpit
  en prod) ; `DISCORD_WEBHOOK_URL` si besoin ;
- les clés des sources (`RELIEFWEB_APPNAME`…), `CONTACT_EMAIL`.

Le jeton Gmail se crée sur le poste (`scripts/gmail_auth.py` ouvre le navigateur), puis se copie
avec `credentials/`.

## 3. Premier démarrage

```bash
dc up -d --build
dc ps
```

Sans certificat Let's Encrypt, nginx démarre avec un certificat auto-signé (avertissement du
navigateur) : c'est normal jusqu'à l'étape 4.

## 4. Certificat HTTPS (une fois)

Let's Encrypt limite les échecs (environ 5 par heure et par domaine) : essayer d'abord en staging.

```bash
set -a; . ./.env; set +a
dc run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --staging
# si c'est bon, le vrai certificat :
dc run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --force-renewal
dc exec web sh -c '/docker-entrypoint.d/40-certs.sh && nginx -s reload'
```

Le service `certbot` renouvelle ensuite tout seul (toutes les 12 h) et nginx se recharge toutes
les 6 h.

## 5. Après le premier démarrage

1. Ouvrir `https://<DOMAIN>/` (identifiants de `.env`), vue **Sources** :
   « Mettre à jour la liste des sources » (crée les partitions ; sinon rien avant 04:00).
2. Données : importer le fichier Excel dans **Candidatures** (import idempotent), ou restaurer une
   sauvegarde du poste (§6).
3. Dagster : `https://<DOMAIN>/dagster/` ; vérifier que les planifications sont **Running**.

## 6. Sauvegardes

Le service `backup` fait un `pg_dump` quotidien de la base `veille` dans `./backups/`
(14 jours de rotation). La sauvegarde de l'hébergeur ne garde que 24 h : il faut **une copie hors du VPS**,
par exemple depuis le poste :

```bash
rsync -av <vps>:~/stagiaire-recruteur/backups/ ~/Sauvegardes/stagiaire-recruteur/
```

Restauration (dans une base vide, ex. après réinstallation) :

```bash
dc exec -T postgres createdb -U veille veille_restauree
dc exec -T postgres pg_restore -U veille -d veille_restauree --no-owner < backups/veille-AAAAMMJJ-HHMM.dump
```

Les sauvegardes contiennent des données personnelles : ne jamais les mettre dans git.

## 7. Mises à jour

```bash
cd ~/stagiaire-recruteur && git pull && dc up -d --build
```

Les migrations Alembic passent automatiquement (service `migrate`). Nettoyer de temps en temps les
anciennes images : `docker image prune -f`.

Si « lancer maintenant » répond `Could not find Pipeline …` après une mise à jour, l'interface
Dagster n'a pas rechargé le code : `dc restart dagster-webserver dagster-daemon`.

## Mémoire

Limites par conteneur dans `docker-compose.prod.yml` ; `dagster-code` a la plus grosse (3 Go) car
les runs et le modèle d'embeddings y tournent. Mesure (pile de prod en local, job
`process` avec chargement du modèle) : 2,5 Go atteints, dont ~1,2 Go de fichiers du modèle en cache ;
pas d'OOM mais le noyau récupérait sans cesse du cache sous l'ancienne limite de 2,5 Go. Au repos,
les autres services prennent ~0,7 Go au total.

Tant que `embedding.weight` vaut 0 dans `config/scoring.yaml` (les embeddings ne comptent pas dans
le score), `EMBEDDING_MODEL=fake` dans `.env` évite de charger le modèle et économise ~1,5 Go.
