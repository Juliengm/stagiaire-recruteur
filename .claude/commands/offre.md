---
description: Ajoute une offre au stagiaire à partir d'un lien, d'un texte collé, d'un PDF, ou des e-mails Gmail libellés « a-ajouter » ; ou une candidature spontanée, avec recherche sur l'entreprise et angles proposés
argument-hint: "[lien | chemin de PDF | texte collé | spontanée <entreprise ou lien>]  [--angle <ESG, data…>]  (vide : e-mails « a-ajouter »)  [--dev]"
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

**Candidature spontanée** : si l'entrée le dit (« spontanée », « spontaneous »), si la page est un
formulaire de candidature spontanée, ou si elle présente l'entreprise sans aucun poste, il n'y a pas
d'annonce à lire. Ne demande pas de texte : passe à la section 1 bis.

## 1 bis. Candidature spontanée : chercher, puis proposer des angles

Il n'y a pas de poste : c'est au stagiaire de trouver ce que Julien peut proposer à l'entreprise.

**Chercher.** Charge WebSearch avec ToolSearch, puis cherche et lis les pages utiles (WebFetch) :
- le site officiel : activités, filiales, implantations (Madagascar d'abord), chiffres publiés ;
- le rapport annuel, le rapport RSE / ESG / de durabilité, la politique environnementale et sociale ;
- les bailleurs et investisseurs (SFI, Proparco, BAD…) et leurs exigences E&S (NP SFI, plans d'action) ;
- la data et le numérique : outils, projets de transformation, équipes, offres d'emploi récentes ;
- l'actualité de moins de deux ans : projets, acquisitions, certifications, controverses ;
- les offres d'emploi en cours : elles disent ce qui manque à l'entreprise.

Note chaque fait **avec sa source (URL) et sa date**. Rien de deviné : un point non trouvé reste
« non trouvé ».

**Confronter à `cv/faits.md`.** Propose **deux ou trois angles**. Pour chacun :
- l'intitulé du rôle proposé, comme dans une annonce (« Chargé de données E&S / ESG ») ;
- le besoin de l'entreprise qu'il sert, avec la source ;
- les deux ou trois références de `cv/faits.md` qui le portent ;
- le CV à joindre, selon « Choix du CV » de `cv/faits.md` ;
- ce qui manque à Julien pour ce rôle, en une ligne.

Les angles nouveaux sont bienvenus (ESG / RSE, reporting extra-financier, données E&S, data,
suivi-évaluation), mais ils ne s'appuient que sur des faits du fichier. Julien n'a pas de CV ESG
dédié : pour un angle ESG, propose le CV le plus proche et dis-le.

Si l'entrée donne `--angle <thème>`, retiens l'angle correspondant. Sinon, demande à Julien
(AskUserQuestion, choix multiple) lesquels garder. C'est la seule question de la commande.

**Ranger la recherche.** Enregistre-la dans
`cv/candidatures/entreprises/<Organisation>.md` (hors dépôt ; `<Organisation>` en lettres et chiffres
sans accents, séparés par `_`). `/entretien` la reprendra et la complétera.

**Une offre par angle retenu**, avec les champs de la section 2, sauf :

| Champ | Règle |
|---|---|
| `url` | `null` : le formulaire est commun à toute l'entreprise, deux angles se confondraient |
| `title` | l'intitulé du rôle proposé, **sans** « candidature spontanée » (le contrat le dit déjà) |
| `contract_type` | `spontaneous` |
| `location_text`, `country`, `city` | l'implantation visée (Madagascar en priorité, sinon le siège) |
| `deadline`, `posted_at` | `null` |
| `description` | trois parties : **L'organisation** (ce que dit la recherche, sources et dates), **Rôle proposé** (le besoin et ce que Julien y apporte), **Sources** (les URL). Ce texte sert au score, puis aux lettres : les chiffres de l'entreprise qu'il contient pourront y être cités. |
| `contact_email` | une adresse RH trouvée sur le site, s'il y en a une |
| `apply_url` | le formulaire de candidature spontanée, s'il y en a un |
| `provenance` | `spontanée` |

Continue ensuite à la section 3.

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

Pour une candidature spontanée, remplace la date limite par « candidature spontanée » et ajoute
l'angle en une ligne, avec le chemin de la recherche.

Puis propose de préparer la candidature avec `/candidatures <id>`, et, une fois l'entretien obtenu,
le dossier avec `/entretien <id>`.
