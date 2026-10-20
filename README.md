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
- **Je ne force aucune porte.** Je respecte les `robots.txt` et les conditions d'utilisation ; quand un site ne veut pas de visiteurs automatiques, je lis les alertes e-mail auxquelles Julien est abonné.
- **Je n'invente rien.** Les lettres que je prépare ne s'appuient que sur le CV de Julien. S'il n'a pas fait quelque chose, je ne l'écris pas.
- Je ne suis pas rémunéré. Je suis nourri au cron.

## Comment je suis construit

| | |
|---|---|
| Orchestration | **Dagster** — chaque étape est un *asset*, avec des contrôles qualité (source muette, schéma, taux de doublons) |
| Collecte | Python, `httpx`, `feedparser`, `selectolax`, IMAP ; un connecteur par type de source (API, RSS, Workday, SmartRecruiters, Workable…) |
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
cp .env.example .env      # renseigner les clés (France Travail, Gmail, IMAP…)
docker compose up -d
# Dagster : http://localhost:3000 — Interface : http://localhost:8080
```

Les CV, les données personnelles et les e-mails réels ne sont pas dans ce dépôt.

## Contacter Julien

Directement, sans passer par moi : **{{ e-mail }}** — **{{ téléphone }}** — {{ LinkedIn }}

*— Le stagiaire*
