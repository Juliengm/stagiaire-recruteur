"""Dédoublonnage : empreinte exacte, puis similarité approximative titre / organisation."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from rapidfuzz import fuzz

THRESHOLD = 90
WINDOW_DAYS = 60


def normalize(text: str | None) -> str:
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def fingerprint(title: str, organization: str | None) -> str:
    return f"{normalize(title)}|{normalize(organization)}"


@dataclass(frozen=True)
class Candidate:
    id: int
    title: str
    organization: str | None
    seen: date  # date de publication, à défaut de première apparition


def is_similar(a: Candidate, b: Candidate) -> bool:
    """Titre ≥ 90 (set et sort) ET organisation ≥ 90, sur des scores séparés.

    Un score sur « titre + organisation » concaténés est gonflé par l'organisation commune :
    deux postes distincts d'IMPACT Initiatives (Amman / Dakar) atteignent 90,3. Une
    organisation manquante n'est jamais un indice de doublon.
    """
    if abs((a.seen - b.seen).days) > WINDOW_DAYS:
        return False
    org_a, org_b = normalize(a.organization), normalize(b.organization)
    if not org_a or not org_b:
        return False
    if fuzz.token_set_ratio(org_a, org_b) < THRESHOLD:
        return False
    title_a, title_b = normalize(a.title), normalize(b.title)
    # token_set_ratio vaut 100 dès qu'un titre contient l'autre, et 94 pour « Amman » / « Dakar » ;
    # token_sort_ratio (88 pour ce dernier cas) écarte les titres dont les mots diffèrent.
    return (fuzz.token_set_ratio(title_a, title_b) >= THRESHOLD
            and fuzz.token_sort_ratio(title_a, title_b) >= THRESHOLD)


def find_duplicates(offers: list[Candidate]) -> dict[int, int]:
    """Renvoie {id_doublon: id_de_l_offre_conservée}, la plus ancienne (id le plus petit) gardée."""
    keepers: list[Candidate] = []
    by_fingerprint: dict[str, Candidate] = {}
    result: dict[int, int] = {}
    for offer in sorted(offers, key=lambda o: o.id):
        key = fingerprint(offer.title, offer.organization)
        exact = by_fingerprint.get(key)
        if exact is not None and abs((exact.seen - offer.seen).days) <= WINDOW_DAYS:
            result[offer.id] = exact.id
            continue
        match = next((k for k in keepers if is_similar(k, offer)), None)
        if match is not None:
            result[offer.id] = match.id
            continue
        by_fingerprint[key] = offer
        keepers.append(offer)
    return result
