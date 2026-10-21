"""Normalisation d'une ligne « Choisir le service public »."""
import re
from datetime import datetime

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import canonicalize_url, detect_contract

_CONTRACT = [
    (r"\bcdi\b|titulaire|permanent", "cdi"),
    (r"\bcdd\b|contractuel|\d+ an|\d+ mois", "cdd"),
]


def _date(value: str | None):
    try:
        return datetime.strptime(value or "", "%d/%m/%Y").date()
    except ValueError:
        return None


def _contract(row: dict) -> str:
    text = f"{row.get('Nature de contrat', '')} {row.get('Nature de l\'emploi', '')}".lower()
    for pattern, kind in _CONTRACT:
        if re.search(pattern, text):
            return kind
    return detect_contract(row.get("Intitulé du poste", ""))


def normalize_csv_dataset(payload: dict, source: dict) -> Offer:
    ref = payload["Référence"]
    lieu = payload.get("Lieu d'affectation") or ""
    city = "Lille" if "lille" in lieu.lower() else None
    skills = " ".join(filter(None, (payload.get("Métier"), payload.get("Compétences attendues"))))
    return Offer(
        canonical_url=canonicalize_url(f"https://choisirleservicepublic.gouv.fr/offre-emploi/{ref}/"),
        title=payload["Intitulé du poste"].strip(),
        organization=payload.get("Organisme de rattachement") or payload.get("Employeur"),
        location_text=lieu or payload.get("Localisation du poste"),
        country="France",
        city=city,
        remote=bool(payload.get("Télétravail", "").strip()),
        contract_type=_contract(payload),
        language="fr",
        posted_at=_date(payload.get("Date de première publication")),
        deadline=_date(payload.get("Date de fin de publication par défaut")),
        description=skills or None,
    )
