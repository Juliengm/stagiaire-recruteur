# stagiaire-recruteur

> Bonjour. Je suis le stagiaire recruteur de **Julien Gasser Morlay**.
> Je ne suis pas un vrai stagiaire : je suis un pipeline de données. Si vous lisez ceci,
> c'est probablement que je vous ai écrit, et que Julien a validé le message avant que je l'envoie.

---

## Ce que je fais

Julien est spécialiste du suivi-évaluation et de la donnée : 10 ans d'expérience, 33 pays,
installé à Madagascar depuis 8 ans, et 5 ans à la tête d'une équipe Data qui a suivi plus de
200 études. Il cherche son prochain poste, à Antananarivo, à Lille ou à distance.

Moi, je m'occupe de la partie ingrate :

1. **Je fais la tournée des offres** chaque matin à 5 h (heure de Tana) : API, flux RSS, pages carrières,
   alertes e-mail. ReliefWeb, France Travail, les avis de la Banque mondiale, les agences de l'ONU,
   quelques dizaines d'organisations.
2. **Je range.** Chaque source a son format ; je ramène tout dans un seul schéma (titre, organisation,
   lieu, type de contrat, date limite).
3. **Je dédoublonne.** La même offre UNICEF vue sur trois sites, c'est une seule offre.
4. **Je trie.** Je donne un score à chaque offre (mots-clés, lieu, et similarité avec chacun des trois
   CV de Julien) et je propose le CV le plus adapté.
5. **Je fais mon rapport** deux fois par semaine : uniquement les nouvelles offres pertinentes, et les relances à faire.
6. **Je prépare les candidatures.** Pour une offre que Julien retient, je rédige un brouillon d'e-mail et de
   lettre de motivation, je joins le bon CV.
7. **J'attends le feu vert.** Julien relit, corrige, et clique sur « Envoyer ». Pas avant.

```
 Sources ─► Collecte ─► Brut ─► Normalisation ─► Dédoublonnage ─► Score ─► Interface ─► ✋ Julien valide ─► E-mail
                                                                          └─► Rapport du stagiaire (lundi, jeudi)
```

## Ce que je ne fais pas

- **Je n'envoie rien sans l'accord de Julien.** Chaque e-mail est relu et validé à la main.
- **Je n'envoie pas en masse.** Une offre, un message, écrit pour elle. Dix au maximum par jour, et jamais deux fois à la même organisation en trois mois.
- **Je ne force aucune porte.** Je respecte les `robots.txt` des sites et des flux, et les conditions d'utilisation des API officielles que j'interroge ; quand un site ne veut pas de visiteurs automatiques, je lis les alertes e-mail auxquelles Julien est abonné.
- **Je n'invente rien.** Les lettres que je prépare ne s'appuient que sur le CV de Julien. S'il n'a pas fait quelque chose, je ne l'écris pas.
- Je ne suis pas rémunéré. Je suis nourri au cron.

## Comment je suis construit

| | |
|---|---|
| Orchestration | **Dagster** — chaque étape est un *asset*, avec des contrôles qualité (source muette, schéma, taux de doublons) |
| Collecte | Python, `httpx`, `feedparser`, `selectolax`, API Gmail ; un connecteur par type de source (API, RSS, Workday, SmartRecruiters, Workable…) |
| Stockage | **PostgreSQL** + `pgvector` |
| Pertinence | règles de mots-clés + embeddings multilingues (FR/EN) comparés aux CV |
| Rédaction | modèles Jinja2 + LLM, avec garde-fous vérifiés après génération |
| Interface | **FastAPI** + **Vue 3** |
| Envoi | API Gmail, depuis l'adresse de Julien |
| Déploiement | **Docker Compose** sur un petit VPS, CI GitHub Actions |

<!-- schéma d'architecture et captures d'écran : à ajouter en phase 6 -->

## Pourquoi Julien m'a créé

Parce qu'il passe ses journées à concevoir des systèmes de collecte et de suivi de données pour des
projets de développement — enquêtes ODK, bases de suivi, tableaux de bord — et qu'il s'est dit qu'il
pouvait appliquer la même méthode à sa propre recherche d'emploi.

Je suis donc à la fois un outil et une démonstration : si vous recrutez quelqu'un pour construire des
pipelines de données propres, documentés et qui tournent tout seuls, vous avez sous les yeux un exemple
de ce qu'il fait.

## Lancer le projet

```bash
cp .env.example .env      # renseigner les clés (Gmail, ReliefWeb…)
docker compose up -d      # dev : ports sur 127.0.0.1 seulement (docker-compose.override.yml)
# Interface : http://localhost:8080 — Dagster : http://localhost:8080/dagster/ (ou :3000/dagster/)
# API : http://127.0.0.1:8000/docs
```

**Accès en production** : `https://<domaine>/`, identifiant et mot de passe de la basic auth
(`BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD` dans le `.env` du serveur). La même authentification
protège l'API (`/api/`, documentation sur `/api/docs`) et Dagster (`/dagster/`). Rien d'autre n'est
exposé. Installation, certificat HTTPS, sauvegardes : [docs/deploiement.md](docs/deploiement.md).

Tests de l'API : ils utilisent la base `veille_test` du Postgres de Docker, publié en dev sur
`127.0.0.1:5433` (`VEILLE_TEST_DB_URL` pour en choisir une autre).

```bash
cd api && uv run pytest -q && uv run ruff check . && uv run mypy src tests
```

Interface (Vue 3, `web/`) : trois vues, **Offres** (tri au clavier : `j`/`k`, `o` ouvrir, `i` `a` `e` `g` `r` `x` `n`
pour le statut, `c` créer une candidature), **Candidatures** (tableau éditable, relances en retard en rouge,
import du fichier Excel) et **Sources** (état, activation, « lancer maintenant » qui déclenche le job Dagster par
son API GraphQL). En développement : `cd web && npm install && npm run dev` (l'API de Docker est jointe par le
proxy de Vite).

Ajouter une offre trouvée ailleurs : dans Claude Code, `/offre <lien | PDF | texte collé>` (ou `/offre` seul
pour les e-mails Gmail libellés `a-ajouter`). Claude lit l'offre, la structure et l'envoie à
`POST /offers/manual` ; le job `process` la note comme les autres. Voir `.claude/commands/offre.md`.

Préparer les candidatures : `/candidatures` (offres « ça sent bon » sans candidature, ou `/candidatures <id>`).
Claude choisit le CV, rédige l'e-mail et la lettre de motivation à partir des seuls faits de `cv/` (hors
dépôt), les pré-contrôle et les range dans la vue **Brouillons**. Julien y corrige l'e-mail et la lettre
(éditeur WYSIWYG), change de CV si besoin, prévisualise la lettre en PDF, puis clique « Déposer dans
Gmail » : l'API refait les contrôles (termes interdits, une page, chiffres absents des faits) et crée le
brouillon avec le CV et la lettre en pièces jointes. **L'API ne sait pas envoyer** (un test le vérifie) :
Julien envoie lui-même depuis Gmail. Les brouillons envoyés passent ensuite en « postulé », avec une
relance à 10 jours. Voir `.claude/commands/candidatures.md`.

Les CV, les données personnelles et les e-mails réels ne sont pas dans ce dépôt.

## Contacter Julien

Directement, sans passer par moi : **julien.gassermorlay@gmail.com**

*— Le stagiaire*
