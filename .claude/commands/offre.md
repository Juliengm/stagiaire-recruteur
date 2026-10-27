---
description: Ajoute une offre au stagiaire à partir d'un lien, d'un texte collé, d'un PDF, ou des e-mails Gmail libellés « a-ajouter »
argument-hint: "[lien | chemin de PDF | texte collé]  (vide : e-mails « a-ajouter »)  [--dev]"
---

Tu ajoutes une ou plusieurs offres d'emploi ou de consultance à la base du stagiaire recruteur.
Lis l'offre à la place de l'utilisateur : il ne doit rien avoir à remplir lui-même.

Entrée : $ARGUMENTS

## 1. Récupérer le texte de l'offre

- **Lien** : lis la page (WebFetch). Si elle exige une connexion (LinkedIn, portail) ou ne renvoie
  presque rien, demande à l'utilisateur de coller le texte de l'annonce. Ne contourne jamais un
  blocage.
- **Chemin de fichier** (PDF de TdR, AMI, avis) : lis le fichier.
- **Texte collé** : utilise-le tel quel.
- **Vide** : utilise les outils Gmail du connecteur claude.ai. Cherche les fils `label:a-ajouter`,
  lis chacun et traite chaque offre qu'il contient (lien, texte transféré, pièce jointe), comme
  ci-dessus. Une fois l'offre ajoutée, retire le libellé `a-ajouter` du fil et ajoute
  `a-ajouter/fait` (à créer s'il n'existe pas). Si les outils Gmail ne sont pas disponibles,
  dis-le et arrête-toi.

Un même document peut contenir plusieurs postes (lots d'un AMI, plusieurs profils) : une offre
par poste.

## 2. Extraire la fiche

Construis un JSON conforme à `ManualOfferIn` (`api/src/veille_api/manual.py`) :

| Champ | Règle |
|---|---|
| `url` | lien de la page de l'offre ; `null` pour un texte collé sans lien |
| `title` | intitulé exact du poste, dans la langue de l'offre |
| `organization` | employeur ou commanditaire (pour un projet : le projet, puis le bailleur entre parenthèses) |
| `location_text` | lieu tel qu'écrit dans l'offre |
| `country`, `city` | en français : `Madagascar`, `France`… ; `Antananarivo`, `Lille`… |
| `remote` | `true` seulement si l'offre l'indique (télétravail, home-based) |
| `contract_type` | `cdi`, `cdd`, `consultancy` (consultance individuelle, AMI/REOI), `roster`, `volunteer`, `internship`, `tender` (marché de cabinet), sinon `unknown` |
| `language` | `fr` ou `en` : langue de l'offre |
| `posted_at`, `deadline` | `AAAA-MM-JJ`, seulement si la date figure dans l'offre |
| `description` | texte complet de l'offre, nettoyé (sans menus ni mentions de cookies) : il sert au score et aux lettres |
| `contact_email` | adresse à laquelle envoyer la candidature, si l'offre en donne une |
| `apply_url` | lien du portail ou du formulaire, si la candidature passe par là |
| `provenance` | `lien`, `texte`, `pdf` ou `gmail` |

N'invente rien : un champ absent de l'offre reste `null`. Pas de date limite devinée.

## 3. Envoyer à l'API

Par défaut en production (`--prod`) ; en dev seulement si l'entrée contient `--dev` (retire alors
`--prod` des commandes). Écris le JSON dans un fichier temporaire, puis, depuis `api/` :

```bash
uv run python ../scripts/api.py --prod POST /offers/manual < offre.json
```

Si la réponse donne un `offer_id`, l'offre était déjà en base (trouvée par une autre source) :
utilise cet identifiant et passe à l'étape 5. Sinon, après toutes les offres de la série, lance
**un seul** traitement :

```bash
echo '{"job": "process"}' | uv run python ../scripts/api.py --prod POST /runs
```

## 4. Attendre la note

Pour chaque offre (avec l'`external_id` renvoyé à l'étape 3) :

```bash
uv run python ../scripts/api.py --prod --attendre GET /offers/manual/<external_id>
```

Si `duplicate_of` n'est pas nul, l'offre doublonne une offre déjà connue : utilise
`duplicate_of` comme identifiant.

## 5. Rendre compte

Le pipeline passe d'office les offres saisies à la main en « ça sent bon » : elles restent
affichées quel que soit leur score. Termine par une fiche courte par offre :

> **Intitulé** — Organisation · Lieu · type de contrat · date limite (ou « pas de date limite »)
> Score 0,xx · CV conseillé : … · Candidature : e-mail à … / portail … / à préciser

Puis propose de préparer la candidature avec `/candidatures <id>`.
