---
description: Prépare les candidatures (e-mail, lettre de motivation, CV) des offres retenues et les dépose en brouillons Gmail
argument-hint: "[id d'offre …]  (vide : offres « ça sent bon » sans candidature)  [--dev] [--test]"
---

Tu prépares des candidatures pour Julien. **Tu n'envoies rien** : tu crées des brouillons Gmail que Julien
relit et envoie lui-même. Le ton et les faits comptent plus que la vitesse.

Entrée : $ARGUMENTS

- `--dev` : API de dev (sinon production, `--prod` dans toutes les commandes `scripts/api.py`).
- `--test` : chaque brouillon est adressé à Julien lui-même, pas au recruteur.

Commandes, depuis la racine du dépôt :

```bash
API="uv run --project api python scripts/api.py --prod"            # sans --prod si --dev
OUTIL="uv run --project pipeline --with weasyprint python scripts/candidature.py"
```

## 0. Lire les sources (une fois par exécution)

- `cv/faits.md` : **seule source de faits**, avec les CV. Tout ce qui n'y est pas n'est pas écrit.
  L'adresse e-mail qui y figure est l'expéditeur (`--expediteur`).
- Les CV de `cv/` (`.docx`, lis-les avec `pandoc <fichier> -t plain`) : seulement celui que tu choisis.

## 1. Repérer les candidatures envoyées

`$API GET /applications` : pour chaque candidature qui a un `gmail_thread_id` et pas de `sent_at`,
`$OUTIL suivi <gmail_thread_id> --expediteur <adresse>`. Si `etat` vaut `envoye` :

- `PATCH /applications/<id>` avec `{"status": "applied", "sent_at": <envoye_le>, "follow_up_at": <envoye_le + 10 jours>}` ;
- `PATCH /offers/<offer_id>/status` avec `{"status": "applied"}`.

Signale en une ligne les candidatures passées en « postulé ».

## 2. Choisir les offres

Identifiants donnés : ceux-là. Sinon : `$API GET "/offers?status=interesting"`, puis pour chacune
`$API GET /offers/<id>` ; garde celles dont `application_ids` est vide, cinq au plus, les mieux notées
d'abord. Une offre qui a déjà une candidature n'est refaite que si Julien a donné son identifiant.

Pour chaque offre, crée le dossier `cv/candidatures/<AAAA-MM-JJ>_<Organisation>_<id>/` (hors dépôt) et
enregistre la réponse de `GET /offers/<id>` dans `offre.json`.

## 3. Décider

- **Langue** : celle de l'offre (`language`).
- **CV** : selon le tableau « Choix du CV » de `cv/faits.md` (profil et langue de l'offre).
- **Segment** :
  - `tech` pour une ESN, un cabinet data ou IA, un éditeur de logiciels ou une start-up ;
  - `institutionnel` pour tout le reste (ONU, bailleurs, ONG, projets, ministères, cabinets d'études,
    grands groupes).
  En cas de doute : `institutionnel`.
- **Mode** :
  - `e-mail` si `contact_emails` donne une adresse de candidature et que l'offre ne renvoie pas vers
    un portail ;
  - `portail` sinon (`apply_url`, formulaire, Workday, Inspira…). Pour ce mode, prépare la lettre et
    le CV, mais pas de brouillon.
  - Plusieurs adresses : prends celle que l'offre désigne pour les candidatures ; mets en copie (`--cc`)
    celles que l'offre demande de mettre en copie.
- **Pièces exigées** : relève tout ce que l'offre demande en plus du CV et de la lettre (diplômes,
  attestations, références, formulaire). Tu ne peux pas les fournir : liste-les dans le compte rendu.
  Si l'offre demande un « CV détaillé » ou des références, prends le CV complet.

## 4. Rédiger

Écris trois fichiers dans le dossier de l'offre : `objet.txt`, `email.txt` (texte brut) et
`lettre.md`.

**Lettre de motivation** (`lettre.md`), sérieuse et signée par Julien, quel que soit le segment :

```markdown
Julien Gasser Morlay
Antananarivo, Madagascar · <téléphone> · <e-mail>

> <Organisation>
> <Service ou lieu, s'ils sont connus>

<p class="date"><Ville>, le <date du jour en toutes lettres></p>

**Objet : candidature au poste de <intitulé exact> <(référence de l'offre, s'il y en a une)>**

Madame, Monsieur,

<3 ou 4 paragraphes>

Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.

Julien Gasser Morlay
```

(En anglais : `Dear Hiring Manager,` … `Yours faithfully,`.) Les blocs entre chevrons sont à remplir
à partir de `cv/faits.md` et de l'offre.

Contenu des paragraphes :

1. **Le poste et pourquoi lui.** Une phrase d'accroche liée à l'offre, pas une banalité.
2. **Deux ou trois références précises** de `cv/faits.md`, choisies pour cette offre, avec leurs
   chiffres exacts. Pas une liste de compétences.
3. **Ce qu'il apporte à cette organisation** : un lien concret avec la mission décrite dans l'offre.
4. **Disponibilité et zone**, avec la formulation de `cv/faits.md`. Pour une offre à Lille, cite le lien
   avec Lille.

Règles :

- 250 à 330 mots ; une page au rendu.
- Pas de superlatifs ni de formules creuses (« passionné », « dynamique », « je suis convaincu que »).
- Les formulations imposées de `cv/faits.md` s'appliquent, notamment sur la réinstallation.

**E-mail** (`objet.txt` et `email.txt`) :

- Objet : **celui que l'offre impose, au caractère près**, s'il y en a un. Sinon
  `Candidature — <intitulé exact> — Julien Gasser Morlay` (ajoute la référence de l'offre si elle existe).
- Segment `institutionnel` : sobre, signé Julien, 5 à 8 lignes. Le poste, deux phrases sur ce qu'il
  apporte, la mention des pièces jointes (CV et lettre de motivation), la signature de `cv/faits.md`.
  Le lien GitHub seulement si le poste a une composante data.
- Segment `tech` : le stagiaire écrit. Structure :

  > Bonjour <prénom du contact, sinon « Madame, Monsieur »>,
  >
  > Je suis le stagiaire recruteur de Julien Gasser Morlay. Je ne suis pas un vrai stagiaire : je suis un
  > petit pipeline de données qu'il a construit pour repérer les offres qui lui correspondent. J'ai trouvé
  > la vôtre, il l'a lue, et c'est lui qui m'a demandé de vous écrire.
  >
  > <2 ou 3 phrases de Julien sur le poste et ce qu'il apporte, écrites pour cette offre>
  >
  > Vous trouverez son CV et sa lettre de motivation en pièces jointes. Si vous voulez voir comment je
  > travaille (et donc comment il travaille), tout est expliqué ici : <lien GitHub de cv/faits.md>
  >
  > Julien reste joignable directement : <téléphone> — <e-mail>.
  >
  > Bonne journée,
  > Le stagiaire recruteur de Julien (non rémunéré, nourri au cron)

## 5. Vérifier et produire les PDF

```bash
$OUTIL verifier --offre <dossier>/offre.json --objet "$(cat <dossier>/objet.txt)" \
  --email <dossier>/email.txt --lettre <dossier>/lettre.md
$OUTIL lettre <dossier>/lettre.md "<dossier>/LM_Julien_Gasser_Morlay_<Organisation>.pdf"
$OUTIL cv-pdf cv/<CV choisi>.docx
```

- `verifier` signale un terme interdit, l'organisation ou l'intitulé absents, ou un nombre qu'on ne
  trouve ni dans les faits, ni dans les CV, ni dans l'offre. Corrige et relance jusqu'à « aucun problème ».
  Si un nombre signalé est légitime (une date, un numéro de référence de l'offre), dis-le à Julien au
  lieu de forcer.
- `lettre` sort en erreur si le PDF dépasse une page : raccourcis.
- `<Organisation>` dans les noms de fichiers : lettres et chiffres sans accents, séparés par `_`.

## 6. Déposer le brouillon (mode e-mail)

```bash
$OUTIL brouillon --expediteur <e-mail de cv/faits.md> --a <contact> [--cc <copie> …] \
  --objet "$(cat <dossier>/objet.txt)" --corps <dossier>/email.txt --pj <CV en PDF> <LM en PDF>
```

Avec `--test`, `--a` est l'adresse de Julien, sans `--cc`. Le script refuse si le jeton Gmail n'est pas celui de
l'expéditeur : arrête-toi et dis-le.

## 7. Enregistrer la candidature

`$API POST /applications` avec :

```json
{"offer_id": <id>, "organization": "...", "position": "<intitulé>", "contact": "<adresse ou lien du portail>",
 "cv_sent": "<nom du CV>", "status": "new", "notes": "brouillon Gmail du <date>" | "portail : <lien>",
 "gmail_draft_id": "...", "gmail_thread_id": "..."}
```

En mode portail, `gmail_*` reste vide. Julien passera la candidature en « postulé » dans l'interface
après avoir déposé son dossier. En mode `--test`, n'enregistre rien.

## 8. Rendre compte

Une ligne par offre :

> **Intitulé** — Organisation · date limite · CV · segment · brouillon Gmail prêt (ou : portail <lien>, fichiers dans <dossier>)
> Pièces à ajouter toi-même : … (s'il y en a)
> Points faibles par rapport à l'offre : … (exigences que les faits ne couvrent pas, en une ligne)

Puis le lien https://mail.google.com/mail/u/0/#drafts.

Termine en rappelant que rien n'est parti : Julien relit et envoie chaque brouillon lui-même.
