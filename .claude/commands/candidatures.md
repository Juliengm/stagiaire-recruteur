---
description: Prépare les candidatures (e-mail, lettre de motivation, CV) des offres retenues et les range dans l'appli pour relecture
argument-hint: "[id d'offre …]  (vide : offres « ça sent bon » sans candidature)  [--dev] [--test]"
---

Tu prépares des candidatures pour Julien. **Tu n'envoies rien et tu ne touches pas à Gmail.**
Tu ranges chaque candidature dans l'appli (vue **Brouillons**). Julien y relit et corrige l'e-mail, la
lettre et le choix du CV, la dépose dans Gmail d'un clic, puis l'envoie lui-même depuis Gmail.
Le ton et les faits comptent plus que la vitesse.

Entrée : $ARGUMENTS

- `--dev` : API de dev (sinon production : `--prod` dans toutes les commandes `scripts/api.py`).
- `--test` : le destinataire est l'adresse de Julien, sans copie.

Commandes, depuis la racine du dépôt :

```bash
API="uv run --project api python scripts/api.py --prod"            # sans --prod si --dev
OUTIL="uv run --project api python scripts/candidature.py"
```

## 0. Lire les sources (une fois par exécution)

- `cv/faits.md` : **seule source de faits**, avec les CV. Tout ce qui n'y est pas n'est pas écrit.
- Le CV choisi (`cv/*.docx`, lis-le avec `pandoc <fichier> -t plain`).
- `$API GET /cvs` : noms des CV en PDF disponibles dans l'appli (le champ `cv_file`).

## 1. Mettre à jour les candidatures envoyées

```bash
echo '{}' | $API POST /drafts/sync
```

Cette commande passe en « postulé » les brouillons que Julien a envoyés depuis Gmail, avec une relance
à 10 jours. Si le résultat n'est pas nul, signale-le en une ligne.

## 2. Choisir les offres

Identifiants donnés : ceux-là. Sinon :
1. `$API GET "/offers?status=interesting"`, puis pour chacune `$API GET /offers/<id>` ;
2. écarte celles qui ont déjà une candidature (`application_ids` non vide) ou un brouillon
   (`$API GET /drafts`, champ `offer_id`) ;
3. garde-en cinq au plus, les mieux notées d'abord.

Une offre déjà traitée n'est refaite que si Julien a donné son identifiant.

Pour chaque offre, crée le dossier de travail `cv/candidatures/<AAAA-MM-JJ>_<Organisation>_<id>/` (hors
dépôt) et enregistre la réponse de `GET /offers/<id>` dans `offre.json`.

## 3. Décider

- **Langue** : celle de l'offre (`language`).
- **CV** : selon le tableau « Choix du CV » de `cv/faits.md`. Si l'offre demande un « CV détaillé » ou
  des références, prends le CV complet. Retiens le nom du PDF correspondant dans `GET /cvs`.
- **Segment** :
  - `tech` pour une ESN, un cabinet data ou IA, un éditeur de logiciels ou une start-up ;
  - `institutionnel` pour tout le reste (ONU, bailleurs, ONG, projets, ministères, cabinets d'études,
    grands groupes).
  En cas de doute : `institutionnel`.
- **Destinataire** : l'adresse que l'offre désigne pour les candidatures (`contact_emails`) ; en copie
  (`cc`), celles que l'offre demande de mettre en copie. Une candidature par portail (`apply_url`,
  formulaire, Workday, Inspira…) n'a pas de destinataire : `recipient` vide, `apply_url` renseigné.
- **Pièces exigées** : relève tout ce que l'offre demande en plus du CV et de la lettre (diplômes,
  attestations, références, formulaire). Tu ne peux pas les fournir : elles vont dans
  `required_documents`.
- **Points faibles** : les exigences de l'offre que les faits ne couvrent pas (années d'expérience dans
  un domaine précis, langue, diplôme), en une ou deux lignes, dans `weaknesses`. Sois franc : c'est ce
  qui aide Julien à décider s'il dépose.

**Candidature spontanée** (`contract_type` = `spontaneous`) : il n'y a pas d'annonce. La description
de l'offre contient la recherche sur l'organisation et le rôle proposé, et
`cv/candidatures/entreprises/<Organisation>.md` contient la recherche complète. Lis les deux. Le
destinataire est l'adresse RH trouvée (`contact_emails`), sinon le formulaire (`apply_url`). Si ni l'une
ni l'autre n'existe, laisse `recipient` et `apply_url` vides et dis-le dans `required_documents`
(« destinataire à trouver »).

## 4. Rédiger (en HTML simple)

Écris `email.html` et `lettre.html` dans le dossier de l'offre. N'utilise que les balises suivantes :
`<p>`, `<br>`, `<strong>`, `<em>`, `<ul>`/`<ol>`/`<li>`, `<a href>`. Pour aligner un paragraphe à droite,
utilise `style="text-align:right"`. C'est tout ce que l'éditeur de l'appli conserve.

**Lettre de motivation** : sérieuse et signée par Julien, quel que soit le segment. Structure :

```html
<p>Julien Gasser Morlay<br>Antananarivo, Madagascar · <téléphone> · <e-mail></p>
<p></p>
<p style="text-align:right"><Organisation><br><Service ou lieu, s'ils sont connus></p>
<p></p>
<p style="text-align:right"><Ville>, le <date du jour en toutes lettres></p>
<p><strong>Objet : candidature au poste de <intitulé exact> (<référence de l'offre, s'il y en a une>)</strong></p>
<p>Madame, Monsieur,</p>
<p>…3 ou 4 paragraphes…</p>
<p>Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.</p>
<p>Julien Gasser Morlay</p>
```

(En anglais : `Dear Hiring Manager,` … `Yours faithfully,`.)

Candidature spontanée : `Objet : candidature spontanée — <rôle proposé>`, sans référence.

Contenu des paragraphes :

1. **Le poste et pourquoi lui.** Une phrase d'accroche liée à l'offre, pas une banalité.
2. **Deux ou trois références précises** de `cv/faits.md`, choisies pour cette offre, avec leurs
   chiffres exacts. Pas une liste de compétences.
3. **Ce qu'il apporte à cette organisation** : un lien concret avec la mission décrite dans l'offre.
4. **Disponibilité et zone**, avec la formulation de `cv/faits.md`. Pour une offre à Lille, cite le lien
   avec Lille.

Candidature spontanée : le paragraphe 1 part d'un fait précis et daté de la recherche (un projet,
un engagement du rapport RSE, une exigence d'un bailleur), pas d'une annonce. Le paragraphe 3
propose le rôle et ce qu'il changerait concrètement pour l'organisation. Termine par une demande
d'échange plutôt que par une candidature à un poste. Un chiffre de l'entreprise n'est cité que s'il
figure dans la description de l'offre.

Règles :

- 250 à 330 mots ; une page au rendu.
- Pas de superlatifs ni de formules creuses (« passionné », « dynamique », « je suis convaincu que »).
- Les formulations imposées de `cv/faits.md` s'appliquent, notamment sur la réinstallation.

**Objet de l'e-mail** : **celui que l'offre impose, au caractère près**, s'il y en a un. Sinon
`Candidature — <intitulé exact> — Julien Gasser Morlay` (ajoute la référence de l'offre si elle existe).
Candidature spontanée : `Candidature spontanée — <rôle proposé> — Julien Gasser Morlay`.

**E-mail** (`email.html`), un `<p>` par paragraphe, la signature de `cv/faits.md` à la fin :

- Segment `institutionnel` : sobre, signé Julien, 5 à 8 lignes. Le poste, deux phrases sur ce qu'il
  apporte, la mention des pièces jointes (CV et lettre de motivation). Le lien GitHub seulement si le
  poste a une composante data.
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

  Candidature spontanée : remplace « J'ai trouvé la vôtre, il l'a lue » par « Il n'y a pas d'annonce :
  je me suis renseigné sur <organisation>, il a lu ce que j'ai trouvé ».

## 5. Pré-contrôler

```bash
$OUTIL verifier --offre <dossier>/offre.json --objet "<objet>" --email <dossier>/email.html \
  --lettre <dossier>/lettre.html --cv cv/pdf/<CV choisi>.pdf
$OUTIL lettre <dossier>/lettre.html <dossier>/apercu.pdf
```

- `verifier` signale :
  - `BLOQUANT` : un terme interdit ;
  - `À VÉRIFIER` : l'organisation ou l'intitulé absents, ou un nombre qu'on ne trouve ni dans les
    faits, ni dans le CV, ni dans l'offre.
  Corrige et relance. Si un avertissement est légitime (numéro de référence de l'offre, date), garde le
  texte et dis-le dans le compte rendu.
- `lettre` sort en erreur si la lettre dépasse une page : raccourcis.

L'appli refait ces contrôles au moment du dépôt, sur le texte que Julien aura modifié.

## 6. Ranger le brouillon dans l'appli

Écris le JSON dans `<dossier>/brouillon.json`, puis `$API POST /drafts < <dossier>/brouillon.json` :

```json
{"offer_id": <id>, "organization": "...", "position": "<intitulé exact>", "language": "fr",
 "segment": "institutionnel", "cv_file": "<PDF de GET /cvs>", "recipient": "<adresse ou null>",
 "cc": ["..."], "subject": "...", "email_html": "...", "letter_html": "...",
 "letter_filename": "LM_Julien_Gasser_Morlay_<Organisation>.pdf",
 "required_documents": "..." , "weaknesses": "...", "apply_url": "<lien du portail ou null>"}
```

`<Organisation>` dans le nom de fichier : lettres et chiffres sans accents, séparés par `_`.

## 7. Rendre compte

Une ligne par offre :

> **Intitulé** — Organisation · date limite · CV · segment · e-mail à … (ou : portail <lien>)
> Pièces à ajouter toi-même : … (s'il y en a)
> Points faibles : … (s'il y en a)

Termine par le lien de la vue Brouillons de l'appli (`INTERFACE_URL` de `.env.prod`, suivi de
`#/brouillons`). Rappelle que rien n'est parti : Julien relit, dépose dans Gmail depuis l'appli, puis
envoie lui-même depuis Gmail.
