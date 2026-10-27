---
description: Prépare le dossier d'entretien d'une offre (ou d'une candidature spontanée) : l'entreprise vue sous l'angle du poste, questions probables, réponses tirées des faits
argument-hint: "<id d'offre>  [--dev]"
---

Tu prépares Julien à un entretien. Tu cherches ce qu'il faut savoir de l'organisation **pour ce
poste**, et tu le relies à ce qu'il a fait. Tu n'envoies rien et tu ne touches pas à Gmail.

Entrée : $ARGUMENTS

```bash
API="uv run --project api python scripts/api.py --prod"            # sans --prod si --dev
```

## 1. Lire

- `$API GET /offers/<id>` : l'offre (ou, pour `contract_type` = `spontaneous`, la recherche sur
  l'organisation et le rôle proposé).
- `cv/faits.md` : **seule source de faits sur Julien**.
- Le dossier de la candidature dans `cv/candidatures/` (nom terminé par `_<id>`), s'il existe : la
  lettre et l'e-mail envoyés. L'entretien part de ce qui y est écrit.
- `cv/candidatures/entreprises/<Organisation>.md`, s'il existe : la recherche déjà faite (`/offre`
  pour une candidature spontanée, ou un entretien précédent avec la même organisation). Complète-la,
  ne la refais pas.

## 2. Chercher selon le poste

Charge WebSearch avec ToolSearch, puis cherche et lis les pages utiles (WebFetch). Toujours :
activités, implantations (Madagascar d'abord), taille, gouvernance, actualité de moins de deux ans,
offres d'emploi en cours. Puis, selon le poste :

| Poste | À chercher en plus |
|---|---|
| ESG, RSE, durabilité, E&S | dernier rapport RSE / ESG / de durabilité (cadres : GRI, CSRD, NP SFI, TCFD), matérialité, objectifs chiffrés et leur avancement, notations ESG, bailleurs et plans d'action E&S, controverses et griefs publics |
| Data, BI, plateforme, produit | stack et outils cités (offres d'emploi, blog, conférences), projets data ou de transformation numérique, organisation de l'équipe, produits et clients |
| Réinstallation, sauvegardes | projets en cours, PAR et EIES publiés (sites des bailleurs : SFI, Banque mondiale, BAD, AFD), mécanismes de plainte, normes appliquées |
| Suivi-évaluation, socio-économie | programmes, cadres de résultats, évaluations publiées, bailleurs, zones d'intervention |
| Candidature spontanée | le portrait général ci-dessus, plus ce qui justifie le rôle proposé |

Note chaque fait avec sa source (URL) et sa date. Un point non trouvé reste « non trouvé ». Si
l'entretien a lieu avec des personnes nommées, ne cherche que leur fonction et leur parcours
professionnel publics.

## 3. Rédiger le dossier

Écris `entretien.md` dans le dossier de la candidature (crée-le sur le modèle de `/candidatures` s'il
n'existe pas). Il se lit en dix minutes avant l'entretien :

1. **En bref** : cinq lignes sur l'organisation, ce qu'elle attend du poste, et l'angle de Julien.
2. **L'organisation** : les faits trouvés à l'étape 2, sourcés et datés, regroupés par thème.
3. **Sous l'angle du poste** : ce qui compte pour ce poste (pour un poste ESG, les engagements du
   rapport, ses manques visibles et les exigences des bailleurs ; pour un poste data, l'outillage
   et ses limites probables), et où Julien peut aider.
4. **Questions probables et éléments de réponse** : huit à douze questions, y compris les
   difficiles (les points faibles du brouillon, le départ d'Insuco, la mobilité, la rémunération).
   Chaque réponse s'appuie sur une référence de `cv/faits.md`, avec ses chiffres exacts, et suit les
   formulations imposées (réinstallation : le volet données, jamais la conduite).
5. **Histoires à raconter** : trois ou quatre références de `cv/faits.md` sous la forme
   situation, action, résultat, choisies pour ce poste.
6. **Questions à poser** : cinq ou six, tirées de la recherche (pas de question dont la réponse est
   sur leur site).
7. **Sources** : la liste des URL consultées, avec leur date.

Ajoute à `cv/candidatures/entreprises/<Organisation>.md` ce que la recherche a appris sur
l'organisation, pour la prochaine fois.

## 4. Rendre compte

Trois lignes : le chemin du dossier, les deux ou trois faits les plus utiles trouvés, et ce qui n'a
pas été trouvé (le rapport ESG, par exemple).
